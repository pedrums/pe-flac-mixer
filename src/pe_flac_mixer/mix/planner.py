"""Heuristischer Mix-Planer für den Proben-Grobmix."""

from dataclasses import asdict, dataclass

from pe_flac_mixer.analysis.analyzer import TrackAnalysis
from pe_flac_mixer.config import SetupConfig


@dataclass
class TrackMixParams:
    filename: str
    instrument: str
    group: str
    channel_type: str  # "mono" | "stereo"
    gain_db: float
    pan: float
    highpass_hz: float | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MasterMixParams:
    target_lufs: float = -14.0
    limiter_ceiling_db: float = -1.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MixPlan:
    setup_name: str
    tracks: dict[str, TrackMixParams]
    master: MasterMixParams

    def to_dict(self) -> dict:
        return {
            "setup_name": self.setup_name,
            "tracks": {k: v.to_dict() for k, v in self.tracks.items()},
            "master": self.master.to_dict(),
        }


# Ziel-Lautheiten (LUFS) für Instrumentengruppen im Übungsmix
TARGET_LUFS_BY_GROUP = {
    # Gesang differenziert: Lead klar im Vordergrund, Background dezent dahinter
    "vocals lead": -16.0,  # Lead-Gesang: präsent ganz vorne im Mix
    "lead vocals": -16.0,
    "lead vocal": -16.0,
    "lead": -16.0,
    "vocals background": -23.0,  # Background/Chor: aufgeräumt im Hintergrund
    "background vocals": -23.0,
    "backing vocals": -23.0,
    "background": -23.0,
    "backing": -23.0,
    "vocals": -18.0,  # Standard falls keine Unterscheidung getroffen wurde
    "vocal": -18.0,
    # Rhythmusgruppe & Instrumente
    "bass": -21.0,  # Fundament
    "drums": -21.0,
    "guitars": -23.0,  # Gitarren ausgewogen
    "guitar": -23.0,
    "keys": -23.0,
    "other": -23.0,
}

# Spezifische Ziel-Lautheiten nach Instrumenten-Name (überschreibt generische Gruppe)
TARGET_LUFS_BY_INSTRUMENT = {
    "kick": -19.0,
    "snare": -20.0,
    "snare top": -20.0,
    "snare bottom": -23.0,
    "snare under": -23.0,
    "hihat": -25.0,  # HiHat / Blech bewusst gezügelt
    "overheads": -24.0,
    "overhead left": -24.0,
    "overhead right": -24.0,
    "high tom": -22.0,
    "floor tom": -22.0,
}

# Highpass-Frequenzen zur Rumpel- und Mulmbefreiung
HIGHPASS_BY_INSTRUMENT = {
    "kick": 30.0,
    "bass": 35.0,
    "snare": 80.0,
    "snare top": 80.0,
    "snare bottom": 120.0,
    "snare under": 120.0,
    "hihat": 250.0,
    "overhead left": 200.0,
    "overhead right": 200.0,
    "overheads left": 200.0,
    "overheads right": 200.0,
    "high tom": 60.0,
    "floor tom": 45.0,
    "guitar": 90.0,
    "e-gitarre": 90.0,
    "a-gitarre": 100.0,
    "guitars": 90.0,
    "lead vocal": 100.0,
    "vocals": 100.0,
    "vocal": 100.0,
    "keyboard left": 70.0,
    "keyboard right": 70.0,
    "keyboards": 70.0,
    "keys": 70.0,
}


def generate_mix_plan(analyses: dict[str, TrackAnalysis], setup: SetupConfig) -> MixPlan:
    """Berechnet vollautomatisch die Gain-, Pan- und Filter-Werte für jeden Track."""
    tracks_plan: dict[str, TrackMixParams] = {}

    for filename, analysis in analyses.items():
        ch_cfg = setup.channels.get(filename)
        inst_name = ch_cfg.name if ch_cfg else analysis.instrument
        inst_lower = inst_name.lower().strip()
        group_lower = (ch_cfg.group if ch_cfg else analysis.group).lower().strip()
        ch_type = ch_cfg.type if ch_cfg else "mono"
        pan = ch_cfg.pan if ch_cfg else 0.0

        # 1. Highpass-Filter ermitteln
        highpass_hz = HIGHPASS_BY_INSTRUMENT.get(inst_lower)
        if highpass_hz is None:
            # Fallback über Gruppe
            if "lead" in group_lower:
                highpass_hz = 90.0
            elif "background" in group_lower or "backing" in group_lower:
                highpass_hz = 120.0
            elif "vocal" in group_lower:
                highpass_hz = 100.0
            elif "guitar" in group_lower:
                highpass_hz = 90.0
            elif "bass" in group_lower:
                highpass_hz = 35.0
            elif "drum" in group_lower:
                highpass_hz = 60.0
            else:
                highpass_hz = 50.0

        # 2. Ziel-Lautheit bestimmen
        # Gruppe hat bei differenziertem Gesang Vorrang vor generischem Instrumentennamen
        target_lufs = TARGET_LUFS_BY_GROUP.get(group_lower)
        if target_lufs is None:
            target_lufs = TARGET_LUFS_BY_INSTRUMENT.get(
                inst_lower, TARGET_LUFS_BY_GROUP.get("other", -23.0)
            )

        # 3. Gain ermitteln
        if analysis.is_silent or analysis.lufs <= -70.0:
            gain_db = 0.0
        else:
            raw_gain = target_lufs - analysis.lufs

            is_vocal = "vocal" in group_lower or "lead" in group_lower or "back" in group_lower
            is_lead = "lead" in group_lower

            # Gesang darf weiter angehoben werden (+24 dB), um im Mix präsent zu sein
            max_boost = 24.0 if is_vocal else 12.0
            gain_db = max(-24.0, min(max_boost, raw_gain))

            # Headroom-Prüfung:
            # Bei Instrumenten auf -1.0 dBFS Peak begrenzen.
            # Bei Vocals (besonders Lead) einzelne Pop-/Transienten-Peaks nicht den gesamten Pegel
            # abwürgen lassen; Float32-Summierung und Master-Limiter fangen Peaks sauber ab.
            max_allowed_track_peak = 4.0 if is_lead else (2.0 if is_vocal else -1.0)
            if analysis.peak_db + gain_db > max_allowed_track_peak:
                gain_db = max_allowed_track_peak - analysis.peak_db

        gain_db = round(float(gain_db), 2)
        pan = max(-1.0, min(1.0, float(pan)))

        tracks_plan[filename] = TrackMixParams(
            filename=filename,
            instrument=inst_name,
            group=group_lower,
            channel_type=ch_type,
            gain_db=gain_db,
            pan=pan,
            highpass_hz=highpass_hz,
        )

    return MixPlan(
        setup_name=setup.name,
        tracks=tracks_plan,
        master=MasterMixParams(target_lufs=-14.0, limiter_ceiling_db=-1.0),
    )

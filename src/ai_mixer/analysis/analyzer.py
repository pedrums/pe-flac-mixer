"""Audio-Analyse für Multitrack-Spuren."""

import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from ai_mixer.config import SetupConfig


@dataclass
class TrackAnalysis:
    filename: str
    instrument: str
    group: str
    sample_rate: int
    channels: int
    duration_sec: float
    peak_db: float
    rms_db: float
    lufs: float
    crest_factor_db: float
    is_silent: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _to_db(val: float, floor_db: float = -90.0) -> float:
    if val <= 1e-9:
        return floor_db
    return round(float(20.0 * math.log10(val)), 2)


def analyze_track(file_path: Path, filename: str, instrument: str, group: str) -> TrackAnalysis:
    """Analysiert eine einzelne FLAC/WAV-Datei und ermittelt Lautheitsmetriken."""
    with sf.SoundFile(str(file_path)) as f:
        sr = f.samplerate
        channels = f.channels
        frames = len(f)
        duration_sec = round(frames / sr, 2)

        # Schnelle Prüfung auf leere Datei
        if frames == 0:
            return TrackAnalysis(
                filename=filename,
                instrument=instrument,
                group=group,
                sample_rate=sr,
                channels=channels,
                duration_sec=0.0,
                peak_db=-90.0,
                rms_db=-90.0,
                lufs=-90.0,
                crest_factor_db=0.0,
                is_silent=True,
            )

        # Datei in Blöcken lesen, um Peak & Sum-of-Squares zu berechnen
        block_size = 65536
        peak_val = 0.0
        sum_sq = 0.0
        total_samples = frames * channels

        f.seek(0)
        while True:
            data = f.read(block_size, dtype="float32")
            if len(data) == 0:
                break
            block_peak = float(np.max(np.abs(data)))
            peak_val = max(peak_val, block_peak)
            sum_sq += float(np.sum(data**2))

        rms_val = math.sqrt(sum_sq / total_samples) if total_samples > 0 else 0.0

        peak_db = _to_db(peak_val)
        rms_db = _to_db(rms_val)
        crest_factor_db = round(peak_db - rms_db, 2)
        is_silent = rms_db < -70.0 or peak_db < -60.0

        # LUFS-Messung via pyloudnorm
        lufs = -90.0
        if not is_silent:
            try:
                # pyloudnorm benötigt das Signal im Speicher.
                # Falls Datei länger als 5 Minuten ist, analysieren wir für Speed & RAM
                # einen repräsentativen Ausschnitt (oder die ersten 5 Minuten).
                max_frames_to_read = min(frames, sr * 300)
                f.seek(0)
                audio_sample = f.read(max_frames_to_read, dtype="float32")
                meter = pyln.Meter(sr)
                measured_lufs = meter.integrated_loudness(audio_sample)
                if not (math.isinf(measured_lufs) or math.isnan(measured_lufs)):
                    lufs = round(float(measured_lufs), 2)
                else:
                    lufs = rms_db
            except Exception:
                lufs = rms_db
        else:
            lufs = -90.0

    return TrackAnalysis(
        filename=filename,
        instrument=instrument,
        group=group,
        sample_rate=sr,
        channels=channels,
        duration_sec=duration_sec,
        peak_db=peak_db,
        rms_db=rms_db,
        lufs=lufs,
        crest_factor_db=crest_factor_db,
        is_silent=is_silent,
    )


def analyze_tracks(matched_tracks: dict[str, Path], setup: SetupConfig) -> dict[str, TrackAnalysis]:
    """Analysiert alle zugeordneten Spuren."""
    results: dict[str, TrackAnalysis] = {}
    for filename, path in matched_tracks.items():
        ch_cfg = setup.channels.get(filename)
        instrument = ch_cfg.name if ch_cfg else filename
        group = ch_cfg.group if ch_cfg else "other"
        results[filename] = analyze_track(path, filename, instrument, group)
    return results

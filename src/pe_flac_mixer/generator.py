"""Setup generation by analyzing and guessing tracks from an audio directory."""

import re
from pathlib import Path

import soundfile as sf
import yaml

from pe_flac_mixer.config import ChannelConfig, SetupConfig


def natural_sort_key(path: Path):
    """Sort filenames naturally (01, 02, ..., 10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", path.name)]


def guess_track_channel(file_path: Path) -> ChannelConfig:
    """Infer channel configuration (name, group, type, pan) from audio metadata and filename."""
    # Determine mono / stereo from audio file if possible
    ch_type = "mono"
    try:
        info = sf.info(str(file_path))
        if info.channels >= 2:
            ch_type = "stereo"
    except Exception:
        pass

    stem = file_path.stem
    # Remove leading track indices like "01 ", "01-", "01_", "track_01 "
    cleaned = re.sub(r"^(?:track[_\s-]*)?\d+[\s._-]*", "", stem, flags=re.IGNORECASE).strip()
    if not cleaned:
        cleaned = stem

    # Normalize separators (underscores, dashes, dots) to spaces for regex word boundary matching
    s = re.sub(r"[-_.]+", " ", cleaned).lower()

    # Drums - Kick
    if re.search(r"\b(kick|bd|bassdrum|bass\s*drum)\b", s):
        return ChannelConfig(name="Kick", group="drums", type=ch_type, pan=0.0)

    # Drums - Snare bottom / under
    if re.search(r"\b(snare\s*u(nder)?|snare\s*bot(tom)?|sn\s*u|sn\s*bot)\b", s) or s.endswith(
        "snare u"
    ):
        return ChannelConfig(name="Snare Bottom", group="drums", type=ch_type, pan=0.0)

    # Drums - Snare top / general
    if re.search(r"\b(snare|sd)\b", s):
        return ChannelConfig(name="Snare Top", group="drums", type=ch_type, pan=0.0)

    # Drums - HiHat
    if re.search(r"\b(hi\s*hat|hihat|hh|hat)\b", s):
        return ChannelConfig(name="HiHat", group="drums", type=ch_type, pan=0.25)

    # Drums - Toms
    if re.search(r"\b(ht1?|high\s*tom|rack\s*tom|tom\s*1)\b", s):
        return ChannelConfig(name="High Tom", group="drums", type=ch_type, pan=-0.3)
    if re.search(r"\b(mt|mid\s*tom|tom\s*2)\b", s):
        return ChannelConfig(name="Mid Tom", group="drums", type=ch_type, pan=0.0)
    if re.search(
        r"\b(ft|st|floor\s*tom|stand\s*tom|standtom|low\s*tom|tom\s*3)\b",
        s,
    ):
        return ChannelConfig(name="Floor Tom", group="drums", type=ch_type, pan=0.35)
    if re.search(r"\btom\b", s):
        return ChannelConfig(name=cleaned.title(), group="drums", type=ch_type, pan=0.0)

    # Drums - Overheads / Cymbals
    if re.search(r"\b(ovh\s*l|oh\s*l|overhead\s*l|overheads\s*l)\b", s) or (
        "ovh" in s and s.endswith("l")
    ):
        return ChannelConfig(name="Overhead Left", group="drums", type=ch_type, pan=-0.75)
    if re.search(r"\b(ovh\s*r|oh\s*r|overhead\s*r|overheads\s*r)\b", s) or (
        "ovh" in s and s.endswith("r")
    ):
        return ChannelConfig(name="Overhead Right", group="drums", type=ch_type, pan=0.75)
    if re.search(r"\b(ovh|oh|overhead|overheads|cymbal|cymbals|ride|crash)\b", s):
        return ChannelConfig(name="Overheads", group="drums", type=ch_type, pan=0.0)

    # Drums - Percussion
    if re.search(r"\b(perc|percussion|conga|bongo|shaker|tamb)\b", s):
        return ChannelConfig(name="Percussion", group="drums", type=ch_type, pan=0.3)

    # Bass
    if re.search(r"\b(bass|e-bass|di\s*bass|bass\s*di)\b", s):
        return ChannelConfig(name="Bass", group="bass", type=ch_type, pan=0.0)

    # Acoustic Guitar
    if re.search(r"\b(a[-_\s]*git(arre)?|acoustic(\s*git)?|western)\b", s) or s.startswith(
        "a-gitarre"
    ):
        return ChannelConfig(name="A-Gitarre", group="guitars", type=ch_type, pan=0.45)

    # Electric Guitar
    if re.search(r"\b(e[-_\s]*git(arre)?|electric(\s*git)?)\b", s) or s.startswith("e-gitarre"):
        return ChannelConfig(name="E-Gitarre", group="guitars", type=ch_type, pan=-0.45)

    # Guitar general
    if re.search(r"\b(git|gitarre|guitar)\b", s):
        pan = -0.4 if ch_type == "mono" else 0.0
        return ChannelConfig(name=cleaned.title(), group="guitars", type=ch_type, pan=pan)

    # Keys / Keyboards / Piano
    if re.search(r"\b(key|keys|keyboard|keyboards|piano|synth|synthesizer|organ|orgel)\b", s):
        pan = 0.0
        name = "Keyboards"
        if ch_type == "mono":
            if s.endswith((" l", "left")) or cleaned.lower().endswith(("-l", "_l")):
                pan = -0.6
                name = "Keyboard Left"
            elif s.endswith((" r", "right")) or cleaned.lower().endswith(("-r", "_r")):
                pan = 0.6
                name = "Keyboard Right"
        return ChannelConfig(name=name, group="keys", type=ch_type, pan=pan)

    # Vocals
    if re.search(r"\b(voc|vocals|vocal|gesang|stimme|voice|mic)\b", s):
        name = cleaned.title()
        if "lead" in s or "main" in s:
            return ChannelConfig(name=name, group="vocals lead", type=ch_type, pan=0.0)
        if "back" in s or "bg" in s or "chor" in s or "harm" in s:
            return ChannelConfig(name=name, group="vocals background", type=ch_type, pan=0.25)
        # Undetermined vocal group
        return ChannelConfig(name=name, group="vocals", type=ch_type, pan=0.0)

    # Horns / Brass
    if re.search(r"\b(sax|saxophone|trompete|trumpet|posaune|trombone|horn)\b", s):
        return ChannelConfig(name=cleaned.title(), group="horns", type=ch_type, pan=0.3)

    # Fallback
    return ChannelConfig(name=cleaned.title(), group="other", type=ch_type, pan=0.0)


def generate_setup_from_directory(
    input_dir: Path,
    setup_name: str | None = None,
) -> SetupConfig:
    """Scans directory for FLAC files and creates a smart SetupConfig."""
    flac_files = [f for f in input_dir.iterdir() if f.is_file() and f.suffix.lower() == ".flac"]
    flac_files.sort(key=natural_sort_key)

    if not flac_files:
        raise ValueError(f"No FLAC files found in directory: {input_dir}")

    channels: dict[str, ChannelConfig] = {}
    for f in flac_files:
        channels[f.name] = guess_track_channel(f)

    # Pass 2: Refine Vocals and Guitars distribution
    vocal_keys = [k for k, ch in channels.items() if ch.group.startswith("vocals")]
    has_explicit_lead = any(channels[k].group == "vocals lead" for k in vocal_keys)

    # Background vocal pan offsets to cycle through
    bg_pans = [0.2, -0.2, 0.35, -0.35, 0.5, -0.5]
    bg_pan_idx = 0

    if vocal_keys:
        if not has_explicit_lead:
            # Assign first vocal as lead vocal
            lead_key = vocal_keys[0]
            channels[lead_key].group = "vocals lead"
            channels[lead_key].pan = 0.0

            # Remaining vocals become background vocals
            for k in vocal_keys[1:]:
                channels[k].group = "vocals background"
                channels[k].pan = bg_pans[bg_pan_idx % len(bg_pans)]
                bg_pan_idx += 1
        else:
            # Assign pan offsets to remaining background vocals
            for k in vocal_keys:
                if channels[k].group == "vocals background" and channels[k].pan == 0.0:
                    channels[k].pan = bg_pans[bg_pan_idx % len(bg_pans)]
                    bg_pan_idx += 1

    # Balance mono guitars if both centered
    mono_guitars = [
        k
        for k, ch in channels.items()
        if ch.group == "guitars" and ch.type == "mono" and ch.pan == 0.0
    ]
    if len(mono_guitars) == 2:
        channels[mono_guitars[0]].pan = -0.45
        channels[mono_guitars[1]].pan = 0.45

    name = setup_name or input_dir.name
    return SetupConfig(
        name=name,
        description=f"Auto-generated setup for {name} from {input_dir.name} - Please review and adjust",
        channels=channels,
    )


def save_setup_file(setup: SetupConfig, output_path: Path, overwrite: bool = False) -> Path:
    """Exports SetupConfig to a YAML file with formatted output."""
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"File already exists: {output_path}. Use --force / -f to overwrite.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "name": setup.name,
        "description": setup.description,
        "channels": {},
    }

    for filename, ch in setup.channels.items():
        ch_dict = {
            "name": ch.name,
            "group": ch.group,
            "type": ch.type,
        }
        if ch.type == "mono":
            ch_dict["pan"] = round(ch.pan, 2)
        elif ch.width != 1.0:
            ch_dict["width"] = round(ch.width, 2)

        data["channels"][filename] = ch_dict

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True)

    return output_path

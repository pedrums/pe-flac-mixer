"""Configuration and setup management for pe-flac-mixer."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml


def normalize_path(path_input: str | Path | None) -> Path | None:
    """
    Normalizes a path string or Path object.
    Supports Windows-style paths on Linux/WSL:
    Converts 'E:\\path\\to\\dir' or 'E:/path' to '/mnt/e/path/to/dir'.
    """
    if path_input is None:
        return None
    p_str = str(path_input).strip().strip("'\"")
    if not p_str:
        return None

    # Handle unescaped backslashes in shell/make arguments (e.g. E:\data2\...)
    # Replace backslashes with forward slashes first
    p_str = p_str.replace("\\", "/")

    # Check for Windows drive letter e.g. E:/ or E:path
    m = re.match(r"^([a-zA-Z]):[ /]?(.*)$", p_str)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2).lstrip("/")
        p_str = f"/mnt/{drive}/{rest}" if rest else f"/mnt/{drive}"

    return Path(p_str).expanduser()


@dataclass
class ChannelConfig:
    name: str
    group: str
    type: Literal["mono", "stereo"] = "mono"
    pan: float = 0.0  # -1.0 (hard left) to 1.0 (hard right), 0.0 = Center
    width: float = 1.0  # Stereo width for stereo tracks (1.0 = normal)


@dataclass
class SetupConfig:
    name: str
    description: str = ""
    channels: dict[str, ChannelConfig] = field(default_factory=dict)


def load_setup(setup_name_or_path: str, setups_dir: Path | None = None) -> SetupConfig:
    """Loads a mixer setup from a YAML file or by setup name."""
    norm = normalize_path(setup_name_or_path)
    path = norm if norm else Path(setup_name_or_path)

    # 1. Direct path to file
    if not path.is_file():
        # 2. Search in setups/
        base_dir = setups_dir or (Path.cwd() / "setups")
        candidate1 = base_dir / f"{setup_name_or_path}.yml"
        candidate2 = base_dir / f"{setup_name_or_path}.yaml"

        if candidate1.is_file():
            path = candidate1
        elif candidate2.is_file():
            path = candidate2
        else:
            raise FileNotFoundError(
                f"Setup '{setup_name_or_path}' not found (neither as direct file nor in {base_dir})."
            )

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    channels: dict[str, ChannelConfig] = {}
    for filename, cfg in data.get("channels", {}).items():
        channels[filename] = ChannelConfig(
            name=cfg.get("name", filename),
            group=cfg.get("group", "other").lower(),
            type=cfg.get("type", "mono").lower(),
            pan=float(cfg.get("pan", 0.0)),
            width=float(cfg.get("width", 1.0)),
        )

    return SetupConfig(
        name=data.get("name", path.stem),
        description=data.get("description", ""),
        channels=channels,
    )


def validate_and_match_tracks(
    input_dir: Path, setup: SetupConfig
) -> tuple[dict[str, Path], list[str], list[str]]:
    """
    Prüft die Audio-Dateien im Aufnahmeverzeichnis gegen das Setup.

    Returns:
        matched: dict[Dateiname im Setup -> tatsächlicher Path]
        missing: list[Dateinamen, die im Setup stehen aber fehlen]
        unknown: list[Dateinamen von FLAC/WAV-Dateien, die nicht im Setup vorkommen]
    """
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Eingabeverzeichnis nicht gefunden: {input_dir}")

    # Alle Audio-Dateien im Verzeichnis finden (case-insensitive Match ermöglichen)
    existing_files: dict[str, Path] = {}
    for p in input_dir.iterdir():
        if p.is_file() and p.suffix.lower() in [".flac", ".wav"]:
            existing_files[p.name] = p
            existing_files[p.name.lower()] = p

    matched: dict[str, Path] = {}
    missing: list[str] = []

    for filename in setup.channels:
        if filename in existing_files:
            matched[filename] = existing_files[filename]
        elif filename.lower() in existing_files:
            matched[filename] = existing_files[filename.lower()]
        else:
            missing.append(filename)

    # Unbekannte Spuren identifizieren
    matched_paths = set(matched.values())
    unknown: list[str] = [
        p.name
        for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in [".flac", ".wav"] and p not in matched_paths
    ]

    return matched, missing, sorted(unknown)

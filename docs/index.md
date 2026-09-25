# pe-flac-mixer

Automatic rough mix generator for band rehearsals and live recordings from FLAC multitrack files (e.g., recorded on a Soundcraft Ui24R digital mixer).

## Features

- **No external AI / No internet required:** 100% local, rule-based audio engineering expert system.
- **Channel mapping via setups or Soundcraft .uirecsession:** FLAC files are mapped to instruments via YAML configuration files (`setups/probe.yml`, `setups/gig.yml`) or automatically via Soundcraft Ui24R `.uirecsession` files present in the recording folder.
- **Lead vs. Background Vocals:** Clear layering – lead vocals are prominent in the mix (-14 LUFS target), background vocals sit subtly behind.
- **Automatic file naming:** The mix takes the exact name of the input recording directory (e.g., `260915_0014_ZuFuss.mp3`).
- **Mono/Stereo & Panning:** Mono tracks are cleanly positioned across the stereo image; true stereo tracks are preserved.
- **High-pass filtering:** Cuts rumble and low-frequency handling noise tailored to each instrument type.
- **Auto-gain & Loudness balancing:** Consistent and balanced track levels.
- **Subgroup processing:** Separate compression and reverb for **Drums** and **Vocals** subgroups, creating a polished, natural-sounding mix with controlled dynamics and spacious reverb.
- **Master limiter & Normalization:** Exports punchy, distortion-free mixes in MP3 and FLAC (-14 LUFS integrated loudness, -0.5 dBFS true-peak ceiling).

## Configuration (.env)

You can define default values by copying `.env.example` to `.env`:

```env
SETUP=probe
RECORDS=/path/to/hidrive/rehearsals/2026
SOURCE=Probe_2026-09-15
```

This allows `make` commands to pick up these defaults automatically (e.g. `make mix` or `make bulk`).

## Per-Track Setup Overrides (Bulk Mode)

When running bulk mixes, you can override the setup for individual tracks by placing a setup file directly in the track directory. The mixer automatically detects any file matching `setup*.yml` or `setup*.yaml` (e.g., `setup.yml`, `setup_Mattl.yml`, `setup_custom.yml`). This is useful when one song has a different vocalist or requires different mixing parameters.

**Example:** If one track needs different vocal settings:

```
records/2026/
├── Song_01/
│   ├── 01 KICK.flac
│   ├── 02 SNARE.flac
│   ├── 11 VOC.flac
│   └── setup_Matscher.yml      # Auto-detected local setup override!
├── Song_02/
│   ├── 01 KICK.flac
│   ├── 02 SNARE.flac
│   ├── 11 VOC GUEST.flac
│   └── setup_Mattl.yml         # Different vocalist, different setup
└── Song_03/
    ├── 01 KICK.flac
    ├── 02 SNARE.flac
    └── 11 VOC.flac
```

Run bulk mixing – each subdirectory's local `setup*.yml` file is automatically detected and used:

```bash
uv run pe-flac-mixer mix ./records/2026 --bulk --setup probe
```

Output will show which setup was used for each track:
```
▶ Processing track directory: Song_01
  Using local setup override: setup_Matscher.yml

▶ Processing track directory: Song_02
  Using local setup override: setup_Mattl.yml

▶ Processing track directory: Song_03
  Using global setup: probe
```

### Customizing Mix Levels per Setup

Each setup file (global or local) can define custom target loudness levels per track group. This allows fine-tuning the mix for different performers or styles:

```yaml
name: Setup for Guest Vocalist
description: Adjusted levels for guest vocalist performance

# Target loudness levels per group (in LUFS)
group_levels:
  vocals lead: -12.0      # Guest vocals 2 dB louder
  vocals background: -24.0
  drums: -20.0
  bass: -20.0
  guitars: -23.0
  keys: -23.0
  other: -23.0

channels:
  "01 KICK.flac":
    ...
```

If `group_levels` is not specified in the setup, the default values from the code are used.

## Installation

Ensure [uv](https://github.com/astral-sh/uv) is installed:

```bash
uv sync
```

## Usage

```bash
# Generate rough mix (defaults to probe setup):
uv run pe-flac-mixer mix ./aufnahme

# Or specify a setup explicitly:
uv run pe-flac-mixer mix ./aufnahme --setup probe

# Bulk render a whole directory of rehearsal sessions (e.g. all subfolders in RECORDS):
uv run pe-flac-mixer mix ./records/2026 --bulk --setup probe

# Run analysis only (inspect levels & LUFS without rendering):
uv run pe-flac-mixer analyze ./aufnahme --setup probe

# Auto-generate a new setup from a directory with FLAC files:
uv run pe-flac-mixer create-setup --source ./aufnahme --name my_band
```

Or using `make`:

```bash
make mix INPUT=./aufnahme
make bulk RECORDS=./records SOURCE=2026 SETUP=probe
make analyze INPUT=./aufnahme
make create-setup SOURCE=./aufnahme NAME=my_band
```

## Output Files

Each mix run produces:

- **`{song_name}.mp3`** – Final mixed audio (192 kbps, -14 LUFS, -0.5 dBFS ceiling)
- **`{song_name}_analysis.json`** – Track analysis data (stored in input directory alongside FLAC files)
- **`{song_name}_mix_plan.json`** – Complete mix plan with all channel parameters (gain, pan, highpass, group assignments)

The mix plan JSON is useful for:
- Auditing the mixer's decisions
- Reproducing exact mixes
- Troubleshooting or manual adjustments

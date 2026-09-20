# pe-flac-mixer

Automatic rough mix generator for band rehearsals and live recordings from FLAC multitrack files (e.g., recorded on a Soundcraft Ui24R digital mixer).

## Features

- **No external AI / No internet required:** 100% local, rule-based audio engineering expert system.
- **Channel mapping via setups:** FLAC files are mapped to instruments via YAML configuration files (`setups/probe.yml`, `setups/gig.yml`).
- **Lead vs. Background Vocals:** Clear layering – lead vocals are prominent in the mix (-16 LUFS target), background vocals sit subtly behind.
- **Automatic file naming:** The mix takes the exact name of the input recording directory (e.g., `260915_0014_ZuFuss.mp3`).
- **Mono/Stereo & Panning:** Mono tracks are cleanly positioned across the stereo image; true stereo tracks are preserved.
- **High-pass filtering:** Cuts rumble and low-frequency handling noise tailored to each instrument type.
- **Auto-gain & Loudness balancing:** Consistent and balanced track levels.
- **Master limiter & Normalization:** Exports punchy, distortion-free mixes in MP3 and FLAC (-14 LUFS integrated loudness, -1.0 dBFS true-peak ceiling).

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

# Run analysis only (inspect levels & LUFS without rendering):
uv run pe-flac-mixer analyze ./aufnahme --setup probe

# Auto-generate a new setup from a directory with FLAC files:
uv run pe-flac-mixer create-setup --source ./aufnahme --name my_band
```

Or using `make`:

```bash
make mix INPUT=./aufnahme
make analyze INPUT=./aufnahme
make create-setup SOURCE=./aufnahme NAME=my_band
```

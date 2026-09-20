# Auto-Mixer (Rough Mix Tool for Band Rehearsals)

## Objective

This tool serves a concrete, pragmatic purpose:
**Directly after a band rehearsal, automatically, quickly, and reliably create a clean rough mix (MP3 / FLAC) for practice from digital mixer multitrack FLAC stems.**

No over-engineering, no external APIs, no bloated plug-in chains:
* Vocals should be immediately clear and intelligible.
* Drums and cymbals should not be piercing or harsh.
* Bass and guitars should be cleanly separated and audible.
* Fully processed in seconds and ready to listen as MP3.

---

# 1. The KISS Principle (Keep It Simple & Solid)

A great practice rough mix needs only five core steps:

1. **Channel Mapping:** Which FLAC file corresponds to which instrument? (configured via YAML setup).
2. **High-pass Filtering:** Cut low-end rumble and boominess on vocal, guitar, and snare microphones.
3. **Panning:** Spread mono tracks logically across the stereo field (Vocals, Kick, Snare, Bass centered; Guitars/Overheads panned L/R).
4. **Gain Staging (Loudness Balance):** Level tracks so vocals sit on top and no instrument drowns out the others.
5. **Master Limiter & Normalization:** Deliver a solid master level (e.g. -14 LUFS / -1.0 dBFS Peak Ceiling) so recordings play back loud and clear without clipping in the car or on smartphones.

---

# 2. Workflow

```text
Rehearsal FLAC files (e.g. ./aufnahme)
      │
      ▼
Load setup (setups/probe.yml)
      │  validates tracks, mono/stereo & pan settings
      ▼
Fast level & loudness analysis
      │  (Peak, RMS, LUFS)
      ▼
Heuristic mix plan (mix.json)
      │  - Gain per track (vocals slightly in the foreground)
      │  - High-pass filter (30–120 Hz)
      │  - Panning
      ▼
DSP Summing & Master Limiter
      │
      ▼
Rendered practice mix:
      ├── <name>.mp3   (for smartphone / band chat)
      ├── <name>.flac  (lossless)
      └── <name>.json  (applied mix plan & parameters)
```

---

# 3. Setup Configuration (`setups/probe.yml`)

Configure once which audio file corresponds to which instrument and whether it is mono or stereo:

```yaml
name: Schlappseil
description: Probe-Setup für Schlappseil (Digitalmixer 18-Kanal Multitrack)

channels:
  "01 KICK.flac":
    name: Kick
    group: drums
    type: mono
    pan: 0.0

  "02 SNARE.flac":
    name: Snare Top
    group: drums
    type: mono
    pan: 0.0

  "03 SNARE U.flac":
    name: Snare Bottom
    group: drums
    type: mono
    pan: 0.0

  "04 HIHAT.flac":
    name: HiHat
    group: drums
    type: mono
    pan: 0.25

  "05 HT1.flac":
    name: High Tom
    group: drums
    type: mono
    pan: -0.3

  "06 STANDTOM.flac":
    name: Floor Tom
    group: drums
    type: mono
    pan: 0.35

  "07 OVH L.flac":
    name: Overhead Left
    group: drums
    type: mono
    pan: -0.75

  "08 OVH R.flac":
    name: Overhead Right
    group: drums
    type: mono
    pan: 0.75

  "09 BASS.flac":
    name: Bass
    group: bass
    type: mono
    pan: 0.0

  "10 E-GITARRE.flac":
    name: E-Gitarre
    group: guitars
    type: mono
    pan: -0.45

  "11 VOC MATSCHER.flac":
    name: Vocals Matscher
    group: vocals lead
    type: mono
    pan: -0.2

  "12 VOC MATTEL.flac":
    name: Vocals Mattel
    group: vocals background
    type: mono
    pan: 0.2

  "13 VOC ZILLE.flac":
    name: Vocals Zille
    group: vocals background
    type: mono
    pan: -0.35

  "14 VOC TORSTEN.flac":
    name: Vocals Torsten
    group: vocals background
    type: mono
    pan: 0.35

  "15 VOC PETER.flac":
    name: Vocals Peter (Lead)
    group: vocals background
    type: mono
    pan: 0.0

  "16 A-GITARRE.flac":
    name: A-Gitarre
    group: guitars
    type: mono
    pan: 0.45

  "19 TORSTENKEY-L.flac":
    name: Keyboard Left
    group: keys
    type: mono
    pan: -0.6

  "20 TORSTENKEY-R.flac":
    name: Keyboard Right
    group: keys
    type: mono
    pan: 0.6
```

---

# 4. Standard Mixing Rules

The planner (`planner.py`) applies simple, proven mixing heuristics:

| Group / Instrument  | Highpass (Hz) | Relative Loudness Target | Panning |
|---------------------|---------------|--------------------------|---------|
| **Lead Vocal**      | 90–100 Hz     | -16 LUFS (prominent)     | Center / Lead Pan |
| **Backing Vocals**  | 120 Hz        | -23 LUFS (subtle)        | L / R   |
| **Kick**            | 30 Hz         | Baseline (-19 LUFS)      | Center  |
| **Snare Top**       | 80 Hz         | -20 LUFS                 | Center  |
| **HiHat / OH**      | 200–250 Hz    | -24 to -25 LUFS (smooth) | L / R   |
| **Bass**            | 35 Hz         | Low-end foundation       | Center  |
| **Guitars**         | 90–100 Hz     | Balanced in rhythm       | L / R   |
| **Keys**            | 70 Hz         | Subtle in stereo field   | L / R   |

---

# 5. Audio Engine (Lean & Fast)

No heavy audio processing frameworks required:
* **`soundfile`:** Fast reading and writing of FLAC, WAV, and MP3 files.
* **`scipy.signal`:** Biquad second-order Butterworth high-pass filters (fast and phase-stable SOS implementation).
* **`numpy`:** Vectorized gain staging, panning, and block-based summing.
* **`pyloudnorm`:** Industry-standard ITU-R BS.1770-4 loudness measurement (LUFS).
* **Master Limiter:** Fast peak limiter with smooth release to prevent digital clipping.

---

# 6. Usage

Simple one-liner after band practice:

```bash
make mix INPUT=/path/to/rehearsal
```

Or directly via CLI:

```bash
uv run pe-flac-mixer mix ./aufnahme
```

Auto-generate a new setup from an audio recording directory:

```bash
uv run pe-flac-mixer create-setup --source ./aufnahme --name my_band
# or via make:
make create-setup SOURCE=./aufnahme NAME=my_band
```

Output files in `./output`:
* `<name>.mp3` $\to$ Ready to share in the band group chat!
* `<name>.flac` $\to$ Lossless audio archive
* `<name>.json` $\to$ Applied mix parameters

---

# 7. Project Structure

```text
pe-flac-mixer/
├── pyproject.toml
├── Makefile
├── README.md
├── pe-flac-mixer.md
│
├── setups/
│   ├── probe.yml
│   └── gig.yml
│
├── src/
│   └── pe_flac_mixer/
│       ├── __init__.py
│       ├── cli.py             # CLI with Typer & Rich
│       ├── config.py          # Setup loader & validation
│       ├── generator.py       # Setup auto-generation & guessing
│       │
│       ├── analysis/
│       │   ├── __init__.py
│       │   └── analyzer.py    # Peak, RMS, LUFS
│       │
│       └── mix/
│           ├── __init__.py
│           ├── planner.py     # Heuristic mix planner
│           ├── dsp.py         # Filters, panning, gain, limiter
│           └── renderer.py    # Block-based summing & audio export
│
└── tests/
    └── test_mixer.py
```

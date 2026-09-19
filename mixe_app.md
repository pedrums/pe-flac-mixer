# Auto-Mixer (Grobmix-Tool für Bandproben)

## Ziel

Dieses Tool hat einen ganz konkreten, pragmatischen Zweck:
**Direkt nach der Bandprobe aus den FLAC-Einzelspuren des Digitalmixers vollautomatisch, schnell und zuverlässig einen sauberen Grobmix (MP3 / FLAC) zum Üben zu erzeugen.**

Kein Over-Engineering, keine externen APIs, keine komplizierten Plug-in-Chains:
* Gesang soll sofort verständlich sein.
* Drums / Becken sollen nicht in den Ohren wehtun.
* Bass und Gitarren sollen sauber hörbar sein.
* In wenigen Sekunden fertig gerechnet und als MP3 anhörbereit.

---

# 1. Das „KISS“-Prinzip (Keep It Simple & Solid)

Ein perfekter Übungs-Grobmix braucht im Kern nur 5 Dinge:

1. **Kanal-Zuordnung:** Welcher FLAC-Dateiname ist welches Instrument? (per YAML-Setup)
2. **Trittschallfilter (Highpass):** Rumpeln und Dröhnen auf Gesangs-, Gitarren- und Snaremikrofonen abschneiden.
3. **Panning:** Mono-Spuren sinnvoll im Stereobild verteilen (Vocals, Kick, Snare, Bass Center; Gitarren/Overheads dezent L/R).
4. **Gain-Staging (Lautheits-Balance):** Spuren so einpegeln, dass Gesang gut durchkommt und nichts übertönt wird.
5. **Master-Limiter & Normalisierung:** Ein sauberer Summenpegel (z. B. -14 LUFS / -1 dB True Peak), damit der Mitschnitt auf dem Smartphone oder im Auto angenehm laut und ohne Übersteuerung abgespielt werden kann.

---

# 2. Workflow

```text
FLAC-Dateien der Probe (z.B. ./aufnahme)
      │
      ▼
Setup laden (setups/probe.yml)
      │  prüft: Sind alle Spuren da? Mono/Stereo & Pan
      ▼
Schnelle Pegel- & Lautheitsanalyse
      │  (Peak, RMS, LUFS)
      ▼
Heuristischer Mixplan (mix.json)
      │  - Gain pro Spur (Vocals leicht im Vordergrund)
      │  - Highpass-Filter (30–120 Hz)
      │  - Panning
      ▼
DSP Summing & Master Limiter
      │
      ▼
Fertiger Übungsmix:
      ├── mix.mp3   (fürs Smartphone / Band-Chat)
      ├── mix.flac  (unkomprimiert)
      └── mix.json  (angewandte Pegel)
```

---

# 3. Setup-Datei (`setups/probe.yml`)

Hier wird einmalig festgelegt, welche Datei zu welchem Instrument gehört und ob sie Mono oder Stereo ist:

```yaml
name: Probe

channels:
  KICK.flac:
    name: Kick
    group: drums
    type: mono
    pan: 0.0

  SNARE.flac:
    name: Snare
    group: drums
    type: mono
    pan: 0.0

  HH.flac:
    name: HiHat
    group: drums
    type: mono
    pan: 0.25

  OH_L.flac:
    name: Overheads Left
    group: drums
    type: mono
    pan: -0.7

  OH_R.flac:
    name: Overheads Right
    group: drums
    type: mono
    pan: 0.7

  BASS.flac:
    name: Bass
    group: bass
    type: mono
    pan: 0.0

  GIT.flac:
    name: Guitar
    group: guitars
    type: mono
    pan: -0.4

  GIT2.flac:
    name: Guitar 2
    group: guitars
    type: mono
    pan: 0.4

  KEYS.flac:
    name: Keyboards
    group: keys
    type: stereo

  VOC.flac:
    name: Lead Vocal
    group: vocals
    type: mono
    pan: 0.0
```

---

# 4. Standard-Mischregeln für den Proben-Grobmix

Der Planer (`planner.py`) verwendet einfache, praxiserprobte Standardregeln:

| Gruppe / Instrument | Highpass (Hz) | Lautheits-Ziel relativ | Panning |
|---------------------|---------------|------------------------|---------|
| **Lead Vocal**      | 100 Hz        | +2 dB (präsent im Mix) | Center  |
| **Kick**            | 30 Hz         | Basis (Referenz)       | Center  |
| **Snare**           | 80 Hz         | -1 dB                  | Center  |
| **HiHat / OH**      | 250 Hz        | -4 dB bis -6 dB (weich)| L / R   |
| **Bass**            | 35 Hz         | Fundament              | Center  |
| **Gitarren**        | 90 Hz         | Ausgewogen im Rhythmus | L / R   |
| **Keys**            | 80 Hz         | Dezent im Stereobild   | Stereo  |

---

# 5. Audio-Engine (Schlank & Schnell)

Keine tonnenschweren Frameworks:
* **`soundfile`:** Zum schnellen Lesen/Schreiben von FLAC, WAV und MP3.
* **`scipy.signal`:** Biquad Highpass-Filter (Butterworth 2. Ordnung) – extrem schnell und phasenstabil.
* **`numpy`:** Vektorisierte Lautstärke-Anpassung, Panning und Summenbildung.
* **`pyloudnorm`:** Standardmäßige Lautheitsmessung (LUFS).
* **Master-Limiter:** Schneller Peak-Limiter gegen Clipping.

---

# 6. Bedienung

Einfacher One-Liner nach der Probe:

```bash
make mix INPUT=/pfad/zur/probe SETUP=probe
```

oder direkt per CLI:

```bash
uv run ai-mixer mix ./aufnahme --setup probe
```

Ergebnis in `./output`:
* `mix.mp3` $\to$ fertig zum Teilen in der Band-Gruppe!
* `mix.flac` $\to$ unkomprimiert
* `mix.json` $\to$ Mixplan

---

# 7. Projektstruktur

```text
ai-mixer/
├── pyproject.toml
├── Makefile
├── README.md
│
├── setups/
│   ├── probe.yml
│   └── gig.yml
│
├── src/
│   └── ai_mixer/
│       ├── __init__.py
│       ├── cli.py             # CLI mit Typer
│       ├── config.py          # Setup-Lader & Validierung
│       │
│       ├── analysis/
│       │   ├── __init__.py
│       │   └── analyzer.py    # Peak, RMS, LUFS
│       │
│       └── mix/
│           ├── __init__.py
│           ├── planner.py     # Heuristischer Planer
│           ├── dsp.py         # Filter, Pan, Gain, Limiter
│           └── renderer.py    # Chunked Summing & Audio-Export
│
└── tests/
    └── test_mixer.py
```

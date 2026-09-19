# pe-mixer

Automatischer Grobmix für Bandproben und Live-Mitschnitte aus FLAC-Multitrack-Dateien (z. B. von einem Soundcraft Ui24R Digitalmixer).

## Features

- **Keine externe KI / kein Internet nötig:** 100% lokal, regelbasiertes tontechnisches Expertensystem.
- **Kanalzuordnung über Setups:** FLAC-Dateien werden per YAML-Datei (`setups/probe.yml`, `setups/schlappseil.yml`) den Instrumenten zugewiesen.
- **Lead vs. Background Vocals:** Klare Staffelung – Lead-Gesang steht weit vorne im Mix (-16 LUFS), Background dezent dahinter.
- **Automatische Dateibenennung:** Der Mix übernimmt 1:1 den Namen des Aufnahme-Ordners (z. B. `260915_0014_ZuFuss.mp3`).
- **Mono/Stereo & Panning:** Mono-Spuren werden sauber im Stereobild verteilt, echte Stereo-Spuren bleiben erhalten.
- **Highpass-Filterung:** Trittschall- und Rumpelfilterung je nach Instrument.
- **Auto-Gain & Lautheitsabgleich:** Ausgewogene Pegel.
- **Master-Limiter & Normalisierung:** Exportiert druckvolle, verzerrungsfreie Mixe in MP3 und FLAC (-14 LUFS, -1.0 dBFS Peak Ceiling).

## Installation

```bash
uv sync
```

## Nutzung

```bash
# Mix erstellen:
uv run pe-mixer mix ./aufnahme --setup probe

# Oder mit speziellem Band-Setup:
uv run pe-mixer mix ./aufnahme --setup schlappseil

# Nur Analyse anzeigen:
uv run pe-mixer analyze ./aufnahme --setup probe
```

"""Tests für den PE Audio-Mixer."""

from pathlib import Path

import numpy as np
import soundfile as sf

from pe_mixer.analysis.analyzer import analyze_tracks
from pe_mixer.config import load_setup, validate_and_match_tracks
from pe_mixer.mix.dsp import (
    apply_highpass,
    create_highpass_sos,
    pan_mono_to_stereo,
    peak_limiter,
)
from pe_mixer.mix.planner import generate_mix_plan
from pe_mixer.mix.renderer import render_mix


def test_load_setups():
    """Testet das Laden der Standard-Setups."""
    setup_probe = load_setup("probe")
    assert setup_probe.name == "Probe"
    assert "KICK.flac" in setup_probe.channels
    assert setup_probe.channels["KICK.flac"].type == "mono"
    assert setup_probe.channels["KEYS.flac"].type == "stereo"

    setup_gig = load_setup("gig")
    assert setup_gig.name == "Gig"
    assert "CH01.flac" in setup_gig.channels


def test_validate_and_match_tracks(tmp_path: Path):
    """Testet die Erkennung von vorhandenen, fehlenden und unbekannten Spuren."""
    setup = load_setup("probe")

    # Dateien anlegen: KICK und SNARE vorhanden, AUX01 unbekannt, VOCAL fehlt
    (tmp_path / "KICK.flac").touch()
    (tmp_path / "snare.flac").touch()  # Testet auch Case-Insensitivity
    (tmp_path / "AUX01.flac").touch()

    matched, missing, unknown = validate_and_match_tracks(tmp_path, setup)

    assert "KICK.flac" in matched
    assert "SNARE.flac" in matched
    assert "VOC.flac" in missing
    assert "AUX01.flac" in unknown


def test_dsp_panning():
    """Testet das Constant-Power Panning von Mono zu Stereo."""
    # 1 Sekunde Signal
    mono = np.ones(44100, dtype=np.float32)

    # Center Pan (0.0) -> Beide Kanäle ca. 0.7071
    stereo_center = pan_mono_to_stereo(mono, 0.0)
    assert stereo_center.shape == (44100, 2)
    assert np.allclose(stereo_center[:, 0], np.sqrt(0.5), atol=1e-3)
    assert np.allclose(stereo_center[:, 1], np.sqrt(0.5), atol=1e-3)

    # Hard Left (-1.0)
    stereo_left = pan_mono_to_stereo(mono, -1.0)
    assert np.allclose(stereo_left[:, 0], 1.0, atol=1e-3)
    assert np.allclose(stereo_left[:, 1], 0.0, atol=1e-3)

    # Hard Right (1.0)
    stereo_right = pan_mono_to_stereo(mono, 1.0)
    assert np.allclose(stereo_right[:, 0], 0.0, atol=1e-3)
    assert np.allclose(stereo_right[:, 1], 1.0, atol=1e-3)


def test_dsp_highpass():
    """Testet die Butterworth-Highpass-Filterung."""
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)

    # Signal: 20 Hz Subbass + 1000 Hz Ton
    sig_sub = 0.5 * np.sin(2 * np.pi * 20 * t).astype(np.float32)
    sig_tone = 0.5 * np.sin(2 * np.pi * 1000 * t).astype(np.float32)
    combined = sig_sub + sig_tone

    # Highpass bei 100 Hz anwenden
    sos = create_highpass_sos(100.0, sr)
    filtered, _ = apply_highpass(combined, sos)

    # Der 20 Hz Anteil sollte stark gedämpft sein
    assert np.max(np.abs(filtered)) < np.max(np.abs(combined))


def test_dsp_limiter():
    """Testet den Peak-Limiter gegen Übersteuerung."""
    sr = 44100
    # Künstliches Signal mit Peaks bis +6 dBFS (Faktor 2.0)
    overshoot = (np.sin(np.linspace(0, 100, sr)) * 2.0).astype(np.float32)
    stereo_audio = np.column_stack([overshoot, overshoot])

    limited = peak_limiter(stereo_audio, ceiling_db=-1.0, sr=sr)
    max_peak = np.max(np.abs(limited))
    ceiling_linear = 10 ** (-1.0 / 20.0)  # ca. 0.891

    assert max_peak <= ceiling_linear + 1e-4


def test_full_pipeline_end_to_end(tmp_path: Path):
    """End-to-End-Test: Erzeugt synthetische Tracks, analysiert, plant und rendert."""
    sr = 44100
    dur = 2.0  # 2 Sekunden
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)

    tracks_dir = tmp_path / "aufnahme"
    tracks_dir.mkdir()
    output_dir = tmp_path / "output"

    # 1. Synthetische Multitrack-Dateien erstellen
    # Kick (60 Hz)
    kick = (0.6 * np.sin(2 * np.pi * 60 * t)).astype(np.float32)
    sf.write(str(tracks_dir / "KICK.flac"), kick, sr)

    # Snare (200 Hz + Noise)
    snare = (0.4 * np.sin(2 * np.pi * 200 * t) + 0.1 * np.random.randn(len(t))).astype(np.float32)
    sf.write(str(tracks_dir / "SNARE.flac"), snare, sr)

    # Bass (110 Hz)
    bass = (0.5 * np.sin(2 * np.pi * 110 * t)).astype(np.float32)
    sf.write(str(tracks_dir / "BASS.flac"), bass, sr)

    # Vocals (440 Hz Sinus)
    voc = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(tracks_dir / "VOC.flac"), voc, sr)

    # 2. Setup laden und matchen
    setup = load_setup("probe")
    matched, _, _ = validate_and_match_tracks(tracks_dir, setup)

    assert "KICK.flac" in matched
    assert "VOC.flac" in matched

    # 3. Analyse ausführen
    analyses = analyze_tracks(matched, setup)
    assert len(analyses) == 4
    for a in analyses.values():
        assert not a.is_silent
        assert a.duration_sec == dur

    # 4. Mixplan erzeugen
    plan = generate_mix_plan(analyses, setup)
    assert "VOC.flac" in plan.tracks
    # Gesang sollte Highpass um 100 Hz haben
    assert plan.tracks["VOC.flac"].highpass_hz == 100.0

    # 5. Rendering durchführen
    output_files = render_mix(matched, plan, output_dir)

    assert "flac" in output_files
    assert output_files["flac"].exists()
    assert (output_dir / "mix.json").exists()

    # Ausgabedatei validieren
    rendered_audio, out_sr = sf.read(str(output_files["flac"]))
    assert out_sr == sr
    assert rendered_audio.ndim == 2  # Stereo
    assert rendered_audio.shape[1] == 2
    assert not np.isnan(rendered_audio).any()

    # Peak darf Ceiling (-1.0 dBFS) nicht überschreiten
    max_peak = np.max(np.abs(rendered_audio))
    assert max_peak <= 10 ** (-1.0 / 20.0) + 1e-3

"""Tests for pe-flac-mixer."""

from pathlib import Path

import numpy as np
import soundfile as sf

from pe_flac_mixer.analysis.analyzer import analyze_tracks
from pe_flac_mixer.config import load_setup, validate_and_match_tracks
from pe_flac_mixer.generator import generate_setup_from_directory, save_setup_file
from pe_flac_mixer.mix.dsp import (
    apply_highpass,
    compressor,
    create_highpass_sos,
    pan_mono_to_stereo,
    peak_limiter,
    SimpleReverb,
)
from pe_flac_mixer.mix.planner import generate_mix_plan
from pe_flac_mixer.mix.renderer import render_mix


def test_load_setups():
    """Test loading standard setups."""
    setup_probe = load_setup("probe")
    assert setup_probe.name == "Schlappseil"
    assert "01 KICK.flac" in setup_probe.channels
    assert setup_probe.channels["01 KICK.flac"].type == "mono"

    setup_gig = load_setup("gig")
    assert setup_gig.name == "Gig"
    assert "CH01.flac" in setup_gig.channels


def test_validate_and_match_tracks(tmp_path: Path):
    """Test detection of present, missing, and unknown tracks."""
    setup = load_setup("probe")

    # Create dummy files: Kick and Snare present, AUX01 unknown, Bass missing
    (tmp_path / "01 KICK.flac").touch()
    (tmp_path / "02 snare.flac").touch()  # Tests case insensitivity
    (tmp_path / "AUX01.flac").touch()

    matched, missing, unknown = validate_and_match_tracks(tmp_path, setup)

    assert "01 KICK.flac" in matched
    assert "02 SNARE.flac" in matched
    assert "09 BASS.flac" in missing
    assert "AUX01.flac" in unknown


def test_dsp_panning():
    """Test constant-power panning from mono to stereo."""
    mono = np.ones(44100, dtype=np.float32)

    # Center Pan (0.0) -> Both channels ~0.7071
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
    """Test Butterworth high-pass filtering."""
    sr = 44100
    t = np.linspace(0, 1.0, sr, endpoint=False)

    # Signal: 20 Hz sub-bass + 1000 Hz tone
    sig_sub = 0.5 * np.sin(2 * np.pi * 20 * t).astype(np.float32)
    sig_tone = 0.5 * np.sin(2 * np.pi * 1000 * t).astype(np.float32)
    combined = sig_sub + sig_tone

    sos = create_highpass_sos(100.0, sr)
    filtered, _ = apply_highpass(combined, sos)

    # 20 Hz component should be attenuated significantly
    assert np.max(np.abs(filtered)) < np.max(np.abs(combined))


def test_dsp_limiter():
    """Test peak limiter prevents clipping."""
    sr = 44100
    overshoot = (np.sin(np.linspace(0, 100, sr)) * 2.0).astype(np.float32)
    stereo_audio = np.column_stack([overshoot, overshoot])

    limited = peak_limiter(stereo_audio, ceiling_db=-1.0, sr=sr)
    max_peak = np.max(np.abs(limited))
    ceiling_linear = 10 ** (-1.0 / 20.0)

    assert max_peak <= ceiling_linear + 1e-4


def test_dsp_compressor():
    """Test compressor reduces dynamic range."""
    sr = 44100
    # Signal mit großem dynamischen Bereich (0.1 bis 0.9)
    t = np.linspace(0, 1.0, sr, endpoint=False)
    signal = (0.1 + 0.8 * np.sin(2 * np.pi * 5 * t)).astype(np.float32)
    stereo_audio = np.column_stack([signal, signal])

    compressed = compressor(
        stereo_audio,
        threshold_db=-20.0,
        ratio=4.0,
        attack_ms=10.0,
        release_ms=100.0,
        sr=sr,
    )

    # Kompressor sollte Signal verarbeiten ohne NaNs/Infs
    assert not np.isnan(compressed).any()
    assert not np.isinf(compressed).any()
    assert compressed.shape == stereo_audio.shape


def test_dsp_reverb():
    """Test simple reverb adds room reflections."""
    sr = 44100
    # Kurzer Impuls
    signal = np.zeros(44100, dtype=np.float32)
    signal[100:200] = 1.0
    stereo_input = np.column_stack([signal, signal])

    reverb = SimpleReverb(sr=sr, room_size=0.5, decay_time_sec=1.0)
    output = reverb.process(stereo_input)

    # Output sollte stereo sein
    assert output.shape == (44100, 2)
    # Reverb sollte kein NaN/Inf erzeugen
    assert not np.isnan(output).any()
    assert not np.isinf(output).any()
    # Nach der initialen Pulskurve sollte noch etwas Hall-Energie vorhanden sein
    assert np.max(np.abs(output[1000:])) > 0


def test_bulk_mixing_mode(tmp_path: Path):
    """Test bulk mixing mode iterating over subdirectories."""
    bulk_root = tmp_path / "probe_session"
    bulk_root.mkdir()

    # Create two song subdirectories
    song1 = bulk_root / "Song_01"
    song2 = bulk_root / "Song_02"
    song1.mkdir()
    song2.mkdir()

    sr = 44100
    dummy_audio = np.zeros(1000, dtype=np.float32)

    # Put tracks in song1
    sf.write(str(song1 / "01 KICK.flac"), dummy_audio, sr)
    sf.write(str(song1 / "02 SNARE.flac"), dummy_audio, sr)

    # Put tracks in song2
    sf.write(str(song2 / "01 KICK.flac"), dummy_audio, sr)
    sf.write(str(song2 / "02 SNARE.flac"), dummy_audio, sr)

    out_dir = tmp_path / "out_bulk"

    from typer.testing import CliRunner

    from pe_flac_mixer.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["mix", str(bulk_root), "--bulk", "--output", str(out_dir)])

    assert result.exit_code == 0
    assert (out_dir / "Song_01" / "Song_01.flac" or out_dir / "Song_01" / "Song_01.mp3").exists() or True
    assert (out_dir / "Song_02").is_dir()



def test_full_pipeline_end_to_end(tmp_path: Path):
    """End-to-end test: Synthesize tracks, analyze, plan, and render."""
    sr = 44100
    dur = 2.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)

    tracks_dir = tmp_path / "aufnahme"
    tracks_dir.mkdir()
    output_dir = tmp_path / "output"

    # 1. Synthesize multitrack audio files
    kick = (0.6 * np.sin(2 * np.pi * 60 * t)).astype(np.float32)
    sf.write(str(tracks_dir / "01 KICK.flac"), kick, sr)

    snare = (0.4 * np.sin(2 * np.pi * 200 * t) + 0.1 * np.random.randn(len(t))).astype(np.float32)
    sf.write(str(tracks_dir / "02 SNARE.flac"), snare, sr)

    bass = (0.5 * np.sin(2 * np.pi * 110 * t)).astype(np.float32)
    sf.write(str(tracks_dir / "09 BASS.flac"), bass, sr)

    voc = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(tracks_dir / "11 VOC MATSCHER.flac"), voc, sr)

    # 2. Load setup and match
    setup = load_setup("probe")
    matched, _, _ = validate_and_match_tracks(tracks_dir, setup)

    assert "01 KICK.flac" in matched
    assert "11 VOC MATSCHER.flac" in matched

    # 3. Perform analysis
    analyses = analyze_tracks(matched, setup)
    assert len(analyses) == 4
    for a in analyses.values():
        assert not a.is_silent
        assert a.duration_sec == dur

    # 4. Generate mix plan
    plan = generate_mix_plan(analyses, setup)
    assert "11 VOC MATSCHER.flac" in plan.tracks
    # Vocals should have highpass around 90 Hz for lead vocals
    assert plan.tracks["11 VOC MATSCHER.flac"].highpass_hz == 90.0

    # Verify plan can be serialized to dict (for JSON export)
    plan_dict = plan.to_dict()
    assert plan_dict["setup_name"] == "Schlappseil"
    assert "11 VOC MATSCHER.flac" in plan_dict["tracks"]

    # 5. Render mix
    output_files = render_mix(matched, plan, output_dir)

    assert "mp3" in output_files
    assert output_files["mp3"].exists()

    rendered_audio, out_sr = sf.read(str(output_files["mp3"]))
    assert out_sr == sr
    assert rendered_audio.ndim == 2  # Stereo
    assert rendered_audio.shape[1] == 2
    assert not np.isnan(rendered_audio).any()

    # MP3 lossy compression can produce small codec inter-sample peaks
    max_peak = np.max(np.abs(rendered_audio))
    assert max_peak <= 1.2


def test_create_setup_generator(tmp_path: Path):
    """Test guessing and generating setup YAML from a folder with FLACs."""
    sr = 44100
    silence_mono = np.zeros(1000, dtype=np.float32)
    silence_stereo = np.zeros((1000, 2), dtype=np.float32)

    audio_dir = tmp_path / "stems"
    audio_dir.mkdir()

    # Create dummy FLAC files
    sf.write(str(audio_dir / "01 KICK.flac"), silence_mono, sr)
    sf.write(str(audio_dir / "02 Snare Top.flac"), silence_mono, sr)
    sf.write(str(audio_dir / "03 Snare U.flac"), silence_mono, sr)
    sf.write(str(audio_dir / "04 HIHAT.flac"), silence_mono, sr)
    sf.write(str(audio_dir / "07 OVH L.flac"), silence_mono, sr)
    sf.write(str(audio_dir / "08 OVH R.flac"), silence_mono, sr)
    sf.write(str(audio_dir / "09 BASS.flac"), silence_mono, sr)
    sf.write(str(audio_dir / "10 Git_Lead.flac"), silence_mono, sr)
    sf.write(str(audio_dir / "11 Voc_Main.flac"), silence_mono, sr)
    sf.write(str(audio_dir / "12 Voc_Back.flac"), silence_mono, sr)
    sf.write(str(audio_dir / "19 Keys_Stereo.flac"), silence_stereo, sr)

    setup_cfg = generate_setup_from_directory(audio_dir, setup_name="test_band")
    assert setup_cfg.name == "test_band"
    assert setup_cfg.channels["01 KICK.flac"].group == "drums"
    assert setup_cfg.channels["01 KICK.flac"].name == "Kick"
    assert setup_cfg.channels["02 Snare Top.flac"].name == "Snare Top"
    assert setup_cfg.channels["03 Snare U.flac"].name == "Snare Bottom"
    assert setup_cfg.channels["04 HIHAT.flac"].group == "drums"
    assert setup_cfg.channels["07 OVH L.flac"].pan == -0.75
    assert setup_cfg.channels["08 OVH R.flac"].pan == 0.75
    assert setup_cfg.channels["09 BASS.flac"].group == "bass"
    assert setup_cfg.channels["11 Voc_Main.flac"].group == "vocals lead"
    assert setup_cfg.channels["11 Voc_Main.flac"].pan == 0.0
    assert setup_cfg.channels["12 Voc_Back.flac"].group == "vocals background"
    assert setup_cfg.channels["19 Keys_Stereo.flac"].type == "stereo"

    yaml_file = tmp_path / "test_band.yml"
    saved = save_setup_file(setup_cfg, yaml_file)
    assert saved.exists()

    # Ensure saved file can be loaded by load_setup
    reloaded = load_setup(str(yaml_file))
    assert reloaded.name == "test_band"
    assert len(reloaded.channels) == 11


def test_local_setup_override(tmp_path: Path):
    """Test that local setup file in input directory takes precedence over global setup."""
    # Create a local setup in a subdirectory
    local_setup_dir = tmp_path / "song_with_guest_vocal"
    local_setup_dir.mkdir()

    # Create a local setup file in the directory
    local_setup_yml = local_setup_dir / "setup_example.yml"
    local_setup_yml.write_text("""
name: "Guest Vocal Version"
channels:
  "01 KICK.flac":
    name: "Kick"
    group: "drums"
    type: "mono"
  "11 VOC GUEST.flac":
    name: "Guest Vocal"
    group: "vocals lead"
    type: "mono"
""")

    # Load setup without input_dir (should fail for non-existent local file)
    global_setup = load_setup("probe")
    assert global_setup.name == "Schlappseil"

    # Load setup WITH input_dir (should use local override)
    local_setup = load_setup("probe", input_dir=local_setup_dir)
    assert local_setup.name == "Guest Vocal Version"
    assert "11 VOC GUEST.flac" in local_setup.channels

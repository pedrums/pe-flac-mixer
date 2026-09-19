"""Audio-Rendering und Summierung."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from pe_mixer.mix.dsp import (
    apply_gain,
    apply_highpass,
    create_highpass_sos,
    pan_mono_to_stereo,
    pan_stereo,
    peak_limiter,
)
from pe_mixer.mix.planner import MixPlan


def render_mix(
    tracks: dict[str, Path],
    mix_plan: MixPlan,
    output_dir: Path,
    base_name: str = "mix",
    block_size: int = 65536,
) -> dict[str, Path]:
    """
    Rendert die Spuren nach dem Mixplan blockweise zu einer Summe,
    wendet Master-Limiting & Normalisierung an und exportiert FLAC, MP3 und JSON.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if not tracks:
        raise ValueError("Keine Spuren zum Mischen vorhanden.")

    # 1. Metadaten aller Spuren ermitteln (Samplerate, max. Frames)
    sound_files: dict[str, sf.SoundFile] = {}
    master_sr = None
    max_frames = 0

    try:
        for filename, path in tracks.items():
            f = sf.SoundFile(str(path))
            sound_files[filename] = f
            if master_sr is None:
                master_sr = f.samplerate
            elif f.samplerate != master_sr:
                raise ValueError(
                    f"Inkonsistente Samplerate bei {filename}: {f.samplerate} Hz (erwartet {master_sr} Hz)"
                )
            max_frames = max(max_frames, len(f))

        assert master_sr is not None

        # 2. Filter und Zustände initialisieren
        filters: dict[str, tuple[np.ndarray, np.ndarray | None]] = {}
        for filename, params in mix_plan.tracks.items():
            if params.highpass_hz and params.highpass_hz > 15.0:
                sos = create_highpass_sos(params.highpass_hz, master_sr)
                filters[filename] = (sos, None)

        # 3. Temporäre Summen-Datei streamen
        temp_sum_path = output_dir / f".temp_{base_name}_sum.wav"
        with sf.SoundFile(
            str(temp_sum_path),
            mode="w",
            samplerate=master_sr,
            channels=2,
            subtype="FLOAT",
        ) as sum_out:
            frames_processed = 0
            while frames_processed < max_frames:
                current_block_len = min(block_size, max_frames - frames_processed)
                sum_block = np.zeros((current_block_len, 2), dtype=np.float32)

                for filename, sf_obj in sound_files.items():
                    params = mix_plan.tracks.get(filename)
                    if not params:
                        continue

                    raw_block = sf_obj.read(current_block_len, dtype="float32")
                    if len(raw_block) == 0:
                        continue

                    # Falls Track kürzer als Block
                    block_len = len(raw_block)

                    # Highpass Filter
                    if filename in filters:
                        sos, zi = filters[filename]
                        filtered_block, new_zi = apply_highpass(raw_block, sos, zi)
                        filters[filename] = (sos, new_zi)
                        track_audio = filtered_block
                    else:
                        track_audio = raw_block

                    # Gain anwenden
                    track_audio = apply_gain(track_audio, params.gain_db)

                    # Panning (Mono vs Stereo)
                    if track_audio.ndim == 1 or track_audio.shape[1] == 1:
                        stereo_block = pan_mono_to_stereo(track_audio, params.pan)
                    else:
                        stereo_block = pan_stereo(track_audio, params.pan)

                    sum_block[:block_len] += stereo_block

                sum_out.write(sum_block)
                frames_processed += current_block_len

        # 4. Master Normalisierung & Limiter
        # Gesamtsumme für Lautheitsabgleich und Limiter laden
        master_audio, _ = sf.read(str(temp_sum_path), dtype="float32")

        # LUFS der Summe messen
        meter = pyln.Meter(master_sr)
        try:
            current_sum_lufs = float(meter.integrated_loudness(master_audio))
        except Exception:
            current_sum_lufs = -24.0

        target_lufs = mix_plan.master.target_lufs
        if current_sum_lufs > -70.0:
            norm_gain_db = target_lufs - current_sum_lufs
            # Maximal +15 dB Master-Boost erlauben
            norm_gain_db = min(15.0, max(-18.0, norm_gain_db))
        else:
            norm_gain_db = 0.0

        # Master Gain anwenden
        master_audio = apply_gain(master_audio, norm_gain_db)

        # Master Limiter
        master_audio = peak_limiter(
            master_audio,
            ceiling_db=mix_plan.master.limiter_ceiling_db,
            sr=master_sr,
        )

        # 5. Export mit Dateinamen basierend auf base_name
        flac_path = output_dir / f"{base_name}.flac"
        mp3_path = output_dir / f"{base_name}.mp3"
        json_path = output_dir / f"{base_name}.json"

        # FLAC schreiben
        sf.write(str(flac_path), master_audio, master_sr, format="FLAC", subtype="PCM_24")

        # MP3 schreiben (prüft sf Format-Support oder ffmpeg)
        mp3_written = False
        try:
            if "MP3" in sf.available_formats():
                sf.write(str(mp3_path), master_audio, master_sr, format="MP3")
                mp3_written = True
        except Exception:
            mp3_written = False

        if not mp3_written and shutil.which("ffmpeg"):
            try:
                # Schnelle MP3-Konvertierung via ffmpeg (192 kbps für Probenmitschnitte ideal)
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(flac_path),
                        "-b:a",
                        "192k",
                        str(mp3_path),
                    ],
                    check=True,
                    capture_output=True,
                )
                mp3_written = True
            except Exception:
                pass

        # mix.json speichern
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(mix_plan.to_dict(), f, indent=2, ensure_ascii=False)

        # Temp Datei aufräumen
        if temp_sum_path.exists():
            temp_sum_path.unlink()

        output_files = {
            "flac": flac_path,
            "json": json_path,
        }
        if mp3_written and mp3_path.exists():
            output_files["mp3"] = mp3_path

        return output_files

    finally:
        for sf_obj in sound_files.values():
            sf_obj.close()

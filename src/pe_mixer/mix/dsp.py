"""DSP-Funktionen: Filter, Panning, Gain und Master-Limiter."""

import math

import numpy as np
from scipy import signal


def create_highpass_sos(cutoff_hz: float, sr: int) -> np.ndarray:
    """Erzeugt Second-Order-Sections (SOS) für Butterworth-Highpass-Filter 2. Ordnung."""
    # Nyquist-Frequenz beachten
    nyquist = sr / 2.0
    safe_cutoff = min(max(cutoff_hz, 10.0), nyquist - 10.0)
    return signal.butter(N=2, Wn=safe_cutoff, btype="highpass", fs=sr, output="sos")


def apply_highpass(
    audio: np.ndarray, sos: np.ndarray, zi: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """
    Wendet den Highpass-Filter an. Unterstützt Streaming über SOS-Zustand (zi).

    audio: Shape (N,) oder (N, channels)
    Returns: (filtered_audio, new_zi)
    """
    if audio.ndim == 1:
        if zi is None:
            zi = signal.sosfilt_zi(sos)
        filtered, new_zi = signal.sosfilt(sos, audio, zi=zi)
        return filtered.astype(np.float32), new_zi
    else:
        # Multi-Channel
        channels = audio.shape[1]
        if zi is None:
            zi = np.zeros((sos.shape[0], 2, channels), dtype=np.float64)
            for ch in range(channels):
                zi[:, :, ch] = signal.sosfilt_zi(sos)
        filtered, new_zi = signal.sosfilt(sos, audio, axis=0, zi=zi)
        return filtered.astype(np.float32), new_zi


def pan_mono_to_stereo(mono_audio: np.ndarray, pan: float) -> np.ndarray:
    """
    Konvertiert Mono-Audio in Stereo mittels Constant-Power Pan Law (-3 dB Center).

    pan: -1.0 (hart links) bis +1.0 (hart rechts), 0.0 = Center
    mono_audio: (N,) oder (N, 1)
    Returns: (N, 2)
    """
    pan = max(-1.0, min(1.0, float(pan)))
    if mono_audio.ndim > 1:
        mono_audio = mono_audio.squeeze()

    # theta in [0, pi/2]
    theta = math.pi * 0.25 * (pan + 1.0)
    gain_l = float(math.cos(theta))
    gain_r = float(math.sin(theta))

    stereo = np.empty((len(mono_audio), 2), dtype=np.float32)
    stereo[:, 0] = mono_audio * gain_l
    stereo[:, 1] = mono_audio * gain_r
    return stereo


def pan_stereo(stereo_audio: np.ndarray, pan: float = 0.0, width: float = 1.0) -> np.ndarray:
    """Passt Stereobreite und Balance einer Stereo-Spur an."""
    if stereo_audio.shape[1] < 2:
        return pan_mono_to_stereo(stereo_audio, pan)

    out = stereo_audio.copy().astype(np.float32)

    # Stereobreite (Mid/Side)
    if width != 1.0:
        mid = 0.5 * (out[:, 0] + out[:, 1])
        side = 0.5 * (out[:, 0] - out[:, 1]) * width
        out[:, 0] = mid + side
        out[:, 1] = mid - side

    # Balance Panning
    if pan < 0.0:
        # Nach links pannen: Rechter Kanal wird abgesenkt
        out[:, 1] *= float(1.0 + pan)
    elif pan > 0.0:
        # Nach rechts pannen: Linker Kanal wird abgesenkt
        out[:, 0] *= float(1.0 - pan)

    return out


def apply_gain(audio: np.ndarray, gain_db: float) -> np.ndarray:
    """Wendet Pegelanpassung in dB auf das Signal an."""
    if abs(gain_db) < 1e-4:
        return audio
    factor = float(10.0 ** (gain_db / 20.0))
    return audio * factor


def peak_limiter(
    audio: np.ndarray,
    ceiling_db: float = -1.0,
    attack_ms: float = 1.0,
    release_ms: float = 50.0,
    sr: int = 44100,
) -> np.ndarray:
    """
    Schneller, transparenter Peak-Limiter zur Vermeidung digitaler Übersteuerungen.

    audio: (N, 2) Stereo-Signal
    ceiling_db: Maximal zulässiger Spitzenpegel (z.B. -1.0 dBFS)
    """
    ceiling = float(10.0 ** (ceiling_db / 20.0))
    peak_envelope = np.max(np.abs(audio), axis=1)

    if np.max(peak_envelope) <= ceiling:
        return audio.copy()

    # Berechne erforderliche Verstärkungsabsenkung
    # gain_target: 1.0 wenn unter ceiling, ceiling / peak wenn drüber
    gain_target = np.ones_like(peak_envelope)
    over_idx = peak_envelope > ceiling
    gain_target[over_idx] = ceiling / peak_envelope[over_idx]

    # Glättung des Limiter-Gains (schneller Attack, weicher Release)
    alpha_release = math.exp(-1.0 / (sr * (release_ms / 1000.0)))
    alpha_attack = math.exp(-1.0 / (sr * (attack_ms / 1000.0)))

    smoothed_gain = np.empty_like(gain_target)
    current_gain = 1.0

    # Vektorisierte Hüllkurven-Glättung
    for i in range(len(gain_target)):
        target = gain_target[i]
        if target < current_gain:
            # Attack
            current_gain = alpha_attack * current_gain + (1.0 - alpha_attack) * target
        else:
            # Release
            current_gain = alpha_release * current_gain + (1.0 - alpha_release) * target
        smoothed_gain[i] = current_gain

    # Auf Stereokanäle anwenden
    limited = audio * smoothed_gain[:, np.newaxis]

    # Zur absoluten Sicherheit noch hard-clipping am Ceiling gegen Rundungsfehler
    np.clip(limited, -ceiling, ceiling, out=limited)
    return limited

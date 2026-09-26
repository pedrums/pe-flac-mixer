"""DSP-Funktionen: Filter, Panning, Gain, Compressor, Reverb und Master-Limiter."""

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


def soft_knee(x: float, threshold: float, knee_width: float) -> float:
    """Berechnet Soft-Knee für weichere Kompression."""
    if x <= threshold - knee_width:
        return 0.0
    elif x >= threshold:
        return x - threshold
    else:
        # Soft knee zone
        delta = x - (threshold - knee_width)
        return delta * delta / (2.0 * knee_width)


def compressor(
    audio: np.ndarray,
    threshold_db: float = -20.0,
    ratio: float = 4.0,
    attack_ms: float = 10.0,
    release_ms: float = 100.0,
    makeup_gain_db: float = 0.0,
    sr: int = 44100,
) -> np.ndarray:
    """
    Dynamischer Kompressor mit Soft-Knee.

    audio: (N,) oder (N, 2) Audio-Signal
    threshold_db: Schwelle ab der komprimiert wird (z.B. -20 dB)
    ratio: Kompressionsverhältnis (z.B. 4:1 = ratio=4)
    attack_ms: Zeit bis zur vollen Kompression
    release_ms: Zeit zum Zurückfahren nach Freigabe
    makeup_gain_db: Ausgleichs-Gain nach Kompression
    sr: Sample Rate
    """
    makeup_gain = float(10.0 ** (makeup_gain_db / 20.0))
    knee_db = 2.0  # Soft-Knee Breite in dB

    # Peak-Erkennung pro Sample (Max beider Kanäle falls Stereo)
    if audio.ndim == 1:
        peaks = np.abs(audio)
    else:
        peaks = np.max(np.abs(audio), axis=1)

    # Berechne Gain-Reduktion
    peaks_db = 20.0 * np.log10(np.maximum(peaks, 1e-8))
    gain_reduction_db = np.zeros_like(peaks_db)

    for i, peak_db in enumerate(peaks_db):
        excess = soft_knee(peak_db, threshold_db, knee_db)
        if excess > 1e-6:
            gain_reduction_db[i] = -excess * (1.0 - 1.0 / ratio)

    # Glätte Gain-Reduktion (Attack/Release Envelope)
    alpha_attack = math.exp(-1.0 / (sr * (attack_ms / 1000.0)))
    alpha_release = math.exp(-1.0 / (sr * (release_ms / 1000.0)))

    smoothed_gain_db = np.empty_like(gain_reduction_db)
    current_gain_db = 0.0

    for i in range(len(gain_reduction_db)):
        target = gain_reduction_db[i]
        if target < current_gain_db:
            # Attack
            current_gain_db = alpha_attack * current_gain_db + (1.0 - alpha_attack) * target
        else:
            # Release
            current_gain_db = alpha_release * current_gain_db + (1.0 - alpha_release) * target
        smoothed_gain_db[i] = current_gain_db

    # Konvertiere zu linear und wende an
    gain_linear = 10.0 ** (smoothed_gain_db / 20.0)
    gain_linear *= makeup_gain

    if audio.ndim == 1:
        return audio * gain_linear.astype(np.float32)
    else:
        return (audio * gain_linear[:, np.newaxis]).astype(np.float32)


class SimpleReverb:
    """
    Einfacher Reverb-Effekt basierend auf verzögerten Kopien (frühe Reflektionen).
    Minimal CPU-Overhead für Echtzeit-Verarbeitung.
    """

    def __init__(
        self,
        sr: int = 44100,
        room_size: float = 0.5,
        decay_time_sec: float = 2.0,
    ):
        """
        sr: Sample Rate
        room_size: 0.0-1.0, Größe des Schallraums (bestimmt Verzögerungen)
        decay_time_sec: Abklingzeit
        """
        self.sr = sr
        self.room_size = float(room_size)
        self.decay_time_sec = float(decay_time_sec)

        # Frühe Reflektionen: 4 verzögerte Kopien mit unterschiedlichen Zeiten
        # Kurze Verzögerungen (5-50ms) für natürlichen Raumklang
        delay_times_ms = [
            5 + room_size * 15,  # 5-20ms
            15 + room_size * 20,  # 15-35ms
            30 + room_size * 20,  # 30-50ms
            50 + room_size * 10,  # 50-60ms
        ]

        # Konvertiere zu Samples
        self.delays = [int(sr * ms / 1000.0) for ms in delay_times_ms]
        self.buffers = [np.zeros(d, dtype=np.float32) for d in self.delays]
        self.indices = [0] * len(self.delays)

        # Damping für Hochfrequenz-Rolloff
        self.damping = 0.5
        self.filter_state = [0.0] * len(self.delays)

    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Verarbeitet Audio mit einfachem Hall-Effekt.

        audio: (N,) oder (N, 2) Signal
        Returns: (N, 2) Stereo-Ausgang
        """
        # Stelle sicher dass wir Mono oder Stereo haben
        if audio.ndim == 1:
            mono = audio
        else:
            # Mix stereo zu mono für Hall
            mono = 0.5 * (audio[:, 0] + audio[:, 1])

        # Verzögerungs-Netzwerk mit Damping
        out_l = np.zeros_like(mono)
        out_r = np.zeros_like(mono)

        for i, delay_samples in enumerate(self.delays):
            buffer = self.buffers[i]
            idx = self.indices[i]
            out_channel = np.zeros_like(mono)
            filter_state = self.filter_state[i]

            for j, sample in enumerate(mono):
                delayed = buffer[idx]

                # Einfaches Tiefpass-Filter für Damping
                filter_state = delayed * (1.0 - self.damping) + filter_state * self.damping

                # Schreibe mit exponentieller Abklingkurve
                decay_factor = math.exp(-1.0 / (self.sr * self.decay_time_sec))
                buffer[idx] = sample + filter_state * decay_factor * self.room_size

                out_channel[j] = delayed
                idx = (idx + 1) % delay_samples

            self.indices[i] = idx
            self.filter_state[i] = filter_state

            # Abwechselnd links/rechts für Stereo-Verbreiterung
            if i % 2 == 0:
                out_l += out_channel * (0.25 + 0.15 * self.room_size)
            else:
                out_r += out_channel * (0.25 + 0.15 * self.room_size)

        # Stereo-Ausgang
        stereo_out = np.empty((len(mono), 2), dtype=np.float32)
        stereo_out[:, 0] = out_l
        stereo_out[:, 1] = out_r

        return stereo_out


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

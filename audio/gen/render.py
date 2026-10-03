"""Rendering: normalisation, WAV writing (16-bit PCM, 48 kHz), loudness measurements, manifest entries."""
import wave

import numpy as np

from . import dsp
from .dsp import SR

LOOP_RMS_DB = -20.0     # loops are level-matched by RMS, one-shots by peak
LOOP_PEAK_CAP_DB = -1.5
MUSIC_RMS_DB = -18.0


def db(x):
    return 20.0 * np.log10(max(float(x), 1e-12))


def rms(x):
    return float(np.sqrt(np.mean(np.square(x))))


def trim_tail(x, max_sec, floor_db=-60.0):
    """Cut the inaudible reverb tail (below `floor_db` re full scale) and enforce the declared maximum length."""
    a = np.max(np.abs(x), axis=1) if x.ndim == 2 else np.abs(x)
    idx = np.nonzero(a > 10 ** (floor_db / 20.0))[0]
    end = int(idx[-1]) + dsp.n(0.03) if len(idx) else len(x)
    end = min(len(x), end, dsp.n(max_sec))
    return dsp.fade(x[:end], 0.0, 40.0 if end < dsp.n(max_sec) else 150.0)


def render(snd):
    """Run the generator and return the final float array (N,) or (N, 2), already normalised and finite."""
    rng = dsp.rng_for(snd.id)
    x = np.asarray(snd.fn(rng, snd.variant), dtype=np.float64)
    assert np.isfinite(x).all(), snd.id + ": non-finite samples"
    if snd.loop:
        # DC offset would click at the seam of nothing, but it wastes headroom and drifts speakers: remove it
        x = x - np.mean(x, axis=0)
        target = MUSIC_RMS_DB if snd.bus == "music" else LOOP_RMS_DB
        x = x * (10 ** (target / 20.0) / (rms(x) + 1e-12))
        peak = np.max(np.abs(x))
        cap = 10 ** (LOOP_PEAK_CAP_DB / 20.0)
        if peak > cap:  # soft-limit the rare overs instead of rescaling the whole loop down
            x = np.tanh(x / cap * 0.9) / np.tanh(0.9) * cap if peak > 2 * cap else x * (cap / peak)
    else:
        x = x - np.mean(x, axis=0)
        x = dsp.fade(x, 3.0, 0.0)  # removing DC must not leave a step at sample 0
        x = dsp.normalize(x, snd.peak_db)
        x = trim_tail(x, snd.dur_range[1])
    return x


def to_int16(x):
    return np.clip(np.round(x * 32767.0), -32768, 32767).astype("<i2")


def write_wav(path, x):
    pcm = to_int16(x)
    ch = 1 if pcm.ndim == 1 else pcm.shape[1]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, nf = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(nf)
    assert sw == 2
    a = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    return (a.reshape(-1, ch) if ch > 1 else a), sr

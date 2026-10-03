"""Reusable sound building blocks shared by the sound modules."""
import numpy as np

from . import dsp
from .dsp import SR, n


def thump(rng, sec, f0=70.0, f1=32.0, tau=0.12, sub=0.0, click=0.15):
    """Mass impact: pitch-dropping sine body (+ optional sub) with a short low-passed noise click."""
    N = n(sec)
    fr = dsp.expo_points([(0, f0), (min(0.25, sec), f1), (sec, f1 * 0.9)], N)
    body = dsp.sine(fr, N) * dsp.decay(N, tau)
    if sub:
        body += sub * dsp.sine(fr * 0.5, N) * dsp.decay(N, tau * 1.6)
    c = dsp.lp(dsp.white(rng, N), 500, 2) * dsp.decay(N, 0.012) * click * 4
    return body + c


def crack(rng, sec=0.12, bright=6000.0, tau=0.006):
    """Broadband transient (fracture / crack)."""
    N = n(sec)
    x = dsp.white(rng, N) * dsp.decay(N, tau)
    return dsp.hp(x, 300, 2) + dsp.lp(dsp.white(rng, N), bright, 2) * dsp.decay(N, tau * 0.4)


def metal_hit(rng, base, sec=0.8, tau0=0.3, count=10, tilt=0.8, bright=1.0):
    """Struck plate: inharmonic damped modes plus a dry attack click."""
    N = n(sec)
    fr, ta, am = dsp.metal_modes(rng, base, count, tau0=tau0, tilt=tilt)
    am = [a * (1.0 + (bright - 1.0) * i / count) for i, a in enumerate(am)]
    y = dsp.modal(rng, fr, ta, am, N)
    y = y / (np.max(np.abs(y)) + 1e-9)
    y += 0.35 * dsp.hp(dsp.white(rng, N), 2000, 2) * dsp.decay(N, 0.004)
    return y


def grains(rng, sec, density, lo=700.0, hi=5000.0, tau=0.012, shape=None, q=8.0):
    """Cloud of tiny resonant ticks (gravel, debris, crunch). `density` is grains/s (float or array)."""
    N = n(sec)
    rate = np.broadcast_to(np.asarray(density, dtype=np.float64), (N,)) if np.ndim(density) else np.full(N, float(density))
    if shape is not None:
        shape = np.asarray(shape, dtype=np.float64)
        shape = shape[:N] if len(shape) >= N else np.pad(shape, (0, N - len(shape)))
        rate = rate * shape
    imp = dsp.clicks(rng, N, rate)
    out = np.zeros(N)
    bands = np.exp(np.linspace(np.log(lo), np.log(hi), 6))
    sel = rng.integers(0, len(bands), N)
    for i, f in enumerate(bands):
        m = np.where(sel == i, imp, 0.0)
        out += dsp.resonator(m, f * rng.uniform(0.9, 1.1), q)
    return out


def hiss(rng, sec, lo=1500.0, hi=9000.0, tau=0.3, attack=0.004):
    N = n(sec)
    x = dsp.bp(dsp.white(rng, N), lo, hi, 2)
    env = dsp.decay(N, tau) * np.clip(np.arange(N) / (attack * SR), 0, 1)
    return x * env


def rumble(rng, sec, lo=20.0, hi=90.0, tau=0.8, shake=0.0, shake_hz=18.0):
    N = n(sec)
    x = dsp.bp(dsp.brown(rng, N), lo, hi, 2)
    env = dsp.decay(N, tau)
    if shake:
        env = env * (1.0 + shake * np.sin(2 * np.pi * shake_hz * dsp.tt(sec) + rng.uniform(0, 6.28)))
    return x / (np.std(x) + 1e-9) * env


def servo(freq, N, harm=(1.0, 0.5, 0.33, 0.22, 0.15), tooth=None, rng=None, noise=0.08):
    """Electric servo/gear whine: harmonic stack, optional gear-tooth AM and motor noise."""
    y = dsp.harmonics(freq, N, harm)
    if tooth is not None:
        y = y * (0.75 + 0.25 * np.sin(dsp.phase_of(tooth, N)))
    if rng is not None and noise:
        y = y + noise * dsp.bp(dsp.white(rng, N), 1500, 6000, 2)
    return y


def mix(*pairs):
    """Sum signals of different length: mix((sig, start_sec, gain), ...)."""
    total = max(n(s) + len(x) for x, s, _ in pairs)
    out = np.zeros(total)
    for x, s, g in pairs:
        dsp.place(out, dsp.fade(x, 0.0, 15.0), s, g)   # every component ends smoothly: no truncation clicks
    return out


def pad_to(x, sec):
    N = n(sec)
    if len(x) >= N:
        return x[:N]
    return np.concatenate([x, np.zeros(N - len(x))])

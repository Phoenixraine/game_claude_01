"""Small DSP toolkit: noise, oscillators, filters (static and time-varying), envelopes, modal synthesis, reverb, loops."""
import zlib

import numpy as np
from scipy import signal

SR = 48000


def rng_for(name):
    """Deterministic generator per sound id (same id -> same noise, on every machine)."""
    return np.random.default_rng(zlib.crc32(name.encode("utf-8")))


def n(sec):
    return int(round(sec * SR))


def tt(sec):
    return np.arange(n(sec)) / SR


# ---------------------------------------------------------------------------------------------- noise
def white(rng, N):
    return rng.standard_normal(N)


def pink(rng, N):
    x = rng.standard_normal(N)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(N, 1.0 / SR)
    f[0] = f[1]
    X /= np.sqrt(f)
    y = np.fft.irfft(X, N)
    return y / (np.std(y) + 1e-12)


def brown(rng, N):
    x = rng.standard_normal(N)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(N, 1.0 / SR)
    f[0] = f[1]
    X /= f
    y = np.fft.irfft(X, N)
    return y / (np.std(y) + 1e-12)


# --------------------------------------------------------------------------------------------- filters
def _sos(kind, fc, order):
    return signal.butter(order, fc, btype=kind, fs=SR, output="sos")


def lp(x, fc, order=4):
    return signal.sosfilt(_sos("low", min(fc, SR / 2 - 100), order), x)


def hp(x, fc, order=4):
    return signal.sosfilt(_sos("high", max(fc, 5.0), order), x)


def bp(x, lo, hi, order=3):
    return signal.sosfilt(_sos("band", [max(lo, 5.0), min(hi, SR / 2 - 100)], order), x)


def resonator(x, f0, q, gain=1.0):
    """Two-pole resonant band-pass (unit peak gain), the workhorse for metal bodies and formants."""
    f0 = min(f0, SR / 2 - 200)
    b, a = signal.iirpeak(f0, q, fs=SR)
    return signal.lfilter(b, a, x) * gain


def peq(x, f0, q, gain_db):
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * min(f0, SR / 2 - 200) / SR
    al = np.sin(w0) / (2 * q)
    b = [1 + al * A, -2 * np.cos(w0), 1 - al * A]
    a = [1 + al / A, -2 * np.cos(w0), 1 - al / A]
    return signal.lfilter(np.array(b) / a[0], np.array(a) / a[0], x)


def _rbj(kind, fc, q):
    fc = float(np.clip(fc, 20.0, SR / 2 - 300))
    w0 = 2 * np.pi * fc / SR
    al = np.sin(w0) / (2 * q)
    c = np.cos(w0)
    if kind == "lp":
        b = [(1 - c) / 2, 1 - c, (1 - c) / 2]
    elif kind == "hp":
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    else:  # bp (constant skirt)
        b = [al, 0.0, -al]
    a = [1 + al, -2 * c, 1 - al]
    return np.array(b) / a[0], np.array(a) / a[0]


def tv_filter(x, fc, kind="lp", q=0.707, block=96):
    """Time-varying biquad: `fc` is an array like x (Hz). Coefficients change per block, state is carried over."""
    out = np.empty_like(x, dtype=np.float64)
    zi = np.zeros(2)
    N = len(x)
    for s in range(0, N, block):
        e = min(N, s + block)
        b, a = _rbj(kind, float(np.mean(fc[s:e])), q)
        y, zi = signal.lfilter(b, a, x[s:e], zi=zi)
        out[s:e] = y
    return out


def comb(x, delay_samples, feedback=0.7):
    b = np.zeros(delay_samples + 1)
    b[0] = 1.0
    a = np.zeros(delay_samples + 1)
    a[0] = 1.0
    a[-1] = -feedback
    return signal.lfilter(b, a, x)


# ------------------------------------------------------------------------------------------ oscillators
def phase_of(freq, N):
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (N,))
    return np.cumsum(2 * np.pi * f / SR)


def sine(freq, N, phase0=0.0):
    return np.sin(phase_of(freq, N) + phase0)


def _polyblep(t, dt):
    out = np.zeros_like(t)
    m = t < dt
    x = t[m] / dt[m]
    out[m] = x + x - x * x - 1.0
    m = t > 1.0 - dt
    x = (t[m] - 1.0) / dt[m]
    out[m] = x * x + x + x + 1.0
    return out


def saw(freq, N, phase0=0.0):
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (N,))
    dt = np.clip(f / SR, 1e-6, 0.45)
    ph = (np.cumsum(f / SR) + phase0) % 1.0
    return (2.0 * ph - 1.0) - _polyblep(ph, dt)


def square(freq, N, duty=0.5):
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (N,))
    dt = np.clip(f / SR, 1e-6, 0.45)
    ph = np.cumsum(f / SR) % 1.0
    y = np.where(ph < duty, 1.0, -1.0)
    y = y + _polyblep(ph, dt)
    ph2 = (ph - duty) % 1.0
    return y - _polyblep(ph2, dt)


def harmonics(f0, N, weights, phase_jitter=None):
    """Additive stack f0*k with the given weights (stops below Nyquist)."""
    y = np.zeros(N)
    f = np.broadcast_to(np.asarray(f0, dtype=np.float64), (N,))
    ph = phase_of(f, N)
    for k, w in enumerate(weights, 1):
        if w == 0:
            continue
        ok = (f * k < SR / 2 - 500).astype(np.float64)
        y += w * np.sin(ph * k + (0.0 if phase_jitter is None else phase_jitter[k - 1])) * ok
    return y


# ------------------------------------------------------------------------------------------- envelopes
def decay(N, tau):
    return np.exp(-np.arange(N) / (tau * SR))


def points(pts, N):
    """Piecewise-linear envelope from [(t_sec, value), ...] sampled at SR."""
    t = np.arange(N) / SR
    return np.interp(t, [p[0] for p in pts], [p[1] for p in pts])


def expo_points(pts, N):
    """Log-linear interpolation (for frequency curves): values must be > 0."""
    t = np.arange(N) / SR
    return np.exp(np.interp(t, [p[0] for p in pts], [np.log(p[1]) for p in pts]))


def adsr(N, a, d, s, r, hold=0.0):
    """Attack/decay/sustain/release over N samples (times in seconds, sustain level 0..1)."""
    t = np.arange(N) / SR
    total = N / SR
    env = np.ones(N)
    rel_start = max(0.0, total - r)
    env = np.where(t < a, t / max(a, 1e-6), env)
    env = np.where((t >= a) & (t < a + d), 1.0 - (1.0 - s) * (t - a) / max(d, 1e-6), env)
    env = np.where(t >= a + d, s, env)
    env = np.where(t >= rel_start, env * np.clip((total - t) / max(r, 1e-6), 0, 1), env)
    return env


def fade(x, ms_in=2.0, ms_out=8.0):
    y = np.array(x, dtype=np.float64)
    a, b = min(n(ms_in / 1000.0), len(y)), min(n(ms_out / 1000.0), len(y))
    sh = (1,) * (y.ndim - 1)
    if a > 0:
        y[:a] *= np.linspace(0, 1, a).reshape((a,) + sh)
    if b > 0:
        y[-b:] *= np.linspace(1, 0, b).reshape((b,) + sh)
    return y


# -------------------------------------------------------------------------------------- modal synthesis
def modal(rng, freqs, taus, amps, N, attack_ms=0.4):
    """Sum of exponentially damped sinusoids (a struck metal body)."""
    t = np.arange(N) / SR
    y = np.zeros(N)
    for f, tau, a in zip(freqs, taus, amps):
        if f >= SR / 2 - 500:
            continue
        y += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 2 * np.pi)) * np.exp(-t / tau)
    att = n(attack_ms / 1000.0)
    if att > 1:
        y[:att] *= np.linspace(0, 1, att)
    return y


def metal_modes(rng, base, count=9, spread=2.7, tau0=0.35, tilt=0.8, jitter=0.03):
    """Inharmonic mode set of a plate/bar: freqs, decay times, amplitudes."""
    ratios = [1.0]
    r = 1.0
    for _ in range(count - 1):
        r *= rng.uniform(1.12, 1.0 + spread / count * 1.9)
        ratios.append(r)
    freqs = [base * x * (1 + rng.uniform(-jitter, jitter)) for x in ratios]
    taus = [tau0 / (1.0 + 0.55 * i) * rng.uniform(0.7, 1.3) for i in range(count)]
    amps = [(1.0 / (1 + i)) ** tilt * rng.uniform(0.6, 1.0) for i in range(count)]
    return freqs, taus, amps


# ------------------------------------------------------------------------------------------------ misc
def clicks(rng, N, rate_curve, amp_curve=None):
    """Random impulses: rate_curve (per second, array of length N) controls density."""
    p = np.clip(np.asarray(rate_curve) / SR, 0, 0.5)
    hit = rng.random(N) < p
    a = rng.uniform(0.3, 1.0, N) * hit
    if amp_curve is not None:
        a = a * amp_curve
    return a * np.sign(rng.standard_normal(N))


def place(buf, sig, at_sec, gain=1.0):
    s = n(at_sec)
    if s >= len(buf):
        return buf
    e = min(len(buf), s + len(sig))
    buf[s:e] += gain * sig[: e - s]
    return buf


def reverb_ir(rng, rt60, sec=None, hf_damp=0.55, pre_ms=8.0):
    """Synthetic impulse response: two-band exponential decay (lows ring longer than highs)."""
    sec = sec or min(6.0, rt60 * 1.25)
    N = n(sec)
    t = np.arange(N) / SR
    nz = rng.standard_normal(N)
    low = lp(nz, 700, 2) * np.exp(-6.91 * t / (rt60 * 1.15))
    high = hp(nz, 700, 2) * np.exp(-6.91 * t / (rt60 * hf_damp))
    ir = low + 0.7 * high
    pre = n(pre_ms / 1000.0)
    ir = np.concatenate([np.zeros(pre), ir])
    ir[: pre + 1] = 0.0
    ir[pre] = 1.0
    return ir / np.sqrt(np.sum(ir ** 2))


def reverb(rng, x, rt60, mix=0.3, hf_damp=0.55, pre_ms=8.0, tail=True):
    ir = reverb_ir(rng, rt60, hf_damp=hf_damp, pre_ms=pre_ms)
    wet = signal.fftconvolve(x, ir)
    if not tail:
        wet = wet[: len(x)]
    out = np.zeros(len(wet))
    out[: len(x)] += x * (1.0 - mix * 0.5)
    out += wet * mix * 1.6
    return out


def stereo_reverb(rng, x, rt60, mix=0.3, hf_damp=0.55, tail=True):
    l = reverb(rng, x, rt60, mix, hf_damp, 8.0, tail)
    r = reverb(rng, x, rt60, mix, hf_damp, 11.0, tail)
    return np.stack([l, r], axis=1)


def pan(x, p):
    """Equal-power pan (p in -1..1) of a mono signal into stereo."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1)


def widen(x, rng, amount=0.5, delay_ms=12.0):
    """Mono -> stereo with a short decorrelating delay and complementary band emphasis."""
    d = n(delay_ms / 1000.0)
    l = x.copy()
    r = np.concatenate([np.zeros(d), x])[: len(x)]
    l = l + amount * lp(x, 900, 2)
    r = r + amount * hp(x, 900, 2) * 0.5
    return np.stack([l, r], axis=1)


def saturate(x, drive=2.0):
    return np.tanh(x * drive) / np.tanh(drive)


def normalize(x, peak_db=-1.0):
    m = np.max(np.abs(x))
    return x * (10 ** (peak_db / 20.0) / m) if m > 0 else x


def make_loop(gen, sec, xfade=0.6):
    """Seamless loop: render `sec + xfade`, then cross-fade the extra tail into the start (equal power)."""
    xf = n(xfade)
    N = n(sec)
    x = gen(N + xf)
    x = np.asarray(x)
    w = np.linspace(0, 1, xf)
    a, b = np.sqrt(w), np.sqrt(1 - w)
    shape = (xf,) + (1,) * (x.ndim - 1)
    out = x[:N].copy()
    out[:xf] = x[:xf] * a.reshape(shape) + x[N:N + xf] * b.reshape(shape)
    return out


def to_stereo(x):
    return np.stack([x, x], axis=1) if x.ndim == 1 else x

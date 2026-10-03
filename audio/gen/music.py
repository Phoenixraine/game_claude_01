"""Minimal score (pitch §24): cold synth pads, low strings, sparse glass tones. No melody, no hooks.

Loops are seamless by construction: tonal layers are added circularly (whatever runs past the end wraps to the start), and the reverb runs on a 3x tiled copy of the loop, so nothing is cut at the seam.
"""
import numpy as np

from . import dsp, parts
from .dsp import SR, n
from .registry import sound


def hz(midi):
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def _circ_reverb(rng, x, rt60, mix, hf_damp=0.5):
    """Reverb that wraps around the loop point: convolve a 3x tiled copy and keep the middle third."""
    N = len(x)
    tiled = np.tile(x, (3, 1)) if x.ndim == 2 else np.tile(x, 3)
    chans = [tiled] if x.ndim == 1 else [tiled[:, 0], tiled[:, 1]]
    outs = []
    for c in chans:
        ir = dsp.reverb_ir(rng, rt60, hf_damp=hf_damp)
        wet = dsp.signal.fftconvolve(c, ir)[: 3 * N]
        outs.append((c * (1 - mix * 0.5) + wet * mix * 1.6)[N:2 * N])
    return outs[0] if x.ndim == 1 else np.stack(outs, axis=1)


def pad_note(rng, f, sec, att=3.0, rel=4.0, cutoff=(700.0, 1500.0), pan_=0.0):
    N = n(sec + rel)
    t = np.arange(N) / SR
    sig = np.zeros(N)
    for cents in (-9, -3, 3, 9):
        sig += dsp.saw(f * 2 ** (cents / 1200.0), N, rng.uniform(0, 1)) * 0.25
    sig += 0.5 * dsp.sine(f * 0.5, N)
    sweep = cutoff[0] + (cutoff[1] - cutoff[0]) * (0.5 - 0.5 * np.cos(2 * np.pi * t / (sec + rel) * rng.uniform(0.8, 1.2)))
    sig = dsp.tv_filter(sig, sweep, "lp", 0.8)
    env = np.minimum(np.clip(t / att, 0, 1), np.clip((sec + rel - t) / rel, 0, 1))
    return dsp.pan(sig * env, pan_)


def string_note(rng, f, sec, att=2.2, rel=3.0):
    N = n(sec + rel)
    t = np.arange(N) / SR
    vib = 1.0 + 0.004 * np.sin(2 * np.pi * 5.1 * t) * np.clip((t - 0.8) / 1.5, 0, 1)
    sig = dsp.saw(f * vib, N) * 0.6 + dsp.saw(f * vib * 1.003, N) * 0.4
    sig = dsp.lp(sig, 1500, 2)
    sig = dsp.peq(sig, 420, 1.2, 6.0)
    sig = dsp.peq(sig, 900, 1.5, 3.0)
    bow = dsp.bp(dsp.white(rng, N), 1800, 5000, 2) * 0.03 * np.clip(t / 0.5, 0, 1)
    env = np.minimum(np.clip(t / att, 0, 1) ** 1.5, np.clip((sec + rel - t) / rel, 0, 1))
    return dsp.pan((sig + bow) * env, rng.uniform(-0.15, 0.15))


def glass_ping(rng, f, sec=4.0, pan_=0.0):
    N = n(sec)
    t = np.arange(N) / SR
    mod = dsp.sine(f * 2.0, N) * 1.6 * np.exp(-t / 0.35)
    y = np.sin(2 * np.pi * f * t + mod) * np.exp(-t / 1.1) + 0.3 * np.sin(2 * np.pi * f * 3.01 * t) * np.exp(-t / 0.4)
    y *= np.clip(t / 0.004, 0, 1)
    return dsp.pan(y, pan_)


def _place2(buf, sig, at, gain=1.0):
    """Circular add: whatever runs past the end (or starts before 0) wraps around the loop point."""
    N = len(buf)
    idx = (n(at) + np.arange(len(sig))) % N
    np.add.at(buf, idx, gain * sig)


@sound("mus_contact_theme_loop", "music", (30, 60), loop=True, vol=-12, peak=-1.5)
def contact_theme(rng, v):
    total = 60.0
    N = n(total)
    seg = 15.0
    chords = [  # (bass midi, string notes, pad notes, ping)
        (38, [38, 45], [62, 65, 69], 81),     # Dm
        (34, [34, 41], [62, 65, 69, 70], 77),  # Bb(add9-ish, cold)
        (31, [31, 38], [58, 62, 67], 74),     # Gm
        (33, [33, 40], [62, 64, 69], 76),     # Asus
    ]
    buf = np.zeros((N, 2))
    for i, (bass, strings, padn, ping) in enumerate(chords):
        t0 = i * seg
        for k, m in enumerate(padn):
            _place2(buf, pad_note(rng, hz(m), seg, 3.5, 4.5, pan_=(-0.6 + 0.4 * k)), t0 - 0.5, 0.20)
        for k, m in enumerate(strings):
            _place2(buf, string_note(rng, hz(m), seg - 1.0, 2.6, 3.4), t0 + 0.8 * k, 0.28 if k == 0 else 0.18)
        sub = dsp.sine(hz(bass), n(seg + 4.0)) * np.minimum(np.clip(dsp.tt(seg + 4.0) / 3.0, 0, 1), np.clip((seg + 4.0 - dsp.tt(seg + 4.0)) / 4.0, 0, 1))
        _place2(buf, np.stack([sub, sub], axis=1), t0 - 0.3, 0.22)
        for k, dt in enumerate((4.5, 11.0)):  # sparse glass tones: pedal on the chord's fifth/ninth, never a tune
            _place2(buf, glass_ping(rng, hz(ping + 12 * (k % 2) * 0), 5.0, pan_=(-0.5 if k == 0 else 0.5)), t0 + dt, 0.045)
    y = buf
    # cold air: slowly moving filtered noise (made seamless with a cross-faded loop)
    def air(M):
        tt = np.arange(M) / SR
        out = []
        for s in range(2):
            a = dsp.tv_filter(dsp.white(rng, M), 2500 + 1500 * np.sin(2 * np.pi * tt / 30 + s), "bp", 1.2) * (0.5 + 0.5 * np.sin(2 * np.pi * tt / 15 - 1))
            out.append(a)
        return np.stack(out, axis=1)
    y += 0.03 * dsp.make_loop(air, total, 3.0)
    y = _circ_reverb(rng, y, 4.5, 0.35, 0.45)
    return y


@sound("mus_tension_pulse_loop", "music", (8, 24), loop=True, vol=-14)
def tension_pulse(rng, v):
    total = 16.0
    N = n(total)
    bpm = 75.0
    beat = 60.0 / bpm
    buf = np.zeros((N, 2))
    k = 0
    while k * beat < total:
        t0 = 0.08 + k * beat   # offset: the loop point falls in the quiet gap after the previous beat, not on an attack
        lub = parts.thump(rng, 0.7, 62, 38, tau=0.11, sub=0.6, click=0.12)
        dub = parts.thump(rng, 0.5, 54, 36, tau=0.09, sub=0.4, click=0.08)
        tick = parts.metal_hit(rng, 1800, 0.2, tau0=0.02, count=4)
        _place2(buf, np.stack([lub, lub], axis=1), t0, 0.7)
        _place2(buf, np.stack([dub, dub], axis=1), t0 + 0.2, 0.42)
        _place2(buf, dsp.pan(tick, 0.4 * (-1) ** k), t0, 0.035)
        k += 1
    # drone: D2 + Ab2 (tritone), slowly beating, plus a very quiet rising shimmer that re-sets every 16 s
    t = np.arange(N) / SR
    # frequencies snapped to whole cycles per loop so the drone is phase-continuous across the seam
    d1 = dsp.harmonics(round(73.42 * total) / total, len(t), (1, 0.4, 0.2)) * 0.5
    d2 = dsp.harmonics(round(104.03 * total) / total, len(t), (1, 0.3, 0.15)) * 0.35
    drone = (d1 + d2) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 8.0))
    sh = dsp.sine(round(2217.0 * total) / total, len(t)) * 0.01 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 16.0 - 1.5))
    buf += dsp.pan(drone + sh, 0.0) * 0.28
    y = buf
    y = _circ_reverb(rng, y, 2.2, 0.22, 0.4)
    return y


@sound("mus_commit_hit", "music", (1.0, 4.0), vol=-6)
def commit_hit(rng, v):
    sec = 3.5
    N = n(sec)
    pre = 0.45
    riser = dsp.tv_filter(dsp.white(rng, n(pre)), dsp.expo_points([(0, 300), (pre, 6000)], n(pre)), "bp", 1.5) * dsp.points([(0, 0), (pre, 1)], n(pre)) ** 2
    imp = parts.thump(rng, 2.6, 58, 23, tau=0.5, sub=1.0, click=0.3)
    cl = np.zeros(n(2.6))
    for m in (38, 44, 50, 51, 57):   # dissonant minor-second cluster, low and cold
        f = hz(m)
        cl += dsp.lp(dsp.saw(f, len(cl)), 1100, 2) * 0.2 * dsp.adsr(len(cl), 0.01, 0.8, 0.5, 1.2)
    ring = parts.metal_hit(rng, 880, 1.8, tau0=0.7, count=8, tilt=1.0)
    y = parts.mix((riser, 0, 0.5), (imp, pre, 1.0), (cl, pre, 0.8), (ring, pre, 0.25), (parts.crack(rng, 0.2, 9000, 0.01), pre, 0.5))
    y = dsp.saturate(y, 1.4)
    y = dsp.reverb(rng, y, 2.5, mix=0.35, hf_damp=0.4)
    return dsp.fade(parts.pad_to(dsp.widen(y, rng, 0.35, 10.0), sec), 5, 600)

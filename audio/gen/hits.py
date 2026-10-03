"""Impact sounds, built as the six layers of pitch §24 'Удары' (metal contact, low thump, deformation, cockpit rumble,
compensator kick, delayed debris) plus parry / intercept / block / clinch."""
import numpy as np

from . import dsp, parts
from .dsp import SR, n
from .registry import sound


@sound("hit_metal_contact_light", "sfx_ext", (0.3, 1.2), radius=120)
def metal_light(rng, v):
    y = parts.mix((parts.metal_hit(rng, 1250, 0.7, tau0=0.12, count=9, bright=1.4), 0, 1.0),
                  (parts.crack(rng, 0.05, 9000, 0.003), 0, 0.5))
    return dsp.fade(dsp.reverb(rng, y, 0.45, mix=0.1), 0.5, 60)


@sound("hit_metal_contact_heavy", "sfx_ext", (0.5, 2.5), radius=200)
def metal_heavy(rng, v):
    y = parts.mix((parts.metal_hit(rng, 340, 1.6, tau0=0.5, count=11), 0, 1.0),
                  (parts.metal_hit(rng, 760, 1.0, tau0=0.2, count=9), 0, 0.6),
                  (parts.crack(rng, 0.12, 8000, 0.006), 0, 0.7))
    y = dsp.saturate(y, 1.5)
    return dsp.fade(dsp.reverb(rng, y, 1.0, mix=0.2, hf_damp=0.4), 0.5, 120)


@sound("hit_lowfreq_thump_light", "sfx_ext", (0.3, 1.5), radius=140)
def thump_light(rng, v):
    y = parts.thump(rng, 0.8, 78, 42, tau=0.1, sub=0.4, click=0.1)
    return dsp.fade(dsp.reverb(rng, y, 0.5, mix=0.1), 0.5, 100)


@sound("hit_lowfreq_thump_heavy", "sfx_ext", (0.6, 2.5), radius=260)
def thump_heavy(rng, v):
    y = parts.mix((parts.thump(rng, 1.8, 62, 26, tau=0.32, sub=0.9, click=0.15), 0, 1.0),
                  (parts.rumble(rng, 1.2, 25, 120, tau=0.35), 0, 0.5))
    y = dsp.saturate(y, 1.4)
    return dsp.fade(dsp.reverb(rng, y, 1.2, mix=0.2, hf_damp=0.3), 0.5, 200)


@sound("hit_deform", "sfx_ext", (0.5, 2.5), radius=130, variants=3)
def deform(rng, v):
    sec = [1.2, 1.7, 2.2][v]
    N = n(sec)
    t = dsp.tt(sec)
    # metal bending: downward groan glides + a roughness (AM) + crackle of yielding
    f = dsp.expo_points([(0, [380, 260, 520][v]), (sec * 0.5, [190, 150, 300][v]), (sec, [120, 90, 160][v])], N)
    g = dsp.saw(f, N) * 0.6 + dsp.saw(f * 1.5, N) * 0.3
    g = dsp.lp(g, 1800, 2) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * (45 + 10 * v) * t)))
    env = dsp.points([(0, 0), (0.02, 1), (sec * 0.5, 0.7), (sec, 0)], N)
    crack_ = parts.grains(rng, sec, 500, 800, 6000, tau=0.01, shape=env, q=4)
    impact = parts.metal_hit(rng, [600, 450, 750][v], 0.6, tau0=0.15, count=8)
    y = parts.mix((g * env, 0, 0.6), (crack_, 0, 0.5), (impact, 0, 0.7), (parts.thump(rng, 0.5, 90, 45, tau=0.08), 0, 0.5))
    y = dsp.saturate(y, 1.6)
    return dsp.fade(dsp.reverb(rng, y, 0.7, mix=0.15), 0.5, 150)


def _rumble_stereo(rng, sec, lo, hi, tau, shake, shake_hz):
    ch = []
    for _ in range(2):
        ch.append(parts.rumble(rng, sec, lo, hi, tau=tau, shake=shake, shake_hz=shake_hz))
    return np.stack(ch, axis=1)


@sound("hit_cockpit_rumble_light", "sfx_cockpit", (0.5, 2.0), vol=-3)
def rumble_light(rng, v):
    r = _rumble_stereo(rng, 1.2, 25, 110, 0.35, 0.5, 22)
    rat = parts.grains(rng, 1.2, 80, 700, 3500, tau=0.02, shape=dsp.decay(n(1.2), 0.3), q=10)
    return dsp.fade(r + 0.25 * dsp.pan(rat, 0.2), 1, 150)


@sound("hit_cockpit_rumble_heavy", "sfx_cockpit", (0.8, 2.5), vol=0)
def rumble_heavy(rng, v):
    r = _rumble_stereo(rng, 2.3, 20, 90, 0.8, 0.6, 14)
    rat = parts.grains(rng, 2.3, 140, 500, 4000, tau=0.025, shape=dsp.decay(n(2.3), 0.7), q=10)
    sub = dsp.pan(parts.thump(rng, 2.3, 48, 24, tau=0.4, sub=0.5), 0)
    y = r * 1.5 + 0.35 * dsp.pan(rat, -0.2) + sub * 0.8
    return dsp.fade(dsp.saturate(y, 1.3), 1, 250)


@sound("hit_compensator_kick", "sfx_cockpit", (0.3, 1.0), vol=-4)
def compensator_kick(rng, v):
    # the seat/cockpit compensator pushing back: pneumatic thunk + short air release
    th = parts.thump(rng, 0.6, 95, 52, tau=0.06, sub=0.3, click=0.2)
    piston = parts.metal_hit(rng, 260, 0.25, tau0=0.05, count=5)
    air = parts.hiss(rng, 0.45, 2000, 8000, tau=0.09)
    y = parts.mix((th, 0, 1.0), (piston, 0.012, 0.5), (air, 0.03, 0.18))
    return dsp.fade(dsp.widen(y, rng, 0.3, 9.0), 0.5, 100)


@sound("hit_debris_delay", "sfx_ext", (0.8, 2.5), radius=90, variants=3)
def debris_delay(rng, v):
    sec = [1.6, 2.0, 2.4][v]
    N = n(sec)
    # nothing for ~0.15-0.35 s, then chunks and gravel raining down (layer 6)
    d0 = [0.15, 0.25, 0.35][v]
    y = np.zeros(N)
    for i in range(14 + 4 * v):
        t0 = d0 + rng.exponential(0.35) * (1 + i / 10)
        if t0 > sec - 0.3:
            continue
        kind = rng.random()
        if kind < 0.45:
            s = parts.metal_hit(rng, rng.uniform(300, 1600), 0.35, tau0=0.07, count=6)
        elif kind < 0.8:
            s = parts.thump(rng, 0.25, rng.uniform(90, 170), 60, tau=0.03, click=0.4)
        else:
            s = parts.grains(rng, 0.25, 1500, 900, 5000, tau=0.01, shape=dsp.decay(n(0.25), 0.08), q=5)
        dsp.place(y, s, t0, rng.uniform(0.15, 0.6) * np.exp(-t0 * 0.9))
    dust = parts.grains(rng, sec, 500, 1500, 6500, tau=0.01, shape=dsp.points([(0, 0), (d0, 0), (d0 + 0.2, 1), (sec, 0)], N), q=5) * 0.5
    y = y + dust
    return dsp.fade(dsp.reverb(rng, y, 0.9, mix=0.2, hf_damp=0.4), 1, 200)


@sound("parry_clang", "sfx_ext", (0.5, 2.0), radius=170)
def parry_clang(rng, v):
    y = parts.mix((parts.metal_hit(rng, 1180, 1.5, tau0=0.55, count=12, tilt=0.6, bright=1.8), 0, 1.0),
                  (parts.metal_hit(rng, 2350, 0.9, tau0=0.3, count=9, tilt=0.5, bright=1.5), 0, 0.5),
                  (parts.crack(rng, 0.06, 12000, 0.002), 0, 0.5),
                  (parts.thump(rng, 0.4, 120, 60, tau=0.05), 0, 0.3))
    return dsp.fade(dsp.reverb(rng, y, 1.0, mix=0.22, hf_damp=0.6), 0.5, 150)


@sound("intercept_clash", "sfx_ext", (0.6, 2.2), radius=170)
def intercept_clash(rng, v):
    N = n(1.6)
    t = dsp.tt(1.6)
    grind = dsp.tv_filter(dsp.white(rng, N), dsp.expo_points([(0, 3000), (0.3, 1500), (1.6, 900)], N), "bp", 3.0) \
        * dsp.points([(0, 0), (0.02, 1), (0.35, 0.5), (1.6, 0)], N) * (0.6 + 0.4 * np.sin(2 * np.pi * 40 * t))
    y = parts.mix((parts.metal_hit(rng, 640, 1.3, tau0=0.4, count=11), 0, 0.9),
                  (parts.metal_hit(rng, 910, 1.0, tau0=0.3, count=10), 0.025, 0.8),
                  (grind, 0, 0.6), (parts.crack(rng, 0.1, 9000, 0.004), 0, 0.5),
                  (parts.thump(rng, 0.6, 100, 48, tau=0.08), 0, 0.6))
    return dsp.fade(dsp.reverb(rng, dsp.saturate(y, 1.5), 0.9, mix=0.2), 0.5, 150)


@sound("block_impact", "sfx_ext", (0.3, 1.5), radius=140)
def block_impact(rng, v):
    y = parts.mix((parts.thump(rng, 0.9, 85, 40, tau=0.12, sub=0.5, click=0.15), 0, 1.0),
                  (parts.metal_hit(rng, 280, 0.6, tau0=0.12, count=7, tilt=1.2), 0, 0.6),
                  (parts.grains(rng, 0.4, 600, 600, 3000, tau=0.02, shape=dsp.decay(n(0.4), 0.1), q=6), 0.02, 0.3))
    return dsp.fade(dsp.reverb(rng, dsp.saturate(y, 1.3), 0.5, mix=0.12), 0.5, 100)


@sound("clinch_grind_loop", "sfx_ext", (8, 20), loop=True, radius=120)
def clinch_grind(rng, v):
    def gen(N):
        t = np.arange(N) / SR
        slow = np.interp(t, np.linspace(0, t[-1], 24), rng.uniform(0.7, 1.3, 24))
        sc = dsp.tv_filter(dsp.white(rng, N), 1300 * slow, "bp", 4.0) * (0.55 + 0.45 * np.sin(2 * np.pi * 9 * t * slow))
        low = dsp.tv_filter(dsp.brown(rng, N), 220 * slow, "lp", 1.0)
        creak = dsp.harmonics(110 * slow, N, (1, 0.5, 0.3, 0.2, 0.1)) * 0.25 * (0.5 + 0.5 * np.sin(2 * np.pi * 1.3 * t))
        gr = parts.grains(rng, N / SR, 90, 700, 5000, tau=0.02, q=8)[:N]
        return sc * 0.9 + low * 0.35 + creak + gr * 0.4
    return dsp.make_loop(gen, 8.0, 0.6)

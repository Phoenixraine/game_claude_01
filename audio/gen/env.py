"""Environment sounds: collapse, glass, concrete, vehicles, sea/rain/wind beds, siren, arcs, missiles, distant booms."""
import numpy as np

from . import dsp, parts
from .dsp import SR, n
from .registry import sound


def _groan(rng, sec, f0, f1, rate0=18.0, rate1=9.0, q=12.0):
    N = n(sec)
    rate = dsp.expo_points([(0, rate0), (sec, rate1)], N)
    ph = np.cumsum(rate / SR)
    pulses = np.clip(np.diff(np.floor(ph), prepend=0.0), 0, 1) * rng.uniform(0.4, 1.0, N)
    fc = dsp.expo_points([(0, f0), (sec * 0.5, f1), (sec, f0)], N)
    y = dsp.tv_filter(pulses, fc, "bp", q) + 0.6 * dsp.tv_filter(pulses, fc * 0.5, "bp", q)
    return y / (np.max(np.abs(y)) + 1e-9)


@sound("env_building_collapse_start", "sfx_ext", (2.0, 8.0), radius=600)
def collapse_start(rng, v):
    sec = 4.5
    N = n(sec)
    env = dsp.points([(0, 0), (0.6, 0.35), (2.5, 0.8), (sec, 1.0)], N)
    g = _groan(rng, sec, 140, 260, 14, 6) * 0.9 + _groan(rng, sec, 420, 700, 22, 11) * 0.4
    cracks = np.zeros(N)
    for t0 in sorted(rng.uniform(0.2, sec - 0.5, 9)):
        c = parts.mix((parts.crack(rng, 0.25, 7000, 0.012), 0, 1.0), (parts.metal_hit(rng, rng.uniform(250, 700), 0.5, tau0=0.1, count=6), 0, 0.4))
        dsp.place(cracks, c, t0, 0.3 + 0.7 * t0 / sec)
    low = dsp.bp(dsp.brown(rng, N), 20, 110, 2) * 0.9
    grit = parts.grains(rng, sec, 250, 800, 4500, tau=0.012, shape=env, q=6) * 0.5
    y = (g * 0.6 + low * 0.5 + grit) * env + cracks * 0.7
    y = dsp.reverb(rng, dsp.saturate(y, 1.3), 2.0, mix=0.25, hf_damp=0.35)
    return dsp.fade(parts.pad_to(y, sec + 1.0), 20, 600)


@sound("env_building_collapse_mid", "sfx_ext", (2.0, 8.0), radius=700)
def collapse_mid(rng, v):
    sec = 5.0
    N = n(sec)
    env = dsp.points([(0, 0.4), (0.5, 1), (3.0, 0.8), (sec, 0.3)], N)
    roar = dsp.tv_filter(dsp.white(rng, N), dsp.points([(0, 900), (2.0, 600), (sec, 350)], N), "lp", 0.7) * 0.8
    low = dsp.bp(dsp.brown(rng, N), 20, 120, 2) * 1.2 * (1 + 0.4 * np.sin(2 * np.pi * 5 * dsp.tt(sec)))
    chunks = np.zeros(N)
    for t0 in rng.uniform(0.0, sec - 0.6, 26):
        k = rng.random()
        s = parts.thump(rng, 0.5, rng.uniform(55, 110), 30, tau=0.07, click=0.4) if k < 0.5 \
            else parts.metal_hit(rng, rng.uniform(120, 900), 0.6, tau0=0.2, count=8)
        dsp.place(chunks, s, t0, rng.uniform(0.2, 0.9))
    grit = parts.grains(rng, sec, 1100, 500, 6000, tau=0.01, shape=env, q=5)
    y = (roar * 0.5 + low * 0.7 + grit * 0.5) * env + chunks * 0.6
    y = dsp.reverb(rng, dsp.saturate(y, 1.4), 2.2, mix=0.25, hf_damp=0.35)
    return dsp.fade(parts.pad_to(y, sec + 1.0), 20, 600)


@sound("env_building_collapse_end", "sfx_ext", (2.0, 8.0), radius=700)
def collapse_end(rng, v):
    sec = 5.5
    N = n(sec)
    imp = parts.mix((parts.thump(rng, 3.0, 52, 22, tau=0.6, sub=1.0, click=0.2), 0, 1.0),
                    (parts.crack(rng, 0.3, 9000, 0.02), 0, 0.5),
                    (dsp.bp(dsp.white(rng, n(2.5)), 150, 2200, 2) * dsp.decay(n(2.5), 0.7), 0, 0.7))
    clat = np.zeros(N)
    for i in range(30):
        t0 = 0.4 + rng.exponential(0.6) * (1 + i / 12)
        if t0 > sec - 0.5:
            continue
        s = parts.metal_hit(rng, rng.uniform(200, 1400), 0.4, tau0=0.08, count=6) if rng.random() < 0.5 \
            else parts.grains(rng, 0.3, 1500, 800, 4500, tau=0.01, shape=dsp.decay(n(0.3), 0.1), q=5)
        dsp.place(clat, s, t0, rng.uniform(0.1, 0.5) * np.exp(-t0 * 0.5))
    dust = dsp.lp(dsp.white(rng, N), 1800, 2) * dsp.points([(0, 0), (0.3, 0.5), (2.0, 0.2), (sec, 0)], N) * 0.2
    y = parts.mix((imp, 0, 1.0), (clat, 0, 0.8), (dust, 0, 0.5))
    y = dsp.reverb(rng, dsp.saturate(y, 1.4), 2.8, mix=0.3, hf_damp=0.3)
    return dsp.fade(parts.pad_to(y, sec + 1.5), 1, 800)


@sound("env_glass_shatter_big", "sfx_ext", (1.0, 4.0), radius=250)
def glass_big(rng, v):
    sec = 3.0
    N = n(sec)
    crk = parts.crack(rng, 0.15, 14000, 0.005)
    y = np.zeros(N)
    for i in range(160):
        t0 = abs(rng.normal(0, 0.45)) + 0.01
        if t0 > sec - 0.2:
            continue
        f = rng.uniform(2200, 9500)
        L = n(rng.uniform(0.04, 0.22))
        g = dsp.sine(f, L) * dsp.decay(L, rng.uniform(0.01, 0.06)) + 0.5 * dsp.sine(f * 2.76, L) * dsp.decay(L, 0.02)
        dsp.place(y, g, t0, rng.uniform(0.1, 0.5) / (1 + t0 * 2))
    sheet = dsp.hp(dsp.white(rng, N), 3500, 2) * dsp.points([(0, 1), (0.25, 0.4), (1.2, 0.05), (sec, 0)], N) * 0.5
    y = parts.mix((crk, 0, 0.9), (y, 0, 1.0), (sheet, 0, 0.5), (parts.thump(rng, 0.4, 120, 60, tau=0.05), 0, 0.3))
    y = dsp.reverb(rng, y, 1.4, mix=0.3, hf_damp=0.7)
    return dsp.fade(parts.pad_to(y, sec + 0.5), 0.5, 300)


@sound("env_concrete_crumble", "sfx_ext", (1.5, 6.0), radius=350)
def concrete_crumble(rng, v):
    sec = 4.0
    N = n(sec)
    env = dsp.points([(0, 0), (0.05, 1), (1.5, 0.55), (sec, 0)], N)
    low = dsp.bp(dsp.brown(rng, N), 30, 160, 2) * env * 1.2
    mid = dsp.tv_filter(dsp.white(rng, N), dsp.points([(0, 1400), (sec, 500)], N), "bp", 0.8) * env * 0.5
    gr = parts.grains(rng, sec, 1600, 400, 4000, tau=0.014, shape=env, q=5)
    blocks = np.zeros(N)
    for t0 in rng.uniform(0.1, 2.8, 8):
        dsp.place(blocks, parts.thump(rng, 0.4, rng.uniform(70, 130), 40, tau=0.05, click=0.5), t0, rng.uniform(0.3, 0.8))
    y = parts.mix((low, 0, 1.0), (mid, 0, 1.0), (gr, 0, 0.5), (blocks, 0, 0.7))
    y = dsp.reverb(rng, dsp.saturate(y, 1.2), 1.6, mix=0.22, hf_damp=0.35)
    return dsp.fade(parts.pad_to(y, sec + 0.8), 1, 500)


@sound("env_car_crush", "sfx_ext", (1.0, 4.0), radius=220)
def car_crush(rng, v):
    sec = 2.4
    N = n(sec)
    crush = _groan(rng, 1.2, 180, 350, 40, 14, q=6) * 0.8
    sheet = dsp.tv_filter(dsp.white(rng, N), dsp.points([(0, 2200), (0.4, 1200), (sec, 600)], N), "bp", 1.8) \
        * dsp.points([(0, 0), (0.02, 1), (0.6, 0.6), (1.4, 0.15), (sec, 0)], N) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 22 * dsp.tt(sec))))
    glass = np.zeros(N)
    for t0 in rng.uniform(0.0, 0.9, 40):
        f = rng.uniform(2500, 8000)
        L = n(0.08)
        dsp.place(glass, dsp.sine(f, L) * dsp.decay(L, 0.02), t0, rng.uniform(0.05, 0.25))
    y = parts.mix((crush, 0, 0.8), (sheet, 0, 0.9), (glass, 0, 0.6),
                  (parts.thump(rng, 1.2, 70, 32, tau=0.2, sub=0.6), 0, 1.0),
                  (parts.metal_hit(rng, 190, 1.2, tau0=0.35, count=9), 0, 0.6),
                  (parts.metal_hit(rng, 480, 0.6, tau0=0.12, count=8), 0.3, 0.4))
    y = dsp.reverb(rng, dsp.saturate(y, 1.5), 1.0, mix=0.2, hf_damp=0.4)
    return dsp.fade(parts.pad_to(y, sec + 0.4), 0.5, 250)


@sound("env_wave_big", "sfx_ext", (2.0, 8.0), radius=300)
def wave_big(rng, v):
    sec = 6.0
    N = n(sec)
    t = dsp.tt(sec)
    swell = dsp.points([(0, 0), (1.6, 0.5), (2.3, 1.0), (2.7, 0.8), (4.0, 0.35), (sec, 0)], N)
    body = dsp.tv_filter(dsp.white(rng, N), 300 + 2400 * swell, "lp", 0.8) * swell
    foam = dsp.hp(dsp.white(rng, N), 3000, 2) * dsp.points([(0, 0), (2.2, 0), (2.6, 0.8), (4.5, 0.2), (sec, 0)], N) * 0.5
    surge = dsp.bp(dsp.brown(rng, N), 25, 100, 2) * swell * 1.3
    gurgle = parts.grains(rng, sec, 300, 600, 2500, tau=0.02, shape=dsp.points([(0, 0), (3, 0), (4, 1), (sec, 0)], N), q=12) * 0.4
    y = body * 0.8 + foam + surge * 0.6 + gurgle
    y = dsp.reverb(rng, y, 1.4, mix=0.2, hf_damp=0.5)
    return dsp.fade(parts.pad_to(y, sec + 0.6), 50, 600)


@sound("env_water_loop_sea", "ambient", (8, 24), loop=True, radius=None, vol=-14)
def sea_loop(rng, v):
    def gen(N):
        t = np.arange(N) / SR
        out = []
        for side in range(2):
            ph = 2 * np.pi * (t / 7.5 + 0.17 * side)
            swell = 0.5 + 0.5 * np.sin(ph - 0.7 * np.sin(ph) * 0.4)
            swell = swell ** 1.8
            body = dsp.tv_filter(dsp.white(rng, N), 250 + 1400 * swell, "lp", 0.7) * (0.25 + 0.75 * swell)
            low = dsp.lp(dsp.brown(rng, N), 120, 2) * (0.3 + 0.7 * swell) * 0.9
            foam = dsp.hp(dsp.white(rng, N), 3500, 2) * swell ** 3 * 0.15
            slap = parts.grains(rng, N / SR, 40, 700, 3500, tau=0.03, shape=swell, q=6)[:N] * 0.4
            out.append(body * 0.7 + low + foam + slap)
        return np.stack(out, axis=1)
    return dsp.make_loop(gen, 22.5, 1.5)


@sound("env_rain_loop", "ambient", (8, 24), loop=True, vol=-14)
def rain_loop(rng, v):
    def gen(N):
        out = []
        for side in range(2):
            bed = dsp.bp(dsp.pink(rng, N), 900, 9000, 2) * 0.5
            hi = dsp.hp(dsp.white(rng, N), 6000, 2) * 0.08
            drops = parts.grains(rng, N / SR, 700, 1500, 7500, tau=0.004, q=4)[:N]
            plink = parts.grains(rng, N / SR, 60, 2000, 5500, tau=0.03, q=20)[:N] * 0.5
            roof = dsp.bp(dsp.pink(rng, N), 150, 600, 2) * 0.25
            out.append(bed + hi + drops * 0.6 + plink + roof)
        return np.stack(out, axis=1)
    return dsp.make_loop(gen, 20.0, 1.2)


@sound("env_wind_loop_city", "ambient", (8, 24), loop=True, vol=-14)
def wind_loop(rng, v):
    def gen(N):
        t = np.arange(N) / SR
        out = []
        for side in range(2):
            gust = np.interp(t, np.linspace(0, t[-1], 18), rng.uniform(0.3, 1.0, 18))
            gust = dsp.lp(gust, 3, 1)
            body = dsp.tv_filter(dsp.pink(rng, N), 250 + 900 * gust, "bp", 0.7) * gust
            low = dsp.lp(dsp.brown(rng, N), 90, 2) * 0.6 * gust
            wh = dsp.tv_filter(dsp.white(rng, N), 1200 + 1600 * dsp.lp(np.interp(t, np.linspace(0, t[-1], 9), rng.uniform(0, 1, 9)), 2, 1), "bp", 14.0) * gust ** 2 * 1.2
            out.append(body * 0.9 + low + wh * 0.5)
        return np.stack(out, axis=1)
    return dsp.make_loop(gen, 20.0, 1.5)


@sound("env_siren_distant_loop", "ambient", (8, 24), loop=True, vol=-20, radius=1500)
def siren_loop(rng, v):
    def gen(N):
        t = np.arange(N) / SR
        cyc = 8.0
        f = 520 + 380 * (0.5 - 0.5 * np.cos(2 * np.pi * t / cyc))
        s = dsp.harmonics(f, N, (1, 0.4, 0.55, 0.15, 0.2, 0.08, 0.1)) * 0.5
        s = dsp.lp(s, 2200, 2)
        amp = 0.7 + 0.3 * (0.5 - 0.5 * np.cos(2 * np.pi * t / cyc))
        s = s * amp
        # distance: darker, plus a few echo slaps off buildings
        out = np.stack([s, np.concatenate([np.zeros(n(0.011)), s[:-n(0.011)]])], axis=1)
        for d, g in ((0.31, 0.35), (0.62, 0.2), (1.1, 0.1)):
            sh = n(d)
            out[sh:] += g * out[:-sh][:, ::-1]
        return out
    return dsp.make_loop(gen, 16.0, 1.0)


@sound("env_substation_arc", "sfx_ext", (1.0, 4.0), radius=120)
def substation_arc(rng, v):
    sec = 3.0
    N = n(sec)
    t = dsp.tt(sec)
    mains = dsp.harmonics(100.0, N, (1, 0.5, 0.7, 0.3, 0.4, 0.2, 0.2, 0.1)) * (0.6 + 0.4 * np.sin(2 * np.pi * 3.1 * t))
    env = dsp.points([(0, 0), (0.05, 1), (1.4, 0.8), (2.2, 0.6), (sec, 0)], N)
    cr = parts.grains(rng, sec, 450, 1500, 9000, tau=0.002, shape=env * (0.4 + 0.6 * (rng.random(N) > 0.5)), q=3)
    zap = dsp.hp(dsp.white(rng, N), 4500, 2) * env * 0.12 * (np.sin(2 * np.pi * 100 * t) > 0)
    y = dsp.saturate(mains * env * 0.5, 2.0) * 0.4 + cr * 0.9 + zap
    y = parts.mix((y, 0, 1.0), (parts.crack(rng, 0.1, 12000, 0.004), 0, 0.5))
    y = dsp.reverb(rng, y, 0.8, mix=0.15)
    return dsp.fade(parts.pad_to(y, sec + 0.4), 2, 300)


@sound("env_missile_incoming", "sfx_ext", (1.5, 5.0), radius=700)
def missile_incoming(rng, v):
    sec = 3.6
    N = n(sec)
    t = dsp.tt(sec)
    approach = dsp.points([(0, 0.02), (2.4, 1.0), (2.7, 0.9), (sec, 0.0)], N) ** 1.5
    # doppler: pitch falls through the fly-by at ~2.5 s
    f = dsp.expo_points([(0, 2000), (2.4, 2400), (2.7, 1200), (sec, 800)], N)
    jet = dsp.tv_filter(dsp.white(rng, N), f * 0.6, "bp", 1.1) * approach
    whistle = dsp.harmonics(f, N, (1, 0.25, 0.1)) * approach * 0.15
    rumble = dsp.lp(dsp.brown(rng, N), 200, 2) * approach * 0.7
    y = jet * 1.0 + whistle + rumble
    y = dsp.reverb(rng, y, 1.0, mix=0.15, hf_damp=0.5)
    return dsp.fade(parts.pad_to(y, sec + 0.5), 100, 300)


@sound("env_missile_explosion", "sfx_ext", (2.0, 7.0), radius=900)
def missile_explosion(rng, v):
    sec = 5.0
    N = n(sec)
    cr = parts.crack(rng, 0.3, 14000, 0.015)
    boom = parts.thump(rng, 3.0, 66, 24, tau=0.55, sub=1.0, click=0.25)
    blast = dsp.tv_filter(dsp.white(rng, N), dsp.expo_points([(0, 6000), (0.4, 1200), (sec, 250)], N), "lp", 0.8) * dsp.decay(N, 0.7)
    debris = parts.grains(rng, 3.0, 500, 600, 6000, tau=0.012, shape=dsp.points([(0, 0), (0.25, 1), (3, 0)], n(3.0)), q=5)
    y = parts.mix((cr, 0, 0.9), (boom, 0, 1.0), (blast, 0, 0.8), (debris, 0.1, 0.6),
                  (parts.metal_hit(rng, 260, 1.5, tau0=0.4, count=9), 0.4, 0.3))
    y = dsp.reverb(rng, dsp.saturate(y, 1.8), 2.6, mix=0.3, hf_damp=0.35)
    return dsp.fade(parts.pad_to(y, sec + 1.0), 1, 800)


@sound("env_distant_boom", "sfx_ext", (2.0, 7.0), radius=2500, variants=3)
def distant_boom(rng, v):
    sec = [3.5, 4.5, 5.5][v]
    N = n(sec)
    f0 = [48, 40, 56][v]
    delay = [0.0, 0.08, 0.2][v]
    body = parts.thump(rng, sec - 0.5, f0, f0 * 0.5, tau=0.5 + 0.1 * v, sub=0.6, click=0.0)
    rolling = dsp.tv_filter(dsp.brown(rng, N), dsp.points([(0, 260), (sec, 70)], N), "lp", 0.7) * dsp.points([(0, 0), (0.25, 1), (sec * 0.5, 0.45), (sec, 0)], N) * 1.0
    y = parts.mix((body, delay, 1.0), (rolling, delay, 0.8))
    y = dsp.lp(y, 380, 2)
    y = dsp.reverb(rng, y, 2.4, mix=0.35, hf_damp=0.25)
    return dsp.fade(parts.pad_to(y, sec + 0.8), 8, 700)

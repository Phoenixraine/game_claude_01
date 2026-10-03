"""Interior (cockpit) sounds: reactor bed, breathing, harness, switches, alarms, sparks, sensors, HUD cues. All stereo."""
import numpy as np

from . import dsp, parts
from .dsp import SR, n
from .registry import sound


@sound("cockpit_reactor_loop", "sfx_cockpit", (8, 24), loop=True, vol=-12)
def reactor_loop(rng, v):
    def gen(N):
        t = np.arange(N) / SR
        ch = []
        for side, det in ((0, 0.0), (1, 0.35)):
            f = 54.0 + det
            core = dsp.harmonics(f * (1 + 0.002 * np.sin(2 * np.pi * 0.11 * t + side)), N, (1, 0.55, 0.38, 0.22, 0.12, 0.07))
            beat = 0.7 + 0.3 * np.sin(2 * np.pi * (0.7 + 0.13 * side) * t + side)
            air = dsp.lp(dsp.pink(rng, N), 280, 2) * 0.8
            whine = dsp.sine(6800 + 60 * np.sin(2 * np.pi * 0.3 * t), N) * 0.012
            coil = dsp.resonator(dsp.white(rng, N), 1400 + 20 * side, 40) * 0.07
            ch.append(core * beat * 0.7 + air + whine + coil)
        return np.stack(ch, axis=1)
    return dsp.make_loop(gen, 16.0, 1.0)


@sound("cockpit_breath_loop", "sfx_cockpit", (8, 24), loop=True, vol=-14)
def breath_loop(rng, v):
    cycle = 4.0

    def gen(N):
        t = np.arange(N) / SR
        ph = (t % cycle) / cycle
        # inhale (0..0.4) louder and brighter, short pause, exhale (0.5..0.95) softer and darker
        inh = np.exp(-0.5 * ((ph - 0.2) / 0.1) ** 2)
        exh = np.exp(-0.5 * ((ph - 0.72) / 0.13) ** 2) * 0.8
        out = []
        for side in range(2):
            nz = dsp.white(rng, N)
            a = dsp.tv_filter(nz, 1700 + 700 * inh, "bp", 0.9)
            b = dsp.tv_filter(nz, 900 + 300 * exh, "bp", 0.9)
            y = a * inh * 0.9 + b * exh * 0.7
            valve = dsp.resonator(dsp.white(rng, N), 3200, 12) * (inh + 0.6 * exh) * 0.12
            out.append(y + valve)
        mask = dsp.lp(dsp.pink(rng, N), 220, 2) * 0.05
        return np.stack(out, axis=1) + mask[:, None]
    return dsp.make_loop(gen, 12.0, 0.8)


@sound("cockpit_harness_creak", "sfx_cockpit", (0.4, 2.0), vol=-8)
def harness_creak(rng, v):
    sec = 1.1
    N = n(sec)
    y = np.zeros(N)
    pulses = np.zeros(N)
    rate = dsp.points([(0, 70), (0.5, 38), (sec, 22)], N)
    ph = np.cumsum(rate / SR)
    pulses = np.clip(np.diff(np.floor(ph), prepend=0.0), 0, 1) * rng.uniform(0.4, 1.0, N)
    fc = dsp.points([(0, 380), (0.5, 520), (sec, 300)], N)
    y = dsp.tv_filter(pulses, fc, "bp", 9.0) + 0.4 * dsp.tv_filter(pulses, fc * 2.4, "bp", 8.0)
    rub = dsp.bp(dsp.white(rng, N), 800, 3000, 2) * 0.12 * dsp.points([(0, 0), (0.1, 1), (sec, 0)], N)
    y = (y / (np.max(np.abs(y)) + 1e-9) + rub) * dsp.points([(0, 0), (0.15, 1), (0.8, 0.7), (sec, 0)], N)
    return dsp.fade(dsp.widen(y, rng, 0.3, 7.0), 5, 80)


@sound("cockpit_switch", "sfx_cockpit", (0.1, 0.6), vol=-8, variants=4)
def switch(rng, v):
    base = [1900, 1400, 2400, 1100][v]
    down = parts.mix((parts.metal_hit(rng, base, 0.12, tau0=0.012, count=5), 0, 1.0), (parts.crack(rng, 0.02, 7000, 0.0015), 0, 0.6))
    up = parts.metal_hit(rng, base * 1.25, 0.1, tau0=0.01, count=4) * 0.6
    body = parts.thump(rng, 0.1, 190 + 30 * v, 120, tau=0.012, click=0.0) * 0.5
    gap = [0.11, 0.07, 0.15, 0.09][v]
    y = parts.mix((down, 0, 1.0), (body, 0, 0.4), (up, gap, 0.7), (body, gap, 0.2))
    return dsp.fade(dsp.widen(parts.pad_to(y, 0.35), rng, 0.2, 5.0), 0.2, 40)


def _beeps(freqs, durs, gaps, rate=1.0, shape="sq", rng=None):
    out = np.zeros(0)
    for f, d, g in zip(freqs, durs, gaps):
        N = n(d / rate)
        x = dsp.square(f, N) if shape == "sq" else dsp.sine(f, N)
        x = dsp.lp(x, 4200, 2) * dsp.adsr(N, 0.004, 0.01, 0.9, 0.012)
        out = np.concatenate([out, x, np.zeros(n(g / rate))])
    return out


@sound("cockpit_alarm_warning", "sfx_cockpit", (1.0, 4.0), vol=-8)
def alarm_warning(rng, v):
    y = _beeps([880, 660, 880, 660], [0.18] * 4, [0.1, 0.22, 0.1, 0.4])
    sig = dsp.reverb(rng, y, 0.35, mix=0.12)
    return dsp.fade(dsp.widen(sig, rng, 0.2, 6.0), 1, 60)


@sound("cockpit_alarm_critical", "sfx_cockpit", (1.0, 4.0), vol=-5)
def alarm_critical(rng, v):
    N = n(2.4)
    t = dsp.tt(2.4)
    gate = (np.sin(2 * np.pi * 4.0 * t) > -0.2).astype(float)
    gate = dsp.lp(gate, 90, 2)
    sweep = dsp.expo_points([(0, 1000), (0.12, 1300), (0.25, 1000)], n(0.25))
    f = np.tile(sweep, N // len(sweep) + 1)[:N]
    y = dsp.saturate(dsp.lp(dsp.square(f, N), 5000, 2) * 0.8 + dsp.sine(f * 0.5, N) * 0.5, 2.0) * gate
    y = y * dsp.points([(0, 0), (0.01, 1), (2.2, 1), (2.4, 0)], N)
    y = dsp.reverb(rng, y, 0.4, mix=0.12)
    return dsp.fade(dsp.widen(y, rng, 0.25, 6.0), 1, 80)


@sound("cockpit_coolant_leak_loop", "sfx_cockpit", (8, 24), loop=True, vol=-12)
def coolant_leak_loop(rng, v):
    def gen(N):
        t = np.arange(N) / SR
        out = []
        for side in range(2):
            hs = dsp.hp(dsp.white(rng, N), 3500, 2) * (0.7 + 0.3 * dsp.lp(dsp.white(rng, N), 4, 1) * 6)
            hs = hs * 0.35
            drips = np.zeros(N)
            for _ in range(int(N / SR * 3.5)):
                t0 = rng.integers(0, N - n(0.1))
                L = n(0.05)
                f = rng.uniform(900, 2400)
                fr = np.linspace(f, f * 1.7, L)
                drips[t0:t0 + L] += dsp.sine(fr, L) * dsp.decay(L, 0.012) * rng.uniform(0.15, 0.5)
            hiss_low = dsp.bp(dsp.white(rng, N), 800, 2200, 2) * 0.1
            out.append(hs + drips + hiss_low)
        return np.stack(out, axis=1)
    return dsp.make_loop(gen, 8.0, 0.5)


@sound("cockpit_spark", "sfx_cockpit", (0.2, 1.2), vol=-6, variants=4)
def spark(rng, v):
    sec = [0.45, 0.7, 0.55, 0.9][v]
    N = n(sec)
    env = dsp.points([(0, 1), (sec * 0.4, 0.5), (sec, 0)], N)
    cl = parts.grains(rng, sec, [900, 600, 1200, 500][v], 1800, 9000, tau=0.002, shape=env, q=3)
    zap = dsp.hp(dsp.white(rng, N), 5000, 2) * dsp.decay(N, 0.04) * 0.5
    buzz = dsp.lp(dsp.saw(100, N), 1500, 2) * dsp.decay(N, 0.08) * 0.3
    y = (cl * 0.8 + zap + buzz) * env
    return dsp.fade(dsp.widen(y, rng, 0.3, 8.0 + v), 0.2, 80)


@sound("cockpit_panel_burst", "sfx_cockpit", (0.4, 2.0), vol=-3)
def panel_burst(rng, v):
    sec = 1.4
    cr = parts.crack(rng, 0.2, 11000, 0.01)
    pop = parts.thump(rng, 0.4, 140, 70, tau=0.05, click=0.5)
    plate = parts.metal_hit(rng, 700, 0.6, tau0=0.12, count=7)
    glass = parts.grains(rng, 0.8, 900, 2500, 9000, tau=0.006, shape=dsp.decay(n(0.8), 0.2), q=10)
    hs = parts.hiss(rng, 1.2, 2500, 9000, tau=0.3)
    y = parts.mix((cr, 0, 0.9), (pop, 0, 0.8), (plate, 0.01, 0.4), (glass, 0.02, 0.5), (hs, 0.03, 0.25))
    return dsp.fade(dsp.widen(parts.pad_to(y, sec), rng, 0.3, 8.0), 0.5, 200)


@sound("cockpit_sensor_fail_static", "sfx_cockpit", (0.6, 3.0), vol=-8)
def sensor_fail(rng, v):
    sec = 1.8
    N = n(sec)
    t = dsp.tt(sec)
    gate = (rng.random(n(0.03) + 1)[np.minimum(np.arange(N) // n(0.03), n(0.03))] > 0.35).astype(float)
    stat = dsp.white(rng, N) * gate * 0.8 + dsp.hp(dsp.white(rng, N), 6000, 2) * 0.3
    tone = dsp.sine(dsp.points([(0, 1500), (0.2, 1500), (0.5, 220), (sec, 90)], N), N) * dsp.points([(0, 0.6), (0.4, 0.4), (sec, 0)], N)
    env = dsp.points([(0, 0), (0.005, 1), (0.6, 0.7), (sec, 0)], N)
    y = (stat * 0.6 + tone * 0.5) * env
    return dsp.fade(dsp.widen(y, rng, 0.4, 5.0), 0.5, 150)


@sound("cockpit_sensor_boot", "sfx_cockpit", (0.6, 4.0), vol=-8)
def sensor_boot(rng, v):
    sec = 2.2
    N = n(sec)
    notes = [(0.0, 700), (0.12, 900), (0.24, 1200), (0.36, 1600), (0.62, 1050), (0.74, 2100)]
    y = np.zeros(N)
    for t0, f in notes:
        L = n(0.09)
        s = dsp.lp(dsp.square(f, L), 5000, 2) * dsp.adsr(L, 0.003, 0.02, 0.7, 0.03)
        dsp.place(y, s, t0, 0.35)
    stat = dsp.white(rng, N) * dsp.points([(0, 0.4), (0.4, 0.3), (1.2, 0.0), (sec, 0)], N) * 0.5
    hum = dsp.harmonics(dsp.points([(0, 40), (1.0, 110), (sec, 110)], N), N, (1, 0.5, 0.3)) * dsp.points([(0, 0), (0.8, 0.8), (sec, 0)], N) * 0.5
    y = y + stat + hum
    y = dsp.reverb(rng, y, 0.5, mix=0.15)
    return dsp.fade(dsp.widen(parts.pad_to(y, sec), rng, 0.3, 7.0), 2, 200)


def _chirp(f0, f1, sec=0.16):
    N = n(sec)
    fr = dsp.expo_points([(0, f0), (sec, f1)], N)
    return dsp.lp(dsp.sine(fr, N) + 0.3 * dsp.sine(fr * 2, N), 6000, 2) * dsp.adsr(N, 0.004, 0.03, 0.6, 0.06)


@sound("cockpit_hud_lock", "sfx_cockpit", (0.1, 1.0), vol=-8)
def hud_lock(rng, v):
    y = parts.mix((_chirp(900, 1500, 0.1), 0, 0.5), (_chirp(1500, 1500, 0.2), 0.11, 0.6))
    return dsp.fade(dsp.widen(dsp.reverb(rng, y, 0.3, mix=0.1), rng, 0.2, 5.0), 1, 60)


@sound("cockpit_hud_unlock", "sfx_cockpit", (0.1, 1.0), vol=-8)
def hud_unlock(rng, v):
    y = parts.mix((_chirp(1500, 1500, 0.08), 0, 0.5), (_chirp(1500, 700, 0.2), 0.09, 0.6))
    return dsp.fade(dsp.widen(dsp.reverb(rng, y, 0.3, mix=0.1), rng, 0.2, 5.0), 1, 60)

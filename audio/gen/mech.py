"""Exterior mech sounds: footsteps, servos, hydraulics, weapon, joints, armour tearing, sever."""
import numpy as np

from . import dsp, parts
from .dsp import SR, n
from .registry import sound


@sound("mech_step_heavy", "sfx_ext", (1.2, 2.5), vol=0.0, radius=220, variants=4)
def step_heavy(rng, v):
    f0 = [74, 66, 80, 60][v]
    N = n(2.0)
    heel = parts.thump(rng, 1.4, f0, f0 * 0.42, tau=0.16 + 0.02 * v, sub=0.6)
    toe = parts.thump(rng, 1.0, f0 * 1.15, f0 * 0.55, tau=0.1, sub=0.3)
    plate = parts.metal_hit(rng, [310, 380, 270, 440][v], 0.7, tau0=0.18, count=8)
    clank = parts.metal_hit(rng, [900, 760, 1100, 840][v], 0.45, tau0=0.08, count=7)
    gravel = parts.grains(rng, 0.8, 900, 400, 3500, shape=dsp.decay(n(0.8), 0.25))
    hyd = parts.hiss(rng, 0.9, 2500, 8000, tau=0.22)
    y = parts.mix((heel, 0.0, 1.0), (toe, 0.11 + 0.01 * v, 0.55), (plate, 0.0, 0.5), (clank, 0.12, 0.28),
                  (gravel, 0.02, 0.18), (hyd, 0.2, 0.09))
    y = dsp.saturate(y, 1.4)
    y = dsp.reverb(rng, y, 1.1, mix=0.25, hf_damp=0.4)
    return dsp.fade(parts.pad_to(y, 2.0), 1, 30)


@sound("mech_step_water", "sfx_ext", (1.2, 2.5), radius=180, variants=2)
def step_water(rng, v):
    N = n(2.2)
    thump = parts.thump(rng, 1.0, 58 + 8 * v, 32, tau=0.12, sub=0.5, click=0.05)
    # splash body: band-limited noise with a fast swell and a slower tail
    sp = dsp.bp(dsp.white(rng, N), 350, 3800, 2)
    env = dsp.points([(0, 0), (0.012, 1), (0.12, 0.55), (0.5, 0.18), (1.4, 0.04), (2.2, 0)], N)
    # bubbles: rising chirps
    bub = np.zeros(N)
    for _ in range(26):
        t0 = rng.uniform(0.02, 1.4)
        f = rng.uniform(300, 1400)
        L = n(rng.uniform(0.03, 0.08))
        fr = np.linspace(f, f * rng.uniform(1.6, 2.4), L)
        b = dsp.sine(fr, L) * dsp.decay(L, 0.02) * rng.uniform(0.1, 0.5) * np.exp(-t0 * 1.6)
        dsp.place(bub, b, t0)
    drops = parts.grains(rng, 1.8, 120, 1800, 7000, tau=0.01, shape=dsp.decay(n(1.8), 0.7), q=5)
    y = parts.mix((thump, 0, 0.9), (sp * env, 0, 0.9), (bub, 0, 0.5), (drops, 0.1, 0.25))
    y = dsp.reverb(rng, y, 0.9, mix=0.15, hf_damp=0.3)
    return dsp.fade(parts.pad_to(y, 2.2), 1, 40)


@sound("mech_step_rubble", "sfx_ext", (1.2, 2.5), radius=200, variants=2)
def step_rubble(rng, v):
    thump = parts.thump(rng, 1.2, 68 - 6 * v, 34, tau=0.14, sub=0.5, click=0.1)
    N = n(2.0)
    crunch = parts.grains(rng, 1.9, 2400, 500, 4500, shape=dsp.decay(N, 0.32) * (1 + 0.6 * np.sin(np.arange(N) / SR * 40)), q=6)
    chunks = np.zeros(N)
    for _ in range(9):
        t0 = rng.uniform(0.04, 1.2)
        m = parts.metal_hit(rng, rng.uniform(250, 900), 0.25, tau0=0.05, count=5) * rng.uniform(0.1, 0.4)
        dsp.place(chunks, m, t0)
    concrete = dsp.bp(dsp.white(rng, N), 200, 1500, 2) * dsp.decay(N, 0.18) * 0.6
    y = parts.mix((thump, 0, 1.0), (crunch, 0.015, 0.45), (chunks, 0, 0.8), (concrete, 0.0, 0.5))
    y = dsp.saturate(y, 1.2)
    y = dsp.reverb(rng, y, 0.8, mix=0.18, hf_damp=0.35)
    return dsp.fade(parts.pad_to(y, 2.0), 1, 40)


@sound("mech_servo_arm_windup", "sfx_ext", (0.5, 2.0), radius=90)
def servo_windup(rng, v):
    sec = 1.1
    N = n(sec)
    fr = dsp.expo_points([(0, 160), (0.9, 520), (sec, 540)], N)
    tooth = fr * 0.25
    y = parts.servo(fr, N, rng=rng, tooth=tooth, noise=0.1)
    motor = dsp.harmonics(dsp.expo_points([(0, 55), (0.9, 130), (sec, 135)], N), N, (1, 0.5, 0.3, 0.2))
    env = dsp.points([(0, 0), (0.08, 0.5), (0.85, 1), (sec, 0.9)], N)
    # hydraulic hiss swelling and a locking clunk at the end
    hs = dsp.bp(dsp.white(rng, N), 2000, 7000, 2) * dsp.points([(0, 0), (0.5, 0.2), (0.9, 0.35), (sec, 0.0)], N)
    clunk = parts.metal_hit(rng, 420, 0.3, tau0=0.06, count=6)
    y = dsp.lp(y * env, 6000, 2) * 0.5 + motor * env * 0.55 + hs * 0.35
    y = parts.mix((y, 0, 1.0), (clunk, 0.93, 0.5), (parts.thump(rng, 0.25, 110, 60, tau=0.04), 0.93, 0.4))
    y = dsp.reverb(rng, y, 0.5, mix=0.12)
    return dsp.fade(parts.pad_to(y, 1.3), 4, 60)


@sound("mech_servo_arm_strike", "sfx_ext", (0.4, 1.5), radius=130)
def servo_strike(rng, v):
    sec = 0.9
    N = n(sec)
    fr = dsp.expo_points([(0, 700), (0.18, 260), (0.4, 180), (sec, 120)], N)
    y = parts.servo(fr, N, harm=(1, 0.6, 0.4, 0.3), rng=rng, tooth=fr * 0.2, noise=0.06)
    env = dsp.points([(0, 0), (0.01, 1), (0.25, 0.5), (sec, 0)], N)
    whoosh = dsp.tv_filter(dsp.white(rng, N), dsp.points([(0, 4000), (0.15, 2200), (0.5, 700), (sec, 300)], N), "bp", 1.4)
    wenv = dsp.points([(0, 0), (0.04, 1), (0.3, 0.55), (sec, 0)], N)
    puff = parts.hiss(rng, 0.5, 1800, 9000, tau=0.1)
    y = dsp.lp(y * env, 5000, 2) * 0.55 + whoosh * wenv * 0.9
    y = parts.mix((y, 0, 1.0), (puff, 0.0, 0.3), (parts.thump(rng, 0.4, 90, 45, tau=0.07), 0.0, 0.4))
    y = dsp.reverb(rng, y, 0.6, mix=0.12)
    return dsp.fade(parts.pad_to(y, 1.1), 1, 60)


@sound("mech_hydraulic_release", "sfx_ext", (0.6, 2.5), radius=110)
def hydraulic_release(rng, v):
    sec = 1.6
    N = n(sec)
    x = dsp.white(rng, N)
    fc = dsp.expo_points([(0, 7500), (0.25, 4200), (sec, 1400)], N)
    y = dsp.tv_filter(x, fc, "lp", 0.8)
    y = dsp.hp(y, 900, 2)
    env = dsp.points([(0, 0), (0.006, 1), (0.25, 0.7), (0.9, 0.2), (sec, 0)], N)
    # pneumatic valve: sharp click + short low "chuff"
    click = parts.metal_hit(rng, 1700, 0.12, tau0=0.02, count=5)
    chuff = dsp.lp(dsp.white(rng, n(0.3)), 300, 2) * dsp.decay(n(0.3), 0.06)
    y = parts.mix((y * env, 0, 0.9), (click, 0, 0.35), (chuff, 0, 0.6))
    y = dsp.reverb(rng, y, 0.7, mix=0.15)
    return dsp.fade(parts.pad_to(y, 1.8), 1, 80)


@sound("mech_stabilizer_whine", "sfx_ext", (0.6, 2.5), radius=70)
def stabilizer_whine(rng, v):
    sec = 1.8
    N = n(sec)
    t = dsp.tt(sec)
    f = 1100 + 180 * np.sin(2 * np.pi * 1.7 * t) + dsp.points([(0, -250), (0.5, 0), (sec, 80)], N)
    y = dsp.harmonics(f, N, (1.0, 0.0, 0.35, 0.0, 0.15)) * (0.8 + 0.2 * np.sin(2 * np.pi * 9 * t))
    flutter = dsp.resonator(dsp.white(rng, N), 2400, 25) * 3
    env = dsp.points([(0, 0), (0.25, 1), (1.3, 0.8), (sec, 0)], N)
    low = dsp.harmonics(95 + 6 * np.sin(2 * np.pi * 1.7 * t), N, (1, 0.4, 0.2)) * 0.5
    y = (y * 0.55 + flutter * 0.12 + low) * env
    y = dsp.reverb(rng, y, 0.5, mix=0.1)
    return dsp.fade(parts.pad_to(y, 2.0), 20, 80)


@sound("mech_power_shift", "sfx_ext", (0.5, 2.5), radius=60)
def power_shift(rng, v):
    sec = 1.4
    N = n(sec)
    sweep = dsp.tv_filter(dsp.white(rng, N), dsp.expo_points([(0, 200), (0.55, 2400), (sec, 700)], N), "bp", 3.0)
    swenv = dsp.points([(0, 0), (0.15, 0.7), (0.55, 1.0), (sec, 0)], N)
    sub = dsp.sine(dsp.expo_points([(0, 50), (0.55, 120), (sec, 70)], N), N) * dsp.points([(0, 0), (0.1, 1), (sec, 0)], N)
    buzz = dsp.lp(dsp.saw(dsp.expo_points([(0, 90), (0.55, 240), (sec, 120)], N), N), 1800, 2) * 0.25 * swenv
    zap = parts.crack(rng, 0.1, 9000, 0.004)
    y = sweep * swenv * 0.9 + sub * 0.7 + buzz
    y = parts.mix((y, 0, 1.0), (zap, 0.55, 0.3))
    y = dsp.reverb(rng, y, 0.7, mix=0.15)
    return dsp.fade(parts.pad_to(y, 1.6), 4, 100)


@sound("mech_weapon_charge_loop", "sfx_ext", (8, 20), loop=True, radius=90)
def weapon_charge_loop(rng, v):
    def gen(N):
        t = np.arange(N) / SR
        wob = 1.0 + 0.012 * np.sin(2 * np.pi * 0.5 * t)
        core = dsp.harmonics(220 * wob, N, (1, 0.55, 0.3, 0.2, 0.12, 0.08)) * (0.7 + 0.3 * np.sin(2 * np.pi * 12 * t))
        low = dsp.harmonics(55 * wob, N, (1, 0.6, 0.35)) * 0.8
        whine = dsp.sine(1760 * wob + 40 * np.sin(2 * np.pi * 0.25 * t), N) * 0.12
        arc = dsp.hp(dsp.white(rng, N), 4500, 2) * (0.04 + 0.04 * (np.sin(2 * np.pi * 7 * t) > 0.8))
        return core * 0.45 + low + whine + arc
    y = dsp.make_loop(gen, 8.0, 0.5)
    return y


@sound("mech_weapon_charge_peak", "sfx_ext", (0.5, 2.5), radius=100)
def weapon_charge_peak(rng, v):
    sec = 1.4
    N = n(sec)
    t = dsp.tt(sec)
    # the "ready" signal (§13): a clear two-partial ring over a charged hum
    ring = dsp.sine(1320, N) * 0.5 + dsp.sine(1980.5, N) * 0.3 + dsp.sine(2640, N) * 0.12
    ring *= dsp.points([(0, 0), (0.006, 1), (0.2, 0.55), (sec, 0)], N) * (1 + 0.15 * np.sin(2 * np.pi * 6 * t))
    hum = dsp.harmonics(220, N, (1, 0.5, 0.3, 0.2)) * dsp.points([(0, 0.3), (0.3, 1), (sec, 0)], N) * 0.5
    snap = parts.crack(rng, 0.1, 10000, 0.003)
    y = parts.mix((ring, 0, 0.7), (hum, 0, 0.6), (snap, 0, 0.35), (parts.thump(rng, 0.5, 90, 50, tau=0.1), 0, 0.5))
    y = dsp.reverb(rng, y, 0.9, mix=0.2, hf_damp=0.7)
    return dsp.fade(parts.pad_to(y, 1.8), 1, 120)


@sound("mech_weapon_fire", "sfx_ext", (1.2, 4.0), radius=500)
def weapon_fire(rng, v):
    sec = 3.0
    N = n(sec)
    cr = parts.crack(rng, 0.25, 12000, 0.012)
    boom = parts.thump(rng, 1.8, 62, 26, tau=0.4, sub=0.8, click=0.2)
    zap = dsp.tv_filter(dsp.white(rng, n(0.6)), dsp.expo_points([(0, 9000), (0.5, 600)], n(0.6)), "lp", 1.0) * dsp.decay(n(0.6), 0.12)
    ring = dsp.sine(dsp.expo_points([(0, 2400), (0.7, 500)], n(0.8)), n(0.8)) * dsp.decay(n(0.8), 0.18) * 0.3
    body = dsp.lp(dsp.white(rng, n(1.0)), 700, 2) * dsp.decay(n(1.0), 0.28)
    y = parts.mix((cr, 0, 0.9), (boom, 0, 1.0), (zap, 0.0, 0.5), (ring, 0, 0.5), (body, 0.0, 0.8))
    y = dsp.saturate(y, 1.8)
    y = dsp.reverb(rng, y, 2.2, mix=0.35, hf_damp=0.4)
    return dsp.fade(parts.pad_to(y, 3.5), 1, 200)


def _creak(rng, sec, rate0, rate1, f0, f1, q=14.0, rough=0.25):
    """Stick-slip: a pulse train with jittered rate excites a moving resonance."""
    N = n(sec)
    rate = dsp.expo_points([(0, rate0), (sec * 0.5, (rate0 + rate1) / 2 * rng.uniform(0.7, 1.3)), (sec, rate1)], N)
    ph = np.cumsum(rate / SR + rough * rate / SR * 0.5 * rng.standard_normal(N) * 0.05)
    pulses = np.diff(np.floor(ph), prepend=0.0)
    pulses = np.clip(pulses, 0, 1) * rng.uniform(0.5, 1.0, N)
    fc = dsp.expo_points([(0, f0), (sec * 0.6, f1), (sec, f0 * 1.1)], N)
    y = dsp.tv_filter(pulses, fc, "bp", q)
    y += 0.5 * dsp.tv_filter(pulses, fc * 2.1, "bp", q)
    y /= np.max(np.abs(y)) + 1e-9
    env = dsp.points([(0, 0), (sec * 0.2, 1), (sec * 0.7, 0.8), (sec, 0)], N)
    return y * env


@sound("mech_joint_creak", "sfx_ext", (0.8, 2.5), radius=45, variants=3)
def joint_creak(rng, v):
    sec = [1.5, 1.9, 1.2][v]
    y = _creak(rng, sec, [35, 24, 55][v], [70, 40, 28][v], [820, 560, 1400][v], [1250, 900, 760][v])
    y = y + 0.3 * dsp.bp(dsp.white(rng, len(y)), 2000, 6000, 2) * np.abs(y) * 2
    y = dsp.reverb(rng, y, 0.5, mix=0.12)
    return dsp.fade(parts.pad_to(y, sec + 0.3), 8, 80)


@sound("mech_armor_plate_tear", "sfx_ext", (0.8, 3.0), radius=140)
def plate_tear(rng, v):
    sec = 1.9
    N = n(sec)
    t = dsp.tt(sec)
    # screeching sweep with a rasp (AM noise) and ripping crackle
    f = dsp.expo_points([(0, 1400), (0.5, 2600), (1.2, 1800), (sec, 900)], N) * (1 + 0.03 * np.sin(2 * np.pi * 31 * t))
    scr = dsp.saw(f, N) * 0.5
    rasp = dsp.tv_filter(dsp.white(rng, N), f * 1.5, "bp", 2.5) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 85 * t + 6 * np.sin(2 * np.pi * 7 * t))))
    env = dsp.points([(0, 0), (0.03, 1), (0.9, 0.8), (sec, 0)], N)
    rip = parts.grains(rng, sec, 900, 1200, 7000, tau=0.006, shape=env, q=4)
    groan = _creak(rng, sec, 28, 14, 360, 520, q=10)
    y = (scr * 0.45 + rasp * 0.9 + rip * 0.35 + groan * 0.5) * env
    y = parts.mix((y, 0, 1.0), (parts.metal_hit(rng, 520, 0.9, tau0=0.25, count=8), 0.0, 0.45),
                  (parts.thump(rng, 0.5, 80, 40, tau=0.08), 0.0, 0.5))
    y = dsp.saturate(y, 1.6)
    y = dsp.reverb(rng, y, 0.8, mix=0.18)
    return dsp.fade(parts.pad_to(y, 2.2), 1, 100)


@sound("mech_limb_sever", "sfx_ext", (1.5, 4.0), radius=320)
def limb_sever(rng, v):
    sec = 3.2
    N = n(sec)
    cr = parts.crack(rng, 0.3, 14000, 0.02)
    boom = parts.thump(rng, 2.0, 70, 28, tau=0.35, sub=0.8, click=0.2)
    tear = plate_tear(rng, 0)
    sizzle = parts.grains(rng, 2.0, 700, 3000, 11000, tau=0.004, shape=dsp.decay(n(2.0), 0.9), q=3) * 0.8
    parts_ = [(cr, 0.0, 1.0), (boom, 0.0, 1.0), (tear, 0.02, 0.8), (sizzle, 0.1, 0.35)]
    # the severed limb: heavy clanging falls
    for i, t0 in enumerate([0.55, 0.95, 1.35, 1.65]):
        parts_.append((parts.metal_hit(rng, rng.uniform(150, 420), 1.0, tau0=0.4, count=9), t0, 0.5 / (1 + i * 0.5)))
        parts_.append((parts.thump(rng, 0.6, 60, 30, tau=0.1), t0, 0.5 / (1 + i * 0.5)))
    y = parts.mix(*parts_)
    y = dsp.saturate(y, 1.5)
    y = dsp.reverb(rng, y, 2.0, mix=0.3, hf_damp=0.4)
    return dsp.fade(parts.pad_to(y, sec + 0.3), 1, 250)

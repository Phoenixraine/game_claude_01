"""Menu / HUD sounds and the hangar ambience. Soft, short, dry-ish: the cockpit is an industrial machine, not a toy."""
import numpy as np

from . import dsp, parts
from .dsp import SR, n
from .registry import sound


def _tone(f0, f1, sec, harm=(1.0, 0.3, 0.12), att=0.004, rel=0.05, lpf=6000):
    N = n(sec)
    fr = dsp.expo_points([(0, f0), (sec, f1)], N)
    return dsp.lp(dsp.harmonics(fr, N, harm), lpf, 2) * dsp.adsr(N, att, sec * 0.3, 0.55, rel)


@sound("ui_move", "ui", (0.05, 0.5), vol=-10, peak=-6.0)
def ui_move(rng, v):
    y = parts.mix((_tone(1250, 1250, 0.07, (1, 0.15)), 0, 0.7), (parts.metal_hit(rng, 2600, 0.08, tau0=0.01, count=4), 0, 0.3))
    return dsp.fade(dsp.reverb(rng, y, 0.25, mix=0.1), 0.3, 30)


@sound("ui_confirm", "ui", (0.1, 0.8), vol=-8, peak=-4.0)
def ui_confirm(rng, v):
    y = parts.mix((_tone(880, 880, 0.1), 0, 0.6), (_tone(1320, 1320, 0.2, att=0.004, rel=0.12), 0.08, 0.7),
                  (parts.metal_hit(rng, 1900, 0.2, tau0=0.03, count=5), 0.08, 0.25))
    return dsp.fade(dsp.reverb(rng, y, 0.4, mix=0.12), 0.3, 80)


@sound("ui_back", "ui", (0.1, 0.8), vol=-9, peak=-5.0)
def ui_back(rng, v):
    y = parts.mix((_tone(990, 990, 0.08), 0, 0.5), (_tone(660, 560, 0.16, rel=0.08), 0.07, 0.6))
    return dsp.fade(dsp.reverb(rng, y, 0.3, mix=0.1), 0.3, 60)


@sound("ui_deny", "ui", (0.1, 0.8), vol=-8, peak=-4.0)
def ui_deny(rng, v):
    N = n(0.32)
    y = np.zeros(N)
    for t0 in (0.0, 0.14):
        L = n(0.12)
        s = dsp.lp(dsp.square(150, L), 1200, 2) * dsp.adsr(L, 0.003, 0.02, 0.8, 0.03) + 0.4 * dsp.lp(dsp.saw(158, L), 1500, 2) * dsp.adsr(L, 0.003, 0.02, 0.8, 0.03)
        dsp.place(y, s, t0, 0.7)
    return dsp.fade(dsp.reverb(rng, y, 0.25, mix=0.08), 0.3, 40)


@sound("ui_hangar_ambience_loop", "ambient", (8, 24), loop=True, vol=-14)
def hangar_loop(rng, v):
    def gen(N):
        t = np.arange(N) / SR
        out = []
        for side in range(2):
            hum = dsp.harmonics(50.0 + 0.15 * side, N, (1, 0.5, 0.25, 0.12)) * 0.5
            room = dsp.lp(dsp.pink(rng, N), 600, 2) * 0.6
            vent = dsp.tv_filter(dsp.white(rng, N), 900 + 250 * np.sin(2 * np.pi * t / 8.0 + side), "bp", 0.8) * (0.25 + 0.1 * np.sin(2 * np.pi * t / 16))
            far = np.zeros(N)
            for t0 in rng.uniform(0.5, N / SR - 1.5, 5):
                c = parts.metal_hit(rng, rng.uniform(150, 700), 1.0, tau0=0.3, count=8) * 0.2
                dsp.place(far, dsp.lp(c, 1500, 2), t0, 1.0)
            far = dsp.reverb(rng, far, 2.5, mix=0.6, hf_damp=0.4, tail=False)[:N]
            out.append(hum + room + vent + far * 0.6)
        return np.stack(out, axis=1)
    return dsp.make_loop(gen, 16.0, 1.0)

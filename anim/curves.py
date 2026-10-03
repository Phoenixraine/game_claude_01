"""Time curves: heavy-mass easing, per-joint blending with independent timing, spring-damper secondary motion, step camera shake."""
import math

import numpy as np

from . import rig


# ---------------------------------------------------------------------------------------------------- easing
def smoothstep(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def ease_heavy(u, tail=2.6):
    """Heavy-mass easing: the intent shows at once (fast start, f'(0) = tail) and the motion settles slowly (f'(1) = 0)."""
    u = min(1.0, max(0.0, u))
    return 1.0 - (1.0 - u) ** tail


def ease_in_out(u):
    return smoothstep(u)


def ease_lag(u, lag=0.25):
    """Delayed follow: the joint starts moving `lag` (fraction) later than the lead joint and arrives later."""
    return smoothstep((u - lag) / max(1e-9, 1.0 - lag))


EASINGS = {"smoothstep": smoothstep, "heavy": ease_heavy, "lag": ease_lag, "linear": lambda u: min(1.0, max(0.0, u))}

# per-joint timing for a heavy swing: pelvis/torso lead, shoulder and arm follow, hand last (offset, duration) in 0..1
SWING_TIMING = {"root": (0.0, 0.8), "pelvis": (0.0, 0.7), "torso": (0.05, 0.75), "head": (0.15, 0.7),
                "shoulder": (0.12, 0.7), "upperarm": (0.15, 0.75), "forearm": (0.25, 0.7), "hand": (0.35, 0.6),
                "thigh": (0.0, 0.8), "shin": (0.0, 0.8), "foot": (0.1, 0.7)}


def joint_group(bone):
    return bone.split("_")[0]


# groups that show the weight shift at once (fast start); the arm chain moves with a smooth, heavy-looking S-curve
HEAVY_GROUPS = {"root", "pelvis", "torso", "head", "thigh", "shin", "foot"}


def blend_poses(a, b, u, timing=None, easing="heavy", ease_kw=None, smooth_arms=True):
    """Blend two joint dicts {bone: [rx, ry, rz]} at global progress u in 0..1. `timing` maps a joint group to (start, length)
    inside 0..1, so e.g. the torso can lead and the hand trail."""
    f = EASINGS[easing]
    out = {}
    for bone in set(a) | set(b):
        ea = np.array(a.get(bone, [0, 0, 0]), dtype=float)
        eb = np.array(b.get(bone, [0, 0, 0]), dtype=float)
        s, ln = (timing or {}).get(joint_group(bone), (0.0, 1.0))
        local = (u - s) / max(ln, 1e-9)
        grp = joint_group(bone)
        if easing == "heavy" and smooth_arms and grp not in HEAVY_GROUPS:
            w = smoothstep(local)
        else:
            w = f(local, **(ease_kw or {})) if easing == "heavy" else f(local)
        out[bone] = (ea + (eb - ea) * w).tolist()
    return out


def blend_root(a, b, u, easing="heavy"):
    f = EASINGS[easing]
    w = f(u)
    return (np.array(a, dtype=float) + (np.array(b, dtype=float) - np.array(a, dtype=float)) * w).tolist()


# -------------------------------------------------------------------------------------- secondary motion (spring)
class Spring:
    """Critically-damped-ish spring-damper following a target (cockpit/shoulder inertia). Semi-implicit Euler, fixed step."""

    def __init__(self, freq_hz=1.2, damping=0.7, dim=3):
        self.w = 2 * math.pi * freq_hz
        self.z = damping
        self.x = np.zeros(dim)
        self.v = np.zeros(dim)

    def step(self, target, dt):
        a = self.w * self.w * (np.asarray(target, dtype=float) - self.x) - 2 * self.z * self.w * self.v
        self.v = self.v + a * dt
        self.x = self.x + self.v * dt
        return self.x.copy()


def secondary_motion(target_track, dt, freq_hz=1.2, damping=0.45):
    """Run a spring over a (N, dim) target track; returns the lagged/overshooting response (N, dim)."""
    tr = np.asarray(target_track, dtype=float)
    sp = Spring(freq_hz, damping, tr.shape[1])
    sp.x = tr[0].copy()
    return np.array([sp.step(t, dt) for t in tr])


# ------------------------------------------------------------------------------------------ camera shake from steps
def step_shake(phase, amplitude=1.0):
    """Camera shake amplitude for a step phase in 0..1 (0 = heel strike): a hard impact decaying over ~35 % of the step,
    plus a small low-frequency sway. Returns (vertical, lateral, roll_deg)."""
    p = phase % 1.0
    impact = math.exp(-p / 0.09) * math.cos(2 * math.pi * 6.0 * p)
    sway = 0.15 * math.sin(2 * math.pi * p)
    return (amplitude * (0.9 * impact + 0.1 * sway), amplitude * 0.25 * sway, amplitude * 0.8 * impact)


def shake_track(step_period_s, duration_s, fps=60, amplitude=1.0):
    n = int(duration_s * fps)
    return [dict(zip(("vertical", "lateral", "roll_deg"), step_shake((i / fps) / step_period_s, amplitude))) for i in range(n)]

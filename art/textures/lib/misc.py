"""LUTs (heat, damage colour code §21) and armour destruction masks (Dent / Crack / Burn x 4 variants)."""
import numpy as np

from . import noise as nz

F32 = np.float32

HEAT_STOPS = [(0.0, (0.02, 0.04, 0.22)), (0.25, (0.05, 0.45, 0.85)), (0.45, (0.55, 0.9, 0.95)), (0.6, (1.0, 0.95, 0.4)),
              (0.78, (1.0, 0.55, 0.08)), (0.92, (0.95, 0.12, 0.04)), (1.0, (1.0, 1.0, 1.0))]
# pitch §21: neutral (white-blue), exposed armour (yellow), damaged mechanisms (orange), critical (red), lost (black)
DAMAGE_STEPS = [("neutral", (0.78, 0.92, 1.0)), ("exposed", (1.0, 0.85, 0.2)), ("damaged", (1.0, 0.5, 0.1)), ("critical", (1.0, 0.1, 0.08)), ("lost", (0.01, 0.01, 0.012))]


def heat_lut(width=256):
    t = np.linspace(0, 1, width, dtype=F32)[None, :]
    rgb = nz.ramp(np.broadcast_to(t, (1, width)), HEAT_STOPS)
    return np.concatenate([rgb, np.ones((1, width, 1), F32)], -1)


def damage_lut(width=256, smooth=False):
    """Row 0: hard steps (5 equal bands). Row 1: smooth blend between neighbouring steps."""
    k = len(DAMAGE_STEPS)
    x = np.linspace(0, 1, width, dtype=F32)
    hard = np.zeros((width, 3), F32)
    for i, (_, c) in enumerate(DAMAGE_STEPS):
        m = (x >= i / k) & (x < (i + 1) / k) if i < k - 1 else (x >= i / k)
        hard[m] = c
    pos = [(i + 0.5) / k for i in range(k)]
    soft = np.stack([np.interp(x, pos, [c[ch] for _, c in DAMAGE_STEPS]) for ch in range(3)], -1).astype(F32)
    out = np.stack([hard, soft], 0)
    return np.concatenate([out, np.ones((2, width, 1), F32)], -1)


def _crack(n, rng, cells, w):
    d1, d2 = nz.worley(n, rng, cells, 1.0)
    e = nz.warp(d2 - d1, rng, 0.03, 2.4, 14)
    return 1 - nz.smoothstep(e, 0.0, w)


def mask_dent(n, i):
    rng = nz.rng_for("mask_dent", i)
    cnt = [8, 14, 24, 40][i]
    m = nz.blobs(n, rng, cnt, (0.02 + 0.01 * (3 - i), 0.09), 0.9)
    return np.clip(m * (0.6 + 0.6 * nz.fbm(n, rng, 2, 2, 40)), 0, 1)


def mask_crack(n, i):
    rng = nz.rng_for("mask_crack", i)
    c = _crack(n, rng, [5, 7, 10, 14][i], 0.05)
    sc = nz.lines(n, rng, [40, 90, 160, 260][i], (0.05, 0.3), (max(1.0, n / 600), max(1.5, n / 300)), curvy=0.5)
    return np.clip(c * nz.smoothstep(nz.fbm(n, rng, 2.4, 1, 8), 0.35, 0.65) + sc * 0.7, 0, 1)


def mask_burn(n, i):
    rng = nz.rng_for("mask_burn", i)
    core = nz.blobs(n, rng, [3, 5, 8, 12][i], (0.08, 0.22), 0.7)
    t = nz.fbm(n, rng, 2.0, 2, 40)
    return np.clip(nz.smoothstep(core * (0.6 + 0.8 * t), 0.2, 0.9), 0, 1)


def zone_variants():
    """Deterministic variant choice per damage zone (index 0..3 for each mask kind), so every zone looks different."""
    zones = ["Head", "Torso", "Reactor", "ShoulderL", "ShoulderR", "ArmL", "ArmR", "LegL", "LegR"]
    out = {z: {"Dent": i % 4, "Crack": (i // 2 + i) % 4, "Burn": (i // 4 + 3 * i) % 4} for i, z in enumerate(zones)}
    assert len({tuple(v.values()) for v in out.values()}) == len(zones)
    return out

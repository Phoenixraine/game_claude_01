"""Clips: sequences of key poses blended with per-joint timing and heavy easing; legs re-solved by IK so feet stay where the poses put them."""
import math

import numpy as np

from . import curves, poses, rig

FPS = 30

# name -> list of (pose, seconds to reach it from the previous key). Durations are long: 82 m, >8000 t.
KEYS = {
    # timings follow core/include/iv/Tuning.h: windup 300-1000 ms (+ commit delay), strike travel 330 ms, recovery 600 ms
    "swing_up_right": [("guard_neutral", 0.0), ("swing_up_r_windup", 0.9), ("swing_up_r_commit", 0.10), ("swing_up_r_strike_end", 0.33),
                       ("swing_up_r_recovery", 0.6), ("guard_neutral", 1.0)],
    "block_up": [("guard_neutral", 0.0), ("block_up", 0.28), ("block_up", 0.6), ("guard_neutral", 0.9)],
    "dodge_left": [("guard_neutral", 0.0), ("dodge_left_shift", 0.7), ("dodge_left_lift", 0.8), ("dodge_left_plant", 0.9), ("guard_neutral", 1.2)],
    "fall_back": [("guard_neutral", 0.0), ("knockdown_fall", 1.1), ("knockdown_down", 1.3)],
    "quick_piston_right": [("guard_neutral", 0.0), ("quick_piston_r_windup", 0.3), ("quick_piston_r_strike", 0.12), ("guard_neutral", 0.55)],
}
UPPER = (set(rig.BONES) - {"root"}) - {b for b in rig.BONES if b.startswith(("thigh", "shin", "foot"))}


def _feet_targets(p):
    return {s: np.array(p.record()["feet"][s]["ankle"]) for s in "lr"}


def build_clip(name, keys, library, fps=FPS):
    """library: dict pose name -> finished Pose. Returns {'name', 'fps', 'frames': [...]} (same frame layout as locomotion minus plants)."""
    frames = []
    t = 0.0
    prev = library[keys[0][0]]
    for pose_name, dur in keys[1:]:
        nxt = library[pose_name]
        n = max(1, int(round(dur * fps)))
        direct = bool(prev.leg_direct or nxt.leg_direct)
        fa, fb = _feet_targets(prev), _feet_targets(nxt)
        for i in range(n):
            u = (i + 1) / n
            joints = curves.blend_poses({b: e for b, e in prev.final.items() if b in UPPER or b == "root"},
                                        {b: e for b, e in nxt.final.items() if b in UPPER or b == "root"}, u, curves.SWING_TIMING, "heavy")
            root = np.array(curves.blend_root(prev.root, nxt.root, u))
            if direct:
                legs = curves.blend_poses({b: e for b, e in prev.final.items() if b not in UPPER}, {b: e for b, e in nxt.final.items() if b not in UPPER},
                                          u, curves.SWING_TIMING, "heavy")
                joints.update(legs)
            else:
                F0 = rig.fk(joints, root)
                w = curves.smoothstep(u)
                for s in "lr":
                    tgt = fa[s] + (fb[s] - fa[s]) * w
                    # a foot that has to travel more than a few metres steps (arc) instead of dragging
                    disp = float(np.linalg.norm((fb[s] - fa[s])[:2]))
                    if disp > 3.0:
                        tgt = tgt + np.array([0, 0, min(5.0, disp * 0.25) * math.sin(math.pi * u)])
                    sol = rig.solve_limb("leg", s, F0["pelvis"], tgt)
                    for b, e in sol["angles"].items():
                        joints[b] = [float(x) for x in e]
            clamped, _ = rig.clamp_pose(joints)
            frames.append({"t": round(t + (i + 1) / fps, 4), "root_pos": [round(float(x), 4) for x in root], "joints": clamped})
        t += n / fps
        prev = nxt
    return {"name": name, "fps": fps, "frames": frames}


def all_clips(library):
    return [build_clip(n, k, library) for n, k in KEYS.items()]

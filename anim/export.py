"""Export: poses.json, locomotion.json, curves.json, schemas, and BVH clips. Run: python -m anim.export [--out anim/out]."""
import json
import math
import os

import numpy as np

from . import clips, curves, damage, locomotion, poses, rig, schema

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
BONE_ORDER = [b for b in rig.BONES if b != "root"]


def dump(path, obj, compact=False):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=None if compact else 1, separators=(",", ":") if compact else None, ensure_ascii=False)
        f.write("\n")


def poses_json(pose_objs):
    recs = {p.name: p.record() for p in pose_objs}
    return {
        "version": 1,
        "convention": "Local Euler angles in degrees in the parent's frame, R = Rz(rz) Ry(ry) Rx(rx); +Z up, mech faces -Y, left side = +X. "
                      "Zero = rest (arms hanging). Pitch rx: negative swings a hanging limb's tip forward/up. root_pos is a translation "
                      "added to the rest root; com and feet are world positions in metres with the root at the origin.",
        "bones": rig.BONES,
        "limits_deg": {b: {a: list(r) for a, r in rig.LIMITS[b].items()} for b in rig.BONES},
        "rest_heads": {b: [float(x) for x in rig.REST[b]] for b in rig.BONES},
        "poses": recs,
        "transitions": poses.transitions(recs.keys()),
    }


def frame_compact(fr):
    j = fr["joints"]
    flat = []
    for b in BONE_ORDER:
        flat += [round(float(x), 2) for x in j.get(b, [0, 0, 0])]
    rr = j.get("root", [0, 0, 0])
    return {"t": fr["t"], "root": fr["root_pos"], "root_rot": [round(float(x), 2) for x in rr], "j": flat,
            "contact": [fr["contact"]["l"], fr["contact"]["r"]], "ankle_l": fr["ankle"]["l"], "ankle_r": fr["ankle"]["r"]}


def locomotion_json(clip_list):
    return {"version": 1, "fps": locomotion.FPS, "bone_order": BONE_ORDER,
            "note": "Each frame: j = 3 angles (rx, ry, rz) per bone in bone_order, root_rot = world heading of the root (degrees), "
                    "root = world translation added to the rest root; contact = [left, right] foot on the ground.",
            "gaits": locomotion.table(), "phases": locomotion.PHASE, "leg_reach_m": round(locomotion.LEG_REACH, 3),
            "clips": [dict(c.to_json(), frames=[frame_compact(f) for f in c.frames]) for c in clip_list]}


def curves_json():
    u = np.linspace(0, 1, 41)
    return {"version": 1,
            "easings": {"heavy": [round(curves.ease_heavy(float(x)), 5) for x in u], "smoothstep": [round(curves.smoothstep(float(x)), 5) for x in u],
                        "lag": [round(curves.ease_lag(float(x)), 5) for x in u]},
            "easing_sample_points": 41,
            "swing_timing": {k: {"start": v[0], "length": v[1]} for k, v in curves.SWING_TIMING.items()},
            "spring": {"cockpit": {"freq_hz": 1.2, "damping": 0.45}, "shoulder": {"freq_hz": 2.0, "damping": 0.35}, "head": {"freq_hz": 2.6, "damping": 0.5}},
            "shake": {g: {"step_period_s": locomotion.GAITS[g]["T"], "amplitude": amp,
                          "track": [[round(v, 4) for v in curves.step_shake(p / 40.0, amp)] for p in range(41)]}
                      for g, amp in (("walk_slow", 0.7), ("walk", 1.0), ("walk_fast", 1.3), ("run", 1.7))}}


# ------------------------------------------------------------------------------------------------------------ BVH
def bvh_text(clip_frames, fps, name):
    kids = {b: [c for c in rig.BONES if rig.PARENT[c] == b] for b in rig.BONES}
    lines = ["HIERARCHY"]

    def emit(b, depth):
        pad = "  " * depth
        off = rig.REST[b] - (rig.REST[rig.PARENT[b]] if rig.PARENT[b] else np.zeros(3))
        lines.append("%s%s %s" % (pad, "ROOT" if depth == 0 else "JOINT", b))
        lines.append(pad + "{")
        lines.append("%s  OFFSET %.4f %.4f %.4f" % (pad, *off))
        if depth == 0:
            lines.append(pad + "  CHANNELS 6 Xposition Yposition Zposition Zrotation Yrotation Xrotation")
        else:
            lines.append(pad + "  CHANNELS 3 Zrotation Yrotation Xrotation")
        for c in kids[b]:
            emit(c, depth + 1)
        if not kids[b]:
            tip = rig.TAIL.get(b, rig.REST[b] + np.array([0, 0, -2.0])) - rig.REST[b]
            lines.append(pad + "  End Site")
            lines.append(pad + "  {")
            lines.append("%s    OFFSET %.4f %.4f %.4f" % (pad, *tip))
            lines.append(pad + "  }")
        lines.append(pad + "}")

    emit("root", 0)
    order = []

    def walk(b):
        order.append(b)
        for c in kids[b]:
            walk(c)

    walk("root")
    lines.append("MOTION")
    lines.append("Frames: %d" % len(clip_frames))
    lines.append("Frame Time: %.6f" % (1.0 / fps))
    for fr in clip_frames:
        j = fr["joints"]
        rp = fr["root_pos"]
        r = j.get("root", [0, 0, 0])
        vals = [REST_ROOT[0] + rp[0], REST_ROOT[1] + rp[1], REST_ROOT[2] + rp[2], r[2], r[1], r[0]]
        for b in order[1:]:
            e = j.get(b, [0, 0, 0])
            vals += [e[2], e[1], e[0]]
        lines.append(" ".join("%.4f" % v for v in vals))
    return "\n".join(lines) + "\n"


REST_ROOT = [0.0, 0.0, 0.0]


def parse_bvh(text):
    """Minimal BVH reader used by the tests: returns (joint order, frames count, frame time, channel counts, rows)."""
    head, motion = text.split("MOTION")
    joints = [l.split()[1] for l in head.splitlines() if l.strip().startswith(("ROOT", "JOINT"))]
    chans = [int(l.split()[1]) for l in head.splitlines() if l.strip().startswith("CHANNELS")]
    ml = motion.strip().splitlines()
    n = int(ml[0].split(":")[1])
    ft = float(ml[1].split(":")[1])
    rows = [[float(x) for x in l.split()] for l in ml[2:]]
    return joints, n, ft, chans, rows


def build_all(out=OUT, verbose=True):
    os.makedirs(out, exist_ok=True)
    os.makedirs(os.path.join(out, "bvh"), exist_ok=True)
    pose_objs = poses.all_poses()
    library = {p.name: p for p in pose_objs}
    pj = poses_json(pose_objs)
    loco_clips = locomotion.all_clips() + [damage.limp_walk({"LegL": "Damaged"}, "walk", 6), damage.limp_walk({"LegR": "Critical"}, "walk", 6)]
    lj = locomotion_json(loco_clips)
    cj = curves_json()
    dump(os.path.join(out, "poses.json"), pj)
    dump(os.path.join(out, "locomotion.json"), lj, compact=True)
    dump(os.path.join(out, "curves.json"), cj)
    dump(os.path.join(out, "schema.json"), {"poses": schema.POSES_SCHEMA, "locomotion": schema.LOCO_SCHEMA, "curves": schema.CURVES_SCHEMA})
    pose_clips = clips.all_clips(library)
    walk = locomotion.walk_cycle("walk", 2)
    bvh_sources = [("walk", walk.frames, locomotion.FPS)] + [(c["name"], c["frames"], c["fps"]) for c in pose_clips]
    for name, frames, fps in bvh_sources:
        with open(os.path.join(out, "bvh", name + ".bvh"), "w") as f:
            f.write(bvh_text(frames, fps, name))
    if verbose:
        print("poses: %d, locomotion clips: %d, bvh: %d" % (len(pj["poses"]), len(lj["clips"]), len(bvh_sources)))
    return pj, lj, cj, pose_clips, walk


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    build_all(a.out)

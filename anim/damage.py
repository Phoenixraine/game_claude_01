"""Damage modifiers (zones and states of TASK-001): limp, hanging arm, jammed joint, restricted shoulder.

`apply_damage(pose, damage)` takes a pose record (as in poses.json) and `damage` = {zone: state}; `limp_walk(damage)` generates a walk
clip with an asymmetric gait. Zones: Head, Torso, Reactor, ShoulderL/R, ArmL/R, LegL/R.
States: Intact, Dented, Exposed, Damaged, Critical, Destroyed, Severed.
"""
import copy
import math

import numpy as np

from . import locomotion, rig

STATES = ["Intact", "Dented", "Exposed", "Damaged", "Critical", "Destroyed", "Severed"]
SEVERITY = {"Intact": 0.0, "Dented": 0.08, "Exposed": 0.25, "Damaged": 0.5, "Critical": 0.8, "Destroyed": 1.0, "Severed": 1.0}
ZONES = ["Head", "Torso", "Reactor", "ShoulderL", "ShoulderR", "ArmL", "ArmR", "LegL", "LegR"]
HANG = {"upperarm": (4.0, 0.0, 0.0), "forearm": (-8.0, 0.0, 0.0), "hand": (0.0, 0.0, 0.0)}   # limp arm hanging under gravity


def severity(state):
    return SEVERITY[state]


def _side(zone):
    return zone[-1].lower()


def apply_damage(pose, damage):
    """Returns a modified copy of `pose` plus a `damage` report: {'jammed': [...], 'hidden_bones': [...], 'limited': {...}}."""
    out = copy.deepcopy(pose)
    j = out["joints"]
    report = {"jammed": [], "hidden_bones": [], "limited": {}, "locomotion_blocked": False}
    for zone in ZONES:
        st = damage.get(zone, "Intact")
        s = SEVERITY[st]
        if s <= 0:
            continue
        side = _side(zone) if zone[-1] in "LR" else None
        if zone.startswith("Shoulder"):
            ur = "upperarm_" + side
            # restricted raise: the arm can no longer go above a limit that shrinks with damage, and sags a little
            lo = rig.LIMITS[ur]["x"][0] * (1.0 - 0.65 * s)
            j[ur][0] = max(lo, j[ur][0]) + 6.0 * s * s
            report["limited"][ur] = {"x_min": round(lo, 1)}
        elif zone.startswith("Arm"):
            ur, fr, hd = "upperarm_" + side, "forearm_" + side, "hand_" + side
            if st in ("Destroyed", "Severed"):
                for b, key in ((ur, "upperarm"), (fr, "forearm"), (hd, "hand")):
                    tgt = np.array(HANG[key])
                    mirror = 1.0
                    j[b] = [float(x) for x in tgt * np.array([1, mirror, mirror])]
                if st == "Severed":
                    report["hidden_bones"] += [fr, hd]
            else:
                w = s ** 1.3
                for b, key in ((ur, "upperarm"), (fr, "forearm"), (hd, "hand")):
                    tgt = np.array(HANG[key])
                    j[b] = [float(x) for x in (1 - w) * np.array(j[b]) + w * tgt]
                if st == "Critical":    # elbow jammed at a fixed angle, regardless of what the pose asks for
                    j[fr] = [-38.0, 0.0, 0.0]
                    report["jammed"].append(fr)
        elif zone.startswith("Leg"):
            th, sh, ft = "thigh_" + side, "shin_" + side, "foot_" + side
            if st in ("Destroyed", "Severed"):
                report["locomotion_blocked"] = True
            # stiff knee: flexion shrinks with damage; the pelvis sags toward the damaged side
            j[sh][0] = j[sh][0] * (1.0 - 0.55 * s)
            if st == "Critical":
                j[sh] = [14.0, 0.0, 0.0]
                report["jammed"].append(sh)
            j["pelvis"][1] += (-1 if side == "l" else 1) * 6.0 * s     # roll toward the damaged side
        elif zone == "Head":
            j["head"][0] = j["head"][0] * (1 - 0.7 * s) + 10.0 * s      # head droops
            j["head"][2] *= (1 - 0.8 * s)
        elif zone == "Torso":
            j["torso"][1] += 5.0 * s * (1 if math.sin(sum(ord(c) for c in out["name"])) > 0 else -1)
            j["torso"][2] *= (1 - 0.5 * s)                              # twist range shrinks
        elif zone == "Reactor":
            pass                                                       # no pose change: the reactor shows in VFX/camera shake
    clamped, hits = rig.clamp_pose({b: e for b, e in j.items()})
    out["joints"] = {b: [round(float(x), 3) for x in e] for b, e in clamped.items()}
    out["damage"] = report
    return out


def limp_walk(damage, gait="walk", steps=4):
    """Walk clip with the gait asymmetry of a damaged leg (shorter, slower, lower steps on the damaged side + hip hike)."""
    side, s = None, 0.0
    for zone in ("LegL", "LegR"):
        sv = SEVERITY[damage.get(zone, "Intact")]
        if sv > s:
            side, s = zone[-1].lower(), sv
    g = locomotion.GAITS[gait]
    if side is None:
        return locomotion.walk_cycle(gait, steps)
    seq = []
    swing = "r"
    for k in range(steps):
        dmg_swing = swing == side
        # the damaged leg takes a shorter step but also leaves less room for the healthy one: both steps shrink, asymmetrically
        L = g["L"] * (1.0 - (0.38 if dmg_swing else 0.10) * s)
        T = g["T"] * (1.0 + (0.45 if dmg_swing else 0.12) * s)
        seq.append({"L": L, "T": T, "clear": 1.0 - 0.6 * s if dmg_swing else 1.0,
                    "roll": (4.0 * s) * (1 if side == "l" else -1) if dmg_swing else 0.0})
        swing = "l" if swing == "r" else "r"
    return locomotion.generate("limp_%s_%s" % (side, gait), gait, seq, init="stride")


def asymmetry(clip):
    """Step-length and swing-time ratio between the feet in a clip (1.0 = symmetric): returns (length_ratio, time_ratio, worst side)."""
    by = {"l": [], "r": []}
    prev = None
    for pl in clip.plants:                       # step length = distance between consecutive plants of opposite feet
        pos = np.array(pl["pos"])
        if prev is not None:
            by[pl["foot"]].append(float(np.linalg.norm(pos - prev)))
        prev = pos
    # swing durations: frames with contact False per foot
    dur = {"l": 0, "r": 0}
    for f in clip.frames:
        for s in "lr":
            if not f["contact"][s]:
                dur[s] += 1
    ml = {s: (sum(v) / len(v) if v else 0.0) for s, v in by.items()}
    lr = min(ml.values()) / max(ml.values()) if max(ml.values()) > 0 else 1.0
    tr = min(dur.values()) / max(dur.values()) if max(dur.values()) > 0 else 1.0
    return lr, tr

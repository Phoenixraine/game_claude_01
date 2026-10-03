"""Kinematics of BASTION-01: hierarchy, rest geometry (metres), joint limits (degrees), FK, two-bone IK, centre of mass.

Frame: +Z up, the mech faces -Y, its LEFT side is +X (art/mech/build_bastion.py). Rest = standing with arms hanging, all rest
rotations identity, so a bone frame is just a translation at the bone head.

Angle convention (this library and its JSON): every joint stores LOCAL Euler angles in degrees in the PARENT's frame,
R = Rz(rz) @ Ry(ry) @ Rx(rx). rx = pitch: for a limb hanging down, negative rx swings its tip forward (-Y) and up, positive swings it
back. ry = roll/abduction (negative moves a hanging limb toward +X), rz = twist about the bone's long axis (yaw for the torso/head).
Knee: shin rx in [0, 120] (positive = heel back). Elbow: forearm rx in [-140, 0] (negative = forearm forward/up).
"""
import math

import numpy as np

# ---------------------------------------------------------------------------------------------------- geometry
BONES = ["root", "pelvis", "torso", "head", "reactor"] + [
    "%s_%s" % (n, s) for s in ("l", "r") for n in ("shoulder", "upperarm", "forearm", "hand", "thigh", "shin", "foot")]
PARENT = {"root": None, "pelvis": "root", "torso": "pelvis", "head": "torso", "reactor": "torso"}
for _s in ("l", "r"):
    PARENT.update({"shoulder_" + _s: "torso", "upperarm_" + _s: "shoulder_" + _s, "forearm_" + _s: "upperarm_" + _s,
                   "hand_" + _s: "forearm_" + _s, "thigh_" + _s: "pelvis", "shin_" + _s: "thigh_" + _s, "foot_" + _s: "shin_" + _s})


def _rest():
    h = {"root": (0, 0, 0), "pelvis": (0, 0, 44), "torso": (0, 0, 48), "head": (0, -7, 68), "reactor": (0, 15.5, 57)}
    for s, k in (("l", 1), ("r", -1)):
        h.update({"shoulder_" + s: (k * 18.4, 0, 66), "upperarm_" + s: (k * 23, 0, 65), "forearm_" + s: (k * 30, -2, 47),
                  "hand_" + s: (k * 30, -4, 27), "thigh_" + s: (k * 11.5, 0, 42), "shin_" + s: (k * 11.5, -1, 26),
                  "foot_" + s: (k * 11.5, 2, 5)})
    return {b: np.array(v, dtype=float) for b, v in h.items()}


REST = _rest()
# tips used for end-effectors / segment drawing: bone -> tail point in rest
TAIL = {"hand_l": np.array([30, -4, 19.0]), "hand_r": np.array([-30, -4, 19.0]), "foot_l": np.array([11.5, -9, 0.0]),
        "foot_r": np.array([-11.5, -9, 0.0]), "head": np.array([0, -7, 79.0]), "reactor": np.array([0, 15.5, 65.0]),
        "torso": np.array([0, 0, 68.0]), "pelvis": np.array([0, 0, 48.0]), "root": np.array([0, 0, 4.0])}
GROUND_ANKLE_Z = 5.0   # ankle height with the sole flat on the ground

# relative masses (sum ~ 1; >8000 t in total) and drawing thickness (m); used for COM and silhouettes
MASS = {"root": 0.0, "pelvis": 0.10, "torso": 0.30, "head": 0.02, "reactor": 0.08, "shoulder_l": 0.03, "shoulder_r": 0.03,
        "upperarm_l": 0.04, "upperarm_r": 0.04, "forearm_l": 0.05, "forearm_r": 0.05, "hand_l": 0.02, "hand_r": 0.02,
        "thigh_l": 0.055, "thigh_r": 0.055, "shin_l": 0.045, "shin_r": 0.045, "foot_l": 0.015, "foot_r": 0.015}
THICK = {"pelvis": 26, "torso": 30, "head": 12, "reactor": 12, "shoulder_l": 16, "shoulder_r": 16, "upperarm_l": 11, "upperarm_r": 11,
         "forearm_l": 13, "forearm_r": 13, "hand_l": 12, "hand_r": 12, "thigh_l": 13, "thigh_r": 13, "shin_l": 12, "shin_r": 12,
         "foot_l": 12, "foot_r": 12, "root": 1}
TOTAL_MASS_T = 9200.0  # tonnes (pitch §11: >8000 t)


def _lim(x=(0, 0), y=(0, 0), z=(0, 0)):
    return {"x": tuple(x), "y": tuple(y), "z": tuple(z)}


def _limits():
    L = {"root": _lim((-180, 180), (-180, 180), (-180, 180)), "reactor": _lim(),
         "pelvis": _lim((-12, 12), (-8, 8), (-20, 20)),
         "torso": _lim((-15, 20), (-10, 10), (-40, 40)),
         "head": _lim((-20, 25), (0, 0), (-50, 50))}
    for s, k in (("l", 1), ("r", -1)):
        L["shoulder_" + s] = _lim((-10, 10), (0, 0), (-10, 10))
        ab = (-100, 30) if k > 0 else (-30, 100)          # abduction: the arm moves away from the body
        L["upperarm_" + s] = _lim((-170, 60), ab, (-70, 70))
        L["forearm_" + s] = _lim((-140, 0))                # elbow: 1 DoF
        L["hand_" + s] = _lim((-60, 60), (-40, 40))        # wrist: 2 DoF
        hab = (-45, 10) if k > 0 else (-10, 45)
        L["thigh_" + s] = _lim((-100, 30), hab, (-30, 30))
        L["shin_" + s] = _lim((0, 120))                    # knee: 1 DoF
        L["foot_" + s] = _lim((-60, 60), (-15, 15))        # ankle: 2 DoF
    return L


LIMITS = _limits()


def mirror_name(b):
    if b.endswith("_l"):
        return b[:-2] + "_r"
    if b.endswith("_r"):
        return b[:-2] + "_l"
    return b


# ------------------------------------------------------------------------------------------------ rotations
def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler_to_mat(e):
    return rz(e[2]) @ ry(e[1]) @ rx(e[0])


def mat_to_euler(R):
    """Inverse of euler_to_mat (R = Rz Ry Rx), degrees (rx, ry, rz)."""
    sy = -R[2, 0]
    sy = max(-1.0, min(1.0, sy))
    y = math.asin(sy)
    if abs(sy) < 0.999999:
        x = math.atan2(R[2, 1], R[2, 2])
        z = math.atan2(R[1, 0], R[0, 0])
    else:  # gimbal lock: put everything into x
        x = math.atan2(-R[1, 2], R[1, 1])
        z = 0.0
    return [math.degrees(x), math.degrees(y), math.degrees(z)]


def clamp_pose(angles):
    """Clamp every joint to its limits; returns (clamped dict, list of (bone, axis, requested, clamped))."""
    out, hits = {}, []
    for b, e in angles.items():
        c = list(e)
        for i, ax in enumerate("xyz"):
            lo, hi = LIMITS[b][ax]
            v = min(hi, max(lo, e[i]))
            if abs(v - e[i]) > 1e-9:
                hits.append((b, ax, e[i], v))
            c[i] = v
        out[b] = c
    return out, hits


def limit_violations(angles, tol=1e-6):
    bad = []
    for b, e in angles.items():
        for i, ax in enumerate("xyz"):
            lo, hi = LIMITS[b][ax]
            if not (lo - tol <= e[i] <= hi + tol):
                bad.append((b, ax, e[i], (lo, hi)))
    return bad


# -------------------------------------------------------------------------------------------------------- FK
def fk(angles, root_pos=(0.0, 0.0, 0.0)):
    """Frames of all bones: dict bone -> 4x4 world matrix. Joints missing in `angles` are at rest.
    A point p given in REST world coordinates and attached to bone b moves to F[b] @ (p - REST[b])."""
    F = {}
    for b in BONES:
        e = angles.get(b, (0, 0, 0))
        R = euler_to_mat(e)
        M = np.eye(4)
        M[:3, :3] = R
        p = PARENT[b]
        if p is None:
            M[:3, 3] = REST[b] + np.array(root_pos, dtype=float)
        else:
            local = np.eye(4)
            local[:3, :3] = R
            local[:3, 3] = REST[b] - REST[p]
            M = F[p] @ local
        F[b] = M
    return F


def joint_positions(F):
    return {b: F[b][:3, 3].copy() for b in BONES}


def attach(F, b, p_rest):
    """World position of a rest-space point carried by bone b."""
    return (F[b] @ np.append(np.asarray(p_rest, dtype=float) - REST[b], 1.0))[:3]


def tip_positions(F):
    """Posed segment end points (child head or tail) for drawing and foot/hand targets."""
    tips = {}
    for b in BONES:
        if b in TAIL:
            tips[b] = attach(F, b, TAIL[b])
    return tips


def segment_endpoints(F):
    """bone -> (start, end) world points used by the silhouette renderer."""
    seg = {}
    for b in BONES:
        if b == "root":
            continue
        start = F[b][:3, 3]
        kids = [c for c in BONES if PARENT[c] == b and c != "reactor"]
        if b in ("pelvis", "torso", "head", "reactor", "shoulder_l", "shoulder_r") or not kids:
            end = attach(F, b, TAIL[b]) if b in TAIL else start
            if b.startswith("shoulder"):
                end = attach(F, "upperarm_" + b[-1], REST["upperarm_" + b[-1]])
        else:
            c = kids[0]
            end = F[c][:3, 3]
        seg[b] = (start, end)
    return seg


def com(F):
    """Centre of mass: each segment's mass sits at the midpoint of its start/end points."""
    seg = segment_endpoints(F)
    tot = sum(MASS[b] for b in seg)
    p = sum(MASS[b] * (seg[b][0] + seg[b][1]) / 2 for b in seg) / tot
    return p


def foot_contacts(F, tol=0.6):
    """Sole points (heel, toe) per foot in world space + whether each foot is on the ground (lowest sole point < tol)."""
    out = {}
    for s in ("l", "r"):
        b = "foot_" + s
        k = 1 if s == "l" else -1
        heel = attach(F, b, REST[b] + np.array([0, 6, -5.0]))      # sole points at z=0 when the foot is flat
        toe = attach(F, b, np.array([k * 11.5, -9, 0.0]))
        ank = F[b][:3, 3].copy()
        out[s] = {"ankle": ank, "heel": heel, "toe": toe, "ground": bool(min(heel[2], toe[2]) < tol)}
    return out


# -------------------------------------------------------------------------------------------------------- IK
def _two_link(k0, a0, theta_range, target_local, sign):
    """Knee/elbow angle theta (rotation about local X) such that |k0 + Rx(theta) a0| = |target_local|.
    `sign` picks the bend direction (+1 for knees, -1 for elbows). Returns (theta, reachable)."""
    d = np.linalg.norm(target_local)
    # |k0|^2 + |a0|^2 + 2 k0.Rx(t)a0 = d^2, with k0.Rx(t)a0 = A cos t + B sin t + C0
    C0 = k0[0] * a0[0]
    A = k0[1] * a0[1] + k0[2] * a0[2]
    B = -k0[1] * a0[2] + k0[2] * a0[1]
    rhs = (d * d - k0 @ k0 - a0 @ a0) / 2.0 - C0
    R = math.hypot(A, B)
    phi = math.atan2(B, A)
    c = rhs / R if R > 1e-9 else 2.0
    reach = True
    if c > 1.0:
        c = 1.0
        reach = False
    elif c < -1.0:
        c = -1.0
        reach = False
    base = math.acos(c)
    sols = [math.degrees(phi + base), math.degrees(phi - base)]
    sols = [((s + 180) % 360) - 180 for s in sols]
    lo, hi = theta_range
    inside = [s for s in sols if lo - 1e-6 <= s <= hi + 1e-6]
    if inside:
        # among valid solutions prefer the one with the larger bend in the wanted direction
        theta = max(inside, key=lambda s: s * sign)
    else:
        theta = min(max(sols[0], lo), hi)
        reach = False
    return theta, reach


def _hip_rotations(w, v, yaw):
    """Both (p, r) solutions of Rz(yaw) Ry(r) Rx(p) w = v (3-vectors of equal length)."""
    v1 = rz(-yaw) @ v
    R = math.hypot(w[1], w[2])
    if R < 1e-9:
        return [(0.0, 0.0)]
    ratio = max(-1.0, min(1.0, v1[1] / R))
    phi = math.atan2(w[2], w[1])
    cand = []
    for sgn in (1, -1):
        p = sgn * math.acos(ratio) - phi
        p = math.degrees(((p + math.pi) % (2 * math.pi)) - math.pi)
        c, s = math.cos(math.radians(p)), math.sin(math.radians(p))
        z1 = w[1] * s + w[2] * c
        r = math.degrees(math.atan2(v1[0], v1[2]) - math.atan2(w[0], z1))
        r = ((r + 180) % 360) - 180
        cand.append((p, r))
    return cand


def _violation(bone, e):
    tot = 0.0
    for i, ax in enumerate("xyz"):
        lo, hi = LIMITS[bone][ax]
        tot += max(0.0, lo - e[i]) + max(0.0, e[i] - hi)
    return tot


def solve_limb(kind, side, parent_world, target, foot_yaw=0.0, hand_world_rot=None):
    """Closed-form two-bone IK for a leg (kind='leg': thigh/shin/foot) or an arm (kind='arm': upperarm/forearm/hand).
    `parent_world` is the 4x4 world frame of the bone above the limb (pelvis for legs, shoulder for arms) with ITS OWN rest
    translation already included; `target` is the wanted world position of the wrist/ankle bone head.
    Returns dict(angles={bone: [rx, ry, rz]}, reachable, error_m, clamped)."""
    if kind == "leg":
        b1, b2, b3 = "thigh_" + side, "shin_" + side, "foot_" + side
        sign = 1.0
    else:
        b1, b2, b3 = "upperarm_" + side, "forearm_" + side, "hand_" + side
        sign = -1.0
    p1 = PARENT[b1]
    head1_world = (parent_world @ np.append(REST[b1] - REST[p1], 1.0))[:3]
    k0 = REST[b2] - REST[b1]
    a0 = REST[b3] - REST[b2]
    Rp = parent_world[:3, :3]
    v = Rp.T @ (np.asarray(target, dtype=float) - head1_world)          # target in the parent's frame
    theta, reach = _two_link(k0, a0, LIMITS[b2]["x"], v, sign)
    w = k0 + rx(theta) @ a0
    scale = np.linalg.norm(w)
    d = np.linalg.norm(v)
    vv = v * (scale / d) if d > 1e-9 else v                                # clamp the reach: aim at the ray, report the error
    Rt = np.eye(3) if hand_world_rot is None else hand_world_rot
    yaw = foot_yaw
    for _ in range(8):   # the end bone has no yaw DoF: let the hip twist absorb the residual yaw (fixed-point iteration)
        cands = _hip_rotations(w, vv, yaw)
        p, r = min(cands, key=lambda pr: (round(_violation(b1, [pr[0], pr[1], yaw]), 6), abs(pr[0]) + abs(pr[1])))
        R1 = rz(yaw) @ ry(r) @ rx(p)
        e3 = mat_to_euler((Rp @ R1 @ rx(theta)).T @ Rt)
        if abs(e3[2]) < 1e-5 or kind != "leg":
            break
        yaw = yaw + e3[2]
    if kind == "leg" and (max(0.0, abs(e3[0]) - 60.0) + max(0.0, abs(e3[1]) - 15.0)) > 0.05:
        # the end bone cannot be made world-flat (it would exceed its limits): do not bend the hip twist for it
        yaw = foot_yaw
        cands = _hip_rotations(w, vv, yaw)
        p, r = min(cands, key=lambda pr: (round(_violation(b1, [pr[0], pr[1], yaw]), 6), abs(pr[0]) + abs(pr[1])))
        R1 = rz(yaw) @ ry(r) @ rx(p)
        e3 = mat_to_euler((Rp @ R1 @ rx(theta)).T @ Rt)
    ang = {b1: [p, r, yaw], b2: [theta, 0.0, 0.0]}
    # reached ankle/wrist position and error
    reached = head1_world + Rp @ (R1 @ w)
    err = float(np.linalg.norm(reached - np.asarray(target, dtype=float)))
    clamped = []
    c1, hits = clamp_pose({b1: ang[b1]})
    ang[b1] = c1[b1]
    clamped += hits
    # end bone orientation: world-aligned with the target rotation (flat foot) unless told otherwise
    c3, hits = clamp_pose({b3: e3})
    ang[b3] = c3[b3]
    clamped += hits
    reachable = bool(reach and err < 0.05 and not [h for h in clamped if h[0] == b1])
    return {"angles": ang, "reachable": reachable, "error_m": err, "clamped": clamped}

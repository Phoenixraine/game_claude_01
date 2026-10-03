"""BASTION-01 design: geometry of every zone (units: metres, +Z up, the mech faces -Y, its LEFT side is +X).

Proportions follow pitch §23: wide heavy chest, compact sensor head sunk between the shoulders, massive hydraulic arms,
thick legs. Armour plates stand proud of a closed body shell with the 'mechanics' (Inner_*) in the gap, so any plate can be
removed without a hole.
"""
import math

from mathutils import Vector

from . import hs


# ---------------------------------------------------------------------------------------------------- skeleton
def skeleton(P):
    """bone -> (head, tail, parent). Heads are the real rotation points of the joints."""
    L = P
    b = {}
    b["root"] = ((0, 0, 0), (0, 0, 4), None)
    b["pelvis"] = ((0, 0, L["hip_z"] + 2), (0, 0, L["hip_z"] + 8), "root")
    b["torso"] = ((0, 0, L["waist_z"]), (0, 0, L["shoulder_z"] + 2), "pelvis")
    b["head"] = ((0, L["head_y"], L["neck_z"]), (0, L["head_y"], L["head_top"]), "torso")
    b["reactor"] = ((0, L["reactor_y"], L["reactor_z"]), (0, L["reactor_y"], L["reactor_z"] + 8), "torso")
    for side, s in (("l", 1), ("r", -1)):
        sx = s * L["shoulder_x"]
        b["shoulder_" + side] = ((sx * 0.8, 0, L["shoulder_z"]), (sx, 0, L["shoulder_z"]), "torso")
        b["upperarm_" + side] = ((sx, 0, L["shoulder_z"] - 1), (s * L["arm_x"], -2, L["elbow_z"]), "shoulder_" + side)
        b["forearm_" + side] = ((s * L["arm_x"], -2, L["elbow_z"]), (s * L["arm_x"], -4, L["wrist_z"]), "upperarm_" + side)
        b["hand_" + side] = ((s * L["arm_x"], -4, L["wrist_z"]), (s * L["arm_x"], -4, L["wrist_z"] - 8), "forearm_" + side)
        b["thigh_" + side] = ((s * L["leg_x"], 0, L["hip_z"]), (s * L["leg_x"], -1, L["knee_z"]), "pelvis")
        b["shin_" + side] = ((s * L["leg_x"], -1, L["knee_z"]), (s * L["leg_x"], 2, L["ankle_z"]), "thigh_" + side)
        b["foot_" + side] = ((s * L["leg_x"], 2, L["ankle_z"]), (s * L["leg_x"], -9, 1.5), "shin_" + side)
    return b


# ------------------------------------------------------------------------------------------------ plate helper
def plate(zone, bone, loc, size, face, mat="M_CeramicGray", bevel=0.3, taper=(1, 1), bolts=True, panel=True, accent=False, louvres=0,
          windows=0, rot=(0, 0, 0), chamfer=None, base="M_Graphite", hatch=False):
    """Removable armour plate: chamfered slab + raised inset panel + corner bolts (+ vents / accent stripe / windows / hatch).
    Built around the origin in local axes, then rotated by `rot` and moved to `loc`. `face` is the outward normal axis."""
    p = hs.armor(zone, bone, mat)
    sign = -1.0 if face.startswith("-") else 1.0
    ax = face.lstrip("+-")
    i = "xyz".index(ax)
    others = [k for k in range(3) if k != i]
    t = size[i]
    if chamfer is None:
        chamfer = min(size[others[0]], size[others[1]]) * 0.14
    p.box(size, (0, 0, 0), bevel=bevel, taper=taper if ax == "z" else (1, 1), chamfer=chamfer, chamfer_axis=ax, mat=base if panel else mat)
    if panel:
        inset = [size[k] * 0.8 for k in range(3)]
        inset[i] = 0.3
        c = [0.0, 0.0, 0.0]
        c[i] += sign * (t * 0.5 + 0.08)
        p.box(inset, c, bevel=0.1, chamfer=min(inset[others[0]], inset[others[1]]) * 0.1, chamfer_axis=ax, mat=mat)
    if bolts:
        pts = []
        for a in (-1, 1):
            for b in (-1, 1):
                c = [0.0, 0.0, 0.0]
                c[others[0]] += a * size[others[0]] * 0.43
                c[others[1]] += b * size[others[1]] * 0.43
                c[i] += sign * (t * 0.5)
                pts.append(tuple(c))
        p.bolts(pts, face, radius=min(0.32, min(size[others[0]], size[others[1]]) * 0.04 + 0.12), height=0.18)
    if accent:
        c = [0.0, 0.0, 0.0]
        c[i] += sign * (t * 0.5 + 0.3)
        c[others[1]] += size[others[1]] * 0.3
        sz = [0.2, 0.2, 0.2]
        sz[i] = 0.12
        sz[others[0]] = size[others[0]] * 0.45
        sz[others[1]] = max(0.35, size[others[1]] * 0.05)
        p.box(sz, c, mat="M_AccentOrange")
    if louvres:
        c = [0.0, 0.0, 0.0]
        c[i] += sign * (t * 0.5 + 0.25)
        p.louvres(c, size[others[0]] * 0.55, size[others[1]] * 0.5, louvres, face, depth=0.35)
    if windows:
        for k in range(windows):
            c = [0.0, 0.0, 0.0]
            c[i] += sign * (t * 0.5 + 0.28)
            c[others[0]] += (k - (windows - 1) / 2) * size[others[0]] * 0.2
            sz = [0.25, 0.25, 0.25]
            sz[i] = 0.12
            sz[others[0]] = size[others[0]] * 0.12
            sz[others[1]] = size[others[1]] * 0.12
            p.box(sz, c, mat="M_Glass_Sensor")
    if hatch:   # maintenance hatch: orange frame + dark door + a handle
        c = [0.0, 0.0, 0.0]
        c[i] += sign * (t * 0.5 + 0.25)
        fr = [size[others[0]] * 0.42, size[others[1]] * 0.5]
        s3 = [0, 0, 0]
        s3[i] = 0.2
        s3[others[0]], s3[others[1]] = fr
        p.box(s3, c, bevel=0.05, mat="M_AccentOrange")
        s3b = list(s3)
        s3b[others[0]] *= 0.82
        s3b[others[1]] *= 0.82
        s3b[i] = 0.3
        c2 = list(c)
        c2[i] += sign * 0.05
        p.box(s3b, c2, bevel=0.05, mat="M_DarkMetal")
        hd = [0.2, 0.2, 0.2]
        hd[others[1]] = fr[1] * 0.3
        c3 = list(c2)
        c3[i] += sign * 0.25
        p.box(hd, c3, mat="M_Hydraulic")
    p.transform(rot, loc)
    return p.commit()


def mechanics(zone, bone, cx, cy, z0, z1, hw, hd, seed, front=-1, gears=True):
    """Exposed 'muscle' under removed plates: rib frames hugging the shell, drive shaft with gears, servo drums, cable runs and
    orange clamps. (cx, cy) is the centre of the shell cross-section, hw/hd its half width/depth; `front` = -1 for the -Y face."""
    import random
    rng = random.Random(seed)
    L = z1 - z0
    n = max(2, int(L / 3.4))
    ribs = hs.inner(zone, bone, "M_DarkMetal")
    for k in range(n):
        z = z0 + L * (k + 0.5) / n
        t, h = 0.55, 0.9
        ribs.box((2 * hw + 0.8, t, h), (cx, cy - hd - 0.1, z))
        ribs.box((2 * hw + 0.8, t, h), (cx, cy + hd + 0.1, z))
        ribs.box((t, 2 * hd + 0.8, h), (cx - hw - 0.1, cy, z))
        ribs.box((t, 2 * hd + 0.8, h), (cx + hw + 0.1, cy, z))
    ribs.commit()
    drive = hs.inner(zone, bone, "M_Hydraulic")
    yface = cy + front * (hd + 0.9)
    drive.cyl(0.55, L * 0.92, (cx, yface, (z0 + z1) / 2), "z", 10)
    if gears:
        for k in range(max(1, int(L / 7))):
            z = z0 + L * (k + 0.5) / max(1, int(L / 7))
            r = rng.uniform(1.7, 2.6)
            drive.cyl(r, 0.55, (cx, yface, z), "y", 14, bevel=0.12, mat="M_DarkMetal")
            drive.cyl(r * 0.4, 0.9, (cx, yface, z), "y", 10)
    drive.commit()
    motors = hs.inner(zone, bone, "M_DarkMetal")
    for k in range(max(2, int(L / 6))):
        z = z0 + L * (k + 0.5) / max(2, int(L / 6))
        x = cx + rng.choice([-1, 1]) * hw * 0.5
        motors.cyl(rng.uniform(1.2, 1.7), rng.uniform(2.6, 3.8), (x, yface + front * 0.6, z), "z", 12, bevel=0.15)
        motors.cyl(1.95, 0.4, (x, yface + front * 0.6, z + 1.6), "z", 12)
        motors.box((1.6, 0.5, 0.5), (x, yface + front * 0.6, z - 1.9), mat="M_Emissive_Status")
    motors.commit()
    clamp = hs.inner(zone, bone, "M_AccentOrange")
    for k in range(max(2, int(L / 8))):
        z = z0 + L * (k + 0.3 + 0.4 * rng.random()) / max(2, int(L / 8))
        clamp.box((2 * hw * 0.7, 0.4, 0.7), (cx, cy + front * (hd + 0.45), z), bevel=0.05)
    clamp.commit()
    for q in range(3):
        x = cx + (q - 1) * hw * 0.55
        pts = [(x, yface + front * 0.2, z0 + 0.5 * L * 0.1)]
        for k in range(1, 5):
            pts.append((x + rng.uniform(-0.8, 0.8), yface + front * rng.uniform(0.1, 0.7), z0 + L * k / 4))
        hs.cable_curve(zone, bone, pts, radius=rng.uniform(0.18, 0.3))


def piston(zone, bone_barrel, bone_rod, a, b, r=0.8, mat_rod="M_Hydraulic"):
    """Hydraulic piston between world points a (barrel end) and b (rod end): barrel on one bone, rod on another."""
    A, B = Vector(a), Vector(b)
    d = B - A
    ln = d.length
    e = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler("XYZ")
    barrel = hs.inner(zone, bone_barrel, "M_DarkMetal")
    barrel.cyl(r, ln * 0.55, (0, 0, 0), "z", 12, bevel=0.1)
    barrel.cyl(r * 1.3, ln * 0.06, (0, 0, -ln * 0.2), "z", 12)
    ob = barrel.commit()
    ob.location = A.lerp(B, 0.28)
    ob.rotation_euler = e
    hs.bake_transform(ob)
    rod = hs.inner(zone, bone_rod, mat_rod)
    rod.cyl(r * 0.55, ln * 0.55, (0, 0, 0), "z", 10)
    orod = rod.commit()
    orod.location = A.lerp(B, 0.72)
    orod.rotation_euler = e
    hs.bake_transform(orod)
    return ob, orod


# ----------------------------------------------------------------------------------------------------- zones
def build_head(P):
    hy, hz = P["head_y"], P["neck_z"]
    cz = hz + 5.4
    b = hs.body("head", "Head", "M_Graphite")
    b.box((13.0, 13.0, 8.6), (0, hy, cz), bevel=0.6, chamfer=2.0, chamfer_axis="z", taper=(0.88, 0.72))
    b.box((8.0, 7.0, 2.2), (0, hy + 1.8, cz + 5.2), bevel=0.4, chamfer=0.8, chamfer_axis="z")           # sensor hump
    b.box((9.5, 0.7, 1.6), (0, hy - 6.7, cz + 1.0), mat="M_Glass_Sensor")                              # main visor
    b.box((2.6, 0.6, 1.0), (4.8, hy - 6.2, cz - 1.4), mat="M_Glass_Sensor")
    b.box((2.6, 0.6, 1.0), (-4.8, hy - 6.2, cz - 1.4), mat="M_Glass_Sensor")
    b.commit()
    plate("Head", "head", (0, hy - 7.0, cz - 1.2), (11.0, 1.2, 4.6), "-y", accent=True, rot=(8, 0, 0), chamfer=1.0)
    plate("Head", "head", (6.6, hy + 0.5, cz), (1.0, 9.5, 5.6), "+x", louvres=3, rot=(0, 0, 0), chamfer=1.0)
    plate("Head", "head", (-6.6, hy + 0.5, cz), (1.0, 9.5, 5.6), "-x", louvres=3, chamfer=1.0)
    plate("Head", "head", (0, hy + 1.8, cz + 6.5), (7.5, 6.5, 0.9), "+z", chamfer=0.8)
    j = hs.joint("head", "Head")
    j.cyl(3.6, 2.2, (0, hy + 1.0, hz + 0.6), "z", 20, bevel=0.2)
    j.commit()
    sens = hs.inner("Head", "head", "M_DarkMetal")
    sens.box((3.0, 3.0, 3.0), (0, hy, cz - 0.5), bevel=0.2)
    sens.cyl(0.5, 4.0, (3.0, hy + 2.0, cz + 5.8), "z", 8)
    sens.cyl(0.5, 4.5, (-3.2, hy + 2.0, cz + 5.7), "z", 8)
    sens.commit()
    lights = hs.inner("Head", "head", "M_DarkMetal")
    for k in range(3):
        lights.box((0.5, 0.3, 0.3), (-1.4 + 1.4 * k, hy - 7.1, cz - 3.4), mat="M_Emissive_Status")
    lights.commit()
    mast = hs.armor("Head", "head", "M_DarkMetal")   # sensor mast: tops out the 82 m height
    zb = cz + 6.4                                    # mast base on the sensor hump; its tip is the highest point: 82.0 m
    top = P["height"]
    mast.box((1.6, 1.6, 0.4), (2.5, hy + 3.0, zb - 0.1), bevel=0.1)
    mast.cyl(0.35, (top - zb) * 0.6, (2.5, hy + 3.0, zb + (top - zb) * 0.3), "z", 8)
    mast.cyl(0.18, (top - zb) * 0.5, (2.5, hy + 3.0, top - (top - zb) * 0.25), "z", 6)
    mast.commit()


def build_torso(P):
    wz, sz = P["waist_z"], P["shoulder_z"]
    bz = P["chest_z"]
    b = hs.body("torso", "Torso", "M_Graphite")
    b.box((30, 20, 19), (0, 0, bz), bevel=0.9, chamfer=2.8, chamfer_axis="z", taper=(1.18, 1.0))        # chest shell, wide on top
    b.box((22, 16, 8), (0, 0, wz + 3.5), bevel=0.8, chamfer=2.2, chamfer_axis="z", taper=(1.12, 1.0))   # abdomen
    b.box((22, 15, 3.5), (0, -1.0, sz + 5.8), bevel=0.6, chamfer=2.0, chamfer_axis="z")                 # shoulder deck
    b.commit()
    cj = hs.joint("torso", "Torso")
    cj.cyl(11.5, 3.2, (0, 0, wz - 0.4), "z", 28, bevel=0.3)
    cj.commit()
    # front: two big sloped breast plates, a vented sternum strip, windowed belly plates
    plate("Torso", "torso", (-9.3, -11.2, bz + 3.8), (16.0, 1.8, 10.5), "-y", accent=True, rot=(-7, 0, 0), chamfer=2.0)
    plate("Torso", "torso", (9.3, -11.2, bz + 3.8), (16.0, 1.8, 10.5), "-y", louvres=4, rot=(-7, 0, 0), chamfer=2.0)
    plate("Torso", "torso", (0, -11.0, bz + 3.2), (4.0, 1.6, 9.0), "-y", windows=2, louvres=0, chamfer=0.8)
    plate("Torso", "torso", (0, -11.6, bz - 5.8), (27, 1.6, 6.5), "-y", windows=6, chamfer=1.5)
    plate("Torso", "torso", (-9.0, -9.6, wz + 3.5), (9.0, 1.4, 6.0), "-y", chamfer=1.2)
    plate("Torso", "torso", (9.0, -9.6, wz + 3.5), (9.0, 1.4, 6.0), "-y", louvres=3, chamfer=1.2)
    # sides
    plate("Torso", "torso", (-18.3, -3.0, bz + 1.5), (1.8, 15, 14), "-x", louvres=5, rot=(0, 0, 6), chamfer=2.0)
    plate("Torso", "torso", (18.3, -3.0, bz + 1.5), (1.8, 15, 14), "+x", windows=3, rot=(0, 0, -6), chamfer=2.0)
    # back with maintenance hatch + vents
    plate("Torso", "torso", (-8.5, 11.2, bz + 1.5), (15, 1.6, 14), "+y", hatch=True, chamfer=2.0)
    plate("Torso", "torso", (8.5, 11.2, bz + 1.5), (15, 1.6, 14), "+y", louvres=5, chamfer=2.0)
    # shoulder deck plates and a landing pad
    plate("Torso", "torso", (-12.5, -1.0, sz + 7.8), (8, 11, 1.0), "+z", chamfer=1.4)
    pad = hs.armor("Torso", "torso", "M_CeramicGray")
    pad.cyl(4.2, 0.7, (12.0, -1.0, sz + 7.8), "z", 24, bevel=0.1)
    pad.cyl(3.6, 0.18, (12.0, -1.0, sz + 8.2), "z", 24, mat="M_AccentOrange")
    pad.cyl(2.3, 0.2, (12.0, -1.0, sz + 8.4), "z", 24, mat="M_CeramicGray")
    pad.commit()
    ladder = hs.armor("Torso", "torso", "M_DarkMetal")
    for k in range(13):
        ladder.box((0.35, 2.6, 0.3), (-8.0 + 0.0, 12.9, bz - 7.0 + k * 1.1) if False else (21.6, 7.0, bz - 6.0 + k * 1.0), mat="M_DarkMetal")
    ladder.box((0.3, 0.3, 13.5), (21.6, 5.7, bz + 0.5), mat="M_DarkMetal")
    ladder.box((0.3, 0.3, 13.5), (21.6, 8.3, bz + 0.5), mat="M_DarkMetal")
    ladder.commit()
    # inner mechanics
    mechanics("Torso", "torso", 0.0, 0.0, bz - 8.0, bz + 8.0, 13.0, 9.0, 61, front=-1)
    inn = hs.inner("Torso", "torso", "M_DarkMetal")
    for x in (-9, 9):
        inn.cyl(0.9, 9, (x, -10.0, bz + 3.5), "z", 12)
        inn.box((3.5, 1.0, 1.0), (x, -10.0, bz - 1.5), bevel=0.1)
    inn.commit()
    inn2 = hs.inner("Torso", "torso", "M_DarkMetal")
    for x in (-10, -3, 3, 10):
        inn2.cyl(0.6, 12, (x, 10.4, bz + 1.5), "z", 10)
    inn2.box((26, 0.8, 0.8), (0, 10.4, bz - 4), bevel=0.1)
    inn2.commit()
    inn3 = hs.inner("Torso", "torso", "M_Hydraulic")
    inn3.cyl(0.7, 12, (-17.2, -5, bz + 1), "z", 10)
    inn3.cyl(0.7, 12, (17.2, -5, bz + 1), "z", 10)
    inn3.commit()
    for s in (-1, 1):
        hs.cable_curve("Torso", "torso", [(s * 3, -10.8, bz + 9), (s * 10, -11.0, bz + 8), (s * 16, -8, bz + 8.6), (s * 18.2, -3, bz + 8)],
                       radius=0.32)
    # pelvis
    pb = hs.body("pelvis", "Torso", "M_Graphite")
    pb.box((28, 17, 7), (0, 0, P["hip_z"] + 5), bevel=0.8, chamfer=2.4, chamfer_axis="z", taper=(0.94, 0.95))
    pb.box((9, 12, 5), (0, 3.5, P["hip_z"] + 4), bevel=0.4)
    pb.commit()
    plate("Torso", "pelvis", (0, -9.3, P["hip_z"] + 5), (18, 1.4, 6), "-y", louvres=3, chamfer=1.2)
    plate("Torso", "pelvis", (-14.3, 0, P["hip_z"] + 5), (1.3, 12, 5), "-x", chamfer=1.0)
    plate("Torso", "pelvis", (14.3, 0, P["hip_z"] + 5), (1.3, 12, 5), "+x", chamfer=1.0)
    plate("Torso", "pelvis", (0, 9.3, P["hip_z"] + 5), (18, 1.4, 6), "+y", louvres=3, chamfer=1.2)


def build_reactor(P):
    ry, rz = P["reactor_y"], P["reactor_z"]
    b = hs.body("reactor", "Reactor", "M_Graphite")
    b.box((15, 10, 15), (0, ry, rz + 3.5), bevel=0.8, chamfer=2.0, chamfer_axis="y")
    b.commit()
    core = hs.inner("Reactor", "reactor", "M_DarkMetal")
    core.cyl(2.8, 12, (0, ry - 5.4, rz + 3.5), "z", 20, bevel=0.2)
    core.cyl(1.9, 11, (0, ry - 5.8, rz + 3.5), "z", 20, mat="M_Emissive_Status")
    for k in (-1, 1):
        core.cyl(0.7, 10, (k * 5.5, ry - 5.5, rz + 3.5), "z", 10)
    core.commit()
    plate("Reactor", "reactor", (-4.3, ry + 5.9, rz + 3.5), (6.5, 1.4, 13), "+y", louvres=6, chamfer=1.2)
    plate("Reactor", "reactor", (4.3, ry + 5.9, rz + 3.5), (6.5, 1.4, 13), "+y", louvres=6, accent=True, chamfer=1.2)
    plate("Reactor", "reactor", (0, ry, rz + 11.5), (11, 8, 1.2), "+z", louvres=3, chamfer=1.5)
    for s in (-1, 1):
        fin = hs.armor("Reactor", "reactor", "M_DarkMetal")
        for q in range(7):
            fin.box((0.35, 8.5, 12.5), (s * (8.1 + 0.55 * q), ry, rz + 3.5), bevel=0.05)
        fin.commit()
    stack = hs.inner("Reactor", "reactor", "M_Hydraulic")
    for x in (-3.5, 3.5):
        stack.cyl(1.0, 6, (x, ry + 1, rz + 13.5), "z", 12)
    stack.commit()


def build_shoulder(P, side):
    s = 1 if side == "l" else -1
    Z = "Shoulder" + side.upper()
    bone = "shoulder_" + side
    x0, z0 = s * P["shoulder_x"], P["shoulder_z"]
    cx = s * (P["shoulder_x"] + 2.5)
    cz = z0 + 3.5
    out = "+x" if s > 0 else "-x"
    b = hs.body(bone, Z, "M_Graphite")
    b.box((17, 21, 13), (cx, 0, cz), bevel=1.0, chamfer=3.4, chamfer_axis="z", taper=(0.8, 0.88))
    b.commit()
    plate(Z, bone, (cx, 0, cz + 6.9), (14.5, 19.0, 1.8), "+z", accent=True, chamfer=2.8)
    plate(Z, bone, (cx, -10.6, cz + 0.4), (14, 1.8, 11), "-y", louvres=4, rot=(8, 0, 0), chamfer=2.4)
    plate(Z, bone, (cx, 10.6, cz + 0.4), (14, 1.8, 11), "+y", windows=3, rot=(-8, 0, 0), chamfer=2.4)
    plate(Z, bone, (cx + s * 7.6, 0, cz), (1.8, 19, 11.5), out, louvres=5, accent=True, rot=(0, 0, 0), chamfer=2.6)
    plate(Z, bone, (cx - s * 7.4, 0, cz + 0.8), (1.6, 16, 9.5), "-x" if s > 0 else "+x", chamfer=2.0)
    plate(Z, bone, (cx, 0, cz - 6.9), (13.5, 17, 1.5), "-z", chamfer=2.4)
    mechanics(Z, bone, cx, 0.0, cz - 4.5, cz + 4.5, 6.0, 8.5, 31 + s, front=-1)
    inn = hs.inner(Z, bone, "M_DarkMetal")
    inn.cyl(0.9, 8, (cx, -9.4, cz + 0.4), "x", 12)
    inn.cyl(0.9, 8, (cx, 9.4, cz + 0.4), "x", 12)
    inn.box((9, 0.8, 0.8), (cx, -9.3, cz + 3), bevel=0.1)
    inn.commit()
    ant = hs.armor(Z, bone, "M_DarkMetal")
    ant.box((1.6, 1.6, 4.0), (cx + s * 4.0, 7.0, cz + 8.8), bevel=0.15)
    ant.cyl(0.2, 2.5, (cx + s * 4.0, 7.0, cz + 11.25), "z", 6)
    ant.commit()
    tower = hs.armor(Z, bone, "M_Graphite")        # boxy vent/sensor towers on the shoulder top, as in the key art
    tower.box((4.5, 4.5, 4.5), (cx - s * 3.0, -3.0, cz + 9.3), bevel=0.3, chamfer=0.9, chamfer_axis="z")
    tower.louvres((cx - s * 3.0, -3.0, cz + 9.3), 3.5, 3.0, 4, "-y", depth=0.25)
    tower.commit()
    j = hs.joint(bone, Z)
    j.cyl(6.2, 7.0, (x0 * 0.82, 0, z0 - 0.5), "x", 24, bevel=0.3)
    j.commit()
    hs.cable_curve(Z, bone, [(s * 14, -4, cz + 1), (s * 18, -10.5, z0 + 3), (s * 24, -10.8, z0 - 3), (s * 27, -8, z0 - 8)], radius=0.36)


def build_arm(P, side):
    s = 1 if side == "l" else -1
    Z = "Arm" + side.upper()
    ax = s * P["arm_x"]
    sz, ez, wz = P["shoulder_z"], P["elbow_z"], P["wrist_z"]
    ua, fa, hd = "upperarm_" + side, "forearm_" + side, "hand_" + side
    out = "+x" if s > 0 else "-x"
    inw = "-x" if s > 0 else "+x"
    ucz = (sz - 1 + ez) / 2 - 0.5
    ulen = sz - 1 - ez
    b = hs.body(ua, Z, "M_Graphite")
    b.box((11.5, 12.5, ulen - 1.0), (ax, -1.0, ucz), bevel=0.8, chamfer=2.6, chamfer_axis="z", taper=(0.88, 0.9))
    b.commit()
    plate(Z, ua, (ax + s * 6.4, -1.0, ucz + 0.5), (1.6, 12, ulen - 3.5), out, louvres=3, chamfer=2.0)
    plate(Z, ua, (ax - s * 6.2, -1.0, ucz + 0.5), (1.5, 11, ulen - 5), inw, chamfer=1.6)
    plate(Z, ua, (ax, -7.6, ucz + 0.5), (10.5, 1.6, ulen - 3.5), "-y", accent=True, chamfer=2.0)
    plate(Z, ua, (ax, 5.8, ucz + 0.5), (10.5, 1.6, ulen - 3.5), "+y", windows=2, chamfer=2.0)
    plate(Z, ua, (ax, -1.0, ucz + ulen / 2 + 0.2), (12.5, 13.5, 1.4), "+z", chamfer=2.0)
    jsock = hs.joint(ua, Z)
    jsock.cyl(5.0, 11.0, (s * P["shoulder_x"], 0, sz - 2.0), "y", 20, bevel=0.3)
    jsock.commit()
    mechanics(Z, ua, ax, -1.0, ez + 1.0, sz - 5.0, 4.6, 5.4, 11 + s, front=-1)
    piston(Z, ua, fa, (ax + s * 4.2, -8.4, ez + 10.0), (ax + s * 4.2, -9.0, ez - 3.0), r=0.9)
    piston(Z, ua, fa, (ax - s * 4.2, -8.4, ez + 10.0), (ax - s * 4.2, -9.0, ez - 3.0), r=0.9)
    j = hs.joint(fa, Z)
    j.cyl(5.4, 13.5, (ax, -2, ez), "x", 24, bevel=0.35)
    j.commit()
    hs.cable_curve(Z, ua, [(ax + s * 3, -8.0, sz - 6), (ax + s * 4.8, -9.2, ucz), (ax + s * 4.4, -9.4, ez + 3), (ax + s * 2, -9.8, ez - 3)],
                   radius=0.36)
    flen = ez - wz
    fcz = (ez + wz) / 2 - 0.5
    b = hs.body(fa, Z, "M_Graphite")
    b.box((13.5, 15.0, flen - 2.0), (ax, -3.0, fcz), bevel=0.9, chamfer=3.0, chamfer_axis="z", taper=(0.78, 0.82))
    b.commit()
    plate(Z, fa, (ax + s * 7.7, -3.0, fcz + 1.0), (1.8, 14, flen - 4.5), out, louvres=4, accent=True, chamfer=2.2)
    plate(Z, fa, (ax - s * 7.4, -3.0, fcz + 1.0), (1.6, 12.5, flen - 5.5), inw, chamfer=1.8)
    plate(Z, fa, (ax, -11.2, fcz + 1.0), (12.0, 1.8, flen - 4.5), "-y", windows=3, chamfer=2.4)
    plate(Z, fa, (ax, 5.0, fcz + 1.0), (12.0, 1.8, flen - 4.5), "+y", louvres=3, chamfer=2.4)
    plate(Z, fa, (ax, -3.0, fcz + flen / 2 - 0.6), (13.5, 15.5, 1.5), "+z", chamfer=2.2)
    mechanics(Z, fa, ax, -3.0, wz + 2.0, ez - 3.0, 5.4, 6.2, 21 + s, front=-1)
    inner = hs.inner(Z, fa, "M_DarkMetal")
    inner.cyl(1.1, flen - 6, (ax + s * 4.8, -10.2, fcz), "z", 12)
    inner.cyl(1.1, flen - 6, (ax - s * 4.8, -10.2, fcz), "z", 12)
    inner.commit()
    hs.cable_curve(Z, fa, [(ax + s * 3, -10.9, ez - 3), (ax + s * 5.4, -11.0, fcz), (ax + s * 4.4, -11.0, wz + 4), (ax + s * 2, -9.8, wz + 1)],
                   radius=0.32)
    j = hs.joint(hd, Z)
    j.cyl(3.8, 10.5, (ax, -4, wz), "x", 20, bevel=0.3)
    j.commit()
    hb = hs.body(hd, Z, "M_Graphite")
    hb.box((13.0, 14.0, 10.0), (ax, -4.5, wz - 6.2), bevel=0.8, chamfer=2.2, chamfer_axis="z", taper=(1.0, 0.95))
    for k in range(4):   # fingers curled into a fist (knuckle row faces -Y)
        hb.box((2.9, 4.8, 6.5), (ax + (k - 1.5) * 3.1, -12.2, wz - 7.4), bevel=0.4, chamfer=0.7, chamfer_axis="z")
    hb.box((3.6, 7.5, 4.2), (ax - s * 7.4, -7.0, wz - 4.6), bevel=0.5, chamfer=1.0, chamfer_axis="z")   # thumb block
    hb.commit()
    plate(Z, hd, (ax, -4.5, wz - 0.6), (12.0, 13.0, 1.3), "+z", chamfer=2.0)
    plate(Z, hd, (ax, -14.9, wz - 7.8), (11.5, 1.2, 4.6), "-y", bolts=False, chamfer=1.2)
    plate(Z, hd, (ax + s * 6.9, -4.5, wz - 6.4), (1.2, 11, 7.0), out, chamfer=1.6)


def build_leg(P, side):
    s = 1 if side == "l" else -1
    Z = "Leg" + side.upper()
    lx = s * P["leg_x"]
    hz, kz, az = P["hip_z"], P["knee_z"], P["ankle_z"]
    th, sh, ft = "thigh_" + side, "shin_" + side, "foot_" + side
    out = "+x" if s > 0 else "-x"
    inw = "-x" if s > 0 else "+x"
    tlen = hz - kz
    tcz = (hz + kz) / 2
    b = hs.body(th, Z, "M_Graphite")
    b.box((13.5, 18, tlen - 1.5), (lx, -0.5, tcz), bevel=1.0, chamfer=3.0, chamfer_axis="z", taper=(0.9, 0.92))
    b.commit()
    plate(Z, th, (lx + s * 7.8, -0.5, tcz + 0.5), (1.8, 14, tlen - 4), out, louvres=3, chamfer=2.2)
    plate(Z, th, (lx, -10.4, tcz + 0.7), (13, 1.8, tlen - 3.5), "-y", accent=True, chamfer=2.4)
    plate(Z, th, (lx, 9.4, tcz + 0.7), (12, 1.6, tlen - 3.5), "+y", chamfer=2.2)
    plate(Z, th, (lx - s * 7.5, -0.5, tcz + 1.0), (1.6, 12, tlen - 5), inw, chamfer=1.8)
    jh = hs.joint(th, Z)
    jh.cyl(6.6, 9.5, (lx, 0, hz), "x", 24, bevel=0.3)
    jh.commit()
    mechanics(Z, th, lx, -0.5, kz + 2.0, hz - 2.0, 5.4, 7.0, 41 + s, front=-1)
    ti = hs.inner(Z, th, "M_DarkMetal")
    ti.cyl(1.2, tlen - 3, (lx + s * 3.8, -9.6, tcz), "z", 12)
    ti.cyl(1.2, tlen - 3, (lx - s * 3.8, -9.6, tcz), "z", 12)
    ti.commit()
    jk = hs.joint(sh, Z)
    jk.cyl(6.0, 15.5, (lx, -1, kz), "x", 24, bevel=0.35)
    jk.commit()
    knee = hs.armor(Z, th, "M_CeramicGray")   # knee guard rides on the thigh bone
    knee.box((12.0, 4.5, 7.0), (0, 0, 0), bevel=0.8, chamfer=1.8, chamfer_axis="y", taper=(0.9, 0.85))
    knee.box((8.0, 0.8, 4.0), (0, -2.5, 0), bevel=0.2, mat="M_Graphite")
    knee.transform((-6, 0, 0), (lx, -11.8, kz + 2.8))
    knee.commit()
    slen = kz - az
    scz = (kz + az) / 2 - 0.5
    b = hs.body(sh, Z, "M_Graphite")
    b.box((12.5, 17, slen - 2.0), (lx, 0.5, scz), bevel=1.0, chamfer=3.0, chamfer_axis="z", taper=(0.76, 0.8))
    b.commit()
    plate(Z, sh, (lx + s * 7.1, 0.5, scz + 1), (1.7, 14, slen - 5), out, windows=2, chamfer=2.2)
    plate(Z, sh, (lx - s * 7.0, 0.5, scz + 1), (1.6, 13, slen - 6), inw, chamfer=1.8)
    plate(Z, sh, (lx, -9.0, scz + 1.2), (11.5, 1.8, slen - 5), "-y", louvres=3, accent=True, chamfer=2.4, rot=(10, 0, 0))
    plate(Z, sh, (lx, 9.8, scz + 0.5), (11.5, 2.0, slen - 4), "+y", louvres=5, chamfer=2.4)
    ja = hs.joint(ft, Z)
    ja.cyl(4.6, 12.5, (lx, 2, az), "x", 20, bevel=0.3)
    ja.commit()
    mechanics(Z, sh, lx, 0.5, az + 2.0, kz - 2.0, 4.8, 6.4, 51 + s, front=-1)
    si = hs.inner(Z, sh, "M_DarkMetal")
    si.cyl(1.1, slen - 6, (lx + s * 3.8, -8.4, scz), "z", 12)
    si.cyl(1.1, slen - 6, (lx - s * 3.8, -8.4, scz), "z", 12)
    si.commit()
    rod = hs.inner(Z, ft, "M_Hydraulic")
    rod.cyl(0.6, 6, (lx + s * 3.8, -8.4, az + 5.0), "z", 10)
    rod.cyl(0.6, 6, (lx - s * 3.8, -8.4, az + 5.0), "z", 10)
    rod.commit()
    hs.cable_curve(Z, sh, [(lx + s * 5.4, -7.0, kz - 3), (lx + s * 6, -8.0, scz), (lx + s * 4.4, -8.2, az + 6), (lx + s * 2, -5, az + 3)],
                   radius=0.36)
    fb = hs.body(ft, Z, "M_Graphite")
    fb.box((13.0, 27, 3.6), (lx, -4.0, 2.0), bevel=0.8, chamfer=2.4, chamfer_axis="z", taper=(0.93, 0.88))
    fb.box((10.5, 9, 3.4), (lx, 4.5, az + 1.7), bevel=0.8, chamfer=1.5, chamfer_axis="z")
    fb.commit()
    sole = hs.armor(Z, ft, "M_Rubber")
    sole.box((13.4, 28, 0.9), (lx, -4.0, 0.45), bevel=0.3, chamfer=2.2, chamfer_axis="z", mat="M_Rubber")
    sole.commit()
    plate(Z, ft, (lx, -11.0, 4.1), (11.5, 10.0, 1.2), "+z", accent=True, chamfer=2.0)
    plate(Z, ft, (lx, -17.7, 2.2), (11.8, 1.5, 3.2), "-y", bolts=False, chamfer=1.0)
    plate(Z, ft, (lx + s * 6.8, -4.0, 2.4), (1.3, 21, 3.0), out, chamfer=1.0)


def build_all(P):
    build_head(P)
    build_torso(P)
    build_reactor(P)
    for side in ("l", "r"):
        build_shoulder(P, side)
        build_arm(P, side)
        build_leg(P, side)

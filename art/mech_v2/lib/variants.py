"""Damage and faction variants (all registered in hs.REG.variants, exported separately from the contract mesh):
dented plates (`Armor_<Zone>_<NN>_dent`), severed stumps (`Stump_<bone>`), torn-open mechanics (`Inner_<Zone>_<NN>_dmg`), enemy head and
angular enemy pauldrons, detached arms (`Detached_Arm_L/R` with their own 3-bone rig)."""
import math
import random

import bpy
import bmesh
from mathutils import Matrix, Vector

from . import forms, hs, kit
from .forms import Sec, Tube
from .z_legs import L3
from .z_torso import ly


# ----------------------------------------------------------------------------------------------- dented plates
DENT_PICKS = (
    "Armor_Torso_01", "Armor_Torso_02", "Armor_Torso_03", "Armor_Torso_04", "Armor_Torso_14", "Armor_ShoulderL_01", "Armor_ShoulderR_01",
    "Armor_ShoulderL_04", "Armor_ShoulderR_04", "Armor_ArmL_08", "Armor_ArmR_08", "Armor_ArmL_09", "Armor_ArmR_09", "Armor_LegL_01", "Armor_LegR_01",
    "Armor_LegL_09", "Armor_LegR_09", "Armor_Head_02", "Armor_Reactor_01",
)


def dent_variants(amount=0.95):
    made = []
    for nm in DENT_PICKS:
        spec = kit.SPECS.get(nm)
        if spec is None:
            continue
        o = kit.plate(**spec, dent=amount, name=nm + "_dent", variant=True)
        o["dent_of"] = nm
        made.append(o)
    return made


def finalize_dents():
    """Dent variants whose topology equals the original's reuse its UVs; the others are packed like any other variant."""
    same, other = [], []
    for o in hs.REG.variants:
        src = o.get("dent_of")
        if not src:
            continue
        a = bpy.data.objects[src]
        if len(a.data.loops) == len(o.data.loops) and len(a.data.polygons) == len(o.data.polygons):
            same.append(o.name)
        else:
            del o["dent_of"]
            other.append(o.name)
    return same, other


def copy_uvs_from_originals():
    """A dented plate has the same topology as its original: reuse its UVs 1:1 (it maps into the same atlas region)."""
    for o in hs.REG.variants:
        src = o.get("dent_of")
        if not src:
            continue
        a = bpy.data.objects[src]
        if len(a.data.loops) != len(o.data.loops):
            raise RuntimeError("dent variant %s has different topology from %s" % (o.name, src))
        if "UVMap" not in o.data.uv_layers:
            o.data.uv_layers.new(name="UVMap")
        arr = [0.0] * (2 * len(a.data.loops))
        a.data.uv_layers["UVMap"].data.foreach_get("uv", arr)
        o.data.uv_layers["UVMap"].data.foreach_set("uv", arr)


# ----------------------------------------------------------------------------------------------- stumps
def stump(name, bone, zone, centre, axis, radius, seed, outward=1.0):
    """Torn end of a limb: jagged armour rim around a dark cavity, cut cables, two broken pistons and a bundle with bare wires.
    `axis` is the direction pointing OUT of the remaining body (towards the missing part)."""
    rng = random.Random(seed)
    p = hs.Part(name, bone, zone, "stump", "M_DarkMetal")
    p.variant = True
    ax = Vector(axis).normalized()
    up = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
    a = ax.cross(up).normalized()
    b = ax.cross(a)
    c = Vector(centre)
    n = 20
    bm = p.bm
    mi_arm = p._mi("M_CeramicGray")
    mi_dark = p._mi("M_DarkMetal")
    mi_hyd = p._mi("M_Hydraulic")
    # jagged outer rim (armour/skin torn off at different lengths), inner dark cavity, the sleeve behind
    rings = []
    for k_ring, (r_mul, d0, mat_i) in enumerate(((1.0, -2.2, mi_arm), (1.0, 0.0, mi_arm), (0.86, 0.0, mi_dark), (0.64, -1.2, mi_dark))):
        ring = []
        for k in range(n):
            ang = 2 * math.pi * k / n
            jag = (rng.uniform(-0.15, 0.15) + (0.34 if k % 2 else -0.1)) if k_ring in (1, 2) else 0.0
            r = radius * r_mul * (1 + rng.uniform(-0.06, 0.06))
            d = d0 + (jag * radius * 0.9 if k_ring in (1, 2) else 0.0)
            ring.append(forms._add_vert(bm, c + ax * d + (a * math.cos(ang) + b * math.sin(ang)) * r))
        rings.append((ring, mat_i))
    for i in range(3):
        r0, r1 = rings[i][0], rings[i + 1][0]
        for k in range(n):
            k2 = (k + 1) % n
            forms._face(bm, [r0[k], r0[k2], r1[k2], r1[k]], rings[i + 1][1] if i == 1 else mi_arm if i == 0 else mi_dark)
    forms._face(bm, list(reversed(rings[0][0])), mi_arm)
    centre_v = forms._add_vert(bm, c - ax * 2.6)
    last = rings[-1][0]
    for k in range(n):
        forms._face(bm, [last[k], last[(k + 1) % n], centre_v], mi_dark)
    # cut cables sticking out of the cavity
    for k in range(7):
        ang = rng.uniform(0, 2 * math.pi)
        rr = radius * rng.uniform(0.1, 0.55)
        base = c - ax * 1.0 + (a * math.cos(ang) + b * math.sin(ang)) * rr
        tip = base + ax * rng.uniform(1.4, 3.6) + (a * rng.uniform(-1, 1) + b * rng.uniform(-1, 1)) * 1.6
        forms.add_capsule(p, base, tip, radius * 0.07, radius * 0.06, 8, 2.0, "M_Rubber")
        forms.add_capsule(p, tip, tip + (tip - base).normalized() * 0.5, radius * 0.045, radius * 0.045, 6, 2.0, "M_AccentOrange" if k % 3 == 0 else "M_Hydraulic")
    # two broken pistons: sleeve stubs with bent rods
    for k, sgn in enumerate((-1, 1)):
        off = (a * 0.5 + b * 0.2) * radius * 0.45 * sgn
        s0 = c - ax * 1.6 + off
        forms.add_capsule(p, s0, s0 + ax * 2.2, radius * 0.12, radius * 0.12, 10, 3.0, "M_DarkMetal")
        forms.add_capsule(p, s0 + ax * 2.0, s0 + ax * 3.8 + (b * 0.9 * sgn), radius * 0.065, radius * 0.06, 8, 2.0, "M_Hydraulic")
    return p.commit()


def build_stumps(P):
    out = []
    for s in (1, -1):
        side = "l" if s > 0 else "r"
        sx, ax_, lx = s * P["shoulder_x"], s * P["arm_x"], s * P["leg_x"]
        E = Vector((ax_, -4.6, P["elbow_z"]))
        W = Vector((ax_ + s * 0.5, -7.0, P["wrist_z"]))
        K = Vector((lx, P["knee_y"], P["knee_z"]))
        A = Vector((lx, P["ankle_y"], P["ankle_z"]))
        H = Vector((lx, P["hip_y"], P["hip_z"]))
        Z_arm, Z_leg = "Arm" + side.upper(), "Leg" + side.upper()
        out.append(stump("Stump_shoulder_" + side, "shoulder_" + side, Z_arm, Vector((s * 13.0, 0.2, 59.0)), (s * 0.5, 0, -1), 5.4, 11 + s))
        out.append(stump("Stump_upperarm_" + side, "upperarm_" + side, Z_arm, E + Vector((0, 0, 2.2)), (0, 0.15, -1), 4.9, 21 + s))
        out.append(stump("Stump_forearm_" + side, "forearm_" + side, Z_arm, W + Vector((0, 0, 1.0)), (0, -0.1, -1), 5.8, 31 + s))
        out.append(stump("Stump_pelvis_" + side, "pelvis", Z_leg, H + Vector((s * 0.3, 0, -1.0)), (s * 0.15, 0, -1), 7.2, 41 + s))
        out.append(stump("Stump_thigh_" + side, "thigh_" + side, Z_leg, K + Vector((0, 0, 1.8)), (0, -0.2, -1), 5.9, 51 + s))
        out.append(stump("Stump_shin_" + side, "shin_" + side, Z_leg, A + Vector((0, 0, 1.2)), (0, 0.1, -1), 6.0, 61 + s))
    return out


# ----------------------------------------------------------------------------------------------- torn mechanics
def torn_inner(zone, bone, centre, axis, radius, length, seed, idx):
    """`Inner_<Zone>_<NN>_dmg`: what a stripped region shows: ripped hoses with frayed ends, bare pistons and a spark bundle."""
    rng = random.Random(seed)
    p = hs.Part("Inner_%s_%02d_dmg" % (zone, idx), bone, zone, "inner", "M_DarkMetal")
    p.variant = True
    c = Vector(centre)
    ax = Vector(axis).normalized()
    up = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
    a = ax.cross(up).normalized()
    b = ax.cross(a)
    for k in range(5):    # torn hoses: bent capsules that stop mid-way, fat frayed tip
        ang = 2 * math.pi * k / 5 + rng.uniform(-0.3, 0.3)
        o = c + (a * math.cos(ang) + b * math.sin(ang)) * radius * rng.uniform(0.3, 0.9)
        L = length * rng.uniform(0.35, 0.75)
        mid = o + ax * L * 0.5 + (a * rng.uniform(-1, 1) + b * rng.uniform(-1, 1)) * radius * 0.4
        end = o + ax * L + (a * rng.uniform(-1, 1) + b * rng.uniform(-1, 1)) * radius * 0.7
        forms.add_capsule(p, o, mid, radius * 0.07, radius * 0.07, 8, 2.0, "M_Rubber")
        forms.add_capsule(p, mid, end, radius * 0.07, radius * 0.085, 8, 2.0, "M_Rubber")
        forms.add_capsule(p, end, end + (end - mid).normalized() * radius * 0.12, radius * 0.1, radius * 0.1, 6, 2.0, "M_AccentOrange" if k == 0 else "M_Hydraulic")
    for sgn in (-1, 1):   # bare pistons: sleeve + a long shiny rod
        o = c + (a * sgn * radius * 0.35) + b * radius * 0.2
        forms.add_capsule(p, o, o + ax * length * 0.45, radius * 0.1, radius * 0.1, 10, 3.0, "M_DarkMetal")
        forms.add_capsule(p, o + ax * length * 0.4, o + ax * length * 0.95 + b * radius * 0.1 * sgn, radius * 0.055, radius * 0.055, 8, 2.0, "M_Hydraulic")
    for k in range(6):    # spark bundle: thin bright wires fanning out (emissive in the textures)
        o = c + ax * length * 0.2 + (a * rng.uniform(-1, 1) + b * rng.uniform(-1, 1)) * radius * 0.2
        d = (ax + a * rng.uniform(-0.8, 0.8) + b * rng.uniform(-0.8, 0.8)).normalized()
        forms.add_capsule(p, o, o + d * radius * rng.uniform(0.3, 0.6), radius * 0.03, radius * 0.02, 6, 2.0, "M_Emissive_Status")
    return p.commit()


def build_torn_inners(P):
    out = []
    i = {"Head": 0, "Torso": 0, "Reactor": 0, "ShoulderL": 0, "ShoulderR": 0, "ArmL": 0, "ArmR": 0, "LegL": 0, "LegR": 0}

    def add(zone, bone, centre, axis, r, ln, seed):
        i[zone] += 1
        out.append(torn_inner(zone, bone, centre, axis, r, ln, seed, i[zone]))

    add("Head", "head", (0, P["head_y"] - 3.0, 72.5), (0, -1, 0.2), 3.2, 4.0, 1)
    add("Torso", "torso", (0, ly(P, 56) - 9.8, 56.0), (0, -1, 0), 8.0, 4.0, 2)
    add("Torso", "pelvis", (0, -7.6, 41.0), (0, -1, 0), 6.0, 3.5, 3)
    add("Reactor", "reactor", (0, P["reactor_y"] + 5.0, 58.0), (0, 1, 0), 6.0, 4.0, 4)
    for s, side in ((1, "L"), (-1, "R")):
        add("Shoulder" + side, "shoulder_" + side.lower(), (s * 17.0, 0.5, 66.0), (s, 0, 0.1), 5.0, 4.0, 5 + s)
        add("Arm" + side, "upperarm_" + side.lower(), (s * P["arm_x"] + s * 3.5, -2.6, 55.0), (s, -0.1, 0), 3.4, 3.4, 7 + s)
        add("Arm" + side, "forearm_" + side.lower(), (s * P["arm_x"] + s * 5.0, -6.0, 43.0), (s, -0.1, 0), 4.5, 3.8, 9 + s)
        add("Leg" + side, "thigh_" + side.lower(), (s * P["leg_x"] + s * 5.5, -1.4, 31.0), (s, 0, 0), 5.2, 4.0, 11 + s)
        add("Leg" + side, "shin_" + side.lower(), (s * P["leg_x"] + s * 4.6, -0.5, 14.0), (s, 0, 0), 4.6, 3.6, 13 + s)
    return out


# ----------------------------------------------------------------------------------------------- enemy faction parts
def build_enemy_head(P):
    hy = P["head_y"]
    Z, a = "Head", "head"
    secs = [Sec((0, hy, 68.6), 3.8, 4.0, 1.9), Sec((0, hy, 70.4), 5.2, 5.6, 2.0), Sec((0, hy - 0.5, 73.4), 5.9, 6.4, 2.0, flat_front=0.55), Sec((0, hy - 0.2, 76.4), 5.4, 6.0, 2.0),
            Sec((0, hy + 0.2, 78.6), 3.4, 4.2, 1.9), Sec((0, hy + 0.5, 79.4), 1.6, 2.4, 1.9)]
    p = hs.Part("Body_head_enemy", a, Z, "body", "M_Graphite")
    p.variant = True
    t = kit.vt(secs, 10)           # 10-sided: faceted, aggressive
    forms.add_tube(p, t)
    for sx in (-1, 1):             # twin sensor eyes
        p.box((2.4, 0.9, 1.5), (sx * 2.5, hy - 6.7, 73.7), bevel=0.15, mat="M_Glass_Sensor")
        p.box((1.4, 0.35, 0.5), (sx * 2.5, hy - 7.2, 73.7), mat="M_Emissive_Status")
    p.box((8.0, 0.6, 0.5), (0, hy - 6.5, 71.9), mat="M_DarkMetal")
    # forward-raked crest blades
    for sx in (-1, 1):
        p.box((0.8, 5.0, 5.0), (sx * 3.2, hy - 1.5, 79.4), rot=(-35, 0, sx * 8), bevel=0.15, mat="M_DarkMetal")
    p.commit()


def build_enemy_shoulders(P):
    for s in (1, -1):
        side = "L" if s > 0 else "R"
        Z, a = "Shoulder" + side, "shoulder_" + side.lower()
        o = hs.Part("Armor_Shoulder%s_enemy" % side, a, Z, "armor", "M_Graphite")
        o.variant = True
        secs = [Sec((s * 15.4, 0.5, 57.6), 4.8, 6.2, 1.9), Sec((s * 15.0, 0.3, 61.0), 8.6, 9.4, 2.0), Sec((s * 14.4, 0.2, 66.0), 9.2, 10.0, 2.0),
                Sec((s * 13.4, 0.0, 71.0), 8.0, 8.8, 2.0), Sec((s * 12.6, -0.2, 73.8), 5.0, 5.8, 1.9), Sec((s * 12.4, -0.2, 75.0), 1.8, 2.4, 1.9)]
        t = kit.vt(secs, 8)            # octagonal: angular plates
        forms.add_tube(o, t)
        for dy in (-1, 1):             # forward / aft blade fins
            o.box((1.2, 5.0, 9.0), (s * 14.0, dy * 10.2, 66.0), rot=(dy * 14, 0, 0), bevel=0.2, taper=(1.0, 0.5), mat="M_DarkMetal")
        o.box((7.0, 0.8, 7.0), (s * 22.0, 0.0, 66.0), rot=(0, 0, 0), mat="M_AccentOrange", taper=(0.6, 1.0))
        o.commit()


# ----------------------------------------------------------------------------------------------- detached arms
def build_detached_arms(P):
    """Complete arm (upperarm + forearm + fist, with every plate / inner / joint / cable) as ONE skinned mesh on its own 3-bone rig."""
    out = []
    for s, side in ((1, "l"), (-1, "r")):
        bones = {"upperarm_" + side, "forearm_" + side, "hand_" + side}
        src = [o for o in hs.REG.parts if o["bone"] in bones]
        copies = []
        for o in src:
            c = o.copy()
            c.data = o.data.copy()
            c.modifiers.clear()
            c.parent = None
            bpy.context.scene.collection.objects.link(c)
            copies.append(c)
        for o in bpy.context.selected_objects:
            o.select_set(False)
        for c in copies:
            c.select_set(True)
        bpy.context.view_layer.objects.active = copies[0]
        bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
        obj.name = "Detached_Arm_%s" % side.upper()
        obj.data.name = obj.name
        obj["bone"], obj["zone"], obj["kind"], obj["variant"] = "upperarm_" + side, "Arm" + side.upper(), "detached", True
        bpy.context.scene.collection.objects.unlink(obj)
        hs.REG.collection.objects.link(obj)
        # own rig: the same three bones as on the mech
        arm = bpy.data.armatures.new("Detached_Arm_%s_Rig" % side.upper())
        ro = bpy.data.objects.new(arm.name, arm)
        hs.REG.collection.objects.link(ro)
        bpy.context.view_layer.objects.active = ro
        ro.select_set(True)
        main = hs.REG.armature.data.bones
        bpy.ops.object.mode_set(mode="EDIT")
        eb = {}
        for nm in ("upperarm_", "forearm_", "hand_"):
            b = arm.edit_bones.new(nm + side)
            b.head, b.tail = main[nm + side].head_local, main[nm + side].tail_local
            eb[nm + side] = b
        eb["forearm_" + side].parent = eb["upperarm_" + side]
        eb["hand_" + side].parent = eb["forearm_" + side]
        bpy.ops.object.mode_set(mode="OBJECT")
        mod = obj.modifiers.new("Armature", "ARMATURE")
        mod.object = ro
        obj.parent = ro
        obj.matrix_parent_inverse = ro.matrix_world.inverted()
        ro["variant"] = True
        hs.REG.detached_rigs = getattr(hs.REG, "detached_rigs", []) + [ro]
        hs.REG.variants.append(obj)
        out.append(obj)
    return out


def build_all(P):
    dent_variants()
    build_stumps(P)
    build_torn_inners(P)
    build_enemy_head(P)
    build_enemy_shoulders(P)

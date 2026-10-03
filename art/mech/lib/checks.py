"""Contract checks: the build FAILS (raises ContractError) when the Unreal contract of TASK-002 is violated."""
import re

import bmesh
import bpy
import numpy as np

from . import hs, uv

REQUIRED_BONES = ["root", "pelvis", "torso", "head", "reactor"] + [
    "%s_%s" % (n, s) for s in ("l", "r") for n in ("shoulder", "upperarm", "forearm", "hand", "thigh", "shin", "foot")]
ZONES = ["Head", "Torso", "Reactor", "ShoulderL", "ShoulderR", "ArmL", "ArmR", "LegL", "LegR"]
MIN_PLATES = {"Head": 2, "Torso": 8, "Reactor": 3, "ShoulderL": 4, "ShoulderR": 4, "ArmL": 8, "ArmR": 8, "LegL": 8, "LegR": 8}
TRI_BUDGET = 450_000
NAME_RE = re.compile(r"^(Body_(?P<b1>\w+)|Armor_(?P<z1>[A-Za-z]+)_\d\d|Inner_(?P<z2>[A-Za-z]+)_\d\d|Joint_(?P<b2>\w+)|Cable_(?P<z3>[A-Za-z]+)_\d\d)$")


class ContractError(Exception):
    pass


def tris(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def run(P, height=82.0, check_uv=True, verbose=True):
    errs = []
    note = print if verbose else (lambda *a: None)
    arm = hs.REG.armature
    if arm is None or arm.name != "BASTION_Rig":
        errs.append("armature BASTION_Rig missing")
        raise ContractError("; ".join(errs))
    bones = set(b.name for b in arm.data.bones)
    if bones != set(REQUIRED_BONES):
        errs.append("bones differ: missing %s, extra %s" % (sorted(set(REQUIRED_BONES) - bones), sorted(bones - set(REQUIRED_BONES))))
    if arm.data.bones["reactor"].parent is None or arm.data.bones["reactor"].parent.name != "torso":
        errs.append("reactor must be a child of torso")
    parts = hs.REG.parts
    names = [o.name for o in parts]
    if len(set(names)) != len(names):
        errs.append("duplicate object names")
    # no stray mesh objects in the scene
    stray = [o.name for o in bpy.data.objects if o.type == "MESH" and o not in parts and o.name not in ("Ground",) and not o.name.startswith("X_")]
    if stray:
        errs.append("mesh objects without registry entry: %s" % stray[:5])
    total = 0
    used_mats = set()
    for o in parts:
        m = NAME_RE.match(o.name)
        if not m:
            errs.append("%s: name does not follow Body_/Armor_/Inner_/Joint_/Cable_ pattern" % o.name)
            continue
        zone = m.group("z1") or m.group("z2") or m.group("z3")
        if zone and zone not in ZONES:
            errs.append("%s: unknown zone %s" % (o.name, zone))
        b = o["bone"]
        if b not in bones:
            errs.append("%s: bone %s not in rig" % (o.name, b))
        bn = m.group("b1") or m.group("b2")
        if bn and bn != b:
            errs.append("%s: name says bone %s but bound to %s" % (o.name, bn, b))
        if [vg.name for vg in o.vertex_groups] != [b]:
            errs.append("%s: must have exactly one vertex group named after its bone" % o.name)
        else:
            vg = o.vertex_groups[0]
            bad = 0
            for v in o.data.vertices:
                w = [g.weight for g in v.groups if g.group == vg.index]
                if len(v.groups) != 1 or not w or abs(w[0] - 1.0) > 1e-6:
                    bad += 1
            if bad:
                errs.append("%s: %d vertices without weight 1.0" % (o.name, bad))
        if o.parent != arm or not any(md.type == "ARMATURE" and md.object == arm for md in o.modifiers):
            errs.append("%s: not parented/skinned to BASTION_Rig" % o.name)
        for slot in o.material_slots:
            if slot.material is None or slot.material.name not in hs.MATERIALS:
                errs.append("%s: unknown material" % o.name)
            else:
                used_mats.add(slot.material.name)
        me = o.data
        bad_area = sum(1 for p in me.polygons if p.area < 1e-7)
        if bad_area:
            errs.append("%s: %d zero-area faces" % (o.name, bad_area))
        ngon = sum(1 for p in me.polygons if len(p.vertices) > 4)
        if ngon:
            errs.append("%s: %d n-gons" % (o.name, ngon))
        bm = bmesh.new()
        bm.from_mesh(me)
        if bm.faces:
            vol = bm.calc_volume(signed=True)
            if vol <= 0:
                errs.append("%s: non-positive signed volume (inverted normals?)" % o.name)
        bm.free()
        if check_uv:
            if not me.uv_layers:
                errs.append("%s: no UV map" % o.name)
        total += tris(o)
    for mname in hs.MATERIALS:
        if mname not in used_mats:
            errs.append("material %s unused" % mname)
    if total > TRI_BUDGET:
        errs.append("triangle budget exceeded: %d > %d" % (total, TRI_BUDGET))
    for z, need in MIN_PLATES.items():
        n = sum(1 for o in parts if o.name.startswith("Armor_%s_" % z))
        if n < need:
            errs.append("zone %s: %d armour plates, need >= %d" % (z, n, need))
        ni = sum(1 for o in parts if o.name.startswith("Inner_%s_" % z))
        if ni < 1:
            errs.append("zone %s: no Inner_ mechanics under the plates" % z)
    for b in REQUIRED_BONES:
        if b not in ("root", "pelvis", "reactor") and not any(o.name == "Joint_" + b for o in parts):
            errs.append("no Joint_%s" % b)
        if b != "root" and not any(o.name == "Body_" + b for o in parts):
            errs.append("no Body_%s" % b)
    # extents: 82 m tall, standing on z=0, centred between the feet, facing -Y
    allv = np.array([o.matrix_world @ v.co for o in parts for v in o.data.vertices])
    mn, mx = allv.min(0), allv.max(0)
    note("bbox min %s max %s, height %.2f m" % (np.round(mn, 2), np.round(mx, 2), mx[2] - mn[2]))
    if abs(mx[2] - height) > 0.6:
        errs.append("height %.2f m, expected %.1f +-0.6" % (mx[2], height))
    if abs(mn[2]) > 0.02:
        errs.append("lowest point z=%.3f, origin must be on the ground" % mn[2])
    if abs(mn[0] + mx[0]) > 0.5:
        errs.append("not centred in X: %.2f..%.2f" % (mn[0], mx[0]))
    vis = [o for o in parts if o.name == "Body_head"][0]
    gl = [i for i, s in enumerate(vis.material_slots) if s.material.name == "M_Glass_Sensor"]
    ys = [v.co.y for p in vis.data.polygons if p.material_index in gl for v in [vis.data.vertices[i] for i in p.vertices]]
    if not ys or np.mean(ys) > P["head_y"]:
        errs.append("visor must face -Y")
    if check_uv:
        dens = []
        for o in parts:
            ua, a3, d = uv.uv_stats(o)
            if ua <= 0:
                errs.append("%s: UV area is zero" % o.name)
            dens.append(d)
            ov = uv.overlap_fraction(o)
            if ov > 0.005:
                errs.append("%s: UV islands overlap (%.1f%% of triangles)" % (o.name, ov * 100))
            for loop in o.data.uv_layers.active.data:
                if not (-1e-4 <= loop.uv[0] <= 1.0001 and -1e-4 <= loop.uv[1] <= 1.0001):
                    errs.append("%s: UV outside 0..1" % o.name)
                    break
        dens = [d for d in dens if d > 0]
        if dens and max(dens) / min(dens) > 1.05:
            errs.append("texel density spread %.2f (must be within 5%%)" % (max(dens) / min(dens)))
        note("texel density: %.5f UV/m, spread %.3f" % (min(dens), max(dens) / min(dens)))
    note("triangles: %d / %d, parts: %d" % (total, TRI_BUDGET, len(parts)))
    if errs:
        raise ContractError("\n".join(errs))
    return dict(triangles=total, bbox_min=mn.tolist(), bbox_max=mx.tolist())

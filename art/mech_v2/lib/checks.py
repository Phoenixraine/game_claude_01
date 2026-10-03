"""Contract checks: the build FAILS (raises ContractError) when the Unreal contract of TASK-002 is violated."""
import re

import bmesh
import bpy
import numpy as np

from . import hs, uv, kit

REQUIRED_BONES = ["root", "pelvis", "torso", "head", "reactor"] + [
    "%s_%s" % (n, s) for s in ("l", "r") for n in ("shoulder", "upperarm", "forearm", "hand", "thigh", "shin", "foot")]
ZONES = ["Head", "Torso", "Reactor", "ShoulderL", "ShoulderR", "ArmL", "ArmR", "LegL", "LegR"]
MIN_PLATES = {"Head": 2, "Torso": 8, "Reactor": 3, "ShoulderL": 4, "ShoulderR": 4, "ArmL": 8, "ArmR": 8, "LegL": 8, "LegR": 8}
TRI_BUDGET = 450_000
TRI_TARGET_MIN = 250_000        # TASK-013: "use at least 250 000 meaningfully" (reported, not enforced as an error)
MIN_PLATE_TYPES = {"Torso": 6, "ShoulderL": 6, "ShoulderR": 6, "ArmL": 6, "ArmR": 6, "LegL": 6, "LegR": 6}
VARIANT_RE = re.compile(r"^(Armor_(?P<z1>[A-Za-z]+)_\d\d_dent|Armor_(?P<z2>Shoulder[LR])_enemy|Body_head_enemy|Stump_(?P<b1>\w+)|Inner_(?P<z3>[A-Za-z]+)_\d\d_dmg|Detached_Arm_[LR])$")
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
    known = set(parts) | set(hs.REG.variants)
    stray = [o.name for o in bpy.data.objects if o.type == "MESH" and o not in known and o.name not in ("Ground",) and not o.name.startswith("X_")]
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
        errs += check_uv_atlases(list(parts) + [o for o in hs.REG.variants if o.get("dent_of") is None and o.name.startswith(("Stump_", "Inner_", "Body_", "Armor_"))], note)
    for z, need in MIN_PLATE_TYPES.items():
        sig = set()
        for nm, sp in kit.SPECS.items():
            if sp["zone"] == z:
                sig.add((sp["kind"], sp["nu"], sp["nv"], round(sp["taper"], 1), tuple(round(c, 1) for c in sp["cham"]), round(sp["crown"], 1), sp["mat"], bool(sp["accent"]), sp["ribs"], sp["vent"]))
        if len(sig) < need:
            errs.append("zone %s: only %d distinct plate types, need >= %d" % (z, len(sig), need))
    if total < TRI_TARGET_MIN:
        note("NOTE: %d triangles is below the 250 000 target" % total)
    note("triangles: %d / %d, parts: %d, variants: %d" % (total, TRI_BUDGET, len(parts), len(hs.REG.variants)))
    if errs:
        raise ContractError("\n".join(errs))
    return dict(triangles=total, bbox_min=mn.tolist(), bbox_max=mx.tolist())


def check_uv_atlases(objs, note):
    """UV rules for per-material atlases: every part has the UV map; all UVs inside 0..1; islands of one material do not overlap
    (bolt heads / hidden undersides, tagged faces, share tiles by design); the texel density is uniform."""
    errs = []
    by_mat = {}
    for o in objs:
        me = o.data
        if not me.uv_layers:
            errs.append("%s: no UV map" % o.name)
            continue
        uvd = me.uv_layers.active.data
        for loop in uvd:
            if not (-1e-4 <= loop.uv[0] <= 1.0001 and -1e-4 <= loop.uv[1] <= 1.0001):
                errs.append("%s: UV outside 0..1" % o.name)
                break
        tags = uv._tags(o)
        names = [s.material.name for s in o.material_slots]
        for pi, poly in enumerate(me.polygons):
            if tags[pi] or poly.area < 1e-6:
                continue
            pts = [tuple(uvd[li].uv) for li in poly.loop_indices]
            by_mat.setdefault(names[poly.material_index], []).append((pts, o.name))
    for mat, polys in by_mat.items():
        rep = {}
        ov = uv.overlap_fraction_polys([p for p, _ in polys], names=[n for _, n in polys], report=rep)
        note("  UV atlas %-18s %6d polygons, overlapping %.3f%%" % (mat, len(polys), ov * 100))
        if ov > 0.005:
            top = sorted(rep.items(), key=lambda kv: -kv[1])[:6]
            errs.append("material %s: UV islands overlap (%.2f%% of triangles), mostly in %s" % (mat, ov * 100, top))
    lo, med, hi = uv.island_density_spread([o for o in objs])
    note("texel density (UV per m): p2 %.5f, median %.5f, p98 %.5f -> %.3f px/m at 2048, spread p98/p2 = %.2f" % (lo, med, hi, med * 2048, hi / lo))
    if hi / lo > 1.45:
        errs.append("texel density spread p98/p2 = %.2f (must be <= 1.45)" % (hi / lo))
    return errs

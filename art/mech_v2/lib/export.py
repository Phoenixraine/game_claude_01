"""Exports for Unreal (FBX, glTF binary) and the machine-readable parts/pose reports."""
import json
import os

import bpy
import numpy as np

from . import hs, uv, checks


def _select_rig_and_parts():
    bpy.ops.object.select_all(action="DESELECT")
    for o in bpy.data.objects:
        o.select_set(False)
    hs.REG.armature.select_set(True)
    for o in hs.REG.parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = hs.REG.armature


def export_fbx(path):
    """Metres, +Z up, forward -Y (the contract), scale 1.0, skeletal mesh without leaf bones or baked animation."""
    _select_rig_and_parts()
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                             axis_forward="-Y", axis_up="Z", object_types={"ARMATURE", "MESH"}, add_leaf_bones=False,
                             bake_anim=False, mesh_smooth_type="FACE", use_mesh_modifiers=True, bake_space_transform=False,
                             path_mode="AUTO", use_armature_deform_only=False)


def export_variants(path):
    """Variants (dent / stump / torn mechanics / enemy parts) on the SAME rig, plus the detached arms with their own 3-bone rigs."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in bpy.data.objects:
        o.select_set(False)
    hs.REG.armature.select_set(True)
    for o in hs.REG.variants:
        o.select_set(True)
    for r in getattr(hs.REG, "detached_rigs", []):
        r.select_set(True)
    bpy.context.view_layer.objects.active = hs.REG.armature
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                             axis_forward="-Y", axis_up="Z", object_types={"ARMATURE", "MESH"}, add_leaf_bones=False,
                             bake_anim=False, mesh_smooth_type="FACE", use_mesh_modifiers=True, bake_space_transform=False,
                             path_mode="AUTO", use_armature_deform_only=False)


def export_glb(path):
    _select_rig_and_parts()
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=False, export_yup=False,
                              export_skins=True, export_animations=False, export_materials="EXPORT")


def parts_report(P, stats):
    rows = []
    for o in hs.REG.parts:
        v = np.array([o.matrix_world @ vv.co for vv in o.data.vertices])
        ua, a3, d = uv.uv_stats(o)
        rows.append({
            "name": o.name, "bone": o["bone"], "zone": o["zone"], "kind": o["kind"],
            "triangles": checks.tris(o), "vertices": len(o.data.vertices),
            "materials": [s.material.name for s in o.material_slots],
            "bbox_min": [round(float(x), 3) for x in v.min(0)], "bbox_max": [round(float(x), 3) for x in v.max(0)],
            "uv_texel_density_uv_per_m": round(d, 6), "area_m2": round(a3, 2),
        })
    zones = {}
    for r in rows:
        z = zones.setdefault(r["zone"], {"triangles": 0, "armor": [], "inner": [], "body": [], "joint": [], "cable": []})
        z["triangles"] += r["triangles"]
        z[r["kind"]].append(r["name"])
    arm = hs.REG.armature
    bones = {b.name: {"head": [round(x, 3) for x in b.head_local], "tail": [round(x, 3) for x in b.tail_local],
                      "parent": b.parent.name if b.parent else None} for b in arm.data.bones}
    return {"name": "BASTION-01 v2", "height_m": round(stats["bbox_max"][2], 3), "units": "metres, +Z up, forward -Y, origin on the ground between the feet",
            "triangles_total": stats["triangles"], "triangle_budget": checks.TRI_BUDGET, "part_count": len(rows),
            "bbox_min": [round(x, 3) for x in stats["bbox_min"]], "bbox_max": [round(x, 3) for x in stats["bbox_max"]],
            "params": P, "bones": bones, "zones": zones, "parts": rows}


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


def verify_fbx(path, expect_parts, height, tol=0.1):
    """Re-import the exported FBX into an empty scene and check what Unreal will see (bones, parts, scale, orientation)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    errs = []
    if [a.name for a in arms] != ["BASTION_Rig"]:
        errs.append("armature objects: %s" % [a.name for a in arms])
    elif set(b.name for b in arms[0].data.bones) != set(checks.REQUIRED_BONES):
        errs.append("bones after re-import differ from the contract")
    if len(meshes) != expect_parts:
        errs.append("%d meshes after re-import, expected %d" % (len(meshes), expect_parts))
    v = np.array([m.matrix_world @ vv.co for m in meshes for vv in m.data.vertices])
    if abs(v[:, 2].max() - height) > tol or abs(v[:, 2].min()) > tol:
        errs.append("re-imported z range %.3f..%.3f" % (v[:, 2].min(), v[:, 2].max()))
    if not (v[:, 1].max() > abs(v[:, 1].min())):
        errs.append("orientation: the reactor (back) must be at +Y")
    if any(len(m.vertex_groups) != 1 or not m.data.uv_layers for m in meshes):
        errs.append("a re-imported mesh lost its vertex group or UV map")
    if errs:
        raise SystemExit("FBX verification failed:\n" + "\n".join(errs))
    return len(meshes), float(v[:, 2].max())


GIT_LIMIT = 4.8 * 1024 * 1024   # CLAUDE.md: no binaries above 5 MB in git


def package_large(out_dir, names=("BASTION_01_v2.fbx", "BASTION_01_v2.glb")):
    """Files above the git limit are shipped as <name>.zip (deflate) and the raw file is git-ignored (it is rebuilt by the script)."""
    import zipfile
    ignored = []
    for n in names:
        p = os.path.join(out_dir, n)
        if os.path.getsize(p) > GIT_LIMIT:
            with zipfile.ZipFile(p + ".zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
                z.write(p, n)
            ignored.append(n)
        elif os.path.exists(p + ".zip"):
            os.remove(p + ".zip")
    with open(os.path.join(out_dir, ".gitignore"), "w") as f:
        f.write("# raw exports above 5 MB are not committed (CLAUDE.md): use the .zip next to them or rebuild\n")
        f.writelines(n + "\n" for n in ignored)
    return ignored

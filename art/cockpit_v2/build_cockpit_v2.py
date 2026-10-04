#!/usr/bin/env python3
"""Cockpit v2 build: model -> FBX/GLB + JSON contract files + crack masks + preview renders (Blender 'bpy' module, Cycles on CPU).

  python3 build_cockpit_v2.py                 # everything
  python3 build_cockpit_v2.py --no-previews   # model + export + json only
  python3 build_cockpit_v2.py --previews-only # renders only
  python3 build_cockpit_v2.py --only=S3,class # subset of previews: intact S2 S3 S4 class top
Deterministic: seed 20261004 for the layout, 7 for the damage spec."""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib import cracks, layout, metrics  # noqa: E402

OUT = os.path.join(HERE, "out")
PRE = os.path.join(HERE, "previews")
SEED = 20261004
W, H, SAMPLES = 1600, 900, 40
STATES = {"intact": "S0", "S2": "S2", "S3": "S3", "S4": "S4"}


def write_json(name, doc):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, sort_keys=False)
        f.write("\n")


def fresh(model):
    from lib import blendout
    return blendout.build_scene(model)


def export(model):
    import bpy
    from lib import blendout
    objs, eobjs, mats = fresh(model)
    for ob in list(objs.values()) + list(eobjs.values()):
        ob.hide_render = False
        ob.hide_viewport = False
    for ob in bpy.data.objects:
        ob.select_set(True)
    fbx = os.path.join(OUT, "cockpit_v2.fbx")
    glb = os.path.join(OUT, "cockpit_v2.glb")
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=False, global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE",
                             add_leaf_bones=False, bake_anim=False)
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=False, export_apply=True, export_yup=True)
    return {os.path.basename(p): os.path.getsize(p) for p in (fbx, glb)}


def prep_render(model, spec, level_name, crack_ks=()):
    """Scene for one first-person frame of damage level `level_name` (S0..S4)."""
    from lib import render
    objs, eobjs, mats = fresh(model)
    render.setup_render(W, H, SAMPLES)
    lv = spec["levels"][level_name]
    render.world(red=lv["red_light_peak"])
    render.city()
    render.lights(red=lv["red_light_peak"])
    render.hide_decals(objs, model)
    render.apply_state(lv, spec, objs, eobjs, model, mats)
    steam = [e.name for e in model.empties if e.kind == "SteamPort"]
    sparks = [e.name for e in model.empties if e.kind == "SparkPort"]
    lv2 = dict(lv)
    lv2["_sparks"] = sparks[:max(0, len(lv.get("Wire_Snapped", [])))]
    render.add_effects(lv2, eobjs, steam, strong=level_name in ("S3", "S4"))
    if crack_ks:
        render.apply_cracks(os.path.join(OUT), list(crack_ks), mats)
    render.eye_camera()
    return objs, eobjs, mats


def render_to(path):
    """Render to `path` (.jpg: rendered as PNG next to it, converted with Pillow at quality 88 and the PNG removed, keeps previews small)."""
    import bpy
    png = path[:-4] + ".png" if path.endswith(".jpg") else path
    bpy.context.scene.render.filepath = png
    bpy.ops.render.render(write_still=True)
    if png != path:
        from PIL import Image
        Image.open(png).convert("RGB").save(path, quality=88, optimize=True)
        os.remove(png)


def preview_state(model, spec, name, level):
    cracks_of = {"S0": (), "S2": (0,), "S3": (0, 1), "S4": (0, 1, 2)}
    prep_render(model, spec, level, cracks_of[level])
    render_to(os.path.join(PRE, "fp_%s.jpg" % name))


CLASS_COLORS = {"Pipe": (0.1, 0.45, 1.0), "Pipe_Burst": (0.0, 1.0, 1.0), "Wire": (1.0, 0.1, 0.9), "Wire_Snapped": (1.0, 0.6, 1.0), "Btn": (1.0, 0.85, 0.1), "Dial": (1.0, 0.6, 0.0),
                "Slider": (0.9, 0.5, 0.1), "Cap": (0.8, 0.8, 0.2), "Mon": (0.2, 1.0, 0.6), "Lamp_Warn": (1.0, 0.05, 0.05), "Lamp_Ok": (0.1, 1.0, 0.1), "AlarmBeacon": (1.0, 0.3, 0.0),
                "StrobePanel": (1.0, 1.0, 1.0), "Glass": (0.05, 0.1, 0.2), "Frame": (0.25, 0.25, 0.28), "Console": (0.35, 0.3, 0.3), "Scorch_Decal": (0.4, 0.2, 0.0)}
EMPTY_COLORS = {"SteamPort": (1.0, 1.0, 1.0), "LeakPoint": (0.0, 1.0, 1.0), "SparkPort": (1.0, 1.0, 0.0), "Fire_Socket": (1.0, 0.4, 0.0), "WireAnchor": (1.0, 0.0, 0.6), "MonitorAnchor": (0.0, 1.0, 0.5)}


def class_color(p):
    if p.kind == "Lamp":
        return CLASS_COLORS["Lamp_Warn" if p.name.startswith("Lamp_Warn") else "Lamp_Ok"]
    return CLASS_COLORS.get(p.kind, (0.3, 0.3, 0.3))


def class_scene(model, view):
    """Flat class-coloured scene: all variants visible, empties drawn as small spheres. view: 'eye' or 'top'."""
    import bpy
    from lib import render
    objs, eobjs, mats = fresh(model)
    render.setup_render(W, H, 4)
    sc = bpy.context.scene
    sc.cycles.use_denoising = False
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("flat")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.02, 0.03, 1)
    sc.world = w
    cache = {}
    for p in model.parts:
        ob = objs[p.name]
        ob.hide_render = False
        ob.hide_viewport = False
        if view == "top" and (p.kind == "Glass" or p.meta.get("panel") == "ceiling" or p.name.startswith(("Frame_Header", "Frame_Rear", "Frame_Roof", "Console_Ceiling", "Hatch"))):
            ob.hide_render = True
        c = class_color(p)
        if c not in cache:
            cache[c] = render.flat_material(c, "C%d" % len(cache))
        for i in range(len(ob.data.materials)):
            ob.data.materials[i] = cache[c]
        if p.kind == "Glass":
            ob.hide_render = view == "top"
    for e in model.empties:
        k = e.kind
        if k not in EMPTY_COLORS:
            continue
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025, segments=8, ring_count=6, location=tuple(e.pos))
        s = bpy.context.active_object
        s.data.materials.append(render.flat_material(EMPTY_COLORS[k], "E" + k))
    if view == "eye":
        render.eye_camera()
    else:
        render.eye_camera(fov_deg=70.0, loc=(2.3, 2.5, 2.6), look=(-2.3 + 0.0, -2.5 - 0.3, -2.3))
    return objs


def preview_class(model):
    class_scene(model, "eye")
    render_to(os.path.join(PRE, "classes_eye.jpg"))
    class_scene(model, "top")
    render_to(os.path.join(PRE, "top_rear.jpg"))


def measure_glass(model):
    from lib import render
    objs, eobjs, mats = fresh(model)
    return render.glass_share(objs, model, os.path.join(PRE, "glass_mask.png"))


def schematic(model):
    """Plan and side views in class colours (matplotlib): pipes and wires as their route polylines, steam ports as rings, other parts as bounding boxes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    fig, axs = plt.subplots(1, 2, figsize=(16, 7.4), dpi=100)
    fig.patch.set_facecolor("#10121a")
    for ax, (ix, iy, title) in zip(axs, ((0, 1, "plan: X right, forward (-Y) is up"), (1, 2, "side: forward (-Y) is left, Z up"))):
        ax.set_facecolor("#10121a")
        for p in model.parts:
            if p.kind in ("Pipe", "Wire", "Pipe_Burst", "Wire_Snapped"):
                continue
            bb = p.mb.bbox()
            if bb is None:
                continue
            lo, hi = bb
            ax.add_patch(plt.Rectangle((lo[ix], lo[iy]), hi[ix] - lo[ix], hi[iy] - lo[iy], fc=class_color(p), ec="none", alpha=0.25 if p.kind in ("Glass", "Frame") else 0.8))
        for r in model.pipes:
            pts = np.array(r["points"])
            ax.plot(pts[:, ix], pts[:, iy], color=CLASS_COLORS["Pipe"], lw=0.6 + 90 * r["radius"], alpha=0.8, solid_capstyle="round")
        for r in model.wires:
            pts = np.array(r["points"])
            ax.plot(pts[:, ix], pts[:, iy], color=CLASS_COLORS["Wire"], lw=0.8, alpha=0.9)
        for e in model.empties:
            if e.kind in ("SteamPort", "Fire_Socket", "SparkPort", "LeakPoint"):
                ax.plot(e.pos[ix], e.pos[iy], "o", mfc="none", mec=EMPTY_COLORS[e.kind], ms=7)
        ax.plot(0, 0, "w+", ms=16, mew=2)
        ax.set_aspect("equal")
        ax.autoscale()
        if ix == 1:
            ax.invert_xaxis()
        else:
            ax.invert_yaxis()
        ax.set_title(title, color="w")
        ax.tick_params(colors="#aaa")
    handles = [plt.Line2D([0], [0], marker="s", ls="", color=c, label=k) for k, c in CLASS_COLORS.items() if k not in ("Pipe_Burst", "Wire_Snapped")]
    handles += [plt.Line2D([0], [0], marker="o", ls="", mfc="none", mec=c, label=k) for k, c in EMPTY_COLORS.items() if k in ("SteamPort", "Fire_Socket", "SparkPort", "LeakPoint")]
    fig.legend(handles=handles, loc="lower center", ncol=11, facecolor="#10121a", labelcolor="w", fontsize=8)
    fig.savefig(os.path.join(PRE, "layout_schematic.png"), facecolor=fig.get_facecolor())


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PRE, exist_ok=True)
    only = None
    for a in argv:
        if a.startswith("--only="):
            only = set(a[7:].split(","))
    model = layout.build_model(SEED)
    spec = metrics.spec_doc(model)
    if "--previews-only" not in argv:
        write_json("cockpit_parts.json", metrics.parts_doc(model))
        write_json("cockpit_damage_spec.json", spec)
        sizes = cracks.write_masks(OUT)
        print("crack masks:", [(os.path.basename(p), n) for p, n in sizes])
        pct = measure_glass(model)
        print("glass share %.2f %%" % pct)
        write_json("cockpit_metrics.json", metrics.metrics_doc(model, round(pct, 2)))
        if "--no-export" not in argv:
            print("export:", export(model))
    if "--no-previews" not in argv:
        schematic(model)
        for name, lv in STATES.items():
            if only is None or name in only:
                preview_state(model, spec, name, lv)
                print("preview", name)
        if only is None or "class" in only or "top" in only:
            preview_class(model)
    print("done")


if __name__ == "__main__":
    main(sys.argv[1:])

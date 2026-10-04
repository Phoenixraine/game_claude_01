"""Exports (FBX per group + one GLB) and preview renders. Needs bpy."""
import json
import math
import os
import random

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw, ImageFont

from . import blend, builders, geom as g

UPRIGHT = {"Panel_Facade_Torn", "Window_Frame_Broken", "AC_Unit_Broken", "Sign_Torn"}


def _objects(lib, collection_by_group=False):
    blend.reset()
    mats = blend.make_materials(builders.MATS)
    objs = {}
    for a in lib:
        objs[a.name] = blend.mesh_to_object(a.mesh, a.name, mats)
    return objs, mats


def export_all(lib, out):
    """FBX per group (with UCX_ meshes of the L/XL shards, slabs and columns) and one GLB with every render mesh."""
    os.makedirs(out, exist_ok=True)
    objs, _ = _objects(lib)
    bad = [n for n, o in objs.items() if o.data.validate(verbose=False)]
    if bad:
        raise RuntimeError("Blender reports invalid meshes: %s" % bad)
    print("Blender mesh validation: %d meshes OK" % len(objs))
    for grp in builders.GROUPS:
        sel = [objs[a.name] for a in lib if a.group == grp]
        ucx = [blend.solid_to_ucx(a.ucx, "UCX_%s_00" % a.name) for a in lib if a.group == grp and a.ucx is not None and
               (a.category in ("Slab_Concrete", "Column_Broken") or (a.category == "Shard_Concrete" and a.size_class in ("L", "XL")))]
        blend.export_fbx(os.path.join(out, "Shards_%s.fbx" % grp), sel + ucx)
        print("exported", grp, len(sel), "meshes", len(ucx), "UCX")
        for o in ucx:
            bpy.data.objects.remove(o)
    blend.export_glb(os.path.join(out, "Shards_All.glb"), list(objs.values()))
    print("exported GLB")


# ------------------------------------------------------------------------------------------------------------------ preview helpers
def _orient(a):
    R = blend.lay_flat_matrix(a.mesh, a.category in UPRIGHT)
    v = a.mesh.v @ R.T
    return R, v


def _foot_depth(it):
    """Depth a row needs on the sheet: upright objects (facade panels, frames) also hide what is behind them, so their height counts."""
    ext = it[2].max(axis=0) - it[2].min(axis=0)
    return ext[1] + (0.65 * ext[2] if it[0].category in UPRIGHT else 0.0)


def _place_rows(items, row_w):
    """Shelf layout of (asset, R, v) items: returns positions (x,y) of the object centres and the total size."""
    gap = 0.18
    rows = []
    cur = []
    w = 0.0
    for it in items:
        ext = it[2].max(axis=0) - it[2].min(axis=0)
        fw = ext[0] + gap * max(0.5, 0.35 * max(ext[0], ext[1]) + 0.1)
        if cur and w + fw > row_w:
            rows.append(cur)
            cur, w = [], 0.0
        cur.append((it, fw))
        w += fw
    if cur:
        rows.append(cur)
    pos = {}
    y = 0.0
    total_w = 0.0
    for row in rows:
        depth = max((it[2].max(axis=0) - it[2].min(axis=0))[1] for it, _ in row)
        x = 0.0
        for it, fw in row:
            ext = it[2].max(axis=0) - it[2].min(axis=0)
            fd = _foot_depth(it)
            pos[it[0].name] = (x + ext[0] / 2, y + (fd - ext[1] / 2 if it[0].category in UPRIGHT else depth / 2) - (0 if it[0].category in UPRIGHT else 0))
            x += fw
        total_w = max(total_w, x)
        y += depth + 0.32 * max(depth, 0.3) + 0.12
    return pos, total_w, y


def _place_elevation(items, w, h):
    """Layout for upright objects (facade panels, frames): rows stacked in height on one vertical plane, seen almost frontally."""
    gap = 0.5
    best = None
    total = sum((it[2].max(axis=0) - it[2].min(axis=0))[0] + gap for it in items)
    widest = max((it[2].max(axis=0) - it[2].min(axis=0))[0] for it in items)
    for k in range(40):
        rw = widest + gap + (total - widest) * k / 39.0
        rows, cur, x = [], [], 0.0
        for it in items:
            ext = it[2].max(axis=0) - it[2].min(axis=0)
            if cur and x + ext[0] + gap > rw:
                rows.append(cur)
                cur, x = [], 0.0
            cur.append(it)
            x += ext[0] + gap
        rows.append(cur)
        pos, z, tw = {}, 0.0, 0.0
        for row in rows:
            rh = max((it[2].max(axis=0) - it[2].min(axis=0))[2] for it in row)
            x = 0.0
            for it in row:
                ext = it[2].max(axis=0) - it[2].min(axis=0)
                pos[it[0].name] = (x + ext[0] / 2, z)
                x += ext[0] + gap
            tw = max(tw, x - gap)
            z += rh + gap * 1.6
        th = z - gap * 1.6
        sc = max(tw * 1.06, th * 1.1 * (w / h))
        if best is None or sc < best[0]:
            best = (sc, pos, tw, th)
    return best[1], best[2], best[3]


def render_sheet(lib, names, path, title, row_w=None, w=1600, h=900, samples=40, pitch=30.0, label=True):
    objs, mats = _objects(lib)
    sel = [a for a in lib if a.name in names]
    items = []
    for a in sel:
        R, v = _orient(a)
        items.append((a, R, v))
    items.sort(key=lambda it: -(it[2].max(axis=0) - it[2].min(axis=0))[0])
    total_len = sum((it[2].max(axis=0) - it[2].min(axis=0))[0] for it in items)
    elev = all(a.category in UPRIGHT for a, _, _ in items)
    if elev:
        pitch = 10.0
    maxh = max(it[2][:, 2].max() - it[2][:, 2].min() for it in items)
    sp = math.sin(math.radians(pitch))
    cp = math.cos(math.radians(pitch))
    widest = max((it[2].max(axis=0) - it[2].min(axis=0))[0] for it in items)
    best = None
    for k in range(40):                                  # pick the row width that makes the camera frame as tight as possible
        rw = widest * 1.05 + (total_len - widest) * (k / 39.0) * 1.0 + 1e-6
        p_, tw_, td_ = _place_rows(items, rw)
        sc_ = max(tw_ * 1.06, (td_ * sp + maxh * cp) * (w / h) * 1.1)
        if best is None or sc_ < best[0]:
            best = (sc_, rw, p_, tw_, td_)
    _, row_w, pos, tw, td = best
    if elev:
        pos, tw, th = _place_elevation(items, w, h)
        td = 0.6
    for a, R, v in items:
        ob = objs[a.name]
        x, y = pos[a.name]
        ext = v.max(axis=0) - v.min(axis=0)
        if elev:        # (x, y) from the elevation layout = (x centre, base height)
            M = Matrix.Translation((x - (v.max(axis=0)[0] + v.min(axis=0)[0]) / 2, -(v.max(axis=0)[1] + v.min(axis=0)[1]) / 2, y - v[:, 2].min())) @ Matrix(R.tolist()).to_4x4()
        else:
            M = Matrix.Translation((x - (v.max(axis=0)[0] + v.min(axis=0)[0]) / 2, y - (v.max(axis=0)[1] + v.min(axis=0)[1]) / 2, -v[:, 2].min())) @ Matrix(R.tolist()).to_4x4()
        ob.matrix_world = M
    for n, o in objs.items():
        if n not in {a.name for a in sel}:
            bpy.data.objects.remove(o)
    blend.ground(size=max(tw, td) * 4)
    blend.setup_render(w, h, samples)
    light = blend.world_and_lights(1.0)
    cx, cy = tw / 2, td / 2
    vert = td * sp + maxh * cp
    tz = maxh * 0.15
    if elev:
        cx, cy = tw / 2, 0.0
        vert = th * cp + 1.2 * sp
        tz = th / 2
        wall = bpy.data.meshes.new("Wall")
        S = max(tw, th) * 3
        wall.from_pydata([(-S, 1.2, -S), (S, 1.2, -S), (S, 1.2, S), (-S, 1.2, S)], [], [(0, 1, 2, 3)])
        wo = bpy.data.objects.new("Wall", wall)
        sc0 = bpy.context.scene
        sc0.collection.objects.link(wo)
        wo.data.materials.append(bpy.data.objects["Ground"].data.materials[0])
    scale = max(tw * 1.06, vert * (w / h) * 1.1) + 0.02
    dist = max(tw, td, 6.0) * 3
    cam_loc = (cx, cy - dist * cp, dist * sp + tz)
    cam = blend.camera(cam_loc, (cx, cy, tz), ortho=scale)
    big = max(tw, td)
    light("SUN", (cx + big, cy - big, big * 2), (math.radians(58), 0, math.radians(40)), 2.2, (1.0, 0.93, 0.85))
    light("AREA", (cx - big, cy + big * 0.5, big), (math.radians(60), 0, math.radians(-120)), big * big * 120, (0.45, 0.65, 1.0), size=big)
    light("AREA", (cx + big, cy + big * 0.8, big * 0.6), (math.radians(70), 0, math.radians(140)), big * big * 45, (1.0, 0.6, 0.35), size=big)
    sc = bpy.context.scene
    sc.render.filepath = path[:-4] + ".png"
    bpy.ops.render.render(write_still=True)
    if True:
        img = Image.open(path[:-4] + ".png").convert("RGB")
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default(size=max(11, int(h / 70)))
        except TypeError:
            font = ImageFont.load_default()
        for li, (a, R, v) in enumerate(items):
            ob = objs.get(a.name)
            if ob is None:
                continue
            ext = v.max(axis=0) - v.min(axis=0)
            x, y = pos[a.name]
            p = world_to_camera_view(sc, cam, Vector((x, y - ext[1] / 2, 0)))
            px, py = p.x * w, (1 - p.y) * h
            txt = a.name.replace("Shard_Concrete_", "SC_")
            tw_ = d.textlength(txt, font=font)
            d.text((px - tw_ / 2, py + 3 + (li % 2) * int(h / 62)), txt, fill=(205, 225, 235), font=font)
        d.text((14, 10), title, fill=(255, 210, 120), font=font)
        img.save(path, quality=86, optimize=True)
        os.remove(path[:-4] + ".png")
    return path


def render_pile(lib, path, w=1600, h=900, samples=64, seed=7):
    """'Heap of rubble' scene after ref05: shards on a mound, glass on top, rebar sticking out, wet street, fog, warm + cold lights. A scatter, not a physics sim."""
    objs, mats = _objects(lib)
    r = random.Random("pile|%d" % seed)
    by = {}
    for a in lib:
        by.setdefault(a.category, []).append(a)

    def heap(x, y, R=5.2, H=1.7):
        d = math.hypot(x, y) / R
        return H * max(0.0, 1 - d * d) ** 1.4

    plan = [("Shard_Concrete", "S", 170), ("Shard_Concrete", "M", 80), ("Shard_Concrete", "L", 7), ("Shard_Concrete", "XL", 0), ("Slab_Concrete", None, 9), ("Column_Broken", None, 4),
            ("Rebar_Bundle", None, 8), ("Rebar_Single", None, 26), ("Steel_Plate_Bent", None, 7), ("Girder_Twisted", None, 4), ("Pipe_Broken", None, 4), ("Cable_Dangling", None, 4),
            ("Panel_Facade_Torn", None, 5), ("AC_Unit_Broken", None, 2), ("Sign_Torn", None, 2), ("Window_Frame_Broken", None, 4), ("Glass_Shard", None, 320), ("Pebble", None, 320),
            ("Gravel_Cluster", None, 60)]
    used = []
    for cat, cls, n in plan:
        pool = [a for a in by[cat] if cls is None or a.size_class == cls]
        for k in range(n):
            a = r.choice(pool)
            ang = r.uniform(0, 2 * math.pi)
            rad = 5.0 * math.sqrt(r.random()) ** 1.05 * (1.0 if cat not in ("Pebble", "Gravel_Cluster", "Glass_Shard") else 1.25)
            x, y = math.cos(ang) * rad, math.sin(ang) * rad * 0.8
            if a.category in ("Shard_Concrete", "Slab_Concrete") and a.size_class == "XL":
                x, y = r.uniform(-2.5, -1.0), r.uniform(1.5, 3.5)
            R0, v0 = _orient(a)
            Rz = g.rot_axis([0, 0, 1], r.uniform(0, 2 * math.pi))
            tilt = g.rot_axis([r.uniform(-1, 1), r.uniform(-1, 1), 0] if True else [1, 0, 0], r.gauss(0, 0.32 if cat not in ("Rebar_Single", "Girder_Twisted", "Cable_Dangling") else 0.5))
            if cat in ("Panel_Facade_Torn", "Sign_Torn", "AC_Unit_Broken", "Window_Frame_Broken"):
                R0 = g.rot_axis([1, 0, 0], r.uniform(1.0, 1.4)) @ np.eye(3) if r.random() < 0.7 else R0
            R = tilt @ Rz @ R0
            vv = a.mesh.v @ R.T
            hz = heap(x, y) * (0.85 if a.mesh.v.max() > 1.0 else 1.0)
            z = hz - vv[:, 2].min() - 0.12 * (vv[:, 2].max() - vv[:, 2].min())
            z = max(z, -vv[:, 2].min() * 0.9)
            ob = blend.mesh_to_object(a.mesh, "%s_%d" % (a.name, len(used)), mats)
            ob.matrix_world = Matrix.Translation((x, y, z)) @ Matrix(R.tolist()).to_4x4()
            used.append(ob)
    for o in list(objs.values()):
        bpy.data.objects.remove(o)
    blend.ground(size=80)
    blend.setup_render(w, h, samples)
    sc = bpy.context.scene
    light = blend.world_and_lights(0.6)
    nt = sc.world.node_tree
    out = [n for n in nt.nodes if n.type == "OUTPUT_WORLD"][0]
    vs = nt.nodes.new("ShaderNodeVolumeScatter")
    vs.inputs["Density"].default_value = 0.018
    vs.inputs["Color"].default_value = (0.75, 0.72, 0.7, 1)
    nt.links.new(vs.outputs["Volume"], out.inputs["Volume"])
    blend.camera((-8.5, -13.5, 3.4), (0.0, 0.0, 0.8), lens=40)
    light("SUN", (6, -8, 12), (math.radians(40), 0, math.radians(30)), 1.6, (0.6, 0.72, 1.0))
    light("AREA", (6, 9, 7), (math.radians(80), 0, math.radians(180)), 9000, (1.0, 0.5, 0.2), size=6)
    light("AREA", (-8, 6, 5), (math.radians(80), 0, math.radians(-150)), 7000, (0.2, 0.7, 1.0), size=5)
    light("POINT", (-2, -3, 3.5), (0, 0, 0), 1200, (1.0, 0.65, 0.3))
    for (x, y, c) in ((-14, 14, (1.0, 0.25, 0.1)), (4, 20, (0.2, 0.8, 1.0)), (20, 10, (1.0, 0.7, 0.2)), (-24, 6, (0.9, 0.2, 0.8))):   # far neon, bokeh through the fog
        me = bpy.data.meshes.new("N")
        me.from_pydata([(x - 1.2, y, 6), (x + 1.2, y, 6), (x + 1.2, y, 10), (x - 1.2, y, 10)], [], [(0, 1, 2, 3)])
        ob = bpy.data.objects.new("N", me)
        sc.collection.objects.link(ob)
        m = bpy.data.materials.new("Neon")
        m.use_nodes = True
        e = m.node_tree.nodes["Principled BSDF"]
        e.inputs["Emission Color"].default_value = (*c, 1)
        e.inputs["Emission Strength"].default_value = 40.0
        ob.data.materials.append(m)
    sc.render.filepath = path[:-4] + ".png"
    bpy.ops.render.render(write_still=True)
    Image.open(path[:-4] + ".png").convert("RGB").save(path, quality=88, optimize=True)
    os.remove(path[:-4] + ".png")
    return path


def previews(lib, out, only=None):
    os.makedirs(out, exist_ok=True)
    N = lambda cat, cls=None: {a.name for a in lib if a.category == cat and (cls is None or a.size_class == cls)}
    sheets = [("sheet_concrete_S.jpg", N("Shard_Concrete", "S"), "Shard_Concrete_S (0.25-0.6 m)"),
              ("sheet_concrete_M.jpg", N("Shard_Concrete", "M"), "Shard_Concrete_M (0.6-1.5 m)"),
              ("sheet_concrete_L.jpg", N("Shard_Concrete", "L"), "Shard_Concrete_L (1.5-4 m)"),
              ("sheet_concrete_XL.jpg", N("Shard_Concrete", "XL"), "Shard_Concrete_XL (4-10 m)"),
              ("sheet_structure.jpg", N("Slab_Concrete") | N("Column_Broken") | N("Rebar_Bundle") | N("Rebar_Single"), "slabs, columns, rebar"),
              ("sheet_facade_panels.jpg", N("Panel_Facade_Torn"), "Panel_Facade_Torn S / M / L"),
              ("sheet_glass.jpg", N("Glass_Shard"), "Glass_Shard (2-40 cm)"),
              ("sheet_window_frames.jpg", N("Window_Frame_Broken"), "Window_Frame_Broken"),
              ("sheet_gravel.jpg", N("Pebble") | N("Gravel_Cluster"), "pebbles + gravel clusters"),
              ("sheet_metal.jpg", N("Steel_Plate_Bent") | N("Girder_Twisted") | N("Pipe_Broken") | N("Cable_Dangling") | N("AC_Unit_Broken") | N("Sign_Torn"), "steel, girders, pipes, cables, AC, signs")]
    for fn, names, title in sheets:
        if only and fn not in only:
            continue
        render_sheet(lib, names, os.path.join(out, fn), title)
        print("rendered", fn)
    if not only or "scene_rubble_pile.jpg" in only:
        render_pile(lib, os.path.join(out, "scene_rubble_pile.jpg"))
        print("rendered pile")


def verify_exports(lib, out):
    """Re-imports every FBX and the GLB into a clean scene and compares object names, triangle counts and sizes with the manifest. Returns a list of problems."""
    probs = []
    expect = {a.name: a for a in lib}
    seen = {}
    for grp in builders.GROUPS:
        blend.reset()
        bpy.ops.import_scene.fbx(filepath=os.path.join(out, "Shards_%s.fbx" % grp))
        for o in bpy.data.objects:
            if o.type != "MESH":
                continue
            base = o.name.split(".")[0] if o.name not in expect and not o.name.startswith("UCX_") else o.name
            if base.startswith("UCX_"):
                src = base[4:-3]
                if src not in expect or expect[src].ucx is None:
                    probs.append("%s: unexpected UCX %s" % (grp, base))
                continue
            if base not in expect:
                probs.append("%s: unknown object %s" % (grp, o.name))
                continue
            a = expect[base]
            tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
            if tris != a.mesh.tris():
                probs.append("%s: %d triangles after import, expected %d" % (base, tris, a.mesh.tris()))
            dim = sorted(o.dimensions)
            ref = sorted(a.mesh.v.max(axis=0) - a.mesh.v.min(axis=0))
            if max(abs(x - y) for x, y in zip(dim, ref)) > 1e-3 + 0.01 * max(ref):
                probs.append("%s: size %s != %s" % (base, [round(x, 3) for x in dim], [round(x, 3) for x in ref]))
            if len(o.material_slots) != len(set(a.mesh.mats)) and len(o.material_slots) != len(a.mesh.mats):
                probs.append("%s: %d material slots" % (base, len(o.material_slots)))
            seen[base] = seen.get(base, 0) + 1
    for n in expect:
        if seen.get(n, 0) != 1:
            probs.append("%s exported %d times" % (n, seen.get(n, 0)))
    blend.reset()
    bpy.ops.import_scene.gltf(filepath=os.path.join(out, "Shards_All.glb"))
    n_glb = sum(1 for o in bpy.data.objects if o.type == "MESH")
    if n_glb != len(expect):
        probs.append("GLB holds %d meshes, expected %d" % (n_glb, len(expect)))
    return probs

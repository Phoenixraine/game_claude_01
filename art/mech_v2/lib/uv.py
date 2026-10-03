"""UV atlases: one 0..1 atlas PER MATERIAL shared by all parts (so the 8 PBR sets T_BASTION_<mat>_* map the whole mech), uniform texel density.

Per material: all its polygons of all parts are copied into one temporary mesh (connectivity preserved), smart-projected, island scales
averaged and packed by Blender's packer (rotation allowed); the UVs are copied back into each part's single UV map. Finally the atlases are
scaled to ONE common texel density (the tightest atlas sets it)."""
import math

import bpy
import bmesh
import numpy as np

from . import hs

UV_NAME = "UVMap"


def _poly_mat_names(obj):
    names = [s.material.name for s in obj.material_slots]
    return np.array([names[p.material_index] for p in obj.data.polygons], dtype=object)


TAG_STRIP = 0.025   # the top strip of every atlas (y in 1-TAG_STRIP..1) holds the shared UVs of bolts and hidden undersides


def _tags(obj):
    a = obj.data.attributes.get("tag")
    if a is None:
        return np.zeros(len(obj.data.polygons), dtype=np.int32)
    out = np.zeros(len(obj.data.polygons), dtype=np.int32)
    a.data.foreach_get("value", out)
    return out


def _shared_uv(obj, poly, tag):
    """Collapsed/shared UVs for tagged faces: planar projection of the polygon normalised into a fixed tile of the top strip.
    Bolt heads (tag 1) share one tile (they overlap by design, painted as plain bolt metal); hidden undersides (tag 2) share another."""
    me = obj.data
    pts = [np.array(me.vertices[vi].co) for vi in poly.vertices]
    n = np.array(poly.normal)
    a = np.cross(n, [0, 0, 1.0] if abs(n[2]) < 0.9 else [1.0, 0, 0])
    a /= np.linalg.norm(a) + 1e-12
    b = np.cross(n, a)
    q = np.array([[p @ a, p @ b] for p in pts])
    lo, hi = q.min(0), q.max(0)
    q = (q - lo) / np.maximum(hi - lo, 1e-6)
    x0 = 0.01 if tag == 1 else 0.30
    return [(x0 + 0.25 * u_, 1.0 - TAG_STRIP + 0.001 + (TAG_STRIP - 0.002) * v_) for u_, v_ in q]


def unwrap_all(angle=66.0, margin=0.0007, parts=None, verbose=True):
    parts = parts if parts is not None else hs.REG.parts
    for obj in parts:
        if UV_NAME not in obj.data.uv_layers:
            obj.data.uv_layers.new(name=UV_NAME)
        obj.data.uv_layers.active = obj.data.uv_layers[UV_NAME]
    pm = [(obj, _poly_mat_names(obj), _tags(obj)) for obj in parts]
    density = {}
    for mat in hs.MATERIALS:
        bm = bmesh.new()
        index = []
        uvl = bm.loops.layers.uv.new(UV_NAME)
        for oi, (obj, names, tags) in enumerate(pm):
            sel = np.nonzero((names == mat) & (tags == 0))[0]
            if not len(sel):
                continue
            me = obj.data
            vmap = {}
            for pi in sel:
                poly = me.polygons[int(pi)]
                vs = []
                for vi in poly.vertices:
                    if vi not in vmap:
                        vmap[vi] = bm.verts.new(me.vertices[vi].co)
                    vs.append(vmap[vi])
                try:
                    bm.faces.new(vs)
                    index.append((oi, int(pi)))
                except ValueError:       # duplicate face: cannot happen for sane parts, keep the index list aligned
                    raise RuntimeError("duplicate face while building the atlas mesh for %s in %s" % (mat, obj.name))
        if not index:
            bm.free()
            continue
        me = bpy.data.meshes.new("ATLAS_" + mat)
        bm.to_mesh(me)
        bm.free()
        tmp = bpy.data.objects.new("ATLAS_" + mat, me)
        bpy.context.scene.collection.objects.link(tmp)
        for o in bpy.context.selected_objects:
            o.select_set(False)
        bpy.context.view_layer.objects.active = tmp
        tmp.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=0.0, scale_to_bounds=False)
        bpy.ops.uv.average_islands_scale()
        bpy.ops.uv.pack_islands(rotate=True, margin=margin, margin_method="SCALED")
        # keep the main atlas out of the strip reserved for tagged faces
        bpy.ops.object.mode_set(mode="OBJECT")
        uvd = me.uv_layers[UV_NAME].data
        for fi, poly in enumerate(me.polygons):
            oi, pi = index[fi]
            tgt = pm[oi][0].data
            tl = tgt.uv_layers[UV_NAME].data
            for k, li in enumerate(tgt.polygons[pi].loop_indices):
                tl[li].uv = (uvd[poly.loop_start + k].uv[0], uvd[poly.loop_start + k].uv[1] * (1.0 - TAG_STRIP))
        # density of this atlas: sqrt(UV area / 3D area)
        ua = a3 = 0.0
        for poly in me.polygons:
            pts = [np.array(uvd[li].uv) for li in poly.loop_indices]
            for k in range(1, len(pts) - 1):
                u, v = pts[k] - pts[0], pts[k + 1] - pts[0]
                ua += abs(u[0] * v[1] - u[1] * v[0]) * 0.5
            a3 += poly.area
        density[mat] = (math.sqrt(ua * (1.0 - TAG_STRIP) / a3), ua, a3)
        bpy.data.objects.remove(tmp)
        bpy.data.meshes.remove(me)
        if verbose:
            print("  atlas %-18s %6d polys, area %9.0f m2, uv fill %.2f, density %.5f" % (mat, len(index), a3, ua, density[mat][0]))
    target = min(d[0] for d in density.values())
    for obj, names, tags in pm:
        tl = obj.data.uv_layers[UV_NAME].data
        for pi, poly in enumerate(obj.data.polygons):
            if tags[pi]:
                for li, uvv in zip(poly.loop_indices, _shared_uv(obj, poly, int(tags[pi]))):
                    tl[li].uv = uvv
                continue
            k = target / density[names[pi]][0]
            if k != 1.0:
                for li in poly.loop_indices:
                    tl[li].uv = (tl[li].uv[0] * k, tl[li].uv[1] * k)
    return target, density


def uv_stats(obj):
    """(uv_area, 3D area, density = sqrt(uv_area/area)) of one object."""
    me = obj.data
    uv = me.uv_layers.active.data
    ua = a3 = 0.0
    for poly in me.polygons:
        pts = [np.array(uv[li].uv) for li in poly.loop_indices]
        for k in range(1, len(pts) - 1):
            u, v = pts[k] - pts[0], pts[k + 1] - pts[0]
            ua += abs(u[0] * v[1] - u[1] * v[0]) * 0.5
        a3 += poly.area
    return ua, a3, (math.sqrt(ua / a3) if a3 > 0 and ua > 0 else 0.0)


def overlap_fraction_polys(polys, probes=4, seed=3, names=None, report=None):
    """Share of triangles (sampled, max 6000) that have a probe point inside ANOTHER triangle; polys = list of UV point lists (same atlas)."""
    tris = []
    tname = []
    for pi, pts in enumerate(polys):
        for k in range(1, len(pts) - 1):
            tris.append([pts[0], pts[k], pts[k + 1]])
            tname.append(names[pi] if names else "")
    tris = np.array(tris, dtype=np.float64)
    T = len(tris)
    if T < 2:
        return 0.0
    # bucket grid: only compare triangles that share a cell
    cen = tris.mean(axis=1)
    mn, mx = tris.min(1), tris.max(1)
    G = 64
    cells = {}
    for t in range(T):
        x0, y0 = int(mn[t, 0] * G), int(mn[t, 1] * G)
        x1, y1 = int(mx[t, 0] * G), int(mx[t, 1] * G)
        for gx in range(max(x0, 0), min(x1, G - 1) + 1):
            for gy in range(max(y0, 0), min(y1, G - 1) + 1):
                cells.setdefault((gx, gy), []).append(t)
    rng = np.random.default_rng(seed)
    sample = rng.choice(T, size=min(T, 6000), replace=False)
    bad = 0
    for t in sample:
        a, b, c = tris[t]
        pts = [cen[t]] + [tris[t, k] * 0.7 + cen[t] * 0.3 for k in range(3)]
        cand = set()
        gx, gy = int(cen[t, 0] * G), int(cen[t, 1] * G)
        for q in cells.get((min(max(gx, 0), G - 1), min(max(gy, 0), G - 1)), []):
            cand.add(q)
        hit = False
        for q in cand:
            if q == t:
                continue
            A, B, C = tris[q]
            v0, v1 = B - A, C - A
            den = v0[0] * v1[1] - v1[0] * v0[1]
            if abs(den) < 1e-18:
                continue
            for p in pts[:probes]:
                v2 = p - A
                u_ = (v2[0] * v1[1] - v1[0] * v2[1]) / den
                w_ = (v0[0] * v2[1] - v2[0] * v0[1]) / den
                if u_ > 1e-6 and w_ > 1e-6 and u_ + w_ < 1 - 1e-6:
                    hit = True
                    break
            if hit:
                break
        bad += hit
        if hit and report is not None:
            report[tname[t]] = report.get(tname[t], 0) + 1
    return bad / len(sample)


def island_density_spread(parts):
    """Per-polygon texel density (sqrt(uv area / 3D area)) over all parts: returns (min, max) ignoring degenerate polys."""
    ds = []
    for obj in parts:
        me = obj.data
        uv = me.uv_layers.active.data
        tg = _tags(obj)
        for pi, poly in enumerate(me.polygons):
            if poly.area < 0.05 or tg[pi]:
                continue
            pts = [np.array(uv[li].uv) for li in poly.loop_indices]
            ua = 0.0
            for k in range(1, len(pts) - 1):
                u, v = pts[k] - pts[0], pts[k + 1] - pts[0]
                ua += abs(u[0] * v[1] - u[1] * v[0]) * 0.5
            if ua > 0:
                ds.append(math.sqrt(ua / poly.area))
    ds = np.array(ds)
    return float(np.percentile(ds, 2)), float(np.percentile(ds, 50)), float(np.percentile(ds, 98))

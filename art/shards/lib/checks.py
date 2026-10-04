"""Self-checks and the manifest of the shard library (pure numpy, no bpy)."""
import math

import numpy as np

from . import geom as g

MAX_TRIS_MESH = 1500
MAX_TRIS_TOTAL = 300000
CONCRETE_SIZE = {"S": (0.25, 0.60), "M": (0.60, 1.50), "L": (1.50, 4.00), "XL": (4.00, 10.0)}


def pca(mesh):
    """Principal axes of the vertex cloud (rows, longest first, right-handed) and the extents along them."""
    v = mesh.v - mesh.v.mean(axis=0)
    w, V = np.linalg.eigh(v.T @ v)
    ax = V[:, ::-1].T.copy()
    if np.linalg.det(ax) < 0:
        ax[2] *= -1
    proj = mesh.v @ ax.T
    ext = proj.max(axis=0) - proj.min(axis=0)
    return ax, ext


def uv_problems(mesh):
    out = []
    uv = mesh.uv
    if uv is None:
        return ["no UVs"]
    if not np.all(np.isfinite(uv)):
        out.append("non-finite UV")
    if uv.min() < -1e-6 or uv.max() > 1 + 1e-6:
        out.append("UV outside [0,1]: %.3f..%.3f" % (uv.min(), uv.max()))
    rects = list(mesh.uv_rects.items())
    for i in range(len(rects)):
        (a, (alo, ahi)) = rects[i]
        for j in range(i + 1, len(rects)):
            (b, (blo, bhi)) = rects[j]
            if ahi[0] > blo[0] + 1e-9 and bhi[0] > alo[0] + 1e-9 and ahi[1] > blo[1] + 1e-9 and bhi[1] > alo[1] + 1e-9:
                out.append("UV islands %d and %d overlap" % (a, b))
                break
    # every triangle inside its island rectangle
    for k in range(len(mesh.t)):
        lo, hi = mesh.uv_rects[int(mesh.isl[k])]
        p = mesh.uv[k]
        if p[:, 0].min() < lo[0] - 1e-6 or p[:, 0].max() > hi[0] + 1e-6 or p[:, 1].min() < lo[1] - 1e-6 or p[:, 1].max() > hi[1] + 1e-6:
            out.append("triangle %d leaves its UV island" % k)
            break
    return out


def check_library(lib):
    p = []
    names = [a.name for a in lib]
    if len(set(names)) != len(names):
        p.append("duplicate asset names")
    total = sum(a.mesh.tris() for a in lib)
    if total > MAX_TRIS_TOTAL:
        p.append("library %d triangles > %d" % (total, MAX_TRIS_TOTAL))
    for a in lib:
        m = a.mesh
        if m.tris() > MAX_TRIS_MESH:
            p.append("%s: %d triangles > %d" % (a.name, m.tris(), MAX_TRIS_MESH))
        if not np.all(np.isfinite(m.v)):
            p.append("%s: non-finite vertices" % a.name)
        if np.abs(m.v).max() > 20:
            p.append("%s: absurd size" % a.name)
        areas = np.linalg.norm(np.cross(m.v[m.t[:, 1]] - m.v[m.t[:, 0]], m.v[m.t[:, 2]] - m.v[m.t[:, 0]]), axis=1)
        keys = [tuple(sorted(x)) for x in m.t.tolist()]
        if len(set(keys)) != len(keys):
            p.append("%s: duplicate / back-to-back triangles" % a.name)
        if (areas < 1e-12).any():
            p.append("%s: %d degenerate triangles" % (a.name, int((areas < 1e-12).sum())))
        for e in uv_problems(m):
            p.append("%s: %s" % (a.name, e))
        if a.category == "Shard_Concrete":
            lo, hi = CONCRETE_SIZE[a.size_class]
            ext = pca(m)[1][0]
            lng = float((m.v.max(axis=0) - m.v.min(axis=0)).max())
            if not (lo * 0.9 <= lng <= hi * 1.25):
                p.append("%s: longest bbox side %.2f outside %.2f..%.2f" % (a.name, lng, lo, hi))
            if not (40 <= m.tris() <= 400):
                p.append("%s: %d triangles outside 40..400" % (a.name, m.tris()))
            if a.ucx is None:
                p.append("%s: no UCX" % a.name)
        if a.category == "Pebble" and not (20 <= m.tris() <= 60):
            p.append("%s: %d triangles outside 20..60" % (a.name, m.tris()))
        if a.category == "Gravel_Cluster" and not (30 <= a.extra["stones"] <= 80):
            p.append("%s: %d stones" % (a.name, a.extra["stones"]))
        if a.category == "Glass_Shard":
            lng = float((m.v.max(axis=0) - m.v.min(axis=0)).max())
            if not (0.015 <= lng <= 0.45):
                p.append("%s: glass size %.3f" % (a.name, lng))
        if np.linalg.norm(a.mesh.volume_centroid()[1]) > 0.35 * max(1e-6, float((m.v.max(axis=0) - m.v.min(axis=0)).max())) + 0.02:
            p.append("%s: pivot not at the centre of mass" % a.name)
    counts = {}
    for a in lib:
        counts[(a.category, a.size_class)] = counts.get((a.category, a.size_class), 0) + 1
    for cls in ("S", "M", "L", "XL"):
        if not (8 <= counts.get(("Shard_Concrete", cls), 0) <= 12):
            p.append("Shard_Concrete_%s has %d variants (need 8..12)" % (cls, counts.get(("Shard_Concrete", cls), 0)))
    if counts.get(("Pebble", ""), 0) != 30:
        p.append("need 30 pebbles")
    return p


def manifest(lib):
    entries = []
    for a in lib:
        m = a.mesh
        lo, hi = m.bbox()
        ax, ext = pca(m)
        rad = float(np.linalg.norm(m.v, axis=1).max())
        e = {"name": a.name, "category": a.category, "size_class": a.size_class, "group": a.group, "triangles": int(m.tris()), "vertices": int(len(m.v)),
             "bbox_min": [round(float(x), 4) for x in lo], "bbox_max": [round(float(x), 4) for x in hi], "size": [round(float(x), 4) for x in (hi - lo)],
             "radius": round(rad, 4), "mass_kg_hint": round(float(a.extra["mass_kg"]), 5), "volume_m3": round(float(a.extra["volume_m3"]), 5),
             "materials": [m.mats[i] for i in sorted(set(int(x) for x in m.m))], "uv_islands": len(m.uv_rects), "ucx": ("UCX_%s_00" % a.name) if a.ucx is not None else None,
             "pca_axes": [[round(float(x), 5) for x in row] for row in ax], "pca_extents": [round(float(x), 4) for x in ext]}
        if a.category == "Shard_Concrete":
            fs = [f for f in a.ucx.faces if f.tag == "old"]
            e["old_face_normal"] = [round(float(x), 5) for x in fs[0].normal()] if fs else None
        entries.append(e)
    groups = {}
    for e in entries:
        groups.setdefault(e["group"], []).append(e["name"])
    return {"version": 1, "units": "metres (1 uu = 1 m), +Z up, right-handed (Blender); FBX exported with -Y forward / +Z up", "materials": ["M_Concrete_Old", "M_Fracture", "M_Glass_Shard", "M_Steel_Rust", "M_Rebar", "M_Gravel"],
            "pivot": "centre of mass", "triangles_total": int(sum(e["triangles"] for e in entries)), "groups": {k: "out/Shards_%s.fbx" % k for k in groups}, "glb": "out/Shards_All.glb", "assets": entries}

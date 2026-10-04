"""Fracture patterns for a 1x1x1 cuboid (centred at the origin, +Z up, the facade faces -Y): 3D Voronoi, radial impact, layered "pancake" floors, diagonal cuts.
Own implementation (convex cells by half-space clipping), no add-ons. Each cell is then mapped to a shard of the library (`shards_manifest.json`) by
principal-axis matching: the output lists, per fragment, the library name, position, orientation (quaternion x,y,z,w), and the scale that stretches the shard's
own extents to the cell's extents (in unit-cube coordinates)."""
import json
import math
import os

import numpy as np

from . import geom as g
from .geom import Solid, box_solid, clip_solid, rng_for, unit

CUBE = 1.0
FACE_NAMES = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}


def cube():
    s = box_solid((1, 1, 1), mat="M_Fracture")
    for f in s.faces:
        f.mat = "outer"
    return s


def voronoi_cells(points, weights=None):
    """Convex Voronoi cells of `points` inside the unit cube (weights stretch the metric per axis for anisotropic patterns)."""
    pts = [np.asarray(p, float) for p in points]
    w = np.ones(3) if weights is None else np.asarray(weights, float)
    cells = []
    for i, p in enumerate(pts):
        s = cube()
        order = sorted(range(len(pts)), key=lambda j: float(np.sum(((pts[j] - p) * w) ** 2)))
        for j in order:
            if j == i:
                continue
            q = pts[j]
            n = (q - p) * w * w
            if np.linalg.norm(n) < 1e-9:
                continue
            nn = unit(n)
            d = float(np.dot(nn, (p + q) / 2.0))
            # skip planes that cannot touch the current cell (cheap cull)
            vs = s.verts()
            if float((vs @ nn).max()) <= d + 1e-9:
                continue
            res = clip_solid(s, nn, d, cap_mat="fracture", cap_tag="cut")
            if res is None:
                s = None
                break
            s = res
        if s is not None and s.volume() > 1e-6:
            cells.append(s)
    return cells


def lloyd(points, iters, w=None):
    pts = [np.asarray(p, float) for p in points]
    for _ in range(iters):
        cells = voronoi_cells(pts, w)
        if len(cells) != len(pts):
            break
        pts = [np.clip(c.centroid(), -0.45, 0.45) for c in cells]
    return pts


def _uniform(r, n, lo=-0.5, hi=0.5):
    return [np.array([r.uniform(lo, hi), r.uniform(lo, hi), r.uniform(lo, hi)]) for _ in range(n)]


def pat_voronoi(r, n, relax):
    return lloyd(_uniform(r, n), relax)


def pat_radial(r, hit, rings, per_ring, depth_decay):
    """Seeds on rings around the impact point on the -Y face, deeper rings further inside: radial cracks + concentric rim."""
    pts = [np.array([hit[0], -0.5 + 0.06, hit[1]])]
    for k in range(1, rings + 1):
        rad = 0.11 * k ** 1.15
        n = per_ring + 2 * k
        ph = r.uniform(0, 2 * math.pi)
        for j in range(n):
            a = ph + 2 * math.pi * (j + r.uniform(-0.2, 0.2)) / n
            x, z = hit[0] + math.cos(a) * rad, hit[1] + math.sin(a) * rad
            y = -0.5 + 0.06 + depth_decay * k * 0.12 + r.uniform(-0.04, 0.04)
            pts.append(np.array([max(-0.49, min(0.49, x)), max(-0.5, min(0.3, y)), max(-0.49, min(0.49, z))]))
    for _ in range(max(3, 6 - rings)):              # a few big far chunks behind
        pts.append(np.array([r.uniform(-0.4, 0.4), r.uniform(0.0, 0.45), r.uniform(-0.4, 0.4)]))
    return pts


def pat_layers(r, layers, per_layer, jitter):
    """Floors: horizontal slabs of random thickness, each split in-plane by a few seeds (pancake collapse)."""
    th = [r.uniform(0.7, 1.3) for _ in range(layers)]
    tot = sum(th)
    z = -0.5
    pts = []
    for t in th:
        h = t / tot
        zc = z + h / 2
        for _ in range(per_layer):
            pts.append(np.array([r.uniform(-0.45, 0.45), r.uniform(-0.45, 0.45), zc + r.uniform(-jitter, jitter) * h]))
        z += h
    return pts


def diag_cells(r, ang_deg, spacing1, spacing2, cross_deg):
    """Two families of parallel planes (diagonal bands cut across): axis-aligned stripes in a rotated frame."""
    cells = [cube()]
    for fam, (deg, sp) in enumerate(((ang_deg, spacing1), (ang_deg + cross_deg, spacing2))):
        a = math.radians(deg)
        n = unit([math.cos(a), r.uniform(-0.15, 0.15), math.sin(a)])
        k0 = r.uniform(0, sp)
        offs = [k0 - 0.9 + sp * i + r.uniform(-0.08, 0.08) * sp for i in range(int(2.0 / sp) + 2)]
        out = []
        for c in cells:
            vs = c.verts()
            proj = vs @ n
            pieces = [c]
            for o in offs:
                nxt = []
                for p in pieces:
                    pv = p.verts() @ n
                    if pv.min() >= o - 1e-9 or pv.max() <= o + 1e-9:
                        nxt.append(p)
                        continue
                    a_ = clip_solid(p, n, o, cap_mat="fracture", cap_tag="cut")
                    b_ = clip_solid(p, -n, -o, cap_mat="fracture", cap_tag="cut")
                    for q in (a_, b_):
                        if q is not None and q.volume() > 1e-6:
                            nxt.append(q)
                pieces = nxt
            out += pieces
        cells = out
    return cells


PATTERNS = []


def _define():
    P = PATTERNS
    P.append(("voronoi_08", "voronoi", lambda r: voronoi_cells(pat_voronoi(r, 8, 1))))
    P.append(("voronoi_12", "voronoi", lambda r: voronoi_cells(pat_voronoi(r, 12, 1))))
    P.append(("voronoi_16", "voronoi", lambda r: voronoi_cells(pat_voronoi(r, 16, 2))))
    P.append(("voronoi_24", "voronoi", lambda r: voronoi_cells(pat_voronoi(r, 24, 1))))
    P.append(("voronoi_32_relaxed", "voronoi", lambda r: voronoi_cells(pat_voronoi(r, 32, 3))))
    P.append(("voronoi_40_raw", "voronoi", lambda r: voronoi_cells(pat_voronoi(r, 40, 0))))
    P.append(("radial_center", "radial_impact", lambda r: voronoi_cells(pat_radial(r, (0.0, 0.0), 3, 5, 1.0))))
    P.append(("radial_offset", "radial_impact", lambda r: voronoi_cells(pat_radial(r, (0.22, 0.12), 3, 5, 1.0))))
    P.append(("radial_low", "radial_impact", lambda r: voronoi_cells(pat_radial(r, (-0.1, -0.28), 3, 4, 1.4))))
    P.append(("radial_wide", "radial_impact", lambda r: voronoi_cells(pat_radial(r, (0.0, 0.1), 4, 4, 0.7))))
    P.append(("layers_3", "layered", lambda r: voronoi_cells(pat_layers(r, 3, 3, 0.25), (1.0, 1.0, 3.0))))
    P.append(("layers_4", "layered", lambda r: voronoi_cells(pat_layers(r, 4, 4, 0.2), (1.0, 1.0, 3.0))))
    P.append(("layers_5", "layered", lambda r: voronoi_cells(pat_layers(r, 5, 3, 0.15), (1.0, 1.0, 4.0))))
    P.append(("layers_6_fine", "layered", lambda r: voronoi_cells(pat_layers(r, 6, 5, 0.1), (1.0, 1.0, 4.0))))
    P.append(("diagonal_35", "diagonal", lambda r: diag_cells(r, 35, 0.45, 0.55, 80)))
    P.append(("diagonal_50", "diagonal", lambda r: diag_cells(r, 50, 0.38, 0.5, 70)))
    P.append(("diagonal_60_fine", "diagonal", lambda r: diag_cells(r, 60, 0.3, 0.42, 75)))
    P.append(("diagonal_20_shear", "diagonal", lambda r: diag_cells(r, 20, 0.5, 0.6, 85)))
    P.append(("columns_vertical", "voronoi", lambda r: voronoi_cells(pat_voronoi(r, 14, 1), (3.0, 3.0, 1.0))))
    P.append(("beams_horizontal", "voronoi", lambda r: voronoi_cells(pat_voronoi(r, 14, 1), (1.0, 3.0, 3.0))))


_define()
assert len(PATTERNS) == 20


# ------------------------------------------------------------------------------------------------------------------ mapping to the library
def _pca_of(verts):
    c = verts.mean(axis=0)
    v = verts - c
    w, V = np.linalg.eigh(v.T @ v)
    ax = V[:, ::-1].T.copy()
    if np.linalg.det(ax) < 0:
        ax[2] *= -1
    proj = verts @ ax.T
    ext = proj.max(axis=0) - proj.min(axis=0)
    return c, ax, np.maximum(ext, 1e-4)


def _mat_to_quat(R):
    m = R
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, 0.25 * s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] - m[1, 2]) / s]
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s, (m[0, 2] - m[2, 0]) / s]
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s, (m[1, 0] - m[0, 1]) / s]
    n = math.sqrt(sum(x * x for x in q))
    return [x / n for x in q]


def quat_to_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def outer_normals(cell):
    out = []
    for f in cell.faces:
        if f.mat == "outer":
            out.append(f.normal())
    return out


def size_class_for(diam_m):
    return "S" if diam_m < 0.6 else "M" if diam_m < 1.5 else "L" if diam_m < 4.0 else "XL"


def map_to_library(cells, manifest, r, cube_size_m):
    """Chooses a Shard_Concrete_* for every cell. `cube_size_m` is the metric size that a unit cube stands for (decides the size class of each fragment);
    among the shards of that class the one with the closest aspect ratio wins (variety penalty: a shard already used n times costs +0.06 n)."""
    shards = [a for a in manifest["assets"] if a["category"] == "Shard_Concrete"]
    used = {}
    frags = []
    for ci, cell in enumerate(cells):
        verts = cell.verts()
        cen, ax_c, ext_c = _pca_of(verts)
        diam = float(ext_c[0]) * cube_size_m
        cls = size_class_for(diam)
        pool = [s for s in shards if s["size_class"] == cls] or shards
        asp_c = np.array([ext_c[1] / ext_c[0], ext_c[2] / ext_c[0]])
        best = None
        for s in pool:
            e = np.array(s["pca_extents"])
            asp_s = np.array([e[1] / e[0], e[2] / e[0]])
            cost = float(np.abs(np.log(asp_c / asp_s)).sum()) + 0.06 * used.get(s["name"], 0) + 0.001 * r.random()
            if best is None or cost < best[0]:
                best = (cost, s)
        s = best[1]
        used[s["name"]] = used.get(s["name"], 0) + 1
        ax_s = np.array(s["pca_axes"])
        # candidate proper rotations: the 4 sign combinations of the principal axes; prefer the one that turns the shard's "old" face outwards
        outs = outer_normals(cell)
        old = np.array(s["old_face_normal"]) if s.get("old_face_normal") else None
        cands = []
        for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            S = np.diag([sx, sy, sx * sy])
            R = ax_c.T @ S @ ax_s
            score = 0.0
            if old is not None and outs:
                score = max(float(np.dot(R @ old, o)) for o in outs)
            cands.append((score, R))
        R = max(cands, key=lambda c: c[0])[1]
        ext_s = np.array(s["pca_extents"])
        scale = (ext_c / ext_s)
        frags.append({"index": ci, "lib": s["name"], "pos": [round(float(x), 5) for x in cen], "quat": [round(x, 6) for x in _mat_to_quat(R)],
                      "scale": [round(float(x), 5) for x in scale], "extents": [round(float(x), 5) for x in ext_c], "volume": round(float(cell.volume()), 6),
                      "outer_faces": sorted({k for f in cell.faces if f.mat == "outer" for k, v in FACE_NAMES.items() if np.allclose(f.normal(), v, atol=1e-6)})})
    return frags


def make_patterns(manifest, cube_size_m=6.0):
    out = []
    for i, (name, kind, fn) in enumerate(PATTERNS):
        r = rng_for("fracture", name)
        cells = fn(r)
        vol = sum(c.volume() for c in cells)
        frags = map_to_library(cells, manifest, rng_for("map", name), cube_size_m)
        out.append({"id": i, "name": name, "kind": kind, "fragments": len(frags), "volume_sum": round(vol, 5), "cells": [_cell_json(c) for c in cells], "pieces": frags})
    return {"version": 1, "cube": {"size": [1, 1, 1], "centre": [0, 0, 0], "facade_face": "-y", "up": "+z"},
            "convention": "pos/quat/scale are in unit-cube coordinates. A fragment is the library mesh `lib` (pivot = its centre of mass, native size) rotated by quat (x,y,z,w, right-handed) "
                          "and scaled per LOCAL axis by `scale` (shard principal extents -> cell extents), then translated to pos; multiply pos and the extents by the building cell size.",
            "mapping_cube_size_m": cube_size_m, "patterns": out}


def _cell_json(c):
    """Cell geometry as vertices + polygons (indices) so the building mesh can be cut exactly instead of swapped for library shards."""
    verts = []
    key = {}
    polys = []
    for f in c.faces:
        idx = []
        for p in f.v:
            k = (round(float(p[0]) * 1e5), round(float(p[1]) * 1e5), round(float(p[2]) * 1e5))
            if k not in key:
                key[k] = len(verts)
                verts.append([round(float(x), 5) for x in p])
            idx.append(key[k])
        polys.append({"v": idx, "outer": f.mat == "outer"})
    return {"verts": verts, "polys": polys}

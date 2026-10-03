"""UV unwrap: per-object smart projection (angle-limited islands, no auto-cube), uniform island scale, overlap-free packing."""
import math

import bpy
import numpy as np

from . import hs


def unwrap_all(angle=66.0, margin=0.004):
    for obj in hs.REG.parts:
        for o in bpy.context.selected_objects:
            o.select_set(False)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        if not obj.data.uv_layers:
            obj.data.uv_layers.new(name="UVMap")
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, scale_to_bounds=False)
        bpy.ops.uv.average_islands_scale()
        bpy.ops.uv.pack_islands(rotate=False, margin=margin)
        bpy.ops.object.mode_set(mode="OBJECT")
        obj.select_set(False)


def uv_stats(obj):
    """(uv_area_fraction of 0..1 square, 3D area in m^2, texel_density index = sqrt(uv_area / area3d)) for one object."""
    me = obj.data
    uv = me.uv_layers.active.data
    ua = 0.0
    a3 = 0.0
    for poly in me.polygons:
        pts = [np.array(uv[li].uv) for li in poly.loop_indices]
        for k in range(1, len(pts) - 1):
            u = pts[k] - pts[0]
            v = pts[k + 1] - pts[0]
            ua += abs(u[0] * v[1] - u[1] * v[0]) * 0.5
        a3 += poly.area
    return ua, a3, (math.sqrt(ua / a3) if a3 > 0 and ua > 0 else 0.0)


def overlap_fraction(obj, probes=4):
    """Share of UV triangles that have a probe point (centroid and points near each corner) inside ANOTHER triangle."""
    me = obj.data
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    tris = np.array([[uv[li].uv[:] for li in t.loops] for t in me.loop_triangles], dtype=np.float64)
    T = len(tris)
    if T < 2:
        return 0.0
    cen = tris.mean(axis=1)
    pts = [cen] + [tris[:, k] * 0.7 + cen * 0.3 for k in range(3)]
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    bad = np.zeros(T, dtype=bool)
    v0 = b - a
    v1 = c - a
    d00 = (v0 * v0).sum(1)
    d01 = (v0 * v1).sum(1)
    d11 = (v1 * v1).sum(1)
    den = d00 * d11 - d01 * d01
    ok = np.abs(den) > 1e-18
    for p in pts[:probes]:
        for i0 in range(0, T, 512):
            P = p[i0:i0 + 512]
            v2 = P[:, None, :] - a[None]
            d20 = (v2 * v0[None]).sum(2)
            d21 = (v2 * v1[None]).sum(2)
            with np.errstate(divide="ignore", invalid="ignore"):
                u = (d11[None] * d20 - d01[None] * d21) / den[None]
                v = (d00[None] * d21 - d01[None] * d20) / den[None]
            inside = (u > 1e-6) & (v > 1e-6) & (u + v < 1 - 1e-6) & ok[None]
            idx = np.arange(i0, min(T, i0 + 512))
            inside[np.arange(len(idx)), idx] = False
            bad[i0:i0 + 512] |= inside.any(1)
    return float(bad.mean())


def equalize_density():
    """Give every object the SAME texel density (UV units per metre): scale each object's UVs toward (0,0) so that its density
    equals the smallest one (set by the largest object, which still fits 0..1). Islands stay inside 0..1 and overlap-free."""
    dens = {}
    for obj in hs.REG.parts:
        dens[obj.name] = uv_stats(obj)[2]
    target = min(d for d in dens.values() if d > 0)
    for obj in hs.REG.parts:
        k = target / dens[obj.name]
        for loop in obj.data.uv_layers.active.data:
            loop.uv = (loop.uv[0] * k, loop.uv[1] * k)
    return target

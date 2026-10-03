"""Tiny hard-surface kit on bmesh used by the procedural Blender models (cockpit, sword...).
Every vertex carries a material class (float attribute "cls"); finish() writes UV0 = local (x, y)/2+.5 and UV1 = (z/2+.5, cls) so the
Unreal materials can texture procedurally from the local position and the class. Units are whatever the caller uses (metres)."""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix, Euler


class B:
    """bmesh accumulator with per-vertex material class."""

    def __init__(self, name, mat_name="M_Generic"):
        self.name = name
        self.mat_name = mat_name
        self.bm = bmesh.new()
        self.cl = self.bm.verts.layers.float.new("cls")

    def _tag(self, verts, cls):
        for v in verts:
            v[self.cl] = float(cls)

    def box(self, loc, size, rot=(0, 0, 0), cls=0, bevel=0.006):
        M = Matrix.Translation(loc) @ Euler(rot, "XYZ").to_matrix().to_4x4() @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=M)
        vs = r["verts"]
        self._tag(vs, cls)
        if bevel > 0 and min(size) > bevel * 2.6:
            edges = list({e for v in vs for e in v.link_edges})
            bmesh.ops.bevel(self.bm, geom=edges, offset=min(bevel, min(size) * 0.3), offset_type="OFFSET", segments=1, affect="EDGES")
        return vs

    def cyl(self, p0, p1, r0, r1=None, cls=0, seg=18, caps=True):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        L = d.length
        if L < 1e-6:
            return []
        q = Vector((0, 0, 1)).rotation_difference(d.normalized())
        M = Matrix.Translation((p0 + p1) / 2) @ q.to_matrix().to_4x4()
        r = bmesh.ops.create_cone(self.bm, cap_ends=caps, cap_tris=False, segments=seg, radius1=r0, radius2=(r0 if r1 is None else r1), depth=L, matrix=M)
        self._tag(r["verts"], cls)
        return r["verts"]

    def sphere(self, c, r, cls=0, seg=12):
        M = Matrix.Translation(c)
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=seg, v_segments=max(6, seg // 2), radius=r, matrix=M)
        self._tag(res["verts"], cls)

    def pipe(self, pts, r, cls=0, collars=True):
        pts = [Vector(p) for p in pts]
        for a, b in zip(pts[:-1], pts[1:]):
            self.cyl(a, b, r, cls=cls, seg=12)
            if collars and (b - a).length > 0.3:
                n = int((b - a).length / 0.28)
                for k in range(1, n + 1):
                    c = a + (b - a) * (k / (n + 1))
                    self.cyl(c - (b - a).normalized() * 0.018, c + (b - a).normalized() * 0.018, r * 1.35, cls=1, seg=12)
        for p in pts[1:-1]:
            self.sphere(p, r * 1.02, cls=cls, seg=10)

    def finish(self, smooth_deg=38):
        bm = self.bm
        for e in bm.edges:
            if len(e.link_faces) == 2:
                e.smooth = e.calc_face_angle(0.0) < math.radians(smooth_deg)
        for f in bm.faces:
            f.smooth = True
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        # UVs: local position + class
        n = len(me.vertices)
        co = np.empty(n * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        cls = np.empty(n); me.attributes["cls"].data.foreach_get("value", cls)
        lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
        u0 = me.uv_layers.new(name="UV0"); u1 = me.uv_layers.new(name="UV1")
        u0.data.foreach_set("uv", (co[lv][:, :2] * 0.5 + 0.5).astype(np.float32).ravel())
        u1.data.foreach_set("uv", np.stack([co[lv][:, 2] * 0.5 + 0.5, cls[lv]], 1).astype(np.float32).ravel())
        mat = bpy.data.materials.new(self.mat_name); me.materials.append(mat)
        return ob



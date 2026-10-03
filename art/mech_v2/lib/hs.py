"""Hard-surface helpers for the BASTION-01 build (Blender 4/5 `bpy` + `bmesh`).

A `Part` collects geometry (boxes, cylinders, bolts, louvres ...) into one bmesh and is committed as ONE object that is
rigidly bound (weight 1.0) to ONE bone. Names follow the Unreal contract: Body_<bone>, Armor_<Zone>_<NN>, Inner_<Zone>_<NN>,
Joint_<bone>, Cable_<Zone>_<NN>.
"""
import math

import bpy  # noqa: F401  (must be imported before bmesh when running as a module)
import bmesh
from mathutils import Euler, Matrix, Vector

MATERIALS = ["M_Graphite", "M_CeramicGray", "M_DarkMetal", "M_Hydraulic", "M_AccentOrange", "M_Rubber", "M_Glass_Sensor",
             "M_Emissive_Status"]

# base colour, metallic, roughness, extra (name -> value) for the Principled BSDF; neutral PBR values, no baked wear
_MAT_DEF = {
    "M_Graphite": ((0.055, 0.058, 0.064), 0.85, 0.45, {}),
    "M_CeramicGray": ((0.30, 0.31, 0.32), 0.12, 0.62, {}),
    "M_DarkMetal": ((0.025, 0.026, 0.03), 0.95, 0.38, {}),
    "M_Hydraulic": ((0.62, 0.64, 0.66), 1.0, 0.18, {}),
    "M_AccentOrange": ((0.85, 0.28, 0.03), 0.1, 0.5, {}),
    "M_Rubber": ((0.012, 0.012, 0.013), 0.0, 0.85, {}),
    "M_Glass_Sensor": ((0.02, 0.05, 0.08), 0.0, 0.05, {"Transmission Weight": 0.6, "IOR": 1.45}),
    "M_Emissive_Status": ((0.9, 0.45, 0.1), 0.0, 0.4, {"Emission Strength": 3.0}),
}


class Registry:
    """Everything created by a build: object metadata for `BASTION_01_parts.json` and the contract checker."""

    def __init__(self):
        self.parts = []
        self.variants = []
        self.counters = {}
        self.materials = {}
        self.armature = None
        self.collection = None

    def next_index(self, prefix):
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return self.counters[prefix]


REG = Registry()


def reset():
    global REG
    bpy.ops.wm.read_factory_settings(use_empty=True)
    REG = Registry()
    REG.collection = bpy.data.collections.new("BASTION_01")
    bpy.context.scene.collection.children.link(REG.collection)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    make_materials()
    return REG


def make_materials():
    for name in MATERIALS:
        col, met, rough, extra = _MAT_DEF[name]
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*col, 1.0)
        b.inputs["Metallic"].default_value = met
        b.inputs["Roughness"].default_value = rough
        for k, v in extra.items():
            if k in b.inputs:
                b.inputs[k].default_value = v
        if name == "M_Emissive_Status":
            b.inputs["Emission Color"].default_value = (*col, 1.0)
        m.diffuse_color = (*col, 1.0)
        REG.materials[name] = m


# ------------------------------------------------------------------------------------------------ primitives
def _xf(rot, loc):
    return Matrix.Translation(Vector(loc)) @ Euler(tuple(math.radians(a) for a in rot), "XYZ").to_matrix().to_4x4()


class Part:
    """Geometry accumulator; commit() turns it into a Blender object."""

    def __init__(self, name, bone, zone, kind, mat="M_Graphite"):
        self.name, self.bone, self.zone, self.kind = name, bone, zone, kind
        self.bm = bmesh.new()
        self.bm.faces.layers.int.new("tag")
        self.mat = mat
        self.mat_by_face = []   # (face index set marker) handled through face.material_index
        self._mats = [mat]

    # --- material slots (a part may mix materials; slot order = first use)
    def _mi(self, mat):
        if mat not in self._mats:
            self._mats.append(mat)
        return self._mats.index(mat)

    def _finish_prim(self, res_faces, mat, rot, loc):
        mi = self._mi(mat or self.mat)
        for f in res_faces:
            f.material_index = mi

    def box(self, size, loc=(0, 0, 0), rot=(0, 0, 0), bevel=0.0, taper=(1.0, 1.0), top_shift=(0.0, 0.0), mat=None, seg=1,
            chamfer=0.0, chamfer_axis="z"):
        """Cuboid of `size` (x,y,z) centred at loc. `taper` scales the top face in (x,y); `top_shift` slides it.
        `chamfer` cuts the 4 edges parallel to `chamfer_axis` hard (octagonal outline); `bevel` softens the remaining edges."""
        bm = self.bm
        before = set(bm.verts)
        bmesh.ops.create_cube(bm, size=1.0)
        verts = [v for v in bm.verts if v not in before]
        for v in verts:
            top = v.co.z > 0
            sx, sy = (taper if top else (1.0, 1.0))
            v.co = Vector((v.co.x * size[0] * sx + (top_shift[0] if top else 0), v.co.y * size[1] * sy + (top_shift[1] if top else 0),
                           v.co.z * size[2]))
        faces = list({f for v in verts for f in v.link_faces})
        ai = "xyz".index(chamfer_axis)

        def parallel(e):
            d = (e.verts[0].co - e.verts[1].co)
            return d.length > 1e-6 and abs(d[ai]) > 0.9 * d.length

        def run_bevel(edges, off):
            if not edges or off <= 0:
                return
            res = bmesh.ops.bevel(bm, geom=edges, offset=off, offset_type="OFFSET", segments=seg, profile=0.5, affect="EDGES")
            nonlocal faces, verts
            nf = {f for v in res["verts"] for f in v.link_faces} | {f for f in faces if f.is_valid}
            faces = [f for f in nf if f.is_valid]
            verts = list({v for f in faces for v in f.verts})

        dims = [abs(size[0]), abs(size[1]), abs(size[2])]
        perp = [dims[k] for k in range(3) if k != ai]
        if chamfer > 0:
            run_bevel([e for e in {e for v in verts for e in v.link_edges} if parallel(e)], min(chamfer, min(perp) * 0.45))
        if bevel > 0:
            edges = [e for e in {e for v in verts for e in v.link_edges} if e.is_valid and (chamfer <= 0 or not parallel(e))]
            run_bevel(edges, min(bevel, min(dims) * 0.45))
        bmesh.ops.transform(bm, matrix=_xf(rot, loc), verts=verts)
        self._finish_prim([f for f in faces if f.is_valid], mat, rot, loc)
        return self

    def cyl(self, radius, depth, loc=(0, 0, 0), axis="z", segs=16, bevel=0.0, r2=None, mat=None):
        """Cylinder/cone along `axis` ('x','y','z'), centred at loc."""
        bm = self.bm
        before = set(bm.verts)
        res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=radius, radius2=radius if r2 is None else r2,
                                    depth=depth)
        verts = [v for v in bm.verts if v not in before]
        faces = list({f for v in verts for f in v.link_faces})
        if bevel > 0:
            edges = [e for f in faces if len(f.verts) == segs for e in f.edges]
            rb = bmesh.ops.bevel(bm, geom=edges, offset=min(bevel, radius * 0.4), offset_type="OFFSET", segments=1, profile=0.5,
                                 affect="EDGES")
            faces = [f for f in {f for v in rb["verts"] for f in v.link_faces} | set(faces) if f.is_valid]
            verts = list({v for f in faces for v in f.verts})
        rot = {"z": (0, 0, 0), "x": (0, 90, 0), "y": (90, 0, 0)}[axis]
        bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(loc)) @ Euler(tuple(math.radians(a) for a in rot), "XYZ").to_matrix().to_4x4(),
                            verts=verts)
        self._finish_prim([f for f in faces if f.is_valid], mat, rot, loc)
        return self

    def bolts(self, centers, normal="y", radius=0.22, height=0.12, mat=None, segs=6):
        """Hex bolt heads at the given positions (flat discs standing on the surface along `normal` axis, sign allowed)."""
        sign = -1.0 if normal.startswith("-") else 1.0
        ax = normal.lstrip("+-")
        for c in centers:
            off = Vector((0, 0, 0))
            off["xyz".index(ax)] = sign * height * 0.5
            self.cyl(radius, height, loc=Vector(c) + off, axis=ax, segs=segs, mat=mat or "M_DarkMetal")
        return self

    def louvres(self, center, width, height, count, axis_n="y", depth=0.25, mat=None, slat=0.18):
        """Vent grille: `count` horizontal slats on the face whose normal is `axis_n` (e.g. '-y', '+x')."""
        sign = -1.0 if axis_n.startswith("-") else 1.0
        ax = axis_n.lstrip("-+")
        step = height / count
        for i in range(count):
            z = -height / 2 + step * (i + 0.5)
            if ax == "y":
                loc = (center[0], center[1] + sign * depth * 0.5, center[2] + z)
                size = (width, depth, slat)
            else:
                loc = (center[0] + sign * depth * 0.5, center[1], center[2] + z)
                size = (depth, width, slat)
            self.box(size, loc, mat=mat or "M_DarkMetal")
        return self

    def transform(self, rot, loc):
        """Rotate (degrees XYZ) then translate everything accumulated so far."""
        bmesh.ops.transform(self.bm, matrix=_xf(rot, loc), verts=list(self.bm.verts))
        return self

    def commit(self):
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        big = [f for f in bm.faces if len(f.verts) > 4]
        if big:
            bmesh.ops.triangulate(bm, faces=big)
        smooth_angle = getattr(self, "smooth_deg", 34.0)
        for f in bm.faces:
            f.smooth = True
        cos_t = math.cos(math.radians(smooth_angle))
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.link_faces[0].normal.dot(e.link_faces[1].normal) < cos_t:
                e.smooth = False
            elif len(e.link_faces) != 2:
                e.smooth = False
        mesh = bpy.data.meshes.new(self.name)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(self.name, mesh)
        REG.collection.objects.link(obj)
        for mn in self._mats:
            mesh.materials.append(REG.materials[mn])
        obj["bone"] = self.bone
        obj["zone"] = self.zone
        obj["kind"] = self.kind
        if getattr(self, "variant", False):
            REG.variants.append(obj)
            obj["variant"] = True
        else:
            REG.parts.append(obj)
        return obj


def _zone(zone):
    return zone


def body(bone, zone, mat="M_Graphite"):
    return Part("Body_%s" % bone, bone, zone, "body", mat)


def armor(zone, bone, mat="M_CeramicGray"):
    i = REG.next_index("Armor_" + zone)
    return Part("Armor_%s_%02d" % (zone, i), bone, zone, "armor", mat)


def inner(zone, bone, mat="M_DarkMetal"):
    i = REG.next_index("Inner_" + zone)
    return Part("Inner_%s_%02d" % (zone, i), bone, zone, "inner", mat)


def joint(bone, zone, mat="M_DarkMetal"):
    return Part("Joint_%s" % bone, bone, zone, "joint", mat)


def cable_curve(zone, bone, points, radius=0.18, mat="M_Rubber", res=6):
    """Hose/cable: a bevelled bezier-through-points curve converted to a mesh named Cable_<Zone>_<NN>."""
    i = REG.next_index("Cable_" + zone)
    name = "Cable_%s_%02d" % (zone, i)
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 2
    cu.use_fill_caps = True
    cu.resolution_u = res
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for p, co in zip(sp.bezier_points, points):
        p.co = co
        p.handle_left_type = p.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, cu)
    REG.collection.objects.link(obj)
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    bpy.data.objects.remove(obj)
    mesh.name = name
    mesh.materials.append(REG.materials[mat])
    o = bpy.data.objects.new(name, mesh)
    REG.collection.objects.link(o)
    o["bone"], o["zone"], o["kind"] = bone, zone, "cable"
    REG.parts.append(o)
    return o


def bake_transform(obj):
    """Move the object's location/rotation into its mesh (identity object transform): needed so skinning works in world space."""
    obj.data.transform(obj.matrix_basis)
    obj.matrix_basis = Matrix.Identity(4)

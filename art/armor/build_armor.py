"""blender -b -P build_armor.py -- <out_dir>
Armour shells for the mechs. Every piece is authored in metres around its own origin: +Z along the limb (length 1), +X pointing out of the body
(the face of the plate), Y across. The game scales them to the real limb and bolts them to the bones, so the plates follow the shape of the
body underneath (curved shells, stepped lames, ridges, spikes) instead of being flat slabs.
"""
import bpy, bmesh, math, sys, os
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)


def shell(name, radius_fn, thick, arc_deg, nu=14, nv=10, z0=-0.5, z1=0.5, ridge=0.0, ridge_w=0.18, edge_flare=0.0, centre_deg=0.0, cap_taper=0.0):
    """A curved panel: a sector of a tube whose radius varies along z. radius_fn(v in 0..1) -> radius (m). thickness in m."""
    bm = bmesh.new()
    grid_o, grid_i = [], []
    a0 = math.radians(centre_deg - arc_deg / 2)
    a1 = math.radians(centre_deg + arc_deg / 2)
    for j in range(nv + 1):
        v = j / nv
        z = z0 + (z1 - z0) * v
        r = radius_fn(v)
        ro, ri = [], []
        for i in range(nu + 1):
            u = i / nu
            a = a0 + (a1 - a0) * u
            # ridge down the centre of the plate and a flared lip at both ends
            c = (u - 0.5) * 2.0
            bump = ridge * math.exp(-(c / ridge_w) ** 2) if ridge else 0.0
            lip = edge_flare * (abs(c) ** 3)
            end = cap_taper * (v - 0.5) ** 2 * 4
            rr = r + bump - end
            ro.append(bm.verts.new((math.cos(a) * (rr + thick - lip), math.sin(a) * (rr + thick - lip), z)))
            ri.append(bm.verts.new((math.cos(a) * (r - lip * 0.5), math.sin(a) * (r - lip * 0.5), z)))
        grid_o.append(ro)
        grid_i.append(ri)
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((grid_o[j][i], grid_o[j][i + 1], grid_o[j + 1][i + 1], grid_o[j + 1][i]))
            bm.faces.new((grid_i[j][i + 1], grid_i[j][i], grid_i[j + 1][i], grid_i[j + 1][i + 1]))
    for i in range(nu):                                  # ends
        bm.faces.new((grid_o[0][i + 1], grid_o[0][i], grid_i[0][i], grid_i[0][i + 1]))
        bm.faces.new((grid_o[nv][i], grid_o[nv][i + 1], grid_i[nv][i + 1], grid_i[nv][i]))
    for j in range(nv):                                  # sides
        bm.faces.new((grid_o[j][0], grid_o[j + 1][0], grid_i[j + 1][0], grid_i[j][0]))
        bm.faces.new((grid_o[j + 1][nu], grid_o[j][nu], grid_i[j][nu], grid_i[j + 1][nu]))
    return bm


def merge(bms):
    out = bmesh.new()
    for b in bms:
        me = bpy.data.meshes.new("tmp")
        b.to_mesh(me)
        out.from_mesh(me)
        bpy.data.meshes.remove(me)
        b.free()
    return out


def xf(bm, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    M = Matrix.Translation(loc) @ Matrix.Rotation(rot[2], 4, "Z") @ Matrix.Rotation(rot[1], 4, "Y") @ Matrix.Rotation(rot[0], 4, "X") @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm


def box_bm(loc, size, rot=(0, 0, 0)):
    b = bmesh.new()
    bmesh.ops.create_cube(b, size=1.0)
    xf(b, loc, rot, size)
    return b


def spike_bm(base, tip, r):
    b = bmesh.new()
    d = Vector(tip) - Vector(base)
    L = d.length
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    M = Matrix.Translation((Vector(base) + Vector(tip)) / 2) @ q.to_matrix().to_4x4()
    bmesh.ops.create_cone(b, cap_ends=True, cap_tris=False, segments=8, radius1=r, radius2=0.0, depth=L, matrix=M)
    return b


def bevel_all(bm, off=0.012):
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(35)]
    if edges:
        bmesh.ops.bevel(bm, geom=edges, offset=off, offset_type="OFFSET", segments=1, affect="EDGES")


def finish(name, bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = False
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set("use_smooth", [False] * len(me.polygons))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    # UV: planar, so the procedural hull shader (world-position driven) has something sane
    me.uv_layers.new(name="UVMap")
    return ob


pieces = {}

# ---- limb guard (forearm / shin): 3 stepped lames + a front ridge + flared ends. radius 0.5, length 1 along z
def limb_guard(name, r0, r1, n_lames=3, arc=170.0, ridge=0.05):
    parts = []
    for k in range(n_lames):
        v0 = k / n_lames
        v1 = (k + 1) / n_lames + 0.06
        z0 = -0.5 + v0
        z1 = -0.5 + min(v1, 1.0)
        rf = lambda v, k=k, v0=v0, v1=v1: (r0 + (r1 - r0) * (v0 + (v1 - v0) * v)) + 0.02 * k
        parts.append(shell(name, rf, 0.035, arc, 12, 4, z0, z1, ridge=ridge, ridge_w=0.22, edge_flare=0.05))
    parts.append(box_bm((r0 + 0.07, 0, 0.0), (0.05, 0.06, 0.82)))                                  # spine ridge
    for sz in (-0.38, 0.38):
        parts.append(box_bm((r0 + 0.03, 0, sz), (0.06, 0.34, 0.05)))                                  # end trim
    bm = merge(parts)
    bevel_all(bm, 0.006)
    return finish(name, bm)


pieces["Armor_Bracer"] = limb_guard("Armor_Bracer", 0.46, 0.36, 3, 170.0, 0.05)
pieces["Armor_Shin"] = limb_guard("Armor_Shin", 0.5, 0.42, 4, 160.0, 0.06)
pieces["Armor_Thigh"] = limb_guard("Armor_Thigh", 0.52, 0.44, 3, 150.0, 0.07)

# ---- pauldron: dome of stepped lames with a rim and a spike
def pauldron():
    parts = []
    for k in range(4):
        rr = 0.5 - 0.075 * k
        zz = 0.1 + 0.2 * k
        parts.append(shell("p", lambda v, rr=rr: rr, 0.04, 220.0, 16, 3, zz - 0.09, zz + 0.12, ridge=0.025, ridge_w=0.3, edge_flare=0.06, centre_deg=0.0))
    # cap
    cap = bmesh.new()
    bmesh.ops.create_uvsphere(cap, u_segments=14, v_segments=8, radius=0.38)
    xf(cap, (0, 0, 0.78), (0, 0, 0), (1.0, 1.0, 0.55))
    parts.append(cap)
    parts.append(spike_bm((0.0, 0.0, 0.88), (0.12, 0.0, 1.45), 0.07))
    bm = merge(parts)
    bevel_all(bm, 0.008)
    return finish("Armor_Pauldron", bm)


pieces["Armor_Pauldron"] = pauldron()


# ---- chest: curved front shell with a keel, two pec plates and abdominal lames. z is up the body, x forward
def chest():
    parts = []
    parts.append(shell("c", lambda v: 0.9 - 0.18 * abs(v - 0.62) * 2, 0.06, 150.0, 24, 10, -0.5, 0.5, ridge=0.1, ridge_w=0.16, edge_flare=0.1))
    for sy in (-1, 1):
        parts.append(shell("pec", lambda v: 0.95, 0.045, 52.0, 8, 4, 0.0, 0.32, ridge=0.03, ridge_w=0.4, centre_deg=sy * 44.0))
    for k in range(4):
        parts.append(shell("ab", lambda v, k=k: 0.78 + 0.02 * k, 0.04, 110.0, 14, 2, -0.5 - 0.0 + k * 0.1, -0.5 + k * 0.1 + 0.12, ridge=0.025, ridge_w=0.3))
    parts.append(box_bm((0.98, 0, 0.12), (0.08, 0.22, 0.34)))                                       # core housing
    bm = merge(parts)
    bevel_all(bm, 0.008)
    return finish("Armor_Chest", bm)


pieces["Armor_Chest"] = chest()


def back():
    parts = [shell("b", lambda v: 0.92, 0.06, 130.0, 20, 8, -0.5, 0.5, ridge=0.05, ridge_w=0.4, edge_flare=0.08, centre_deg=180.0)]
    for sy in (-1, 1):
        parts.append(box_bm((-1.02, sy * 0.3, 0.1), (0.22, 0.2, 0.7)))                               # exhaust stacks
        parts.append(spike_bm((-1.1, sy * 0.3, 0.45), (-1.1, sy * 0.3, 0.8), 0.09))
    bm = merge(parts)
    bevel_all(bm, 0.008)
    return finish("Armor_Back", bm)


pieces["Armor_Back"] = back()


# ---- head: cheek plates and a crest
def head():
    parts = []
    for sy in (-1, 1):
        parts.append(shell("h", lambda v: 0.46, 0.05, 60.0, 8, 4, -0.3, 0.3, ridge=0.04, ridge_w=0.3, centre_deg=sy * 70.0))
        parts.append(spike_bm((0.0, sy * 0.46, 0.2), (-0.3, sy * 0.62, 0.62), 0.06))
    parts.append(box_bm((0.1, 0, 0.58), (0.7, 0.07, 0.22)))
    parts.append(box_bm((0.46, 0, 0.0), (0.06, 0.5, 0.1)))
    bm = merge(parts)
    bevel_all(bm, 0.008)
    return finish("Armor_Head", bm)


pieces["Armor_Head"] = head()


# ---- knee / elbow cap with a spike
def cap():
    parts = []
    s = bmesh.new()
    bmesh.ops.create_uvsphere(s, u_segments=12, v_segments=6, radius=0.5)
    xf(s, (0.1, 0, 0), (0, 0, 0), (0.7, 1.0, 0.8))
    parts.append(s)
    parts.append(spike_bm((0.4, 0, 0), (0.95, 0, 0), 0.12))
    parts.append(shell("kc", lambda v: 0.5, 0.04, 200.0, 12, 3, -0.2, 0.2, centre_deg=0.0, ridge=0.03))
    bm = merge(parts)
    bevel_all(bm, 0.01)
    return finish("Armor_Cap", bm)


pieces["Armor_Cap"] = cap()

# ---- pelvis skirt: front and side tassets
def skirt():
    parts = []
    for k, ang in enumerate((-70, -35, 0, 35, 70)):
        parts.append(shell("sk", lambda v: 0.55, 0.04, 28.0, 4, 6, -0.5, 0.5, ridge=0.02, ridge_w=0.4, centre_deg=ang, cap_taper=0.1))
    bm = merge(parts)
    bevel_all(bm, 0.006)
    return finish("Armor_Skirt", bm)


pieces["Armor_Skirt"] = skirt()

for name, ob in pieces.items():
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                             axis_forward="-Y", axis_up="Z", object_types={"MESH"}, mesh_smooth_type="FACE", bake_space_transform=False, path_mode="AUTO")
    print("EXPORTED", path, len(ob.data.polygons), "faces")

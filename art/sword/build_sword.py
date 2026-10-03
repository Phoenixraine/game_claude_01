"""blender -b -P build_sword.py -- <out_dir> [--preview]

The duel sword of the mechs (metres, mech scale: ~61 m overall, blade ~56 m). Authored along +X with the GRIP CENTRE at the origin:
handle x -4.5..4.0, crossguard x 4.0..5.4, blade x 5.4..61.0 (edge towards +Y, thickness along Z).
Material classes in UV1.y: 0 dark steel, 1 worn bright steel, 2 glowing edge, 3 grip rubber/cloth, 4 orange accent.
"""
import bpy, sys, os, math, random
import numpy as np
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from bmb import B

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
PREVIEW = "--preview" in argv
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
rr = random.Random(11)

S = B("SM_Sword", "M_Sword")
bm = S.bm

X0, X1 = 5.4, 61.0
stations = [  # x, half-width, thickness
    (5.4, 2.55, 1.35), (6.6, 2.75, 1.25), (12.0, 2.95, 1.12), (22.0, 3.05, 1.02), (34.0, 3.0, 0.95), (45.0, 2.8, 0.86),
    (52.0, 2.4, 0.74), (56.0, 1.75, 0.58), (59.0, 0.95, 0.34), (61.0, 0.0, 0.0),
]


def profile(x, h, t):
    hs = h * 0.88
    he = h * 1.12 + 0.12 * math.sin(math.pi * (x - X0) / (X1 - X0)) * 2.2
    return [(x, -hs, -t / 2), (x, -hs, t / 2), (x, he * 0.12, t * 0.43), (x, he, 0.0), (x, he * 0.12, -t * 0.43)], hs, he


rings = []
meta = []
for (x, h, t) in stations:
    pts, hs, he = profile(x, h, t)
    if h == 0.0:
        v = bm.verts.new((x, 0.0, 0.0))
        v[S.cl] = 0
        rings.append([v])
    else:
        rv = []
        for p in pts:
            v = bm.verts.new(p)
            v[S.cl] = 0
            rv.append(v)
        rings.append(rv)
    meta.append((x, hs, he, t))
# base cap
bm.faces.new(rings[0][::-1])
for i in range(len(rings) - 1):
    a, b = rings[i], rings[i + 1]
    if len(b) == 1:
        for k in range(5):
            bm.faces.new((a[k], a[(k + 1) % 5], b[0]))
    else:
        for k in range(5):
            bm.faces.new((a[k], a[(k + 1) % 5], b[(k + 1) % 5], b[k]))

# glow strips along both bevels of the edge (own vertices so the class does not blend)
def edge_pt(i, side, f):
    """point on the bevel between the shoulder (f=0) and the edge (f=1) of station i, side=+1 upper, -1 lower; slightly proud of the surface"""
    x, hs, he, t = meta[i]
    y0, z0 = he * 0.12, side * t * 0.43
    y1, z1 = he, 0.0
    y = y0 + (y1 - y0) * f
    z = z0 + (z1 - z0) * f
    return (x, y, z + side * 0.025)


for side in (1, -1):
    for i in range(len(meta) - 2):
        a0, a1 = edge_pt(i, side, 0.45), edge_pt(i, side, 0.97)
        b0, b1 = edge_pt(i + 1, side, 0.45), edge_pt(i + 1, side, 0.97)
        vs = [bm.verts.new(p) for p in (a0, a1, b1, b0)]
        for v in vs:
            v[S.cl] = 2
        bm.faces.new(vs if side > 0 else vs[::-1])
# fuller grooves (worn steel, raised slightly) on both faces
for side in (1, -1):
    S.box((26.0, -0.55, side * 0.5), (40.0, 0.55, 0.07), cls=1, bevel=0.02)
    S.box((26.0, 0.9, side * 0.46), (34.0, 0.3, 0.06), cls=1, bevel=0.02)
# serrated spine
for k in range(18):
    x = 9.0 + k * 2.4
    hs = np.interp(x, [m[0] for m in meta], [m[1] for m in meta])
    S.box((x, -hs - 0.18, 0.0), (1.0, 0.62, 0.62), rot=(math.radians(45), 0, 0), cls=0, bevel=0.03)
# ricasso block + guard
S.box((5.8, 0.0, 0.0), (1.4, 5.0, 1.7), cls=1, bevel=0.06)
S.box((4.7, 0.0, 0.0), (1.5, 2.6, 11.5), cls=0, bevel=0.1)
for sgn in (1, -1):
    S.box((4.7, 0.0, sgn * 6.2), (1.6, 2.2, 2.6), rot=(0, 0, sgn * math.radians(-12)), cls=0, bevel=0.08)
    S.box((5.1, -0.2, sgn * 7.7), (1.2, 1.6, 2.4), rot=(0, 0, sgn * math.radians(-26)), cls=1, bevel=0.06)
    S.box((4.1, 0.0, sgn * 3.2), (0.5, 2.0, 1.1), cls=4, bevel=0.03)
    S.box((6.0, 1.2, sgn * 2.0), (0.6, 1.3, 0.9), cls=2, bevel=0.03)
# handle
S.cyl((-4.5, 0, 0), (4.0, 0, 0), 0.5, 0.46, cls=3, seg=16)
for k in range(9):
    S.cyl((-4.2 + k * 0.95, 0, 0), (-3.8 + k * 0.95, 0, 0), 0.58, cls=0, seg=16)
for xx in (3.7, -4.4):
    S.cyl((xx, 0, 0), (xx + 0.4, 0, 0), 0.8, cls=4, seg=18)
S.sphere((-5.2, 0, 0), 0.95, cls=0, seg=14)
S.box((-5.5, 0, 0), (0.5, 0.9, 0.9), cls=2, bevel=0.04)
for k in range(4):
    S.box((-1.0 + k * 1.2, 0.55, 0.0), (0.5, 0.25, 0.3), cls=1, bevel=0.03)
ob = S.finish()

# shift: the grip centre is the origin already (handle spans x -4.5..4.0 -> centre -0.25); nudge by +0.25
ob.location = (0.0, 0.0, 0.0)
bpy.context.view_layer.objects.active = ob
bpy.ops.object.select_all(action="DESELECT")
ob.select_set(True)
path = os.path.join(OUT, "SM_Sword.fbx")
bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                         axis_forward="-Y", axis_up="Z", object_types={"MESH"}, mesh_smooth_type="EDGE", bake_space_transform=False, path_mode="AUTO")
print("EXPORTED", path, len(ob.data.polygons), "faces")

if PREVIEW:
    import mathutils
    sc = bpy.context.scene
    sc.view_settings.view_transform = "Standard"
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 700
    world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.04, 0.05, 0.07, 1)
    cols = {0: (0.05, 0.05, 0.06), 1: (0.4, 0.4, 0.42), 2: (1.0, 0.4, 0.05), 3: (0.02, 0.02, 0.02), 4: (0.7, 0.2, 0.02)}
    me = ob.data
    cls = np.empty(len(me.vertices)); me.attributes["cls"].data.foreach_get("value", cls)
    ca = me.color_attributes.new("PC", "FLOAT_COLOR", "POINT")
    ca.data.foreach_set("color", np.array([list(cols[int(c)]) + [1.0] for c in cls], np.float32).ravel())
    m = bpy.data.materials.new("P"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    vc = nt.nodes.new("ShaderNodeVertexColor"); vc.layer_name = "PC"
    nt.links.new(vc.outputs[0], b.inputs["Base Color"]); b.inputs["Metallic"].default_value = 0.8; b.inputs["Roughness"].default_value = 0.35
    nt.links.new(vc.outputs[0], b.inputs["Emission Color"]); b.inputs["Emission Strength"].default_value = 0.0
    me.materials.clear(); me.materials.append(m)
    for loc, e in (((30, -40, 40), 9000.0), ((30, 40, 20), 5000.0), ((-20, 0, -30), 2500.0)):
        bpy.ops.object.light_add(type="POINT", location=loc); L = bpy.context.object; L.data.energy = e
    cd = bpy.data.cameras.new("C"); cd.lens = 40
    cam = bpy.data.objects.new("C", cd); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (28, -62, 16); cam.rotation_euler = (mathutils.Vector((0, 62, -12)).to_track_quat("-Z", "Y").to_euler())
    sc.render.filepath = os.path.join(OUT, "preview_sword.png"); bpy.ops.render.render(write_still=True)
    cam.location = (10, -30, 6); cam.rotation_euler = (mathutils.Vector((0, 30, -4)).to_track_quat("-Z", "Y").to_euler())
    sc.render.filepath = os.path.join(OUT, "preview_sword_hilt.png"); bpy.ops.render.render(write_still=True)
    print("PREVIEW DONE")

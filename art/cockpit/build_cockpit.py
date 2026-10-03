"""blender -b -P build_cockpit.py -- <out_dir> [--preview]

Procedural hard-surface cockpit for the player mech, authored in pilot scale (metres) with the pilot's EYE at the origin.
Blender axes: +X forward, +Y left, +Z up (imports into Unreal as +X forward, +Y right, no mirroring).

Outputs (FBX, static meshes, pivots at the origin of each part):
  SM_Cockpit_Shell   window frame, dash, side walls, ceiling, floor, second seat, pipes, greebles
  SM_Cockpit_Glass   canopy + side panes (single surface; rain-on-glass material)
  SM_Rig_Upper / SM_Rig_Fore / SM_Rig_Glove   one arm rig (left); mirrored in the game. Built along +X from the pivot, length 0.55 each.
Every vertex carries its material class in UV1.y (see M_Cockpit): 0 dark metal, 1 painted grey, 2 orange paint, 3 rubber/fabric,
4 cyan display, 5 orange LED, 6 off display / black glass, 7 red LED. UV0 = (x, y) and UV1.x = z of the local position (m) for
procedural texturing.
"""
import bpy, bmesh, sys, math, random, os
import numpy as np
from mathutils import Vector, Matrix, Euler

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
PREVIEW = "--preview" in argv
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
rnd = random.Random(42)


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from bmb import B as _B


class B(_B):
    def __init__(self, name):
        super().__init__(name, "M_Cockpit")


def hat(b, loc, size, rot=(0, 0, 0), cls=1):
    """Panel = slab + raised inset + 4 bolts."""
    b.box(loc, size, rot, cls=cls, bevel=0.008)


def greeble_rect(b, origin, ux, vy, nrm, w, h, count, cls_choices=(0, 1, 0, 0, 5), hmax=0.03, seed=0):
    rr = random.Random(seed)
    ux, vy, nrm = Vector(ux).normalized(), Vector(vy).normalized(), Vector(nrm).normalized()
    for _ in range(count):
        u, v = rr.uniform(-w / 2, w / 2), rr.uniform(-h / 2, h / 2)
        sw, sh = rr.uniform(0.02, 0.09), rr.uniform(0.02, 0.07)
        t = rr.uniform(0.006, hmax)
        c = Vector(origin) + ux * u + vy * v + nrm * (t / 2)
        m = Matrix([ux, vy, nrm]).transposed()
        rot = m.to_euler()
        cls = rr.choice(cls_choices)
        b.box(c, (sw, sh, t), rot=tuple(rot), cls=cls, bevel=0.003)


# =============================================================================================================== SHELL
S = B("SM_Cockpit_Shell")
# dash console: a plate tilted toward the pilot (normal points up and back), instruments in its upper, visible half
TH = math.radians(-40.0)
DC = Vector((0.62, 0.0, -0.36))                                   # plate centre
DU = Vector((math.cos(-TH) * 1.0, 0.0, math.sin(-TH)))           # along the slope (rises with x)
DU = Vector((math.cos(TH), 0.0, -math.sin(TH)))
DV = Vector((0.0, 1.0, 0.0))                                      # across (Blender +Y = left)
DN = Vector((math.sin(TH), 0.0, math.cos(TH)))                    # plate normal (towards pilot and up)
DROT = (0.0, TH, 0.0)


def on_dash(u, v, n=0.0):
    return DC + DU * u + DV * v + DN * n


# body under the plate
S.box(DC - DN * 0.12, (0.52, 2.7, 0.10), rot=DROT, cls=0, bevel=0.02)
S.box(DC, (0.50, 2.5, 0.05), rot=DROT, cls=1, bevel=0.012)                       # face plate
S.box(on_dash(0.0, 0.0, 0.03), (0.46, 2.2, 0.016), rot=DROT, cls=0, bevel=0.004)   # inner recess
# main display with bezel
S.box(on_dash(0.12, 0.0, 0.04), (0.22, 0.50, 0.012), rot=DROT, cls=0, bevel=0.006)
S.box(on_dash(0.12, 0.0, 0.049), (0.18, 0.44, 0.006), rot=DROT, cls=4, bevel=0.0)
# side round gauges (cyan rings)
for sgn in (1, -1):
    for vv in (0.40, 0.66):
        S.cyl(on_dash(0.12, sgn * vv, 0.03), on_dash(0.12, sgn * vv, 0.06), 0.058, cls=0, seg=28)
        S.cyl(on_dash(0.12, sgn * vv, 0.06), on_dash(0.12, sgn * vv, 0.066), 0.047, cls=4, seg=28)
        S.cyl(on_dash(0.12, sgn * vv, 0.066), on_dash(0.12, sgn * vv, 0.07), 0.009, cls=5, seg=10)
    # button banks
    for i in range(4):
        for j in range(6):
            S.box(on_dash(0.03 + i * 0.05, sgn * (1.02 + j * 0.055), 0.04), (0.032, 0.034, 0.02), rot=DROT, cls=5 if (i + j) % 3 == 0 else 7 if (i * j) % 7 == 5 else 0, bevel=0.003)
    # shutter blocks (horizontal slats)
    for k in range(8):
        S.box(on_dash(0.19 - k * 0.0, sgn * 1.14, 0.045 + k * 0.0), (0.012, 0.24, 0.012), rot=DROT, cls=0, bevel=0.0)
    for k in range(8):
        S.box(on_dash(0.05 + k * 0.026, sgn * 0.20, 0.03) if False else on_dash(0.02 + k * 0.026, sgn * 0.30, 0.05), (0.01, 0.20, 0.014), rot=DROT, cls=0, bevel=0.0)
# warning strip and rail along the top edge of the plate
S.box(on_dash(0.235, 0.0, 0.03), (0.05, 2.4, 0.04), rot=DROT, cls=1, bevel=0.012)
S.box(on_dash(0.235, 0.0, 0.056), (0.016, 1.4, 0.01), rot=DROT, cls=5, bevel=0.002)
for i in range(18):
    S.box(on_dash(0.235, -1.0 + i * 0.118, 0.056), (0.016, 0.06, 0.012), rot=DROT, cls=7 if i % 5 == 2 else 0, bevel=0.002)
# dash greebles over the whole plate
for k in range(70):
    uu, vv = rnd.uniform(-0.2, 0.21), rnd.uniform(-1.18, 1.18)
    if abs(vv) < 0.30 and uu > 0.0:
        continue
    if 0.30 < abs(vv) < 0.75 and 0.03 < uu < 0.21:
        continue
    t = rnd.uniform(0.012, 0.045)
    S.box(on_dash(uu, vv, 0.025 + t / 2), (rnd.uniform(0.03, 0.10), rnd.uniform(0.03, 0.10), t), rot=DROT, cls=rnd.choice((0, 1, 0, 5)), bevel=0.004)
# lower dash front panel: vents + glowing strip
S.box((0.34, 0, -0.78), (0.12, 2.2, 0.22), cls=1, bevel=0.01)
S.box((0.275, 0, -0.745), (0.02, 1.2, 0.02), cls=5, bevel=0.002)
for i in range(12):
    S.box((0.28, -0.9 + i * 0.05, -0.82), (0.02, 0.025, 0.1), cls=0, bevel=0.002)
# window frame: header, pillars, lower sill
S.box((0.86, 0, 0.60), (0.34, 3.0, 0.16), rot=(0, math.radians(14), 0), cls=0, bevel=0.015)
S.box((0.92, 0, 0.545), (0.20, 2.6, 0.05), rot=(0, math.radians(14), 0), cls=1, bevel=0.01)
S.box((0.95, 0, 0.51), (0.12, 2.2, 0.02), rot=(0, math.radians(14), 0), cls=5, bevel=0.002)
for sgn in (1, -1):
    S.box((0.80, sgn * 1.30, 0.12), (0.26, 0.22, 1.50), rot=(sgn * math.radians(-14), 0, sgn * math.radians(10)), cls=0, bevel=0.02)
    S.box((0.84, sgn * 1.20, 0.10), (0.10, 0.10, 1.35), rot=(sgn * math.radians(-12), 0, sgn * math.radians(9)), cls=2, bevel=0.01)
    S.box((0.78, sgn * 1.46, 0.0), (0.4, 0.2, 1.7), rot=(0, 0, sgn * math.radians(24)), cls=1, bevel=0.02)
    # mid mullions
    S.box((0.93, sgn * 0.62, 0.05), (0.07, 0.05, 1.0), cls=0, bevel=0.006)
    S.box((0.93, sgn * 0.62, 0.05), (0.05, 0.07, 0.96), cls=1, bevel=0.003)
# ceiling
S.box((0.0, 0, 0.84), (1.9, 3.1, 0.10), cls=0, bevel=0.02)
S.box((0.28, 0, 0.775), (1.2, 1.5, 0.05), cls=1, bevel=0.01)
for i in range(4):
    for j in range(9):
        S.box((0.0 + i * 0.1, -0.5 + j * 0.125, 0.745), (0.04, 0.05, 0.02), cls=5 if (i * 3 + j) % 7 == 0 else 7 if (i + j) % 11 == 0 else 0, bevel=0.004)
greeble_rect(S, (0.3, 0.0, 0.752), (0, 1, 0), (1, 0, 0), (0, 0, -1), 1.5, 1.0, 40, seed=3)
# side walls with their own windows (frames only)
for sgn in (1, -1):
    S.box((0.15, sgn * 1.66, -0.1), (1.9, 0.12, 1.6), rot=(0, 0, 0), cls=0, bevel=0.02)
    S.box((0.35, sgn * 1.58, 0.25), (1.2, 0.08, 0.7), cls=6, bevel=0.01)            # dark panel (side window sits in front)
    S.box((0.35, sgn * 1.56, 0.62), (1.3, 0.14, 0.12), cls=1, bevel=0.01)
    S.box((0.35, sgn * 1.56, -0.12), (1.3, 0.14, 0.12), cls=1, bevel=0.01)
    S.box((-0.30, sgn * 1.56, 0.25), (0.14, 0.14, 0.9), cls=2, bevel=0.01)
    greeble_rect(S, (0.2, sgn * 1.51, -0.52), (1, 0, 0), (0, 0, 1), (0, -sgn, 0), 1.6, 0.7, 55, seed=10 + int(sgn))
    greeble_rect(S, (0.9, sgn * 1.25, -0.62), (0, 1, 0), (0, 0, 1), (-1, 0, 0), 0.5, 0.5, 14, seed=20 + int(sgn))
# floor + grate
S.box((0.2, 0, -1.12), (1.6, 3.0, 0.08), cls=0, bevel=0.01)
for i in range(14):
    S.box((0.55, -0.7 + i * 0.1, -1.07), (0.40, 0.012, 0.03), cls=0, bevel=0.002)
S.box((0.55, 0, -1.085), (0.42, 1.5, 0.01), cls=5, bevel=0.0)
for i in range(6):
    S.box((0.35 + i * 0.07, 0, -1.06), (0.012, 1.5, 0.03), cls=0, bevel=0.002)
# second seat on the right (y < 0)
seat_y = -0.98
S.box((-0.15, seat_y, -0.80), (0.62, 0.56, 0.16), cls=3, bevel=0.03)                     # cushion
S.box((-0.52, seat_y, -0.25), (0.16, 0.52, 1.05), rot=(0, math.radians(-14), 0), cls=3, bevel=0.035)   # back
S.box((-0.60, seat_y, 0.35), (0.14, 0.28, 0.24), rot=(0, math.radians(-14), 0), cls=3, bevel=0.03)     # headrest
for sy in (-0.28, 0.28):
    S.box((-0.40, seat_y + sy, -0.28), (0.20, 0.10, 0.90), rot=(0, math.radians(-14), 0), cls=3, bevel=0.03)   # bolsters
    S.box((-0.14, seat_y + sy * 1.04, -0.54), (0.14, 0.04, 0.46), cls=2, bevel=0.01)       # orange side brackets
for k in range(4):
    S.box((-0.455, seat_y + (-0.12 if k % 2 else 0.12), -0.05 - k * 0.0), (0.02, 0.05, 0.9), rot=(0, math.radians(-14), math.radians(8 if k % 2 else -8)), cls=3, bevel=0.002)
    S.box((-0.44, seat_y, -0.18 + 0.07 * k), (0.04, 0.12, 0.04), cls=0, bevel=0.005)      # buckles
S.box((-0.30, seat_y, -0.52), (0.08, 0.18, 0.06), cls=2, bevel=0.01)
S.box((-0.15, seat_y, -1.0), (0.5, 0.5, 0.22), cls=0, bevel=0.02)
# heavy pipes along the walls and ceiling
for sgn in (1, -1):
    S.pipe([(1.0, sgn * 1.12, 0.52), (0.55, sgn * 1.30, 0.62), (0.1, sgn * 1.45, 0.60), (-0.4, sgn * 1.45, 0.42)], 0.045, cls=0)
    S.pipe([(1.0, sgn * 1.02, 0.45), (0.65, sgn * 1.22, 0.30), (0.35, sgn * 1.45, 0.05), (0.35, sgn * 1.50, -0.5)], 0.032, cls=1)
    S.pipe([(0.9, sgn * 0.5, 0.62), (0.7, sgn * 0.9, 0.74), (0.2, sgn * 1.0, 0.76), (-0.3, sgn * 0.9, 0.72)], 0.028, cls=0)
    S.pipe([(0.35, sgn * 1.45, -0.45), (0.25, sgn * 1.30, -0.85), (0.3, sgn * 1.05, -1.05)], 0.05, cls=0)
# cable bundle sagging near the left pillar
S.pipe([(0.80, 0.9, 0.55), (0.85, 0.8, 0.30), (0.88, 0.95, 0.0), (0.85, 1.1, -0.2)], 0.022, cls=3, collars=False)
S.pipe([(0.82, 0.88, 0.55), (0.9, 0.78, 0.26), (0.9, 0.98, -0.04), (0.88, 1.12, -0.24)], 0.018, cls=3, collars=False)
# dash side stubs + warning lamps
for sgn in (1, -1):
    S.box((0.62, sgn * 1.36, -0.30), (0.36, 0.2, 0.12), cls=1, bevel=0.02)
    S.box((0.50, sgn * 1.36, -0.23), (0.05, 0.05, 0.03), cls=7, bevel=0.004)
    S.box((0.44, sgn * 1.36, -0.23), (0.05, 0.05, 0.03), cls=7, bevel=0.004)
    S.box((0.56, sgn * 1.62, 0.10), (0.04, 0.22, 0.05), cls=7, bevel=0.004)
# hanging handles
for sgn in (1, -1):
    S.pipe([(0.2, sgn * 0.5, 0.74), (0.2, sgn * 0.5, 0.60), (0.2, sgn * 0.8, 0.60), (0.2, sgn * 0.8, 0.74)], 0.014, cls=2, collars=False)
shell = S.finish()

# =============================================================================================================== GLASS
G = B("SM_Cockpit_Glass")
# canopy: a cylindrical arc in front of the pilot; single-sided surface quads
def arc_panel(b, y0, y1, z0, z1, x_front, bulge, nseg=24):
    ys = np.linspace(y0, y1, nseg + 1)
    verts_bot, verts_top = [], []
    for y in ys:
        t = (y - (y0 + y1) / 2) / ((y1 - y0) / 2)
        x = x_front - bulge * t * t
        verts_bot.append(b.bm.verts.new((x, y, z0)))
        verts_top.append(b.bm.verts.new((x - 0.12, y, z1)))   # leans back at the top
    for i in range(nseg):
        b.bm.faces.new((verts_bot[i], verts_bot[i + 1], verts_top[i + 1], verts_top[i]))
    for v in verts_bot + verts_top:
        v[b.cl] = 6
arc_panel(G, -1.25, 1.25, -0.20, 0.55, 0.97, 0.25)
for sgn in (1, -1):
    ys = [sgn * 1.30, sgn * 1.57]
    v = [G.bm.verts.new(p) for p in ((0.80, ys[0], -0.1), (0.50, ys[1], -0.1), (0.45, ys[1], 0.60), (0.75, ys[0], 0.58))]
    G.bm.faces.new(v if sgn > 0 else v[::-1])
    for x in v:
        x[G.cl] = 6
glass = G.finish()

# =============================================================================================================== RIG (left arm)
def rig_upper():
    R = B("SM_Rig_Upper")
    L = 0.55
    R.cyl((0, 0, 0), (L, 0, 0), 0.085, 0.075, cls=0, seg=20)
    R.sphere((0, 0, 0), 0.105, cls=0, seg=16)
    for t in (0.18, 0.5, 0.82):
        R.cyl((L * t - 0.02, 0, 0), (L * t + 0.02, 0, 0), 0.098, cls=1, seg=20)
    R.cyl((0.05, 0.0, 0.12), (L - 0.05, 0.0, 0.07), 0.028, cls=1, seg=12)                  # hydraulic ram
    R.cyl((0.05, 0.0, 0.12), (L * 0.5, 0.0, 0.095), 0.04, cls=0, seg=12)
    R.box((L * 0.55, 0, -0.1), (0.3, 0.14, 0.06), cls=2, bevel=0.012)                      # orange clamp plate
    R.box((L * 0.3, 0, 0.1), (0.14, 0.1, 0.05), cls=1, bevel=0.01)
    for k in range(5):
        R.box((0.1 + k * 0.085, 0.09, 0.0), (0.04, 0.02, 0.05), cls=5 if k == 2 else 0, bevel=0.003)
    greeble_rect(R, (L * 0.5, 0, 0.0), (1, 0, 0), (0, 1, 0), (0, 0, 1), 0.4, 0.14, 12, hmax=0.02, seed=5)
    R.pipe([(0.02, -0.09, 0.05), (L * 0.5, -0.12, 0.06), (L - 0.03, -0.09, 0.03)], 0.018, cls=3, collars=False)
    return R.finish()


def rig_fore():
    R = B("SM_Rig_Fore")
    L = 0.55
    R.sphere((0, 0, 0), 0.095, cls=0, seg=16)
    R.cyl((0, 0, 0), (L, 0, 0), 0.078, 0.062, cls=0, seg=20)
    for t in (0.22, 0.55, 0.85):
        R.cyl((L * t - 0.02, 0, 0), (L * t + 0.02, 0, 0), 0.088 - 0.012 * t, cls=1, seg=20)
    R.box((L * 0.6, 0, 0.075), (0.36, 0.16, 0.05), cls=2, bevel=0.012)
    R.cyl((0.04, -0.05, -0.11), (L - 0.04, -0.03, -0.075), 0.022, cls=1, seg=10)
    R.box((L * 0.35, 0.0, -0.085), (0.2, 0.12, 0.04), cls=1, bevel=0.01)
    for k in range(4):
        R.box((0.18 + k * 0.09, 0.075, 0.0), (0.03, 0.02, 0.04), cls=5 if k % 2 == 0 else 0, bevel=0.003)
    greeble_rect(R, (L * 0.5, 0, 0.0), (1, 0, 0), (0, 1, 0), (0, 0, -1), 0.4, 0.12, 12, hmax=0.02, seed=6)
    return R.finish()


def rig_glove():
    R = B("SM_Rig_Glove")
    R.sphere((0, 0, 0), 0.08, cls=0, seg=14)
    R.cyl((0, 0, 0), (0.12, 0, 0), 0.07, 0.065, cls=1, seg=18)               # wrist cuff
    R.cyl((0.04, 0, 0), (0.09, 0, 0), 0.085, cls=2, seg=18)
    R.box((0.24, 0, 0), (0.16, 0.15, 0.1), cls=3, bevel=0.03)                 # palm (fabric/rubber glove)
    R.box((0.24, 0, 0.055), (0.15, 0.14, 0.03), cls=1, bevel=0.01)           # knuckle plate
    # fingers wrapped on a grip bar
    for k, yy in enumerate((-0.054, -0.018, 0.018, 0.054)):
        R.box((0.37, yy, 0.012), (0.1, 0.032, 0.05), rot=(0, math.radians(-20), 0), cls=3, bevel=0.012)
        R.box((0.43, yy, -0.024), (0.07, 0.03, 0.044), rot=(0, math.radians(-70), 0), cls=3, bevel=0.01)
    R.box((0.26, 0.095, -0.015), (0.1, 0.04, 0.05), rot=(0, 0, math.radians(30)), cls=3, bevel=0.012)   # thumb
    R.cyl((0.38, -0.12, -0.03), (0.38, 0.12, -0.03), 0.018, cls=0, seg=12)    # grip bar
    # orange C-bracket frame around the hand
    R.box((0.22, 0, -0.115), (0.34, 0.26, 0.04), cls=2, bevel=0.015)
    R.box((0.22, 0.13, 0.0), (0.34, 0.04, 0.2), cls=2, bevel=0.015)
    R.box((0.22, -0.13, 0.0), (0.34, 0.04, 0.2), cls=2, bevel=0.015)
    R.box((0.05, 0, 0.1), (0.06, 0.3, 0.05), cls=1, bevel=0.012)
    for sy in (-1, 1):
        R.box((0.30, sy * 0.15, 0.03), (0.07, 0.012, 0.025), cls=5 if sy > 0 else 7, bevel=0.002)
    return R.finish()


up, fo, gl = rig_upper(), rig_fore(), rig_glove()

# =============================================================================================================== export
objs = {"SM_Cockpit_Shell": shell, "SM_Cockpit_Glass": glass, "SM_Rig_Upper": up, "SM_Rig_Fore": fo, "SM_Rig_Glove": gl}
for name, ob in objs.items():
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                             axis_forward="-Y", axis_up="Z", object_types={"MESH"}, mesh_smooth_type="EDGE", bake_space_transform=False, path_mode="AUTO")
    print("EXPORTED", path, len(ob.data.polygons), "faces")

if PREVIEW:
    import mathutils
    sc = bpy.context.scene
    sc.view_settings.view_transform = "Standard"
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.06, 0.09, 1)
    # class colours
    cols = {0: (0.04, 0.04, 0.045), 1: (0.17, 0.18, 0.2), 2: (0.8, 0.28, 0.02), 3: (0.02, 0.02, 0.025), 4: (0.0, 0.8, 1.0), 5: (1.0, 0.45, 0.05), 6: (0.0, 0.0, 0.0), 7: (1.0, 0.05, 0.03)}
    for ob in objs.values():
        me = ob.data
        cls = np.empty(len(me.vertices)); me.attributes["cls"].data.foreach_get("value", cls)
        ca = me.color_attributes.new("PC", "FLOAT_COLOR", "POINT")
        arr = np.array([list(cols[int(c)]) + [1.0] for c in cls], np.float32)
        ca.data.foreach_set("color", arr.ravel())
        m = bpy.data.materials.new("P"); m.use_nodes = True
        nt = m.node_tree; bsdf = nt.nodes["Principled BSDF"]
        vc = nt.nodes.new("ShaderNodeVertexColor"); vc.layer_name = "PC"
        nt.links.new(vc.outputs[0], bsdf.inputs["Base Color"]); bsdf.inputs["Metallic"].default_value = 0.6; bsdf.inputs["Roughness"].default_value = 0.4
        nt.links.new(vc.outputs[0], bsdf.inputs["Emission Color"]); bsdf.inputs["Emission Strength"].default_value = 0.0
        me.materials.clear(); me.materials.append(m)
    # glass: translucent blue
    gm = bpy.data.materials.new("GL"); gm.use_nodes = True
    gb = gm.node_tree.nodes["Principled BSDF"]; gb.inputs["Base Color"].default_value = (0.3, 0.5, 0.7, 1); gb.inputs["Alpha"].default_value = 0.12
    glass.data.materials.clear(); glass.data.materials.append(gm)
    # place the rig parts in a rest pose for the preview (two-bone chain forward)
    for name, ob, loc in (("L", up, (0.35, 0.9, -0.5)), ("F", fo, (0.80, 0.78, -0.4)), ("G", gl, (1.30, 0.62, -0.3))):
        pass
    for nm, src, loc, rot in (("UpL", up, (0.30, 0.95, -0.60), (0, math.radians(20), math.radians(-18))),
                              ("FoL", fo, (0.80, 0.80, -0.45), (0, math.radians(8), math.radians(-12))),
                              ("GlL", gl, (1.32, 0.66, -0.40), (0, 0, math.radians(-10)))):
        ob = src.copy(); ob.data = src.data; ob.name = nm
        bpy.context.scene.collection.objects.link(ob)
        ob.location = loc; ob.rotation_euler = rot
        # mirrored right side
        ob2 = src.copy(); ob2.data = src.data; ob2.name = nm + "R"
        bpy.context.scene.collection.objects.link(ob2)
        ob2.location = (loc[0], -loc[1], loc[2]); ob2.rotation_euler = (rot[0], rot[1], -rot[2]); ob2.scale = (1, -1, 1)
    for o in (up, fo, gl, glass):
        o.hide_render = True
    # lights
    for loc, e, c in (((0.2, 0.0, 0.6), 160.0, (0.6, 0.8, 1.0)), ((0.4, 0.9, -0.1), 80.0, (1.0, 0.55, 0.25)), ((0.4, -0.9, -0.1), 80.0, (0.4, 0.7, 1.0)), ((-0.3, 0.0, 0.2), 60.0, (1.0, 1.0, 1.0))):
        bpy.ops.object.light_add(type="POINT", location=loc); L = bpy.context.object; L.data.energy = e; L.data.color = c
    cd = bpy.data.cameras.new("C"); cd.lens = 12; cd.sensor_width = 36
    cam = bpy.data.objects.new("C", cd); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (0, 0, 0); cam.rotation_euler = (math.radians(90), 0, math.radians(-90))
    sc.render.filepath = os.path.join(OUT, "preview_eye.png"); bpy.ops.render.render(write_still=True)
    cam.rotation_euler = (math.radians(75), 0, math.radians(-90 + 40))
    sc.render.filepath = os.path.join(OUT, "preview_eye_left.png"); bpy.ops.render.render(write_still=True)
    cam.location = (-1.6, 1.8, 0.9); cam.rotation_euler = (mathutils.Vector((0.8, -0.3, -0.3)).to_track_quat("-Z", "Y").to_euler())
    cam.data.lens = 24
    sc.render.filepath = os.path.join(OUT, "preview_outer.png"); bpy.ops.render.render(write_still=True)
    cam.location = (-1.0, -2.6, 0.4); cam.rotation_euler = (mathutils.Vector((0.9, 2.2, -0.4)).to_track_quat("-Z", "Y").to_euler())
    sc.render.filepath = os.path.join(OUT, "preview_outer2.png"); bpy.ops.render.render(write_still=True)
    print("PREVIEW DONE")

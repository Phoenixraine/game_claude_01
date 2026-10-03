"""Hunyuan3D GLB -> cleaned, decimated, skinned 19-bone mech FBX for Unreal (same bone contract as BASTION_01).

blender -b -P hy_rig.py -- <config.json> [--preview]

config.json: {"glb": ..., "out_fbx": ..., "out_prefix": ..., "name": "ENEMY", "height": 82, "target_tris": 110000,
              "min_part_frac": 0.02, "bones": {bone: [head, tail, parent, radius]}  # LEFT (+X) and centre bones, right = mirror
              "foot_center_y": optional}
Mesh space after import: +Z up, mech faces -Y, left = +X. Output is scaled so the cleaned mesh is `height` m tall with its feet on z=0
and the stance centred on x=0,y=0.
"""
import bpy, bmesh, sys, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from scipy import sparse
from scipy.sparse.csgraph import connected_components

argv = sys.argv[sys.argv.index("--") + 1:]
CFG = json.load(open(argv[0]))
PREVIEW = "--preview" in argv
H_OUT = CFG.get("height", 82.0)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=CFG["glb"])
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = obj.data


def arrays(me):
    n = len(me.vertices)
    v = np.empty(n * 3, np.float64); me.vertices.foreach_get("co", v); v = v.reshape(-1, 3)
    p = len(me.polygons)
    f = np.empty(p * 3, np.int64); me.polygons.foreach_get("vertices", f); f = f.reshape(-1, 3)
    return v, f


v, f = arrays(me)
print("raw verts", len(v), "tris", len(f))

# ---- 1. keep only the big connected parts (drops the stray rods / floating wisps)
ne = np.concatenate([f[:, [0, 1]], f[:, [1, 2]]])
g = sparse.coo_matrix((np.ones(len(ne)), (ne[:, 0], ne[:, 1])), shape=(len(v), len(v)))
nc, lab = connected_components(g, directed=False)
fcount = np.bincount(lab[f[:, 0]], minlength=nc)
keep = fcount >= CFG.get("min_part_frac", 0.02) * fcount.max()
print("components", nc, "kept", int(keep.sum()), "tri counts kept", sorted(fcount[keep].tolist(), reverse=True)[:8])
fk = keep[lab[f[:, 0]]]
f = f[fk]
used = np.unique(f)
remap = -np.ones(len(v), np.int64); remap[used] = np.arange(len(used))
v = v[used]; f = remap[f]

# ---- 2. optional clipping of floor debris: drop faces entirely below `clip_z` fraction when thin (config) -- not needed yet

# ---- 3. normalise: height, feet on z=0, stance centred
zmin, zmax = v[:, 2].min(), v[:, 2].max()
s = H_OUT / (zmax - zmin)
v = (v - np.array([0, 0, zmin])) * s
foot = v[v[:, 2] < 4.0]
cx = (foot[:, 0].min() + foot[:, 0].max()) / 2 if len(foot) else 0.0
cy = (foot[:, 1].min() + foot[:, 1].max()) / 2 if len(foot) else 0.0
cy = CFG.get("foot_center_y", cy)
v[:, 0] -= cx; v[:, 1] -= cy
print("scale", s, "centre shift", cx, cy, "bbox", v.min(0), v.max(0))

# ---- 3b. cut boxes (final metres): thin generator artefacts (wing sheets, floor wisps); x ranges are mirrored automatically
bad = np.zeros(len(v), bool)
for lo, hi in CFG.get("cut_boxes", []):
    for sx in (1, -1):
        xl, xh = sorted((sx * lo[0], sx * hi[0]))
        bad |= (v[:, 0] >= xl) & (v[:, 0] <= xh) & (v[:, 1] >= lo[1]) & (v[:, 1] <= hi[1]) & (v[:, 2] >= lo[2]) & (v[:, 2] <= hi[2])
if bad.any():
    f = f[~bad[f].any(axis=1)]
    ne = np.concatenate([f[:, [0, 1]], f[:, [1, 2]]])
    g = sparse.coo_matrix((np.ones(len(ne)), (ne[:, 0], ne[:, 1])), shape=(len(v), len(v)))
    nc, lab = connected_components(g, directed=False)
    fcount = np.bincount(lab[f[:, 0]], minlength=nc)
    f = f[(fcount >= CFG.get("min_part_frac", 0.02) * fcount.max())[lab[f[:, 0]]]]
    used = np.unique(f); remap = -np.ones(len(v), np.int64); remap[used] = np.arange(len(used))
    v = v[used]; f = remap[f]
    print("cut boxes removed", int(bad.sum()), "verts")

# ---- 3c. thin-sheet removal inside regions: inward ray hits the opposite wall within max_thickness -> sheet -> delete
if CFG.get("thin_regions"):
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    vnrm = np.zeros_like(v)
    for k in range(3):
        np.add.at(vnrm, f[:, k], fn)
    vnrm /= np.maximum(np.linalg.norm(vnrm, axis=1, keepdims=True), 1e-12)
    tree = BVHTree.FromPolygons([Vector(p) for p in v], [tuple(t) for t in f])
    bad = np.zeros(len(v), bool)
    for lo, hi, thick in CFG["thin_regions"]:
        lo = np.array(lo); hi = np.array(hi)
        cand = np.nonzero(np.all((np.abs(v[:, :1]) >= lo[0]) & (np.abs(v[:, :1]) <= hi[0]), axis=1) & (v[:, 1] >= lo[1]) & (v[:, 1] <= hi[1]) & (v[:, 2] >= lo[2]) & (v[:, 2] <= hi[2]))[0]
        for i in cand:
            n = Vector(-vnrm[i]); o = Vector(v[i]) + n * 0.05
            hit = tree.ray_cast(o, n, thick)
            if hit[0] is not None:
                bad[i] = True
    print("thin sheet verts", int(bad.sum()))
    f = f[~bad[f].any(axis=1)]
    ne = np.concatenate([f[:, [0, 1]], f[:, [1, 2]]])
    g = sparse.coo_matrix((np.ones(len(ne)), (ne[:, 0], ne[:, 1])), shape=(len(v), len(v)))
    nc, lab = connected_components(g, directed=False)
    fcount = np.bincount(lab[f[:, 0]], minlength=nc)
    f = f[(fcount >= CFG.get("min_part_frac", 0.02) * fcount.max())[lab[f[:, 0]]]]
    used = np.unique(f); remap = -np.ones(len(v), np.int64); remap[used] = np.arange(len(used))
    v = v[used]; f = remap[f]

me.clear_geometry()
me.from_pydata(v.tolist(), [], f.tolist())
me.update()

# ---- 4. decimate (collapse) to the triangle budget, light smoothing first
bpy.context.view_layer.objects.active = obj
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(me); bm.free()
tgt = CFG.get("target_tris", 110000)
if len(f) > tgt:
    mod = obj.modifiers.new("Dec", "DECIMATE"); mod.decimate_type = "COLLAPSE"; mod.ratio = tgt / len(f); mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
me = obj.data
v, f = arrays(me)
print("decimated verts", len(v), "tris", len(f))

# ---- 5. skin weights: capsule distance per bone, softmax blend, left/right side limited
B = CFG["bones"]
bones = {}
for name, (head, tail, parent, radius) in B.items():
    bones[name] = (np.array(head, float), np.array(tail, float), parent, radius)
for name, (head, tail, parent, radius) in list(B.items()):
    if name.endswith("_l"):
        r = name[:-2] + "_r"
        h2 = [-head[0], head[1], head[2]]; t2 = [-tail[0], tail[1], tail[2]]
        bones[r] = (np.array(h2, float), np.array(t2, float), parent[:-2] + "_r" if parent.endswith("_l") else parent, radius)
order = ["root", "pelvis", "torso", "head", "reactor"] + [b + sd for b in ("shoulder", "upperarm", "forearm", "hand", "thigh", "shin", "foot") for sd in ("_l", "_r")]
assert set(order) == set(bones.keys()), set(order) ^ set(bones.keys())


def seg_dist(P, a, b):
    ab = b - a; t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


skin_names = [n for n in order if bones[n][3] > 0]
side_margin = CFG.get("side_margin", 2.5)
K = CFG.get("blend_k", 4.0)


def compute_weights(v):
    E = np.full((len(v), len(skin_names)), 1e9)
    for j, n in enumerate(skin_names):
        a, b, _, r = bones[n]
        e = seg_dist(v, a, b) / r
        if n.endswith("_l"):
            e = np.where(v[:, 0] < -side_margin, 1e9, e)
        elif n.endswith("_r"):
            e = np.where(v[:, 0] > side_margin, 1e9, e)
        E[:, j] = e
    emin = E.min(1, keepdims=True)
    W = np.exp(-K * (E - emin)); W[E > 1e8] = 0
    idx = np.argsort(-W, axis=1)[:, 4:]
    np.put_along_axis(W, idx, 0, axis=1)
    W[W < 0.04 * W.max(1, keepdims=True)] = 0
    W /= W.sum(1, keepdims=True)
    return W


W = compute_weights(v)


def rot_about(h, rx, ry, rz):
    """4x4: rotation (degrees, Rz*Ry*Rx about world axes) around point h."""
    a, b, c = math.radians(rx), math.radians(ry), math.radians(rz)
    Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    Ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    Rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    R = Rz @ Ry @ Rx
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = h - R @ h
    return M


def pose_mats(spec):
    """bone -> D_b (rest -> posed), following the game's rig contract (rotation about the already-deformed joint)."""
    D = {}
    for n in order:
        par = bones[n][2]
        Dp = D[par] if par else np.eye(4)
        h = Dp @ np.append(bones[n][0], 1.0)
        D[n] = rot_about(h[:3], *spec.get(n, (0, 0, 0))) @ Dp
    return D


def lbs(v, W, D):
    out = np.zeros_like(v)
    for j, n in enumerate(skin_names):
        w = W[:, j]
        if not w.any():
            continue
        M = D[n]
        out += w[:, None] * (v @ M[:3, :3].T + M[:3, 3])
    return out


def mirror(spec):
    m = dict(spec)
    for n, (x, y, z) in spec.items():
        if n.endswith("_l"):
            m[n[:-2] + "_r"] = (x, -y, -z)
        if n.endswith("_r"):
            m[n[:-2] + "_l"] = (x, -y, -z)
    return m


TEAR_POSES = [
    {"upperarm_l": (-150, 0, 0), "forearm_l": (-100, 0, 0), "upperarm_r": (-30, 0, 0)},
    {"upperarm_l": (-20, 0, 70), "forearm_l": (-60, 0, 0), "hand_l": (0, 55, 0)},
    {"upperarm_l": (55, 0, 0), "forearm_l": (-90, 0, 0), "hand_l": (40, 0, 0)},
    {"torso": (0, 0, 40), "head": (0, 0, 45), "upperarm_l": (-90, 0, 20), "upperarm_r": (-60, 0, -10), "forearm_r": (-70, 0, 0)},
    {"torso": (15, 0, -40), "upperarm_r": (-150, 0, -20), "forearm_r": (-90, 0, 0), "pelvis": (0, 0, 15)},
]
tear = np.zeros(len(f), bool)
e0 = [np.linalg.norm(v[f[:, a]] - v[f[:, b]], axis=1) for a, b in ((0, 1), (1, 2), (2, 0))]
for sp in TEAR_POSES + [mirror(q) for q in TEAR_POSES]:
    vp = lbs(v, W, pose_mats(sp))
    for k, (a, b) in enumerate(((0, 1), (1, 2), (2, 0))):
        e1 = np.linalg.norm(vp[f[:, a]] - vp[f[:, b]], axis=1)
        tear |= (e1 > 2.6 * e0[k] + 1.0)
print("tearing faces removed", int(tear.sum()), "of", len(f))
if tear.any():
    f = f[~tear]
    ne = np.concatenate([f[:, [0, 1]], f[:, [1, 2]]])
    g = sparse.coo_matrix((np.ones(len(ne)), (ne[:, 0], ne[:, 1])), shape=(len(v), len(v)))
    nc, lab = connected_components(g, directed=False)
    fcount = np.bincount(lab[f[:, 0]], minlength=nc)
    f = f[(fcount >= 0.003 * fcount.max())[lab[f[:, 0]]]]
    used = np.unique(f); remap = -np.ones(len(v), np.int64); remap[used] = np.arange(len(used))
    v = v[used]; f = remap[f]
    me.clear_geometry(); me.from_pydata(v.tolist(), [], f.tolist()); me.update()
    W = compute_weights(v)
print("weights per bone (verts with >0.5):", {n: int((W[:, j] > 0.5).sum()) for j, n in enumerate(skin_names)})

# ---- 6. vertex colours: R convexity (edge wear), G ambient occlusion, B zone id, A emissive mask (config boxes)
ne = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
A = sparse.coo_matrix((np.ones(len(ne)), (ne[:, 0], ne[:, 1])), shape=(len(v), len(v))).tocsr()
A = ((A + A.T) > 0).astype(float)
deg = np.asarray(A.sum(1)).ravel()
vn = np.empty(len(v) * 3); me.vertices.foreach_get("normal", vn); vn = vn.reshape(-1, 3)
lap = (A @ v) / np.maximum(deg, 1)[:, None] - v
for _ in range(2):   # smooth the Laplacian over 2 more rings to read form instead of noise
    lap = (A @ lap) / np.maximum(deg, 1)[:, None]
conv = np.clip(-(lap * vn).sum(1) / 0.6 * 0.5 + 0.5, 0, 1)
conv = np.clip(0.5 + (conv - np.median(conv)) / 0.12, 0, 1)   # spread the narrow raw range
print('CONV pct', np.percentile(conv,[5,25,50,75,95,99]).round(3))
# AO with BVH ray casts
bvh = BVHTree.FromObject(obj, bpy.context.evaluated_depsgraph_get())
rng = np.random.default_rng(3)
dirs = rng.normal(size=(10, 3)); dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
ao = np.ones(len(v))
for i in range(len(v)):
    n = Vector(vn[i]); p = Vector(v[i]) + n * 0.15
    hit = 0
    for d in dirs:
        dd = Vector(d)
        if dd.dot(n) < 0:
            dd = -dd
        if bvh.ray_cast(p, dd, 7.0)[0] is not None:
            hit += 1
    ao[i] = 1.0 - hit / len(dirs)
zone = np.array([0.0] * len(v))
for j, n in enumerate(skin_names):
    zone[W[:, j] > 0.5] = (order.index(n) + 1) / 20.0
em = np.zeros(len(v))
for bx in CFG.get("emissive_boxes", []):   # [lo, hi] with x as |x|; only front-facing (normal y < -0.2) vertices glow
    lo, hi = np.array(bx[0]), np.array(bx[1])
    q = np.stack([np.abs(v[:, 0]), v[:, 1], v[:, 2]], axis=1)
    m = np.all((q >= lo) & (q <= hi), axis=1) & (vn[:, 1] < -0.2)
    em[m] = 1.0
vcol = np.stack([conv, ao, zone, em], axis=1)

# ---- 7. write vertex groups, colours, material, armature
for vg in list(obj.vertex_groups):
    obj.vertex_groups.remove(vg)
for j, n in enumerate(skin_names):
    vg = obj.vertex_groups.new(name=n)
    ids = np.nonzero(W[:, j] > 0)[0]
    for i in ids:
        vg.add([int(i)], float(W[i, j]), "REPLACE")
if me.color_attributes:
    for ca in list(me.color_attributes):
        me.color_attributes.remove(ca)
ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
ca.data.foreach_set("color", vcol.astype(np.float32).ravel())
me.color_attributes.active_color = ca
mat = bpy.data.materials.new("M_MechHull"); mat.use_nodes = True
me.materials.clear(); me.materials.append(mat)
me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
# rest-pose position in two UV sets (stable procedural texturing while bones move): UV0 = (x,y)/82, UV1 = (z/82, 0)
for nm in list(me.uv_layers.keys()):
    me.uv_layers.remove(me.uv_layers[nm])
loop_v = np.empty(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", loop_v)
uv0 = me.uv_layers.new(name="UV0"); uv1 = me.uv_layers.new(name="UV1")
uv0.data.foreach_set("uv", np.stack([v[loop_v, 0] / 82.0 + 0.5, v[loop_v, 1] / 82.0 + 0.5], 1).astype(np.float32).ravel())
uv1.data.foreach_set("uv", np.stack([v[loop_v, 2] / 82.0, np.zeros(len(loop_v))], 1).astype(np.float32).ravel())
obj.name = "Body_mech"; me.name = "Body_mech"

arm = bpy.data.armatures.new("BASTION_Rig")
ao_ = bpy.data.objects.new("BASTION_Rig", arm)
bpy.context.scene.collection.objects.link(ao_)
bpy.context.view_layer.objects.active = ao_
bpy.ops.object.mode_set(mode="EDIT")
eb = {}
for n in order:
    h, t, p, r = bones[n]
    e = arm.edit_bones.new(n); e.head = Vector(h); e.tail = Vector(t)
    if (e.tail - e.head).length < 0.5:
        e.tail = e.head + Vector((0, 0, 1))
    eb[n] = e
for n in order:
    p = bones[n][2]
    if p:
        eb[n].parent = eb[p]
bpy.ops.object.mode_set(mode="OBJECT")
mod = obj.modifiers.new("Armature", "ARMATURE"); mod.object = ao_
obj.parent = ao_
obj.matrix_parent_inverse = ao_.matrix_world.inverted()

bpy.ops.object.select_all(action="DESELECT")
ao_.select_set(True); obj.select_set(True)
bpy.context.view_layer.objects.active = ao_
bpy.ops.export_scene.fbx(filepath=CFG["out_fbx"], use_selection=True, apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                         axis_forward="-Y", axis_up="Z", object_types={"ARMATURE", "MESH"}, add_leaf_bones=False, bake_anim=False,
                         mesh_smooth_type="FACE", use_mesh_modifiers=False, bake_space_transform=False, path_mode="AUTO")
print("EXPORTED", CFG["out_fbx"], "tris", len(f))

# ---- 8. preview renders: rest + a swing pose
if PREVIEW:
    import mathutils
    sc = bpy.context.scene
    sc.view_settings.view_transform = "Standard"
    sc.render.engine = "BLENDER_EEVEE_NEXT"; sc.render.resolution_x = 900; sc.render.resolution_y = 1100
    world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.55, 0.62, 1)
    mm = bpy.data.materials.new("P"); mm.use_nodes = True
    mb = mm.node_tree.nodes["Principled BSDF"]; mb.inputs["Base Color"].default_value = (0.3, 0.32, 0.36, 1); mb.inputs["Metallic"].default_value = 0.7; mb.inputs["Roughness"].default_value = 0.4
    me.materials.clear(); me.materials.append(mm)
    for loc, e in (((1, -1.2, 1.4), 4.0), ((-1.4, -0.6, 0.8), 2.0), ((0.2, 1.4, 1.2), 3.0)):
        bpy.ops.object.light_add(type="SUN"); L = bpy.context.object; L.data.energy = e
        L.rotation_euler = mathutils.Vector((-loc[0], -loc[1], -loc[2])).to_track_quat("-Z", "Y").to_euler()
    cd = bpy.data.cameras.new("C"); cd.lens = 50
    cam = bpy.data.objects.new("C", cd); sc.collection.objects.link(cam); sc.camera = cam
    ctr = Vector((0, 0, H_OUT * 0.5))

    def shoot(tag, az, el=8, dist=H_OUT * 2.1):
        a = math.radians(az); e = math.radians(el)
        cam.location = (ctr.x + math.sin(a) * dist * math.cos(e), ctr.y - math.cos(a) * dist * math.cos(e), ctr.z + math.sin(e) * dist)
        cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = f"{CFG['out_prefix']}_{tag}.png"; bpy.ops.render.render(write_still=True)

    if "--weights" in argv:
        import colorsys
        pal = np.array([colorsys.hsv_to_rgb((k * 0.61803) % 1.0, 0.85, 0.95) + (1.0,) for k in range(len(skin_names))])
        wc = me.color_attributes.new("WCol", "FLOAT_COLOR", "POINT")
        wc.data.foreach_set("color", (W @ pal).astype(np.float32).ravel())
        mm.node_tree.nodes.clear()
        vcn = mm.node_tree.nodes.new("ShaderNodeVertexColor"); vcn.layer_name = "WCol"
        em_ = mm.node_tree.nodes.new("ShaderNodeEmission"); out_ = mm.node_tree.nodes.new("ShaderNodeOutputMaterial")
        mm.node_tree.links.new(vcn.outputs[0], em_.inputs[0]); mm.node_tree.links.new(em_.outputs[0], out_.inputs[0])
        print("WEIGHT LEGEND", {n: [round(float(x), 2) for x in pal[i][:3]] for i, n in enumerate(skin_names)})
    shoot("rest_tq", 35)
    # swing pose: right arm overhead + torso twist + step (rotations about world axes through the joint, composed down the chain)
    bpy.context.view_layer.objects.active = ao_
    bpy.ops.object.mode_set(mode="POSE")
    from mathutils import Matrix
    rest = {b.name: b.matrix_local.copy() for b in arm.bones}
    POSES = {"swing": {"torso": (0, 0, 28), "upperarm_r": (-130, 0, -20), "forearm_r": (-40, 0, 0), "thigh_l": (-30, 0, -3), "shin_l": (40, 0, 0), "thigh_r": (12, 0, 3), "upperarm_l": (-25, 0, 5), "forearm_l": (-30, 0, 0), "head": (0, 0, -12)},
             "arm90": {"upperarm_r": (-90, 0, 0), "forearm_r": (-50, 0, 0), "upperarm_l": (-40, 0, 10)},
             "step": {"thigh_l": (-40, 0, 0), "shin_l": (60, 0, 0), "foot_l": (-15, 0, 0), "thigh_r": (20, 0, 0), "torso": (0, 0, 15)}}
    for pname, spec in POSES.items():
        for b in ao_.pose.bones:
            b.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        posed = {}
        depth = lambda b: len(b.parent_recursive)
        for b in sorted(arm.bones, key=depth):
            pb = ao_.pose.bones[b.name]
            M = (posed[b.parent.name] @ rest[b.parent.name].inverted() @ rest[b.name]) if b.parent else rest[b.name].copy()
            rx, ry, rz = spec.get(b.name, (0, 0, 0))
            if rx or ry or rz:
                hd = M.translation.copy()
                R = Matrix.Rotation(math.radians(rz), 4, "Z") @ Matrix.Rotation(math.radians(ry), 4, "Y") @ Matrix.Rotation(math.radians(rx), 4, "X")
                M = Matrix.Translation(hd) @ R @ Matrix.Translation(-hd) @ M
            pb.matrix = M; bpy.context.view_layer.update(); posed[b.name] = pb.matrix.copy()
        shoot("pose_" + pname, 35)
    print("PREVIEW DONE")

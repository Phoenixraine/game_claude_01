"""blender -b -P hy_ortho.py -- <glb> <out_prefix> : orthographic front/side silhouettes with known pixel->world mapping.
Writes <out_prefix>_ortho_front.png / _ortho_side.png (1000x1000, camera ortho_scale = 1.1*height, centred on the bbox) and <out_prefix>_ortho.json."""
import bpy, sys, json, mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
glb, out = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
mn = mathutils.Vector((1e9,) * 3); mx = mathutils.Vector((-1e9,) * 3)
for o in objs:
    for c in o.bound_box:
        w = o.matrix_world @ mathutils.Vector(c)
        mn = mathutils.Vector((min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z)))
        mx = mathutils.Vector((max(mx.x, w.x), max(mx.y, w.y), max(mx.z, w.z)))
ctr = (mn + mx) / 2
H = mx.z - mn.z
for o in objs:
    mat = bpy.data.materials.new("M"); mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.35, 0.37, 0.42, 1); b.inputs["Roughness"].default_value = 0.6
    o.data.materials.clear(); o.data.materials.append(mat)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x = sc.render.resolution_y = 1000
world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1); world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
for loc in ((0.3, -1, 0.8), (-0.5, 1, 0.5)):
    bpy.ops.object.light_add(type="SUN"); L = bpy.context.object; L.data.energy = 3.0
    L.rotation_euler = mathutils.Vector((-loc[0], -loc[1], -loc[2])).to_track_quat("-Z", "Y").to_euler()
cd = bpy.data.cameras.new("C"); cd.type = "ORTHO"; cd.ortho_scale = H * 1.1
cam = bpy.data.objects.new("C", cd); sc.collection.objects.link(cam); sc.camera = cam
for name, d in (("front", mathutils.Vector((0, -1, 0))), ("side", mathutils.Vector((1, 0, 0)))):
    cam.location = ctr + d * H * 3
    cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{out}_ortho_{name}.png"
    bpy.ops.render.render(write_still=True)
json.dump({"center": list(ctr), "height": H, "bbox_min": list(mn), "bbox_max": list(mx), "scale": H * 1.1}, open(out + "_ortho.json", "w"))
print("DONE", list(ctr), H)

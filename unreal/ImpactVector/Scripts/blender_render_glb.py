"""blender -b -P blender_render_glb.py -- <glb> <out_prefix>  : renders 4 views of a GLB on a grey ground (EEVEE)."""
import bpy, sys, math, mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
glb, out = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
# bounds
mn = mathutils.Vector((1e9, 1e9, 1e9)); mx = mathutils.Vector((-1e9, -1e9, -1e9))
for o in objs:
    for c in o.bound_box:
        w = o.matrix_world @ mathutils.Vector(c)
        mn = mathutils.Vector((min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z)))
        mx = mathutils.Vector((max(mx.x, w.x), max(mx.y, w.y), max(mx.z, w.z)))
size = mx - mn
ctr = (mn + mx) / 2
print("BOUNDS", tuple(round(v, 3) for v in mn), tuple(round(v, 3) for v in mx), "size", tuple(round(v, 3) for v in size))
for o in objs:
    mat = bpy.data.materials.new("M"); mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.32, 0.36, 0.42, 1); b.inputs["Metallic"].default_value = 0.6; b.inputs["Roughness"].default_value = 0.45
    o.data.materials.clear(); o.data.materials.append(mat)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.shade_smooth() if hasattr(bpy.ops.object, "shade_smooth") else None

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys() else "BLENDER_EEVEE"
scene.render.resolution_x, scene.render.resolution_y = 900, 1100
scene.render.film_transparent = False
world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.6, 0.68, 1); world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
# ground
bpy.ops.mesh.primitive_plane_add(size=max(size) * 6, location=(ctr.x, ctr.y, mn.z))
g = bpy.context.object
gm = bpy.data.materials.new("G"); gm.use_nodes = True; gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.25, 0.25, 0.27, 1)
g.data.materials.append(gm)
# lights
for loc, e in (((1, -1.2, 1.4), 4.0), ((-1.4, -0.6, 0.8), 2.0), ((0.2, 1.4, 1.2), 3.0)):
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 0))
    L = bpy.context.object; L.data.energy = e
    L.rotation_euler = mathutils.Vector((-loc[0], -loc[1], -loc[2])).to_track_quat("-Z", "Y").to_euler()
H = size.z if size.z > 0 else max(size)
cam_data = bpy.data.cameras.new("C"); cam_data.lens = 50
cam = bpy.data.objects.new("C", cam_data); scene.collection.objects.link(cam); scene.camera = cam
dist = H * 2.0
for name, ang, el in (("front", 0, 5), ("side", 90, 5), ("back", 180, 5), ("tq", 40, 12)):
    a = math.radians(ang); e = math.radians(el)
    cam.location = (ctr.x + math.sin(a) * dist * math.cos(e), ctr.y - math.cos(a) * dist * math.cos(e), ctr.z + math.sin(e) * dist)
    cam.rotation_euler = (ctr - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{out}_{name}.png"
    bpy.ops.render.render(write_still=True)
print("DONE")

"""Preview renders (Cycles, CPU): studio lighting, orthographic technical views, perspective hero views, scale comparison."""
import math

import bpy
from mathutils import Vector


def setup_scene(res=(1280, 720), samples=24, bg=(0.18, 0.2, 0.23)):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (*bg, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    return sc


def lights(target=(0, 0, 40), scale=1.0, key_dir=(0.5, -0.8, 0.8)):
    """Three-point studio rig (key from `key_dir`, fill, rim); previous L_ lights are replaced."""
    for o in [o for o in bpy.data.objects if o.name.startswith("L_")]:
        bpy.data.objects.remove(o)
    k = bpy.data.lights.new("L_key", "SUN")
    k.energy = 3.0
    k.angle = math.radians(8)
    ko = bpy.data.objects.new("L_key", k)
    bpy.context.scene.collection.objects.link(ko)
    d = Vector(key_dir).normalized()
    ko.rotation_euler = Vector((0, 0, -1)).rotation_difference(-d).to_euler()
    f = bpy.data.lights.new("L_fill", "SUN")
    f.energy = 1.2
    fo = bpy.data.objects.new("L_fill", f)
    bpy.context.scene.collection.objects.link(fo)
    fo.rotation_euler = Vector((0, 0, -1)).rotation_difference(Vector((-0.6, 0.5, -0.4)).normalized()).to_euler()
    r = bpy.data.lights.new("L_rim", "SUN")
    r.energy = 2.0
    ro = bpy.data.objects.new("L_rim", r)
    bpy.context.scene.collection.objects.link(ro)
    ro.rotation_euler = Vector((0, 0, -1)).rotation_difference(Vector((0.2, 0.9, -0.3)).normalized()).to_euler()


def ground(size=900, z=0.0, color=(0.22, 0.22, 0.23)):
    for o in [o for o in bpy.data.objects if o.name == "Ground"]:
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    g = bpy.context.object
    g.name = "Ground"
    m = bpy.data.materials.new("M_Ground")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*color, 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    g.data.materials.append(m)
    return g


def camera(loc, target, lens=50.0, ortho=None):
    for o in [o for o in bpy.data.objects if o.name == "Cam"]:
        bpy.data.objects.remove(o)
    cd = bpy.data.cameras.new("Cam")
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    else:
        cd.lens = lens
    cd.clip_end = 5000
    co = bpy.data.objects.new("Cam", cd)
    bpy.context.scene.collection.objects.link(co)
    d = Vector(target) - Vector(loc)
    co.location = loc
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = co
    return co


def shoot(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def hero(path, loc, target, lens=40.0, res=(1280, 800), samples=32):
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = res
    bpy.context.scene.cycles.samples = samples
    camera(loc, target, lens=lens)
    shoot(path)


def ortho_view(path, loc, target, scale, res=(900, 1100), samples=32):
    bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y = res
    bpy.context.scene.cycles.samples = samples
    camera(loc, target, ortho=scale)
    shoot(path)


def _dark_mat(name, color, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 0.8
    if emit:
        b.inputs["Emission Color"].default_value = (*color, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def scale_props():
    """Skyscraper (200 m, with a window grid), a bus and a person, for the scale comparison. Objects are prefixed X_."""
    objs = []
    wall = _dark_mat("X_wall", (0.05, 0.06, 0.08))
    win = _dark_mat("X_win", (0.9, 0.75, 0.4), emit=1.5)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-95, 40, 100))
    t = bpy.context.object
    t.scale = (46, 46, 200)
    t.name = "X_tower"
    t.data.materials.append(wall)
    objs.append(t)
    import random
    rnd = random.Random(5)
    for zi in range(6, 98):
        for xi in range(-9, 10):
            if rnd.random() < 0.55:
                bpy.ops.mesh.primitive_cube_add(size=1, location=(-95 + xi * 2.3, 40 - 23.05, zi * 2.0 + 1.0))
                w = bpy.context.object
                w.scale = (1.3, 0.1, 1.0)
                w.name = "X_w"
                w.data.materials.append(win)
                objs.append(w)
    bus_mat = _dark_mat("X_bus", (0.7, 0.55, 0.1))
    bpy.ops.mesh.primitive_cube_add(size=1, location=(42, -34, 1.9))
    b = bpy.context.object
    b.scale = (2.55, 12.0, 3.0)
    b.name = "X_bus"
    b.data.materials.append(bus_mat)
    objs.append(b)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(46, -34, 0.9))
    h = bpy.context.object
    h.scale = (0.55, 0.45, 1.8)
    h.name = "X_person"
    h.data.materials.append(_dark_mat("X_person", (0.9, 0.9, 0.9), emit=0.6))
    objs.append(h)
    return objs


def remove_objs(objs):
    for o in objs:
        bpy.data.objects.remove(o)

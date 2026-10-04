"""Scene dressing and renders of cockpit v2: eye camera (90 deg horizontal, 16:9), a neon city behind the glass, damage states, glass-share mask, class colour view."""
import math
import os
import random

import bpy
import numpy as np
from mathutils import Vector

from . import blendout


def setup_render(w, h, samples, engine="CYCLES"):
    sc = bpy.context.scene
    sc.render.engine = engine
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = samples > 4
    sc.cycles.max_bounces = 8
    sc.cycles.transmission_bounces = 8
    sc.cycles.transparent_max_bounces = 12
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"


def eye_camera(fov_deg=90.0, loc=(0, 0, 0), look=(0, -1, 0), roll=0.0):
    cam = bpy.data.cameras.new("Eye")
    cam.sensor_fit = "HORIZONTAL"
    cam.lens_unit = "FOV"
    cam.angle = math.radians(fov_deg)
    cam.clip_start = 0.02
    ob = bpy.data.objects.new("Eye", cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector(loc)
    ob.rotation_euler = (Vector(look)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    return ob


def world(red=0.0, color_top=(0.01, 0.02, 0.06), color_horizon=(0.55, 0.22, 0.2), strength=0.9):
    sc = bpy.context.scene
    color_horizon = tuple(c * (1 - 0.7 * red) + t * 0.7 * red for c, t in zip(color_horizon, (0.9, 0.05, 0.03)))
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = (*color_horizon, 1)
    ramp.color_ramp.elements[1].position = 0.85
    ramp.color_ramp.elements[1].color = (*color_top, 1)
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def city(seed=5, ring=(110.0, 460.0), n=520):
    """Emissive box city around the cockpit: lit window grids in cyan / amber / white, a red-white tower, neon sign slabs."""
    rng = random.Random(seed)
    mats = {}

    def window_mat(name, col):
        """Lit window grid in object space: floor/column cells, random on/off per cell, dark facade elsewhere."""
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])

        def m_(op, a=None, b=None, bval=None):
            n = nt.nodes.new("ShaderNodeMath")
            n.operation = op
            if a is not None:
                nt.links.new(a, n.inputs[0])
            if b is not None:
                nt.links.new(b, n.inputs[1])
            elif bval is not None:
                n.inputs[1].default_value = bval
            return n.outputs["Value"]

        u = m_("ADD", sep.outputs["X"], sep.outputs["Y"])
        cu = m_("DIVIDE", u, bval=1.7)
        cw = m_("DIVIDE", sep.outputs["Z"], bval=2.4)
        fu = m_("FRACT", cu)
        fw = m_("FRACT", cw)
        win = m_("MULTIPLY", m_("LESS_THAN", fu, bval=0.5), m_("LESS_THAN", fw, bval=0.45))
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(m_("FLOOR", cu), comb.inputs["X"])
        nt.links.new(m_("FLOOR", cw), comb.inputs["Y"])
        comb.inputs["Z"].default_value = float(hash(name) % 97)
        wn = nt.nodes.new("ShaderNodeTexWhiteNoise")
        wn.noise_dimensions = "3D"
        nt.links.new(comb.outputs["Vector"], wn.inputs["Vector"])
        on = m_("GREATER_THAN", wn.outputs["Value"], bval=0.62)
        lit = m_("MULTIPLY", win, on)
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (*col, 1)
        nt.links.new(m_("MULTIPLY", lit, bval=1.1), em.inputs["Strength"])
        dark = nt.nodes.new("ShaderNodeBsdfPrincipled")
        dark.inputs["Base Color"].default_value = (0.02, 0.025, 0.04, 1)
        dark.inputs["Roughness"].default_value = 0.4
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lit, mix.inputs["Fac"])
        nt.links.new(dark.outputs["BSDF"], mix.inputs[1])
        nt.links.new(em.outputs["Emission"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
        mats[name] = m

    window_mat("City_Cyan", (0.05, 0.55, 1.0))
    window_mat("City_Amber", (1.0, 0.4, 0.04))
    window_mat("City_White", (1.0, 0.75, 0.45))

    def neon(name, col, strength=6.0):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (*col, 1)
        em.inputs["Strength"].default_value = strength
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
        mats[name] = m

    neon("Neon_Red", (1.0, 0.1, 0.05), 6.0)
    neon("Neon_Pink", (1.0, 0.1, 0.7))
    neon("Neon_Cyan", (0.1, 0.8, 1.0))
    neon("Neon_Amber", (1.0, 0.55, 0.05))
    coll = bpy.data.collections.new("City")
    bpy.context.scene.collection.children.link(coll)

    def box(c, size, mat):
        me = bpy.data.meshes.new("b")
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        v = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz), (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        me.from_pydata(v, [], f)
        me.materials.append(mats[mat])
        ob = bpy.data.objects.new("c", me)
        ob.location = c
        coll.objects.link(ob)
        return ob

    names = ["City_Cyan", "City_Amber", "City_White", "City_Cyan"]
    for k in range(n):
        a = rng.uniform(-math.pi * 0.62, math.pi * 0.62) + math.pi / 2        # mostly in front of the pilot (-Y)
        d = rng.uniform(*ring)
        x, y = math.cos(a) * d, -abs(math.sin(a)) * d - 20.0
        if rng.random() < 0.5:
            x, y = rng.uniform(-d, d), -d
        h = rng.uniform(25.0, 120.0) * (0.5 + 0.8 * rng.random() ** 2)
        w, dd = rng.uniform(18.0, 50.0), rng.uniform(18.0, 50.0)
        box((x, y, h / 2 - 28.0), (w, dd, h), rng.choice(names))
        if rng.random() < 0.18:                                           # neon slab on the front face
            box((x, y + dd / 2 + 0.3, h * rng.uniform(0.3, 0.8) - 28.0), (w * rng.uniform(0.15, 0.35), 0.6, h * rng.uniform(0.2, 0.5)), rng.choice(["Neon_Red", "Neon_Pink", "Neon_Cyan", "Neon_Amber"]))
    # a red and white lattice tower in the middle distance
    for k in range(12):
        z = k * 17.0 - 28.0
        w = 34.0 * (1 - k / 14.0) + 3.0
        box((60.0, -330.0, z + 8.5), (w, w, 17.0), "Neon_Red" if k % 2 == 0 else "City_White")
    # the ground / street grid of lights far below
    box((0, -120.0, -33.0), (420, 360, 0.5), "City_Amber")


def lights(red=0.0, base=1.0):
    base = base * (1.0 - 0.55 * red)
    """Interior fill: a cold key through the glass, warm accents, and the red alarm light (strength `red`)."""
    def add(kind, loc, energy, color, size=0.6, rot=None):
        d = bpy.data.lights.new("L", kind)
        d.energy = energy
        d.color = color
        if hasattr(d, "size"):
            d.size = size
        o = bpy.data.objects.new("L", d)
        o.location = loc
        if rot:
            o.rotation_euler = rot
        bpy.context.scene.collection.objects.link(o)
        return o
    add("AREA", (0.0, -0.3, 0.95), 14.0 * base, (0.45, 0.7, 1.0), 1.4, (0, 0, 0))
    add("POINT", (-0.9, -0.7, -0.35), 22.0 * base, (1.0, 0.5, 0.15), 0.3)
    add("POINT", (0.9, -0.7, -0.35), 22.0 * base, (1.0, 0.5, 0.15), 0.3)
    add("POINT", (0.0, -0.9, -0.2), 12.0 * base, (0.2, 1.0, 0.9), 0.3)
    add("POINT", (0.0, 0.2, 0.7), 8.0 * base, (0.7, 0.8, 1.0), 0.4)
    if red > 0.0:
        add("POINT", (0.0, -0.5, 0.7), 900.0 * red, (1.0, 0.03, 0.02), 0.3)
        add("POINT", (-1.0, -0.2, 0.2), 700.0 * red, (1.0, 0.04, 0.02), 0.3)
        add("POINT", (1.0, -0.2, 0.2), 700.0 * red, (1.0, 0.04, 0.02), 0.3)
        add("POINT", (0.0, -0.7, -0.15), 500.0 * red, (1.0, 0.03, 0.02), 0.3)


# ------------------------------------------------------------------------------------------------------------------ damage states
def _set(ob, show):
    ob.hide_render = not show
    ob.hide_viewport = not show


def apply_state(level, spec, objs, eobjs, model, mats):
    """Shows the damage of `level` (a dict of spec['levels'][Sx]): swaps pipes / wires for the torn variants, red lamps, dead monitors, fires, scorch, sparks, steam puffs."""
    burst = level.get("Pipe_Burst", [])
    for nm in burst:
        _set(objs[nm], True)
        _set(objs[objs[nm]["replaces"]], False)
    for nm in level.get("Wire_Snapped", []):
        _set(objs[nm], True)
        _set(objs[objs[nm]["replaces"]], False)
    warn = set(level.get("Lamp_Warn", []))
    for p in model.parts:
        if p.kind == "Lamp":
            ob = objs[p.name]
            if p.name.startswith("Lamp_Warn"):
                ob["lamp_hue"] = 0.0 if p.name in warn else 0.08
                ob["lamp_on"] = 1.0 if p.name in warn else 0.15
            else:
                ob["lamp_on"] = 0.0 if p.name in set(level.get("Lamp_Ok", [])) else 0.6
    dead, glitch = set(level.get("Mon_dead", [])), set(level.get("Mon_glitch", []))
    for p in model.parts:
        if p.kind == "Mon":
            objs[p.name]["screen_on"] = 0.0 if p.name in dead else 0.35 if p.name in glitch else 1.0
    for nm in level.get("Scorch_Decal", []):
        _set(objs[nm], True)
    return objs


def hide_decals(objs, model):
    for p in model.parts:
        if p.kind == "Scorch_Decal":
            _set(objs[p.name], False)


def add_effects(level, eobjs, steam_names, strong=False):
    """Visual stand-ins for the particle effects: translucent steam cones, spark dots, fire cones with a light."""
    mat_steam = bpy.data.materials.new("FX_Steam")
    mat_steam.use_nodes = True
    nt = mat_steam.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    dif = nt.nodes.new("ShaderNodeEmission")
    dif.inputs["Color"].default_value = (0.8, 0.85, 0.9, 1)
    dif.inputs["Strength"].default_value = 0.6
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.22
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(dif.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    mat_fire = bpy.data.materials.new("FX_Fire")
    mat_fire.use_nodes = True
    nt = mat_fire.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (1.0, 0.75, 0.12, 1)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (0.8, 0.04, 0.0, 1)
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 2.4
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mixf = nt.nodes.new("ShaderNodeMixShader")
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "POWER"
    inv.inputs[1].default_value = 2.0
    nt.links.new(sep.outputs["Z"], inv.inputs[0])
    nt.links.new(inv.outputs["Value"], mixf.inputs["Fac"])
    nt.links.new(em.outputs["Emission"], mixf.inputs[1])
    nt.links.new(tr.outputs["BSDF"], mixf.inputs[2])
    nt.links.new(mixf.outputs["Shader"], out.inputs["Surface"])
    mat_spark = bpy.data.materials.new("FX_Spark")
    mat_spark.use_nodes = True
    nt = mat_spark.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.85, 0.4, 1)
    em.inputs["Strength"].default_value = 60.0
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])

    def cone(loc, direction, length, r0, r1, mat, name):
        bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=r0, radius2=r1, depth=length, location=(0, 0, 0))
        ob = bpy.context.active_object
        ob.name = name
        ob.data.materials.append(mat)
        d = Vector(direction).normalized()
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d)
        ob.location = Vector(loc) + d * length / 2
        return ob

    rng = random.Random(3)
    for nm in level.get("SteamPort", steam_names[:1] if not strong else steam_names[:3]):
        e = eobjs[nm]
        d = Vector((1, 0, 0))
        d.rotate(e.rotation_quaternion)
        cone(e.location, d, rng.uniform(0.35, 0.6), 0.01, 0.1, mat_steam, "FXsteam")
    for nm in eobjs:
        if nm.startswith("SparkPort_") and nm in level.get("_sparks", []):
            e = eobjs[nm]
            for k in range(7):
                d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.2, 1)))
                cone(e.location, d, rng.uniform(0.06, 0.2), 0.004, 0.0005, mat_spark, "FXspark")
    for nm in level.get("Fire_Socket", []):
        e = eobjs[nm]
        for k in range(7):
            d = Vector((rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25), 1.0))
            cone(e.location + Vector((rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), 0)), d, rng.uniform(0.15, 0.4), 0.05, 0.003, mat_fire, "FXfire")
        ld = bpy.data.lights.new("fire", "POINT")
        ld.energy = 260.0
        ld.color = (1.0, 0.45, 0.1)
        lo = bpy.data.objects.new("fire", ld)
        lo.location = e.location + Vector((0, 0, 0.15))
        bpy.context.scene.collection.objects.link(lo)


def apply_cracks(masks_dir, k_list, mats):
    """Crack masks into the glass shader: white scattering lines where the mask is bright (transparent elsewhere)."""
    m = mats["M_Glass"]
    nt = m.node_tree
    out = [n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"][0]
    glass = [n for n in nt.nodes if n.type == "BSDF_GLASS"][0]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    prev = None
    for k in k_list:
        img = bpy.data.images.load(os.path.join(masks_dir, "Glass_Crack_Mask_%02d.png" % k))
        img.colorspace_settings.name = "Non-Color"
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.extension = "EXTEND"
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
        mp.inputs["Location"].default_value = (0.1 * k, 0.07 * k, 0)
        nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
        if prev is None:
            prev = tex.outputs["Color"]
        else:
            mx = nt.nodes.new("ShaderNodeMath")
            mx.operation = "MAXIMUM"
            nt.links.new(prev, mx.inputs[0])
            nt.links.new(tex.outputs["Color"], mx.inputs[1])
            prev = mx.outputs["Value"]
    white = nt.nodes.new("ShaderNodeEmission")
    white.inputs["Color"].default_value = (0.9, 0.95, 1.0, 1)
    white.inputs["Strength"].default_value = 0.9
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(prev, mix.inputs["Fac"])
    nt.links.new(glass.outputs["BSDF"], mix.inputs[1])
    nt.links.new(white.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])


# ------------------------------------------------------------------------------------------------------------------ measurement views
def flat_material(color, name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def read_image(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    return px


def glass_share(objs, model, out_png, w=1280, h=720):
    """Percentage of the frame covered by glass: a flat white-on-black render (emission only) from the eye camera, 90 deg horizontal FOV, 16:9."""
    white, black = flat_material((1, 1, 1), "MaskWhite"), flat_material((0, 0, 0), "MaskBlack")
    for p in model.parts:
        ob = objs[p.name]
        if not ob.hide_render:
            for i in range(len(ob.data.materials)):
                ob.data.materials[i] = white if p.kind == "Glass" else black
    for ob in objs.values():
        pass
    bpy.context.scene.world = None
    w_ = bpy.data.worlds.new("black")
    w_.use_nodes = True
    w_.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    bpy.context.scene.world = w_
    setup_render(w, h, 8)
    bpy.context.scene.cycles.use_denoising = False
    bpy.context.scene.view_settings.view_transform = "Standard"
    eye_camera()
    bpy.context.scene.render.filepath = out_png
    bpy.ops.render.render(write_still=True)
    px = read_image(out_png)
    mask = px[..., 0] > 0.5
    return float(mask.mean()) * 100.0

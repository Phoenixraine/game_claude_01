"""bpy layer of cockpit v2: Model -> Blender objects, collections, procedural materials, exports, renders, glass-share measurement."""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

from .geo import frame_from, unit


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


# ------------------------------------------------------------------------------------------------------------------ objects
def mesh_object(name, mb, mats, coll):
    me = bpy.data.meshes.new(name)
    P, T, M, UV = mb.arrays()
    me.from_pydata(P.tolist(), [], T.tolist())
    me.update()
    used = sorted(set(int(m) for m in M))
    remap = {m: i for i, m in enumerate(used)}
    for m in used:
        me.materials.append(mats[mb.mats[m]])
    me.polygons.foreach_set("material_index", np.array([remap[int(m)] for m in M], np.int32))
    uvl = me.uv_layers.new(name="UVMap")
    uvl.data.foreach_set("uv", UV.reshape(-1, 2).astype(np.float32).ravel())
    for p in me.polygons:
        p.use_smooth = True
    me.validate()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def empty_object(e, coll):
    ob = bpy.data.objects.new(e.name, None)
    ob.empty_display_type = "SINGLE_ARROW" if e.kind in ("SteamPort", "SparkPort", "LeakPoint", "AlarmBeaconAxis") else "PLAIN_AXES"
    ob.empty_display_size = 0.05
    ob.location = Vector(e.pos)
    F = frame_from(e.dir)                               # +X of the empty points along `dir`
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Matrix(F.tolist()).to_quaternion()
    for k, v in e.meta.items():
        if isinstance(v, (str, int, float, bool)):
            ob[k] = v
    ob["kind"] = e.kind
    coll.objects.link(ob)
    return ob


def build_scene(model):
    reset()
    sc = bpy.context.scene
    root = sc.collection
    colls = {}
    for nm in ("Cockpit_Intact", "Cockpit_Variants_Burst", "Cockpit_Variants_Snapped", "Cockpit_Sockets"):
        c = bpy.data.collections.new(nm)
        root.children.link(c)
        colls[nm] = c
    mats = make_materials()
    objs = {}
    for p in model.parts:
        coll = colls["Cockpit_Variants_Burst"] if p.kind == "Pipe_Burst" else colls["Cockpit_Variants_Snapped"] if p.kind == "Wire_Snapped" else colls["Cockpit_Intact"]
        ob = mesh_object(p.name, p.mb, mats, coll)
        ob["kind"] = p.kind
        ob["default_visible"] = bool(p.visible)
        for k, v in p.meta.items():
            if isinstance(v, (str, int, float, bool)):
                ob[k] = v
        if p.kind == "Lamp":
            ob["lamp_hue"] = 0.0 if p.meta.get("class") == "Warn" else 0.33
        if not p.visible:
            ob.hide_render = True
            ob.hide_viewport = True
        objs[p.name] = ob
    eobjs = {}
    for e in model.empties:
        eobjs[e.name] = empty_object(e, colls["Cockpit_Sockets"])
    return objs, eobjs, mats


# ------------------------------------------------------------------------------------------------------------------ materials
def _principled(nt, **kw):
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    for k, v in kw.items():
        if k in b.inputs:
            b.inputs[k].default_value = v
    return b


def _mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out


def _rand_node(nt):
    n = nt.nodes.new("ShaderNodeObjectInfo")
    return n.outputs["Random"]


def make_materials():
    mats = {}

    def metal(name, base, rough, metallic, noise_scale=40.0):
        m, nt, out = _mat(name)
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = noise_scale
        nz.inputs["Detail"].default_value = 8.0
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (base[0] * 0.5, base[1] * 0.5, base[2] * 0.5, 1)
        ramp.color_ramp.elements[1].color = (*base, 1)
        nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
        bs = _principled(nt, Roughness=rough, Metallic=metallic)
        nt.links.new(ramp.outputs["Color"], bs.inputs["Base Color"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.15
        nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bs.inputs["Normal"])
        nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
        mats[name] = m

    metal("M_Frame", (0.045, 0.047, 0.055), 0.45, 0.8)
    metal("M_FrameDark", (0.025, 0.026, 0.03), 0.55, 0.7)
    metal("M_Metal", (0.22, 0.23, 0.25), 0.35, 0.95)
    metal("M_MetalDark", (0.07, 0.07, 0.08), 0.5, 0.85)
    metal("M_PaintOrange", (0.62, 0.22, 0.02), 0.4, 0.2)
    metal("M_Rubber", (0.02, 0.02, 0.022), 0.8, 0.0)
    metal("M_Scorch", (0.02, 0.015, 0.012), 0.9, 0.2)
    metal("M_Copper", (0.7, 0.32, 0.12), 0.3, 1.0, 120.0)
    # pipes: colour varies per object (random)
    m, nt, out = _mat("M_Pipe")
    r = _rand_node(nt)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cols = [(0.05, 0.05, 0.055), (0.12, 0.12, 0.13), (0.35, 0.12, 0.02), (0.06, 0.09, 0.13), (0.2, 0.2, 0.2)]
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (*cols[0], 1)
    for k, c in enumerate(cols[1:]):
        e = ramp.color_ramp.elements.new((k + 1) / len(cols))
        e.color = (*c, 1)
    nt.links.new(r, ramp.inputs["Fac"])
    bs = _principled(nt, Roughness=0.4, Metallic=0.85)
    nt.links.new(ramp.outputs["Color"], bs.inputs["Base Color"])
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    mats["M_Pipe"] = m
    metal("M_Insulation", (0.16, 0.15, 0.13), 0.9, 0.0, 15.0)
    m, nt, out = _mat("M_Wire")
    r = _rand_node(nt)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    wc = [(0.01, 0.01, 0.01), (0.2, 0.02, 0.02), (0.02, 0.05, 0.2), (0.35, 0.28, 0.02), (0.02, 0.02, 0.02)]
    ramp.color_ramp.elements[0].color = (*wc[0], 1)
    for k, c in enumerate(wc[1:]):
        e = ramp.color_ramp.elements.new((k + 1) / len(wc))
        e.color = (*c, 1)
    nt.links.new(r, ramp.inputs["Fac"])
    bs = _principled(nt, Roughness=0.35, Metallic=0.0)
    nt.links.new(ramp.outputs["Color"], bs.inputs["Base Color"])
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    mats["M_Wire"] = m
    metal("M_WireTape", (0.4, 0.33, 0.02), 0.6, 0.0)
    # buttons: random cap colour
    m, nt, out = _mat("M_Button")
    r = _rand_node(nt)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    bc = [(0.5, 0.04, 0.02), (0.02, 0.35, 0.06), (0.6, 0.38, 0.02), (0.55, 0.55, 0.5), (0.04, 0.04, 0.05)]
    ramp.color_ramp.elements[0].color = (*bc[0], 1)
    for k, c in enumerate(bc[1:]):
        e = ramp.color_ramp.elements.new((k + 1) / len(bc))
        e.color = (*c, 1)
    nt.links.new(r, ramp.inputs["Fac"])
    bs = _principled(nt, Roughness=0.35)
    nt.links.new(ramp.outputs["Color"], bs.inputs["Base Color"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 0.8
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(bs.outputs["BSDF"], add.inputs[0])
    nt.links.new(em.outputs["Emission"], add.inputs[1])
    nt.links.new(add.outputs["Shader"], out.inputs["Surface"])
    mats["M_Button"] = m
    # lamps: hue from the object property lamp_hue (0 red/orange, 0.33 green); strength from lamp_on (default 1)
    m, nt, out = _mat("M_Lamp")
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_type = "OBJECT"
    at.attribute_name = "lamp_hue"
    hsv = nt.nodes.new("ShaderNodeCombineColor")
    hsv.mode = "HSV"
    nt.links.new(at.outputs["Fac"], hsv.inputs["Red"])
    hsv.inputs["Green"].default_value = 1.0
    hsv.inputs["Blue"].default_value = 1.0
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 6.0
    nt.links.new(hsv.outputs["Color"], em.inputs["Color"])
    at2 = nt.nodes.new("ShaderNodeAttribute")
    at2.attribute_type = "OBJECT"
    at2.attribute_name = "lamp_on"
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 7.0
    nt.links.new(at2.outputs["Fac"], mul.inputs[0])
    nt.links.new(mul.outputs["Value"], em.inputs["Strength"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    mats["M_Lamp"] = m
    metal("M_MonitorFrame", (0.03, 0.03, 0.035), 0.4, 0.6)
    # monitors: cyan radar / graph pattern, random phase
    m, nt, out = _mat("M_Monitor")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.wave_type = "RINGS"
    wv.inputs["Scale"].default_value = 9.0
    wv.inputs["Distortion"].default_value = 0.4
    nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
    sc = nt.nodes.new("ShaderNodeTexWave")
    sc.wave_type = "BANDS"
    sc.bands_direction = "Y"
    sc.inputs["Scale"].default_value = 90.0
    nt.links.new(tc.outputs["UV"], sc.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.0, 0.03, 0.04, 1)
    ramp.color_ramp.elements[1].color = (0.15, 1.0, 0.85, 1)
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[1].position = 0.75
    nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"])
    mul2 = nt.nodes.new("ShaderNodeMixRGB")
    mul2.blend_type = "MULTIPLY"
    mul2.inputs["Fac"].default_value = 0.35
    nt.links.new(ramp.outputs["Color"], mul2.inputs["Color1"])
    nt.links.new(sc.outputs["Fac"], mul2.inputs["Color2"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(mul2.outputs["Color"], em.inputs["Color"])
    at3 = nt.nodes.new("ShaderNodeAttribute")
    at3.attribute_type = "OBJECT"
    at3.attribute_name = "screen_on"
    mu = nt.nodes.new("ShaderNodeMath")
    mu.operation = "MULTIPLY"
    mu.inputs[1].default_value = 2.2
    nt.links.new(at3.outputs["Fac"], mu.inputs[0])
    nt.links.new(mu.outputs["Value"], em.inputs["Strength"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    mats["M_Monitor"] = m
    # glass: clear with a droplet roughness pattern; the crack mask image (if present) is mixed in as scattering white lines
    m, nt, out = _mat("M_Glass")
    gl = nt.nodes.new("ShaderNodeBsdfGlass")
    gl.inputs["IOR"].default_value = 1.45
    gl.inputs["Roughness"].default_value = 0.03
    gl.inputs["Color"].default_value = (0.8, 0.95, 1.0, 1)
    nt.links.new(gl.outputs["BSDF"], out.inputs["Surface"])
    mats["M_Glass"] = m
    m, nt, out = _mat("M_Decal_Scorch")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 5.0
    nt.links.new(tc.outputs["UV"], nz.inputs["Vector"])
    rg = nt.nodes.new("ShaderNodeTexGradient")
    rg.gradient_type = "SPHERICAL"
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Location"].default_value = (-0.5, -0.5, 0)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], rg.inputs["Vector"])
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(rg.outputs["Fac"], inv.inputs[1])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(inv.outputs["Value"], mul.inputs[0])
    nt.links.new(nz.outputs["Fac"], mul.inputs[1])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    bk = _principled(nt, **{"Base Color": (0.005, 0.004, 0.004, 1), "Roughness": 0.9})
    mix = nt.nodes.new("ShaderNodeMixShader")
    mulb = nt.nodes.new("ShaderNodeMath")
    mulb.operation = "MULTIPLY"
    mulb.inputs[1].default_value = 2.2
    nt.links.new(mul.outputs["Value"], mulb.inputs[0])
    nt.links.new(mulb.outputs["Value"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(bk.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    mats["M_Decal_Scorch"] = m
    return mats

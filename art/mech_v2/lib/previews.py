"""Poster-style preview renders (Cycles CPU) with the generated PBR sets applied: cold rim light + warm accent, wet ground, bloom on the glow."""
import math
import os

import bpy
import numpy as np
from mathutils import Vector

from . import hs, render

PBR_MATS = hs.MATERIALS


def apply_pbr(tex_dir, prefix):
    """Replace the plain PBR materials by image-driven ones (BaseColor / Normal / ORM / Emissive of set `prefix`)."""
    for name, mat in hs.REG.materials.items():
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

        def img(kind, cs):
            fn = os.path.join(tex_dir, "T_%s_%s_%s.png" % (prefix, name.replace("M_", ""), kind))
            im = bpy.data.images.load(fn, check_existing=True)
            im.colorspace_settings.name = cs
            n = nt.nodes.new("ShaderNodeTexImage")
            n.image = im
            n.interpolation = "Linear"
            return n
        base = img("BaseColor", "sRGB")
        orm = img("ORM", "Non-Color")
        nrm = img("Normal", "Non-Color")
        em = img("Emissive", "sRGB")
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 0.85
        nt.links.new(base.outputs["Color"], mul.inputs["A"])
        nt.links.new(sep.outputs["Red"], mul.inputs["B"])
        nt.links.new(mul.outputs["Result"], bsdf.inputs["Base Color"])
        nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
        nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 1.0
        nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        nt.links.new(em.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 9.0 if name == "M_Emissive_Status" else 0.0
        if name == "M_Glass_Sensor":
            bsdf.inputs["Specular IOR Level"].default_value = 1.0
            bsdf.inputs["Coat Weight"].default_value = 1.0
            bsdf.inputs["Coat Roughness"].default_value = 0.03


def poster_world(sc, top=(0.035, 0.05, 0.085), horizon=(0.35, 0.22, 0.14), strength=1.0):
    w = bpy.data.worlds.new("Poster")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.42
    ramp.color_ramp.elements[0].color = (*horizon, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (*top, 1)
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def add_area(name, loc, target, energy, color, size, shape="RECTANGLE"):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.color = color
    ld.size = size
    ld.shape = "SQUARE" if shape != "RECTANGLE" else "RECTANGLE"
    if shape == "RECTANGLE":
        ld.size_y = size * 0.5
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


def poster_lights(centre=(0, 0, 40), scale=1.0, rim_side=1.0, warm_side=-1.0):
    for o in [o for o in bpy.data.objects if o.name.startswith("L_")]:
        bpy.data.objects.remove(o)
    c = Vector(centre)
    S = scale
    # cold rim from behind-left, warm accent from low front-right, soft cool fill from above
    add_area("L_rim", c + Vector((-90 * rim_side * S, 140 * S, 70 * S)), c, 5.5e6 * S * S, (0.55, 0.72, 1.0), 120 * S)
    add_area("L_rim2", c + Vector((110 * rim_side * S, 110 * S, 60 * S)), c, 3.0e6 * S * S, (0.6, 0.75, 1.0), 90 * S)
    add_area("L_warm", c + Vector((120 * warm_side * S, -150 * S, 25 * S)), c, 4.0e6 * S * S, (1.0, 0.55, 0.25), 80 * S)
    add_area("L_fill", c + Vector((0, -200 * S, 160 * S)), c, 2.0e6 * S * S, (0.7, 0.8, 1.0), 200 * S)
    # a low warm bounce from the street
    add_area("L_street", c + Vector((0, -60 * S, -30 * S)), c + Vector((0, 0, 20 * S)), 0.6e6 * S * S, (1.0, 0.6, 0.3), 120 * S)


def wet_ground():
    render.ground(900, 0.0, (0.03, 0.032, 0.036))
    g = bpy.data.objects["Ground"]
    m = g.data.materials[0]
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.09
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.8
    return g


def bloom(path, strength=0.5, radius=18):
    from PIL import Image, ImageFilter
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32) / 255.0
    lum = a.max(axis=2)
    bright = np.clip((lum - 0.8) / 0.2, 0, 1)[..., None] * a
    bl = Image.fromarray((bright * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius))
    bl2 = Image.fromarray((bright * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius * 3))
    out = np.clip(a + strength * (np.asarray(bl).astype(np.float32) / 255 + 0.7 * np.asarray(bl2).astype(np.float32) / 255), 0, 1)
    # gentle vignette
    h, w = out.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    v = 1.0 - 0.28 * (((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) * 0.5
    Image.fromarray((np.clip(out * v[..., None], 0, 1) * 255).astype(np.uint8)).save(path)


def _hide(objs, state):
    for o in objs:
        o.hide_render = state
        o.hide_viewport = state


def _by_prefix(*prefixes, pool=None):
    pool = pool if pool is not None else list(hs.REG.parts) + list(hs.REG.variants)
    return [o for o in pool if o.name.startswith(prefixes)]


def render_all(P, out_dir, tex_dir, only, quick, arm):
    import importlib
    sc = bpy.context.scene
    samples = 24 if quick else 96
    want = lambda n: only is None or n in only
    res_wide, res_tall, res_sq = (1600, 1000), (1000, 1400), (1200, 1200)
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.render.film_transparent = False
    poster_world(sc)
    wet_ground()
    var = list(hs.REG.variants)
    _hide(var, True)
    o = lambda n: os.path.join(out_dir, n)
    H = P["height"]
    mid = Vector((0, 0, H * 0.5))

    def shot(name, loc, tgt, lens, res=res_wide, light_c=None, bl=0.5):
        render.hero(o(name), loc, tgt, lens=lens, res=res, samples=samples)
        bloom(o(name), bl)

    apply_pbr(tex_dir, "BASTION")
    poster_lights((0, 0, 42), 1.0)
    if want("three_quarter"):
        shot("preview_three_quarter.png", (95, -165, 36), (0, 0, 41), 45, res_tall)
    if want("front"):
        shot("preview_front.png", (0, -230, 38), (0, 0, 41), 60, res_tall)
    if want("side"):
        poster_lights((0, 0, 42), 1.0, rim_side=-1.0, warm_side=1.0)
        shot("preview_side.png", (230, 0, 38), (0, 0, 41), 60, res_tall)
    if want("back"):
        poster_lights((0, 0, 42), 1.0, rim_side=1.0, warm_side=-1.0)
        add_area("L_backkey", Vector((80, 160, 60)), Vector((0, 0, 40)), 3.0e6, (0.9, 0.85, 0.8), 80)
        shot("preview_back.png", (-30, 240, 38), (0, 0, 41), 60, res_tall)
        poster_lights((0, 0, 42), 1.0)
    if want("detail_head"):
        shot("preview_detail_head.png", (30, -52, 80), (0, -3, 74), 60, res_wide)
    if want("detail_fist"):
        shot("preview_detail_fist.png", (-52, -42, 38), (-14, -6, 31), 55, res_wide)
    if want("detail_leg"):
        shot("preview_detail_leg.png", (60, -76, 22), (8, -2, 18), 50, res_wide)
    if want("damage"):
        plates = _by_prefix("Armor_ArmR_", "Armor_ShoulderR_", "Armor_LegL_0", pool=hs.REG.parts)
        dents = [x for x in var if x.name.endswith("_dent") and ("_Torso_" in x.name or "_LegL_" in x.name or "ShoulderL" in x.name)]
        origs = [bpy.data.objects[d["dent_of"]] for d in dents]
        dmg = [x for x in var if x.name.endswith("_dmg") and ("ArmR" in x.name or "ShoulderR" in x.name or "LegL" in x.name or "Torso" in x.name)]
        hide = [p for p in plates if not p.name.startswith("Armor_LegL_0") or True][:0]
        arm_plates = _by_prefix("Armor_ArmR_", "Armor_ShoulderR_", pool=hs.REG.parts)
        _hide(arm_plates, True)
        _hide(origs, True)
        _hide(dents, False)
        _hide(dmg, False)
        shot("preview_damage_arm.png", (-95, -105, 52), (-22, -2, 52), 52, res_wide)
        _hide(arm_plates, False)
        _hide(origs, False)
        _hide(dents + dmg, True)
    if want("scale"):
        props = render.scale_props()
        poster_lights((0, 0, 42), 1.0)
        shot("preview_scale.png", (-25, -300, 92), (-30, 0, 88), 30, (1600, 900))
        render.remove_objs(props)
    if want("enemy"):
        apply_pbr(tex_dir, "ENEMY")
        heads = _by_prefix("Body_head", pool=hs.REG.parts)
        sh_plates = _by_prefix("Armor_ShoulderL_", "Armor_ShoulderR_", pool=hs.REG.parts)
        en = [x for x in var if x.name.endswith("_enemy")]
        _hide(heads + sh_plates, True)
        _hide(en, False)
        poster_lights((0, 0, 42), 1.0, rim_side=1.0, warm_side=-1.0)
        shot("preview_enemy.png", (-95, -165, 36), (0, 0, 41), 45, res_tall)
        _hide(heads + sh_plates, False)
        _hide(en, True)
        apply_pbr(tex_dir, "BASTION")
    _hide(var, True)

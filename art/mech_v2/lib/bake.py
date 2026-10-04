"""Cycles bake of geometry-driven maps into the per-material atlases (all parts at once): AO (short + long range), thickness, world normal,
world position and a per-object random id. The maps are read back as numpy arrays for the wear/texture synthesis (`textures.py`)."""
import bpy
import numpy as np

from . import hs


def _material_nodes(mat):
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    return nt, out


class _Emit:
    """Context manager: replaces the surface of every mech material with an emission built by `make(nt) -> socket`, plus an active image node."""

    def __init__(self, images, make):
        self.images, self.make = images, make

    def __enter__(self):
        self.saved = {}
        for name, mat in hs.REG.materials.items():
            nt, out = _material_nodes(mat)
            link = out.inputs["Surface"].links[0] if out.inputs["Surface"].links else None
            self.saved[name] = (link.from_socket if link else None)
            em = nt.nodes.new("ShaderNodeEmission")
            em.name = "_bake_emit"
            nt.links.new(self.make(nt), em.inputs["Color"])
            nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
            img = nt.nodes.new("ShaderNodeTexImage")
            img.name = "_bake_img"
            img.image = self.images[name]
            nt.nodes.active = img
        return self

    def __exit__(self, *a):
        for name, mat in hs.REG.materials.items():
            nt, out = _material_nodes(mat)
            for n in ("_bake_emit", "_bake_img"):
                if n in nt.nodes:
                    nt.nodes.remove(nt.nodes[n])
            if self.saved[name] is not None:
                nt.links.new(self.saved[name], out.inputs["Surface"])


def _images(res, tag, float_buffer=True):
    imgs = {}
    for name in hs.MATERIALS:
        im = bpy.data.images.new("bake_%s_%s" % (tag, name), res, res, alpha=False, float_buffer=float_buffer)
        im.colorspace_settings.name = "Non-Color"
        imgs[name] = im
    return imgs


def _read(imgs, channels=3):
    out = {}
    for name, im in imgs.items():
        a = np.empty(len(im.pixels), dtype=np.float32)
        im.pixels.foreach_get(a)
        a = a.reshape(im.size[1], im.size[0], 4)[..., :channels]
        out[name] = a[::-1].copy()      # row 0 = top (image space), matching PNG writing
        bpy.data.images.remove(im)
    return out


def _select_parts():
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in hs.REG.parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = hs.REG.parts[0]


def _bake(btype, **kw):
    _select_parts()
    bpy.ops.object.bake(type=btype, use_selected_to_active=False, target="IMAGE_TEXTURES", use_clear=True, **kw)


def setup(res_samples=16, margin=6):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = res_samples
    sc.cycles.use_denoising = False
    sc.render.bake.margin = margin
    sc.render.bake.margin_type = "EXTEND"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("W")


def bake_ao(res, distance, samples=16, tag="ao"):
    sc = bpy.context.scene
    setup(samples)
    sc.world.light_settings.distance = distance
    imgs = _images(res, tag)
    with _Emit(imgs, lambda nt: nt.nodes.new("ShaderNodeRGB").outputs[0]):    # surface irrelevant for AO bake
        _bake("AO")
    return _read(imgs, 1)[...] if False else {k: v[..., 0] for k, v in _read(imgs, 1).items()}


def bake_emit(res, make, tag, samples=1, margin=6):
    setup(samples, margin)
    imgs = _images(res, tag)
    with _Emit(imgs, make):
        _bake("EMIT")
    return _read(imgs, 3)


def bake_normal(res, tag="nrm"):
    setup(4)
    imgs = _images(res, tag)
    with _Emit(imgs, lambda nt: nt.nodes.new("ShaderNodeRGB").outputs[0]):
        _bake("NORMAL", normal_space="OBJECT")
    return _read(imgs, 3)


POS_RANGE = 200.0     # world position is stored as p / POS_RANGE + 0.5 (emission cannot be negative)


def make_position(nt):
    g = nt.nodes.new("ShaderNodeNewGeometry")
    m = nt.nodes.new("ShaderNodeVectorMath")
    m.operation = "SCALE"
    m.inputs["Scale"].default_value = 1.0 / POS_RANGE
    nt.links.new(g.outputs["Position"], m.inputs[0])
    a = nt.nodes.new("ShaderNodeVectorMath")
    a.operation = "ADD"
    a.inputs[1].default_value = (0.5, 0.5, 0.5)
    nt.links.new(m.outputs[0], a.inputs[0])
    return a.outputs[0]


def make_const(nt, v=1.0):
    n = nt.nodes.new("ShaderNodeRGB")
    n.outputs[0].default_value = (v, v, v, 1.0)
    return n.outputs[0]


def make_random(nt):
    o = nt.nodes.new("ShaderNodeObjectInfo")
    c = nt.nodes.new("ShaderNodeCombineXYZ")
    for i in range(3):
        nt.links.new(o.outputs["Random"], c.inputs[i])
    return c.outputs[0]


def make_packed_ao(nt, d_short=2.5, d_long=30.0, d_thick=3.0, samples=16):
    """R = AO within d_short, G = AO within d_long, B = thickness (AO from the inside within d_thick)."""
    c = nt.nodes.new("ShaderNodeCombineXYZ")
    for i, (dist, inside) in enumerate(((d_short, False), (d_long, False), (d_thick, True))):
        ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
        ao.inside = inside
        ao.samples = samples
        ao.inputs["Distance"].default_value = dist
        nt.links.new(ao.outputs["AO"], c.inputs[i])
    return c.outputs[0]


def make_rid_cover(nt):
    """R = per-object random id (0..1), G = 1 (coverage), B = 0."""
    o = nt.nodes.new("ShaderNodeObjectInfo")
    c = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(o.outputs["Random"], c.inputs[0])
    c.inputs[1].default_value = 1.0
    return c.outputs[0]


def make_thickness(nt, distance=3.0):
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.inside = True
    ao.samples = 16
    ao.inputs["Distance"].default_value = distance
    c = nt.nodes.new("ShaderNodeCombineXYZ")
    for i in range(3):
        nt.links.new(ao.outputs["Color"] if False else ao.outputs["AO"], c.inputs[i])
    return c.outputs[0]

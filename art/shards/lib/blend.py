"""bpy layer: library meshes -> Blender objects with procedural PBR-ish materials, FBX/GLB export, preview renders. Needs `bpy` (pip module or Blender)."""
import math
import os

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

from . import geom as g

MAT_STYLE = {
    "M_Concrete_Old": dict(base=(0.17, 0.17, 0.165), dark=(0.06, 0.06, 0.055), rough=0.85, metal=0.0, scale=7.0),
    "M_Fracture": dict(base=(0.30, 0.28, 0.25), dark=(0.09, 0.08, 0.07), rough=0.95, metal=0.0, scale=14.0),
    "M_Glass_Shard": dict(base=(0.65, 0.85, 0.82), dark=(0.5, 0.7, 0.7), rough=0.04, metal=0.0, scale=3.0, glass=True),
    "M_Steel_Rust": dict(base=(0.09, 0.095, 0.10), dark=(0.30, 0.12, 0.05), rough=0.5, metal=0.6, scale=9.0, rust=True),
    "M_Rebar": dict(base=(0.30, 0.17, 0.10), dark=(0.12, 0.07, 0.05), rough=0.6, metal=0.7, scale=25.0),
    "M_Gravel": dict(base=(0.24, 0.23, 0.21), dark=(0.09, 0.085, 0.08), rough=0.9, metal=0.0, scale=40.0),
}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_materials(names):
    mats = {}
    for n in names:
        st = MAT_STYLE[n]
        m = bpy.data.materials.new(n)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        tc = nt.nodes.new("ShaderNodeTexCoord")
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = st["scale"]
        noise.inputs["Detail"].default_value = 8.0
        noise.inputs["Roughness"].default_value = 0.65
        nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (*st["dark"], 1)
        ramp.color_ramp.elements[1].color = (*st["base"], 1)
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[1].position = 0.7
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = st["rough"]
        bsdf.inputs["Metallic"].default_value = st["metal"]
        if st.get("glass"):
            bsdf.inputs["Transmission Weight"].default_value = 0.55
            bsdf.inputs["IOR"].default_value = 1.5
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.6
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        mats[n] = m
    return mats


def mesh_to_object(mesh, name, mats, collection=None, smooth_deg=22):
    me = bpy.data.meshes.new(name)
    me.from_pydata(mesh.v.tolist(), [], mesh.t.tolist())
    me.update()
    for n in mesh.mats:
        me.materials.append(mats[n])
    me.polygons.foreach_set("material_index", mesh.m.astype(np.int32))
    uvl = me.uv_layers.new(name="UVMap")
    flat = mesh.uv.reshape(-1, 2).astype(np.float32).ravel()
    uvl.data.foreach_set("uv", flat)
    bm = bmesh.new()
    bm.from_mesh(me)
    ang = math.radians(60 if mesh.smooth else smooth_deg)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) < ang
        else:
            e.smooth = False
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def solid_to_ucx(solid, name):
    mb = g.MB(["M_Fracture"])
    g.tessellate(mb, solid, center=False, base_mat="M_Fracture")
    m = mb.finish(name)
    me = bpy.data.meshes.new(name)
    me.from_pydata(m.v.tolist(), [], m.t.tolist())
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _select(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def export_fbx(path, objs):
    _select(objs)
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0, axis_forward="-Y", axis_up="Z",
                             object_types={"MESH"}, add_leaf_bones=False, bake_anim=False, mesh_smooth_type="EDGE", use_mesh_modifiers=True, bake_space_transform=False,
                             path_mode="AUTO")


def export_glb(path, objs):
    _select(objs)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True, export_materials="EXPORT")


# ------------------------------------------------------------------------------------------------------------------ previews
def setup_render(w, h, samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    sc.cycles.max_bounces = 6
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast" if False else "None"
    sc.render.film_transparent = False


def world_and_lights(strength=1.0):
    sc = bpy.context.scene
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
    ramp.color_ramp.elements[0].color = (0.010, 0.014, 0.024, 1)
    ramp.color_ramp.elements[1].color = (0.05, 0.07, 0.11, 1)
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    def light(kind, loc, rot, energy, color, size=None):
        d = bpy.data.lights.new("L", kind)
        d.energy = energy
        d.color = color
        if size and hasattr(d, "size"):
            d.size = size
        o = bpy.data.objects.new("L", d)
        o.location = loc
        o.rotation_euler = rot
        sc.collection.objects.link(o)
        return o
    return light


def ground(size=60.0, z=0.0):
    me = bpy.data.meshes.new("Ground")
    me.from_pydata([(-size, -size, z), (size, -size, z), (size, size, z), (-size, size, z)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("Ground", me)
    bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new("GroundWet")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.02, 0.022, 0.026, 1)
    bsdf.inputs["Roughness"].default_value = 0.22
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 2.5
    nz.inputs["Detail"].default_value = 6.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.1, 0.1, 0.1, 1)
    ramp.color_ramp.elements[1].color = (0.45, 0.45, 0.45, 1)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Roughness"])
    ob.data.materials.append(m)
    return ob


def camera(loc, target, ortho=None, lens=70.0):
    cam = bpy.data.cameras.new("Cam")
    if ortho:
        cam.type = "ORTHO"
        cam.ortho_scale = ortho
    else:
        cam.lens = lens
    ob = bpy.data.objects.new("Cam", cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    return ob


def lay_flat_matrix(mesh, upright):
    """Display orientation: upright assets keep their orientation; others lie with the smallest principal axis vertical and the longest along +X."""
    if upright:
        return np.eye(3)
    v = mesh.v - mesh.v.mean(axis=0)
    w, V = np.linalg.eigh(v.T @ v)
    ax = V[:, ::-1]            # longest first
    R = np.stack([ax[:, 0], ax[:, 1], ax[:, 2]], axis=0)       # rows: x', y', z'
    if np.linalg.det(R) < 0:
        R[2] *= -1
    return R

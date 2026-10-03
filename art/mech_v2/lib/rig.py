"""Armature `BASTION_Rig` (exact bone names from the Unreal contract) and rigid 1.0-weight binding of every part to one bone."""
import bpy
from mathutils import Vector

from . import hs


def build_armature(bones):
    arm = bpy.data.armatures.new("BASTION_Rig")
    obj = bpy.data.objects.new("BASTION_Rig", arm)
    hs.REG.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = {}
    order = list(bones.keys())
    for name in order:
        head, tail, parent = bones[name]
        e = arm.edit_bones.new(name)
        e.head = Vector(head)
        e.tail = Vector(tail)
        if (e.tail - e.head).length < 0.5:
            e.tail = e.head + Vector((0, 0, 1))
        eb[name] = e
    for name in order:
        parent = bones[name][2]
        if parent:
            eb[name].parent = eb[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    hs.REG.armature = obj
    return obj


def bind_all(arm_obj):
    """Vertex group named after the bone (weight 1.0 on every vertex) + Armature modifier + parent to the rig."""
    for obj in hs.REG.parts:
        bone = obj["bone"]
        assert bone in arm_obj.data.bones, "%s: unknown bone %s" % (obj.name, bone)
        vg = obj.vertex_groups.new(name=bone)
        vg.add([v.index for v in obj.data.vertices], 1.0, "REPLACE")
        mod = obj.modifiers.new("Armature", "ARMATURE")
        mod.object = arm_obj
        obj.parent = arm_obj
        obj.matrix_parent_inverse = arm_obj.matrix_world.inverted()


def bind_variants(arm_obj):
    """Variants (dents, stumps, torn mechanics, enemy parts) share the main rig and weights: 1.0 on the bone they belong to."""
    for obj in hs.REG.variants:
        if obj.get("kind") == "detached" or obj.get("bone") is None or obj.name.startswith("Detached_"):
            continue
        bone = obj["bone"]
        assert bone in arm_obj.data.bones, "%s: unknown bone %s" % (obj.name, bone)
        vg = obj.vertex_groups.new(name=bone)
        vg.add([v.index for v in obj.data.vertices], 1.0, "REPLACE")
        mod = obj.modifiers.new("Armature", "ARMATURE")
        mod.object = arm_obj
        obj.parent = arm_obj
        obj.matrix_parent_inverse = arm_obj.matrix_world.inverted()

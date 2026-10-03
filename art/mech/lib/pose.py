"""Pose tests: joint limits, three poses (stand, right overhead swing, step), a coarse part-clash check on the deformed meshes."""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector
from scipy.spatial import ConvexHull

from . import hs

# World-axis rotation limits per bone in degrees, RELATIVE to the parent's pose: axis -> (min, max).
# X = pitch (positive swings the limb's tip toward +Y, i.e. backwards; negative = forward/up), Y = roll, Z = yaw / side swing.
LIMITS = {
    "pelvis": {"x": (-12, 12), "y": (-8, 8), "z": (-20, 20)},
    "torso": {"x": (-15, 20), "y": (-10, 10), "z": (-40, 40)},
    "head": {"x": (-20, 25), "y": (-10, 10), "z": (-50, 50)},
    "shoulder_l": {"x": (-10, 10), "y": (-5, 5), "z": (-10, 10)}, "shoulder_r": {"x": (-10, 10), "y": (-5, 5), "z": (-10, 10)},
    "upperarm_l": {"x": (-165, 60), "y": (-40, 40), "z": (-10, 80)}, "upperarm_r": {"x": (-165, 60), "y": (-40, 40), "z": (-80, 10)},
    "forearm_l": {"x": (-130, 5), "y": (-30, 30), "z": (-10, 10)}, "forearm_r": {"x": (-130, 5), "y": (-30, 30), "z": (-10, 10)},
    "hand_l": {"x": (-45, 45), "y": (-60, 60), "z": (-30, 30)}, "hand_r": {"x": (-45, 45), "y": (-60, 60), "z": (-30, 30)},
    "thigh_l": {"x": (-60, 35), "y": (-15, 15), "z": (-25, 8)}, "thigh_r": {"x": (-60, 35), "y": (-15, 15), "z": (-8, 25)},
    "shin_l": {"x": (-5, 110), "y": (0, 0), "z": (0, 0)}, "shin_r": {"x": (-5, 110), "y": (0, 0), "z": (0, 0)},
    "foot_l": {"x": (-30, 30), "y": (-10, 10), "z": (-10, 10)}, "foot_r": {"x": (-30, 30), "y": (-10, 10), "z": (-10, 10)},
}

# pose name -> bone -> (rx, ry, rz) degrees, world axes, relative to the parent
POSES = {
    "stand": {"upperarm_l": (4, 0, 3), "upperarm_r": (4, 0, -3), "forearm_l": (-6, 0, 0), "forearm_r": (-6, 0, 0),
              "thigh_l": (0, 0, -2), "thigh_r": (0, 0, 2)},
    "swing_right": {"torso": (0, 0, 24), "upperarm_r": (-135, 0, -24), "forearm_r": (-42, 0, 0), "hand_r": (-14, 0, 0),
                    "upperarm_l": (14, 0, 6), "forearm_l": (-22, 0, 0), "thigh_l": (-6, 0, -3), "thigh_r": (8, 0, 3),
                    "shin_r": (6, 0, 0), "head": (0, 0, -10)},
    "step": {"pelvis": (0, 0, -6), "torso": (0, 0, 7), "thigh_l": (-34, 0, -3), "shin_l": (44, 0, 0), "foot_l": (-10, 0, 0),
             "thigh_r": (14, 0, 3), "shin_r": (10, 0, 0), "foot_r": (-6, 0, 0), "upperarm_r": (20, 0, -4),
             "upperarm_l": (-22, 0, 4), "forearm_l": (-28, 0, 0), "forearm_r": (-10, 0, 0)},
}


def check_limits():
    errs = []
    for pose, bones in POSES.items():
        for b, ang in bones.items():
            lim = LIMITS[b]
            for ax, a in zip("xyz", ang):
                lo, hi = lim[ax]
                if not lo <= a <= hi:
                    errs.append("%s: %s %s=%g outside [%g, %g]" % (pose, b, ax, a, lo, hi))
    return errs


def apply_pose(arm, pose, ground=True):
    """Pose the rig: each bone inherits its parent's posed frame, then rotates about its own (moved) head in WORLD axes."""
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    spec = POSES[pose] if isinstance(pose, str) else pose
    rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
    posed = {}
    order = []
    for b in arm.data.bones:
        depth = 0
        p = b
        while p.parent:
            depth += 1
            p = p.parent
        order.append((depth, b.name))
    for _, name in sorted(order):
        bone = arm.data.bones[name]
        if bone.parent:
            M = posed[bone.parent.name] @ rest[bone.parent.name].inverted() @ rest[name]
        else:
            M = rest[name].copy()
        rx, ry, rz = spec.get(name, (0, 0, 0))
        if rx or ry or rz:
            head = M.translation.copy()
            R = (Matrix.Rotation(math.radians(rz), 4, "Z") @ Matrix.Rotation(math.radians(ry), 4, "Y") @ Matrix.Rotation(math.radians(rx), 4, "X"))
            M = Matrix.Translation(head) @ R @ Matrix.Translation(-head) @ M
        arm.pose.bones[name].matrix = M
        bpy.context.view_layer.update()
        posed[name] = arm.pose.bones[name].matrix.copy()
    bpy.ops.object.mode_set(mode="OBJECT")
    if ground:
        verts = deformed_vertices()
        lowest = min(v[:, 2].min() for v in verts.values())
        arm.pose.bones["root"].location = Vector((0, 0, -lowest))
        bpy.context.view_layer.update()
    return spec


def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def deformed_vertices():
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for o in hs.REG.parts:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        out[o.name] = np.array([ev.matrix_world @ v.co for v in me.vertices])
        ev.to_mesh_clear()
    return out


def _adjacent(arm, a, b):
    """Bones that share a joint (parent/child or equal) are allowed to touch."""
    if a == b:
        return True
    ba, bb = arm.data.bones[a], arm.data.bones[b]
    return ba.parent == bb or bb.parent == ba or ba.parent == bb.parent and ba.parent is not None and ba.parent.name in ("torso", "pelvis")


def clash_report(arm, tol=0.5):
    """Deepest vertex-in-convex-hull penetration (m) between Body/Armor parts of non-adjacent bones in the current pose."""
    verts = deformed_vertices()
    objs = [o for o in hs.REG.parts if o["kind"] in ("body", "armor")]
    hulls = {}
    boxes = {}
    for o in objs:
        v = verts[o.name]
        boxes[o.name] = (v.min(0), v.max(0))
        try:
            h = ConvexHull(v)
            hulls[o.name] = h.equations
        except Exception:
            hulls[o.name] = None
    worst = []
    for i, a in enumerate(objs):
        for b in objs[i + 1:]:
            if _adjacent(arm, a["bone"], b["bone"]):
                continue
            (amn, amx), (bmn, bmx) = boxes[a.name], boxes[b.name]
            if np.any(amn > bmx) or np.any(bmn > amx):
                continue
            depth = 0.0
            for src, dst in ((a, b), (b, a)):
                eq = hulls[dst.name]
                if eq is None:
                    continue
                d = verts[src.name] @ eq[:, :3].T + eq[:, 3]          # signed distances to every facet plane (<0 inside)
                inside = np.all(d <= 0, axis=1)
                if inside.any():
                    depth = max(depth, float(-np.max(d[inside], axis=1).min()))
            if depth > tol:
                worst.append((depth, a.name, b.name))
    worst.sort(reverse=True)
    return worst

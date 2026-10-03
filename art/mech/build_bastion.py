#!/usr/bin/env python3
"""BASTION-01 (82 m) hard-surface build for Blender, from scratch and non-interactive.

    blender -b -P art/mech/build_bastion.py -- [--no-render] [--no-uv] [--quick]
    python  art/mech/build_bastion.py        [--no-render] [--no-uv] [--quick]      (needs `pip install bpy`)

Steps: build parts -> rig + rigid binding -> UV unwrap (uniform texel density) -> contract checks (raise on violation)
-> pose tests (joint limits + part clashes in 3 poses) -> FBX/GLB/JSON -> preview renders.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "out")

# ------------------------------------------------------------------------------------------------ parameters
# metres; +Z up, the mech faces -Y, its LEFT side is +X ("_l" bones). Joint heights are the real rotation points.
PARAMS = dict(
    height=82.0,                       # top of the head sensor mast
    hip_z=42.0, knee_z=26.0, ankle_z=5.0, waist_z=48.0, chest_z=60.5, shoulder_z=66.0, neck_z=68.0, head_y=-7.0, head_top=79.0,
    shoulder_x=23.0, arm_x=30.0, elbow_z=47.0, wrist_z=27.0, leg_x=11.5, reactor_y=15.5, reactor_z=57.0,
)
RENDER = dict(res=(1280, 800), samples=32)
CLASH_TOLERANCE_M = 0.5               # a pose passes when no two non-adjacent parts interpenetrate deeper than this


def main(argv):
    flags = set(argv)
    import bpy  # noqa: F401
    from lib import hs, design, rig, uv, checks, pose, export, render
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)

    hs.reset()
    design.build_all(PARAMS)
    arm = rig.build_armature(design.skeleton(PARAMS))
    rig.bind_all(arm)
    print("[1/6] built %d parts" % len(hs.REG.parts))

    use_uv = "--no-uv" not in flags
    if use_uv:
        uv.unwrap_all()
        d = uv.equalize_density()
        print("[2/6] UV unwrapped, uniform texel density %.5f UV units per metre" % d)
    stats = checks.run(PARAMS, check_uv=use_uv)
    print("[3/6] contract checks passed")

    errs = pose.check_limits()
    pose_results = {}
    for name in pose.POSES:
        pose.reset_pose(arm)
        pose.apply_pose(arm, name)
        worst = pose.clash_report(arm, tol=CLASH_TOLERANCE_M)
        pose_results[name] = {"angles_deg": pose.POSES[name],
                              "clashes_over_tolerance": [{"depth_m": round(dd, 3), "a": a, "b": b} for dd, a, b in worst]}
        for dd, a, b in worst:
            errs.append("pose %s: %s penetrates %s by %.2f m" % (name, a, b, dd))
    pose.reset_pose(arm)
    if errs:
        raise SystemExit("pose tests failed:\n" + "\n".join(errs))
    print("[4/6] pose tests passed (%s)" % ", ".join(pose.POSES))

    export.write_json(os.path.join(OUT, "BASTION_01_parts.json"), export.parts_report(PARAMS, stats))
    export.write_json(os.path.join(OUT, "BASTION_01_pose_tests.json"), {
        "convention": "rotations in degrees about WORLD axes through the joint, relative to the parent's pose; X pitch (negative = forward/up), Y roll, Z yaw/side swing",
        "clash_tolerance_m": CLASH_TOLERANCE_M,
        "joint_limits_deg": {b: {a: list(r) for a, r in lim.items()} for b, lim in pose.LIMITS.items()},
        "poses": pose_results})
    export.export_fbx(os.path.join(OUT, "BASTION_01.fbx"))
    export.export_glb(os.path.join(OUT, "BASTION_01.glb"))
    big = export.package_large(OUT)
    print("[5/6] exported FBX, GLB, parts and pose JSON%s" % ("; zipped (>5 MB raw): " + ", ".join(big) if big else ""))

    only = None
    for f in flags:
        if f.startswith("--only="):
            only = set(f.split("=", 1)[1].split(","))
    if "--no-render" not in flags:
        previews(arm, hs, render, pose, only)
        print("[6/6] previews rendered")
    n, h = export.verify_fbx(os.path.join(OUT, "BASTION_01.fbx"), len(hs.REG.parts), PARAMS["height"])
    print("FBX re-import check: %d meshes, height %.2f m, bones and orientation as in the contract" % (n, h))
    print("done in %.0f s" % (time.time() - t0))


def previews(arm, hs, render, pose, only=None):
    """Render the preview set. `only` (a set of names) limits the run, e.g. --only=damage,scale,pose_swing_right."""
    import bpy
    want = lambda n: only is None or n in only
    render.setup_scene(RENDER["res"], RENDER["samples"])
    render.lights()
    render.ground()
    o = lambda n: os.path.join(OUT, n)
    H = PARAMS["height"]
    mid = (0, 0, H / 2)
    if want("front"):
        render.ortho_view(o("preview_front.png"), (0, -400, mid[2]), mid, H * 1.1, res=(900, 1100))
    if want("side"):
        render.ortho_view(o("preview_side.png"), (400, 0, mid[2]), mid, H * 1.1, res=(900, 1100))
    if want("back"):
        render.lights(key_dir=(-0.4, 0.9, 0.8))     # key light moves behind the mech so the reactor side is readable
        render.ortho_view(o("preview_back.png"), (0, 400, mid[2]), mid, H * 1.1, res=(900, 1100))
        render.lights()
    if want("three_quarter"):
        render.hero(o("preview_three_quarter.png"), (92, -128, 40), (0, 0, 42), lens=30)
    if want("damage"):   # right arm without plates: the mechanics under them
        hidden = [p for p in hs.REG.parts if p.name.startswith("Armor_ArmR_") or p.name.startswith("Armor_ShoulderR_")]
        for p in hidden:
            p.hide_render = True
        render.hero(o("preview_damage_arm.png"), (-78, -104, 50), (-30, -4, 48), lens=62, res=(1100, 1100))
        for p in hidden:
            p.hide_render = False
    if want("scale"):    # 200 m tower, a bus and a person next to the mech
        props = render.scale_props()
        render.hero(o("preview_scale.png"), (-25, -300, 92), (-30, 0, 88), lens=30, res=(1600, 900))
        render.remove_objs(props)
    cams = {"stand": ((150, -180, 40), (0, 0, 40)), "swing_right": ((-200, -240, 70), (-10, 0, 56)),
            "step": ((150, -170, 36), (0, 0, 38))}
    for name, view in cams.items():
        if not want("pose_" + name):
            continue
        pose.reset_pose(arm)
        pose.apply_pose(arm, name)
        render.hero(o("preview_pose_%s.png" % name), view[0], view[1], lens=34)
    pose.reset_pose(arm)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(argv)

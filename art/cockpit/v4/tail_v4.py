# =============================================================================================================== PILOT BODY
HIP_Z = -0.82
LAY["body"] = {"hip_l": [0.0, 0.115, HIP_Z], "hip_r": [0.0, -0.115, HIP_Z], "thigh": 0.38, "shin": 0.36, "pelvis": [0.0, 0.0, HIP_Z], "torso_pivot": [0.0, 0.0, HIP_Z], "waist_ring": [0.0, 0.0, -0.80]}


def body_part(name, builder):
    bb = B(name)
    builder(bb)
    return bb.finish()


def build_boot(b):
    # pivot at the ankle; foot points +X
    b.box((0.06, 0, -0.045), (0.30, 0.115, 0.075), cls=12, bevel=0.015)
    b.box((0.09, 0, -0.06), (0.30, 0.125, 0.04), cls=3, bevel=0.01)                  # sole
    b.box((0.11, 0, 0.0), (0.18, 0.10, 0.07), cls=13, bevel=0.012)                    # toe cap armour
    b.box((-0.02, 0, 0.0), (0.12, 0.11, 0.1), cls=13, bevel=0.012)
    b.box((0.06, 0, 0.026), (0.12, 0.07, 0.02), cls=2, bevel=0.004)
    b.cyl((-0.02, -0.055, 0.02), (-0.02, 0.055, 0.02), 0.03, cls=0, seg=10)           # ankle joint
    for k in range(3):
        b.box((0.0 + 0.05 * k, 0, 0.03), (0.02, 0.095, 0.012), cls=9 if k == 1 else 0)


def build_shin(b):
    # pivot at the knee, runs down -Z, length 0.36
    L = 0.36
    b.cyl((0, 0, 0), (0, 0, -L), 0.058, 0.044, cls=12, seg=16)
    b.box((0.04, 0, -0.14), (0.045, 0.1, 0.24), cls=13, bevel=0.01)                   # front shin guard
    b.box((0.052, 0, -0.14), (0.01, 0.06, 0.2), cls=2)
    b.cyl((0.0, -0.06, -0.06), (0.0, 0.06, -0.06), 0.032, cls=0, seg=10)
    for z in (-0.06, -0.22, -0.3):
        b.cyl((0, 0, z - 0.012), (0, 0, z + 0.012), 0.066 - 0.001 * abs(z) * 10, cls=0, seg=14)
    b.box((0.0, 0.06, -0.2), (0.05, 0.016, 0.18), cls=5)
    b.pipe([(0.0, -0.05, -0.04), (-0.06, -0.06, -0.18), (-0.04, -0.045, -0.33)], 0.008, cls=3, collars=False)


def build_thigh(b):
    L = 0.38
    b.cyl((0, 0, 0), (0, 0, -L), 0.075, 0.06, cls=12, seg=16)
    b.box((0.05, 0, -0.17), (0.05, 0.12, 0.28), cls=13, bevel=0.012)
    b.box((0.062, 0, -0.17), (0.01, 0.07, 0.2), cls=2)
    b.sphere((0.045, 0, -L + 0.03), 0.055, cls=13, seg=10)                              # knee cap
    b.cyl((0.0, -0.075, 0.0), (0.0, 0.075, 0.0), 0.04, cls=0, seg=12)                  # hip joint
    b.box((0.0, 0.075, -0.2), (0.04, 0.016, 0.26), cls=9)
    for z in (-0.05, -0.17, -0.3):
        b.cyl((0, 0, z - 0.01), (0, 0, z + 0.01), 0.083, cls=0, seg=14)
    b.pipe([(-0.04, 0.05, 0.0), (-0.08, 0.06, -0.16), (-0.05, 0.05, -0.34)], 0.011, cls=3, collars=False)


def build_pelvis(b):
    b.box((0, 0, 0.02), (0.26, 0.34, 0.14), cls=12, bevel=0.02)
    b.box((0.02, 0, 0.02), (0.22, 0.3, 0.1), cls=13, bevel=0.02)                       # front hip armour
    b.box((0.13, 0, -0.01), (0.06, 0.12, 0.1), cls=2, bevel=0.012)                     # cod plate
    b.box((0, 0, 0.1), (0.3, 0.38, 0.045), cls=0, bevel=0.01)                          # belt
    for sy in (-1, 1):
        b.box((0.08, sy * 0.19, 0.09), (0.08, 0.05, 0.07), cls=13, bevel=0.008)       # belt pouches
        b.box((0.0, sy * 0.175, 0.0), (0.12, 0.05, 0.14), cls=13, bevel=0.012)         # side hip plates
        b.box((0.07, sy * 0.19, 0.09), (0.02, 0.04, 0.012), cls=5)
    for k in range(6):
        b.box((0.145, -0.1 + 0.04 * k, 0.1), (0.012, 0.022, 0.03), cls=5 if k % 2 else 9)


def build_torso(b):
    # pivot at the hip centre; chest top at about +0.62 (the neck is at +0.7)
    b.box((0.0, 0, 0.12), (0.22, 0.28, 0.2), cls=12, bevel=0.03)                       # abdomen
    for z in (0.05, 0.11, 0.17, 0.23):
        b.box((0.02, 0, z), (0.2, 0.3, 0.035), cls=13 if z > 0.1 else 0, bevel=0.01)   # ab plates
    b.box((0.0, 0, 0.42), (0.27, 0.42, 0.33), cls=12, bevel=0.04)                      # chest
    b.box((0.065, 0, 0.44), (0.2, 0.38, 0.28), cls=13, bevel=0.04)                     # chest armour
    b.box((0.17, 0, 0.45), (0.03, 0.12, 0.12), cls=0, bevel=0.01)                      # core housing
    b.cyl((0.19, 0, 0.45), (0.205, 0, 0.45), 0.044, cls=14, seg=6)                     # glowing core (hex)
    for sy in (-1, 1):
        b.box((0.075, sy * 0.1, 0.46), (0.05, 0.1, 0.22), cls=2, bevel=0.01)           # orange pecs plates
        b.box((0.0, sy * 0.24, 0.54), (0.17, 0.12, 0.1), cls=13, bevel=0.03)           # shoulder pads
        b.cyl((0.0, sy * 0.21, 0.51), (0.0, sy * 0.3, 0.51), 0.045, cls=0, seg=12)     # shoulder joints
        b.box((0.0, sy * 0.24, 0.585), (0.15, 0.08, 0.016), cls=2)
        b.box((-0.05, sy * 0.1, 0.5), (0.04, 0.05, 0.3), cls=3)                         # harness straps (back)
    b.box((0.1, 0, 0.62), (0.07, 0.34, 0.06), cls=13, bevel=0.01)                      # collar
    b.box((0.0, 0, 0.64), (0.08, 0.1, 0.07), cls=12)                                    # neck
    for k in range(5):
        b.box((0.16, -0.08 + 0.04 * k, 0.33), (0.012, 0.022, 0.016), cls=9 if k == 2 else 5)
    # cables from the chest port
    b.pipe([(0.18, 0.1, 0.34), (0.25, 0.14, 0.2), (0.22, 0.2, 0.0)], 0.014, cls=3, collars=False)
    b.pipe([(0.18, -0.1, 0.34), (0.25, -0.14, 0.2), (0.22, -0.2, 0.0)], 0.014, cls=3, collars=False)
    # backpack unit
    b.box((-0.17, 0, 0.42), (0.14, 0.3, 0.34), cls=0, bevel=0.02)
    b.box((-0.25, 0, 0.42), (0.04, 0.22, 0.26), cls=1, bevel=0.01)
    for sy in (-1, 1):
        b.cyl((-0.22, sy * 0.08, 0.6), (-0.3, sy * 0.1, 0.8), 0.022, cls=3, seg=8)


boots = body_part("SM_Body_Boot", build_boot)
shins = body_part("SM_Body_Shin", build_shin)
thighs = body_part("SM_Body_Thigh", build_thigh)
pelvis = body_part("SM_Body_Pelvis", build_pelvis)
torso = body_part("SM_Body_Torso", build_torso)

# =============================================================================================================== ARMS (the drive-suit sleeves on the rig; same contract as v1)
def rig_upper():
    R = B("SM_Rig_Upper")
    L = 0.55
    R.cyl((0, 0, 0), (L, 0, 0), 0.085, 0.075, cls=12, seg=20)
    R.sphere((0, 0, 0), 0.105, cls=0, seg=16)
    for t in (0.18, 0.5, 0.82):
        R.cyl((L * t - 0.02, 0, 0), (L * t + 0.02, 0, 0), 0.098, cls=1, seg=20)
    R.box((L * 0.5, 0, 0.1), (0.4, 0.15, 0.06), cls=13, bevel=0.015)
    R.box((L * 0.5, 0, 0.135), (0.3, 0.1, 0.012), cls=2)
    R.cyl((0.05, 0.0, 0.12), (L - 0.05, 0.0, 0.07), 0.028, cls=10, seg=12)
    R.box((L * 0.55, 0, -0.1), (0.3, 0.14, 0.06), cls=2, bevel=0.012)
    for k in range(5):
        R.box((0.1 + k * 0.085, 0.09, 0.0), (0.04, 0.02, 0.05), cls=5 if k == 2 else 0, bevel=0.003)
    R.pipe([(0.02, -0.09, 0.05), (L * 0.5, -0.12, 0.06), (L - 0.03, -0.09, 0.03)], 0.018, cls=3, collars=False)
    return R.finish()


def rig_fore():
    R = B("SM_Rig_Fore")
    L = 0.55
    R.sphere((0, 0, 0), 0.095, cls=0, seg=16)
    R.cyl((0, 0, 0), (L, 0, 0), 0.078, 0.062, cls=12, seg=20)
    for t in (0.22, 0.55, 0.85):
        R.cyl((L * t - 0.02, 0, 0), (L * t + 0.02, 0, 0), 0.088 - 0.012 * t, cls=1, seg=20)
    R.box((L * 0.55, 0, 0.075), (0.38, 0.16, 0.05), cls=13, bevel=0.012)
    R.box((L * 0.55, 0, 0.1), (0.3, 0.1, 0.01), cls=2)
    R.cyl((0.04, -0.05, -0.11), (L - 0.04, -0.03, -0.075), 0.022, cls=10, seg=10)
    for k in range(4):
        R.box((0.18 + k * 0.09, 0.075, 0.0), (0.03, 0.02, 0.04), cls=9 if k % 2 == 0 else 0, bevel=0.003)
    R.box((L * 0.4, 0.0, -0.085), (0.22, 0.12, 0.04), cls=0, bevel=0.01)
    return R.finish()


def rig_glove():
    R = B("SM_Rig_Glove")
    R.sphere((0, 0, 0), 0.08, cls=0, seg=14)
    R.cyl((0, 0, 0), (0.12, 0, 0), 0.07, 0.065, cls=1, seg=18)
    R.cyl((0.04, 0, 0), (0.09, 0, 0), 0.085, cls=2, seg=18)
    R.box((0.24, 0, 0), (0.16, 0.15, 0.1), cls=3, bevel=0.03)
    R.box((0.24, 0, 0.055), (0.15, 0.14, 0.03), cls=13, bevel=0.01)
    for k, yy in enumerate((-0.054, -0.018, 0.018, 0.054)):
        R.box((0.37, yy, 0.012), (0.1, 0.032, 0.05), rot=(0, math.radians(-20), 0), cls=3, bevel=0.012)
        R.box((0.43, yy, -0.024), (0.07, 0.03, 0.044), rot=(0, math.radians(-70), 0), cls=3, bevel=0.01)
    R.box((0.26, 0.095, -0.015), (0.1, 0.04, 0.05), rot=(0, 0, math.radians(30)), cls=3, bevel=0.012)
    R.cyl((0.38, -0.12, -0.03), (0.38, 0.12, -0.03), 0.018, cls=10, seg=12)
    R.box((0.22, 0, -0.115), (0.34, 0.26, 0.04), cls=13, bevel=0.015)
    R.box((0.22, 0.13, 0.0), (0.34, 0.04, 0.2), cls=13, bevel=0.015)
    R.box((0.22, -0.13, 0.0), (0.34, 0.04, 0.2), cls=13, bevel=0.015)
    R.box((0.05, 0, 0.1), (0.06, 0.3, 0.05), cls=1, bevel=0.012)
    R.box((0.22, 0.152, 0.0), (0.3, 0.008, 0.03), cls=2)
    R.box((0.22, -0.152, 0.0), (0.3, 0.008, 0.03), cls=2)
    for sy in (-1, 1):
        R.box((0.30, sy * 0.15, 0.03), (0.07, 0.012, 0.025), cls=5 if sy > 0 else 7, bevel=0.002)
    return R.finish()


up, fo, gl = rig_upper(), rig_fore(), rig_glove()

# =============================================================================================================== export
objs = {"SM_Cockpit_Shell": shell, "SM_Cockpit_Glass": glass, "SM_Body_Boot": boots, "SM_Body_Shin": shins, "SM_Body_Thigh": thighs, "SM_Body_Pelvis": pelvis,
        "SM_Body_Torso": torso, "SM_Rig_Upper": up, "SM_Rig_Fore": fo, "SM_Rig_Glove": gl}
for name, ob in objs.items():
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, name + ".fbx")
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_scale_options="FBX_SCALE_UNITS", global_scale=1.0,
                             axis_forward="-Y", axis_up="Z", object_types={"MESH"}, mesh_smooth_type="EDGE", bake_space_transform=False, path_mode="AUTO")
    print("EXPORTED", path, len(ob.data.polygons), "faces")
with open(os.path.join(OUT, "cockpit_layout.json"), "w") as fh:
    json.dump(LAY, fh, separators=(",", ":"))
print("LAYOUT pipes %d wires %d monitors %d lamps %d sockets %d" % (len(LAY["pipes"]), len(LAY["wires"]), len(LAY["monitors"]), len(LAY["lamps"]), len(LAY["sockets"])))

if PREVIEW:
    sc = bpy.context.scene
    sc.view_settings.view_transform = "Standard"
    sc.render.engine = "CYCLES"; sc.cycles.samples = 10; sc.cycles.use_denoising = False; sc.cycles.device = "CPU"
    sc.render.resolution_x, sc.render.resolution_y = 1672, 941
    world = bpy.data.worlds.new("W"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.58, 0.8, 1)
    cols_ = {0: (0.09, 0.09, 0.105), 1: (0.28, 0.3, 0.34), 2: (0.7, 0.24, 0.02), 3: (0.015, 0.015, 0.02), 4: (0.0, 0.7, 1.0), 5: (1.0, 0.45, 0.05), 6: (0.0, 0.02, 0.03), 7: (1.0, 0.05, 0.03),
             8: (0.8, 0.6, 0.0), 9: (0.9, 0.95, 1.0), 10: (0.5, 0.5, 0.52), 11: (0.1, 1.0, 0.2), 12: (0.05, 0.06, 0.08), 13: (0.1, 0.11, 0.13), 14: (0.0, 0.9, 1.0)}
    emissive = {4, 5, 7, 9, 11, 14}
    for ob in objs.values():
        me = ob.data
        cls = np.empty(len(me.vertices)); me.attributes["cls"].data.foreach_get("value", cls)
        ca = me.color_attributes.new("PC", "FLOAT_COLOR", "POINT")
        arr = np.array([list(cols_[int(round(c))]) + [1.0] for c in cls], np.float32)
        ca.data.foreach_set("color", arr.ravel())
        em = me.color_attributes.new("EM", "FLOAT_COLOR", "POINT")
        arr2 = np.array([(list(cols_[int(round(c))]) if int(round(c)) in emissive else [0, 0, 0]) + [1.0] for c in cls], np.float32)
        em.data.foreach_set("color", arr2.ravel())
        m = bpy.data.materials.new("P"); m.use_nodes = True
        nt = m.node_tree; bsdf = nt.nodes["Principled BSDF"]
        vc = nt.nodes.new("ShaderNodeVertexColor"); vc.layer_name = "PC"
        ve = nt.nodes.new("ShaderNodeVertexColor"); ve.layer_name = "EM"
        nt.links.new(vc.outputs[0], bsdf.inputs["Base Color"]); bsdf.inputs["Metallic"].default_value = 0.55; bsdf.inputs["Roughness"].default_value = 0.42
        nt.links.new(ve.outputs[0], bsdf.inputs["Emission Color"]); bsdf.inputs["Emission Strength"].default_value = 2.0
        me.materials.clear(); me.materials.append(m)
    gm = bpy.data.materials.new("GL"); gm.use_nodes = True
    gb = gm.node_tree.nodes["Principled BSDF"]; gb.inputs["Base Color"].default_value = (0.3, 0.5, 0.7, 1); gb.inputs["Alpha"].default_value = 0.08
    glass.data.materials.clear(); glass.data.materials.append(gm)
    # body in a standing pose
    def put(src, loc, rot=(0, 0, 0), scale=(1, 1, 1), name="X"):
        ob = src.copy(); ob.data = src.data; ob.name = name
        bpy.context.scene.collection.objects.link(ob)
        ob.location = loc; ob.rotation_euler = rot; ob.scale = scale
    put(pelvis, (0, 0, HIP_Z), name="pel")
    put(torso, (0, 0, HIP_Z), name="tor")
    for sy, nm in ((1, "L"), (-1, "R")):
        put(thighs, (0, sy * 0.115, HIP_Z), scale=(1, sy, 1), name="th" + nm)
        put(shins, (0.0, sy * 0.115, HIP_Z - 0.38), scale=(1, sy, 1), name="sh" + nm)
        put(boots, (0.0, sy * 0.115, HIP_Z - 0.38 - 0.36), scale=(1, sy, 1), name="bt" + nm)
    for nm, src, loc, rot in (() if "--norig" in argv else (("UpL", up, (0.25, 0.30, -0.45), (0, math.radians(15), math.radians(-14))), ("FoL", fo, (0.78, 0.22, -0.40), (0, math.radians(8), math.radians(-8))), ("GlL", gl, (1.30, 0.12, -0.36), (0, 0, 0)))):
        put(src, loc, rot, name=nm)
        put(src, (loc[0], -loc[1], loc[2]), (rot[0], rot[1], -rot[2]), (1, -1, 1), nm + "R")
    for o in (up, fo, gl, glass, boots, shins, thighs, pelvis, torso):
        o.hide_render = True
    # monitors lit cyan
    mm = bpy.data.materials.new("MON"); mm.use_nodes = True
    mb = mm.node_tree.nodes["Principled BSDF"]; mb.inputs["Base Color"].default_value = (0, 0.05, 0.08, 1); mb.inputs["Emission Color"].default_value = (0.0, 0.6, 1.0, 1); mb.inputs["Emission Strength"].default_value = 1.5
    for mon in LAY["monitors"]:
        bm_ = bmesh.new()
        c = Vector(mon["c"]); r_ = Vector(mon["right"]); u_ = Vector(mon["up"])
        hw, hh = mon["w"] / 2, mon["h"] / 2
        vs = [bm_.verts.new(c + r_ * sx * hw + u_ * sy * hh + Vector(mon["n"]) * 0.002) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        bm_.faces.new(vs)
        me = bpy.data.meshes.new("mon"); bm_.to_mesh(me); bm_.free()
        mo = bpy.data.objects.new("mon", me); sc.collection.objects.link(mo); me.materials.append(mm)
    # lights
    for loc, e, c in (((-1.0, 0.8, 0.5), 150.0, (1.0, 0.9, 0.8)), ((-1.0, -0.8, 0.5), 150.0, (0.8, 0.9, 1.0)), ((0.2, 0.0, 0.9), 120.0, (0.6, 0.8, 1.0)), ((0.6, 1.0, -0.6), 60.0, (1.0, 0.55, 0.25)), ((0.6, -1.0, -0.6), 60.0, (0.4, 0.7, 1.0)), ((-0.6, 0.0, 0.4), 50.0, (1.0, 0.9, 0.8)), ((0.3, 0.0, -0.9), 30.0, (0.2, 0.8, 1.0))):
        bpy.ops.object.light_add(type="POINT", location=loc); L = bpy.context.object; L.data.energy = e; L.data.color = c
    cd = bpy.data.cameras.new("C"); cd.lens = 17.4; cd.sensor_width = 36
    cam = bpy.data.objects.new("C", cd); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = (0, 0, 0)

    def shot(name, pitch_deg, yaw_deg, lens=17.4):
        if SHOTS is not None and name.replace('prev_', '') not in SHOTS:
            return
        cd.lens = lens
        cam.rotation_euler = Euler((math.radians(90 + pitch_deg), 0, math.radians(-90 + yaw_deg)), "XYZ")
        sc.render.filepath = os.path.join(OUT, name + ".png"); bpy.ops.render.render(write_still=True)
    shot("prev_front", 0, 0)
    shot("prev_down", -62, 0)
    shot("prev_left", -8, 85)
    shot("prev_up", 55, 0)
    shot("prev_back", -10, 180)
    cam.location = (-1.9, 2.2, 0.8); cam.rotation_euler = Vector((1.8, -1.6, -0.5)).to_track_quat("-Z", "Y").to_euler(); cd.lens = 22
    for o in (shell,):
        pass
    if SHOTS is None or "outer" in SHOTS:
        sc.render.filepath = os.path.join(OUT, "prev_outer.png"); bpy.ops.render.render(write_still=True)
    # debug: top-down (ceiling clipped away) and side orthographic
    cd.type = "ORTHO"; cd.ortho_scale = 5.0; cd.clip_start = 0.01
    cam.location = (0, 0, 3.0); cam.rotation_euler = (0, 0, math.radians(-90)); cd.clip_start = 1.85
    if SHOTS is None or "top" in SHOTS:
        sc.render.filepath = os.path.join(OUT, "prev_top.png"); bpy.ops.render.render(write_still=True)
    cd.clip_start = 0.01
    cam.location = (0, 4.0, -0.2); cam.rotation_euler = (math.radians(90), 0, math.radians(180))
    if SHOTS is None or "side" in SHOTS:
        sc.render.filepath = os.path.join(OUT, "prev_side.png"); bpy.ops.render.render(write_still=True)
    print("PREVIEW DONE")

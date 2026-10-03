import unreal
sm = unreal.EditorAssetLibrary.load_asset("/Game/Mechs/Bastion/BASTION_01")
sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
unreal.log("IV insp class=%s" % sm.get_class().get_name())
try:
    unreal.log("IV insp lods=%d" % sub.get_lod_count(sm))
except Exception as e:
    unreal.log("IV insp lod err %s" % e)
try:
    unreal.log("IV insp num_verts lod0=%d" % sm.get_num_vertices(0))
except Exception as e:
    unreal.log("IV insp verts err %s" % e)
try:
    unreal.log("IV insp tris lod0=%d" % sm.get_num_triangles(0) if hasattr(sm, 'get_num_triangles') else "no tris fn")
except Exception as e:
    unreal.log("IV insp tris err %s" % e)
mats = sm.get_editor_property("materials")
for m in mats:
    mi = m.get_editor_property("material_interface")
    unreal.log("IV insp slot %s -> %s parent=%s" % (m.get_editor_property("material_slot_name"), mi.get_name() if mi else None, mi.get_editor_property("parent").get_name() if mi and hasattr(mi, 'get_editor_property') and isinstance(mi, unreal.MaterialInstanceConstant) and mi.get_editor_property("parent") else None))
unreal.log("IV insp bounds %s" % sm.get_bounds())
unreal.log("IV insp import_data? has_vertex_colors=%s" % sm.get_editor_property("has_vertex_colors"))

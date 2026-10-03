"""Imports a mech FBX (contract of docs/tasks/TASK-002) as a skeletal mesh into /Game/Mechs/<Name>.
Usage: UnrealEditor-Cmd ImpactVector.uproject -ExecutePythonScript="Scripts/import_mech.py <fbx path> <AssetName>"
"""
import sys
import unreal

args = sys.argv[1:] if len(sys.argv) > 1 else []
FBX = args[0] if args else r"F:\IVUnreal\Content\Source\BASTION_01.fbx"
NAME = args[1] if len(args) > 1 else "Bastion"
DEST = "/Game/Mechs/" + NAME

opts = unreal.FbxImportUI()
opts.set_editor_property("import_mesh", True)
opts.set_editor_property("import_as_skeletal", True)
opts.set_editor_property("import_materials", True)
opts.set_editor_property("import_textures", False)
opts.set_editor_property("import_animations", False)
opts.set_editor_property("create_physics_asset", False)
sm = opts.get_editor_property("skeletal_mesh_import_data")
sm.set_editor_property("import_uniform_scale", 1.0)
sm.set_editor_property("convert_scene", True)
sm.set_editor_property("convert_scene_unit", True)
sm.set_editor_property("import_morph_targets", False)

task = unreal.AssetImportTask()
task.set_editor_property("filename", FBX)
task.set_editor_property("destination_path", DEST)
task.set_editor_property("automated", True)
task.set_editor_property("replace_existing", True)
task.set_editor_property("save", True)
task.set_editor_property("options", opts)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
unreal.log("IV import result paths: %s" % list(task.get_editor_property("imported_object_paths")))

for p in task.get_editor_property("imported_object_paths"):
    a = unreal.EditorAssetLibrary.load_asset(p)
    unreal.log("IV asset: %s (%s)" % (p, a.get_class().get_name() if a else None))
    if isinstance(a, unreal.SkeletalMesh):
        b = a.get_bounds()
        unreal.log("IV bounds origin=%s extent=%s" % (b.origin, b.box_extent))
        sk = a.get_editor_property("skeleton")
        if sk:
            names = [str(n) for n in sk.get_editor_property("bone_tree")] if False else []
        unreal.log("IV materials: %s" % [str(m.material_slot_name) for m in a.get_editor_property("materials")])

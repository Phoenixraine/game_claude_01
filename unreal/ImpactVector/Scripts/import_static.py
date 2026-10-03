"""Imports static-mesh FBX files into /Game/<Dest>.
UnrealEditor-Cmd ImpactVector.uproject -ExecutePythonScript="Scripts/import_static.py <Dest> <fbx> [<fbx> ...]"
"""
import sys
import unreal

args = sys.argv[1:]
DEST = "/Game/" + args[0]
tasks = []
for fbx in args[1:]:
    opts = unreal.FbxImportUI()
    opts.set_editor_property("import_mesh", True)
    opts.set_editor_property("import_as_skeletal", False)
    opts.set_editor_property("import_materials", False)
    opts.set_editor_property("import_textures", False)
    opts.set_editor_property("import_animations", False)
    sm = opts.get_editor_property("static_mesh_import_data")
    sm.set_editor_property("combine_meshes", True)
    sm.set_editor_property("generate_lightmap_u_vs", False)
    sm.set_editor_property("auto_generate_collision", False)
    sm.set_editor_property("import_uniform_scale", 1.0)
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", fbx)
    t.set_editor_property("destination_path", DEST)
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", True)
    t.set_editor_property("options", opts)
    tasks.append(t)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
for t in tasks:
    for p in t.get_editor_property("imported_object_paths"):
        a = unreal.EditorAssetLibrary.load_asset(p)
        if isinstance(a, unreal.StaticMesh):
            b = a.get_bounds()
            unreal.log("IV static %s origin=%s extent=%s" % (p, b.origin, b.box_extent))

"""Imports the cloud shard library (art/shards/out/*.fbx) as separate static meshes into /Game/Shards."""
import unreal

SRC = "F:/IVRepo/art/shards/out"
FILES = ["Shards_Concrete.fbx", "Shards_Structure.fbx", "Shards_Glass.fbx", "Shards_Gravel.fbx", "Shards_Metal.fbx"]
tasks = []
for f in FILES:
    opts = unreal.FbxImportUI()
    opts.set_editor_property("import_mesh", True)
    opts.set_editor_property("import_as_skeletal", False)
    opts.set_editor_property("import_materials", False)
    opts.set_editor_property("import_textures", False)
    opts.set_editor_property("import_animations", False)
    sm = opts.get_editor_property("static_mesh_import_data")
    sm.set_editor_property("combine_meshes", False)
    sm.set_editor_property("generate_lightmap_u_vs", False)
    sm.set_editor_property("auto_generate_collision", False)
    sm.set_editor_property("import_uniform_scale", 1.0)
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", SRC + "/" + f)
    t.set_editor_property("destination_path", "/Game/Shards")
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", True)
    t.set_editor_property("options", opts)
    tasks.append(t)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
n = 0
for t in tasks:
    for p in t.get_editor_property("imported_object_paths"):
        a = unreal.EditorAssetLibrary.load_asset(p)
        if isinstance(a, unreal.StaticMesh):
            n += 1
            if n % 20 == 1:
                b = a.get_bounds()
                unreal.log("IV static %s extent=%s tris=%d" % (p, b.box_extent, a.get_num_triangles(0) if hasattr(a, 'get_num_triangles') else -1))
unreal.log("IV shards imported: %d" % n)

import unreal
t = unreal.AssetImportTask()
t.set_editor_property("filename", "F:/IVUnreal/Content/Source/audio/env_heli_rotor_loop.wav")
t.set_editor_property("destination_path", "/Game/Audio")
t.set_editor_property("destination_name", "env_heli_rotor_loop")
t.set_editor_property("automated", True)
t.set_editor_property("replace_existing", True)
t.set_editor_property("save", True)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
a = unreal.EditorAssetLibrary.load_asset("/Game/Audio/env_heli_rotor_loop")
if a:
    a.set_editor_property("looping", True)
    unreal.EditorAssetLibrary.save_loaded_asset(a)
    unreal.log("IV audio heli imported")

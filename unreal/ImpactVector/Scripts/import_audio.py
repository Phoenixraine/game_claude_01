"""Imports every WAV from Content/Source/audio into /Game/Audio as SoundWave assets named after the sound id."""
import os
import unreal

SRC = r"F:\IVUnreal\Content\Source\audio"
DEST = "/Game/Audio"
tasks = []
for f in sorted(os.listdir(SRC)):
    if not f.lower().endswith(".wav"):
        continue
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", os.path.join(SRC, f))
    t.set_editor_property("destination_path", DEST)
    t.set_editor_property("destination_name", os.path.splitext(f)[0])
    t.set_editor_property("automated", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("save", True)
    tasks.append(t)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
ok = 0
for t in tasks:
    if t.get_editor_property("imported_object_paths"):
        ok += 1
unreal.log("IV audio imported %d / %d" % (ok, len(tasks)))
# loops: mark the long ambient files as looping
LOOPS = [n for n in os.listdir(SRC) if n.endswith("_loop.wav")]
for n in LOOPS:
    a = unreal.EditorAssetLibrary.load_asset(DEST + "/" + os.path.splitext(n)[0])
    if a:
        a.set_editor_property("looping", True)
        unreal.EditorAssetLibrary.save_loaded_asset(a)
unreal.log("IV audio loops set: %d" % len(LOOPS))

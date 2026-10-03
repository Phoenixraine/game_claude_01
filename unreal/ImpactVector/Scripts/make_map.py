import unreal
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ok = les.new_level("/Game/Maps/L_CombatLab")
unreal.log("IV new_level: %s" % ok)
ok2 = les.save_current_level()
unreal.log("IV save_level: %s" % ok2)

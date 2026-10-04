// Graphics presets (the menu cycles them): LOW .. ULTRA use Lumen software tracing, RTX switches Lumen to hardware ray tracing for GI and reflections.
#pragma once

#include "CoreMinimal.h"

namespace IVGraphics
{
	constexpr int32 kPresetCount = 5;
	const TCHAR* PresetName(int32 Preset);
	/** Applies console variables for the preset to the running game (safe to call every time the menu changes it). */
	void Apply(UWorld* World, int32 Preset);
	/** Reads/writes the choice in Saved/Config (GameUserSettings.ini, section [IV]). */
	int32 Load();
	void Save(int32 Preset);
	/** Applies the saved preset once at game start (the command line -IVGfx=0..4 overrides it). */
	void ApplyAtStart(UWorld* World);
	/** True when the machine can do hardware ray tracing (a DXR capable GPU and DX12). */
	bool SupportsRayTracing();
}

// Player-tunable settings (the SETTINGS screen of the menu). Every setting is a float; toggles are 0/1, choices are 0..N-1.
// Values live in Saved/Config/WindowsNoEditor/IVSettings.ini and are pushed into the running world by Apply().
#pragma once

#include "CoreMinimal.h"

namespace IVSettings
{
	enum class EKind : uint8 { Slider, Toggle, Choice };

	struct FSetting
	{
		const TCHAR* Id;
		const TCHAR* Label;
		const TCHAR* Hint;
		int32 Tab;                     // 0 battle, 1 world, 2 graphics, 3 controls
		EKind Kind;
		float Min, Max, Step, Def;
		TArray<FString> Names;         // choices
		const TCHAR* Unit;             // shown after the number
		float Show;                    // displayed value = value * Show
	};

	constexpr int32 kTabCount = 4;
	const TCHAR* TabName(int32 Tab);
	const TArray<FSetting>& All();
	/** Settings of one tab, in display order (indices into All()). */
	TArray<int32> OfTab(int32 Tab);

	float Get(const TCHAR* Id);
	int32 GetInt(const TCHAR* Id);
	bool GetBool(const TCHAR* Id);
	void Set(const TCHAR* Id, float Value);        // clamps, saves, does not apply
	void Adjust(int32 Index, int32 Dir, bool bFast);
	FString ValueText(int32 Index);
	void ResetAll();
	void Load();
	/** Pushes everything into the world (fog, exposure, rain, helicopters, draw distance, cvars...). Call after any change. */
	void Apply(UWorld* World);
}

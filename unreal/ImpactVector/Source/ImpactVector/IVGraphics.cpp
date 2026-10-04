#include "IVGraphics.h"
#include "HAL/IConsoleManager.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "RHI.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "Kismet/KismetSystemLibrary.h"

namespace
{
	void CV(const TCHAR* Name, float V)
	{
		if (IConsoleVariable* C = IConsoleManager::Get().FindConsoleVariable(Name)) C->Set(V, ECVF_SetByGameSetting);
		else UE_LOG(LogTemp, Verbose, TEXT("IV graphics: cvar %s not found"), Name);
	}
	void CVI(const TCHAR* Name, int32 V)
	{
		if (IConsoleVariable* C = IConsoleManager::Get().FindConsoleVariable(Name)) C->Set(V, ECVF_SetByGameSetting);
	}
	FString IniPath() { return FPaths::ProjectSavedDir() / TEXT("Config/WindowsNoEditor/IVGraphics.ini"); }
}

namespace IVGraphics
{
	const TCHAR* PresetName(int32 P)
	{
		static const TCHAR* N[kPresetCount] = { TEXT("НИЗКАЯ"), TEXT("СРЕДНЯЯ"), TEXT("ВЫСОКАЯ"), TEXT("УЛЬТРА"), TEXT("RTX (ТРАССИРОВКА ЛУЧЕЙ)") };
		return N[FMath::Clamp(P, 0, kPresetCount - 1)];
	}

	bool SupportsRayTracing() { return GRHISupportsRayTracing; }

	void Apply(UWorld*, int32 Preset)
	{
		Preset = FMath::Clamp(Preset, 0, kPresetCount - 1);
		if (Preset == 4 && !SupportsRayTracing()) Preset = 3;
		// resolution scale (TSR upscales)
		static const float Sp[kPresetCount] = { 62.f, 80.f, 100.f, 100.f, 100.f };
		CV(TEXT("r.ScreenPercentage"), Sp[Preset]);
		// volumetric fog grid: coarser is cheaper
		static const int32 Grid[kPresetCount] = { 24, 16, 12, 8, 8 };
		CVI(TEXT("r.VolumetricFog.GridPixelSize"), Grid[Preset]);
		CVI(TEXT("r.VolumetricFog.GridSizeZ"), Preset <= 1 ? 48 : 64);
		// Lumen quality
		CVI(TEXT("r.Lumen.Reflections.Allow"), Preset >= 1 ? 1 : 0);
		CV(TEXT("r.Lumen.ScreenProbeGather.DownsampleFactor"), Preset == 0 ? 32.f : (Preset == 1 ? 24.f : (Preset == 2 ? 16.f : 12.f)));
		CV(TEXT("r.Lumen.TraceMeshSDFs"), Preset >= 2 ? 1.f : 0.f);
		CV(TEXT("r.Lumen.Reflections.MaxRoughnessToTrace"), Preset >= 3 ? 0.6f : 0.35f);
		CV(TEXT("r.SSR.Quality"), Preset == 0 ? 0.f : 3.f);
		CV(TEXT("r.BloomQuality"), Preset == 0 ? 3.f : 5.f);
		CV(TEXT("r.ViewDistanceScale"), Preset == 0 ? 0.7f : 1.f);
		CV(TEXT("r.Shadow.Virtual.ShadowMapMaxResolution"), Preset >= 3 ? 8192.f : 4096.f);
		// hardware ray tracing (RTX): GI, reflections and glass use RT cores; hit lighting gives accurate neon reflections
		const bool bRt = Preset == 4;
		CVI(TEXT("r.RayTracing.Enable"), bRt ? 1 : 0);
		CVI(TEXT("r.Lumen.HardwareRayTracing"), bRt ? 1 : 0);
		CVI(TEXT("r.Lumen.HardwareRayTracing.LightingMode"), bRt ? 0 : 0);
		CVI(TEXT("r.Lumen.Reflections.HardwareRayTracing"), bRt ? 1 : 0);
		CVI(TEXT("r.Lumen.ScreenProbeGather.HardwareRayTracing"), bRt ? 1 : 0);
		CV(TEXT("r.RayTracing.Shadows"), 0.f);
		UE_LOG(LogTemp, Display, TEXT("IV graphics preset %d applied (RT %d)"), Preset, bRt ? 1 : 0);
	}

	int32 Load()
	{
		int32 P = 3;
		GConfig->GetInt(TEXT("IV"), TEXT("GfxPreset"), P, IniPath());
		return FMath::Clamp(P, 0, kPresetCount - 1);
	}

	void Save(int32 P)
	{
		GConfig->SetInt(TEXT("IV"), TEXT("GfxPreset"), P, IniPath());
		GConfig->Flush(false, IniPath());
	}

	void ApplyAtStart(UWorld* World)
	{
		int32 P = Load();
		FParse::Value(FCommandLine::Get(), TEXT("-IVGfx="), P);
		Apply(World, P);
	}
}

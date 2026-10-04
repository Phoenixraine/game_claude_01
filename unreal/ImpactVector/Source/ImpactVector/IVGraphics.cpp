#include "IVGraphics.h"
#include "HAL/IConsoleManager.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "RHI.h"
#include "Engine/World.h"
#include "Engine/GameViewportClient.h"
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
		// internal resolution from a pixel budget (millions of rendered pixels): 3440x1440 renders ~75 % per axis on HIGH, 1080p is native.
		// TSR upscales to the display resolution.
		static const float BudgetMpx[kPresetCount] = { 1.2f, 1.9f, 2.7f, 4.2f, 3.6f };
		float W = 1920.f, H = 1080.f;
		if (GEngine && GEngine->GameViewport) { FVector2D VS; GEngine->GameViewport->GetViewportSize(VS); if (VS.X > 100.f && VS.Y > 100.f) { W = VS.X; H = VS.Y; } }
		const float Sp = FMath::Clamp(FMath::Sqrt(BudgetMpx[Preset] * 1.0e6f / (W * H)) * 100.f, 45.f, 100.f);
		CV(TEXT("r.ScreenPercentage"), Sp);
		CV(TEXT("r.TSR.History.ScreenPercentage"), 100.f);
		// volumetric fog grid: coarser is cheaper
		static const int32 Grid[kPresetCount] = { 24, 16, 14, 8, 8 };
		CVI(TEXT("r.VolumetricFog.GridPixelSize"), Grid[Preset]);
		CVI(TEXT("r.VolumetricFog.GridSizeZ"), Preset <= 1 ? 48 : 64);
		// Lumen: reflections are the expensive part (~16 fps at 3440x1440); below ULTRA the wet ground uses screen-space reflections
		CVI(TEXT("r.Lumen.Reflections.Allow"), Preset >= 3 ? 1 : 0);
		CV(TEXT("r.Lumen.ScreenProbeGather.DownsampleFactor"), Preset == 0 ? 32.f : (Preset == 1 ? 28.f : (Preset == 2 ? 24.f : 16.f)));
		CV(TEXT("r.Lumen.TraceMeshSDFs"), Preset >= 3 ? 1.f : 0.f);
		CV(TEXT("r.Lumen.Reflections.MaxRoughnessToTrace"), Preset >= 3 ? 0.5f : 0.3f);
		CV(TEXT("r.SSR.Quality"), Preset == 0 ? 2.f : 4.f);
		CV(TEXT("r.BloomQuality"), Preset == 0 ? 3.f : 5.f);
		CV(TEXT("r.ViewDistanceScale"), Preset == 0 ? 0.7f : 1.f);
		CV(TEXT("r.Shadow.Virtual.ShadowMapMaxResolution"), Preset >= 3 ? 8192.f : 4096.f);
		CV(TEXT("r.Shadow.Virtual.ResolutionLodBiasDirectional"), Preset >= 3 ? 0.f : 1.f);
		// hardware ray tracing (RTX): GI, reflections and glass use RT cores; hit lighting gives accurate neon reflections
		const bool bRt = Preset == 4;
		CVI(TEXT("r.RayTracing.Enable"), bRt ? 1 : 0);
		CVI(TEXT("r.Lumen.HardwareRayTracing"), bRt ? 1 : 0);
		CVI(TEXT("r.Lumen.Reflections.HardwareRayTracing"), bRt ? 1 : 0);
		CVI(TEXT("r.Lumen.ScreenProbeGather.HardwareRayTracing"), bRt ? 1 : 0);
		if (bRt) CVI(TEXT("r.Lumen.Reflections.Allow"), 1);
		CV(TEXT("r.RayTracing.Shadows"), 0.f);
		UE_LOG(LogTemp, Display, TEXT("IV graphics preset %d applied (RT %d, %.0f%% of %.0fx%.0f)"), Preset, bRt ? 1 : 0, Sp, W, H);
	}

	int32 Load()
	{
		int32 P = 2;
		GConfig->GetInt(TEXT("IV"), TEXT("GfxPresetV2"), P, IniPath());
		return FMath::Clamp(P, 0, kPresetCount - 1);
	}

	void Save(int32 P)
	{
		GConfig->SetInt(TEXT("IV"), TEXT("GfxPresetV2"), P, IniPath());
		GConfig->Flush(false, IniPath());
	}

	void ApplyAtStart(UWorld* World)
	{
		int32 P = Load();
		FParse::Value(FCommandLine::Get(), TEXT("-IVGfx="), P);
		Apply(World, P);
	}
}

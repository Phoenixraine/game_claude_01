import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new, cnt=1):
    assert old in t, old[:70]
    return t.replace(old, new, cnt)


# ------------------------------------------------------------------ district
h, c = rd("IVDistrict.h")
if "ApplyDrawDistance" not in h:
    h = rep(h, "	void SetLightBudget(int32 N);", "	void SetLightBudget(int32 N);\n	/** Instances further than this (cm) from the camera are not drawn; the fog hides the cut. */\n	void ApplyDrawDistance(float Cm);\n	void SetNeonScale(float Scale);")
    wr("IVDistrict.h", h, c)
d, c = rd("IVDistrictDecor.cpp")
if "AIVDistrict::ApplyDrawDistance" not in d:
    d = rep(d, "void AIVDistrict::SetLightBudget(int32 N)", """void AIVDistrict::ApplyDrawDistance(float Cm)
{
	UInstancedStaticMeshComponent* Comps[] = { Concrete, Glass, Hero, Cars, TreeTrunks, TreeCrowns, Lamps, Containers, Chimneys, Signs, TrimBox, TrimBall, ConcCyl, ExtraGlass, ExtraConc };
	for (UInstancedStaticMeshComponent* I : Comps)
		if (I) { I->SetCullDistances(int32(Cm * 0.85f), int32(Cm)); I->bUseAsOccluder = false; }
	for (FIVNeonLight& L : NeonLights) if (L.L) { L.L->MaxDrawDistance = Cm * 0.9f; L.L->MaxDistanceFadeRange = Cm * 0.2f; }
}

void AIVDistrict::SetNeonScale(float Scale)
{
	for (FIVNeonLight& L : NeonLights) if (L.L) L.L->SetIntensity(L.Base * Scale);
	if (Signs) if (UMaterialInstanceDynamic* M = Cast<UMaterialInstanceDynamic>(Signs->GetMaterial(0))) M->SetScalarParameterValue(TEXT("Gain"), Scale);
}

void AIVDistrict::SetLightBudget(int32 N)""")
    wr("IVDistrictDecor.cpp", d, c)

# ------------------------------------------------------------------ environment
h, c = rd("IVEnvironment.h")
if "ApplySettings" not in h:
    h = rep(h, "	static AIVEnvironment* Get(UWorld* World);", "	static AIVEnvironment* Get(UWorld* World);\n	/** Fog / exposure / neon / bloom / motion blur / rain amount / ground mist from the player's settings. */\n	void ApplySettings(float FogMul, float EV, float Neon, float Bloom, float MotionBlur, float Rain, bool bMist);")
    h = rep(h, "	void BuildCityBlockout();", "	void BuildCityBlockout();\n	UPROPERTY() TObjectPtr<AActor> RainActor;")
    wr("IVEnvironment.h", h, c)
e, c = rd("IVEnvironment.cpp")
if "AIVEnvironment::ApplySettings" not in e:
    e = rep(e, "void AIVEnvironment::OnConstruction(", """void AIVEnvironment::ApplySettings(float FogMul, float EV, float Neon, float Bloom, float MotionBlur, float Rain, bool bMist)
{
	if (Fog)
	{
		Fog->SetFogDensity(0.06f * FogMul);
		Fog->SecondFogData.FogDensity = 0.05f * FogMul;
		Fog->MarkRenderStateDirty();
	}
	if (PostProcess)
	{
		FPostProcessSettings& S = PostProcess->Settings;
		S.bOverride_AutoExposureBias = true; S.AutoExposureBias = 0.4f + EV;
		S.bOverride_BloomIntensity = true; S.BloomIntensity = Bloom;
		S.bOverride_MotionBlurAmount = true; S.MotionBlurAmount = MotionBlur;
	}
	if (District) District->SetNeonScale(Neon);
	if (AActor* R = RainActor.Get()) { R->SetActorHiddenInGame(Rain < 0.02f); if (AIVRain* Rn = Cast<AIVRain>(R)) Rn->SetAmount(Rain); }
	AIVFXManager::bGroundMist = bMist;
}

void AIVEnvironment::OnConstruction(""")
    e = rep(e, "GetWorld()->SpawnActor<AIVRain>(FVector::ZeroVector, FRotator::ZeroRotator);", "RainActor = GetWorld()->SpawnActor<AIVRain>(FVector::ZeroVector, FRotator::ZeroRotator);")
    e = rep(e, '#include "IVRain.h"', '#include "IVRain.h"\n#include "IVFXManager.h"\n#include "IVDistrict.h"')
    wr("IVEnvironment.cpp", e, c)

# ------------------------------------------------------------------ rain
h, c = rd("IVRain.h")
if "SetAmount" not in h:
    h = rep(h, "	virtual void BeginPlay() override;", "	virtual void BeginPlay() override;\n	void SetAmount(float A);")
    h = rep(h, "private:\n	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> ISM;", "private:\n	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> ISM;\n	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> RainMID;")
    h = rep(h, "class UInstancedStaticMeshComponent;", "class UInstancedStaticMeshComponent;\nclass UMaterialInstanceDynamic;")
    wr("IVRain.h", h, c)
r, c = rd("IVRain.cpp")
if "AIVRain::SetAmount" not in r:
    r = rep(r, "ISM->SetMaterial(0, MID);", "ISM->SetMaterial(0, MID);" + chr(10) + chr(9) + chr(9) + "RainMID = MID;")
    r = rep(r, "void AIVRain::Tick(float Dt)", "void AIVRain::SetAmount(float A)\n{\n	if (RainMID) RainMID->SetScalarParameterValue(TEXT(\"Amount\"), A);\n}\n\nvoid AIVRain::Tick(float Dt)")
    wr("IVRain.cpp", r, c)

# ------------------------------------------------------------------ FX manager flag
h, c = rd("IVFXManager.h")
if "bGroundMist" not in h:
    h = rep(h, "	static AIVFXManager* Get(UWorld* World);", "	static AIVFXManager* Get(UWorld* World);\n	static bool bGroundMist;")
    wr("IVFXManager.h", h, c)
f, c = rd("IVFXManager.cpp")
if "bool AIVFXManager::bGroundMist" not in f:
    f = rep(f, "AIVFXManager::AIVFXManager()", "bool AIVFXManager::bGroundMist = false;\n\nAIVFXManager::AIVFXManager()")
    f = rep(f, 'FParse::Param(FCommandLine::Get(), TEXT("IVMist"))', "(bGroundMist || FParse::Param(FCommandLine::Get(), TEXT(\"IVMist\")))")
    wr("IVFXManager.cpp", f, c)

# ------------------------------------------------------------------ helicopters
h, c = rd("IVHelicopter.h")
if "SetFleetSize" not in h:
    h = rep(h, "	static void SpawnFleet(UWorld* World, const FVector& ArenaCenter, int32 Count = 2);", "	static void SpawnFleet(UWorld* World, const FVector& ArenaCenter, int32 Count = 2);\n	/** Spawns or removes patrolling helicopters until exactly Count are flying. */\n	static void SetFleetSize(UWorld* World, int32 Count);")
    wr("IVHelicopter.h", h, c)
hc, c = rd("IVHelicopter.cpp")
if "AIVHelicopter::SetFleetSize" not in hc:
    hc = rep(hc, "void AIVHelicopter::UpdateAim(float Dt)", """void AIVHelicopter::SetFleetSize(UWorld* World, int32 Count)
{
	if (!World) return;
	TArray<AIVHelicopter*> Live;
	for (TActorIterator<AIVHelicopter> It(World); It; ++It) if (It->State == EIVHeliState::Patrol) Live.Add(*It);
	for (int32 i = Live.Num() - 1; i >= Count; --i) Live[i]->Destroy();
	if (Live.Num() < Count)
	{
		FVector Mid = FVector(39500.f, 0.f, 0.f);
		int32 N = 0; FVector Sum = FVector::ZeroVector;
		for (TActorIterator<AIVMechPawn> It(World); It; ++It) { Sum += It->GetActorLocation(); ++N; }
		if (N) Mid = FVector(Sum.X / N, Sum.Y / N, 0.f);
		for (int32 i = Live.Num(); i < Count; ++i)
		{
			FActorSpawnParameters Sp;
			Sp.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			AIVHelicopter* H = World->SpawnActor<AIVHelicopter>(Mid, FRotator::ZeroRotator, Sp);
			if (!H) continue;
			H->Center = Mid;
			H->Phase = 2.f * PI * (float(i) / FMath::Max(Count, 1)) + 0.7f;
			H->bClockwise = (i % 2) == 0;
			H->Radius = 17500.f + 4500.f * i;
			H->Altitude = 10500.f + 2200.f * i;
			H->LowTimer = 14.f + 16.f * i;
		}
	}
}

void AIVHelicopter::UpdateAim(float Dt)""")
    wr("IVHelicopter.cpp", hc, c)

# ------------------------------------------------------------------ mech pawn
h, c = rd("IVMechPawn.h")
if "ApplySettings" not in h:
    h = rep(h, "	void SetFirstPersonView(bool bFirstPerson);", "	void SetFirstPersonView(bool bFirstPerson);\n	/** Re-reads the player's settings (field of view, shake, infection...). */\n	void ApplySettings();")
    h = rep(h, "	float AimYaw = 0.f, AimPitch = 0.f;", "	float AimYaw = 0.f, AimPitch = 0.f;\n	float SetFov = 98.f, SetShake = 1.f, SetMinSep = 5000.f;")
    wr("IVMechPawn.h", h, c)
p, c = rd("IVMechPawn.cpp")
if "void AIVMechPawn::ApplySettings" not in p:
    p = rep(p, '#include "IVMechPawn.h"', '#include "IVMechPawn.h"\n#include "IVSettings.h"')
    p = rep(p, "void AIVMechPawn::SetFirstPersonView(bool bFirstPerson)", """void AIVMechPawn::ApplySettings()
{
	SetFov = IVSettings::Get(TEXT("fov"));
	SetShake = IVSettings::Get(TEXT("shake"));
	SetMinSep = IVSettings::Get(TEXT("min_dist")) * 100.f;
	if (bAIControlled)
	{
		const bool bInf = IVSettings::GetBool(TEXT("infected"));
		if (bInf && !bInfected) { bInfected = true; if (bRigActive && GrowthComps.Num() == 0) BuildGrowths(); }
		for (UStaticMeshComponent* G : GrowthComps) if (G) G->SetVisibility(bInf);
		if (!bInf) bInfected = false;
	}
}

void AIVMechPawn::SetFirstPersonView(bool bFirstPerson)""")
    p = rep(p, "static constexpr float kMinSeparation = 5000.f, kSlowSeparation = 7000.f;", "")
    p = p.replace("kMinSeparation", "SetMinSep").replace("kSlowSeparation", "(SetMinSep + 2000.f)")
    p = rep(p, "Camera->SetFieldOfView((bSplit ? 76.f : 98.f) - 7.f * Rage);", "Camera->SetFieldOfView((bSplit ? SetFov - 22.f : SetFov) - 7.f * Rage);")
    p = rep(p, "		ShakeAmp = FMath::FInterpTo(ShakeAmp, 0.f, Dt, 3.4f);", "		ShakeAmp = FMath::FInterpTo(ShakeAmp, 0.f, Dt, 3.4f);\n		const float ShakeUse = ShakeAmp * SetShake;")
    old = "const FRotator Shk(ShakeAmp * 1.1f * FMath::Sin(Tm * 47.f), ShakeAmp * 1.1f * FMath::Sin(Tm * 59.f + 1.f), ShakeAmp * 1.6f * FMath::Sin(Tm * 39.f + 2.f));"
    p = rep(p, old, old.replace("ShakeAmp", "ShakeUse"))
    p = rep(p, "CamPos + FVector(0.f, 0.f, ShakeAmp * 1.8f * FMath::Sin(Tm * 71.f))", "CamPos + FVector(0.f, 0.f, ShakeUse * 1.8f * FMath::Sin(Tm * 71.f))")
    wr("IVMechPawn.cpp", p, c)

# ------------------------------------------------------------------ player controller
h, c = rd("IVPlayerController.h")
if "ApplySettings" not in h:
    h = rep(h, "	float LookSensitivity = 0.11f;", "	void ApplySettings();\n	float RumbleScale = 1.f;\n	float LookSensitivity = 0.11f;")
    wr("IVPlayerController.h", h, c)
pc, c = rd("IVPlayerController.cpp")
if "void AIVPlayerController::ApplySettings" not in pc:
    pc = rep(pc, '#include "IVPlayerController.h"', '#include "IVPlayerController.h"\n#include "IVSettings.h"')
    pc = rep(pc, "void AIVPlayerController::Rumble(float Strength, float Seconds)\n{", """void AIVPlayerController::ApplySettings()
{
	LookSensitivity = 0.11f * IVSettings::Get(TEXT("mouse"));
	StickLookRate = 95.f * IVSettings::Get(TEXT("pad_look"));
	RumbleScale = IVSettings::Get(TEXT("rumble"));
}

void AIVPlayerController::Rumble(float Strength, float Seconds)
{
	Strength *= RumbleScale;""")
    pc = rep(pc, "	Super::BeginPlay();\n", "	Super::BeginPlay();\n	ApplySettings();\n")
    wr("IVPlayerController.cpp", pc, c)

# ------------------------------------------------------------------ combat director
cb, c = rd("IVCombat.cpp")
if 'IVSettings::Get(TEXT("fight_speed"))' not in cb:
    cb = rep(cb, '#include "IVCombat.h"', '#include "IVCombat.h"\n#include "IVSettings.h"')
    a = cb.index("	static const double FightSpeed")
    b = cb.index("\n", a)
    cb = cb[:a] + '	const double FightSpeed = double(IVSettings::Get(TEXT("fight_speed")));' + cb[b:]
    cb = rep(cb, "	HitStop = FMath::Max(HitStop, Seconds * Dilation);", "	Seconds *= IVSettings::Get(TEXT(\"hit_stop\"));\n	if (Seconds <= 0.001f) return;\n	HitStop = FMath::Max(HitStop, Seconds * Dilation);")
    wr("IVCombat.cpp", cb, c)

# ------------------------------------------------------------------ HUD: fps counter and scale
hd, c = rd("IVHUD.cpp")
if 'IVSettings::GetBool(TEXT("fps_counter"))' not in hd:
    hd = rep(hd, '#include "IVHUD.h"', '#include "IVHUD.h"\n#include "IVSettings.h"')
    hd = rep(hd, "		static bool bShow = true;\n", "")
    hd = rep(hd, "if (Pc0->WasInputKeyJustPressed(EKeys::F3)) bShow = !bShow;", "if (Pc0->WasInputKeyJustPressed(EKeys::F3)) { IVSettings::Set(TEXT(\"fps_counter\"), IVSettings::GetBool(TEXT(\"fps_counter\")) ? 0.f : 1.f); }\n		const bool bShow = IVSettings::GetBool(TEXT(\"fps_counter\"));")
    hd = rep(hd, "		const float Sx = FMath::Clamp(W / 1600.f, 0.55f, 1.4f);\n		const float Fd = LookFade;", "		const float Sx = FMath::Clamp(W / 1600.f, 0.55f, 1.4f) * IVSettings::Get(TEXT(\"hud_scale\"));\n		const float Fd = LookFade;")
    wr("IVHUD.cpp", hd, c)

# ------------------------------------------------------------------ game mode: infection flag from settings
gm, c = rd("IVGameMode.cpp")
if 'IVSettings::GetBool(TEXT("infected"))' not in gm:
    gm = rep(gm, '#include "IVGameMode.h"', '#include "IVGameMode.h"\n#include "IVSettings.h"')
    gm = rep(gm, 'EnemyMech->bInfected = !FParse::Param(FCommandLine::Get(), TEXT("IVNoInfect"));', 'EnemyMech->bInfected = IVSettings::GetBool(TEXT("infected")) && !FParse::Param(FCommandLine::Get(), TEXT("IVNoInfect"));')
    gm = rep(gm, "	if (!FParse::Param(FCommandLine::Get(), TEXT(\"IVNoHeli\")))\n		AIVHelicopter::SpawnFleet(W, (PlayerLoc + EnemyLoc) * 0.5f, 2);", "	if (!FParse::Param(FCommandLine::Get(), TEXT(\"IVNoHeli\")))\n		AIVHelicopter::SpawnFleet(W, (PlayerLoc + EnemyLoc) * 0.5f, IVSettings::GetInt(TEXT(\"helis\")));")
    gm = rep(gm, "bGfxReapplied = true; IVGraphics::ApplyAtStart(GetWorld());", "bGfxReapplied = true; IVGraphics::ApplyAtStart(GetWorld()); IVSettings::Apply(GetWorld());")
    wr("IVGameMode.cpp", gm, c)
print("settings hooks patched")

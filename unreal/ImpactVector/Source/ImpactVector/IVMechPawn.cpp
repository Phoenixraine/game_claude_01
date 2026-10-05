#include "IVMechPawn.h"
#include "IVSettings.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Camera/CameraComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/ConstructorHelpers.h"
#include "HAL/IConsoleManager.h"
#include "EngineUtils.h"
#include "Components/SkeletalMeshComponent.h"
#include "IVRigAnimInstance.h"
#include "Engine/SkeletalMesh.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "IVEnvironment.h"
#include "IVFXManager.h"
#include "IVBuilding.h"
#include "IVAudio.h"
#include "Components/PointLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "ProceduralMeshComponent.h"
#include "IVDistrict.h"
#include "IVPlayerController.h"
#include "Components/InstancedStaticMeshComponent.h"

static TAutoConsoleVariable<int32> CVarIVCam(TEXT("iv.Cam"), 0,
	TEXT("0 = cockpit, 1 = chase, 2 = side, 3 = front orbit, 4 = both mechs from the side"), ECVF_Default);
static TAutoConsoleVariable<int32> CVarRigApply(TEXT("iv.RigApply"), 1, TEXT("0 = leave the rig in its rest pose"), ECVF_Default);
static TAutoConsoleVariable<float> CVarIVCamDist(TEXT("iv.CamDist"), 16000.f, TEXT("Debug camera distance (cm)"), ECVF_Default);

static TAutoConsoleVariable<FString> CVarIVFreeCam(TEXT("iv.FreeCam"), TEXT("0 0 0 0 0"), TEXT("Free camera for iv.Cam=6: x y z (m, district frame y=forward) pitch yaw(ue)"), ECVF_Default);

// centre-to-centre distance limits between the two giants (cm)


int32 GetIVCam() { return CVarIVCam.GetValueOnGameThread(); }
float GetIVCamDist() { return CVarIVCamDist.GetValueOnGameThread(); }

namespace
{
	UStaticMesh* GCube = nullptr;
	UMaterialInterface* GBaseMat = nullptr;
	UMaterialInterface* GArmorMat = nullptr;
	constexpr float kTwoPi = 6.28318530718f;
}

AIVMechPawn::AIVMechPawn()
{
	PrimaryActorTick.bCanEverTick = true;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeF(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> MatF(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> ArmorF(TEXT("/Game/Materials/M_MechArmor.M_MechArmor"));
	GCube = CubeF.Object;
	GBaseMat = MatF.Object;
	GArmorMat = ArmorF.Succeeded() ? ArmorF.Object : nullptr;

	Capsule = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Capsule"));
	Capsule->InitCapsuleSize(1300.f, 4100.f);
	Capsule->SetCollisionProfileName(TEXT("Pawn"));
	RootComponent = Capsule;

	RigMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("RigMesh"));
	RigMesh->SetupAttachment(RootComponent);
	RigMesh->SetRelativeLocation(FVector(0, 0, -4100.f));
	RigMesh->SetRelativeRotation(FRotator(0.f, -90.f, 0.f));    // imported mech faces +Y: turn it to +X
	RigMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	RigMesh->SetVisibility(false);
	RigMesh->bUpdateJointsFromAnimation = true;

	SwordMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Sword"));
	SwordMesh->SetupAttachment(RigMesh);
	{
		static ConstructorHelpers::FObjectFinder<UStaticMesh> SwordF(TEXT("/Game/Weapons/SM_ArmBlade.SM_ArmBlade"));
		if (SwordF.Succeeded()) SwordMesh->SetStaticMesh(SwordF.Object);
	}
	SwordMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SwordMesh->SetVisibility(false);
	SwordMesh->SetCastShadow(true);

	BladeTrail = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("BladeTrail"));
	BladeTrail->SetupAttachment(RootComponent);
	BladeTrail->SetUsingAbsoluteLocation(true);
	BladeTrail->SetUsingAbsoluteRotation(true);
	BladeTrail->SetUsingAbsoluteScale(true);
	BladeTrail->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	BladeTrail->SetCastShadow(false);
	BladeTrail->bUseAsyncCooking = false;

	BuildBody();
	BuildCockpit();
}

USceneComponent* AIVMechPawn::AddPivot(USceneComponent* Parent, const FName& Name, const FVector& Location)
{
	USceneComponent* P = CreateDefaultSubobject<USceneComponent>(Name);
	P->SetupAttachment(Parent);
	P->SetRelativeLocation(Location);
	return P;
}

UStaticMeshComponent* AIVMechPawn::AddBlock(USceneComponent* Parent, const FName& Name, const FVector& SizeCm, const FVector& CenterOffset, const FLinearColor& Color)
{
	UStaticMeshComponent* M = CreateDefaultSubobject<UStaticMeshComponent>(Name);
	M->SetupAttachment(Parent);
	M->SetStaticMesh(GCube);
	M->SetRelativeLocation(CenterOffset);
	M->SetRelativeScale3D(SizeCm / 100.f);
	M->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	M->SetCastShadow(true);
	AllMeshes.Add(M);
	return M;
}

void AIVMechPawn::BuildBody()
{
	const FLinearColor C0(0.f, 0.f, 0.f);

	PelvisPivot = AddPivot(RootComponent, TEXT("pelvis"), FVector(0, 0, 200.f));
	PelvisMesh = AddBlock(PelvisPivot, TEXT("Body_pelvis"), FVector(2000, 2800, 1000), FVector(0, 0, 100), C0);

	TorsoPivot = AddPivot(PelvisPivot, TEXT("torso"), FVector(0, 0, 600.f));
	TorsoMesh = AddBlock(TorsoPivot, TEXT("Body_torso"), FVector(2800, 3600, 2400), FVector(0, 0, 1200), C0);
	AddBlock(TorsoPivot, TEXT("Armor_Torso_Chest"), FVector(600, 3000, 1500), FVector(1550, 0, 1500), C0);
	AddBlock(TorsoPivot, TEXT("Armor_Torso_Back"), FVector(900, 2800, 2000), FVector(-1700, 0, 1300), C0);
	AddBlock(TorsoPivot, TEXT("Armor_Torso_Top"), FVector(2400, 3200, 300), FVector(0, 0, 2500), C0);

	HeadPivot = AddPivot(TorsoPivot, TEXT("head"), FVector(300.f, 0, 2450.f));
	HeadMesh = AddBlock(HeadPivot, TEXT("Body_head"), FVector(1100, 1300, 900), FVector(0, 0, 450), C0);

	for (int32 i = 0; i < 2; ++i)
	{
		const float S = (i == 0) ? -1.f : 1.f;
		const FString Sfx = (i == 0) ? TEXT("l") : TEXT("r");
		auto N = [&Sfx](const TCHAR* Base) { return FName(*FString::Printf(TEXT("%s_%s"), Base, *Sfx)); };

		Shoulder[i].Pivot = AddPivot(TorsoPivot, N(TEXT("shoulder")), FVector(0, S * 2250.f, 1900.f));
		Shoulder[i].Mesh = AddBlock(Shoulder[i].Pivot, N(TEXT("Armor_Shoulder")), FVector(1700, 1500, 1500), FVector(0, S * 150.f, 250), C0);
		UpperArm[i].Pivot = AddPivot(Shoulder[i].Pivot, N(TEXT("upperarm")), FVector(0, S * 100.f, -300.f));
		UpperArm[i].Mesh = AddBlock(UpperArm[i].Pivot, N(TEXT("Body_upperarm")), FVector(1100, 1100, 2400), FVector(0, 0, -1200), C0);
		Forearm[i].Pivot = AddPivot(UpperArm[i].Pivot, N(TEXT("forearm")), FVector(0, 0, -2400));
		Forearm[i].Mesh = AddBlock(Forearm[i].Pivot, N(TEXT("Body_forearm")), FVector(1500, 1500, 2500), FVector(0, 0, -1250), C0);
		Hand[i].Pivot = AddPivot(Forearm[i].Pivot, N(TEXT("hand")), FVector(0, 0, -2500));
		Hand[i].Mesh = AddBlock(Hand[i].Pivot, N(TEXT("Body_hand")), FVector(1300, 1200, 1300), FVector(150, 0, -650), C0);

		Thigh[i].Pivot = AddPivot(PelvisPivot, N(TEXT("thigh")), FVector(0, S * 1000.f, -300.f));
		Thigh[i].Mesh = AddBlock(Thigh[i].Pivot, N(TEXT("Body_thigh")), FVector(1600, 1600, 1700), FVector(0, 0, -850), C0);
		Shin[i].Pivot = AddPivot(Thigh[i].Pivot, N(TEXT("shin")), FVector(0, 0, -1700));
		Shin[i].Mesh = AddBlock(Shin[i].Pivot, N(TEXT("Body_shin")), FVector(1800, 1900, 1700), FVector(100, 0, -850), C0);
		Foot[i].Pivot = AddPivot(Shin[i].Pivot, N(TEXT("foot")), FVector(0, 0, -1700));
		Foot[i].Mesh = AddBlock(Foot[i].Pivot, N(TEXT("Body_foot")), FVector(3000, 2000, 600), FVector(600, 0, -300), C0);
	}
}

void AIVMechPawn::BuildCockpit()
{
	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("PilotCamera"));
	Camera->SetupAttachment(HeadPivot);
	Camera->bUsePawnControlRotation = false;
	Camera->SetFieldOfView(92.f);

	CockpitSway = AddPivot(Camera, TEXT("CockpitSway"), FVector::ZeroVector);

	auto CM = [this](const TCHAR* Name, const TCHAR* Path, bool bSolid) -> UStaticMeshComponent*
	{
		UStaticMeshComponent* M = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		M->SetupAttachment(CockpitSway);
		ConstructorHelpers::FObjectFinder<UStaticMesh> F(Path);
		if (F.Succeeded()) M->SetStaticMesh(F.Object);
		M->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		M->SetCastShadow(false);
		M->SetOnlyOwnerSee(true);
		M->bAffectDynamicIndirectLighting = false;
		M->SetLightingChannels(false, true, false);   // cockpit lights live on channel 1 only
		CockpitMeshes.Add(M);
		return M;
	};
	CockpitShellMesh = CM(TEXT("CockpitShell"), TEXT("/Game/Cockpit/V3/SM_Cockpit_Shell.SM_Cockpit_Shell"), true);
	CockpitGlassMesh = CM(TEXT("CockpitGlass"), TEXT("/Game/Cockpit/V3/SM_Cockpit_Glass.SM_Cockpit_Glass"), false);
	for (int32 i = 0; i < 2; ++i)
	{
		const FString S = (i == 0) ? TEXT("L") : TEXT("R");
		CockpitArm[i].Upper = CM(*(TEXT("RigUpper") + S), TEXT("/Game/Cockpit/V3/SM_Rig_Upper.SM_Rig_Upper"), true);
		CockpitArm[i].Fore = CM(*(TEXT("RigFore") + S), TEXT("/Game/Cockpit/V3/SM_Rig_Fore.SM_Rig_Fore"), true);
		CockpitArm[i].Glove = CM(*(TEXT("RigGlove") + S), TEXT("/Game/Cockpit/V3/SM_Rig_Glove.SM_Rig_Glove"), true);
	}
	CockpitFx = CreateDefaultSubobject<UIVCockpitComponent>(TEXT("CockpitFx"));
	CockpitFx->SetupAttachment(CockpitSway);
	struct FLamp { const TCHAR* N; FVector P; FLinearColor C; float I; float R; };
	const FLamp Lamps[] = {
		{ TEXT("LampDash"), FVector(40, 0, -70), FLinearColor(0.2f, 0.6f, 0.9f), 1.0f, 200.f },
		{ TEXT("LampLeft"), FVector(60, -110, -40), FLinearColor(1.f, 0.45f, 0.15f), 1.0f, 200.f },
		{ TEXT("LampRight"), FVector(60, 110, -40), FLinearColor(1.f, 0.45f, 0.15f), 1.0f, 200.f },
		{ TEXT("LampTop"), FVector(10, 0, 80), FLinearColor(0.8f, 0.78f, 0.75f), 0.9f, 260.f },
		{ TEXT("LampBody"), FVector(30, 0, -50), FLinearColor(0.95f, 0.85f, 0.75f), 0.5f, 160.f },
	};
	for (const FLamp& L : Lamps)
	{
		UPointLightComponent* PL = CreateDefaultSubobject<UPointLightComponent>(L.N);
		PL->SetupAttachment(CockpitSway);
		PL->SetRelativeLocation(L.P);
		PL->SetLightColor(L.C);
		PL->SetIntensityUnits(ELightUnits::Candelas);
		PL->SetIntensity(L.I);
		PL->SetAttenuationRadius(L.R);
		PL->SetCastShadows(false);
		PL->SetLightingChannels(false, true, false);
		PL->SetSourceRadius(6.f);
		CockpitLights.Add(PL);
	}
	for (int32 i = 0; i < 2; ++i)
	{
		USpotLightComponent* SL = CreateDefaultSubobject<USpotLightComponent>(*FString::Printf(TEXT("HeadLamp%d"), i));
		SL->SetupAttachment(HeadPivot);
		SL->SetRelativeLocation(FVector(500.f, (i == 0 ? -1.f : 1.f) * 380.f, 350.f));
		SL->SetRelativeRotation(FRotator(-13.f, (i == 0 ? 5.f : -5.f), 0.f));
		SL->SetIntensityUnits(ELightUnits::Candelas);
		SL->SetIntensity(70000.f);
		SL->SetAttenuationRadius(26000.f);
		SL->SetInnerConeAngle(6.f);
		SL->SetOuterConeAngle(17.f);
		SL->SetSourceRadius(40.f);
		SL->SetVolumetricScatteringIntensity(1.6f);
		SL->SetCastShadows(true);
		SL->SetLightingChannels(true, false, false);
		HeadLamp[i] = SL;
	}
}

void AIVMechPawn::BeginPlay()
{
	Super::BeginPlay();

	auto MakeMID = [this](UStaticMeshComponent* M, const FLinearColor& C)
	{
		if (!M || !GBaseMat) return;
		UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(GArmorMat ? GArmorMat : GBaseMat, this);
		MID->SetVectorParameterValue(TEXT("Color"), C);
		MID->SetVectorParameterValue(TEXT("Tint"), C);
		M->SetMaterial(0, MID);
		BodyMIDs.Add(MID);
	};
	for (UStaticMeshComponent* M : AllMeshes)
	{
		const FString N = M->GetName();
		FLinearColor C(0.10f, 0.11f, 0.125f);
		if (N.StartsWith(TEXT("Armor_"))) C = FLinearColor(0.32f, 0.34f, 0.36f);
		if (N.Contains(TEXT("pelvis")) || N.Contains(TEXT("head")) || N.Contains(TEXT("hand")) || N.Contains(TEXT("foot")) || N.Contains(TEXT("Back"))) C = FLinearColor(0.03f, 0.032f, 0.036f);
		if (N.Contains(TEXT("forearm")) || N.Contains(TEXT("shin"))) C = FLinearColor(0.30f, 0.32f, 0.34f);
		MakeMID(M, C);
	}
	{
		UMaterialInterface* CockM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Cockpit.M_Cockpit"));
		UMaterialInterface* GlassM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_CockpitGlass.M_CockpitGlass"));
		if (CockM)
		{
			CockpitMID = UMaterialInstanceDynamic::Create(CockM, this);
			for (UStaticMeshComponent* M : CockpitMeshes) if (M != CockpitGlassMesh) M->SetMaterial(0, CockpitMID);
			if (CockpitFx) CockpitFx->SetCockpitMaterial(CockpitMID);
		}
		if (GlassM && CockpitGlassMesh)
		{
			GlassMID = UMaterialInstanceDynamic::Create(GlassM, this);
			CockpitGlassMesh->SetMaterial(0, GlassMID);
			if (FParse::Param(FCommandLine::Get(), TEXT("IVNoGlass"))) CockpitGlassMesh->SetVisibility(false);
			if (FParse::Param(FCommandLine::Get(), TEXT("IVCrackDemo")))
			{
				GlassCrack = 0.6f;
				GlassMID->SetScalarParameterValue(TEXT("Crack"), 0.6f);
				GlassMID->SetVectorParameterValue(TEXT("Imp0"), FLinearColor(-0.35f, 0.25f, 0.9f, 0.f));
				GlassMID->SetVectorParameterValue(TEXT("Imp1"), FLinearColor(0.45f, 0.05f, 0.6f, 0.f));
				GlassMID->SetVectorParameterValue(TEXT("Imp2"), FLinearColor(0.1f, 0.42f, 0.4f, 0.f));
			}
		}
	}

	for (int32 i = 0; i < 2; ++i) if (HeadLamp[i]) { HeadLamp[i]->SetLightColor(LampColor); HeadLamp[i]->SetIntensity(70000.f * LampPower); HeadLamp[i]->SetVolumetricScatteringIntensity(0.55f * FMath::Sqrt(LampPower)); if (bLampsDown) HeadLamp[i]->SetRelativeRotation(FRotator(-30.f, (i == 0 ? 16.f : -16.f), 0.f)); }
	SetupRig();
	OnFootfall.AddLambda([this](int32 Side, float Strength)
	{
		const FVector Foot = (bRigActive && RigMesh) ? RigMesh->GetBoneLocation(Side < 0 ? FName(TEXT("foot_l")) : FName(TEXT("foot_r")), EBoneSpaces::WorldSpace) : GetActorLocation();
		const bool bWater = Foot.Z < -50.f;
		IVAudio::Play3D(GetWorld(), bWater ? IVAudio::Variant(TEXT("mech_step_water_"), 2) : IVAudio::Variant(TEXT("mech_step_heavy_"), 4), Foot, FMath::Clamp(0.55f + 0.5f * Strength, 0.4f, 1.1f), FMath::RandRange(0.9f, 1.05f));
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) FX->SpawnDust(Foot, 900.f, int32(2 + 4 * Strength), 0.35f);
		if (IsLocallyControlled()) { AddCockpitImpulse(0.f, -1.f, 0.22f * Strength); if (CockpitFx) CockpitFx->Footfall(Strength); }
	});

	{
		FString Lk;
		if (FParse::Value(FCommandLine::Get(), TEXT("-IVLook="), Lk, false))
		{
			FString A, B;
			if (Lk.Split(TEXT(","), &A, &B)) { LookPitchT = FCString::Atof(*A); LookYawT = FCString::Atof(*B); bDebugLook = true; }
		}
	}
	AimYaw = GetActorRotation().Yaw;
	CamPos = GetEyeLocation();
	CamRot = FRotator(0, AimYaw, 0);
	PrevVelocity = Velocity;
}

void AIVMechPawn::SetBodyTint(const FLinearColor& Tint)
{
	for (UMaterialInstanceDynamic* M : BodyMIDs)
	{
		FLinearColor Cur;
		if (M->GetVectorParameterValue(TEXT("Color"), Cur))
		{
			const float L = FMath::Max3(Cur.R, Cur.G, Cur.B);
			const FLinearColor New(Tint.R * (0.4f + L), Tint.G * (0.4f + L), Tint.B * (0.4f + L));
			M->SetVectorParameterValue(TEXT("Color"), New);
			M->SetVectorParameterValue(TEXT("Tint"), New);
		}
	}
}

void AIVMechPawn::SetPlayerLamps(bool bOn)
{
	bLampsDown = !bOn;
	LampPower = bOn ? 1.f : 0.12f;
	LampColor = bOn ? FLinearColor(0.75f, 0.88f, 1.f) : FLinearColor(1.f, 0.28f, 0.12f);
	for (int32 i = 0; i < 2; ++i) if (HeadLamp[i])
	{
		HeadLamp[i]->SetLightColor(LampColor);
		HeadLamp[i]->SetIntensity(70000.f * LampPower);
		HeadLamp[i]->SetVolumetricScatteringIntensity(0.55f * FMath::Sqrt(LampPower));
		HeadLamp[i]->SetRelativeRotation(bOn ? FRotator(-13.f, (i == 0 ? 5.f : -5.f), 0.f) : FRotator(-30.f, (i == 0 ? 16.f : -16.f), 0.f));
	}
}

void AIVMechPawn::ApplySettings()
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

void AIVMechPawn::SetFirstPersonView(bool bFirstPerson)
{
	if (HeadMesh) HeadMesh->SetOwnerNoSee(bFirstPerson);
	if (RigMesh) RigMesh->SetOwnerNoSee(bFirstPerson);
	for (UStaticMeshComponent* G : GreebleComps) if (G) G->SetOwnerNoSee(bFirstPerson);
	for (UStaticMeshComponent* G : GrowthComps) if (G) G->SetOwnerNoSee(bFirstPerson);
	for (FIVPlate& Pl : Plates) if (Pl.C) Pl.C->SetOwnerNoSee(bFirstPerson);
	for (UStaticMeshComponent* M : CockpitMeshes) M->SetVisibility(bFirstPerson);
	if (CockpitFx) CockpitFx->SetShown(bFirstPerson);
}

FVector AIVMechPawn::GetEyeLocation() const
{
	return HeadPivot->GetComponentTransform().TransformPosition(FVector(450.f, 0, 420.f - 1620.f));
}

FVector AIVMechPawn::MoveIntentToWorld() const
{
	const FVector Local(MoveIntent.Y, MoveIntent.X, 0.f);
	return FRotator(0, AimYaw, 0).RotateVector(Local);
}

void AIVMechPawn::Tick(float Dt)
{
	Super::Tick(Dt);
	Dt = FMath::Min(Dt, 0.05f);
	if (bAIControlled && !bExternalControl) UpdateAI(Dt);
	UpdateLocomotion(Dt);
	if (bRigActive) UpdateRig(Dt); else UpdateGait(Dt);
	UpdateUltimateScript(Dt);
	UpdateDetached(Dt);
	UpdateDamageFX(Dt);
	UpdateBladeTrail(Dt);
	UpdateV5Fx(Dt);
	if (bInfected) UpdateGrowths(Dt);
	if (IsLocallyControlled() || GetIVCam() != 0)
	{
		if (CockpitFx && GetIVCam() == 0)
		{
			CockpitFx->EnsureBuilt();
			const FRotator Yaw(0.f, CamRot.Yaw, 0.f);
			CockpitFx->SetMotion(Yaw.UnrotateVector(Velocity), GetSpeedRatio() * 0.55f, Yaw.UnrotateVector((Velocity - PrevVelocity) / FMath::Max(Dt, 1e-4f)), HitKick.X * -0.5f + (CombatAnim.phase == iv::Phase::Windup ? CombatAnim.progress : (CombatAnim.phase == iv::Phase::Strike ? 1.f - CombatAnim.progress : 0.f)) * 6.f, TorsoYawRel * 0.2f);
			if (CockpitMID)
			{
				CockpitMID->SetScalarParameterValue(TEXT("Alert"), CockpitFx->GetAlert());
				CockpitMID->SetScalarParameterValue(TEXT("Damage"), FMath::Clamp(CockpitFx->GetShake() * 0.6f + CockpitFx->GetAlert() * 0.25f, 0.f, 1.f));
			}
		}
		{
			static const float FailAt = [] { float V = -1.f; FParse::Value(FCommandLine::Get(), TEXT("-IVCkFailAt="), V); return V; }();
			if (FailAt > 0.f && CockpitFx && CockpitFx->IsBuilt() && GetWorld()->GetTimeSeconds() > FailAt && !bDebugFailDone) { bDebugFailDone = true; CockpitFx->ForceFailures(3); CockpitFx->Hit(0.9f, FVector(0, 1, 0), false); }
		}
		UpdateCockpitCamera(Dt);
		UpdateCockpitArms(Dt);
	}
}

void AIVMechPawn::UpdateAI(float Dt)
{
	APawn* Target = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Target || Target == this) { MoveIntent = FVector2D::ZeroVector; return; }
	const FVector To = Target->GetActorLocation() - GetActorLocation();
	const float Dist = To.Size2D();
	AimYaw = To.Rotation().Yaw;
	const float Ideal = 9500.f;
	if (Dist > Ideal + 1500.f) MoveIntent = FVector2D(0, 1);
	else if (Dist < Ideal - 2500.f) MoveIntent = FVector2D(0, -0.6);
	else MoveIntent = FVector2D(FMath::Sin(GetWorld()->GetTimeSeconds() * 0.15f) > 0 ? 0.4f : -0.4f, 0.f);
}

void AIVMechPawn::UpdateLocomotion(float Dt)
{
	const FVector Wish = bMoveLocked ? FVector::ZeroVector : MoveIntentToWorld();
	const float Mag = Wish.Size2D();
	const float LegsYaw = GetActorRotation().Yaw;

	// legs cannot spin on the spot: they turn towards the travel direction at a limited rate
	float TargetLegsYaw = LegsYaw;
	if (Mag > 0.05f)
	{
		TargetLegsYaw = (MoveIntent.Y < -0.2f) ? AimYaw : Wish.Rotation().Yaw;
	}
	else
	{
		const float Twist = FRotator::NormalizeAxis(AimYaw - LegsYaw);
		if (FMath::Abs(Twist) > TorsoTwistLimit) TargetLegsYaw = AimYaw;
	}
	const float TurnDelta = FRotator::NormalizeAxis(TargetLegsYaw - LegsYaw);
	const float MaxTurn = LegsTurnRate * Dt * (0.4f + 0.6f * FMath::Clamp(1.f - Velocity.Size2D() / (WalkSpeed * SprintMultiplier * 1.2f), 0.f, 1.f));
	const float NewLegsYaw = LegsYaw + FMath::Clamp(TurnDelta, -MaxTurn, MaxTurn);

	// torso twist follows the aim within limits
	const float WantTwist = FMath::Clamp(FRotator::NormalizeAxis(AimYaw - NewLegsYaw), -TorsoTwistLimit, TorsoTwistLimit);
	TorsoYawRel = FMath::FInterpConstantTo(TorsoYawRel, WantTwist, Dt, 140.f);
	TorsoPivot->SetRelativeRotation(FRotator(0, TorsoYawRel, 0));

	// velocity: heavy build-up, longer stop
	const FVector LegsFwd = FRotator(0, NewLegsYaw, 0).Vector();
	float SpeedFactor = 1.f;
	if (Mag > 0.05f)
	{
		const float Align = FVector::DotProduct(Wish.GetSafeNormal2D(), LegsFwd);
		SpeedFactor = Align >= 0.f ? FMath::Lerp(0.45f, 1.f, Align) : 0.45f;
	}
	const float MaxSpeed = WalkSpeed * (bSprint ? SprintMultiplier : 1.f) * SpeedFactor;
	FVector Desired = Wish.GetClampedToMaxSize2D(1.f) * MaxSpeed;
	// the two giants never close inside 50 m (centre to centre): from 70 m every step towards the opponent costs more and more effort,
	// at 50 m the approach stops dead (no stepping animation either). Walking away is always free.
	FVector ToOther = FVector::ZeroVector;
	float OtherDist = 1e9f;
	{
		if (!OtherMechCache.IsValid()) for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It) if (*It != this) { OtherMechCache = *It; break; }
		if (AIVMechPawn* Om = OtherMechCache.Get())
		{
			ToOther = Om->GetActorLocation() - GetActorLocation(); ToOther.Z = 0.f;
			OtherDist = ToOther.Size();
			ToOther = ToOther.GetSafeNormal();
			const float Appr = FVector::DotProduct(Desired, ToOther);
			if (Appr > 0.f)
			{
				const float F = FMath::Clamp((OtherDist - SetMinSep) / ((SetMinSep + 2000.f) - SetMinSep), 0.f, 1.f);
				const float Eff = F * F * (3.f - 2.f * F);                      // 0 at 50 m .. 1 at 70 m
				Desired -= ToOther * Appr * (1.f - FMath::Lerp(0.f, 1.f, Eff) * FMath::Lerp(0.55f, 1.f, Eff));
			}
		}
	}
	const FVector Delta = Desired - Velocity;
	const float Rate = (Mag > 0.05f) ? Acceleration : Deceleration;
	const float Step = Rate * Dt;
	Velocity += (Delta.Size2D() <= Step) ? Delta : Delta.GetSafeNormal2D() * Step;
	Velocity.Z = 0;
	if (OtherDist < (SetMinSep + 2000.f))
	{
		const float Vt = FVector::DotProduct(Velocity, ToOther);
		if (Vt > 0.f)
		{
			const float F = FMath::Clamp((OtherDist - SetMinSep) / ((SetMinSep + 2000.f) - SetMinSep), 0.f, 1.f);
			Velocity -= ToOther * Vt * (1.f - F);
		}
		if (OtherDist < SetMinSep) Velocity -= ToOther * FMath::Min(0.f, -FVector::DotProduct(Velocity, -ToOther)) ;
	}

	SetActorRotation(FRotator(0, NewLegsYaw, 0));
	if (!Velocity.IsNearlyZero())
	{
		FHitResult Hit;
		const FVector Move = Velocity * Dt;
		AddActorWorldOffset(Move, true, &Hit);
		if (Hit.IsValidBlockingHit())
		{
			// running into a building: it gives way (and costs the mech a little)
			CrashCooldown -= Dt;
			const float SpeedNow = Velocity.Size2D();
			if (CrashCooldown <= 0.f && SpeedNow > 260.f && Hit.GetComponent() && Hit.GetComponent()->IsA<UInstancedStaticMeshComponent>())
			{
				CrashCooldown = 0.45f;
				if (AIVEnvironment* Env = AIVEnvironment::Get(GetWorld()))
					Env->BlastAt(Hit.ImpactPoint + FVector(0, 0, 1500.f), 2400.f + 4.f * SpeedNow, 1100.f + 2.f * SpeedNow);
				if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) { FX->SpawnDust(Hit.ImpactPoint, 2400.f, 22, 1.4f); FX->SpawnSparks(Hit.ImpactPoint, Hit.ImpactNormal, 60, 5000.f); }
				IVAudio::Play3D(GetWorld(), TEXT("env_concrete_crumble"), Hit.ImpactPoint, 1.f);
				IVAudio::Play3D(GetWorld(), TEXT("hit_lowfreq_thump_heavy"), Hit.ImpactPoint, 1.f);
				if (IsLocallyControlled()) AddCockpitImpulse(0.f, 0.f, 0.9f);
				OnCrash.Broadcast(this, FMath::Clamp(SpeedNow / 800.f, 0.2f, 1.f));
			}
			const FVector Rest = FVector::VectorPlaneProject(Move, Hit.ImpactNormal) * (1.f - Hit.Time);
			AddActorWorldOffset(Rest, true);
			Velocity = FVector::VectorPlaneProject(Velocity, Hit.ImpactNormal) * 0.9f;
			Velocity.Z = 0;
		}
	}

	if (OtherDist < SetMinSep - 20.f && !bCine) AddActorWorldOffset(-ToOther * (SetMinSep - OtherDist) * FMath::Min(1.f, Dt * 5.f), false);
	FHitResult G;
	FCollisionQueryParams Q(SCENE_QUERY_STAT(IVGround), false, this);
	const FVector P = GetActorLocation();
	const float LiftTarget = (CombatAnim.posture == iv::Posture::Airborne) ? 3400.f * FMath::Sin(3.14159f * FMath::Clamp(CombatAnim.airProgress, 0.f, 1.f)) : 0.f;
	AirLift = FMath::FInterpTo(AirLift, LiftTarget, Dt, 12.f);
	if (GetWorld()->LineTraceSingleByChannel(G, P + FVector(0, 0, 3000), P - FVector(0, 0, 16000), ECC_WorldStatic, Q))
	{
		SetActorLocation(FVector(P.X, P.Y, G.ImpactPoint.Z + 4100.f + AirLift));
	}
}

void AIVMechPawn::UpdateGait(float Dt)
{
	const float Speed = Velocity.Size2D();
	const float Fwd = FVector::DotProduct(Velocity.GetSafeNormal2D(), GetActorForwardVector());
	const float Dir = (Fwd >= -0.2f) ? 1.f : -1.f;
	GaitAmp = FMath::FInterpTo(GaitAmp, FMath::Clamp(Speed / WalkSpeed, 0.f, 1.6f), Dt, 1.6f);

	PrevGaitPhase = GaitPhase;
	GaitPhase = FMath::Fmod(GaitPhase + Dir * Speed * Dt / (2.f * StrideLength) + 1.f, 1.f);

	const float A = GaitAmp;
	for (int32 i = 0; i < 2; ++i)
	{
		const float Ph = FMath::Fmod(GaitPhase + (i == 0 ? 0.f : 0.5f), 1.f);
		const float W = Ph * kTwoPi;
		const float ThighPitch = 26.f * A * FMath::Sin(W) + 3.f;
		const float KneeBend = 8.f + 58.f * A * FMath::Max(0.f, FMath::Cos(W));
		Thigh[i].Pivot->SetRelativeRotation(FRotator(ThighPitch, 0, 0));
		Shin[i].Pivot->SetRelativeRotation(FRotator(-KneeBend, 0, 0));
		Foot[i].Pivot->SetRelativeRotation(FRotator(KneeBend - ThighPitch, 0, 0));

		// footfall: the swinging leg reaches full extension at phase 0.25
		const float PrevPh = FMath::Fmod(PrevGaitPhase + (i == 0 ? 0.f : 0.5f), 1.f);
		if (PrevPh < 0.25f && Ph >= 0.25f && A > 0.15f)
		{
			OnFootfall.Broadcast(i == 0 ? -1 : 1, FMath::Clamp(A, 0.f, 1.f));
		}

		const float ArmSwing = -9.f * A * FMath::Sin(W);
		UpperArm[i].Pivot->SetRelativeRotation(FRotator(28.f + ArmSwing, 0, (i == 0 ? 6.f : -6.f)));
		Forearm[i].Pivot->SetRelativeRotation(FRotator(72.f, 0, 0));
		Hand[i].Pivot->SetRelativeRotation(FRotator(-10.f, 0, 0));
	}

	PelvisBob = -90.f * A * (0.5f + 0.5f * FMath::Cos(4.f * kTwoPi * (GaitPhase - 0.25f)));
	PelvisPivot->SetRelativeLocation(FVector(0, 0, 200.f + PelvisBob));
	PelvisPivot->SetRelativeRotation(FRotator(0, 0, 2.2f * A * FMath::Sin(GaitPhase * kTwoPi)));
}

void AIVMechPawn::UpdateCockpitArms(float Dt)
{
	if (!Camera || !CockpitArm[0].Upper) return;
	const FTransform CamT = CockpitSway->GetComponentTransform();   // children use this frame
	const float L1 = 55.f, L2 = 55.f;
	for (int32 i = 0; i < 2; ++i)
	{
		FCockpitArm& A = CockpitArm[i];
		const float Sd = (i == 0) ? -1.f : 1.f;           // UE: left = -Y
		const FVector Anchor(-6.f, Sd * 25.f, -26.f);
		const FVector Rest(58.f, Sd * 32.f, -44.f);
		FVector Tgt = Rest;
		FQuat GloveRot = FQuat::Identity;
		if (bRigActive && RigMesh)
		{
			const FName HandBone = (i == 0) ? FName(TEXT("hand_l")) : FName(TEXT("hand_r"));
			const FVector HandW = RigMesh->GetBoneLocation(HandBone, EBoneSpaces::WorldSpace);
			const FQuat HandQ = RigMesh->GetBoneQuaternion(HandBone, EBoneSpaces::WorldSpace);
			const FVector Rel = CamT.InverseTransformPosition(HandW);
			const FQuat RelQ = CamT.GetRotation().Inverse() * HandQ;
			if (!A.bHaveNeutral)
			{
				A.NeutralRel = Rel; A.NeutralRot = RelQ; A.bHaveNeutral = true;
				A.Smoothed = Rest; A.SmoothedRot = FQuat::Identity;
			}
			const float K = 0.0105f;
			FVector D = (Rel - A.NeutralRel) * K;
			D.X = FMath::Clamp(D.X, -40.f, 55.f);
			D.Y = FMath::Clamp(D.Y * 0.8f, -35.f, 35.f);
			D.Z = FMath::Clamp(D.Z, -28.f, 38.f);
			Tgt = Rest + D;
			FQuat Delta = RelQ * A.NeutralRot.Inverse();
			Delta.Normalize();
			GloveRot = FQuat::Slerp(FQuat::Identity, Delta, 0.55f);
		}
		const float Kf = 1.f - FMath::Exp(-Dt * 22.f);
		A.Smoothed = FMath::Lerp(A.Smoothed, Tgt, Kf);
		A.SmoothedRot = FQuat::Slerp(A.SmoothedRot, GloveRot, Kf);

		// two-bone IK from the wall anchor to the wrist
		FVector ToT = A.Smoothed - Anchor;
		float Dist = FMath::Clamp(ToT.Size(), FMath::Abs(L1 - L2) + 4.f, L1 + L2 - 1.f);
		const FVector Dir = ToT.GetSafeNormal();
		const FVector Pole = FVector(-0.1f, Sd * 0.55f, -1.f).GetSafeNormal();   // elbow drops outward/down
		FVector PoleOrtho = (Pole - Dir * FVector::DotProduct(Pole, Dir)).GetSafeNormal();
		const float Aa = (L1 * L1 - L2 * L2 + Dist * Dist) / (2.f * Dist);
		const float Hh = FMath::Sqrt(FMath::Max(L1 * L1 - Aa * Aa, 0.f));
		const FVector Elbow = Anchor + Dir * Aa + PoleOrtho * Hh;
		const FVector Wrist = Anchor + Dir * Dist;
		const FVector Up(0.f, Sd * 0.25f, 1.f);
		const FVector Sc(1.f, -Sd * -1.f * (i == 0 ? 1.f : -1.f), 1.f);
		auto Place = [&](UStaticMeshComponent* M, const FVector& P, const FQuat& Q)
		{
			M->SetRelativeLocationAndRotation(P, Q);
			M->SetRelativeScale3D(FVector(1.f, (i == 0) ? 1.f : -1.f, 1.f));
		};
		Place(A.Upper, Anchor, FRotationMatrix::MakeFromXZ((Elbow - Anchor).GetSafeNormal(), Up).ToQuat());
		Place(A.Fore, Elbow, FRotationMatrix::MakeFromXZ((Wrist - Elbow).GetSafeNormal(), Up).ToQuat());
		const FQuat Base = FRotationMatrix::MakeFromXZ((Wrist - Elbow).GetSafeNormal(), Up).ToQuat();
		Place(A.Glove, Wrist, A.SmoothedRot * Base);
	}
}


namespace
{
	float OtherDirYaw(AIVMechPawn* A)
	{
		for (TActorIterator<AIVMechPawn> It(A->GetWorld()); It; ++It)
			if (*It != A) return (It->GetActorLocation() - A->GetActorLocation()).Rotation().Yaw;
		return A->GetActorRotation().Yaw;
	}
}

void AIVMechPawn::UpdateCockpitCamera(float Dt)
{
	const int32 Mode = GetIVCam();
	SetFirstPersonView(Mode == 0);

	// sway layer: spring-damper driven by acceleration and footfalls
	const FVector Accel = (Velocity - PrevVelocity) / FMath::Max(Dt, 1e-4f);
	PrevVelocity = Velocity;
	const FVector LocalAcc = FRotator(0, CamRot.Yaw, 0).UnrotateVector(Accel);
	const float K = 55.f, C = 8.5f;
	const FVector Target(-LocalAcc.X * 0.035f, -LocalAcc.Y * 0.035f, 0.f);
	SwayVel += (-(SwayOffset - Target) * K - SwayVel * C) * Dt;
	SwayOffset += SwayVel * Dt;
	SwayOffset = SwayOffset.GetClampedToSize(0.f, 14.f);
	const FVector RotAcc(-SwayRot.Roll * K - SwayRotVel.X * C, -SwayRot.Pitch * K - SwayRotVel.Y * C, -SwayRot.Yaw * K - SwayRotVel.Z * C);
	SwayRotVel += RotAcc * Dt;
	SwayRot.Roll += SwayRotVel.X * Dt;
	SwayRot.Pitch += SwayRotVel.Y * Dt;
	SwayRot.Yaw += SwayRotVel.Z * Dt;
	if (bDebugLook) bFreeLook = true;
	// head look inside the room: the camera turns, the room stays where it is (the inverse look is applied to the cockpit)
	LookYaw = FMath::FInterpTo(LookYaw, bFreeLook ? LookYawT : 0.f, Dt, bFreeLook ? 18.f : 6.f);
	LookPitch = FMath::FInterpTo(LookPitch, bFreeLook ? LookPitchT : 0.f, Dt, bFreeLook ? 18.f : 6.f);
	if (!bFreeLook) { LookYawT = FMath::FInterpTo(LookYawT, 0.f, Dt, 6.f); LookPitchT = FMath::FInterpTo(LookPitchT, 0.f, Dt, 6.f); }
	const FQuat LookQ = FRotator(LookPitch, LookYaw, 0.f).Quaternion();
	CockpitSway->SetRelativeLocationAndRotation(LookQ.Inverse().RotateVector(SwayOffset), LookQ.Inverse() * SwayRot.Quaternion());

	// world layer: stabilised horizon, low-passed vertical bob
	const FVector Eye = GetEyeLocation();
	CamPos.X = Eye.X;
	CamPos.Y = Eye.Y;
	CamPos.Z = FMath::FInterpTo(CamPos.Z, Eye.Z, Dt, 5.f);
	{
		static float EyeLogT = 0.f; EyeLogT += Dt;
		if (EyeLogT > 3.f && !bAIControlled && RigMesh)
		{
			EyeLogT = 0.f;
			UE_LOG(LogTemp, Display, TEXT("IV eye: aimPitch=%.1f camPitch=%.1f eyeZ=%.0f headBoneZ=%.0f torsoZ=%.0f footZ=%.0f actorZ=%.0f"), AimPitch, CamRot.Pitch, Eye.Z, RigMesh->GetBoneLocation(FName(TEXT("head")), EBoneSpaces::WorldSpace).Z, RigMesh->GetBoneLocation(FName(TEXT("torso")), EBoneSpaces::WorldSpace).Z, RigMesh->GetBoneLocation(FName(TEXT("foot_l")), EBoneSpaces::WorldSpace).Z, GetActorLocation().Z);
			for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It) if (*It != this && It->RigMesh) UE_LOG(LogTemp, Display, TEXT("IV eye: enemy headZ=%.0f torsoZ=%.0f"), It->RigMesh->GetBoneLocation(FName(TEXT("head")), EBoneSpaces::WorldSpace).Z, It->RigMesh->GetBoneLocation(FName(TEXT("torso")), EBoneSpaces::WorldSpace).Z);
		}
	}
	CamRot.Yaw = GetActorRotation().Yaw + TorsoYawRel;
	CamRot.Pitch = FMath::FInterpTo(CamRot.Pitch, AimPitch, Dt, 14.f);
	CamRot.Roll = 0.25f * PelvisPivot->GetRelativeRotation().Roll;

	if (bBoardCam && !bCine)
	{
		SetFirstPersonView(false);
		Camera->SetFieldOfView(BoardFov);
		Camera->SetWorldLocationAndRotation(BoardFrom, (BoardAt - BoardFrom).Rotation());
		return;
	}
	if (bCine)
	{
		SetFirstPersonView(false);
		CineT += Dt;
		AIVMechPawn* Sub = CineSubject.Get();
		if (!Sub) Sub = this;
		const float U = FMath::Clamp(CineT / FMath::Max(CineDur, 0.1f), 0.f, 1.f);
		// UltimateFrame: the ultimate (kinds 1, 5, 6) frames both mechs from the side; weapon cuts orbit the shooter
		const bool bUlt = (CineKind == 1 || CineKind == 5 || CineKind == 6);
		FVector CC = Sub->GetActorLocation() + FVector(0, 0, 2800.f);
		float Dist = 9500.f;
		if (bUlt)
		{
			FVector OtherLoc = Sub->GetActorLocation();
			for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It) if (*It != Sub) OtherLoc = It->GetActorLocation();
			CC = (Sub->GetActorLocation() + OtherLoc) * 0.5f + FVector(0, 0, 4200.f);
			Dist = 16500.f;
		}
		const float Ang = FMath::Lerp(-70.f, 35.f, U);
		const float YawBase = bUlt ? (OtherDirYaw(Sub)) + 90.f : Sub->GetActorRotation().Yaw + 90.f;
		const FVector Off = FRotator(0.f, YawBase + Ang * (bUlt ? 0.5f : 1.f), 0.f).Vector() * Dist;
		const FVector From2 = CC + Off + FVector(0, 0, bUlt ? FMath::Lerp(-2500.f, 1500.f, U) : FMath::Lerp(-1500.f, 600.f, U));
		Camera->SetFieldOfView(bUlt ? 50.f : 58.f);
		Camera->SetWorldLocationAndRotation(From2, (CC + FVector(0, 0, bUlt ? 0.f : 900.f) - From2).Rotation());
		return;
	}
	{
		UGameViewportClient* VPC = GetWorld() ? GetWorld()->GetGameViewport() : nullptr;
		const bool bSplit = VPC && VPC->GetCurrentSplitscreenConfiguration() != ESplitScreenType::None;
		Camera->SetFieldOfView((bSplit ? SetFov - 22.f : SetFov) - 7.f * Rage);
	}

	if (Mode == 0)
	{
		ShakeAmp = FMath::FInterpTo(ShakeAmp, 0.f, Dt, 3.4f);
		const float ShakeUse = ShakeAmp * SetShake;
		const float Tm = GetWorld()->GetTimeSeconds();
		const FRotator Shk(ShakeUse * 1.1f * FMath::Sin(Tm * 47.f), ShakeUse * 1.1f * FMath::Sin(Tm * 59.f + 1.f), ShakeUse * 1.6f * FMath::Sin(Tm * 39.f + 2.f));
		Camera->SetWorldLocationAndRotation(CamPos + FVector(0.f, 0.f, ShakeUse * 1.8f * FMath::Sin(Tm * 71.f)), (CamRot + FRotator(0.3f * SwayRot.Pitch, 0.3f * SwayRot.Yaw, 0.3f * SwayRot.Roll) + Shk).Quaternion() * LookQ);
		return;
	}

	if (Mode == 6)
	{
		FString Spec = CVarIVFreeCam.GetValueOnGameThread();
		FString Cli;
		if (FParse::Value(FCommandLine::Get(), TEXT("-IVFreeCams="), Cli, false)) Spec = Cli;
		TArray<FString> Cams;
		Spec.ParseIntoArray(Cams, TEXT("|"));
		float Dur = 3.f; FParse::Value(FCommandLine::Get(), TEXT("-IVFreeDur="), Dur);
		if (Cams.Num() > 0)
		{
			const int32 Idx = FMath::Clamp(FMath::FloorToInt(GetWorld()->GetTimeSeconds() / Dur), 0, Cams.Num() - 1);
			TArray<FString> P;
			Cams[Idx].Replace(TEXT(","), TEXT(" ")).ParseIntoArray(P, TEXT(" "));
			if (P.Num() >= 5)
			{
				const FVector At(FCString::Atof(*P[1]) * 100.f, FCString::Atof(*P[0]) * 100.f, FCString::Atof(*P[2]) * 100.f);
				Camera->SetFieldOfView(P.Num() >= 6 ? FCString::Atof(*P[5]) : 70.f);
				Camera->SetWorldLocationAndRotation(At, FRotator(FCString::Atof(*P[3]), FCString::Atof(*P[4]), 0.f));
			}
		}
		return;
	}
	if (Mode == 5)
	{
		FVector Other = GetActorLocation();
		for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It) if (*It != this) Other = It->GetActorLocation();
		const FVector Mid = (GetActorLocation() + Other) * 0.5f + FVector(0, 0, 3600.f);
		const float Ang = GetWorld()->GetTimeSeconds() * 3.2f + 75.f;
		const float Rad = 15500.f + 2200.f * FMath::Sin(GetWorld()->GetTimeSeconds() * 0.21f);
		const FVector From5 = Mid + FRotator(0.f, Ang, 0.f).Vector() * Rad + FVector(0, 0, 500.f + 900.f * FMath::Sin(GetWorld()->GetTimeSeconds() * 0.33f));
		Camera->SetFieldOfView(52.f);
		Camera->SetWorldLocationAndRotation(From5, (Mid - From5).Rotation());
		return;
	}
	// debug cameras for visual checks from outside
	const float D = GetIVCamDist();
	const FVector Center = GetActorLocation() + FVector(0, 0, 4200);
	FVector From;
	FRotator Look;
	const float Yaw = GetActorRotation().Yaw;
	if (Mode == 1) { From = Center - FRotator(0, Yaw, 0).Vector() * D + FVector(0, 0, 1500); Look = (Center - From).Rotation(); }
	else if (Mode == 2) { From = Center + FRotator(0, Yaw + 90, 0).Vector() * D; Look = (Center - From).Rotation(); }
	else if (Mode == 3) { From = Center + FRotator(0, Yaw + 25, 0).Vector() * D + FVector(0, 0, -1500); Look = (Center - From).Rotation(); }
	else
	{
		FVector Other = Center;
		for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It)
		{
			if (*It != this) Other = It->GetActorLocation() + FVector(0, 0, 4200);
		}
		const FVector Mid = (Center + Other) * 0.5f;
		const FVector Side = FRotator(0, (Other - Center).Rotation().Yaw + 90, 0).Vector();
		From = Mid + Side * D + FVector(0, 0, 600);
		Look = (Mid - From).Rotation();
	}
	Camera->SetWorldLocationAndRotation(From, Look);
	static float DbgT = 0.f; DbgT += Dt;
	if (DbgT > 1.5f && !bAIControlled)
	{
		DbgT = 0.f;
		UE_LOG(LogTemp, Display, TEXT("IV cam debug: mode=%d D=%.0f actor=%s cam=%s rigvis=%d rigloc=%s rigb=%s"), Mode, D, *GetActorLocation().ToString(), *From.ToString(), RigMesh ? RigMesh->IsVisible() : -1, RigMesh ? *RigMesh->GetComponentLocation().ToString() : TEXT("-"), RigMesh ? *RigMesh->Bounds.GetBox().ToString() : TEXT("-"));
	}
}

void AIVMechPawn::DebugBlast(float Radius, float Impulse)
{
	const FVector From = Camera->GetComponentLocation();
	const FVector Dir = Camera->GetForwardVector();
	FHitResult Hit;
	FCollisionQueryParams Q(SCENE_QUERY_STAT(IVBlast), false, this);
	const FVector To = From + Dir * 250000.f;
	if (GetWorld()->LineTraceSingleByChannel(Hit, From, To, ECC_Visibility, Q) || GetWorld()->LineTraceSingleByChannel(Hit, From, To, ECC_WorldStatic, Q))
	{
		const FVector P = Hit.ImpactPoint;
		if (AIVEnvironment* Env = AIVEnvironment::Get(GetWorld())) Env->BlastAt(P, Radius, Impulse);
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
		{
			FX->SpawnSparks(P, Hit.ImpactNormal, 40, 6000.f);
			FX->SpawnDust(P, Radius, 14, 0.8f);
		}
	}
}

// ---------------------------------------------------------------------------------------------------------------
void AIVMechPawn::SetupRig()
{
	USkeletalMesh* SM = LoadObject<USkeletalMesh>(nullptr, *RigAssetPath);
	if (!SM) return;
	static TSharedPtr<FIVRigData> Shared;
	if (!Shared.IsValid())
	{
		Shared = MakeShared<FIVRigData>();
		const FString D = FPaths::ProjectContentDir() / TEXT("Data/");
		if (!Shared->Load(D + TEXT("poses.json"), D + TEXT("locomotion.json")))
		{
			UE_LOG(LogTemp, Warning, TEXT("IV rig: anim data missing in Content/Data"));
			Shared.Reset();
			return;
		}
	}
	RigData = Shared;
	if (!RigDriver.Init(SM)) return;
	RigMesh->SetSkeletalMesh(SM);
	if (SwordMesh && SwordMesh->GetStaticMesh())
	{
		// The blade points along the hand bone's tail direction (down while the arm hangs); the grip sits in the fist.
		const FQuat Qh = RigMesh->GetBoneQuaternion(FName(TEXT("hand_r")), EBoneSpaces::ComponentSpace);
		SwordBladeDirLocal = Qh.UnrotateVector(FVector(0, 0, -1)).GetSafeNormal();
		float RollDeg = 0.f;
		FParse::Value(FCommandLine::Get(), TEXT("-IVSwordRoll="), RollDeg);
		SwordRelRot = FQuat::FindBetweenNormals(FVector(1, 0, 0), SwordBladeDirLocal) * FQuat(FVector(1, 0, 0), FMath::DegreesToRadians(RollDeg));
		SwordMesh->AttachToComponent(RigMesh, FAttachmentTransformRules::SnapToTargetNotIncludingScale, FName(TEXT("hand_r")));
		// the imported bones carry a uniform rest scale of 100: compensate so the sword keeps its size
		SwordMesh->SetRelativeLocationAndRotation(SwordBladeDirLocal * 5.2f, SwordRelRot);
		SwordMesh->SetRelativeScale3D(FVector(0.01f, 0.015f, 0.015f));   // arm blade: the bracer housing has to fit the forearm
		if (UMaterialInterface* SM2 = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Sword.M_Sword")))
		{
			SwordMID = UMaterialInstanceDynamic::Create(SM2, this);
			SwordMID->SetVectorParameterValue(TEXT("EdgeColor"), SwordEdge);
			SwordMID->SetScalarParameterValue(TEXT("Heat"), 0.8f);
			SwordMesh->SetMaterial(0, SwordMID);
		}
		if (UMaterialInterface* TM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_BladeTrail.M_BladeTrail")))
		{
			TrailMID = UMaterialInstanceDynamic::Create(TM, this);
			TrailMID->SetVectorParameterValue(TEXT("EdgeColor"), SwordEdge);
			TrailMID->SetScalarParameterValue(TEXT("Gain"), 0.55f);
			BladeTrail->SetMaterial(0, TrailMID);
		}
		SwordMesh->SetVisibility(true);
		UE_LOG(LogTemp, Display, TEXT("IV sword: attached, bladeDirLocal=%s relRot=%s world=%s"), *SwordBladeDirLocal.ToString(), *SwordRelRot.Rotator().ToString(), *SwordMesh->GetComponentLocation().ToString());
	}
	else UE_LOG(LogTemp, Warning, TEXT("IV sword: mesh missing (%d %d)"), SwordMesh != nullptr, SwordMesh && SwordMesh->GetStaticMesh() != nullptr);
	if (bUseHullMaterial)
	{
		if (UMaterialInterface* HM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_MechHull.M_MechHull")))
		{
			HullMID = UMaterialInstanceDynamic::Create(HM, this);
			HullMID->SetVectorParameterValue(TEXT("Tint"), HullTint);
			HullMID->SetVectorParameterValue(TEXT("Accent"), HullAccent);
			HullMID->SetVectorParameterValue(TEXT("Glow"), HullGlow);
			HullMID->SetScalarParameterValue(TEXT("AccentAmount"), HullAccentAmount);
			for (int32 i = 0; i < RigMesh->GetNumMaterials(); ++i) RigMesh->SetMaterial(i, HullMID);
		}
	}
	if (!FParse::Param(FCommandLine::Get(), TEXT("IVNoAnim")))
	{
		RigMesh->SetAnimationMode(EAnimationMode::AnimationBlueprint);
		RigMesh->SetAnimInstanceClass(UIVRigAnimInstance::StaticClass());
		RigMesh->InitAnim(true);
		RigAnim = Cast<UIVRigAnimInstance>(RigMesh->GetAnimInstance());
		if (!RigAnim) { UE_LOG(LogTemp, Warning, TEXT("IV rig: anim instance missing")); return; }
	}
	RigMesh->SetVisibility(true);
	RigMesh->SetBoundsScale(1.6f);
	if (bInfected && GrowthComps.Num() == 0) BuildGrowths();
	if (GreebleComps.Num() == 0 && !FParse::Param(FCommandLine::Get(), TEXT("IVNoGreeble"))) BuildGreebles();
	if (Plates.Num() == 0 && !FParse::Param(FCommandLine::Get(), TEXT("IVNoPlates"))) BuildPlates();
	for (UStaticMeshComponent* M : AllMeshes) M->SetVisibility(false);
	bRigActive = true;
	if (RigAnim)
	if (const FIVPoseAngles* G = RigData->FindPose(FName(TEXT("guard_neutral"))))
	{
		RigDriver.Compute(*G, RigAnim->PoseLocal);
	}
	if (RigAnim)
	{
		int32 Bad = 0;
		for (const FTransform& T : RigAnim->PoseLocal) if (T.ContainsNaN()) ++Bad;
		UE_LOG(LogTemp, Display, TEXT("IV rig pose check: %d transforms, %d NaN"), RigAnim->PoseLocal.Num(), Bad);
		for (int32 i = 0; i < FMath::Min(4, RigAnim->PoseLocal.Num()); ++i)
			UE_LOG(LogTemp, Display, TEXT("IV rig local[%d]: %s"), i, *RigAnim->PoseLocal[i].ToHumanReadableString());
	}
	UE_LOG(LogTemp, Display, TEXT("IV rig active: %d poses, %d clips, %d bones"), RigData->Poses.Num(), RigData->Clips.Num(), RigDriver.NumBones());
}

void AIVMechPawn::GetBladeSegment(FVector& OutBase, FVector& OutTip) const
{
	if (!SwordMesh) { OutBase = OutTip = GetActorLocation(); return; }
	const FTransform T = SwordMesh->GetComponentTransform();
	OutBase = T.TransformPosition(FVector(500.f, 0, 0));
	OutTip = T.TransformPosition(FVector(6100.f, 0, 0));
}

void AIVMechPawn::SetSwordHeat(float Heat)
{
	if (SwordMID) SwordMID->SetScalarParameterValue(TEXT("Heat"), Heat);
}

void AIVMechPawn::SetHullDamage(float Amount)
{
	if (HullMID) HullMID->SetScalarParameterValue(TEXT("Damage"), FMath::Clamp(Amount, 0.f, 1.f));
}

void AIVMechPawn::PlayAction(FName Action, float Speed)
{
	if (!bRigActive || !RigData.IsValid()) return;
	ActionSteps.Reset();
	const float S = FMath::Max(Speed, 0.2f);
	auto Step = [&](const FString& Suffix, float Dur) {
		const FName N(*(Action.ToString() + Suffix));
		if (RigData->FindPose(N)) ActionSteps.Add({ N, Dur / S });
	};
	if (RigData->FindPose(FName(*(Action.ToString() + TEXT("_windup")))))
	{
		Step(TEXT("_windup"), 0.9f); Step(TEXT("_commit"), 0.18f); Step(TEXT("_strike_end"), 0.32f); Step(TEXT("_recovery"), 0.9f);
	}
	else if (RigData->FindPose(FName(*(Action.ToString() + TEXT("_shift")))))
	{
		Step(TEXT("_shift"), 0.6f); Step(TEXT("_lift"), 0.5f); Step(TEXT("_plant"), 0.7f);
	}
	else if (RigData->FindPose(Action))
	{
		ActionSteps.Add({ Action, 1.4f / S });
	}
	if (ActionSteps.Num() == 0) return;
	ActionSteps.Add({ FName(TEXT("guard_neutral")), 0.8f / S });
	ActionIndex = 0;
	ActionTimer = 0.f;
	ActionFrom = FIVPoseAngles();      // blended from the current locomotion pose on the first tick
}

void AIVMechPawn::UpdateRig(float Dt)
{
	const FIVRigData& D = *RigData;
	const float Speed = Velocity.Size2D();

	// ---- locomotion layer: pick the clip whose speed is closest, scale playback so that feet do not slide
	struct FGait { const TCHAR* Clip; float Speed; };
	static const FGait Gaits[] = { { TEXT("walk_slow_cycle"), 400.f }, { TEXT("walk_cycle"), 580.f }, { TEXT("walk_fast_cycle"), 870.f }, { TEXT("run_cycle"), 1080.f } };
	int32 Best = 0;
	for (int32 i = 0; i < 4; ++i) if (FMath::Abs(Gaits[i].Speed - Speed) < FMath::Abs(Gaits[Best].Speed - Speed)) Best = i;
	const FIVClip* Clip = D.FindClip(FName(Gaits[Best].Clip));
	const FIVPoseAngles* Guard = D.FindPose(FName(TEXT("guard_neutral")));
	FIVPoseAngles Pose = Guard ? *Guard : FIVPoseAngles();
	static float Breath = 0.f;
	Breath += Dt;
	if (Clip && Speed > 20.f)
	{
		const float Rate = FMath::Clamp(Speed / Gaits[Best].Speed, 0.35f, 1.5f);
		RigClipTime += Dt * Rate * (FVector::DotProduct(Velocity.GetSafeNormal2D(), GetActorForwardVector()) >= -0.2f ? 1.f : -1.f);
		const FIVPoseAngles Walk = D.SampleClip(*Clip, RigClipTime, true);
		Pose = FIVPoseAngles::Lerp(Pose, Walk, FMath::Clamp(Speed / 220.f, 0.f, 1.f));

		// footfalls from the clip contact flags
		const int32 N = Clip->Frames.Num();
		float F = FMath::Fmod(RigClipTime * Clip->Fps, float(N));
		if (F < 0.f) F += N;
		const FIVClipFrame& Fr = Clip->Frames[FMath::FloorToInt(F) % N];
		if (Fr.bContactL && !bPrevContactL) OnFootfall.Broadcast(-1, FMath::Clamp(Speed / 650.f, 0.3f, 1.f));
		if (Fr.bContactR && !bPrevContactR) OnFootfall.Broadcast(1, FMath::Clamp(Speed / 650.f, 0.3f, 1.f));
		bPrevContactL = Fr.bContactL; bPrevContactR = Fr.bContactR;
	}
	else
	{
		// idle: slow breathing on the torso
		if (FVector* T = Pose.Joint.Find(FName(TEXT("torso")))) T->X += 0.6f * FMath::Sin(Breath * 0.9f);
	}

	if (bCombat) BuildCombatPose(Pose, Dt);
	if (bCombat) UpdateBladeContact(Dt, Pose);

	// ---- action layer (upper body): sequence of named poses with heavy easing
	if (ActionIndex >= 0 && ActionSteps.IsValidIndex(ActionIndex))
	{
		if (ActionTimer == 0.f && ActionIndex == 0) ActionFrom = Pose;
		ActionTimer += Dt;
		const FActionStep& St = ActionSteps[ActionIndex];
		const float U = FMath::Clamp(ActionTimer / FMath::Max(St.Duration, 0.01f), 0.f, 1.f);
		const float E = 1.f - FMath::Pow(1.f - U, 2.6f);          // fast start, slow finish ("ease_heavy")
		const FIVPoseAngles* Target = D.FindPose(St.Pose);
		if (Target)
		{
			static const TCHAR* Upper[] = { TEXT("torso"), TEXT("head"), TEXT("reactor"), TEXT("shoulder_l"), TEXT("upperarm_l"), TEXT("forearm_l"), TEXT("hand_l"),
				TEXT("shoulder_r"), TEXT("upperarm_r"), TEXT("forearm_r"), TEXT("hand_r"), TEXT("pelvis"), TEXT("thigh_l"), TEXT("shin_l"), TEXT("foot_l"), TEXT("thigh_r"), TEXT("shin_r"), TEXT("foot_r") };
			const bool bLegsToo = St.Pose.ToString().Contains(TEXT("dodge")) || St.Pose.ToString().Contains(TEXT("hard")) || St.Pose.ToString().Contains(TEXT("kneel")) || St.Pose.ToString().Contains(TEXT("knockdown"));
			const int32 NUpper = bLegsToo ? UE_ARRAY_COUNT(Upper) : 11;
			FIVPoseAngles Prev = (ActionIndex == 0) ? ActionFrom : *D.FindPose(ActionSteps[ActionIndex - 1].Pose);
			for (int32 i = 0; i < NUpper; ++i)
			{
				const FName B(Upper[i]);
				const FVector* A = Prev.Joint.Find(B);
				const FVector* T2 = Target->Joint.Find(B);
				if (A && T2) Pose.Joint.Add(B, FMath::Lerp(*A, *T2, E));
			}
			ActionWeight = 1.f;
		}
		if (ActionTimer >= St.Duration) { ActionTimer = 0.f; ++ActionIndex; }
	}
	else
	{
		ActionIndex = -1;
		ActionWeight = FMath::FInterpTo(ActionWeight, 0.f, Dt, 4.f);
	}
	if (CVarRigApply.GetValueOnGameThread() != 0 && RigAnim) RigDriver.Compute(Pose, RigAnim->PoseLocal);
}

// =====================================================================================================================
//  Combat presentation
// =====================================================================================================================
namespace
{
	const TCHAR* SideName(iv::SwingSide S)
	{
		switch (S) { case iv::SwingSide::Up: return TEXT("up"); case iv::SwingSide::Left: return TEXT("left"); case iv::SwingSide::Right: return TEXT("right"); default: return TEXT("down"); }
	}
	FName BoneForZone(iv::Zone Z)
	{
		switch (Z)
		{
		case iv::Zone::Head: return FName(TEXT("head"));
		case iv::Zone::Torso: return FName(TEXT("torso"));
		case iv::Zone::Reactor: return FName(TEXT("reactor"));
		case iv::Zone::ShoulderL: return FName(TEXT("shoulder_l"));
		case iv::Zone::ShoulderR: return FName(TEXT("shoulder_r"));
		case iv::Zone::ArmL: return FName(TEXT("forearm_l"));
		case iv::Zone::ArmR: return FName(TEXT("forearm_r"));
		case iv::Zone::LegL: return FName(TEXT("shin_l"));
		default: return FName(TEXT("shin_r"));
		}
	}
	float ZoneSide(iv::Zone Z)     // -1 = mech's left, +1 = right, 0 = centre
	{
		switch (Z)
		{
		case iv::Zone::ShoulderL: case iv::Zone::ArmL: case iv::Zone::LegL: return -1.f;
		case iv::Zone::ShoulderR: case iv::Zone::ArmR: case iv::Zone::LegR: return 1.f;
		default: return 0.f;
		}
	}
}

FVector AIVMechPawn::GetZoneWorldLocation(iv::Zone Z) const
{
	if (bRigActive && RigMesh) return RigMesh->GetBoneLocation(BoneForZone(Z), EBoneSpaces::WorldSpace);
	return GetActorLocation() + FVector(0, 0, 2000.f);
}

void AIVMechPawn::AddCockpitImpulse(float Right, float Up, float Strength)
{
	const float S = Strength * (Strength > 0.7f ? 1.5f : 1.f);
	SwayVel += FVector(-45.f * S, 55.f * Right * S, 40.f * Up * S);
	SwayRotVel += FVector(-14.f * Right * S, -9.f * S * FMath::Abs(Up) - 7.f * S, 9.f * Right * S);
	if (IsLocallyControlled())
	{
		ShakeAmp = FMath::Max(ShakeAmp, FMath::Min(Strength, 2.5f));
		if (AIVPlayerController* C = Cast<AIVPlayerController>(GetController())) C->Rumble(FMath::Clamp(Strength * 0.45f, 0.f, 1.f), 0.12f + 0.16f * FMath::Min(Strength, 2.f));
	}
}

void AIVMechPawn::OnCombatHit(iv::Zone Z, float Strength01, bool bBlocked, bool bParried, iv::SwingSide Dir)
{
	const FVector Loc = GetZoneWorldLocation(Z);
	if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
	{
		const float K = bParried ? 1.2f : (bBlocked ? 0.6f : 1.f);
		FX->SpawnSparks(Loc, GetActorForwardVector() + FVector(0, 0, 0.3f), int32(10 + 55 * Strength01 * K), 3000.f + 4000.f * Strength01);
		if (Strength01 > 0.35f && !bBlocked) FX->SpawnDust(Loc, 900.f + 1800.f * Strength01, int32(4 + 12 * Strength01), 0.5f + Strength01);
		if (Strength01 > 0.3f && !bBlocked)
		{
			const FVector Out = GetActorForwardVector() * 0.6f + GetActorRightVector() * ZoneSide(Z) * 0.8f + FVector(0, 0, 0.7f);
			FX->SpawnChunks(Loc, Out, 1 + int32(5.f * Strength01), EIVChunk::Armor, 2.4f + 1.6f * Strength01, 2600.f + 3600.f * Strength01, 0.5f + 0.5f * Strength01);
		}
	}
	if (IsLocallyControlled() && !bBlocked && Strength01 > 0.3f && GlassMID)
	{
		GlassCrack = FMath::Min(GlassCrack + 0.035f + 0.09f * Strength01, 0.85f);
		GlassMID->SetScalarParameterValue(TEXT("Crack"), GlassCrack);
		{
			static int32 Slot = 0;
			const float Lat = FMath::Clamp(ZoneSide(Z) * 0.35f + FMath::FRandRange(-0.3f, 0.3f), -0.75f, 0.75f);
			const FLinearColor Imp(Lat, FMath::FRandRange(-0.05f, 0.5f), FMath::Clamp(0.4f + 0.6f * Strength01 + 0.2f * GlassCrack, 0.f, 1.2f), 0.f);
			GlassMID->SetVectorParameterValue(*FString::Printf(TEXT("Imp%d"), Slot % 3), Imp);
			++Slot;
		}
		IVAudio::Play2D(GetWorld(), TEXT("cockpit_panel_burst"), 0.5f, 1.6f);
	}
	const float Side = ZoneSide(Z);
	const float S = Strength01 * (bBlocked ? 0.55f : 1.f);
	HitKick += FVector(-7.f * S, 4.f * S * Side, 6.f * S * Side);
	HitKick = HitKick.GetClampedToSize(0.f, 18.f);
	if (IsLocallyControlled())
	{
		AddCockpitImpulse(-Side, Z == iv::Zone::Head ? 0.8f : 0.f, S * (bParried ? 0.6f : 1.f));
		if (CockpitFx) CockpitFx->Hit(FMath::Clamp(Strength01 * 1.15f, 0.f, 1.f), FVector(0.f, Side, 0.f), bBlocked);
	}
}

void AIVMechPawn::OnDefenceEffect(bool bParry, bool bIntercept)
{
	const FVector Loc = GetZoneWorldLocation(CombatAnim.arm == iv::Arm::L ? iv::Zone::ArmL : iv::Zone::ArmR);
	if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
	{
		FX->SpawnSparks(Loc, GetActorForwardVector(), bParry || bIntercept ? 80 : 35, 5000.f);
	}
	if (IsLocallyControlled()) AddCockpitImpulse(0.f, 0.f, bParry ? 0.3f : 0.6f);
}

void AIVMechPawn::OnZoneState(iv::Zone Z, iv::ZoneState NewState, iv::ZoneState OldState)
{
	ZoneStates[iv::Index(Z)] = NewState;
	if (IsLocallyControlled() && CockpitFx) CockpitFx->ZoneChanged(Z, NewState, OldState);
	AIVFXManager* FX = AIVFXManager::Get(GetWorld());
	const FVector Loc = GetZoneWorldLocation(Z);
	if (FX)
	{
		if (NewState >= iv::ZoneState::Damaged && OldState < iv::ZoneState::Damaged) FX->SpawnDust(Loc, 700.f, 6, 0.4f);
		if (NewState >= iv::ZoneState::Damaged && OldState < iv::ZoneState::Damaged)
			FX->SpawnChunks(Loc, GetActorForwardVector() * 0.5f + FVector(0, 0, 0.8f), 3, EIVChunk::Armor, 3.f, 3200.f, 0.6f);
		if (NewState >= iv::ZoneState::Critical && OldState < iv::ZoneState::Critical)
			FX->SpawnChunks(Loc, FVector(0, 0, 1.f), 7, EIVChunk::Armor, 3.6f, 4800.f, 1.f, 1.1f);
		if (NewState >= iv::ZoneState::Destroyed && OldState < iv::ZoneState::Destroyed)
		{
			FX->SpawnChunks(Loc, FVector(0, 0, 1.f), 12, EIVChunk::Armor, 4.4f, 6200.f, 1.f, 1.3f);
			FX->SpawnChunks(Loc, FVector(0, 0, 1.f), 6, EIVChunk::Steel, 3.f, 5200.f, 0.9f, 1.3f);
		}
		if (NewState >= iv::ZoneState::Critical && OldState < iv::ZoneState::Critical)
		{
			FX->SpawnExplosion(Loc, 0.9f);
			IVAudio::Play3D(GetWorld(), TEXT("cockpit_panel_burst"), Loc, 1.f);
			IVAudio::Play3D(GetWorld(), TEXT("env_distant_boom_01"), Loc, 0.8f);
		}
		if (NewState >= iv::ZoneState::Destroyed && OldState < iv::ZoneState::Destroyed)
		{
			FX->SpawnExplosion(Loc, 1.6f);
			IVAudio::Play3D(GetWorld(), TEXT("env_distant_boom_01"), Loc, 1.f);
			if (IsLocallyControlled()) AddCockpitImpulse(0.f, 0.5f, 1.4f);
		}
	}
	RefreshHullDamage();
}

void AIVMechPawn::RefreshHullDamage()
{
	float Sum = 0.f;
	for (int32 i = 0; i < iv::kZoneCount; ++i) Sum += FMath::Clamp(float(int32(ZoneStates[i])) / 5.f, 0.f, 1.f);
	SetHullDamage(Sum / float(iv::kZoneCount) * 1.6f);
}

void AIVMechPawn::OnStatus(iv::StatusKind K, bool bOn, float Seconds)
{
	switch (K)
	{
	case iv::StatusKind::Blind:
		BlindLeft = bOn ? Seconds : 0.f;
		BlindTotal = FMath::Max(Seconds, 0.5f);
		if (bOn && IsLocallyControlled()) { AddCockpitImpulse(0.f, 0.4f, 1.2f); IVAudio::Play2D(GetWorld(), TEXT("cockpit_alarm_warning"), 0.8f); }
		break;
	case iv::StatusKind::StrikeLock:
		bStrikeLocked = bOn;
		if (bOn)
		{
			if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) FX->SpawnSparks(GetZoneWorldLocation(iv::Zone::ArmR), FVector::UpVector, 120, 6000.f);
			if (IsLocallyControlled()) { AddCockpitImpulse(0.f, 0.f, 1.f); IVAudio::Play2D(GetWorld(), TEXT("cockpit_alarm_critical"), 0.8f); }
		}
		break;
	case iv::StatusKind::Burn:
		bBurning = bOn;
		if (bOn && IsLocallyControlled()) IVAudio::Play2D(GetWorld(), TEXT("cockpit_alarm_critical"), 0.9f);
		break;
	default: break;
	}
}

void AIVMechPawn::ResetMotion()
{
	Velocity = FVector::ZeroVector;
	PrevVelocity = FVector::ZeroVector;
	MoveIntent = FVector2D::ZeroVector;
	SwayOffset = FVector::ZeroVector; SwayVel = FVector::ZeroVector;
	SwayRot = FRotator::ZeroRotator; SwayRotVel = FVector::ZeroVector;
	ActionIndex = -1;
	bCine = false;
}

void AIVMechPawn::ResetForNewMatch()
{
	GlassCrack = 0.f;
	if (GlassMID) { GlassMID->SetScalarParameterValue(TEXT("Crack"), 0.f); for (int32 k = 0; k < 3; ++k) GlassMID->SetVectorParameterValue(*FString::Printf(TEXT("Imp%d"), k), FLinearColor(0, 0, 0, 0)); }
	if (GlassMID && FParse::Param(FCommandLine::Get(), TEXT("IVCrackDemo")))
	{
		GlassCrack = 0.6f;
		GlassMID->SetScalarParameterValue(TEXT("Crack"), 0.6f);
		GlassMID->SetVectorParameterValue(TEXT("Imp0"), FLinearColor(-0.35f, 0.25f, 0.9f, 0.f));
		GlassMID->SetVectorParameterValue(TEXT("Imp1"), FLinearColor(0.45f, 0.05f, 0.6f, 0.f));
		GlassMID->SetVectorParameterValue(TEXT("Imp2"), FLinearColor(0.1f, 0.42f, 0.4f, 0.f));
	}
	ClearDetached();
	Ult = FUltScript();
	SetBodyOffset(FVector::ZeroVector);
	if (RigMesh) RigMesh->SetVisibility(true, true);
	if (SwordMesh) SwordMesh->SetVisibility(true);
	bDying = false; bBurning = false; bStrikeLocked = false;
	BlindLeft = 0.f; DeathT = 0.f;
	for (float& F : FxAcc) F = 0.f;
	for (int32 i = 0; i < iv::kZoneCount; ++i) ZoneStates[i] = iv::ZoneState::Intact;
	if (bRigActive && RigMesh)
	{
		static const TCHAR* Bones[] = { TEXT("shoulder_l"), TEXT("shoulder_r"), TEXT("upperarm_l"), TEXT("upperarm_r"), TEXT("forearm_l"), TEXT("forearm_r"), TEXT("hand_l"), TEXT("hand_r"),
			TEXT("thigh_l"), TEXT("thigh_r"), TEXT("shin_l"), TEXT("shin_r"), TEXT("foot_l"), TEXT("foot_r"), TEXT("head"), TEXT("torso") };
		for (const TCHAR* B : Bones) RigMesh->UnHideBoneByName(FName(B));
	}
	SetHullDamage(0.f);
	SetSwordHeat(0.8f);
	ResetMotion();
}

void AIVMechPawn::StartDeathSequence()
{
	bDying = true;
	DeathT = 0.f;
}

void AIVMechPawn::UpdateDamageFX(float Dt)
{
	if (!bRigActive) return;
	if (BlindLeft > 0.f) BlindLeft = FMath::Max(0.f, BlindLeft - Dt);
	AIVFXManager* FX = AIVFXManager::Get(GetWorld());
	if (!FX) return;
	const float Fd = FMath::Min(Dt, 0.1f);
	for (int32 z = 0; z < iv::kZoneCount; ++z)
	{
		const iv::ZoneState St = ZoneStates[z];
		if (St < iv::ZoneState::Damaged) continue;
		FxAcc[z] += Fd;
		const float Period = St >= iv::ZoneState::Destroyed ? 0.07f : (St >= iv::ZoneState::Critical ? 0.12f : 0.4f);
		if (FxAcc[z] < Period) continue;
		FxAcc[z] = 0.f;
		const FVector Loc = GetZoneWorldLocation(static_cast<iv::Zone>(z)) + FMath::VRand() * 300.f;
		if (St >= iv::ZoneState::Critical)
		{
			FX->SpawnFlame(Loc, 220.f, St >= iv::ZoneState::Destroyed ? 3 : 2, St >= iv::ZoneState::Destroyed ? 1.4f : 1.f);
			FX->SpawnSmoke(Loc + FVector(0, 0, 400.f), 300.f, 1, 1.f);
			if (FMath::FRand() < 0.12f) FX->SpawnSparks(Loc, FVector::UpVector, 16, 3500.f);
		}
		else
		{
			FX->SpawnSmoke(Loc, 250.f, 1, 0.6f);
			if (FMath::FRand() < 0.18f) FX->SpawnSparks(Loc, GetActorForwardVector(), 8, 2500.f);
		}
	}
	if (bBurning)
	{
		FxAcc[iv::kZoneCount] += Fd;
		if (FxAcc[iv::kZoneCount] > 0.05f)
		{
			FxAcc[iv::kZoneCount] = 0.f;
			const FVector Loc = GetZoneWorldLocation(iv::Zone::Torso) + FMath::VRand() * FVector(600.f, 600.f, 900.f);
			FX->SpawnFlame(Loc, 250.f, 2, 1.2f);
			if (FMath::FRand() < 0.3f) FX->SpawnSmoke(Loc + FVector(0, 0, 600.f), 300.f, 1, 1.f);
		}
	}
	if (bDying)
	{
		DeathT += Fd;
		FxAcc[iv::kZoneCount + 1] += Fd;
		if (FxAcc[iv::kZoneCount + 1] > FMath::Lerp(0.55f, 0.2f, FMath::Clamp(DeathT / 3.f, 0.f, 1.f)))
		{
			FxAcc[iv::kZoneCount + 1] = 0.f;
			const iv::Zone Zn = static_cast<iv::Zone>(FMath::RandRange(0, iv::kZoneCount - 1));
			const FVector Loc = GetZoneWorldLocation(Zn);
			FX->SpawnExplosion(Loc, FMath::RandRange(0.9f, 1.8f));
			IVAudio::Play3D(GetWorld(), TEXT("env_distant_boom_01"), Loc, 1.f);
		}
		if (DeathT > 3.2f && DeathT - Fd <= 3.2f)
		{
			FX->SpawnExplosion(GetZoneWorldLocation(iv::Zone::Torso), 3.6f);
			IVAudio::Play3D(GetWorld(), TEXT("env_distant_boom_01"), GetZoneWorldLocation(iv::Zone::Torso), 1.f);
		}
		FxAcc[iv::kZoneCount] += Fd;
		if (FxAcc[iv::kZoneCount] > 0.05f)
		{
			FxAcc[iv::kZoneCount] = 0.f;
			FX->SpawnFlame(GetZoneWorldLocation(iv::Zone::Torso) + FMath::VRand() * FVector(700.f, 700.f, 1200.f), 300.f, 3, 1.5f);
		}
	}
}

void AIVMechPawn::OnLimbSevered(iv::Zone Z)
{
	const FVector Loc = GetZoneWorldLocation(Z);
	const bool bArm = iv::IsArmZone(Z);
	if (bRigActive && RigMesh)
	{
		const float Side = ZoneSide(Z);
		const FName Bone(*FString::Printf(TEXT("%s_%s"), bArm ? TEXT("forearm") : TEXT("shin"), Side < 0.f ? TEXT("l") : TEXT("r")));
		RigMesh->HideBoneByName(Bone, PBO_None);
	}
	static UStaticMesh* Cube = []{ UStaticMesh* M = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")); if (M) M->AddToRoot(); return M; }();
	FActorSpawnParameters Sp;
	Sp.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	if (AIVDebris* D = GetWorld()->SpawnActor<AIVDebris>(Loc, GetActorRotation(), Sp))
	{
		D->Init(Cube, nullptr, bArm ? FVector(1500, 1500, 5200) : FVector(1900, 2000, 3400), GetActorRightVector() * ZoneSide(Z) * 1200.f + FVector(0, 0, 900), FVector(40, 15, 25));
	}
	if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
	{
		FX->SpawnSparks(Loc, FVector::UpVector, 150, 7000.f);
		FX->SpawnDust(Loc, 2200.f, 24, 1.2f);
	}
	if (IsLocallyControlled()) AddCockpitImpulse(-ZoneSide(Z), 0.4f, 1.6f);
}

void AIVMechPawn::OnArmorPlateLost(iv::Zone Z, int32 Index, int32 Count)
{
	const FVector Loc = GetZoneWorldLocation(Z);
	for (FIVPlate& P : Plates)
	{
		if (P.bGone || P.Z != Z || !P.C) continue;
		P.bGone = true;
		const FTransform Xf = P.C->GetComponentTransform();
		P.C->SetVisibility(false);
		FRandomStream R2(Index * 211 + int32(Z) * 29 + 3);
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
		{
			const FVector Out = (Xf.GetLocation() - GetActorLocation() + FVector(0, 0, 900.f)).GetSafeNormal();
			FX->SpawnPiece(P.C->GetStaticMesh(), PlateMID, Xf, (Out + R2.VRand() * 0.35f) * R2.FRandRange(1600.f, 3200.f) + FVector(0, 0, 900.f), R2.VRand() * R2.FRandRange(1.f, 4.f), 0.9f);
			FX->SpawnSparks(Xf.GetLocation(), FVector::UpVector, 50, 5500.f);
		}
		IVAudio::Play3D(GetWorld(), TEXT("mech_armor_plate_tear"), Xf.GetLocation(), 1.f);
		return;
	}
	static UStaticMesh* Cube = []{ UStaticMesh* M = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")); if (M) M->AddToRoot(); return M; }();
	FActorSpawnParameters Sp;
	Sp.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	FRandomStream R(Index * 131 + int32(Z) * 17 + 5);
	if (AIVDebris* D = GetWorld()->SpawnActor<AIVDebris>(Loc, GetActorRotation(), Sp))
	{
		D->Init(Cube, nullptr, FVector(R.FRandRange(250.f, 500.f), R.FRandRange(1100.f, 1800.f), R.FRandRange(1100.f, 1800.f)),
			(R.VRand() + FVector(0, 0, 0.8f)) * R.FRandRange(900.f, 1900.f), R.VRand() * R.FRandRange(60.f, 180.f));
	}
	if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) FX->SpawnSparks(Loc, FVector::UpVector, 30, 4500.f);
}

void AIVMechPawn::StartCinematic(AIVMechPawn* Subject, float Seconds, int32 Kind)
{
	bCine = true;
	CineSubject = Subject;
	CineT = 0.f;
	CineDur = FMath::Max(Seconds, 0.5f);
	CineKind = Kind;
}

void AIVMechPawn::StopCinematic()
{
	bCine = false;
	CineSubject.Reset();
}

// ---- upper-body (and, for stances, whole-body) target pose from the core's AnimState ------------------------------
void AIVMechPawn::BuildCombatPose(FIVPoseAngles& Pose, float Dt)
{
	if (!RigData.IsValid()) return;
	const FIVRigData& D = *RigData;
	const iv::AnimState& S = CombatAnim;
	const FIVPoseAngles* Guard = D.FindPose(FName(TEXT("guard_neutral")));
	if (!Guard) return;

	auto P = [&](const FString& N) -> const FIVPoseAngles* { return D.FindPose(FName(*N)); };
	auto Ease = [](float u) { u = FMath::Clamp(u, 0.f, 1.f); return 1.f - FMath::Pow(1.f - u, 2.6f); };
	// the blade lives on the right arm: every sword strike uses it; the left arm only throws the quick strikes and grabs
	const FString Arm = (S.kind == iv::StrikeKind::Quick) ? TEXT("l") : TEXT("r");
	const FString Side = (S.kind == iv::StrikeKind::Lunge) ? FString(TEXT("right")) : ((S.kind == iv::StrikeKind::AirChop) ? FString(TEXT("up")) : FString(SideName(S.side)));

	FIVPoseAngles Target = *Guard;
	bool bLegs = false;

	if (bPoweredDown)
	{
		bLegs = true;
		if (const FIVPoseAngles* K = P(TEXT("kneel"))) Target = FIVPoseAngles::Lerp(*Guard, *K, 0.6f);
	}
	else if (S.posture == iv::Posture::KnockedDown)
	{
		bLegs = true;
		const FIVPoseAngles* A = P(TEXT("knockdown_fall"));
		const FIVPoseAngles* B = P(TEXT("knockdown_down"));
		if (A && B) Target = FIVPoseAngles::Lerp(*A, *B, Ease((S.postureProgress - 0.15f) / 0.5f));
	}
	else if (S.posture == iv::Posture::Staggered || S.posture == iv::Posture::ShutDown || S.posture == iv::Posture::Overloaded)
	{
		bLegs = true;
		if (const FIVPoseAngles* K = P(TEXT("kneel"))) Target = FIVPoseAngles::Lerp(*Guard, *K, (S.posture == iv::Posture::ShutDown || S.posture == iv::Posture::Overloaded) ? 0.9f : 0.45f * FMath::Sin(FMath::Clamp(S.postureProgress, 0.f, 1.f) * 3.14159f));
	}
	else if (S.posture == iv::Posture::Sliding)
	{
		bLegs = true;
		if (const FIVPoseAngles* K = P(TEXT("kneel"))) Target = FIVPoseAngles::Lerp(*Guard, *K, 0.8f);
	}
	else if (S.posture == iv::Posture::Dodging)
	{
		// a dodge is a side-step BACK: the body stays upright and square to the opponent (no lean, no torso twist); only the legs work.
		// the lead leg reaches out, the trailing leg follows, the whole mech slides away along the ground (impulse in the director).
		bLegs = true;
		const float Sg = (S.lateralShift < 0.f) ? 1.f : -1.f;           // which side we leave to
		const float U = FMath::Clamp(S.postureProgress, 0.f, 1.f);
		const float W = (U < 0.3f) ? Ease(U / 0.3f) : (U < 0.7f ? 1.f : 1.f - Ease((U - 0.7f) / 0.3f));
		const float Step = FMath::Sin(U * 3.14159f);
		Target.RootPosM.Z -= 0.06f * W;
		const TCHAR* Lead = Sg > 0.f ? TEXT("thigh_l") : TEXT("thigh_r");
		const TCHAR* LeadShin = Sg > 0.f ? TEXT("shin_l") : TEXT("shin_r");
		const TCHAR* LeadFoot = Sg > 0.f ? TEXT("foot_l") : TEXT("foot_r");
		const TCHAR* Trail = Sg > 0.f ? TEXT("thigh_r") : TEXT("thigh_l");
		const TCHAR* TrailShin = Sg > 0.f ? TEXT("shin_r") : TEXT("shin_l");
		if (FVector* T1 = Target.Joint.Find(FName(Lead))) { T1->X -= 26.f * Step; T1->Y += Sg * -24.f * Step; }
		if (FVector* T2 = Target.Joint.Find(FName(LeadShin))) T2->X += 34.f * Step;
		if (FVector* T3 = Target.Joint.Find(FName(LeadFoot))) T3->X -= 10.f * Step;
		if (FVector* T4 = Target.Joint.Find(FName(Trail))) { T4->X -= 10.f * W; T4->Y += Sg * 8.f * W; }
		if (FVector* T5 = Target.Joint.Find(FName(TrailShin))) T5->X += 14.f * W;
		// the whole body turns on the spot to profile (like a fencer avoiding a thrust): a yaw of the pelvis carries the legs, torso and arms; nothing leans
		if (FVector* T6 = Target.Joint.Find(FName(TEXT("pelvis")))) T6->Z += Sg * 72.f * W;   // joint angles are (pitch X, roll Y, yaw Z): Z is the turn about the vertical axis
	}
	else if (S.posture == iv::Posture::Clinched)
	{
		if (const FIVPoseAngles* G = P(TEXT("grab_clamp"))) Target = *G;
	}
	else if (S.weaponCharging || S.legsLocked)
	{
		bLegs = true;
		const FIVPoseAngles* H = P(TEXT("weapon_charge_hold"));
		const FIVPoseAngles* K = P(TEXT("weapon_charge_peak"));
		if (H && K) Target = FIVPoseAngles::Lerp(*H, *K, Ease(S.weaponChargeProgress));
	}
	else if (S.ultWindTicks > 0)
	{
		// the ultimate's windup: the off hand draws back and drives a punch under the chest (the last quarter is the strike)
		const float Uw = 1.f - float(S.ultWindTicks) / float(FMath::Max(1, S.ultWindLen));
		const FIVPoseAngles* W = P(TEXT("quick_palm_l_windup"));
		const FIVPoseAngles* K = P(TEXT("quick_palm_l_strike"));
		if (W && K) Target = Uw < 0.75f ? FIVPoseAngles::Lerp(*Guard, *W, Ease(Uw / 0.75f)) : FIVPoseAngles::Lerp(*W, *K, Ease((Uw - 0.75f) / 0.25f));
		bLegs = true;
		if (FVector* Th = Target.Joint.Find(FName(TEXT("pelvis")))) Th->X += 6.f * FMath::Sin(Uw * 3.14159f);
	}
	else if (S.phase != iv::Phase::Idle)
	{
		const float U = S.progress;
		if (S.kind == iv::StrikeKind::Heavy)
		{
			const FIVPoseAngles* W = P(FString::Printf(TEXT("swing_%s_%s_windup"), *Side, *Arm));
			const FIVPoseAngles* C = P(FString::Printf(TEXT("swing_%s_%s_commit"), *Side, *Arm));
			const FIVPoseAngles* E = P(FString::Printf(TEXT("swing_%s_%s_strike_end"), *Side, *Arm));
			const FIVPoseAngles* R = P(FString::Printf(TEXT("swing_%s_%s_recovery"), *Side, *Arm));
			if (W && C && E && R)
			{
				switch (S.phase)
				{
				case iv::Phase::Windup: Target = S.committed ? FIVPoseAngles::Lerp(*W, *C, 0.7f) : FIVPoseAngles::Lerp(*Guard, *W, Ease(U)); break;
				case iv::Phase::Strike: Target = FIVPoseAngles::Lerp(*C, *E, Ease(U)); break;
				case iv::Phase::Contact: Target = *E; break;
				case iv::Phase::Recovery: Target = (U < 0.6f) ? FIVPoseAngles::Lerp(*E, *R, Ease(U / 0.6f)) : FIVPoseAngles::Lerp(*R, *Guard, Ease((U - 0.6f) / 0.4f)); break;
				default: break;
				}
			}
		}
		else if (S.kind == iv::StrikeKind::Quick)
		{
			const TCHAR* Type = S.side == iv::SwingSide::Up ? TEXT("piston") : (S.side == iv::SwingSide::Down ? TEXT("palm") : TEXT("hook"));
			const FIVPoseAngles* W = P(FString::Printf(TEXT("quick_%s_%s_windup"), Type, *Arm));
			const FIVPoseAngles* K = P(FString::Printf(TEXT("quick_%s_%s_strike"), Type, *Arm));
			if (W && K)
			{
				switch (S.phase)
				{
				case iv::Phase::Windup: Target = FIVPoseAngles::Lerp(*Guard, *W, Ease(U)); break;
				case iv::Phase::Strike: Target = FIVPoseAngles::Lerp(*W, *K, Ease(U)); break;
				case iv::Phase::Contact: Target = *K; break;
				case iv::Phase::Recovery: Target = FIVPoseAngles::Lerp(*K, *Guard, Ease(U)); break;
				default: break;
				}
			}
		}
		else
		{
			const FIVPoseAngles* A = P(TEXT("grab_reach"));
			const FIVPoseAngles* B = P(TEXT("grab_clamp"));
			if (A && B)
			{
				switch (S.phase)
				{
				case iv::Phase::Windup: Target = FIVPoseAngles::Lerp(*Guard, *A, Ease(U)); break;
				case iv::Phase::Strike: Target = FIVPoseAngles::Lerp(*A, *B, Ease(U)); break;
				case iv::Phase::Contact: Target = *B; break;
				case iv::Phase::Recovery: Target = FIVPoseAngles::Lerp(*B, *Guard, Ease(U)); break;
				default: break;
				}
			}
		}
	}
	else if (S.hardStance)
	{
		bLegs = true;
		if (const FIVPoseAngles* H = P(TEXT("hard_stance"))) Target = *H;
	}
	else if (S.guardRaised)
	{
		if (const FIVPoseAngles* B = P(FString::Printf(TEXT("block_%s"), SideName(S.guardSide)))) Target = *B;
	}

	// one-armed swings: while the blade arm (right) strikes, the off hand stays down in its guard position (it only rises for a parry rocket)
	if (S.phase != iv::Phase::Idle && (S.kind == iv::StrikeKind::Heavy || S.kind == iv::StrikeKind::Lunge || S.kind == iv::StrikeKind::AirChop))
	{
		const FIVPoseAngles* Rest = P(TEXT("guard_neutral"));
		for (const TCHAR* N : { TEXT("shoulder_l"), TEXT("upperarm_l"), TEXT("forearm_l"), TEXT("hand_l") })
		{
			const FName B(N);
			FVector* T = Target.Joint.Find(B);
			const FVector* G = Rest ? Rest->Joint.Find(B) : nullptr;
			if (T && G) *T = *G;
		}
	}
	if (S.posture == iv::Posture::Airborne || S.posture == iv::Posture::Sliding) bLegs = true;
	// smooth towards the target (fast, but never a pop) and merge into the locomotion pose
	if (!bCombatPoseInit) { CombatPose = *Guard; bCombatPoseInit = true; }
	const float K = 1.f - FMath::Exp(-16.f * Dt);
	{
		// spring-damper per joint: heavy limbs lag and overshoot a little (mass), light ones keep up. The strike is stiff so the blade lands on time,
		// the recovery is soft so the arm has to be hauled back.
		const float Phase = (S.phase == iv::Phase::Strike) ? 1.7f : ((S.phase == iv::Phase::Recovery) ? 0.62f : ((S.phase == iv::Phase::Windup) ? 0.85f : 1.f));
		const float Zeta = (S.phase == iv::Phase::Strike) ? 0.78f : 0.6f;
		const float Dtc = FMath::Min(Dt, 1.f / 30.f);
		for (int32 Sub = 0; Sub < 2; ++Sub)
		{
			const float H = Dtc * 0.5f;
			for (const TPair<FName, FVector>& Kv : Target.Joint)
			{
				const FString N = Kv.Key.ToString();
				float W0 = 11.f;
				if (N.Contains(TEXT("torso"))) W0 = 6.5f;
				else if (N.Contains(TEXT("head"))) W0 = 7.5f;
				else if (N.Contains(TEXT("shoulder"))) W0 = 8.5f;
				else if (N.Contains(TEXT("upperarm"))) W0 = 10.f;
				else if (N.Contains(TEXT("forearm"))) W0 = 12.5f;
				else if (N.Contains(TEXT("hand"))) W0 = 15.f;
				else if (N.Contains(TEXT("pelvis")) || N.Contains(TEXT("thigh")) || N.Contains(TEXT("shin")) || N.Contains(TEXT("foot"))) W0 = 9.f;
				const float Wn = W0 * Phase;
				FVector& Cur = CombatPose.Joint.FindOrAdd(Kv.Key, Kv.Value);
				FVector& Vel = CombatVel.FindOrAdd(Kv.Key);
				const FVector Acc = (Kv.Value - Cur) * (Wn * Wn) - Vel * (2.f * Zeta * Wn);
				Vel += Acc * H;
				Cur += Vel * H;
			}
		}
		CombatPose.RootPosM = FMath::Lerp(CombatPose.RootPosM, Target.RootPosM, K);
		CombatPose.RootRotDeg = FMath::Lerp(CombatPose.RootRotDeg, Target.RootRotDeg, 1.f - FMath::Exp(-7.f * Dt));
	}
	// body english: a heavy swing drags the torso round and drops the pelvis; the dip is released as a footfall-like thump at contact
	{
		const float WantYaw = (S.phase == iv::Phase::Windup) ? -9.f * ((S.side == iv::SwingSide::Left) ? 1.f : -1.f) : ((S.phase == iv::Phase::Strike) ? 14.f * ((S.side == iv::SwingSide::Left) ? 1.f : -1.f) : 0.f);
		const float WantDip = (S.phase == iv::Phase::Windup) ? 0.4f : ((S.phase == iv::Phase::Strike || S.phase == iv::Phase::Contact) ? 1.f : 0.f);
		SwingWeightYaw = FMath::FInterpTo(SwingWeightYaw, (S.kind == iv::StrikeKind::Heavy || S.kind == iv::StrikeKind::Lunge) ? WantYaw : 0.f, Dt, 5.f);
		PelvisDip = FMath::FInterpTo(PelvisDip, (S.kind == iv::StrikeKind::Heavy || S.kind == iv::StrikeKind::Lunge) ? WantDip : 0.f, Dt, 6.f);
		if (FVector* T = CombatPose.Joint.Find(FName(TEXT("torso")))) T->Z += SwingWeightYaw;   // a twist about the vertical axis (Y would be a sideways lean)
		Pose.RootPosM.Z -= 0.35f * PelvisDip;
	}
	if (S.posture == iv::Posture::Airborne)
	{
		// the legs fold up under the jump-jets
		const float Tuck = FMath::Pow(FMath::Sin(FMath::Clamp(S.airProgress, 0.f, 1.f) * 3.14159f), 0.6f);
		for (const TCHAR* N : { TEXT("thigh_l"), TEXT("thigh_r") }) if (FVector* V = CombatPose.Joint.Find(FName(N))) V->X += -42.f * Tuck;
		for (const TCHAR* N : { TEXT("shin_l"), TEXT("shin_r") }) if (FVector* V = CombatPose.Joint.Find(FName(N))) V->X += 66.f * Tuck;
		for (const TCHAR* N : { TEXT("foot_l"), TEXT("foot_r") }) if (FVector* V = CombatPose.Joint.Find(FName(N))) V->X += -24.f * Tuck;
	}

	static const TCHAR* Upper[] = { TEXT("torso"), TEXT("head"), TEXT("reactor"), TEXT("shoulder_l"), TEXT("upperarm_l"), TEXT("forearm_l"), TEXT("hand_l"),
		TEXT("shoulder_r"), TEXT("upperarm_r"), TEXT("forearm_r"), TEXT("hand_r") };
	static const TCHAR* Lower[] = { TEXT("pelvis"), TEXT("thigh_l"), TEXT("shin_l"), TEXT("foot_l"), TEXT("thigh_r"), TEXT("shin_r"), TEXT("foot_r") };
	for (const TCHAR* N : Upper)
	{
		const FName B(N);
		if (const FVector* V = CombatPose.Joint.Find(B)) Pose.Joint.Add(B, *V);
	}
	// legs follow the combat pose only when it asks for it (dodge, stance, knockdown...); weight is the smoothed bLegs
	static float LegW = 0.f;
	LegW = FMath::FInterpTo(LegW, bLegs ? 1.f : 0.f, Dt, 9.f);
	if (LegW > 0.01f)
	{
		for (const TCHAR* N : Lower)
		{
			const FName B(N);
			const FVector* V = CombatPose.Joint.Find(B);
			const FVector* Cur = Pose.Joint.Find(B);
			if (V && Cur) Pose.Joint.Add(B, FMath::Lerp(*Cur, *V, LegW));
		}
		Pose.RootPosM = FMath::Lerp(Pose.RootPosM, CombatPose.RootPosM, LegW);
		Pose.RootRotDeg = FMath::Lerp(Pose.RootRotDeg, CombatPose.RootRotDeg, LegW);
	}

	// off-hand rocket salvo after a parry: the left arm punches out and holds, the launcher fires, then it drops back
	if (RocketArmT > 0.f)
	{
		RocketArmT += Dt;
		const float U = RocketArmT / 0.9f;
		const float Wt = U < 0.25f ? Ease(U / 0.25f) : (U < 0.7f ? 1.f : FMath::Max(0.f, 1.f - Ease((U - 0.7f) / 0.3f)));
		if (const FIVPoseAngles* Rk = P(TEXT("quick_piston_l_strike")))
			for (const TCHAR* N : { TEXT("shoulder_l"), TEXT("upperarm_l"), TEXT("forearm_l"), TEXT("hand_l") })
			{
				const FName B(N);
				const FVector* Tg = Rk->Joint.Find(B);
				FVector* Cur = Pose.Joint.Find(B);
				if (Tg && Cur) *Cur = FMath::Lerp(*Cur, *Tg, Wt);
			}
		if (U >= 1.f) RocketArmT = 0.f;
	}
	// boarding defence: the hand opposite to the stranger's shoulder rises, then comes across and slaps it. Slow and readable.
	{
		float Tgt = SlapU;
		if (SlapPrev > 0.9f && SlapU < 0.05f) SlapHoldT = 0.5f;          // the impact beat: the hand stays on the shoulder for a moment
		SlapPrev = SlapU;
		if (SlapHoldT > 0.f) { SlapHoldT -= Dt; Tgt = 1.f; }
		SlapSm = FMath::FInterpTo(SlapSm, Tgt, Dt, Tgt > SlapSm ? 12.f : 5.f);
		if (SlapSm > 0.01f)
		{
			const bool bR = bSlapRight;                              // the stranger sits on our right shoulder: the LEFT hand slaps it
			const float Ww = Ease(FMath::Clamp(SlapSm / 0.72f, 0.f, 1.f));
			const float Sw = Ease(FMath::Clamp((SlapSm - 0.72f) / 0.28f, 0.f, 1.f));
			const float Wt = FMath::Clamp(SlapSm * 4.f, 0.f, 1.f);
			auto Mir = [&](const FVector& V) { return bR ? V : FVector(V.X, -V.Y, -V.Z); };
			const TCHAR* Ua = bR ? TEXT("upperarm_l") : TEXT("upperarm_r");
			const TCHAR* Fa = bR ? TEXT("forearm_l") : TEXT("forearm_r");
			const TCHAR* Ha = bR ? TEXT("hand_l") : TEXT("hand_r");
			auto Drive = [&](const TCHAR* Name, const FVector& Wind, const FVector& Hit)
			{
				if (FVector* Cur = Pose.Joint.Find(FName(Name)))
				{
					const FVector T = FMath::Lerp(FMath::Lerp(*Cur, Mir(Wind), Ww), Mir(Hit), Sw);
					*Cur = FMath::Lerp(*Cur, T, Wt);
				}
			};
			Drive(Ua, FVector(-165.f, -5.f, 0.f), FVector(-84.f, -64.f, 18.f));
			Drive(Fa, FVector(-12.f, 0.f, 0.f), FVector(-62.f, 0.f, 0.f));
			Drive(Ha, FVector(-10.f, 0.f, 0.f), FVector(-20.f, 0.f, 0.f));
			if (FVector* Tt = Pose.Joint.Find(FName(TEXT("torso")))) Tt->Y += (bR ? -1.f : 1.f) * 10.f * Sw * Wt;   // the body turns into the slap
		}
	}
	// hit kick: torso recoil on top of everything, decays quickly
	HitKick *= FMath::Exp(-7.f * Dt);
	if (FVector* T = Pose.Joint.Find(FName(TEXT("torso")))) *T += HitKick;
	if (FVector* H = Pose.Joint.Find(FName(TEXT("head")))) *H += HitKick * 0.5f;
}


void AIVMechPawn::UpdateV5Fx(float Dt)
{
	Rage = FMath::FInterpTo(Rage, RageTarget, Dt, 2.5f);
	if (HullMID) HullMID->SetScalarParameterValue(TEXT("Rage"), Rage);
	AIVFXManager* FX = AIVFXManager::Get(GetWorld());
	if (!FX) return;
	// jump-jets: two nozzles on the back, exhaust straight down
	if (CombatAnim.posture == iv::Posture::Airborne)
	{
		JetAcc += Dt;
		while (JetAcc > 0.025f)
		{
			JetAcc -= 0.025f;
			const FVector Base = GetActorLocation() - FVector(0, 0, 2400.f) - GetActorForwardVector() * 700.f;
			for (int32 s = -1; s <= 1; s += 2) FX->SpawnJet(Base + GetActorRightVector() * (450.f * s), FVector(0.f, 0.f, -1.f), 2, 5200.f, 700.f);
		}
		if (JetAcc < 0.f) JetAcc = 0.f;
	}
	// the charge of a lunge: the blade burns hot and the joints vent
	if (CombatAnim.lungeCharge01 > 0.f)
	{
		SetSwordHeat(0.8f + 1.6f * CombatAnim.lungeCharge01);
		LungeFxAcc += Dt;
		if (LungeFxAcc > 0.12f)
		{
			LungeFxAcc = 0.f;
			FX->SpawnSparks(GetZoneWorldLocation(iv::Zone::ArmR), FVector::UpVector, 3 + int32(8 * CombatAnim.lungeCharge01), 2600.f);
		}
	}
	else if (CombatAnim.kind == iv::StrikeKind::Lunge && CombatAnim.phase == iv::Phase::Strike)
	{
		FVector B, T; GetBladeSegment(B, T);
		FX->SpawnSparks(T, -GetActorForwardVector(), 6, 5000.f);
	}
	// an overloaded mech smokes and sparks while it waits for the power
	if (CombatAnim.posture == iv::Posture::Overloaded)
	{
		LungeFxAcc += Dt;
		if (LungeFxAcc > 0.2f)
		{
			LungeFxAcc = 0.f;
			FX->SpawnSmoke(GetZoneWorldLocation(iv::Zone::Torso), 600.f, 2, 0.8f);
			FX->SpawnSparks(GetZoneWorldLocation(iv::Zone::Reactor), FVector::UpVector, 5, 3500.f);
		}
	}
}

void AIVMechPawn::PlayBerserkSwing(iv::SwingSide Side)
{
	const FString Sd = SideName(Side);
	PlaySequence({ FName(*FString::Printf(TEXT("swing_%s_r_windup"), *Sd)), FName(*FString::Printf(TEXT("swing_%s_r_commit"), *Sd)),
		FName(*FString::Printf(TEXT("swing_%s_r_strike_end"), *Sd)), FName(TEXT("grab_clamp")) }, { 0.28f, 0.1f, 0.18f, 0.5f });
}

void AIVMechPawn::StartCounterPunch(AIVMechPawn* Victim)
{
	PlaySequence({ FName(TEXT("quick_piston_r_windup")), FName(TEXT("quick_piston_r_strike")), FName(TEXT("quick_piston_r_strike")), FName(TEXT("guard_neutral")) }, { 0.45f, 0.14f, 0.5f, 0.9f });
	AddVelocityImpulse(GetActorForwardVector() * 1500.f);   // a short run-up
	if (Victim)
	{
		Victim->PlaySequence({ FName(TEXT("knockdown_fall")), FName(TEXT("knockdown_down")), FName(TEXT("knockdown_down")), FName(TEXT("kneel")) }, { 0.45f, 1.2f, 1.6f, 2.f });
		TWeakObjectPtr<AIVMechPawn> V(Victim);
		FTimerHandle H;
		GetWorld()->GetTimerManager().SetTimer(H, FTimerDelegate::CreateLambda([V]()
		{
			if (!V.IsValid()) return;
			if (AIVFXManager* FX = AIVFXManager::Get(V->GetWorld())) FX->SpawnExplosion(V->GetZoneWorldLocation(iv::Zone::Torso), 1.1f);
			V->AddCockpitImpulse(0.f, 1.f, 2.f);
			V->AddVelocityImpulse(-V->GetActorForwardVector() * 1800.f);
		}), 0.55f, false);
	}
}

void AIVMechPawn::StartLockPose(bool bOn)
{
	if (bOn) PlaySequence({ FName(TEXT("block_up")), FName(TEXT("block_up")) }, { 0.2f, 6.f });
	else PlaySequence({ FName(TEXT("guard_neutral")) }, { 0.4f });
}

void AIVMechPawn::UpdateBladeTrail(float Dt)
{
	if (!BladeTrail || !SwordMesh || !bRigActive || !SwordMesh->IsVisible()) return;
	FVector B, T;
	GetBladeSegment(B, T);
	const float Now = GetWorld()->GetTimeSeconds();
	const FVector Mid = B + (T - B) * 0.55f;   // only the outer part of the blade paints the ribbon
	const float TipSpeed = PrevTip.IsZero() ? 0.f : (T - PrevTip).Size() / FMath::Max(Dt, 1e-3f);
	PrevTip = T;
	// record only while the blade really moves (a swing): the trail then fades out on its own
	const float Life = 0.16f;
	if (TipSpeed > 1800.f) TrailSamples.Add({ Mid, T, Now });
	while (TrailSamples.Num() > 0 && Now - TrailSamples[0].Time > Life) TrailSamples.RemoveAt(0);
	if (TrailSamples.Num() < 2)
	{
		BladeTrail->ClearAllMeshSections();
		return;
	}
	TArray<FVector> V, N;
	TArray<FVector2D> UV;
	TArray<FLinearColor> Col;
	TArray<int32> Tri;
	TArray<FProcMeshTangent> Tan;
	const int32 Num = TrailSamples.Num();
	for (int32 i = 0; i < Num; ++i)
	{
		const FTrailSample& S = TrailSamples[i];
		const float Age = (Now - S.Time) / Life;
		const float Fade = FMath::Clamp(1.f - Age, 0.f, 1.f);
		const float U = float(i) / float(Num - 1);
		V.Add(S.Tip); UV.Add(FVector2D(U, 0.f)); Col.Add(FLinearColor(1, 1, 1, Fade * Fade)); N.Add(FVector::UpVector);
		V.Add(S.Mid); UV.Add(FVector2D(U, 1.f)); Col.Add(FLinearColor(1, 1, 1, Fade * Fade)); N.Add(FVector::UpVector);
	}
	for (int32 i = 0; i < Num - 1; ++i)
	{
		const int32 a = i * 2, b = i * 2 + 1, c2 = i * 2 + 2, d = i * 2 + 3;
		Tri.Add(a); Tri.Add(b); Tri.Add(c2);
		Tri.Add(c2); Tri.Add(b); Tri.Add(d);
		Tri.Add(a); Tri.Add(c2); Tri.Add(b);
		Tri.Add(c2); Tri.Add(d); Tri.Add(b);
	}
	BladeTrail->CreateMeshSection_LinearColor(0, V, Tri, N, UV, Col, Tan, false);
	if (TrailMID) BladeTrail->SetMaterial(0, TrailMID);
}


// =====================================================================================================================
//  Ultimate choreography
// =====================================================================================================================
void AIVMechPawn::SetBodyOffset(const FVector& LocalOffset)
{
	BodyOffset = LocalOffset;
	if (RigMesh) RigMesh->SetRelativeLocation(FVector(LocalOffset.X, LocalOffset.Y, -4100.f + LocalOffset.Z));
}

void AIVMechPawn::PlaySequence(const TArray<FName>& Poses, const TArray<float>& Durations)
{
	if (!bRigActive || !RigData.IsValid()) return;
	ActionSteps.Reset();
	for (int32 i = 0; i < Poses.Num(); ++i)
		if (RigData->FindPose(Poses[i])) ActionSteps.Add({ Poses[i], Durations.IsValidIndex(i) ? Durations[i] : 0.5f });
	if (ActionSteps.Num() == 0) return;
	ActionIndex = 0;
	ActionTimer = 0.f;
	ActionFrom = FIVPoseAngles();
}

void AIVMechPawn::StartUltimateScript(AIVMechPawn* Victim, int32 Mode)
{
	if (!bRigActive || !Victim) return;
	Ult = FUltScript();
	Ult.bActive = true;
	Ult.Victim = Victim;
	Ult.Mode = Mode;
	PlaySequence({ FName("quick_piston_l_windup"), FName("quick_piston_l_strike"), FName("guard_neutral"), FName("swing_up_r_windup"), FName("swing_down_r_commit"),
		FName("swing_down_r_strike_end"), FName("swing_down_r_recovery"), FName("guard_neutral") },
		{ 0.22f, 0.14f, 0.20f, 0.80f, 0.12f, 0.22f, 0.9f, 0.6f });
	Victim->PlaySequence({ FName("guard_neutral"), FName("kneel"), FName("kneel") }, { 0.25f, 0.45f, 3.f });
	if (SwordMID) SwordMID->SetScalarParameterValue(TEXT("Heat"), 1.6f);
	IVAudio::Play3D(GetWorld(), TEXT("mech_servo_arm_windup"), GetActorLocation() + FVector(0, 0, 4000.f), 1.f, 0.8f);
}

void AIVMechPawn::UpdateUltimateScript(float Dt)
{
	if (!Ult.bActive) return;
	Ult.T += Dt;
	const float t = Ult.T;
	AIVMechPawn* V = Ult.Victim.Get();
	AIVFXManager* FX = AIVFXManager::Get(GetWorld());
	// attacker: forward lunge + jump
	float Z = 0.f, F = 0.f;
	if (t >= 0.55f)
	{
		const float U = FMath::Clamp((t - 0.55f) / 1.07f, 0.f, 1.f);
		F = 2300.f * (U * U * (3.f - 2.f * U));
		Z = (t < 1.62f) ? 3500.f * FMath::Sin(U * PI) : 0.f;
	}
	SetBodyOffset(FVector(F, 0.f, Z));
	// the opponent reels back from the punch
	if (V && t >= 0.2f)
	{
		const float U = FMath::Clamp((t - 0.2f) / 0.5f, 0.f, 1.f);
		V->SetBodyOffset(FVector(-650.f * (U * U * (3.f - 2.f * U)), 0.f, 0.f));
		if (!Ult.bPushed)
		{
			Ult.bPushed = true;
			if (FX)
			{
				const FVector P = V->GetZoneWorldLocation(iv::Zone::Torso);
				FX->SpawnSparks(P, GetActorForwardVector() * -1.f, 140, 7000.f);
				FX->SpawnDust(P, 1800.f, 18, 1.f);
				FX->SpawnFlash(P, FLinearColor(1.f, 0.7f, 0.4f), 1.6e5f, 0.3f, 12000.f);
			}
			IVAudio::Play3D(GetWorld(), TEXT("hit_metal_contact_heavy"), V->GetActorLocation() + FVector(0, 0, 3500.f), 1.f);
			IVAudio::Play3D(GetWorld(), TEXT("hit_lowfreq_thump_heavy"), V->GetActorLocation() + FVector(0, 0, 3500.f), 1.f);
		}
	}
	// the chop lands at the top of the fall
	if (!Ult.bImpact && t >= 1.58f)
	{
		Ult.bImpact = true;
		if (V && FX)
		{
			const FVector Head = V->GetZoneWorldLocation(iv::Zone::Head);
			FX->SpawnFlash(Head, FLinearColor(1.f, 0.85f, 0.6f), 4.0e5f, 0.5f, 22000.f);
			FX->SpawnSparks(Head, FVector::UpVector, 300, 10000.f);
			FX->SpawnDust(GetActorLocation() + GetActorForwardVector() * 2000.f, 4000.f, 40, 2.f);
			IVAudio::Play3D(GetWorld(), TEXT("parry_clang"), Head, 1.f);
			IVAudio::Play3D(GetWorld(), TEXT("mech_limb_sever"), Head, 1.f);
			IVAudio::Play3D(GetWorld(), TEXT("env_distant_boom_01"), GetActorLocation(), 1.f);
			if (V->IsLocallyControlled()) V->AddCockpitImpulse(0.f, 1.f, 2.f);
			if (IsLocallyControlled()) AddCockpitImpulse(0.f, -1.f, 1.5f);
			if (Ult.Mode == 1) V->SplitInHalves();
			else if (Ult.Mode == 2) V->SeverOffArm();
		}
		UGameplayStatics::SetGlobalTimeDilation(this, 0.28f);
	}
	if (t > 2.1f) UGameplayStatics::SetGlobalTimeDilation(this, 1.f);
	if (t >= 3.3f)
	{
		// make the lunge permanent: move the actors, not just the mesh
		Ult.bActive = false;
		UGameplayStatics::SetGlobalTimeDilation(this, 1.f);
		AddActorWorldOffset(GetActorForwardVector() * F, false);
		SetBodyOffset(FVector::ZeroVector);
		if (V)
		{
			V->AddActorWorldOffset(-V->GetActorForwardVector() * 650.f, false);
			V->SetBodyOffset(FVector::ZeroVector);
		}
		if (SwordMID) SwordMID->SetScalarParameterValue(TEXT("Heat"), 0.8f);
	}
}

USkeletalMeshComponent* AIVMechPawn::MakeCloneRig(UMaterialInterface* Mat, TObjectPtr<UMaterialInstanceDynamic>& OutMID, bool bClip)
{
	if (!RigMesh || !RigMesh->GetSkeletalMeshAsset()) return nullptr;
	USkeletalMeshComponent* C = NewObject<USkeletalMeshComponent>(this);
	C->SetSkeletalMesh(RigMesh->GetSkeletalMeshAsset());
	C->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	C->SetAnimInstanceClass(UIVRigAnimInstance::StaticClass());
	C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	C->SetCastShadow(false);
	C->SetBoundsScale(3.f);
	C->bUpdateJointsFromAnimation = true;
	C->RegisterComponent();
	C->SetWorldTransform(RigMesh->GetComponentTransform());
	C->InitAnim(true);
	if (UIVRigAnimInstance* CI = Cast<UIVRigAnimInstance>(C->GetAnimInstance()))
		if (RigAnim) CI->PoseLocal = RigAnim->PoseLocal;
	UMaterialInterface* Base = bClip ? LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_MechHullClip.M_MechHullClip")) : Mat;
	if (Base)
	{
		OutMID = UMaterialInstanceDynamic::Create(Base, this);
		OutMID->SetVectorParameterValue(TEXT("Tint"), HullTint);
		OutMID->SetVectorParameterValue(TEXT("Accent"), HullAccent);
		for (int32 i = 0; i < C->GetNumMaterials(); ++i) C->SetMaterial(i, OutMID);
	}
	return C;
}

void AIVMechPawn::SplitInHalves()
{
	if (!RigMesh) return;
	const FVector O = RigMesh->GetBoneLocation(FName(TEXT("torso")), EBoneSpaces::WorldSpace);
	const FVector N = GetActorRightVector();
	const FVector FeetPivot = FVector(O.X, O.Y, GetActorLocation().Z - 4100.f);
	for (int32 s = 0; s < 2; ++s)
	{
		FDetached D;
		D.MID = nullptr;
		D.Comp = MakeCloneRig(nullptr, D.MID, true);
		if (!D.Comp) continue;
		const float Sd = s == 0 ? 1.f : -1.f;
		D.Kind = 0;
		D.T0 = D.Comp->GetComponentTransform();
		D.Pivot = FeetPivot;
		D.ClipO = O;
		D.ClipN = N;
		D.Spin = FVector(0.f, 0.f, 0.f);
		D.Roll = Sd;                       // side
		if (D.MID)
		{
			D.MID->SetVectorParameterValue(TEXT("ClipOrigin"), FLinearColor(O.X, O.Y, O.Z));
			D.MID->SetVectorParameterValue(TEXT("ClipNormal"), FLinearColor(N.X, N.Y, N.Z));
			D.MID->SetScalarParameterValue(TEXT("ClipSide"), Sd);
		}
		Detached.Add(D);
	}
	// the original body disappears; its sword drops
	RigMesh->SetVisibility(false, true);
	if (SwordMesh)
	{
		SwordMesh->SetVisibility(false);
		if (UStaticMesh* SM = SwordMesh->GetStaticMesh())
		{
			UStaticMeshComponent* Drop = NewObject<UStaticMeshComponent>(this);
			Drop->SetStaticMesh(SM);
			Drop->SetMaterial(0, SwordMID);
			Drop->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Drop->RegisterComponent();
			Drop->SetWorldTransform(SwordMesh->GetComponentTransform());
			// reuse the slot of a detached part: a rigid body with its own ballistic path
			FDetached Sw;
			Sw.Comp = nullptr;
			Sw.Kind = 2;
			Sw.T0 = SwordMesh->GetComponentTransform();
			Sw.Vel = GetActorRightVector() * 600.f + FVector(0, 0, 500.f);
			Sw.Spin = FVector(30.f, 80.f, 20.f);
			Detached.Add(Sw);
			SwordDrop = Drop;
		}
	}
	if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
	{
		for (int32 i = 0; i < 9; ++i)
		{
			const FVector P = O + FVector(0, 0, (i - 3) * 800.f);
			FX->SpawnFlame(P, 400.f, 3, 1.6f);
			FX->SpawnSparks(P, N, 18, 5000.f);
		}
		FX->SpawnExplosion(O, 2.6f);
	}
}

void AIVMechPawn::SeverOffArm()
{
	if (!RigMesh) return;
	static const TCHAR* Others[] = { TEXT("root"), TEXT("pelvis"), TEXT("torso"), TEXT("head"), TEXT("reactor"), TEXT("shoulder_l"), TEXT("shoulder_r"), TEXT("upperarm_r"), TEXT("forearm_r"), TEXT("hand_r"),
		TEXT("thigh_l"), TEXT("thigh_r"), TEXT("shin_l"), TEXT("shin_r"), TEXT("foot_l"), TEXT("foot_r") };
	UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_MechHull.M_MechHull"));
	FDetached D;
	D.Comp = MakeCloneRig(Base, D.MID, false);
	if (!D.Comp) return;
	for (const TCHAR* B : Others) D.Comp->HideBoneByName(FName(B), PBO_None);
	static const TCHAR* Arm[] = { TEXT("upperarm_l"), TEXT("forearm_l"), TEXT("hand_l") };
	for (const TCHAR* B : Arm) RigMesh->HideBoneByName(FName(B), PBO_None);
	D.Kind = 1;
	D.bFollow = false;
	D.T0 = D.Comp->GetComponentTransform();
	const FVector ShoulderLoc = RigMesh->GetBoneLocation(FName(TEXT("upperarm_l")), EBoneSpaces::WorldSpace);
	D.Vel = (-GetActorRightVector() * 1300.f + GetActorForwardVector() * 900.f + FVector(0, 0, 1700.f));
	D.Spin = FVector(120.f, 40.f, 200.f);
	D.Pivot = ShoulderLoc;
	Detached.Add(D);
	if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
	{
		FX->SpawnExplosion(ShoulderLoc, 2.2f);
		FX->SpawnSparks(ShoulderLoc, -GetActorRightVector(), 220, 9000.f);
		FX->SpawnFlame(ShoulderLoc, 500.f, 8, 1.8f);
	}
	IVAudio::Play3D(GetWorld(), TEXT("mech_limb_sever"), ShoulderLoc, 1.f);
	ZoneStates[iv::Index(iv::Zone::ArmL)] = iv::ZoneState::Severed;
	RefreshHullDamage();
}

void AIVMechPawn::ClearDetached()
{
	for (FDetached& D : Detached) if (D.Comp) D.Comp->DestroyComponent();
	Detached.Reset();
	if (SwordDrop) { SwordDrop->DestroyComponent(); SwordDrop = nullptr; }
}

void AIVMechPawn::UpdateDetached(float Dt)
{
	if (Detached.Num() == 0) return;
	AIVEnvironment* Env = AIVEnvironment::Get(GetWorld());
	AIVDistrict* Dist = Env ? Env->GetDistrict() : nullptr;
	AIVFXManager* FX = AIVFXManager::Get(GetWorld());
	for (FDetached& D : Detached)
	{
		D.T += Dt;
		if (D.Kind == 0 && D.Comp)
		{
			// a half topples outward about the line of the feet, still playing the collapse of the pose
			const float Sd = D.Roll;
			const float U = FMath::Clamp(D.T / 1.8f, 0.f, 1.f);
			const float Ang = Sd * (4.f + 74.f * U * U);
			const FQuat Q(GetActorForwardVector(), FMath::DegreesToRadians(Ang));
			FTransform Cur = D.T0;
			const FVector Rel = D.T0.GetLocation() - D.Pivot;
			Cur.SetLocation(D.Pivot + Q.RotateVector(Rel) + D.ClipN * Sd * (120.f + 700.f * U));
			Cur.SetRotation(Q * D.T0.GetRotation());
			D.Comp->SetWorldTransform(Cur);
			if (UIVRigAnimInstance* CI = Cast<UIVRigAnimInstance>(D.Comp->GetAnimInstance())) if (RigAnim) CI->PoseLocal = RigAnim->PoseLocal;
			const FTransform Delta = Cur * D.T0.Inverse();
			if (D.MID)
			{
				const FVector O = Delta.TransformPosition(D.ClipO);
				const FVector N = Delta.TransformVectorNoScale(D.ClipN);
				D.MID->SetVectorParameterValue(TEXT("ClipOrigin"), FLinearColor(O.X, O.Y, O.Z));
				D.MID->SetVectorParameterValue(TEXT("ClipNormal"), FLinearColor(N.X, N.Y, N.Z));
			}
			if (FX && FMath::FRand() < 0.5f && U < 0.95f) FX->SpawnFlame(Cur.GetLocation() + FVector(0, 0, FMath::FRandRange(500.f, 7000.f)), 300.f, 1, 1.2f);
		}
		else if (D.Kind == 1 && D.Comp)
		{
			if (!D.bRest)
			{
				D.Vel.Z -= 2600.f * Dt;
				FTransform Cur = D.Comp->GetComponentTransform();
				Cur.AddToTranslation(D.Vel * Dt);
				Cur.SetRotation((FRotator(D.Spin.X, D.Spin.Z, D.Spin.Y) * Dt).Quaternion() * Cur.GetRotation());
				const float Ground = Dist ? Dist->SampleHeightCm(Cur.GetLocation().X, Cur.GetLocation().Y) : -100000.f;
				if (Cur.GetLocation().Z - 1500.f < Ground && D.Vel.Z < 0.f)
				{
					D.bRest = true;
					if (FX) { FX->SpawnDust(Cur.GetLocation(), 2500.f, 24, 1.4f); FX->SpawnExplosion(Cur.GetLocation(), 1.1f); }
					IVAudio::Play3D(GetWorld(), TEXT("env_distant_boom_01"), Cur.GetLocation(), 1.f);
					Cur.SetLocation(FVector(Cur.GetLocation().X, Cur.GetLocation().Y, Ground + 1500.f));
				}
				D.Comp->SetWorldTransform(Cur);
				if (FX && FMath::FRand() < 0.6f) FX->SpawnFlame(Cur.GetLocation(), 300.f, 1, 1.2f);
				if (FX && FMath::FRand() < 0.4f) FX->SpawnSmoke(Cur.GetLocation(), 300.f, 1, 1.f);
			}
			else if (FX && FMath::FRand() < 0.15f)
			{
				FX->SpawnFlame(D.Comp->GetComponentLocation() + FVector(0, 0, 800.f), 400.f, 1, 1.0f);
				FX->SpawnSmoke(D.Comp->GetComponentLocation() + FVector(0, 0, 900.f), 300.f, 1, 1.f);
			}
		}
		else if (D.Kind == 2 && SwordDrop && !D.bRest)
		{
			D.Vel.Z -= 2600.f * Dt;
			FTransform Cur = SwordDrop->GetComponentTransform();
			Cur.AddToTranslation(D.Vel * Dt);
			Cur.SetRotation((FRotator(D.Spin.X, D.Spin.Z, D.Spin.Y) * Dt).Quaternion() * Cur.GetRotation());
			const float Ground = Dist ? Dist->SampleHeightCm(Cur.GetLocation().X, Cur.GetLocation().Y) : -100000.f;
			if (Cur.GetLocation().Z < Ground + 400.f && D.Vel.Z < 0.f) { D.bRest = true; if (FX) FX->SpawnSparks(Cur.GetLocation(), FVector::UpVector, 60, 5000.f); }
			else SwordDrop->SetWorldTransform(Cur);
		}
	}
}


// ---------------------------------------------------------------------------------------------------------- infection growths
void AIVMechPawn::BuildGrowths()
{
	if (!RigMesh) return;
	UStaticMesh* Cone = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cone.Cone"));
	UStaticMesh* Sph = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	UMaterialInterface* GM = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Growth.M_Growth"));
	if (!Cone || !Sph || !GM) return;
	GrowthMID = UMaterialInstanceDynamic::Create(GM, this);
	struct FSpec { const TCHAR* Bone; iv::Zone Z; int32 Spikes; int32 Tumors; FVector Radii; float Len; float Rad; FVector Bias; };
	static const FSpec Specs[] = {
		{ TEXT("torso"), iv::Zone::Torso, 11, 4, FVector(800, 1500, 1250), 1700.f, 230.f, FVector(-0.4f, 0.f, 0.8f) },
		{ TEXT("head"), iv::Zone::Head, 4, 0, FVector(250, 380, 380), 900.f, 130.f, FVector(-0.5f, 0.f, 1.f) },
		{ TEXT("reactor"), iv::Zone::Reactor, 0, 3, FVector(500, 600, 500), 0.f, 0.f, FVector(0.f, 0.f, 0.f) },
		{ TEXT("shoulder_l"), iv::Zone::ShoulderL, 3, 1, FVector(500, 650, 500), 1300.f, 190.f, FVector(0.f, -0.8f, 0.8f) },
		{ TEXT("shoulder_r"), iv::Zone::ShoulderR, 3, 1, FVector(500, 650, 500), 1300.f, 190.f, FVector(0.f, 0.8f, 0.8f) },
		{ TEXT("forearm_l"), iv::Zone::ArmL, 3, 0, FVector(350, 350, 350), 1000.f, 120.f, FVector(-0.3f, -0.6f, 0.6f) },
		{ TEXT("forearm_r"), iv::Zone::ArmR, 3, 0, FVector(350, 350, 350), 1000.f, 120.f, FVector(-0.3f, 0.6f, 0.6f) },
		{ TEXT("thigh_l"), iv::Zone::LegL, 2, 1, FVector(450, 450, 450), 1100.f, 150.f, FVector(-0.4f, -0.5f, 0.5f) },
		{ TEXT("thigh_r"), iv::Zone::LegR, 2, 1, FVector(450, 450, 450), 1100.f, 150.f, FVector(-0.4f, 0.5f, 0.5f) },
	};
	FRandomStream R(GetUniqueID() * 7 + 11);
	const FTransform ActorXf = GetActorTransform();
	for (const FSpec& S : Specs)
	{
		const int32 BI = RigMesh->GetBoneIndex(FName(S.Bone));
		if (BI == INDEX_NONE) continue;
		const FTransform BoneXf = RigMesh->GetBoneTransform(BI);
		auto Make = [&](UStaticMesh* M, const FVector& WorldPos, const FVector& WorldDir, const FVector& Scale, bool bTumor)
		{
			UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
			C->SetStaticMesh(M);
			C->SetMaterial(0, GrowthMID);
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			C->SetCastShadow(false);
			C->bAffectDynamicIndirectLighting = true;
			// built in world space, stored relative to the bone so it follows the animation
			const FTransform W(FRotationMatrix::MakeFromZ(WorldDir).ToQuat(), WorldPos, Scale);
			C->RegisterComponent();
			C->SetWorldTransform(W);
			C->AttachToComponent(RigMesh, FAttachmentTransformRules::KeepWorldTransform, FName(S.Bone));
			GrowthComps.Add(C);
			FIVGrowth G;
			G.C = C; G.Z = S.Z; G.Full = C->GetRelativeScale3D(); G.Phase = R.FRand() * 6.28f; G.bTumor = bTumor;
			Growths.Add(G);
		};
		const FVector Centre = BoneXf.GetLocation();
		auto Dir = [&](const FVector& Bias) -> FVector
		{
			for (int32 Try = 0; Try < 12; ++Try)
			{
				const FVector V = R.VRand();
				const FVector A = ActorXf.TransformVectorNoScale(FVector(V.X * S.Radii.X, V.Y * S.Radii.Y, V.Z * S.Radii.Z));
				const FVector Bw = ActorXf.TransformVectorNoScale(Bias);
				if (FVector::DotProduct(A.GetSafeNormal(), Bw.GetSafeNormal() + FVector(0.0001f)) > -0.2f || Bias.IsNearlyZero()) return V;
			}
			return R.VRand();
		};
		for (int32 i = 0; i < S.Spikes; ++i)
		{
			const FVector V = Dir(S.Bias);
			const FVector Local(V.X * S.Radii.X, V.Y * S.Radii.Y, V.Z * S.Radii.Z);
			const FVector Pos = Centre + ActorXf.TransformVectorNoScale(Local);
			FVector Out = (ActorXf.TransformVectorNoScale(Local)).GetSafeNormal();
			Out = (Out + ActorXf.TransformVectorNoScale(S.Bias) * 0.6f + R.VRand() * 0.2f).GetSafeNormal();
			const float L = S.Len * R.FRandRange(0.55f, 1.2f), Rd = S.Rad * R.FRandRange(0.7f, 1.2f);
			// the engine cone is 100 cm tall with the pivot in the middle: stand its base on the surface
			Make(Cone, Pos + Out * L * 0.42f, Out, FVector(Rd / 50.f, Rd / 50.f, L / 100.f), false);
		}
		for (int32 i = 0; i < S.Tumors; ++i)
		{
			const FVector V = Dir(S.Bias);
			const FVector Local(V.X * S.Radii.X * 0.9f, V.Y * S.Radii.Y * 0.9f, V.Z * S.Radii.Z * 0.9f);
			const FVector Pos = Centre + ActorXf.TransformVectorNoScale(Local);
			const float Rd = FMath::Max(S.Radii.GetMin() * R.FRandRange(0.35f, 0.6f), 150.f);
			Make(Sph, Pos, FVector::UpVector, FVector(Rd / 50.f), true);
		}
	}
	UE_LOG(LogTemp, Display, TEXT("IV infection: %d growths"), Growths.Num());
}

void AIVMechPawn::UpdateGrowths(float Dt)
{
	if (Growths.Num() == 0) { if (bRigActive && GrowthComps.Num() == 0) BuildGrowths(); return; }
	const float T = GetWorld()->GetTimeSeconds();
	float Worst = 0.f;
	for (int32 i = 0; i < iv::kZoneCount; ++i) Worst = FMath::Max(Worst, FMath::Clamp(float(int32(ZoneStates[i])) / 5.f, 0.f, 1.f));
	if (GrowthMID)
	{
		GrowthMID->SetScalarParameterValue(TEXT("Pulse"), FMath::Clamp(0.45f + 0.9f * Worst, 0.f, 1.6f));
		GrowthMID->SetScalarParameterValue(TEXT("Hue"), FMath::Clamp(0.25f + 0.6f * Worst, 0.f, 1.f));
	}
	for (FIVGrowth& G : Growths)
	{
		if (!G.C) continue;
		const float Dmg = FMath::Clamp(float(int32(ZoneStates[iv::Index(G.Z)])) / 5.f, 0.f, 1.f);
		const bool bGone = ZoneStates[iv::Index(G.Z)] >= iv::ZoneState::Severed;
		const float Want = bGone ? 0.f : (0.45f + 0.75f * Dmg) * (1.f + (G.bTumor ? 0.12f * FMath::Sin(T * 3.1f + G.Phase) : 0.f));
		G.Cur = FMath::FInterpTo(G.Cur, Want, Dt, 3.f);
		G.C->SetRelativeScale3D(G.Full * G.Cur);
		G.C->SetVisibility(G.Cur > 0.03f);
	}
}


// ---------------------------------------------------------------------------------------------------------- hydraulics and hardware
void AIVMechPawn::BuildGreebles()
{
	if (!RigMesh) return;
	UStaticMesh* Cyl = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
	UStaticMesh* Sph = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	UMaterialInterface* Armor = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_MechArmor.M_MechArmor"));
	UMaterialInterface* Emi = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Emissive.M_Emissive"));
	if (!Cyl || !Cube || !Sph || !Armor) return;
	UMaterialInstanceDynamic* Chrome = UMaterialInstanceDynamic::Create(Armor, this);
	Chrome->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.62f, 0.64f, 0.7f));
	Chrome->SetScalarParameterValue(TEXT("Metallic"), 1.f);
	Chrome->SetScalarParameterValue(TEXT("Wear"), 0.2f);
	GreebleMID = Chrome;
	UMaterialInstanceDynamic* Lamp = nullptr;
	if (Emi)
	{
		Lamp = UMaterialInstanceDynamic::Create(Emi, this);
		Lamp->SetVectorParameterValue(TEXT("Color"), LampColor);
		Lamp->SetScalarParameterValue(TEXT("Intensity"), 22.f);
	}
	const FTransform ActorXf = GetActorTransform();
	const FVector TorsoC = RigMesh->GetBoneLocation(FName(TEXT("torso")), EBoneSpaces::WorldSpace);
	auto Attach = [&](UStaticMesh* M, UMaterialInterface* Mat, const FName& Bone, const FVector& Pos, const FQuat& Rot, const FVector& Scale)
	{
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
		C->SetStaticMesh(M);
		if (Mat) C->SetMaterial(0, Mat);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCastShadow(false);
		C->RegisterComponent();
		C->SetWorldTransform(FTransform(Rot, Pos, Scale));
		C->AttachToComponent(RigMesh, FAttachmentTransformRules::KeepWorldTransform, Bone);
		GreebleComps.Add(C);
	};
	struct FSeg { const TCHAR* A; const TCHAR* B; float Side; };
	static const FSeg Segs[] = {
		{ TEXT("upperarm_l"), TEXT("forearm_l"), -1.f }, { TEXT("forearm_l"), TEXT("hand_l"), -1.f }, { TEXT("upperarm_r"), TEXT("forearm_r"), 1.f }, { TEXT("forearm_r"), TEXT("hand_r"), 1.f },
		{ TEXT("thigh_l"), TEXT("shin_l"), -1.f }, { TEXT("shin_l"), TEXT("foot_l"), -1.f }, { TEXT("thigh_r"), TEXT("shin_r"), 1.f }, { TEXT("shin_r"), TEXT("foot_r"), 1.f } };
	for (const FSeg& S : Segs)
	{
		const int32 IA = RigMesh->GetBoneIndex(FName(S.A)), IB = RigMesh->GetBoneIndex(FName(S.B));
		if (IA == INDEX_NONE || IB == INDEX_NONE) continue;
		const FVector PA = RigMesh->GetBoneLocation(FName(S.A), EBoneSpaces::WorldSpace), PB = RigMesh->GetBoneLocation(FName(S.B), EBoneSpaces::WorldSpace);
		const FVector Axis = (PB - PA);
		const float Len = Axis.Size();
		if (Len < 200.f) continue;
		const FVector Ax = Axis / Len;
		// push the hydraulics out of the limb: away from the body centre line, a little forward
		FVector Out = (PA + PB) * 0.5f - TorsoC;
		Out -= Ax * FVector::DotProduct(Out, Ax);
		Out = (Out.GetSafeNormal() * 0.6f + ActorXf.GetRotation().GetForwardVector() * 0.5f + ActorXf.GetRotation().GetRightVector() * S.Side * 0.3f).GetSafeNormal();
		const float Off = FMath::Min(Len * 0.14f, 420.f);
		const FVector P0 = PA + Ax * Len * 0.12f + Out * Off, P1 = PB - Ax * Len * 0.1f + Out * Off * 0.8f;
		const FVector Mid = (P0 + P1) * 0.5f;
		const FVector D = (P1 - P0);
		const float L = D.Size();
		const FQuat Q = FRotationMatrix::MakeFromZ(D / L).ToQuat();
		const float R = FMath::Clamp(Len * 0.028f, 40.f, 110.f);
		Attach(Cyl, Chrome, FName(S.A), Mid, Q, FVector(R / 50.f, R / 50.f, L / 100.f));                         // outer cylinder
		Attach(Cyl, Chrome, FName(S.B), Mid + (D / L) * L * 0.3f, Q, FVector(R / 90.f, R / 90.f, L * 0.55f / 100.f));  // piston rod
		Attach(Sph, Chrome, FName(S.A), P0, Q, FVector(R / 38.f));                                                // pivots
		Attach(Sph, Chrome, FName(S.B), P1, Q, FVector(R / 38.f));
	}
	// back stacks and shoulder lamps
	if (RigMesh->GetBoneIndex(FName(TEXT("torso"))) != INDEX_NONE)
	{
		const FVector Back = -ActorXf.GetRotation().GetForwardVector(), Right = ActorXf.GetRotation().GetRightVector(), Up = FVector::UpVector;
		for (int32 s = -1; s <= 1; s += 2)
		{
			const FVector Base = TorsoC + Back * 650.f + Right * s * 520.f + Up * 700.f;
			Attach(Cyl, Chrome, FName(TEXT("torso")), Base + Up * 520.f, FQuat::Identity, FVector(1.5f, 1.5f, 11.f));
			if (Lamp) Attach(Cyl, Lamp, FName(TEXT("torso")), Base + Up * 1080.f, FQuat::Identity, FVector(1.3f, 1.3f, 0.3f));
			if (Lamp) Attach(Sph, Lamp, FName(TEXT("torso")), TorsoC + Right * s * 1300.f + Up * 1500.f + ActorXf.GetRotation().GetForwardVector() * 300.f, FQuat::Identity, FVector(1.1f));
			for (int32 k = 0; k < 3; ++k)   // vent grille
				Attach(Cube, Chrome, FName(TEXT("torso")), TorsoC + Back * 780.f + Right * s * 220.f + Up * (250.f + 130.f * k), FQuat::Identity, FVector(0.4f, 3.0f, 0.5f));
		}
	}
	UE_LOG(LogTemp, Display, TEXT("IV greebles: %d parts"), GreebleComps.Num());
}


// ---------------------------------------------------------------------------------------------------------- blade contact
// The blade must not pass through the opponent's body or the city: the animation says where the arm WANTS to go, this layer measures how deep
// the blade is inside a solid (from last frame's real transforms) and pulls the arms back towards the guard until it rests on the surface.
// The block is held through the strike so the blade stays pressed against the target, then eases off in recovery.
void AIVMechPawn::UpdateBladeContact(float Dt, FIVPoseAngles& Pose)
{
	if (!bRigActive || !RigMesh || !SwordMesh || FParse::Param(FCommandLine::Get(), TEXT("IVNoBladeBlock"))) return;
	if (!OtherMechCache.IsValid()) for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It) if (*It != this) { OtherMechCache = *It; break; }
	AIVMechPawn* O = OtherMechCache.Get();
	FVector B0, T0;
	GetBladeSegment(B0, T0);
	const FVector Bm = B0 + (T0 - B0) * 0.12f;
	float Pen = 0.f;
	FVector ContactAt = FVector::ZeroVector;
	float BodyPen = 0.f, BladePen = 0.f;
	if (O && O->RigMesh && O->bRigActive)
	{
		struct FCap { const TCHAR* A; const TCHAR* B; float R; };
		static const FCap Caps[] = {
			{ TEXT("pelvis"), TEXT("torso"), 1000.f }, { TEXT("torso"), TEXT("head"), 900.f }, { TEXT("head"), TEXT("head"), 650.f },
			{ TEXT("shoulder_l"), TEXT("upperarm_l"), 520.f }, { TEXT("upperarm_l"), TEXT("forearm_l"), 420.f }, { TEXT("forearm_l"), TEXT("hand_l"), 380.f },
			{ TEXT("shoulder_r"), TEXT("upperarm_r"), 520.f }, { TEXT("upperarm_r"), TEXT("forearm_r"), 420.f }, { TEXT("forearm_r"), TEXT("hand_r"), 380.f },
			{ TEXT("thigh_l"), TEXT("shin_l"), 560.f }, { TEXT("shin_l"), TEXT("foot_l"), 470.f }, { TEXT("thigh_r"), TEXT("shin_r"), 560.f }, { TEXT("shin_r"), TEXT("foot_r"), 470.f } };
		for (const FCap& K : Caps)
		{
			const FVector A = O->RigMesh->GetBoneLocation(FName(K.A), EBoneSpaces::WorldSpace);
			const FVector Bp = O->RigMesh->GetBoneLocation(FName(K.B), EBoneSpaces::WorldSpace);
			FVector P1, P2;
			FMath::SegmentDistToSegment(Bm, T0, A, Bp, P1, P2);
			const float D = K.R - (P1 - P2).Size();
			if (D > BodyPen) { BodyPen = D; ContactAt = P1; }
			Pen = FMath::Max(Pen, D);
		}
	}
	// the opponent's blade: the two swords meet and stop each other instead of passing through
	if (O && O->SwordMesh && O->bRigActive)
	{
		FVector OB0, OT0;
		O->GetBladeSegment(OB0, OT0);
		FVector P1, P2;
		FMath::SegmentDistToSegment(Bm, T0, OB0, OT0, P1, P2);
		const float Dd = (P1 - P2).Size();
		if (Dd < 330.f)
		{
			Pen = FMath::Max(Pen, 330.f - Dd + 40.f);
			BladePen = 330.f - Dd;
			ContactAt = (P1 + P2) * 0.5f;
		}
	}
	// the city: a trace along the blade
	{
		FHitResult Hit;
		FCollisionQueryParams Q(SCENE_QUERY_STAT(IVBladeWorld), false, this);
		if (O) Q.AddIgnoredActor(O);
		if (GetWorld()->LineTraceSingleByChannel(Hit, Bm, T0, ECC_WorldStatic, Q))
			Pen = FMath::Max(Pen, (1.f - Hit.Time) * (T0 - Bm).Size() * 0.5f + 60.f);
	}
	// sparks + flash + clang while the steel is touching (only one of the two pawns reports a blade-blade clash)
	{
		ContactSparkCool -= Dt; ContactSoundCool -= Dt;
		const bool bFighting = CombatAnim.phase != iv::Phase::Idle || (O && O->CombatAnim.phase != iv::Phase::Idle);
		const bool bBlade = BladePen > 10.f && (!O || this < O);
		const bool bBody = BodyPen > 10.f && CombatAnim.phase != iv::Phase::Idle;
		const bool bTouch = bFighting && (bBlade || bBody);
		if (bTouch)
		{
			const float Str = FMath::Clamp(FMath::Max(BladePen, BodyPen) / 200.f, 0.4f, 1.6f);
			if (!bWasTouching || ContactSparkCool <= 0.f) { EmitContactSparks(ContactAt, bBlade, bWasTouching ? 0.45f * Str : Str); ContactSparkCool = 0.05f; }
		}
		bWasTouching = bTouch;
	}
	const bool bStriking = CombatAnim.phase == iv::Phase::Strike || CombatAnim.phase == iv::Phase::Contact;
	if (Pen > 20.f && CombatAnim.phase != iv::Phase::Idle)
	{
		const float Target = FMath::Clamp(Pen / 260.f, 0.f, 1.f);
		BladeBlock = FMath::Max(BladeBlock, FMath::FInterpTo(BladeBlock, Target, Dt, 14.f));
		BladeBlockHold = 0.18f;
	}
	else
	{
		BladeBlockHold -= Dt;
		if (!bStriking || BladeBlockHold <= 0.f) BladeBlock = FMath::FInterpTo(BladeBlock, 0.f, Dt, 3.2f);
	}
	{ static float LogT = 0.f; LogT += Dt; if (BladeBlock > 0.25f && LogT > 1.f) { LogT = 0.f; UE_LOG(LogTemp, Display, TEXT("IV blade block %.2f pen %.0f phase %d (%s)"), BladeBlock, Pen, int32(CombatAnim.phase), *GetName()); } }
	if (BladeBlock < 0.01f) return;
	const FIVPoseAngles* Guard = RigData ? RigData->FindPose(FName(TEXT("guard_neutral"))) : nullptr;
	if (!Guard) return;
	static const TCHAR* Arm[] = { TEXT("shoulder_l"), TEXT("upperarm_l"), TEXT("forearm_l"), TEXT("hand_l"), TEXT("shoulder_r"), TEXT("upperarm_r"), TEXT("forearm_r"), TEXT("hand_r"), TEXT("torso") };
	for (int32 i = 0; i < UE_ARRAY_COUNT(Arm); ++i)
	{
		const FName B(Arm[i]);
		FVector* V = Pose.Joint.Find(B);
		const FVector* G = Guard->Joint.Find(B);
		if (V && G) *V = FMath::Lerp(*V, *G, BladeBlock * (i == 8 ? 0.35f : 0.82f));
	}
}


// ---------------------------------------------------------------------------------------------------------- armour plates
// Curved shells authored in Blender (art/armor/build_armor.py): they hug the limbs, are bolted to the bones and come off in pieces
// (the whole shell tumbles away, burning) as the zone beneath is damaged.
void AIVMechPawn::BuildPlates()
{
	if (!RigMesh) return;
	UMaterialInterface* Armor = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_MechArmor.M_MechArmor"));
	if (!Armor) return;
	PlateMID = UMaterialInstanceDynamic::Create(Armor, this);
	PlateMID->SetVectorParameterValue(TEXT("Tint"), HullTint * 2.0f + FLinearColor(0.025f, 0.025f, 0.03f));
	PlateMID->SetScalarParameterValue(TEXT("Metallic"), 0.8f);
	PlateMID->SetScalarParameterValue(TEXT("Wear"), 0.7f);
	auto Mesh = [](const TCHAR* N) { return LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Armor/%s.%s"), N, N)); };
	const FQuat Q = GetActorQuat();
	const FVector Fw = Q.GetForwardVector(), Rt = Q.GetRightVector(), Up = FVector::UpVector;
	auto Bone = [&](const TCHAR* B) { return RigMesh->GetBoneLocation(FName(B), EBoneSpaces::WorldSpace); };
	auto Add = [&](const TCHAR* MeshName, const TCHAR* AttachBone, iv::Zone Z, const FVector& Pos, const FVector& Axis, const FVector& Out, const FVector& Scale)
	{
		UStaticMesh* M = Mesh(MeshName);
		if (!M || RigMesh->GetBoneIndex(FName(AttachBone)) == INDEX_NONE) return;
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
		C->SetStaticMesh(M);
		C->SetMaterial(0, PlateMID);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCastShadow(false);
		C->RegisterComponent();
		C->SetWorldTransform(FTransform(FRotationMatrix::MakeFromZX(Axis.GetSafeNormal(), Out).ToQuat(), Pos, Scale));
		C->AttachToComponent(RigMesh, FAttachmentTransformRules::KeepWorldTransform, FName(AttachBone));
		FIVPlate P;
		P.C = C; P.Z = Z; P.Size = Scale;
		Plates.Add(P);
	};
	// torso
	{
		const FVector Ctr = Bone(TEXT("torso")) + Fw * -250.f + Up * 780.f;
		Add(TEXT("Armor_Chest"), TEXT("torso"), iv::Zone::Torso, Ctr, Up, Fw, FVector(11.5f, 11.5f, 22.f));
		Add(TEXT("Armor_Back"), TEXT("reactor"), iv::Zone::Reactor, Ctr - Fw * 80.f, Up, Fw, FVector(11.5f, 11.5f, 21.f));
		Add(TEXT("Armor_Skirt"), TEXT("pelvis"), iv::Zone::Torso, Bone(TEXT("pelvis")) + Fw * -100.f - Up * 250.f, Up, Fw, FVector(19.f, 19.f, 9.f));
		Add(TEXT("Armor_Head"), TEXT("head"), iv::Zone::Head, Bone(TEXT("head")) + Up * 220.f, Up, Fw, FVector(8.f, 8.f, 8.f));
	}
	for (int32 sd = -1; sd <= 1; sd += 2)
	{
		const bool L = sd < 0;
		const FVector Side = Rt * float(sd);
		const iv::Zone ZS = L ? iv::Zone::ShoulderL : iv::Zone::ShoulderR, ZA = L ? iv::Zone::ArmL : iv::Zone::ArmR, ZL = L ? iv::Zone::LegL : iv::Zone::LegR;
		const TCHAR* BSh = L ? TEXT("shoulder_l") : TEXT("shoulder_r");
		const TCHAR* BUa = L ? TEXT("upperarm_l") : TEXT("upperarm_r");
		const TCHAR* BFa = L ? TEXT("forearm_l") : TEXT("forearm_r");
		const TCHAR* BHa = L ? TEXT("hand_l") : TEXT("hand_r");
		const TCHAR* BTh = L ? TEXT("thigh_l") : TEXT("thigh_r");
		const TCHAR* BSn = L ? TEXT("shin_l") : TEXT("shin_r");
		const TCHAR* BFt = L ? TEXT("foot_l") : TEXT("foot_r");
		// pauldron on top of the shoulder, facing out and forward
		Add(TEXT("Armor_Pauldron"), BSh, ZS, Bone(BSh) + Side * 380.f + Up * 260.f, (Up + Side * 0.9f).GetSafeNormal(), Fw, FVector(12.f, 12.f, 11.f));
		// guards follow the real limb axis
		auto Guard = [&](const TCHAR* MeshName, const TCHAR* A, const TCHAR* B, iv::Zone Z, float RadiusCm, float R0, const FVector& OutBias, float LenScale)
		{
			const FVector PA = Bone(A), PB = Bone(B);
			const float Len = (PB - PA).Size();
			const FVector Ax = (PB - PA).GetSafeNormal();
			const FVector Out = (OutBias - Ax * FVector::DotProduct(OutBias, Ax)).GetSafeNormal();
			const float S = RadiusCm / R0;
			Add(MeshName, A, Z, (PA + PB) * 0.5f + Out * 60.f, Ax, Out, FVector(S, S, FMath::Max(Len * LenScale, 300.f) / 100.f));
		};
		Guard(TEXT("Armor_Bracer"), BUa, BFa, ZA, 560.f, 46.f, Fw * 0.7f + Side * 0.5f, 0.9f);
		Guard(TEXT("Armor_Bracer"), BFa, BHa, ZA, 470.f, 46.f, Fw * 0.8f + Side * 0.3f, 1.0f);
		Guard(TEXT("Armor_Thigh"), BTh, BSn, ZL, 650.f, 52.f, Fw, 0.95f);
		Guard(TEXT("Armor_Shin"), BSn, BFt, ZL, 560.f, 50.f, Fw, 1.0f);
		Add(TEXT("Armor_Cap"), BFa, ZA, Bone(BFa) + Fw * 140.f, Up, Fw + Side * 0.4f, FVector(8.f, 8.f, 8.f));
		Add(TEXT("Armor_Cap"), BSn, ZL, Bone(BSn) + Fw * 260.f, Up, Fw, FVector(10.f, 10.f, 10.f));
	}
	UE_LOG(LogTemp, Display, TEXT("IV plates: %d"), Plates.Num());
}


void AIVMechPawn::EmitContactSparks(const FVector& At, bool bBlade, float Strength)
{
	UWorld* W = GetWorld();
	if (AIVFXManager* FX = AIVFXManager::Get(W))
	{
		const FVector Out = (At - GetActorLocation()).GetSafeNormal2D();
		FX->SpawnSparks(At, (Out + FVector(0, 0, 0.5f)).GetSafeNormal(), FMath::RoundToInt(10.f + 14.f * Strength), 6500.f + 3500.f * Strength, 3.f);
		FX->SpawnSparks(At, FVector::UpVector, FMath::RoundToInt(4.f * Strength), 4000.f, 2.f);
		FX->SpawnFlash(At, bBlade ? FLinearColor(1.f, 0.82f, 0.5f) : FLinearColor(1.f, 0.55f, 0.25f), 5.0e5f * Strength, 0.12f, 9000.f);
	}
	if (ContactSoundCool <= 0.f)
	{
		IVAudio::Play3D(W, bBlade ? TEXT("parry_clang") : TEXT("hit_metal_contact_light"), At, FMath::Clamp(0.5f + 0.4f * Strength, 0.4f, 1.f), FMath::RandRange(0.9f, 1.15f));
		ContactSoundCool = 0.28f;
	}
}

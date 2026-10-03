#include "IVMechPawn.h"
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

static TAutoConsoleVariable<int32> CVarIVCam(TEXT("iv.Cam"), 0,
	TEXT("0 = cockpit, 1 = chase, 2 = side, 3 = front orbit, 4 = both mechs from the side"), ECVF_Default);
static TAutoConsoleVariable<int32> CVarRigApply(TEXT("iv.RigApply"), 1, TEXT("0 = leave the rig in its rest pose"), ECVF_Default);
static TAutoConsoleVariable<float> CVarIVCamDist(TEXT("iv.CamDist"), 16000.f, TEXT("Debug camera distance (cm)"), ECVF_Default);

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

	auto CP = [this](const TCHAR* Name, FVector Size, FVector Loc, FRotator Rot = FRotator::ZeroRotator)
	{
		UStaticMeshComponent* M = AddBlock(CockpitSway, Name, Size, Loc, FLinearColor::Black);
		M->SetRelativeRotation(Rot);
		AllMeshes.Remove(M);   // cockpit parts are not tinted with the body
		CockpitMeshes.Add(M);
		M->SetCastShadow(false);
		M->SetOnlyOwnerSee(true);
	};
	// grey-box cockpit until TASK-003 lands: dash slab, pillars, top bar, control frames and grips
	CP(TEXT("Cockpit_Dash"), FVector(60, 150, 14), FVector(55, 0, -42), FRotator(-12, 0, 0));
	CP(TEXT("Cockpit_PillarL"), FVector(16, 10, 150), FVector(48, -92, 0), FRotator(0, 0, 8));
	CP(TEXT("Cockpit_PillarR"), FVector(16, 10, 150), FVector(48, 92, 0), FRotator(0, 0, -8));
	CP(TEXT("Cockpit_Top"), FVector(30, 190, 10), FVector(45, 0, 52), FRotator(8, 0, 0));
	CP(TEXT("Cockpit_FrameL"), FVector(28, 22, 18), FVector(42, -52, -34));
	CP(TEXT("Cockpit_FrameR"), FVector(28, 22, 18), FVector(42, 52, -34));
	CP(TEXT("Cockpit_GripL"), FVector(8, 8, 26), FVector(36, -52, -22), FRotator(-15, 0, 0));
	CP(TEXT("Cockpit_GripR"), FVector(8, 8, 26), FVector(36, 52, -22), FRotator(-15, 0, 0));
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
	for (UStaticMeshComponent* M : CockpitMeshes) MakeMID(M, FLinearColor(0.02f, 0.022f, 0.026f));

	SetupRig();

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

void AIVMechPawn::SetFirstPersonView(bool bFirstPerson)
{
	if (HeadMesh) HeadMesh->SetOwnerNoSee(bFirstPerson);
	for (UStaticMeshComponent* M : CockpitMeshes) M->SetVisibility(bFirstPerson);
}

FVector AIVMechPawn::GetEyeLocation() const
{
	return HeadPivot->GetComponentTransform().TransformPosition(FVector(450.f, 0, 420.f));
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
	if (IsLocallyControlled() || GetIVCam() != 0) UpdateCockpitCamera(Dt);
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
	const FVector Desired = Wish.GetClampedToMaxSize2D(1.f) * MaxSpeed;
	const FVector Delta = Desired - Velocity;
	const float Rate = (Mag > 0.05f) ? Acceleration : Deceleration;
	const float Step = Rate * Dt;
	Velocity += (Delta.Size2D() <= Step) ? Delta : Delta.GetSafeNormal2D() * Step;
	Velocity.Z = 0;

	SetActorRotation(FRotator(0, NewLegsYaw, 0));
	if (!Velocity.IsNearlyZero())
	{
		FHitResult Hit;
		const FVector Move = Velocity * Dt;
		AddActorWorldOffset(Move, true, &Hit);
		if (Hit.IsValidBlockingHit())
		{
			const FVector Rest = FVector::VectorPlaneProject(Move, Hit.ImpactNormal) * (1.f - Hit.Time);
			AddActorWorldOffset(Rest, true);
			Velocity = FVector::VectorPlaneProject(Velocity, Hit.ImpactNormal) * 0.9f;
			Velocity.Z = 0;
		}
	}

	FHitResult G;
	FCollisionQueryParams Q(SCENE_QUERY_STAT(IVGround), false, this);
	const FVector P = GetActorLocation();
	if (GetWorld()->LineTraceSingleByChannel(G, P + FVector(0, 0, 3000), P - FVector(0, 0, 12000), ECC_WorldStatic, Q))
	{
		SetActorLocation(FVector(P.X, P.Y, G.ImpactPoint.Z + 4100.f));
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
	CockpitSway->SetRelativeLocationAndRotation(SwayOffset, SwayRot);

	// world layer: stabilised horizon, low-passed vertical bob
	const FVector Eye = GetEyeLocation();
	CamPos.X = Eye.X;
	CamPos.Y = Eye.Y;
	CamPos.Z = FMath::FInterpTo(CamPos.Z, Eye.Z, Dt, 5.f);
	CamRot.Yaw = GetActorRotation().Yaw + TorsoYawRel;
	CamRot.Pitch = FMath::FInterpTo(CamRot.Pitch, AimPitch, Dt, 14.f);
	CamRot.Roll = 0.25f * PelvisPivot->GetRelativeRotation().Roll;

	if (bCine)
	{
		SetFirstPersonView(false);
		CineT += Dt;
		AIVMechPawn* Sub = CineSubject.Get();
		if (!Sub) Sub = this;
		const float U = FMath::Clamp(CineT / FMath::Max(CineDur, 0.1f), 0.f, 1.f);
		const FVector CC = Sub->GetActorLocation() + FVector(0, 0, 2800.f);
		const float Ang = FMath::Lerp(-70.f, 35.f, U);
		const FVector Off = FRotator(0.f, Sub->GetActorRotation().Yaw + 90.f + Ang, 0.f).Vector() * 9500.f;
		const FVector From2 = CC + Off + FVector(0, 0, FMath::Lerp(-1500.f, 600.f, U));
		Camera->SetFieldOfView(58.f);
		Camera->SetWorldLocationAndRotation(From2, (CC + FVector(0, 0, 900.f) - From2).Rotation());
		return;
	}
	Camera->SetFieldOfView(92.f);

	if (Mode == 0)
	{
		Camera->SetWorldLocationAndRotation(CamPos, CamRot + FRotator(0.3f * SwayRot.Pitch, 0.3f * SwayRot.Yaw, 0.3f * SwayRot.Roll));
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
	USkeletalMesh* SM = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Mechs/Bastion/BASTION_01.BASTION_01"));
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
	SwayVel += FVector(-45.f * Strength, 55.f * Right * Strength, 40.f * Up * Strength);
	SwayRotVel += FVector(-14.f * Right * Strength, -9.f * Strength * FMath::Abs(Up) - 7.f * Strength, 9.f * Right * Strength);
}

void AIVMechPawn::OnCombatHit(iv::Zone Z, float Strength01, bool bBlocked, bool bParried, iv::SwingSide Dir)
{
	const FVector Loc = GetZoneWorldLocation(Z);
	if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
	{
		const float K = bParried ? 1.2f : (bBlocked ? 0.6f : 1.f);
		FX->SpawnSparks(Loc, GetActorForwardVector() + FVector(0, 0, 0.3f), int32(10 + 55 * Strength01 * K), 3000.f + 4000.f * Strength01);
		if (Strength01 > 0.35f && !bBlocked) FX->SpawnDust(Loc, 900.f + 1800.f * Strength01, int32(4 + 12 * Strength01), 0.5f + Strength01);
	}
	const float Side = ZoneSide(Z);
	const float S = Strength01 * (bBlocked ? 0.55f : 1.f);
	HitKick += FVector(-7.f * S, 4.f * S * Side, 6.f * S * Side);
	HitKick = HitKick.GetClampedToSize(0.f, 18.f);
	if (IsLocallyControlled()) AddCockpitImpulse(-Side, Z == iv::Zone::Head ? 0.8f : 0.f, S * (bParried ? 0.6f : 1.f));
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
	if (NewState >= iv::ZoneState::Damaged && OldState < iv::ZoneState::Damaged)
	{
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) FX->SpawnDust(GetZoneWorldLocation(Z), 700.f, 6, 0.4f);
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
	static UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
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
	static UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
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
	const FString Arm = (S.arm == iv::Arm::R) ? TEXT("r") : TEXT("l");
	const FString Side = SideName(S.side);

	FIVPoseAngles Target = *Guard;
	bool bLegs = false;

	if (S.posture == iv::Posture::KnockedDown)
	{
		bLegs = true;
		const FIVPoseAngles* A = P(TEXT("knockdown_fall"));
		const FIVPoseAngles* B = P(TEXT("knockdown_down"));
		if (A && B) Target = FIVPoseAngles::Lerp(*A, *B, Ease((S.postureProgress - 0.15f) / 0.5f));
	}
	else if (S.posture == iv::Posture::Staggered || S.posture == iv::Posture::ShutDown)
	{
		bLegs = true;
		if (const FIVPoseAngles* K = P(TEXT("kneel"))) Target = FIVPoseAngles::Lerp(*Guard, *K, S.posture == iv::Posture::ShutDown ? 0.9f : 0.45f * FMath::Sin(FMath::Clamp(S.postureProgress, 0.f, 1.f) * 3.14159f));
	}
	else if (S.posture == iv::Posture::Dodging)
	{
		bLegs = true;
		const FString Dir = (S.lateralShift < 0.f) ? TEXT("left") : TEXT("right");
		const float U = FMath::Clamp(S.postureProgress, 0.f, 1.f);
		const FIVPoseAngles* A = P(FString::Printf(TEXT("dodge_%s_shift"), *Dir));
		const FIVPoseAngles* B = P(FString::Printf(TEXT("dodge_%s_lift"), *Dir));
		const FIVPoseAngles* C = P(FString::Printf(TEXT("dodge_%s_plant"), *Dir));
		if (A && B && C) Target = (U < 0.35f) ? FIVPoseAngles::Lerp(*Guard, *A, Ease(U / 0.35f)) : (U < 0.7f ? FIVPoseAngles::Lerp(*A, *B, Ease((U - 0.35f) / 0.35f)) : FIVPoseAngles::Lerp(*B, *C, Ease((U - 0.7f) / 0.3f)));
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

	// smooth towards the target (fast, but never a pop) and merge into the locomotion pose
	if (!bCombatPoseInit) { CombatPose = *Guard; bCombatPoseInit = true; }
	const float K = 1.f - FMath::Exp(-16.f * Dt);
	CombatPose = FIVPoseAngles::Lerp(CombatPose, Target, K);

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

	// hit kick: torso recoil on top of everything, decays quickly
	HitKick *= FMath::Exp(-7.f * Dt);
	if (FVector* T = Pose.Joint.Find(FName(TEXT("torso")))) *T += HitKick;
	if (FVector* H = Pose.Joint.Find(FName(TEXT("head")))) *H += HitKick * 0.5f;
}

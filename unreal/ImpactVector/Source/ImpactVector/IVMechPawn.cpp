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

static TAutoConsoleVariable<int32> CVarIVCam(TEXT("iv.Cam"), 0,
	TEXT("0 = cockpit, 1 = chase, 2 = side, 3 = front orbit, 4 = both mechs from the side"), ECVF_Default);
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
	if (bAIControlled) UpdateAI(Dt);
	UpdateLocomotion(Dt);
	UpdateGait(Dt);
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
	const FVector Wish = MoveIntentToWorld();
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
}

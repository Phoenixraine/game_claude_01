#include "IVBoarding.h"
#include "IVFXManager.h"
#include "ProceduralMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"

namespace
{
	float Ease(float U) { U = FMath::Clamp(U, 0.f, 1.f); return U * U * (3.f - 2.f * U); }
}

AIVPilotFigure::AIVPilotFigure()
{
	PrimaryActorTick.bCanEverTick = true;
	Body = CreateDefaultSubobject<USceneComponent>(TEXT("Body"));
	RootComponent = Body;
}

void AIVPilotFigure::BeginPlay()
{
	Super::BeginPlay();
	BuildModel();
	Hide();
}

void AIVPilotFigure::BuildModel()
{
	if (bBuilt) return;
	bBuilt = true;
	UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
	UStaticMesh* Sph = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	UMaterialInterface* Armor = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_MechArmor.M_MechArmor"));
	UMaterialInterface* Emi = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Emissive.M_Emissive"));
	if (Armor)
	{
		SuitMat = UMaterialInstanceDynamic::Create(Armor, this);
		SuitMat->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.2f, 0.23f, 0.3f));
		SuitMat->SetScalarParameterValue(TEXT("Metallic"), 0.5f);
	}
	if (Emi)
	{
		GlowMat = UMaterialInstanceDynamic::Create(Emi, this);
		GlowMat->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.1f, 0.8f, 1.f));
		GlowMat->SetScalarParameterValue(TEXT("Intensity"), 8.f);
		CableMat = UMaterialInstanceDynamic::Create(Emi, this);
		CableMat->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.2f, 0.9f, 1.f));
		CableMat->SetScalarParameterValue(TEXT("Intensity"), 5.f);
	}
	auto Add = [&](UStaticMesh* M, const FVector& Loc, const FVector& SizeCm, UMaterialInterface* Mat)
	{
		UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
		C->SetStaticMesh(M);
		C->SetupAttachment(Body);
		C->SetRelativeLocation(Loc);
		C->SetRelativeScale3D(SizeCm / 100.f);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCastShadow(true);
		if (Mat) C->SetMaterial(0, Mat);
		C->RegisterComponent();
		Parts.Add(C);
		return C;
	};
	// a drive-suited pilot, ~4.3 m before the actor scale; origin at the feet, +X forward
	for (int32 s = -1; s <= 1; s += 2)
	{
		Add(Cube, FVector(0, s * 22.f, 85.f), FVector(34, 34, 170), SuitMat);        // legs
		Add(Cube, FVector(8, s * 22.f, 20.f), FVector(52, 38, 34), SuitMat);         // boots
		Add(Cube, FVector(0, s * 66.f, 285.f), FVector(30, 30, 130), SuitMat);       // arms
		Add(Cube, FVector(15, s * 22.f, 85.f), FVector(8, 24, 100), GlowMat);        // glowing shin lines
		Add(Cube, FVector(0, s * 80.f, 295.f), FVector(10, 12, 100), GlowMat);       // arm lines
		Add(Cube, FVector(-48.f, s * 20.f, 215.f), FVector(26, 26, 50), GlowMat);    // jet nozzles
	}
	Add(Cube, FVector(0, 0, 190.f), FVector(56, 84, 40), SuitMat);                    // pelvis
	Add(Cube, FVector(0, 0, 285.f), FVector(64, 104, 150), SuitMat);                  // torso
	Add(Cube, FVector(34, 0, 295.f), FVector(8, 60, 80), GlowMat);                    // chest plate light
	Add(Cube, FVector(-48.f, 0, 290.f), FVector(48, 76, 112), SuitMat);               // jet pack
	Add(Sph, FVector(0, 0, 395.f), FVector(80, 76, 80), SuitMat);                     // helmet
	Add(Cube, FVector(32, 0, 398.f), FVector(10, 56, 22), GlowMat);                   // visor
	Grenade = Add(Sph, FVector::ZeroVector, FVector(46, 46, 46), GlowMat);
	Grenade->SetupAttachment(nullptr);
	Grenade->SetVisibility(false);

	Cable = NewObject<UProceduralMeshComponent>(this);
	Cable->SetupAttachment(Body);
	Cable->bUseAsyncCooking = false;
	Cable->SetUsingAbsoluteLocation(true);
	Cable->SetUsingAbsoluteRotation(true);
	Cable->SetUsingAbsoluteScale(true);
	Cable->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Cable->SetCastShadow(false);
	Cable->RegisterComponent();
	if (CableMat) Cable->SetMaterial(0, CableMat);

	SuitLight = NewObject<UPointLightComponent>(this);
	SuitLight->SetupAttachment(Body);
	SuitLight->SetRelativeLocation(FVector(120, 0, 330));
	SuitLight->SetIntensityUnits(ELightUnits::Candelas);
	SuitLight->SetIntensity(3.0e5f);
	SuitLight->SetLightColor(FLinearColor(0.4f, 0.9f, 1.f));
	SuitLight->SetAttenuationRadius(4000.f);
	SuitLight->SetCastShadows(false);
	SuitLight->RegisterComponent();
	SetActorScale3D(FVector(1.4f));
}

void AIVPilotFigure::Hide()
{
	SetActorHiddenInGame(true);
	if (Cable) Cable->ClearAllMeshSections();
	if (Grenade) Grenade->SetVisibility(false);
	if (SuitLight) SuitLight->SetVisibility(false);
}

void AIVPilotFigure::Tick(float Dt)
{
	Super::Tick(Dt);
}

void AIVPilotFigure::SetCable(const FVector& A, const FVector& B, float Sag, bool bShow)
{
	if (!Cable) return;
	if (!bShow || (B - A).SizeSquared() < 400.f) { Cable->ClearAllMeshSections(); return; }
	const int32 N = 20;
	const FVector Dir = (B - A).GetSafeNormal();
	const FVector S1 = FVector::CrossProduct(Dir, FVector::UpVector).GetSafeNormal();
	const FVector S2 = FVector::CrossProduct(Dir, S1).GetSafeNormal();
	const float W = 26.f;
	TArray<FVector> V, Nn;
	TArray<int32> Tri;
	TArray<FVector2D> UV;
	TArray<FLinearColor> C;
	TArray<FProcMeshTangent> Tg;
	for (int32 i = 0; i <= N; ++i)
	{
		const float T = float(i) / N;
		const FVector P = FMath::Lerp(A, B, T) - FVector(0, 0, Sag * 4.f * T * (1.f - T));
		for (int32 k = 0; k < 2; ++k)
		{
			const FVector Off = (k == 0 ? S1 : S2) * W;
			V.Add(P + Off); Nn.Add(S2); UV.Add(FVector2D(T, 0.f)); C.Add(FLinearColor::White);
			V.Add(P - Off); Nn.Add(S2); UV.Add(FVector2D(T, 1.f)); C.Add(FLinearColor::White);
		}
	}
	for (int32 i = 0; i < N; ++i)
		for (int32 k = 0; k < 2; ++k)
		{
			const int32 a = i * 4 + k * 2, b = a + 1, c = a + 4, d = a + 5;
			Tri.Add(a); Tri.Add(b); Tri.Add(c); Tri.Add(c); Tri.Add(b); Tri.Add(d);
			Tri.Add(a); Tri.Add(c); Tri.Add(b); Tri.Add(c); Tri.Add(d); Tri.Add(b);
		}
	Cable->CreateMeshSection_LinearColor(0, V, Tri, Nn, UV, C, Tg, false);
	if (CableMat) Cable->SetMaterial(0, CableMat);
}

void AIVPilotFigure::Present(const FIVBoardView& V, float Dt)
{
	if (!bBuilt) BuildModel();
	using P = iv::BoardPhase;
	const float U = FMath::Clamp(V.U, 0.f, 1.f);
	const float Tm = GetWorld()->GetTimeSeconds();
	FVector Pos = V.Cockpit;
	FVector LookAt = V.EnemyHatch;
	bool bCable = false;
	FVector CableA = V.OwnWrist, CableB = V.EnemyHatch;
	float Sag = 160.f;
	bool bFly = false, bGrenade = false;
	FVector GrenadePos = FVector::ZeroVector;
	float Kneel = 0.f;
	const FVector Up(0, 0, 1);
	const FVector Side = FVector::CrossProduct(V.Away, Up).GetSafeNormal();
	switch (V.Phase)
	{
	case P::ClimbOut:
		Pos = FMath::Lerp(V.Cockpit, V.OwnShoulder + Up * 140.f, Ease(U)) + Side * 160.f * FMath::Sin(U * PI * 5.f) * (1.f - U);
		LookAt = V.OwnShoulder + Up * 600.f;
		break;
	case P::OnShoulder:
		Pos = V.OwnShoulder + Up * 140.f;
		break;
	case P::HookLaunch:
		Pos = V.OwnShoulder + Up * 140.f;
		bCable = true; CableB = FMath::Lerp(V.OwnWrist, V.EnemyHatch, Ease(U)); Sag = 80.f * (1.f - U);
		break;
	case P::HookFlight:
		bCable = true; Sag = 90.f;
		Pos = FMath::Lerp(V.OwnShoulder + Up * 140.f, V.EnemyHatch + V.EnemyUp * 140.f, Ease(U)) + Up * 600.f * FMath::Sin(U * PI);
		bFly = true;
		break;
	case P::Landing:
		Pos = V.EnemyHatch + V.EnemyUp * FMath::Lerp(500.f, 120.f, Ease(U));
		bCable = true; Sag = 40.f;
		break;
	case P::Hacking:
		Pos = V.EnemyHatch + V.EnemyUp * 90.f;
		Kneel = 1.f; bCable = true; Sag = 40.f;
		break;
	case P::GrenadeThrow:
		Pos = V.EnemyHatch + V.EnemyUp * 110.f;
		Kneel = 0.4f; bCable = true; Sag = 40.f;
		bGrenade = true; GrenadePos = FMath::Lerp(Pos + Up * 360.f, V.EnemyHatch, Ease(U)) + Up * 400.f * FMath::Sin(U * PI);
		break;
	case P::Escape:
		Pos = FMath::Lerp(V.EnemyHatch + V.EnemyUp * 140.f, V.EnemyHatch + V.Away * 6500.f + Up * 3200.f, Ease(U));
		bFly = true; LookAt = V.EnemyHatch;
		break;
	case P::WatchBlast:
		Pos = V.EnemyHatch + V.Away * 6500.f + Up * (3200.f + 120.f * FMath::Sin(Tm * 1.6f));
		bFly = true; LookAt = V.EnemyHatch;
		break;
	case P::ReturnHook:
		Pos = FMath::Lerp(V.EnemyHatch + V.EnemyUp * 140.f, V.OwnShoulder + Up * 140.f, Ease(U)) + Up * 500.f * FMath::Sin(U * PI);
		bCable = true; Sag = 120.f; bFly = true; LookAt = V.OwnShoulder;
		break;
	case P::ClimbIn:
		Pos = FMath::Lerp(V.OwnShoulder + Up * 140.f, V.Cockpit, Ease(U)) + Side * 160.f * FMath::Sin(U * PI * 5.f) * (1.f - U);
		LookAt = V.Cockpit;
		break;
	case P::HookSwing:
		Pos = FMath::Lerp(V.EnemyHatch + V.EnemyUp * 140.f, V.EnemyOtherShoulder + V.EnemyUp * 140.f, Ease(U)) + Up * 1400.f * FMath::Sin(U * PI);
		bCable = true; CableA = V.EnemyHatch; CableB = Pos; Sag = 80.f; bFly = true;
		LookAt = V.EnemyOtherShoulder;
		break;
	default:
		SetActorHiddenInGame(true);
		SetCable(V.OwnWrist, V.OwnWrist, 0.f, false);
		return;
	}
	SetActorHiddenInGame(false);
	if (SuitLight) SuitLight->SetVisibility(true);
	// face the look target on the horizontal plane
	FVector Dir = (LookAt - Pos); Dir.Z = 0.f;
	if (Dir.SizeSquared() > 1.f) Facing = FMath::VInterpTo(Facing, Dir.GetSafeNormal(), Dt, 8.f);
	const FRotator Rot(bFly ? -22.f : 0.f, Facing.Rotation().Yaw, 0.f);
	SetActorLocationAndRotation(Pos, Rot);
	SetActorScale3D(FVector(1.4f, 1.4f, 1.4f * (1.f - 0.3f * Kneel)));
	if (bCable)
	{
		const FVector End = (V.Phase == P::HookFlight || V.Phase == P::ReturnHook) ? V.EnemyHatch : CableB;
		SetCable(CableA, End, Sag, true);
	}
	else SetCable(CableA, CableB, 0.f, false);
	if (Grenade)
	{
		Grenade->SetVisibility(bGrenade);
		if (bGrenade)
		{
			Grenade->SetWorldLocation(GrenadePos);
			Grenade->SetWorldScale3D(FVector(0.46f) * (1.f + 0.2f * FMath::Sin(Tm * 30.f)));
		}
	}
	PilotPos = Pos;
	HatchPos = V.EnemyHatch;
	FxAcc += Dt;
	if (bFly && FxAcc > 0.03f)
	{
		FxAcc = 0.f;
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
			FX->SpawnJet(Pos - Facing * 80.f + Up * 250.f, (-Facing + FVector(0, 0, -0.5f)).GetSafeNormal(), 2, 3500.f, 160.f);
	}
	PrevPos = Pos;
}

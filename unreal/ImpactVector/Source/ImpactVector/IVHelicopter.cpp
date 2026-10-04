#include "IVHelicopter.h"
#include "IVFXManager.h"
#include "IVAudio.h"
#include "IVMechPawn.h"
#include "ProceduralMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/AudioComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundAttenuation.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace
{
	/** Lofts an elliptical tube through stations (x, half width, half height, centre z). */
	void AddLoft(UProceduralMeshComponent* M, int32 Section, const TArray<FVector4>& St, int32 Sides)
	{
		TArray<FVector> V, N;
		TArray<int32> Tri;
		TArray<FVector2D> UV;
		TArray<FLinearColor> C;
		TArray<FProcMeshTangent> Tg;
		const int32 R = St.Num();
		for (int32 r = 0; r < R; ++r)
			for (int32 s = 0; s < Sides; ++s)
			{
				const float A = 2.f * PI * s / Sides;
				const float Ca = FMath::Cos(A), Sa = FMath::Sin(A);
				V.Add(FVector(St[r].X, Ca * St[r].Y, St[r].W + Sa * St[r].Z));
				FVector Nn(0.f, Ca / FMath::Max(St[r].Y, 1.f), Sa / FMath::Max(St[r].Z, 1.f));
				N.Add(Nn.GetSafeNormal());
				UV.Add(FVector2D(float(r) / (R - 1), float(s) / Sides));
				C.Add(FLinearColor::White);
			}
		for (int32 r = 0; r + 1 < R; ++r)
			for (int32 s = 0; s < Sides; ++s)
			{
				const int32 s1 = (s + 1) % Sides;
				const int32 a = r * Sides + s, b = r * Sides + s1, c = (r + 1) * Sides + s, d = (r + 1) * Sides + s1;
				Tri.Add(a); Tri.Add(b); Tri.Add(c);
				Tri.Add(c); Tri.Add(b); Tri.Add(d);
			}
		// caps at both ends
		for (int32 End = 0; End < 2; ++End)
		{
			const int32 Ring = End == 0 ? 0 : R - 1;
			const int32 Ctr = V.Num();
			V.Add(FVector(St[Ring].X, 0.f, St[Ring].W));
			N.Add(FVector(End == 0 ? 1.f : -1.f, 0.f, 0.f) * (St[0].X > St[R - 1].X ? 1.f : -1.f) * (End == 0 ? 1.f : -1.f));
			UV.Add(FVector2D(End, 0.5f));
			C.Add(FLinearColor::White);
			for (int32 s = 0; s < Sides; ++s) { Tri.Add(Ctr); Tri.Add(Ring * Sides + s); Tri.Add(Ring * Sides + (s + 1) % Sides); }
		}
		// front face must agree with the outward normal
		for (int32 t = 0; t + 2 < Tri.Num(); t += 3)
		{
			const FVector Cr = FVector::CrossProduct(V[Tri[t + 1]] - V[Tri[t]], V[Tri[t + 2]] - V[Tri[t]]);
			const FVector Nn = N[Tri[t]] + N[Tri[t + 1]] + N[Tri[t + 2]];
			if (FVector::DotProduct(Cr, Nn) < 0.f) Swap(Tri[t + 1], Tri[t + 2]);
		}
		M->CreateMeshSection_LinearColor(Section, V, Tri, N, UV, C, Tg, false);
	}
}

AIVHelicopter::AIVHelicopter()
{
	PrimaryActorTick.bCanEverTick = true;
	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
}

void AIVHelicopter::BeginPlay()
{
	Super::BeginPlay();
	BuildModel();
}

UStaticMeshComponent* AIVHelicopter::AddPart(UStaticMesh* Mesh, USceneComponent* Parent, const FVector& Loc, const FRotator& Rot, const FVector& Scale, UMaterialInterface* Mat)
{
	UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this);
	C->SetStaticMesh(Mesh);
	C->SetupAttachment(Parent);
	C->SetRelativeLocation(Loc);
	C->SetRelativeRotation(Rot);
	C->SetRelativeScale3D(Scale);
	C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	C->SetCastShadow(true);
	if (Mat) C->SetMaterial(0, Mat);
	C->RegisterComponent();
	Parts.Add(C);
	return C;
}

void AIVHelicopter::BuildModel()
{
	if (bBuilt) return;
	bBuilt = true;
	UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
	UStaticMesh* Cyl = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	UStaticMesh* Sph = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	UMaterialInterface* Armor = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_MechArmor.M_MechArmor"));
	UMaterialInterface* Emi = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Emissive.M_Emissive"));
	if (Armor)
	{
		HullMat = UMaterialInstanceDynamic::Create(Armor, this);
		HullMat->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.07f, 0.075f, 0.085f));
		HullMat->SetScalarParameterValue(TEXT("Metallic"), 0.85f);
		GlassMat = UMaterialInstanceDynamic::Create(Armor, this);
		GlassMat->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.012f, 0.02f, 0.035f));
		GlassMat->SetScalarParameterValue(TEXT("Metallic"), 1.f);
		GlassMat->SetScalarParameterValue(TEXT("Wear"), 0.f);
	}
	auto MakeEmi = [&](const FLinearColor& Col, float I) -> UMaterialInstanceDynamic*
	{
		if (!Emi) return nullptr;
		UMaterialInstanceDynamic* M = UMaterialInstanceDynamic::Create(Emi, this);
		M->SetVectorParameterValue(TEXT("Color"), Col);
		M->SetScalarParameterValue(TEXT("Intensity"), I);
		return M;
	};
	NavLMat = MakeEmi(FLinearColor(1.f, 0.05f, 0.03f), 14.f);
	NavRMat = MakeEmi(FLinearColor(0.1f, 1.f, 0.2f), 14.f);
	StrobeMat = MakeEmi(FLinearColor(1.f, 1.f, 1.f), 30.f);

	Hull = NewObject<USceneComponent>(this);
	Hull->SetupAttachment(RootComponent);
	Hull->RegisterComponent();

	// fuselage + tail boom + canopy as lofts (x forward, +z up; cm)
	Body = NewObject<UProceduralMeshComponent>(this);
	Body->SetupAttachment(Hull);
	Body->bUseAsyncCooking = false;
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Body->RegisterComponent();
	AddLoft(Body, 0, { FVector4(1750, 40, 40, -80), FVector4(1620, 280, 240, -60), FVector4(1250, 470, 420, 0), FVector4(650, 540, 540, 40), FVector4(0, 520, 560, 70), FVector4(-700, 440, 470, 110), FVector4(-1250, 240, 260, 160), FVector4(-1500, 120, 150, 190) }, 16);
	if (HullMat) Body->SetMaterial(0, HullMat);

	Tail = NewObject<UProceduralMeshComponent>(this);
	Tail->SetupAttachment(Hull);
	Tail->bUseAsyncCooking = false;
	Tail->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Tail->RegisterComponent();
	AddLoft(Tail, 0, { FVector4(-1400, 130, 150, 190), FVector4(-2200, 90, 110, 230), FVector4(-3000, 50, 80, 290), FVector4(-3300, 40, 60, 330) }, 10);
	if (HullMat) Tail->SetMaterial(0, HullMat);

	Canopy = NewObject<UProceduralMeshComponent>(this);
	Canopy->SetupAttachment(Hull);
	Canopy->bUseAsyncCooking = false;
	Canopy->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Canopy->RegisterComponent();
	AddLoft(Canopy, 0, { FVector4(1680, 30, 30, 20), FVector4(1500, 250, 200, 110), FVector4(1180, 430, 320, 210), FVector4(700, 470, 300, 330), FVector4(300, 400, 150, 420) }, 14);
	if (GlassMat) Canopy->SetMaterial(0, GlassMat);

	// tail fins
	AddPart(Cube, Hull, FVector(-3150, 0, 400), FRotator(0, 0, 0), FVector(3.2f, 0.18f, 3.6f), HullMat);
	AddPart(Cube, Hull, FVector(-2950, 0, 300), FRotator(0, 0, 0), FVector(2.2f, 5.2f, 0.12f), HullMat);
	// skids with struts
	for (int32 Sd = -1; Sd <= 1; Sd += 2)
	{
		AddPart(Cyl, Hull, FVector(100, Sd * 430, -600), FRotator(90, 0, 0), FVector(0.22f, 0.22f, 24.f), HullMat);
		AddPart(Cyl, Hull, FVector(650, Sd * 380, -330), FRotator(0, 0, Sd * 12), FVector(0.14f, 0.14f, 5.f), HullMat);
		AddPart(Cyl, Hull, FVector(-450, Sd * 380, -330), FRotator(0, 0, Sd * 12), FVector(0.14f, 0.14f, 5.f), HullMat);
		// weapon pods
		AddPart(Cyl, Hull, FVector(300, Sd * 780, -120), FRotator(90, 0, 0), FVector(0.55f, 0.55f, 7.f), HullMat);
		AddPart(Cube, Hull, FVector(200, Sd * 640, 120), FRotator(0, 0, 0), FVector(5.f, 3.f, 0.22f), HullMat);
	}
	// main rotor: mast + hub + 4 long blades
	AddPart(Cyl, Hull, FVector(80, 0, 680), FRotator(0, 0, 0), FVector(0.5f, 0.5f, 2.2f), HullMat);
	MainRotor = NewObject<USceneComponent>(this);
	MainRotor->SetupAttachment(Hull);
	MainRotor->SetRelativeLocation(FVector(80, 0, 800));
	MainRotor->RegisterComponent();
	AddPart(Cyl, MainRotor, FVector::ZeroVector, FRotator(0, 0, 0), FVector(1.1f, 1.1f, 0.5f), HullMat);
	for (int32 B = 0; B < 4; ++B)
	{
		UStaticMeshComponent* Bl = AddPart(Cube, MainRotor, FVector::ZeroVector, FRotator(0, 90.f * B, 0), FVector(38.f, 1.3f, 0.06f), HullMat);
		Bl->SetRelativeLocation(FRotator(0, 90.f * B, 0).RotateVector(FVector(1900, 0, 0)));
	}
	// tail rotor
	TailRotor = NewObject<USceneComponent>(this);
	TailRotor->SetupAttachment(Hull);
	TailRotor->SetRelativeLocation(FVector(-3250, 70, 330));
	TailRotor->RegisterComponent();
	for (int32 B = 0; B < 2; ++B)
	{
		UStaticMeshComponent* Bl = AddPart(Cube, TailRotor, FVector::ZeroVector, FRotator(0, 0, 90.f * B), FVector(0.1f, 0.4f, 6.f), HullMat);
		Bl->SetRelativeLocation(FRotator(0, 0, 90.f * B).RotateVector(FVector(0, 0, 300)));
	}

	// navigation lights
	NavLMesh = AddPart(Sph, Hull, FVector(150, -800, -120), FRotator::ZeroRotator, FVector(0.5f), NavLMat);
	NavRMesh = AddPart(Sph, Hull, FVector(150, 800, -120), FRotator::ZeroRotator, FVector(0.5f), NavRMat);
	StrobeMesh = AddPart(Sph, Hull, FVector(-3300, 0, 700), FRotator::ZeroRotator, FVector(0.5f), StrobeMat);
	auto MakeLamp = [&](const FLinearColor& Col, const FVector& Loc) -> UPointLightComponent*
	{
		UPointLightComponent* L = NewObject<UPointLightComponent>(this);
		L->SetupAttachment(Hull);
		L->SetRelativeLocation(Loc);
		L->SetIntensityUnits(ELightUnits::Candelas);
		L->SetIntensity(2.0e4f);
		L->SetLightColor(Col);
		L->SetAttenuationRadius(5000.f);
		L->SetCastShadows(false);
		L->RegisterComponent();
		return L;
	};
	NavL = MakeLamp(FLinearColor(1.f, 0.1f, 0.05f), FVector(150, -900, -120));
	NavR = MakeLamp(FLinearColor(0.15f, 1.f, 0.3f), FVector(150, 900, -120));
	Strobe = MakeLamp(FLinearColor::White, FVector(-3300, 0, 760));
	Strobe->SetIntensity(0.f);

	// the searchlight
	Search = NewObject<USpotLightComponent>(this);
	Search->SetupAttachment(Hull);
	Search->SetRelativeLocation(FVector(1400, 0, -380));
	Search->SetIntensityUnits(ELightUnits::Candelas);
	Search->SetIntensity(3.5e5f);
	Search->SetLightColor(FLinearColor(0.85f, 0.93f, 1.f));
	Search->SetAttenuationRadius(60000.f);
	Search->SetInnerConeAngle(3.5f);
	Search->SetOuterConeAngle(9.f);
	Search->SetSourceRadius(60.f);
	Search->SetCastShadows(true);
	Search->SetVolumetricScatteringIntensity(1.6f);
	Search->RegisterComponent();

	// rotor sound, audible within a few hundred metres
	if (USoundBase* Snd = IVAudio::Get(TEXT("env_heli_rotor_loop")))
	{
		USoundAttenuation* At = NewObject<USoundAttenuation>(this);
		At->Attenuation.bAttenuate = true;
		At->Attenuation.bSpatialize = true;
		At->Attenuation.AttenuationShape = EAttenuationShape::Sphere;
		At->Attenuation.AttenuationShapeExtents = FVector(6000.f);
		At->Attenuation.FalloffDistance = 40000.f;
		RotorSound = UGameplayStatics::SpawnSoundAttached(Snd, Hull, NAME_None, FVector::ZeroVector, EAttachLocation::KeepRelativeOffset, false, 0.5f, 1.f, FMath::FRand() * 2.f, At);
	}
}

void AIVHelicopter::SpawnFleet(UWorld* World, const FVector& ArenaCenter, int32 Count)
{
	if (!World) return;
	for (int32 i = 0; i < Count; ++i)
	{
		FActorSpawnParameters Sp;
		Sp.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		AIVHelicopter* H = World->SpawnActor<AIVHelicopter>(ArenaCenter, FRotator::ZeroRotator, Sp);
		if (!H) continue;
		H->Center = ArenaCenter;
		H->Phase = 2.f * PI * (float(i) / Count) + 0.7f;
		H->bClockwise = (i % 2) == 0;
		H->Radius = 17500.f + 4500.f * i;
		H->Altitude = 10500.f + 2200.f * i;
		H->LowTimer = 14.f + 16.f * i;
		if (FParse::Param(FCommandLine::Get(), TEXT("IVHeliLow"))) H->LowTimer = 0.5f + 8.f * i;
	}
}

void AIVHelicopter::SetFleetSize(UWorld* World, int32 Count)
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

void AIVHelicopter::UpdateAim(float Dt)
{
	// who is on the ground below
	TArray<AIVMechPawn*> Mechs;
	for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It) Mechs.Add(*It);
	AimTimer -= Dt;
	if (AimTimer <= 0.f)
	{
		AimTimer = FMath::RandRange(3.f, 6.f);
		AimMode = float(FMath::RandRange(0, 2));
	}
	FVector Want = Center;
	if (Mechs.Num() > 0)
	{
		FVector Mid = FVector::ZeroVector;
		for (AIVMechPawn* M : Mechs) Mid += M->GetActorLocation();
		Mid /= Mechs.Num();
		Center = FMath::VInterpTo(Center, FVector(Mid.X, Mid.Y, 0.f), Dt, 0.6f);
		if (AimMode < 1.f) Want = Mechs[0]->GetZoneWorldLocation(iv::Zone::Torso);
		else if (AimMode < 2.f) Want = Mechs.Num() > 1 ? Mechs[1]->GetZoneWorldLocation(iv::Zone::Torso) : Mid;
		else Want = FVector(Mid.X + 9000.f * FMath::Cos(Time * 0.6f), Mid.Y + 9000.f * FMath::Sin(Time * 0.45f), 0.f);
	}
	AimPoint = FMath::VInterpTo(AimPoint.IsNearlyZero() ? Want : AimPoint, Want, Dt, 1.6f);
}

void AIVHelicopter::TickPatrol(float Dt)
{
	// low passes
	if (LowLeft > 0.f) LowLeft -= Dt;
	else
	{
		LowTimer -= Dt;
		if (LowTimer <= 0.f) { LowLeft = 11.f; LowTimer = FMath::RandRange(24.f, 40.f); }
	}
	LowFactor = FMath::FInterpConstantTo(LowFactor, LowLeft > 0.f ? 1.f : 0.f, Dt, 0.22f);
	const float R = FMath::Lerp(Radius, 9800.f, LowFactor);
	const float Alt = FMath::Lerp(Altitude, 5200.f, LowFactor) + 220.f * FMath::Sin(Time * 0.9f + Phase);
	const float Spd = FMath::Lerp(4300.f, 3200.f, LowFactor);
	const float Dir = bClockwise ? -1.f : 1.f;
	Phase += Dir * Spd / R * Dt;
	const FVector Pos = Center + FVector(FMath::Cos(Phase) * R, FMath::Sin(Phase) * R, Alt);
	const FVector Tan = FVector(-FMath::Sin(Phase), FMath::Cos(Phase), 0.f) * Dir;
	SetActorLocationAndRotation(Pos, FRotator(0.f, Tan.Rotation().Yaw, 0.f));
	const float WantBank = -13.f * Dir;
	Bank = FMath::FInterpTo(Bank, WantBank, Dt, 1.2f);
	Pitch = FMath::FInterpTo(Pitch, -4.f - 3.f * LowFactor, Dt, 1.f);
	Hull->SetRelativeRotation(FRotator(Pitch + 1.2f * FMath::Sin(Time * 1.7f + Phase), 0.f, Bank + 1.5f * FMath::Sin(Time * 1.3f)));
	UpdateAim(Dt);
}

void AIVHelicopter::GrabAndThrow(TWeakObjectPtr<AActor> InHolder, TWeakObjectPtr<AActor> InTarget, float HoldTime, float Duration, TFunction<void(const FVector&)> InOnImpact)
{
	State = EIVHeliState::Grabbed;
	Holder = InHolder; Target = InTarget;
	HoldT = HoldTime; ThrowDur = Duration;
	OnImpact = MoveTemp(InOnImpact);
	Tumble = GetActorRotation();
	TumbleRate = FRotator(FMath::RandRange(-120.f, 120.f), FMath::RandRange(-200.f, 200.f), FMath::RandRange(300.f, 560.f));
	if (RotorSound) RotorSound->SetPitchMultiplier(0.8f);
	IVAudio::Play3D(GetWorld(), TEXT("hit_lowfreq_thump_heavy"), GetActorLocation(), 1.f);
	IVAudio::Play3D(GetWorld(), TEXT("block_impact"), GetActorLocation(), 1.f);
}

void AIVHelicopter::TickHeld(float Dt)
{
	HoldT -= Dt;
	FVector P = GetActorLocation();
	if (AIVMechPawn* M = Cast<AIVMechPawn>(Holder.Get()))
		P = FMath::VInterpTo(P, M->GetZoneWorldLocation(iv::Zone::ArmR) + M->GetActorForwardVector() * 1800.f + FVector(0, 0, 1200.f), Dt, 9.f);
	Tumble += TumbleRate * Dt * 0.3f;
	SetActorLocationAndRotation(P, Tumble);
	FxAcc += Dt;
	if (FxAcc > 0.05f)
	{
		FxAcc = 0.f;
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) { FX->SpawnSparks(P, FVector::UpVector, 5, 3500.f); FX->SpawnSmoke(P - FVector(1500, 0, 0), 200.f, 1, 0.5f); }
	}
	if (HoldT <= 0.f)
	{
		State = EIVHeliState::Thrown;
		ThrowT = 0.f;
		ThrowStart = GetActorLocation();
		if (AActor* T = Target.Get())
			LastTarget = T->GetActorLocation();
	}
}

void AIVHelicopter::TickThrown(float Dt)
{
	ThrowT += Dt;
	if (AActor* T = Target.Get())
	{
		if (AIVMechPawn* M = Cast<AIVMechPawn>(T)) LastTarget = M->GetZoneWorldLocation(iv::Zone::Head);
		else LastTarget = T->GetActorLocation();
	}
	const float U = FMath::Clamp(ThrowT / ThrowDur, 0.f, 1.f);
	const float Ease = U * U * (3.f - 2.f * U) * 0.3f + U * 0.7f;
	const FVector P = FMath::Lerp(ThrowStart, LastTarget, Ease) + FVector(0, 0, 3200.f * 4.f * U * (1.f - U));
	Tumble += TumbleRate * Dt;
	SetActorLocationAndRotation(P, Tumble);
	FxAcc += Dt;
	if (FxAcc > 0.03f)
	{
		FxAcc = 0.f;
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
		{
			FX->SpawnFlame(P - GetActorForwardVector() * 1600.f, 260.f, 2, 1.2f);
			FX->SpawnSmoke(P - GetActorForwardVector() * 2000.f, 300.f, 1, 0.8f);
			if (FMath::FRand() < 0.4f) FX->SpawnSparks(P, FVector::UpVector, 6, 4500.f);
		}
	}
	if (U >= 1.f) Blow(P);
}

void AIVHelicopter::Blow(const FVector& At)
{
	if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
	{
		FX->SpawnExplosion(At, 3.2f);
		FX->SpawnChunks(At, FVector(0, 0, 1), 26, EIVChunk::Steel, 3.6f, 6500.f, 1.f, 1.4f);
		FX->SpawnChunks(At, FVector(0, 0, 1), 14, EIVChunk::Armor, 4.4f, 5200.f, 1.f, 1.4f);
		FX->SpawnChunks(At, FVector(0, 0, 1), 18, EIVChunk::Glass, 4.f, 6000.f, 0.f, 1.5f);
		FX->SpawnFlash(At, FLinearColor(1.f, 0.6f, 0.25f), 6.0e5f, 0.7f, 22000.f);
	}
	IVAudio::Play3D(GetWorld(), TEXT("env_distant_boom_01"), At, 1.f);
	IVAudio::Play3D(GetWorld(), TEXT("hit_lowfreq_thump_heavy"), At, 1.f);
	if (OnImpact) OnImpact(At);
	State = EIVHeliState::Wreck;
	Destroy();
}

void AIVHelicopter::Tick(float Dt)
{
	Super::Tick(Dt);
	if (!bBuilt) return;
	Dt = FMath::Min(Dt, 0.05f);
	Time += Dt;
	switch (State)
	{
	case EIVHeliState::Patrol: TickPatrol(Dt); break;
	case EIVHeliState::Grabbed: TickHeld(Dt); break;
	case EIVHeliState::Thrown: TickThrown(Dt); break;
	default: break;
	}
	// rotors
	const float Rpm = State == EIVHeliState::Patrol ? 1.f : 0.45f;
	BladeYaw = FMath::Fmod(BladeYaw + 1500.f * Rpm * Dt, 360.f);
	TailYaw = FMath::Fmod(TailYaw + 2400.f * Rpm * Dt, 360.f);
	if (MainRotor) MainRotor->SetRelativeRotation(FRotator(0.f, BladeYaw, 0.f));
	if (TailRotor) TailRotor->SetRelativeRotation(FRotator(0.f, 0.f, TailYaw));
	// lights
	const bool bStrobe = FMath::Frac(Time * 0.9f) < 0.08f;
	if (Strobe) Strobe->SetIntensity(bStrobe ? 6.0e5f : 0.f);
	if (StrobeMat) StrobeMat->SetScalarParameterValue(TEXT("Intensity"), bStrobe ? 400.f : 2.f);
	const bool bBlink = FMath::Frac(Time * 0.5f + Phase) < 0.5f;
	if (NavL) NavL->SetIntensity(bBlink ? 3.0e4f : 1.0e4f);
	if (NavR) NavR->SetIntensity(bBlink ? 3.0e4f : 1.0e4f);
	if (Search)
	{
		const FVector From = Search->GetComponentLocation();
		FVector Aim = AimPoint.IsNearlyZero() ? From + GetActorForwardVector() * 4000.f - FVector(0, 0, 3000.f) : AimPoint;
		if (State != EIVHeliState::Patrol)
		{
			// the searchlight tumbles with the wreck and flickers out
			Search->SetIntensity(2.2e5f * (0.5f + 0.5f * FMath::Sin(Time * 40.f)));
			Aim = From + GetActorForwardVector() * 3000.f;
		}
		Search->SetWorldRotation((Aim - From).GetSafeNormal().Rotation());
	}
}

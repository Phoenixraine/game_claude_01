#include "IVAbilities.h"
#include "IVFXManager.h"
#include "IVAudio.h"
#include "IVMechPawn.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "UObject/ConstructorHelpers.h"
#include "Math/RandomStream.h"

AIVThrownDebris::AIVThrownDebris()
{
	PrimaryActorTick.bCanEverTick = true;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	Chunks = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Chunks"));
	RootComponent = Chunks;
	if (Cube.Succeeded()) Chunks->SetStaticMesh(Cube.Object);
	Chunks->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Chunks->SetCastShadow(true);
	Chunks->SetBoundsScale(6.f);
}

void AIVThrownDebris::Launch(const FVector& InStart, TWeakObjectPtr<AActor> InFollow, const FVector& InTargetFallback, float InDuration, float Scale, TFunction<void(const FVector&)> InOnImpact)
{
	Start = InStart;
	Follow = InFollow;
	TargetFallback = InTargetFallback;
	LastTarget = InTargetFallback;
	Duration = FMath::Max(InDuration, 0.2f);
	OnImpact = MoveTemp(InOnImpact);
	FRandomStream R(int32(InStart.X) ^ int32(InStart.Y));
	Spin = FVector(R.FRandRange(-60.f, 60.f), R.FRandRange(-120.f, 120.f), R.FRandRange(-80.f, 80.f));
	Arc = 3500.f + 1500.f * R.FRand();
	// a slab broken out of a facade: many chunks of a similar grey
	if (UMaterialInterface* M = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_BuildingFacade.M_BuildingFacade")))
	{
		UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(M, this);
		MID->SetVectorParameterValue(TEXT("Tint"), FLinearColor(0.16f, 0.16f, 0.17f));
		MID->SetVectorParameterValue(TEXT("GlassColor"), FLinearColor(0.02f, 0.03f, 0.04f));
		MID->SetScalarParameterValue(TEXT("LitAmount"), 0.f);
		Chunks->SetMaterial(0, MID);
	}
	TArray<FTransform> Tr;
	for (int32 i = 0; i < 26; ++i)
	{
		const FVector P(R.FRandRange(-1700.f, 1700.f), R.FRandRange(-1700.f, 1700.f), R.FRandRange(-900.f, 900.f));
		const FVector S = FVector(R.FRandRange(0.6f, 2.6f), R.FRandRange(0.6f, 2.6f), R.FRandRange(0.4f, 1.6f)) * Scale;
		Tr.Add(FTransform(FRotator(R.FRandRange(-30.f, 30.f), R.FRandRange(0.f, 360.f), R.FRandRange(-30.f, 30.f)), P * Scale, S));
	}
	Chunks->AddInstances(Tr, false);
	SetActorLocation(Start);
}

void AIVThrownDebris::Tick(float Dt)
{
	Super::Tick(Dt);
	T += Dt;
	if (AActor* F = Follow.Get())
	{
		if (AIVMechPawn* M = Cast<AIVMechPawn>(F)) LastTarget = M->GetZoneWorldLocation(iv::Zone::Head);
		else LastTarget = F->GetActorLocation();
	}
	const float U = FMath::Clamp(T / Duration, 0.f, 1.f);
	const float Ease = U * U * (3.f - 2.f * U) * 0.35f + U * 0.65f;
	FVector P = FMath::Lerp(Start, LastTarget, Ease) + FVector(0, 0, Arc * 4.f * U * (1.f - U));
	SetActorLocation(P);
	Rot += FRotator(Spin.X, Spin.Y, Spin.Z) * Dt;
	SetActorRotation(Rot);
	DustAcc += Dt;
	if (DustAcc > 0.06f)
	{
		DustAcc = 0.f;
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) FX->SpawnDust(P, 1400.f, 2, 0.5f);
	}
	if (U >= 1.f)
	{
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
		{
			FX->SpawnSparks(P, FVector::UpVector, 120, 7000.f);
			FX->SpawnDust(P, 3200.f, 36, 1.6f);
		}
		IVAudio::Play3D(GetWorld(), TEXT("env_concrete_crumble"), P, 1.f);
		IVAudio::Play3D(GetWorld(), TEXT("hit_lowfreq_thump_heavy"), P, 1.f);
		if (OnImpact) OnImpact(P);
		Destroy();
	}
}

// =====================================================================================================================
#include "ProceduralMeshComponent.h"
#include "Kismet/GameplayStatics.h"

AIVProjectile::AIVProjectile()
{
	PrimaryActorTick.bCanEverTick = true;
	Beam = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("Beam"));
	RootComponent = Beam;
	Beam->SetUsingAbsoluteLocation(true);
	Beam->SetUsingAbsoluteRotation(true);
	Beam->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Beam->SetCastShadow(false);
	Beam->bUseAsyncCooking = false;
}

void AIVProjectile::Launch(int32 InKind, const FVector& InFrom, TWeakObjectPtr<AActor> InTarget, bool bInHit, float InDuration)
{
	Kind = InKind; From = InFrom; Target = InTarget; bHit = bInHit; Duration = FMath::Max(InDuration, 0.15f);
	UpdateTarget();
	if (Kind == 0)
	{
		if (UMaterialInterface* M = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_BladeTrail.M_BladeTrail")))
		{
			BeamMID = UMaterialInstanceDynamic::Create(M, this);
			BeamMID->SetVectorParameterValue(TEXT("EdgeColor"), FLinearColor(0.5f, 1.6f, 3.4f));
			BeamMID->SetScalarParameterValue(TEXT("Gain"), 6.f);
			Beam->SetMaterial(0, BeamMID);
		}
		IVAudio::Play3D(GetWorld(), TEXT("mech_weapon_fire"), From, 1.f);
	}
	else if (Kind == 1)
	{
		FRandomStream R(int32(From.X) + 7);
		for (int32 i = 0; i < 6; ++i)
		{
			FRocket Rk;
			Rk.Side = FVector(R.FRandRange(-1.f, 1.f), R.FRandRange(-1.f, 1.f), R.FRandRange(0.2f, 1.f)).GetSafeNormal() * R.FRandRange(1500.f, 4200.f);
			Rk.Delay = float(i) * 0.07f;
			Rk.Wob = float(R.FRandRange(0.f, 6.28f));
			Rockets.Add(Rk);
		}
	}
}

void AIVProjectile::UpdateTarget()
{
	if (AActor* A = Target.Get())
	{
		if (AIVMechPawn* M = Cast<AIVMechPawn>(A)) To = M->GetZoneWorldLocation(iv::Zone::Torso);
		else To = A->GetActorLocation();
		if (!bHit) To += FVector(0, 0, 0) + FVector::CrossProduct((To - From).GetSafeNormal(), FVector::UpVector) * 4200.f;
	}
}

void AIVProjectile::Tick(float Dt)
{
	Super::Tick(Dt);
	T += Dt;
	UpdateTarget();
	AIVFXManager* FX = AIVFXManager::Get(GetWorld());
	if (!FX) { Destroy(); return; }
	const float U = FMath::Clamp(T / Duration, 0.f, 1.f);
	if (Kind == 0)
	{
		// a lance of light along the line, fading out; impact at once
		const FVector Dir = (To - From).GetSafeNormal();
		const float Fade = FMath::Clamp(1.f - T / Duration, 0.f, 1.f);
		const FVector Up = FVector::CrossProduct(Dir, FVector::UpVector).GetSafeNormal();
		const FVector Up2 = FVector::CrossProduct(Dir, Up).GetSafeNormal();
		const float W = 280.f * (0.4f + 0.6f * Fade);
		TArray<FVector> V; TArray<int32> Tri; TArray<FVector> N; TArray<FVector2D> UV; TArray<FLinearColor> C; TArray<FProcMeshTangent> Tg;
		const int32 Seg = 10;
		for (int32 i = 0; i <= Seg; ++i)
		{
			const FVector P = FMath::Lerp(From, To, float(i) / Seg);
			for (int32 k = 0; k < 2; ++k)
			{
				const FVector Off = (k == 0 ? Up : Up2) * W;
				V.Add(P + Off); UV.Add(FVector2D(float(i) / Seg, 0.f)); C.Add(FLinearColor(1, 1, 1, Fade)); N.Add(Dir);
				V.Add(P - Off); UV.Add(FVector2D(float(i) / Seg, 1.f)); C.Add(FLinearColor(1, 1, 1, Fade)); N.Add(Dir);
			}
		}
		for (int32 i = 0; i < Seg; ++i)
			for (int32 k = 0; k < 2; ++k)
			{
				const int32 a = i * 4 + k * 2, b = a + 1, c = a + 4, d = a + 5;
				Tri.Add(a); Tri.Add(b); Tri.Add(c); Tri.Add(c); Tri.Add(b); Tri.Add(d);
				Tri.Add(a); Tri.Add(c); Tri.Add(b); Tri.Add(c); Tri.Add(d); Tri.Add(b);
			}
		Beam->CreateMeshSection_LinearColor(0, V, Tri, N, UV, C, Tg, false);
		if (BeamMID) Beam->SetMaterial(0, BeamMID);
		if (!bDone)
		{
			bDone = true;
			FX->SpawnFlash(To, FLinearColor(0.5f, 0.85f, 1.f), 4.0e5f, 0.35f, 16000.f);
			FX->SpawnSparks(To, -Dir, bHit ? 220 : 80, 9000.f);
			if (bHit) FX->SpawnExplosion(To, 1.4f);
			for (int32 i = 0; i < 30; ++i) FX->SpawnSparks(FMath::Lerp(From, To, i / 29.f), Up, 3, 2500.f);
		}
		if (T > Duration) Destroy();
	}
	else if (Kind == 1)
	{
		int32 Alive = 0;
		for (const FRocket& R : Rockets)
		{
			const float Ur = FMath::Clamp((T - R.Delay) / (Duration * 0.8f), 0.f, 1.f);
			if (T < R.Delay) { ++Alive; continue; }
			if (Ur >= 1.f) continue;
			++Alive;
			const FVector Mid = (From + To) * 0.5f + R.Side;
			const FVector P = FMath::Lerp(FMath::Lerp(From, Mid, Ur), FMath::Lerp(Mid, To, Ur), Ur) + FVector(0, 0, 250.f * FMath::Sin(R.Wob + T * 20.f));
			FX->SpawnFlame(P, 120.f, 1, 0.9f);
			FX->SpawnSmoke(P, 100.f, 1, 0.5f);
			if (Ur > 0.985f) {}
		}
		// detonations when each rocket arrives
		static_cast<void>(U);
		if (T > Duration * 0.8f + 0.5f && !bDone)
		{
			bDone = true;
			for (int32 i = 0; i < 6; ++i)
				FX->SpawnExplosion(To + FVector(FMath::RandRange(-1500.f, 1500.f), FMath::RandRange(-1500.f, 1500.f), FMath::RandRange(-2200.f, 1800.f)), bHit ? 0.8f : 0.4f);
		}
		if (Alive == 0 || T > Duration + 1.2f) Destroy();
	}
	else
	{
		const FVector P = FMath::Lerp(From, To, U * U * 0.3f + U * 0.7f);
		FX->SpawnFlame(P, 400.f, 4, 1.8f);
		if (FMath::FRand() < 0.5f) FX->SpawnSparks(P, FVector::UpVector, 6, 3000.f);
		FX->SpawnFlash(P, FLinearColor(1.f, 0.35f, 0.5f), 1.0e5f, 0.05f, 14000.f);
		if (U >= 1.f)
		{
			FX->SpawnExplosion(To, bHit ? 2.6f : 1.4f);
			Destroy();
		}
	}
}

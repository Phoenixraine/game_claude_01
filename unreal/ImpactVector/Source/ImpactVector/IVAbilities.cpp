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

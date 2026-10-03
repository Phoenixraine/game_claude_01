#include "IVFXManager.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"
#include "Camera/PlayerCameraManager.h"

AIVFXManager::AIVFXManager()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostUpdateWork;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> PlaneF(TEXT("/Engine/BasicShapes/Plane.Plane"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeF(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> PuffM(TEXT("/Game/Materials/M_Puff.M_Puff"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> SparkM(TEXT("/Game/Materials/M_Spark.M_Spark"));

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

	PuffISM = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Puffs"));
	PuffISM->SetupAttachment(Root);
	PuffISM->SetStaticMesh(PlaneF.Object);
	if (PuffM.Succeeded()) PuffISM->SetMaterial(0, PuffM.Object);
	PuffISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	PuffISM->SetCastShadow(false);
	PuffISM->NumCustomDataFloats = 2;           // [age01, seed]
	PuffISM->SetCanEverAffectNavigation(false);
	PuffISM->bUseAsOccluder = false;
	PuffISM->SetCullDistances(0, 0);

	SparkISM = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Sparks"));
	SparkISM->SetupAttachment(Root);
	SparkISM->SetStaticMesh(CubeF.Object);
	if (SparkM.Succeeded()) SparkISM->SetMaterial(0, SparkM.Object);
	SparkISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SparkISM->SetCastShadow(false);
}

AIVFXManager* AIVFXManager::Get(UWorld* World)
{
	if (!World) return nullptr;
	for (TActorIterator<AIVFXManager> It(World); It; ++It) return *It;
	return World->SpawnActor<AIVFXManager>(FVector::ZeroVector, FRotator::ZeroRotator);
}

void AIVFXManager::SpawnDust(const FVector& Center, float Radius, int32 Count, float Strength)
{
	for (int32 i = 0; i < Count && Puffs.Num() < MaxPuffs; ++i)
	{
		FIVPuff P;
		const FVector Dir = Rng.VRand();
		P.Pos = Center + Dir * Radius * Rng.FRand() * 0.7f + FVector(0, 0, Rng.FRandRange(0.f, Radius * 0.3f));
		P.Vel = FVector(Dir.X, Dir.Y, FMath::Abs(Dir.Z) * 0.6f + 0.15f) * Rng.FRandRange(300.f, 1400.f) * Strength;
		P.Life = Rng.FRandRange(5.f, 11.f);
		P.Size0 = Rng.FRandRange(400.f, 900.f) * (0.6f + 0.4f * Strength);
		P.Size1 = P.Size0 * Rng.FRandRange(3.5f, 6.5f);
		P.Roll = Rng.FRandRange(0.f, 360.f);
		P.RollRate = Rng.FRandRange(-12.f, 12.f);
		P.Drag = Rng.FRandRange(0.5f, 1.1f);
		P.Rise = Rng.FRandRange(10.f, 90.f);
		P.Opacity = Rng.FRandRange(0.35f, 0.7f);
		P.Seed = Rng.FRand();
		Puffs.Add(P);
	}
}

void AIVFXManager::SpawnSparks(const FVector& Center, const FVector& Normal, int32 Count, float Speed)
{
	for (int32 i = 0; i < Count && Sparks.Num() < MaxSparks; ++i)
	{
		FIVSpark S;
		S.Pos = Center;
		const FVector Dir = (Normal + Rng.VRand() * 0.9f).GetSafeNormal();
		S.Vel = Dir * Speed * Rng.FRandRange(0.3f, 1.f);
		S.Life = Rng.FRandRange(0.4f, 1.2f);
		S.Len = Rng.FRandRange(60.f, 220.f);
		Sparks.Add(S);
	}
}

void AIVFXManager::Tick(float Dt)
{
	Super::Tick(Dt);
	Dt = FMath::Min(Dt, 0.05f);

	FVector CamPos = FVector::ZeroVector;
	if (APlayerCameraManager* Cam = UGameplayStatics::GetPlayerCameraManager(this, 0)) CamPos = Cam->GetCameraLocation();

	// ---- puffs: integrate, cull, billboard
	for (int32 i = Puffs.Num() - 1; i >= 0; --i)
	{
		FIVPuff& P = Puffs[i];
		P.Age += Dt;
		if (P.Age >= P.Life) { Puffs.RemoveAtSwap(i); continue; }
		P.Vel *= FMath::Exp(-P.Drag * Dt);
		P.Vel.Z += P.Rise * Dt;
		P.Pos += P.Vel * Dt;
		P.Roll += P.RollRate * Dt;
	}
	{
		TArray<FTransform> T;
		T.Reserve(Puffs.Num());
		TArray<float> Custom;
		Custom.Reserve(Puffs.Num() * 2);
		for (const FIVPuff& P : Puffs)
		{
			const float A = P.Age / P.Life;
			const float Size = FMath::Lerp(P.Size0, P.Size1, 1.f - FMath::Square(1.f - FMath::Min(A * 1.6f, 1.f)));
			FVector ToCam = (CamPos - P.Pos);
			if (!ToCam.Normalize()) ToCam = FVector::UpVector;
			FQuat Q = FQuat::FindBetweenNormals(FVector::UpVector, ToCam) * FQuat(FVector::UpVector, FMath::DegreesToRadians(P.Roll));
			T.Add(FTransform(Q, P.Pos, FVector(Size / 100.f)));
			Custom.Add(A);                        // x: age01
			Custom.Add(P.Seed);
		}
		if (PuffISM->GetInstanceCount() != T.Num())
		{
			PuffISM->ClearInstances();
			PuffISM->NumCustomDataFloats = 2;
			PuffISM->AddInstances(T, false, true);
		}
		else if (T.Num() > 0)
		{
			PuffISM->BatchUpdateInstancesTransforms(0, T, true, true, true);
		}
		for (int32 i = 0; i < T.Num(); ++i)
		{
			PuffISM->SetCustomDataValue(i, 0, Custom[i * 2], false);
			PuffISM->SetCustomDataValue(i, 1, Custom[i * 2 + 1], i == T.Num() - 1);
		}
	}

	// ---- sparks
	for (int32 i = Sparks.Num() - 1; i >= 0; --i)
	{
		FIVSpark& S = Sparks[i];
		S.Age += Dt;
		if (S.Age >= S.Life) { Sparks.RemoveAtSwap(i); continue; }
		S.Vel.Z -= 2400.f * Dt;
		S.Vel *= FMath::Exp(-0.5f * Dt);
		S.Pos += S.Vel * Dt;
	}
	{
		TArray<FTransform> T;
		T.Reserve(Sparks.Num());
		for (const FIVSpark& S : Sparks)
		{
			const FVector Dir = S.Vel.GetSafeNormal();
			const float Fade = 1.f - S.Age / S.Life;
			T.Add(FTransform(FRotationMatrix::MakeFromX(Dir).ToQuat(), S.Pos, FVector(S.Len / 100.f, 0.035f, 0.035f) * (0.4f + 0.6f * Fade)));
		}
		if (SparkISM->GetInstanceCount() != T.Num())
		{
			SparkISM->ClearInstances();
			SparkISM->AddInstances(T, false, true);
		}
		else if (T.Num() > 0)
		{
			SparkISM->BatchUpdateInstancesTransforms(0, T, true, true, true);
		}
	}
}

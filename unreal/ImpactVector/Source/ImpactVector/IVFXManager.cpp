#include "IVFXManager.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/PointLightComponent.h"

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
	PuffISM->NumCustomDataFloats = 3;           // [age01, seed, dark]
	PuffISM->SetCanEverAffectNavigation(false);
	PuffISM->bUseAsOccluder = false;
	PuffISM->SetCullDistances(0, 0);

	{
		static ConstructorHelpers::FObjectFinder<UMaterialInterface> FireM(TEXT("/Game/Materials/M_Fire.M_Fire"));
		FireISM = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Flames"));
		FireISM->SetupAttachment(Root);
		FireISM->SetStaticMesh(PlaneF.Object);
		if (FireM.Succeeded()) FireISM->SetMaterial(0, FireM.Object);
		FireISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		FireISM->SetCastShadow(false);
		FireISM->NumCustomDataFloats = 3;       // [age01, seed, heat]
		FireISM->SetCanEverAffectNavigation(false);
		FireISM->bUseAsOccluder = false;
		FireISM->SetCullDistances(0, 0);
		for (int32 i = 0; i < 5; ++i)
		{
			UPointLightComponent* L = CreateDefaultSubobject<UPointLightComponent>(*FString::Printf(TEXT("Flash%d"), i));
			L->SetupAttachment(Root);
			L->SetIntensityUnits(ELightUnits::Candelas);
			L->SetIntensity(0.f);
			L->SetCastShadows(false);
			L->SetSourceRadius(200.f);
			L->SetLightingChannels(true, false, false);
			FlashLights.Add(L);
		}
	}

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
		Custom.Reserve(Puffs.Num() * 3);
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
			Custom.Add(P.Dark);
		}
		if (PuffISM->GetInstanceCount() != T.Num())
		{
			PuffISM->ClearInstances();
			PuffISM->NumCustomDataFloats = 3;
			PuffISM->AddInstances(T, false, true);
		}
		else if (T.Num() > 0)
		{
			PuffISM->BatchUpdateInstancesTransforms(0, T, true, true, true);
		}
		for (int32 i = 0; i < T.Num(); ++i)
		{
			PuffISM->SetCustomDataValue(i, 0, Custom[i * 3], false);
			PuffISM->SetCustomDataValue(i, 1, Custom[i * 3 + 1], false);
			PuffISM->SetCustomDataValue(i, 2, Custom[i * 3 + 2], i == T.Num() - 1);
		}
	}

	// ---- flames
	for (int32 i = Flames.Num() - 1; i >= 0; --i)
	{
		FIVFlame& F = Flames[i];
		F.Age += Dt;
		if (F.Age >= F.Life) { Flames.RemoveAtSwap(i); continue; }
		F.Vel *= FMath::Exp(-1.4f * Dt);
		F.Vel.Z += F.Rise * Dt;
		F.Pos += F.Vel * Dt;
	}
	{
		TArray<FTransform> T;
		T.Reserve(Flames.Num());
		for (const FIVFlame& F : Flames)
		{
			const float A = F.Age / F.Life;
			const float Size = FMath::Lerp(F.Size0, F.Size1, FMath::Sqrt(A));
			FVector ToCam = (CamPos - F.Pos);
			if (!ToCam.Normalize()) ToCam = FVector::UpVector;
			const FQuat Q = FQuat::FindBetweenNormals(FVector::UpVector, ToCam) * FQuat(FVector::UpVector, FMath::DegreesToRadians(F.Roll));
			T.Add(FTransform(Q, F.Pos, FVector(Size / 100.f)));
		}
		if (FireISM->GetInstanceCount() != T.Num())
		{
			FireISM->ClearInstances();
			FireISM->NumCustomDataFloats = 3;
			FireISM->AddInstances(T, false, true);
		}
		else if (T.Num() > 0)
		{
			FireISM->BatchUpdateInstancesTransforms(0, T, true, true, true);
		}
		for (int32 i = 0; i < T.Num(); ++i)
		{
			const FIVFlame& F = Flames[i];
			FireISM->SetCustomDataValue(i, 0, F.Age / F.Life, false);
			FireISM->SetCustomDataValue(i, 1, F.Seed, false);
			FireISM->SetCustomDataValue(i, 2, F.Heat, i == T.Num() - 1);
		}
	}
	// ---- light flashes
	for (int32 i = 0; i < 5; ++i)
	{
		FIVFlash& Fl = Flashes[i];
		UPointLightComponent* L = FlashLights[i];
		if (Fl.Age >= Fl.Life) { if (L->Intensity != 0.f) L->SetIntensity(0.f); continue; }
		Fl.Age += Dt;
		const float K = FMath::Max(0.f, 1.f - Fl.Age / Fl.Life);
		L->SetWorldLocation(Fl.Pos);
		L->SetLightColor(Fl.Color);
		L->SetAttenuationRadius(Fl.Radius);
		L->SetIntensity(Fl.Intensity * K * K);
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

void AIVFXManager::SpawnSmoke(const FVector& Center, float Radius, int32 Count, float Strength)
{
	for (int32 i = 0; i < Count && Puffs.Num() < MaxPuffs; ++i)
	{
		FIVPuff P;
		P.Dark = Rng.FRandRange(0.65f, 1.f);
		P.Pos = Center + Rng.VRand() * Radius * 0.4f;
		P.Vel = FVector(Rng.FRandRange(-250.f, 250.f), Rng.FRandRange(-250.f, 250.f), Rng.FRandRange(500.f, 1500.f)) * Strength;
		P.Life = Rng.FRandRange(5.f, 9.f);
		P.Size0 = Rng.FRandRange(300.f, 700.f) * (0.6f + 0.4f * Strength);
		P.Size1 = P.Size0 * Rng.FRandRange(4.f, 7.f);
		P.Roll = Rng.FRandRange(0.f, 360.f);
		P.RollRate = Rng.FRandRange(-8.f, 8.f);
		P.Drag = Rng.FRandRange(0.3f, 0.7f);
		P.Rise = Rng.FRandRange(120.f, 320.f);
		P.Opacity = 0.7f;
		P.Seed = Rng.FRand();
		Puffs.Add(P);
	}
}

void AIVFXManager::SpawnFlame(const FVector& Center, float Radius, int32 Count, float Strength)
{
	for (int32 i = 0; i < Count && Flames.Num() < MaxFlames; ++i)
	{
		FIVFlame F;
		F.Pos = Center + FVector(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-0.2f, 0.6f)) * Radius;
		F.Vel = FVector(Rng.FRandRange(-120.f, 120.f), Rng.FRandRange(-120.f, 120.f), Rng.FRandRange(300.f, 900.f)) * Strength;
		F.Life = Rng.FRandRange(0.6f, 1.4f);
		F.Size0 = Rng.FRandRange(300.f, 650.f) * (0.6f + 0.4f * Strength);
		F.Size1 = F.Size0 * Rng.FRandRange(1.6f, 2.6f);
		F.Roll = Rng.FRandRange(0.f, 360.f);
		F.Rise = Rng.FRandRange(500.f, 1200.f);
		F.Heat = Rng.FRandRange(0.3f, 1.f);
		F.Seed = Rng.FRand();
		Flames.Add(F);
	}
}

void AIVFXManager::SpawnFlash(const FVector& Center, const FLinearColor& Color, float Candela, float Seconds, float Radius)
{
	int32 Slot = 0;
	float Oldest = -1.f;
	for (int32 i = 0; i < 5; ++i)
	{
		const float Rem = Flashes[i].Life - Flashes[i].Age;
		if (Rem <= 0.f) { Slot = i; Oldest = 1e9f; break; }
		if (Flashes[i].Age > Oldest) { Oldest = Flashes[i].Age; Slot = i; }
	}
	FIVFlash& F = Flashes[Slot];
	F.Pos = Center; F.Color = Color; F.Intensity = Candela * 0.28f; F.Life = Seconds; F.Age = 0.f; F.Radius = Radius;
}

void AIVFXManager::SpawnExplosion(const FVector& Center, float Scale)
{
	for (int32 i = 0; i < int32(14 * Scale) && Flames.Num() < MaxFlames; ++i)
	{
		FIVFlame F;
		const FVector D = Rng.VRand();
		F.Pos = Center + D * 250.f * Scale * Rng.FRand();
		F.Vel = D * Rng.FRandRange(600.f, 2600.f) * Scale + FVector(0, 0, 500.f * Scale);
		F.Life = Rng.FRandRange(0.7f, 1.7f);
		F.Size0 = Rng.FRandRange(600.f, 1300.f) * Scale;
		F.Size1 = F.Size0 * Rng.FRandRange(1.8f, 3.2f);
		F.Roll = Rng.FRandRange(0.f, 360.f);
		F.Rise = Rng.FRandRange(300.f, 1200.f);
		F.Heat = Rng.FRandRange(0.6f, 1.f);
		F.Seed = Rng.FRand();
		Flames.Add(F);
	}
	SpawnSmoke(Center + FVector(0, 0, 400.f * Scale), 700.f * Scale, int32(16 * Scale), 1.2f * Scale);
	SpawnSparks(Center, FVector::UpVector, int32(70 * Scale), 6500.f * Scale);
	SpawnFlash(Center, FLinearColor(1.f, 0.55f, 0.2f), 2.6e5f * Scale, 0.55f, 14000.f * Scale);
}

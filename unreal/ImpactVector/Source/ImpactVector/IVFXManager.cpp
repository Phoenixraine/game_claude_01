#include "IVFXManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/PointLightComponent.h"
#include "IVDistrict.h"

bool AIVFXManager::bGroundMist = false;

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

void AIVFXManager::BeginPlay()
{
	Super::BeginPlay();
	struct FFam { const TCHAR* Prefix; int32 First; int32 Num; };
	static const FFam Fams[int32(EIVChunk::Count)] = {
		{ TEXT("Shard_Concrete_M_"), 0, 6 }, { TEXT("Slab_Concrete_"), 0, 4 }, { TEXT("Glass_Shard_"), 0, 8 },
		{ TEXT("Steel_Plate_Bent_"), 0, 4 }, { TEXT("Steel_Plate_Bent_"), 4, 4 }, { TEXT("Pebble_"), 0, 6 } };
	UMaterialInterface* Mat = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Materials/M_Chunk.M_Chunk"));
	for (int32 F = 0; F < int32(EIVChunk::Count); ++F)
	{
		FamilyFirst.Add(ChunkISM.Num());
		int32 Got = 0;
		for (int32 k = 0; k < Fams[F].Num; ++k)
		{
			const FString Name = FString::Printf(TEXT("%s%02d"), Fams[F].Prefix, Fams[F].First + k);
			UStaticMesh* M = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Game/Shards/%s.%s"), *Name, *Name));
			if (!M) continue;
			UInstancedStaticMeshComponent* I = NewObject<UInstancedStaticMeshComponent>(this);
			I->SetStaticMesh(M);
			I->SetupAttachment(RootComponent);
			I->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			I->SetCastShadow(true);
			I->NumCustomDataFloats = 3;
			I->SetCullDistances(0, 0);
			I->bUseAsOccluder = false;
			I->SetCanEverAffectNavigation(false);
			if (Mat) for (int32 s = 0; s < M->GetStaticMaterials().Num(); ++s) I->SetMaterial(s, Mat);
			I->RegisterComponent();
			ChunkISM.Add(I);
			ChunkRadius.Add(M->GetBounds().SphereRadius);
			++Got;
		}
		FamilyCount.Add(Got);
	}
	UE_LOG(LogTemp, Display, TEXT("IV chunks: %d meshes"), ChunkISM.Num());
}

void AIVFXManager::SpawnPiece(UStaticMesh* Mesh, UMaterialInterface* Mat, const FTransform& Xf, const FVector& Vel, const FVector& Spin, float Heat)
{
	if (!Mesh || Chunks.Num() >= MaxChunks) return;
	int32* Found = PieceSlots.Find(Mesh);
	int32 Slot;
	if (Found) Slot = *Found;
	else
	{
		UInstancedStaticMeshComponent* I = NewObject<UInstancedStaticMeshComponent>(this);
		I->SetStaticMesh(Mesh);
		I->SetupAttachment(RootComponent);
		I->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		I->SetCastShadow(true);
		I->NumCustomDataFloats = 3;
		I->SetCullDistances(0, 0);
		I->bUseAsOccluder = false;
		I->SetCanEverAffectNavigation(false);
		if (Mat) for (int32 s = 0; s < Mesh->GetStaticMaterials().Num(); ++s) I->SetMaterial(s, Mat);
		I->RegisterComponent();
		Slot = ChunkISM.Add(I);
		ChunkRadius.Add(Mesh->GetBounds().SphereRadius);
		PieceSlots.Add(Mesh, Slot);
	}
	FIVChunk C;
	C.Slot = Slot;
	C.Kind = 3.f;
	C.Scale = 1.f;
	C.Scale3 = Xf.GetScale3D();
	C.Radius = ChunkRadius[Slot] * C.Scale3.GetMax() * 0.5f;
	C.Pos = Xf.GetLocation();
	C.Rot = Xf.GetRotation();
	C.Vel = Vel;
	C.AngVel = Spin;
	C.Life = 18.f;
	C.Heat = Heat;
	C.Seed = Rng.FRand();
	Chunks.Add(C);
}

void AIVFXManager::SpawnChunks(const FVector& Center, const FVector& Dir, int32 Count, EIVChunk Family, float Scale, float Speed, float Heat, float Spread)
{
	const int32 F = int32(Family);
	if (!FamilyCount.IsValidIndex(F) || FamilyCount[F] == 0) return;
	static const float KindOf[int32(EIVChunk::Count)] = { 0.f, 0.f, 2.f, 1.f, 3.f, 0.f };
	const FVector D0 = Dir.GetSafeNormal();
	for (int32 i = 0; i < Count && Chunks.Num() < MaxChunks; ++i)
	{
		FIVChunk C;
		C.Slot = FamilyFirst[F] + Rng.RandRange(0, FamilyCount[F] - 1);
		C.Kind = KindOf[F];
		C.Scale = Scale * 2.6f * Rng.FRandRange(0.6f, 1.5f);
		C.Radius = ChunkRadius[C.Slot] * C.Scale;
		const FVector D = (D0 + Rng.VRand() * Spread).GetSafeNormal();
		C.Pos = Center + Rng.VRand() * C.Radius * 1.5f;
		C.Vel = D * Speed * Rng.FRandRange(0.35f, 1.f) + FVector(0, 0, Speed * 0.25f);
		C.AngVel = Rng.VRand() * Rng.FRandRange(2.f, 9.f);
		C.Rot = FQuat(Rng.VRand(), Rng.FRandRange(0.f, 6.28f));
		C.Life = Rng.FRandRange(7.f, 13.f);
		C.Heat = Heat * Rng.FRandRange(0.6f, 1.f);
		C.Seed = Rng.FRand();
		Chunks.Add(C);
	}
}

void AIVFXManager::TickChunks(float Dt)
{
	if (ChunkISM.Num() == 0) return;
	FVector CamPos = FVector::ZeroVector;
	if (APlayerCameraManager* Cam0 = UGameplayStatics::GetPlayerCameraManager(this, 0)) CamPos = Cam0->GetCameraLocation();
	if (!Dist.IsValid()) for (TActorIterator<AIVDistrict> It(GetWorld()); It; ++It) { Dist = *It; break; }
	for (int32 i = Chunks.Num() - 1; i >= 0; --i)
	{
		FIVChunk& C = Chunks[i];
		C.Age += Dt;
		if (C.Age >= C.Life) { Chunks.RemoveAtSwap(i); continue; }
		C.Heat = FMath::Max(0.f, C.Heat - Dt * (C.bRest ? 0.18f : 0.1f));
		if (C.bRest) continue;
		C.Vel.Z -= 1900.f * Dt;
		C.Vel *= FMath::Exp(-0.12f * Dt);
		C.Pos += C.Vel * Dt;
		const FQuat Dq = FQuat(C.AngVel.GetSafeNormal(), C.AngVel.Size() * Dt);
		C.Rot = (Dq * C.Rot).GetNormalized();
		const float G = (Dist.IsValid() ? Dist->SampleHeightCm(C.Pos.X, C.Pos.Y) : GroundZ) + C.Radius * 0.35f;
		if (C.Pos.Z < G)
		{
			C.Pos.Z = G;
			if (FMath::Abs(C.Vel.Z) < 260.f && C.Vel.Size2D() < 500.f) { C.bRest = true; C.Vel = FVector::ZeroVector; }
			else
			{
				C.Vel.Z = FMath::Abs(C.Vel.Z) * 0.32f;
				C.Vel.X *= 0.62f; C.Vel.Y *= 0.62f;
				C.AngVel *= 0.55f;
				if (C.Vel.Z > 700.f && C.Scale > 1.5f && Rng.FRand() < 0.3f) SpawnDust(C.Pos, C.Radius, 1, 0.3f);
			}
		}
		if (C.Heat > 0.35f)
		{
			C.FlameAcc += Dt;
			if (C.FlameAcc > 0.07f)
			{
				C.FlameAcc = 0.f;
				FIVFlame F;
				F.Pos = C.Pos; F.Vel = FVector(0, 0, 250.f) + Rng.VRand() * 150.f;
				F.Life = Rng.FRandRange(0.4f, 0.8f);
				F.Size0 = C.Radius * 0.8f; F.Size1 = C.Radius * 1.6f;
				F.Roll = Rng.FRandRange(0.f, 360.f); F.Rise = 500.f; F.Heat = C.Heat; F.Seed = Rng.FRand();
				if (Flames.Num() < MaxFlames) Flames.Add(F);
				if (Rng.FRand() < 0.35f && Puffs.Num() < MaxPuffs)
				{
					FIVPuff P;
					P.Dark = 0.8f; P.Pos = C.Pos; P.Vel = FVector(0, 0, 200.f) + Rng.VRand() * 100.f;
					P.Life = Rng.FRandRange(2.5f, 4.5f); P.Size0 = C.Radius * 1.2f; P.Size1 = C.Radius * 4.f;
					P.Roll = Rng.FRandRange(0.f, 360.f); P.RollRate = Rng.FRandRange(-8.f, 8.f); P.Drag = 0.6f; P.Rise = 140.f; P.Opacity = 0.6f; P.Seed = Rng.FRand();
					Puffs.Add(P);
				}
			}
		}
	}
	{
		static float LogT = 0.f;
		LogT += Dt;
		if (Chunks.Num() > 0 && LogT > 1.5f)
		{
			LogT = 0.f;
			int32 Inst = 0;
			for (UInstancedStaticMeshComponent* I : ChunkISM) Inst += I->GetInstanceCount();
			UE_LOG(LogTemp, Display, TEXT("IV chunks live %d instances %d first(%s) pos %s scale %.1f"), Chunks.Num(), Inst, *GetNameSafe(ChunkISM[Chunks[0].Slot]->GetStaticMesh()), *Chunks[0].Pos.ToString(), Chunks[0].Scale);
		}
	}
	// instances per mesh slot
	static TArray<TArray<int32>> BySlot;
	BySlot.SetNum(ChunkISM.Num());
	for (TArray<int32>& B : BySlot) B.Reset();
	for (int32 i = 0; i < Chunks.Num(); ++i) BySlot[Chunks[i].Slot].Add(i);
	for (int32 S = 0; S < ChunkISM.Num(); ++S)
	{
		UInstancedStaticMeshComponent* I = ChunkISM[S];
		const TArray<int32>& L = BySlot[S];
		if (L.Num() == 0 && I->GetInstanceCount() == 0) continue;
		TArray<FTransform> T;
		T.Reserve(L.Num());
		for (int32 k : L)
		{
			const FIVChunk& C = Chunks[k];
			const float Fade = FMath::Clamp((C.Life - C.Age) / 1.5f, 0.f, 1.f);
			// nothing may fill the pilot's view: pieces that tumble close past the camera shrink away
			const float Near = FMath::Clamp((FVector::Dist(C.Pos, CamPos) - 2500.f) / 3500.f, 0.f, 1.f);
			T.Add(FTransform(C.Rot, C.Pos, C.Scale3 * (C.Scale * Fade * Near)));
		}
		if (I->GetInstanceCount() != T.Num())
		{
			I->ClearInstances();
			I->NumCustomDataFloats = 3;
			if (T.Num() > 0) I->AddInstances(T, false, true);
		}
		else if (T.Num() > 0) I->BatchUpdateInstancesTransforms(0, T, true, true, true);
		for (int32 n = 0; n < L.Num(); ++n)
		{
			const FIVChunk& C = Chunks[L[n]];
			I->SetCustomDataValue(n, 0, C.Heat, false);
			I->SetCustomDataValue(n, 1, C.Kind, false);
			I->SetCustomDataValue(n, 2, C.Seed, n == L.Num() - 1);
		}
	}
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

void AIVFXManager::SpawnSparks(const FVector& Center, const FVector& Normal, int32 Count, float Speed, float Scale)
{
	for (int32 i = 0; i < Count && Sparks.Num() < MaxSparks; ++i)
	{
		FIVSpark S;
		S.Pos = Center;
		const FVector Dir = (Normal + Rng.VRand() * 0.9f).GetSafeNormal();
		S.Vel = Dir * Speed * Rng.FRandRange(0.3f, 1.f);
		S.Life = Rng.FRandRange(0.4f, 1.2f);
		S.Len = Rng.FRandRange(60.f, 220.f) * Scale;
		Sparks.Add(S);
	}
}

void AIVFXManager::Tick(float Dt)
{
	Super::Tick(Dt);
	Dt = FMath::Min(Dt, 0.05f);
	TickChunks(Dt);
	{	// ground mist drifting along the street around the camera
		MistAcc += Dt;
		if (MistAcc > 0.18f && Puffs.Num() < MaxPuffs - 150 && (bGroundMist || FParse::Param(FCommandLine::Get(), TEXT("IVMist"))))
		{
			MistAcc = 0.f;
			APlayerCameraManager* PCM = UGameplayStatics::GetPlayerCameraManager(this, 0);
			if (PCM)
			{
				const FVector C = PCM->GetCameraLocation();
				FIVPuff P;
				P.Dark = 0.3f;
				const float A = Rng.FRandRange(0.f, 6.283f), Rr = Rng.FRandRange(10000.f, 32000.f);
				P.Pos = FVector(C.X + FMath::Cos(A) * Rr, C.Y + FMath::Sin(A) * Rr, Rng.FRandRange(150.f, 700.f));
				P.Vel = FVector(Rng.FRandRange(-260.f, 260.f), Rng.FRandRange(-260.f, 260.f), 0.f);
				P.Life = Rng.FRandRange(14.f, 24.f);
				P.Size0 = Rng.FRandRange(5000.f, 9000.f);
				P.Size1 = P.Size0 * Rng.FRandRange(1.6f, 2.4f);
				P.Roll = Rng.FRandRange(0.f, 360.f);
				P.RollRate = Rng.FRandRange(-1.5f, 1.5f);
				P.Drag = 0.3f; P.Rise = 0.f; P.Opacity = 0.16f; P.Seed = Rng.FRand();
				Puffs.Add(P);
			}
		}
	}

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
			T.Add(FTransform(FRotationMatrix::MakeFromX(Dir).ToQuat(), S.Pos, FVector(S.Len / 100.f, 0.035f * FMath::Max(1.f, S.Len / 150.f), 0.035f * FMath::Max(1.f, S.Len / 150.f)) * (0.4f + 0.6f * Fade)));
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

void AIVFXManager::SpawnJet(const FVector& Pos, const FVector& Dir, int32 Count, float Speed, float Size)
{
	for (int32 i = 0; i < Count && Flames.Num() < MaxFlames; ++i)
	{
		FIVFlame F;
		F.Pos = Pos + Rng.VRand() * Size * 0.15f;
		F.Vel = Dir * Speed * Rng.FRandRange(0.7f, 1.1f) + Rng.VRand() * Speed * 0.08f;
		F.Life = Rng.FRandRange(0.25f, 0.55f);
		F.Size0 = Size * Rng.FRandRange(0.5f, 0.8f);
		F.Size1 = Size * Rng.FRandRange(1.2f, 1.9f);
		F.Roll = Rng.FRandRange(0.f, 360.f);
		F.Rise = 0.f;
		F.Heat = Rng.FRandRange(0.8f, 1.f);
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

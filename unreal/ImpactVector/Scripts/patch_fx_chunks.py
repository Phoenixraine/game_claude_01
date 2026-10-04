import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    return io.open(SRC + "\\" + n, encoding="utf-8").read()


def wr(n, s):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\n").write(s)


h = rd("IVFXManager.h")
if "EIVChunk" not in h:
    h = h.replace("UCLASS()\nclass IMPACTVECTOR_API AIVFXManager", """/** Debris families from the shard library (art/shards). */
enum class EIVChunk : uint8 { Concrete, Slab, Glass, Steel, Armor, Gravel, Count };

struct FIVChunk
{
	int32 Slot = 0;                  // index into ChunkISM
	float Kind = 0.f;                // material kind: 0 concrete, 1 steel, 2 glass, 3 armour
	FVector Pos = FVector::ZeroVector, Vel = FVector::ZeroVector, AngVel = FVector::ZeroVector;
	FQuat Rot = FQuat::Identity;
	float Scale = 1.f, Radius = 50.f;
	float Age = 0.f, Life = 10.f, Heat = 0.f, Seed = 0.f, FlameAcc = 0.f;
	bool bRest = false;
};

UCLASS()
class IMPACTVECTOR_API AIVFXManager""", 1)
    h = h.replace("	/** Short light flash (clashes, muzzle, lightning-like). */", """	/** Flying debris from the shard library. Dir = main direction of the spray; Heat > 0 makes the pieces glow and burn while they fly. */
	void SpawnChunks(const FVector& Center, const FVector& Dir, int32 Count, EIVChunk Family, float Scale, float Speed, float Heat = 0.f, float Spread = 0.8f);
	/** Short light flash (clashes, muzzle, lightning-like). */""", 1)
    h = h.replace("	virtual void Tick(float Dt) override;\n", "	virtual void Tick(float Dt) override;\n	virtual void BeginPlay() override;\n", 1)
    h = h.replace("	TArray<FIVSpark> Sparks;\n", """	TArray<FIVSpark> Sparks;
	UPROPERTY() TArray<TObjectPtr<UInstancedStaticMeshComponent>> ChunkISM;
	TArray<float> ChunkRadius;
	TArray<int32> FamilyFirst, FamilyCount;
	TArray<FIVChunk> Chunks;
	float GroundZ = 0.f;
	TWeakObjectPtr<class AIVDistrict> Dist;
	static constexpr int32 MaxChunks = 420;
	void TickChunks(float Dt);
""", 1)
    wr("IVFXManager.h", h)

c = rd("IVFXManager.cpp")
if "TickChunks" not in c:
    c = c.replace('#include "Components/PointLightComponent.h"', '#include "Components/PointLightComponent.h"\n#include "IVDistrict.h"', 1)
    new = r'''void AIVFXManager::BeginPlay()
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
		C.Scale = Scale * Rng.FRandRange(0.6f, 1.5f);
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
			T.Add(FTransform(C.Rot, C.Pos, FVector(C.Scale * Fade)));
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

'''
    c = c.replace("void AIVFXManager::SpawnDust(", new + "void AIVFXManager::SpawnDust(", 1)
    c = c.replace("	Dt = FMath::Min(Dt, 0.05f);\n", "	Dt = FMath::Min(Dt, 0.05f);\n	TickChunks(Dt);\n", 1)
    wr("IVFXManager.cpp", c)
print("patched")

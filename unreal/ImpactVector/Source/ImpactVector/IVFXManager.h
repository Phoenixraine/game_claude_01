// CPU particle manager: dust/smoke puffs and sparks rendered through instanced meshes.
// Cheap enough for split-screen; replaces Niagara for the gameplay-critical effects (predictable cost, no asset authoring).
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "IVFXManager.generated.h"

class UInstancedStaticMeshComponent;
class UMaterialInterface;

struct FIVPuff
{
	float Dark = 0.f;
	FVector Pos, Vel;
	float Age = 0.f, Life = 1.f;
	float Size0 = 100.f, Size1 = 500.f;
	float Roll = 0.f, RollRate = 0.f;
	float Drag = 0.8f, Rise = 40.f;
	float Opacity = 0.6f;
	float Seed = 0.f;
};

struct FIVFlame
{
	FVector Pos, Vel;
	float Age = 0.f, Life = 0.8f;
	float Size0 = 200.f, Size1 = 700.f;
	float Roll = 0.f, Rise = 600.f, Heat = 1.f, Seed = 0.f;
};

struct FIVFlash
{
	FVector Pos = FVector::ZeroVector;
	FLinearColor Color = FLinearColor::White;
	float Age = 1.f, Life = 0.3f, Intensity = 0.f, Radius = 8000.f;
};

struct FIVSpark
{
	FVector Pos, Vel;
	float Age = 0.f, Life = 0.6f;
	float Len = 80.f;
};

/** Debris families from the shard library (art/shards). */
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
class IMPACTVECTOR_API AIVFXManager : public AActor
{
	GENERATED_BODY()

public:
	AIVFXManager();
	virtual void Tick(float Dt) override;
	virtual void BeginPlay() override;

	static AIVFXManager* Get(UWorld* World);

	/** Big expanding dust/smoke cloud (building collapse, impacts). */
	void SpawnDust(const FVector& Center, float Radius, int32 Count, float Strength = 1.f);
	void SpawnSparks(const FVector& Center, const FVector& Normal, int32 Count, float Speed = 4000.f);
	/** Dark smoke column / cloud (burning wrecks). */
	void SpawnSmoke(const FVector& Center, float Radius, int32 Count, float Strength = 1.f);
	/** Licking flames rising from a point (one call = a few sprites; call repeatedly for a burning zone). */
	void SpawnFlame(const FVector& Center, float Radius, int32 Count, float Strength = 1.f);
	/** A directed burst of flame (jetpack nozzle): Dir is the exhaust direction. */
	void SpawnJet(const FVector& Pos, const FVector& Dir, int32 Count, float Speed, float Size);
	/** Fireball + smoke + sparks + light flash. Scale 1 = a limb breaking, 3 = a mech blowing up. */
	void SpawnExplosion(const FVector& Center, float Scale = 1.f);
	/** Flying debris from the shard library. Dir = main direction of the spray; Heat > 0 makes the pieces glow and burn while they fly. */
	void SpawnChunks(const FVector& Center, const FVector& Dir, int32 Count, EIVChunk Family, float Scale, float Speed, float Heat = 0.f, float Spread = 0.8f);
	/** Short light flash (clashes, muzzle, lightning-like). */
	void SpawnFlash(const FVector& Center, const FLinearColor& Color, float Candela, float Seconds, float Radius = 9000.f);

private:
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> PuffISM;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> SparkISM;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> FireISM;
	UPROPERTY() TArray<TObjectPtr<class UPointLightComponent>> FlashLights;
	TArray<FIVFlame> Flames;
	FIVFlash Flashes[5];
	static constexpr int32 MaxFlames = 500;
	TArray<FIVPuff> Puffs;
	TArray<FIVSpark> Sparks;
	UPROPERTY() TArray<TObjectPtr<UInstancedStaticMeshComponent>> ChunkISM;
	TArray<float> ChunkRadius;
	TArray<int32> FamilyFirst, FamilyCount;
	TArray<FIVChunk> Chunks;
	float GroundZ = 0.f;
	TWeakObjectPtr<class AIVDistrict> Dist;
	static constexpr int32 MaxChunks = 420;
	void TickChunks(float Dt);
	FRandomStream Rng{4711};
	static constexpr int32 MaxPuffs = 900;
	static constexpr int32 MaxSparks = 600;
};

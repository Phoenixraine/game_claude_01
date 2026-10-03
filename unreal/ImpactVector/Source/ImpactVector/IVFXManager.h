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
	FVector Pos, Vel;
	float Age = 0.f, Life = 1.f;
	float Size0 = 100.f, Size1 = 500.f;
	float Roll = 0.f, RollRate = 0.f;
	float Drag = 0.8f, Rise = 40.f;
	float Opacity = 0.6f;
	float Seed = 0.f;
};

struct FIVSpark
{
	FVector Pos, Vel;
	float Age = 0.f, Life = 0.6f;
	float Len = 80.f;
};

UCLASS()
class IMPACTVECTOR_API AIVFXManager : public AActor
{
	GENERATED_BODY()

public:
	AIVFXManager();
	virtual void Tick(float Dt) override;

	static AIVFXManager* Get(UWorld* World);

	/** Big expanding dust/smoke cloud (building collapse, impacts). */
	void SpawnDust(const FVector& Center, float Radius, int32 Count, float Strength = 1.f);
	void SpawnSparks(const FVector& Center, const FVector& Normal, int32 Count, float Speed = 4000.f);

private:
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> PuffISM;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> SparkISM;
	TArray<FIVPuff> Puffs;
	TArray<FIVSpark> Sparks;
	FRandomStream Rng{4711};
	static constexpr int32 MaxPuffs = 900;
	static constexpr int32 MaxSparks = 600;
};

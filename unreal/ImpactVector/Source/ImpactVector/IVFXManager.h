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
	/** Dark smoke column / cloud (burning wrecks). */
	void SpawnSmoke(const FVector& Center, float Radius, int32 Count, float Strength = 1.f);
	/** Licking flames rising from a point (one call = a few sprites; call repeatedly for a burning zone). */
	void SpawnFlame(const FVector& Center, float Radius, int32 Count, float Strength = 1.f);
	/** Fireball + smoke + sparks + light flash. Scale 1 = a limb breaking, 3 = a mech blowing up. */
	void SpawnExplosion(const FVector& Center, float Scale = 1.f);
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
	FRandomStream Rng{4711};
	static constexpr int32 MaxPuffs = 900;
	static constexpr int32 MaxSparks = 600;
};

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "IVEnvironment.generated.h"

class UDirectionalLightComponent;
class USkyAtmosphereComponent;
class USkyLightComponent;
class UExponentialHeightFogComponent;
class UVolumetricCloudComponent;
class UPostProcessComponent;
class UInstancedStaticMeshComponent;
class UStaticMeshComponent;
class AIVBuilding;
class AIVDistrict;

struct FIVBuildingDef
{
	FVector Center = FVector::ZeroVector;
	FVector Size = FVector::OneVector;
	bool bGlass = false;
	bool bActive = false;
	TWeakObjectPtr<AIVBuilding> Actor;
};

/** Sky, light, fog, post-process, ground, sea and a grey-box city. The city is replaced by worldgen output (TASK-004) later. */
UCLASS()
class IMPACTVECTOR_API AIVEnvironment : public AActor
{
	GENERATED_BODY()

public:
	AIVEnvironment();
	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float Dt) override;
	/** Test helper / console: strike now. */
	void Lightning();
	void DistantExplosion();

	static AIVEnvironment* Get(UWorld* World);
	/** Fog / exposure / neon / bloom / motion blur / rain amount / ground mist from the player's settings. */
	/** PS2-style screen filter: strength 0..1 (0 = off), big-pixel size in screen pixels, colour steps per channel, dither 0..1. */
	void ApplyPs2(float Strength, float PixelSize, float Levels, float Dither);
	void ApplySettings(float FogMul, float EV, float Neon, float Bloom, float MotionBlur, float Rain, bool bMist);

	/** Blast at a world point: opens up the buildings it touches and destroys cells. Returns cells destroyed. */
	int32 BlastAt(const FVector& Center, float Radius, float Impulse);
	bool FindScoopBuilding(const FVector& From, const FVector& Dir, FVector& OutBase, FVector& OutSize) const;

	/** Test helper: cut the base of the nearest building ahead of From along Dir. */
	int32 CollapseNearestAhead(const FVector& From, const FVector& Dir);

private:
	UPROPERTY() TObjectPtr<AIVDistrict> District;
public:
	AIVDistrict* GetDistrict() const { return District; }
private:
	TArray<FIVBuildingDef> Defs;
	TArray<FTransform> PodiumTransforms;
	void RebuildStaticInstances();

	UPROPERTY() TObjectPtr<USceneComponent> Root;
	UPROPERTY() TObjectPtr<UDirectionalLightComponent> Sun;
	UPROPERTY() TObjectPtr<UDirectionalLightComponent> Moon;
	UPROPERTY() TObjectPtr<USkyAtmosphereComponent> Atmosphere;
	UPROPERTY() TObjectPtr<USkyLightComponent> SkyLight;
	UPROPERTY() TObjectPtr<UExponentialHeightFogComponent> Fog;
	UPROPERTY() TObjectPtr<UVolumetricCloudComponent> Clouds;
	UPROPERTY() TObjectPtr<UPostProcessComponent> PostProcess;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Ground;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Sea;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Concrete;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Glass;

	void BuildCityBlockout();
	UPROPERTY() TObjectPtr<AActor> RainActor;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> Ps2MID;
	// storm: lightning pulses lift the moon and sky light for a moment; thunder and far-off blasts follow with a delay
	float StormClock = 5.f, ExplClock = 11.f, BoltT = -1.f, BoltAmp = 1.f, BoltDelay = 0.f;
	float MoonBase = 2.6f, SkyBase = 0.8f, EvBase = 0.f;
	bool bStorm = true;
	struct FDelayed { float T; int32 Kind; FVector P; };
	TArray<FDelayed> Delayed;
};

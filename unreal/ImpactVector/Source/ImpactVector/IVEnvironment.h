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

	static AIVEnvironment* Get(UWorld* World);

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
};

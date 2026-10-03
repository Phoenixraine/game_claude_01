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

/** Sky, light, fog, post-process, ground, sea and a grey-box city. The city is replaced by worldgen output (TASK-004) later. */
UCLASS()
class IMPACTVECTOR_API AIVEnvironment : public AActor
{
	GENERATED_BODY()

public:
	AIVEnvironment();
	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;

private:
	UPROPERTY() TObjectPtr<USceneComponent> Root;
	UPROPERTY() TObjectPtr<UDirectionalLightComponent> Sun;
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

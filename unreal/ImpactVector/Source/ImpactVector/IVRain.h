#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "IVRain.generated.h"

class UInstancedStaticMeshComponent;

/** Rain: thousands of streak instances that wrap around the camera in the vertex shader (M_Rain). The actor follows the camera in
 *  whole box steps so the instances always surround the view. */
UCLASS()
class IMPACTVECTOR_API AIVRain : public AActor
{
	GENERATED_BODY()
public:
	AIVRain();
	virtual void Tick(float Dt) override;
	virtual void BeginPlay() override;
	int32 Count = 30000;
	float BoxXY = 14000.f, BoxZ = 9000.f;
private:
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> ISM;
};

// Presentation of the boarding sequence (core: iv::Boarding): the pilot in a drive suit climbs out of the cockpit, crosses to the enemy
// shoulder on a grapple, hacks the hatch, throws a grenade and flies back. The core owns the rules; this actor only draws the pilot,
// the cable and the grenade where the phase says they are, and the director places the camera.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "iv/Boarding.h"
#include "IVBoarding.generated.h"

class UProceduralMeshComponent;
class UStaticMeshComponent;
class UPointLightComponent;
class UMaterialInstanceDynamic;

/** Everything the figure needs to know for one frame, in world space (cm). */
struct FIVBoardView
{
	iv::BoardPhase Phase = iv::BoardPhase::Idle;
	float U = 0.f;                         // progress inside the phase 0..1
	FVector Cockpit = FVector::ZeroVector;      // the hatch of the owner's cockpit
	FVector OwnShoulder = FVector::ZeroVector;  // the owner's shoulder the pilot climbs to
	FVector OwnWrist = FVector::ZeroVector;     // grapple launcher on the owner's wrist
	FVector EnemyShoulder = FVector::ZeroVector;
	FVector EnemyOtherShoulder = FVector::ZeroVector;
	FVector EnemyHatch = FVector::ZeroVector;   // the hatch next to the shoulder joint
	FVector EnemyUp = FVector::UpVector;
	FVector Away = FVector::ForwardVector;      // direction from the enemy to the owner (where the escape goes)
	bool bSwapped = false;
};

UCLASS()
class IMPACTVECTOR_API AIVPilotFigure : public AActor
{
	GENERATED_BODY()

public:
	AIVPilotFigure();
	virtual void Tick(float Dt) override;
	virtual void BeginPlay() override;

	/** Places the pilot, cable and grenade for this frame. */
	void Present(const FIVBoardView& V, float Dt);
	void Hide();
	FVector GetPilotLocation() const { return PilotPos; }
	FVector GetHatchLocation() const { return HatchPos; }

private:
	UPROPERTY() TObjectPtr<USceneComponent> Body;
	UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Parts;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Grenade;
	UPROPERTY() TObjectPtr<UProceduralMeshComponent> Cable;
	UPROPERTY() TObjectPtr<UPointLightComponent> SuitLight;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> CableMat;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> SuitMat;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> GlowMat;
	FVector PilotPos = FVector::ZeroVector, HatchPos = FVector::ZeroVector, PrevPos = FVector::ZeroVector;
	FVector Facing = FVector::ForwardVector;
	float FxAcc = 0.f;
	bool bBuilt = false;
	void BuildModel();
	void SetCable(const FVector& A, const FVector& B, float Sag, bool bShow);
};

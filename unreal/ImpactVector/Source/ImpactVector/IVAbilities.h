// Abilities that live in the world rather than in the combat core: the building thrown in the opponent's face.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "IVAbilities.generated.h"

class UInstancedStaticMeshComponent;

/** A torn-off chunk of a building flying from the thrower's hand to the target's head; calls OnImpact on arrival. */
UCLASS()
class IMPACTVECTOR_API AIVThrownDebris : public AActor
{
	GENERATED_BODY()

public:
	AIVThrownDebris();
	virtual void Tick(float Dt) override;

	/** Start/target in world cm; the target is re-read from `Follow` each tick when it is set (the head moves). */
	void Launch(const FVector& InStart, TWeakObjectPtr<AActor> InFollow, const FVector& InTargetFallback, float InDuration, float Scale, TFunction<void(const FVector&)> InOnImpact);

private:
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Chunks;
	FVector Start = FVector::ZeroVector, TargetFallback = FVector::ZeroVector, LastTarget = FVector::ZeroVector;
	TWeakObjectPtr<AActor> Follow;
	float Duration = 1.f, T = 0.f, Arc = 0.f;
	FVector Spin = FVector::ZeroVector;
	FRotator Rot = FRotator::ZeroRotator;
	float DustAcc = 0.f;
	TFunction<void(const FVector&)> OnImpact;
};

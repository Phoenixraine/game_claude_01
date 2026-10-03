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

class UProceduralMeshComponent;
class UMaterialInstanceDynamic;

/** Visuals of the three long-cooldown weapons: a rail beam, a volley of six rockets, a plasma orb. Purely cosmetic: the core already decided the hits. */
UCLASS()
class IMPACTVECTOR_API AIVProjectile : public AActor
{
	GENERATED_BODY()

public:
	AIVProjectile();
	virtual void Tick(float Dt) override;

	/** Kind: 0 rail beam, 1 rockets, 2 plasma. Target is re-read each tick while it moves; bHit false = the shot flies past. */
	void Launch(int32 InKind, const FVector& InFrom, TWeakObjectPtr<AActor> InTarget, bool bInHit, float InDuration);

private:
	UPROPERTY() TObjectPtr<UProceduralMeshComponent> Beam;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> BeamMID;
	int32 Kind = 0;
	bool bHit = true;
	FVector From = FVector::ZeroVector, To = FVector::ZeroVector;
	TWeakObjectPtr<AActor> Target;
	float T = 0.f, Duration = 1.f;
	bool bDone = false;
	struct FRocket { FVector Side; float Delay; float Wob; };
	TArray<FRocket> Rockets;
	void UpdateTarget();
};

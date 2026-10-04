// Heavy transport helicopters circling the arena with searchlights. When one dips low (a "low pass") a mech can grab it with the
// scoop action and hurl it at the opponent: it spins in, trailing fire, and blows up on the head. Everything is built at runtime.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "IVHelicopter.generated.h"

class UProceduralMeshComponent;
class UStaticMeshComponent;
class USpotLightComponent;
class UPointLightComponent;
class UMaterialInstanceDynamic;
class UAudioComponent;
class USceneComponent;

enum class EIVHeliState : uint8 { Patrol, Grabbed, Thrown, Wreck };

UCLASS()
class IMPACTVECTOR_API AIVHelicopter : public AActor
{
	GENERATED_BODY()

public:
	AIVHelicopter();
	virtual void Tick(float Dt) override;
	virtual void BeginPlay() override;

	/** Spawns the standing traffic (called once per match start). */
	static void SpawnFleet(UWorld* World, const FVector& ArenaCenter, int32 Count = 2);
	/** Spawns or removes patrolling helicopters until exactly Count are flying. */
	static void SetFleetSize(UWorld* World, int32 Count);

	/** True while it is low enough and close enough for a mech to take hold of it. */
	bool IsGrabbable() const { return State == EIVHeliState::Patrol && LowFactor > 0.55f; }
	EIVHeliState GetState() const { return State; }
	/** A mech's hand closes on it; after HoldTime it is hurled at Target and OnImpact runs when it hits. */
	void GrabAndThrow(TWeakObjectPtr<AActor> InHolder, TWeakObjectPtr<AActor> InTarget, float HoldTime, float Duration, TFunction<void(const FVector&)> InOnImpact);

	float Phase = 0.f;
	float Radius = 18000.f, Altitude = 11000.f;
	bool bClockwise = true;
	float LowTimer = 20.f;

private:
	EIVHeliState State = EIVHeliState::Patrol;
	FVector Center = FVector(39500.f, 0.f, 0.f);
	float LowFactor = 0.f, LowLeft = 0.f;
	float Time = 0.f, BladeYaw = 0.f, TailYaw = 0.f;
	float Bank = 0.f, Pitch = 0.f;
	FVector AimPoint = FVector::ZeroVector;
	float AimMode = 0.f, AimTimer = 0.f;
	FVector PrevPos = FVector::ZeroVector;
	// grabbed / thrown
	TWeakObjectPtr<AActor> Holder, Target;
	float HoldT = 0.f, ThrowT = 0.f, ThrowDur = 1.15f;
	FVector ThrowStart = FVector::ZeroVector, LastTarget = FVector::ZeroVector;
	FRotator Tumble = FRotator::ZeroRotator, TumbleRate = FRotator::ZeroRotator;
	TFunction<void(const FVector&)> OnImpact;
	float FxAcc = 0.f;

	UPROPERTY() TObjectPtr<USceneComponent> Hull;           // everything that banks and pitches
	UPROPERTY() TObjectPtr<UProceduralMeshComponent> Body;
	UPROPERTY() TObjectPtr<UProceduralMeshComponent> Tail;
	UPROPERTY() TObjectPtr<UProceduralMeshComponent> Canopy;
	UPROPERTY() TObjectPtr<USceneComponent> MainRotor;
	UPROPERTY() TObjectPtr<USceneComponent> TailRotor;
	UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Parts;
	UPROPERTY() TObjectPtr<USpotLightComponent> Search;
	UPROPERTY() TObjectPtr<UPointLightComponent> NavL;
	UPROPERTY() TObjectPtr<UPointLightComponent> NavR;
	UPROPERTY() TObjectPtr<UPointLightComponent> Strobe;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> NavLMesh;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> NavRMesh;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> StrobeMesh;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> HullMat;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> GlassMat;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> NavLMat;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> NavRMat;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> StrobeMat;
	UPROPERTY() TObjectPtr<UAudioComponent> RotorSound;
	bool bBuilt = false;

	void BuildModel();
	UStaticMeshComponent* AddPart(UStaticMesh* Mesh, USceneComponent* Parent, const FVector& Loc, const FRotator& Rot, const FVector& Scale, UMaterialInterface* Mat);
	void TickPatrol(float Dt);
	void TickHeld(float Dt);
	void TickThrown(float Dt);
	void UpdateAim(float Dt);
	void Blow(const FVector& At);
};

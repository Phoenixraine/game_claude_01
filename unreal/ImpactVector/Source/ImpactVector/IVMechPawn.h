// IMPACT VECTOR - articulated mech pawn (grey-box).
// Joint hierarchy mirrors the bone contract of docs/tasks/TASK-002 so that the real BASTION-01 mesh can replace the blockout.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "IVMechPawn.generated.h"

class UCapsuleComponent;
class USceneComponent;
class UStaticMeshComponent;
class UCameraComponent;
class UMaterialInstanceDynamic;

DECLARE_MULTICAST_DELEGATE_TwoParams(FIVFootfallSignature, int32 /*Side: -1 left, +1 right*/, float /*Strength 0..1*/);

/** One articulated mech limb part: a joint pivot plus a grey-box mesh. */
struct FIVJoint
{
	USceneComponent* Pivot = nullptr;
	UStaticMeshComponent* Mesh = nullptr;
};

UCLASS()
class IMPACTVECTOR_API AIVMechPawn : public APawn
{
	GENERATED_BODY()

public:
	AIVMechPawn();

	virtual void Tick(float DeltaSeconds) override;
	virtual void BeginPlay() override;

	/** Desired movement in aim space: X = right, Y = forward, both -1..1. */
	void SetMoveIntent(const FVector2D& Intent) { MoveIntent = Intent.GetClampedToMaxSize(1.f); }
	/** Aim = where the torso/head look, in world degrees. */
	void SetAim(float YawDeg, float PitchDeg) { AimYaw = YawDeg; AimPitch = FMath::Clamp(PitchDeg, -35.f, 30.f); }
	void AddAim(float DeltaYaw, float DeltaPitch) { SetAim(AimYaw + DeltaYaw, AimPitch + DeltaPitch); }
	void SetSprint(bool bInSprint) { bSprint = bInSprint; }
	/** Prototype weapon: blast at the point under the crosshair. Replaced by the combat system. */
	void DebugBlast(float Radius = 2400.f, float Impulse = 1800.f);

	float GetAimYaw() const { return AimYaw; }
	float GetAimPitch() const { return AimPitch; }
	FVector GetEyeLocation() const;
	FVector GetBodyVelocity() const { return Velocity; }
	float GetSpeedRatio() const { return FMath::Clamp(Velocity.Size2D() / WalkSpeed, 0.f, 2.f); }

	/** Tints all grey-box parts (used to differentiate the enemy). */
	void SetBodyTint(const FLinearColor& Tint);
	/** Hide parts that would block the first-person view. */
	void SetFirstPersonView(bool bFirstPerson);

	FIVFootfallSignature OnFootfall;

	// ---- tuning (cm, seconds, degrees) ----
	float WalkSpeed = 650.f;          // ~6.5 m/s: a heavy stride
	float SprintMultiplier = 1.9f;
	float Acceleration = 140.f;        // slow build-up: mass is felt through consequences, not input lag
	float Deceleration = 220.f;
	float LegsTurnRate = 26.f;         // deg/s, cannot spin on the spot
	float TorsoTwistLimit = 85.f;      // deg
	float StrideLength = 2300.f;       // cm per step
	bool bAIControlled = false;

protected:
	UPROPERTY() TObjectPtr<UCapsuleComponent> Capsule;
	UPROPERTY() TObjectPtr<USceneComponent> PelvisPivot;
	UPROPERTY() TObjectPtr<USceneComponent> TorsoPivot;
	UPROPERTY() TObjectPtr<USceneComponent> HeadPivot;
	UPROPERTY() TObjectPtr<UCameraComponent> Camera;
	UPROPERTY() TObjectPtr<USceneComponent> CockpitSway;
	UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> AllMeshes;
	UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> CockpitMeshes;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> HeadMesh;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> TorsoMesh;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> PelvisMesh;

	// joints [0]=left [1]=right
	FIVJoint Shoulder[2], UpperArm[2], Forearm[2], Hand[2];
	FIVJoint Thigh[2], Shin[2], Foot[2];

	UStaticMeshComponent* AddBlock(USceneComponent* Parent, const FName& Name, const FVector& SizeCm, const FVector& CenterOffset, const FLinearColor& Color);
	USceneComponent* AddPivot(USceneComponent* Parent, const FName& Name, const FVector& Location);
	void BuildBody();
	void BuildCockpit();

	void UpdateLocomotion(float Dt);
	void UpdateGait(float Dt);
	void UpdateCockpitCamera(float Dt);
	void UpdateAI(float Dt);

	FVector MoveIntentToWorld() const;

	FVector2D MoveIntent = FVector2D::ZeroVector;
	FVector Velocity = FVector::ZeroVector;
	float AimYaw = 0.f, AimPitch = 0.f;
	float TorsoYawRel = 0.f;
	bool bSprint = false;

	float GaitPhase = 0.f;      // 0..1 per full two-step cycle
	float GaitAmp = 0.f;        // smoothed speed ratio
	float PrevGaitPhase = 0.f;
	float PelvisBob = 0.f;

	// cockpit camera state (two-layer motion: stabilized world, swaying cockpit)
	FVector CamPos = FVector::ZeroVector;
	FRotator CamRot = FRotator::ZeroRotator;
	FVector SwayOffset = FVector::ZeroVector, SwayVel = FVector::ZeroVector;
	FRotator SwayRot = FRotator::ZeroRotator;
	FVector SwayRotVel = FVector::ZeroVector;   // (roll, pitch, yaw) rates
	FVector PrevVelocity = FVector::ZeroVector;

	TArray<TObjectPtr<UMaterialInstanceDynamic>> BodyMIDs;
};

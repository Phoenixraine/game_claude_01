// IMPACT VECTOR - articulated mech pawn (grey-box).
// Joint hierarchy mirrors the bone contract of docs/tasks/TASK-002 so that the real BASTION-01 mesh can replace the blockout.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "IVRigAnim.h"
#include "iv/Anim.h"
#include "iv/Events.h"
#include "IVCockpit.h"
#include "IVMechPawn.generated.h"

class UCapsuleComponent;
class USceneComponent;
class UStaticMeshComponent;
class UCameraComponent;
class UMaterialInstanceDynamic;
class USkeletalMeshComponent;
class UIVRigAnimInstance;
class UProceduralMeshComponent;

DECLARE_MULTICAST_DELEGATE_TwoParams(FIVFootfallSignature, int32 /*Side: -1 left, +1 right*/, float /*Strength 0..1*/);
class AIVMechPawn;
DECLARE_MULTICAST_DELEGATE_TwoParams(FIVCrashSignature, AIVMechPawn*, float /*Strength 0..1*/);

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

	/** Plays a named pose sequence on the upper body, e.g. "swing_up_r" (windup/commit/strike_end/recovery), "block_up" or "dodge_left". */
	void PlayAction(FName Action, float Speed = 1.f);
	bool IsRigged() const { return bRigActive; }
	float GetActionWeight() const { return ActionWeight; }

	/** Tints all grey-box parts (used to differentiate the enemy). */
	void SetBodyTint(const FLinearColor& Tint);
	/** Skeletal mesh asset of this mech (set before BeginPlay); generated hulls get the M_MechHull material. */
	FString RigAssetPath = TEXT("/Game/Mechs/Player/PLAYER_01.PLAYER_01");
	bool bUseHullMaterial = true;
	/** Infected variant: mutations burst out of the armour (spikes, glowing tumours); they swell as the zone underneath is damaged. */
	bool bInfected = false;
	FLinearColor HullTint = FLinearColor(0.045f, 0.065f, 0.105f);
	FLinearColor HullAccent = FLinearColor(0.85f, 0.26f, 0.025f);
	FLinearColor HullGlow = FLinearColor(0.5f, 2.4f, 7.0f);
	float HullAccentAmount = 1.3f;
	/** Blade edge colour (cyan for the player, red for the enemy). */
	FLinearColor SwordEdge = FLinearColor(0.35f, 1.4f, 3.0f);
	FLinearColor LampColor = FLinearColor(0.75f, 0.88f, 1.f);
	float LampPower = 1.f;       // 1 = the player's key light, small values for the opponent's rim lamps
	bool bLampsDown = false;     // aim the lamps at the ground instead of at the opponent
	/** World-space ends of the blade (grip and tip) for trails, clashes and hit tests. */
	void GetBladeSegment(FVector& OutBase, FVector& OutTip) const;
	void SetSwordHeat(float Heat);
	/** Weapon / debris status effects laid on this mech by the core (blind, strike lock, burn). */
	void OnStatus(iv::StatusKind K, bool bOn, float Seconds);
	float GetBlind01() const { return BlindTotal > 0.f ? FMath::Clamp(BlindLeft / BlindTotal, 0.f, 1.f) : 0.f; }
	bool IsBurning() const { return bBurning; }
	bool IsStrikeLocked() const { return bStrikeLocked; }
	/** Chain of explosions on the loser, ending with a burning wreck. */
	void StartDeathSequence();
	/** Plays a custom list of poses on the upper body (names from the pose library, durations in seconds). */
	void PlaySequence(const TArray<FName>& Poses, const TArray<float>& Durations);
	/** Ultimate choreography: punch under the chest, jump, chop on the head. Mode 0 plain, 1 cut in half, 2 sever the off-hand arm. */
	void StartUltimateScript(AIVMechPawn* Victim, int32 Mode);
	bool IsUltimateScripted() const { return Ult.bActive; }
	/** Fresh match: unhide limbs, clear damage visuals / statuses, stop all motion. */
	void ResetForNewMatch();
	void ResetMotion();
	bool IsDying() const { return bDying; }
	/** 0..1 visible battle damage (soot, embers) on the hull material. */
	void SetHullDamage(float Amount);
	/** Hide parts that would block the first-person view. */
	void SetFirstPersonView(bool bFirstPerson);
	/** Re-reads the player's settings (field of view, shake, infection...). */
	void ApplySettings();
	/** The off hand raises and launches a rocket salvo (after a parry): drives the left-arm pose overlay. */
	void StartRocketArm() { RocketArmT = 0.001f; }
	/** Boarding defence: the free hand rises and comes down on the shoulder where the enemy pilot sits. U 0..1 follows the telegraph; 0 = none. */
	void SetSlap(float U, bool bRightShoulderTarget) { SlapU = U; bSlapRight = bRightShoulderTarget; }
	/** The pilot is outside and lies stunned: the empty mech slumps (kneeling, lights low). */
	void SetPoweredDown(bool b) { bPoweredDown = b; }
	bool IsSlapRight() const { return bSlapRight; }
	float GetHeadWorldZ() const;

	// ---- combat presentation (driven by AIVCombatDirector) ----
	void SetCombatAnim(const iv::AnimState& S) { CombatAnim = S; bCombat = true; }
	void SetMovementLocked(bool b) { bMoveLocked = b; }
	void SetExternalControl(bool b) { bExternalControl = b; }
	void AddVelocityImpulse(const FVector& V) { Velocity += V; }
	void OnCombatHit(iv::Zone Z, float Strength01, bool bBlocked, bool bParried, iv::SwingSide Dir);
	void OnDefenceEffect(bool bParry, bool bIntercept);
	void OnZoneState(iv::Zone Z, iv::ZoneState NewState, iv::ZoneState OldState);
	void OnLimbSevered(iv::Zone Z);
	void OnArmorPlateLost(iv::Zone Z, int32 Index, int32 Count);
	void AddCockpitImpulse(float Right, float Up, float Strength);
	/** Free look inside the cockpit (hold the key): the head turns, the room stays. Pitch down far enough to see the pilot's own body. */
	void SetFreeLook(bool b) { bFreeLook = b; }
	/** The opponent's head lamps: dim and aimed at the ground for the AI mech, the full key light for a second human pilot. */
	void SetPlayerLamps(bool bOn);
	bool IsFreeLook() const { return bFreeLook; }
	void AddLook(float DYaw, float DPitch) { LookYawT = FMath::Clamp(LookYawT + DYaw, -115.f, 115.f); LookPitchT = FMath::Clamp(LookPitchT + DPitch, -82.f, 58.f); }
	float GetLookAmount() const { return FMath::Max(FMath::Abs(LookYaw) / 40.f, FMath::Abs(LookPitch) / 28.f); }
	UIVCockpitComponent* GetCockpitFx() const { return CockpitFx; }
	void SetCockpitFeed(const FIVCockpitFeed& F) { if (CockpitFx) CockpitFx->SetFeed(F); }
	// v5 presentation
	void SetRage(float R) { RageTarget = R; }
	float GetRage() const { return Rage; }
	void PlayBerserkSwing(iv::SwingSide Side);
	void StartCounterPunch(AIVMechPawn* Victim);
	void StartLockPose(bool bOn);
	float GetAirLift() const { return AirLift; }
	void StartCinematic(AIVMechPawn* Subject, float Seconds, int32 Kind);
	void StopCinematic();
	bool IsInCinematic() const { return bCine; }
	/** Outside camera while the pilot is on the grapple (boarding). */
	void SetBoardCam(bool bOn, const FVector& From, const FVector& At, float Fov) { bBoardCam = bOn; BoardFrom = From; BoardAt = At; BoardFov = Fov; }
	FVector GetZoneWorldLocation(iv::Zone Z) const;
	iv::ZoneState GetZoneState(iv::Zone Z) const { return ZoneStates[iv::Index(Z)]; }
	const iv::AnimState& GetCombatAnim() const { return CombatAnim; }

	FIVFootfallSignature OnFootfall;
	FIVCrashSignature OnCrash;
	float CrashCooldown = 0.f;

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
	void UpdateCockpitArms(float Dt);

	/** Pilot-scale arm rig in the cockpit (two-bone chain from a wall anchor to a glove that follows the mech hand). */
	struct FCockpitArm
	{
		UStaticMeshComponent* Upper = nullptr;
		UStaticMeshComponent* Fore = nullptr;
		UStaticMeshComponent* Glove = nullptr;
		FVector NeutralRel = FVector::ZeroVector;
		FQuat NeutralRot = FQuat::Identity;
		bool bHaveNeutral = false;
		FVector Smoothed = FVector::ZeroVector;
		FQuat SmoothedRot = FQuat::Identity;
	};
	FCockpitArm CockpitArm[2];   // 0 = left, 1 = right
	UPROPERTY() TObjectPtr<UStaticMeshComponent> CockpitShellMesh;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> CockpitGlassMesh;
	UPROPERTY() TArray<TObjectPtr<class UPointLightComponent>> CockpitLights;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> CockpitMID;
	UPROPERTY() TObjectPtr<UIVCockpitComponent> CockpitFx;
	bool bFreeLook = false, bDebugLook = false, bDebugFailDone = false;
	float LookYaw = 0.f, LookPitch = 0.f, LookYawT = 0.f, LookPitchT = 0.f;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> GlassMID;
	float GlassCrack = 0.f;

	void UpdateLocomotion(float Dt);
	void UpdateRig(float Dt);
	void SetupRig();
	void UpdateGait(float Dt);
	void UpdateCockpitCamera(float Dt);
	void UpdateAI(float Dt);

	FVector MoveIntentToWorld() const;

	FVector2D MoveIntent = FVector2D::ZeroVector;
	FVector Velocity = FVector::ZeroVector;
	float AimYaw = 0.f, AimPitch = 0.f;
	float RocketArmT = 0.f;
	float SlapU = 0.f, SlapSm = 0.f, SlapPrev = 0.f, SlapHoldT = 0.f;
	iv::Posture PrevPostureC = iv::Posture::Standing;
	float DodgeCamYaw = 0.f;   // the pilot's head turns with the body during a dodge
	float GetUpT = -1.f;   // > 0 while the mech rises from a stagger / knock-down: slow, no hop
	bool bSlapRight = true, bPoweredDown = false;
	float SetFov = 98.f, SetShake = 1.f, SetMinSep = 5000.f;
	float TorsoYawRel = 0.f;
	bool bSprint = false;

	// combat state
	iv::AnimState CombatAnim;
	bool bCombat = false;
	bool bMoveLocked = false;
	bool bExternalControl = false;
	iv::ZoneState ZoneStates[iv::kZoneCount] = {};
	FIVPoseAngles CombatPose;          // smoothed upper-body pose target
	bool bCombatPoseInit = false;
	FVector HitKick = FVector::ZeroVector;      // decaying torso kick (rx, ry, rz degrees)
	TWeakObjectPtr<AIVMechPawn> CineSubject;
	bool bCine = false;
	bool bBoardCam = false;
	FVector BoardFrom = FVector::ZeroVector, BoardAt = FVector::ZeroVector;
	float BoardFov = 60.f;
	float CineT = 0.f, CineDur = 0.f;
	int32 CineKind = 0;
	void BuildCombatPose(FIVPoseAngles& InOut, float Dt);

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

	// ---- rigged mesh driven by the anim library
	UPROPERTY() TObjectPtr<USkeletalMeshComponent> RigMesh;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> HullMID;
	struct FIVGrowth { TObjectPtr<UStaticMeshComponent> C; iv::Zone Z = iv::Zone::Torso; FVector Full = FVector::OneVector; float Phase = 0.f, Cur = 0.f; bool bTumor = false; };
	TArray<FIVGrowth> Growths;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> GrowthMID;
	UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> GrowthComps;
	void BuildGrowths();
	void BuildGreebles();
	void BuildPlates();
	struct FIVPlate { TObjectPtr<UStaticMeshComponent> C; iv::Zone Z = iv::Zone::Torso; FVector Size = FVector::OneVector; bool bGone = false; };
	TArray<FIVPlate> Plates;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> PlateMID;
	void UpdateBladeContact(float Dt, FIVPoseAngles& Pose);
	float BladeBlock = 0.f, BladeBlockHold = 0.f;
	float ContactSparkCool = 0.f, ContactSoundCool = 0.f;
	bool bWasTouching = false;
	/** Sparks, flash and clang where the blade meets the other blade (bBlade) or the other body. */
	void EmitContactSparks(const FVector& At, bool bBlade, float Strength);
TMap<FName, FVector> CombatVel;       // joint velocities of the spring-driven combat pose (weight and follow-through)
float SwingWeightPitch = 0.f, SwingWeightYaw = 0.f, PelvisDip = 0.f;
	TWeakObjectPtr<AIVMechPawn> OtherMechCache;
	UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> GreebleComps;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> GreebleMID;
	void UpdateGrowths(float Dt);

	// ---- head lamps (motivated key light on the opponent, volumetric beams in the fog)
	UPROPERTY() TObjectPtr<class USpotLightComponent> HeadLamp[2];

	// ---- ultimate choreography and the parts it tears off
	struct FUltScript { bool bActive = false; float T = 0.f; TWeakObjectPtr<AIVMechPawn> Victim; int32 Mode = 0; bool bImpact = false; bool bPushed = false; } Ult;
	struct FDetached
	{
		TObjectPtr<USkeletalMeshComponent> Comp;
		TObjectPtr<UMaterialInstanceDynamic> MID;
		FTransform T0;                 // component transform when it was cut loose
		FVector Pivot = FVector::ZeroVector;
		FVector Vel = FVector::ZeroVector;
		FVector Spin = FVector::ZeroVector;   // deg/s
		FVector ClipO = FVector::ZeroVector, ClipN = FVector::ZeroVector;
		float T = 0.f, Roll = 0.f;
		int32 Kind = 0;                // 0 half, 1 arm
		bool bRest = false;
		bool bFollow = true;
	};
	TArray<FDetached> Detached;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> SwordDrop;
	FVector BodyOffset = FVector::ZeroVector;
	void SetBodyOffset(const FVector& LocalOffset);
	void UpdateUltimateScript(float Dt);
	void UpdateDetached(float Dt);
	void SplitInHalves();
	void SeverOffArm();
	void ClearDetached();
	USkeletalMeshComponent* MakeCloneRig(UMaterialInterface* Mat, TObjectPtr<UMaterialInstanceDynamic>& OutMID, bool bClip);

	// ---- status effects and damage visuals
	float BlindLeft = 0.f, BlindTotal = 1.f;
	bool bBurning = false, bStrikeLocked = false, bDying = false;
	float DeathT = 0.f, FxAcc[iv::kZoneCount + 2] = {};
	void UpdateDamageFX(float Dt);
	void UpdateV5Fx(float Dt);
	float ShakeAmp = 0.f;
	float Rage = 0.f, RageTarget = 0.f, AirLift = 0.f, JetAcc = 0.f, LungeFxAcc = 0.f;
	void RefreshHullDamage();

	// ---- blade trail (ribbon behind the swinging sword)
	UPROPERTY() TObjectPtr<UProceduralMeshComponent> BladeTrail;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> TrailMID;
	struct FTrailSample { FVector Mid, Tip; float Time; };
	TArray<FTrailSample> TrailSamples;
	FVector PrevTip = FVector::ZeroVector;
	void UpdateBladeTrail(float Dt);

	// ---- the duel sword (right hand)
	UPROPERTY() TObjectPtr<UStaticMeshComponent> SwordMesh;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> SwordMID;
	FQuat SwordRelRot = FQuat::Identity;
	FVector SwordBladeDirLocal = FVector(0, 0, -1);   // blade direction in the hand bone's frame
	UPROPERTY() TObjectPtr<UIVRigAnimInstance> RigAnim;
	TSharedPtr<FIVRigData> RigData;
	FIVRigDriver RigDriver;
	bool bRigActive = false;
	float RigClipTime = 0.f;
	bool bPrevContactL = true, bPrevContactR = true;

	struct FActionStep { FName Pose; float Duration; };
	TArray<FActionStep> ActionSteps;
	int32 ActionIndex = -1;
	float ActionTimer = 0.f;
	float ActionWeight = 0.f;
	FIVPoseAngles ActionFrom;
};

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "InputActionValue.h"
#include "iv/Types.h"
#include "IVPlayerController.generated.h"

class UInputAction;
class UInputMappingContext;
class AIVMechPawn;
class AIVCombatDirector;

/**
 * Builds its Enhanced Input assets in code (no editor assets needed) and drives the possessed mech.
 *
 * Controls (keyboard + mouse | gamepad):
 *   WASD / left stick = walk, Shift / L3 = sprint, mouse / right stick = look (free) or the sword vector (while a button is held)
 *   LMB hold + move the mouse + release = heavy sword stroke along the drawn vector | RT + right stick   (a quick tap = left-fist jab)
 *   RMB = guard, the mouse picks the sector; Ctrl while guarding = hard stance | LT (+ D-pad down)
 *   Q / E = sidestep left / right (beats lateral slashes only, opens a counter) | LB / RB
 *   1 = rockets (blind)   2 = rail lance (jams the arms)   3 = plasma (burns)   hold to charge, release to fire | D-pad up / left / right
 *   F = scoop a building and throw it in the opponent's face | A     G = grab | X     C / R = cancel / reverse | B
 *   V = ultimate | Y     arrows = power priority     Tab = lock-on | R3     Enter = restart     Esc = menu
 */
/** DbD-style below-deck repair: hold to work, and hit the skill checks that pop up. */
struct FIVRepairGame
{
	bool bActive = false, bWorking = false, bCheck = false;
	float Progress = 0.f, Time = 0.f, TimeLimit = 22.f;
	float Needle = 0.f, NeedleSpeed = 240.f, ZoneStart = 0.f, ZoneLen = 54.f, GreatLen = 12.f;
	float NextCheck = 1.2f, FlashGood = 0.f, FlashBad = 0.f, Cooldown = 0.f, RepairedMark = 0.f;
	int32 Level = 1;
};

UCLASS()
class IMPACTVECTOR_API AIVPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	virtual void BeginPlay() override;
	virtual void SetupInputComponent() override;
	virtual void PlayerTick(float DeltaTime) override;

	void ApplySettings();
	float RumbleScale = 1.f;
	float LookSensitivity = 0.11f;      // deg per mouse count
	float StickLookRate = 95.f;         // deg/s at full deflection
	float VectorSensitivity = 0.0045f;  // mouse counts -> virtual stick units

	FVector2D GetCombatStick() const { return Stick; }
	bool IsLockOn() const { return bLockOn; }
	void SetCombatEnabled(bool bOn) { bCombatEnabled = bOn; if (!bOn) { Stick = FVector2D::ZeroVector; } }
	bool IsCombatEnabled() const { return bCombatEnabled; }
	bool IsStrikeDown() const { return bStrikeWasDown; }
	/** The path drawn with the mouse / right stick while a strike or guard button is held (virtual stick units, -1..1), for the HUD. */
	const TArray<FVector2D>& GetTrail() const { return Trail; }
	float GetTrailFade() const { return FMath::Clamp(1.f - TrailAge / 1.1f, 0.f, 1.f); }
	bool IsTrailLive() const { return bStrikeWasDown || bGuardWasDown; }
	bool IsTrailGuard() const { return bTrailGuard; }
	bool bTrailGuard = false;
	iv::SwingSide GetTrailSide() const { return CurSide; }

private:
	UPROPERTY() TObjectPtr<UInputMappingContext> Mapping;
	UPROPERTY() TObjectPtr<UInputAction> MoveAction;
	UPROPERTY() TObjectPtr<UInputAction> LookAction;
	UPROPERTY() TObjectPtr<UInputAction> SprintAction;
	UPROPERTY() TObjectPtr<UInputAction> FireAction;
	TWeakObjectPtr<AIVCombatDirector> Director;

	void OnMove(const FInputActionValue& V) { MoveValue = V.Get<FVector2D>(); }
	void OnMoveEnd(const FInputActionValue&) { MoveValue = FVector2D::ZeroVector; }
	void OnLook(const FInputActionValue& V);
	void OnSprint(const FInputActionValue& V) { bSprint = V.Get<bool>(); }
	void OnFire(const FInputActionValue&);
	void DoAction(FName N);
	void OnAct1() { DoAction(TEXT("swing_up_r")); }
	void OnAct2() { DoAction(TEXT("swing_right_r")); }
	void OnAct3() { DoAction(TEXT("swing_left_l")); }
	void OnAct4() { DoAction(TEXT("block_up")); }
	void OnAct5() { DoAction(TEXT("dodge_left")); }
	void OnAct6() { DoAction(TEXT("quick_piston_r")); }

public:
	bool WantsFreeLook() const;
	bool IsRepairing() const { return Repair.bActive; }
	const FIVRepairGame& GetRepair() const { return Repair; }
	FVector2D GetBerserkAim() const { return BerserkAim; }
	void SetLockOn(bool b) { bLockOn = b; LockOffYaw = LockOffPitch = 0.f; }
	/** Gamepad vibration (large + small motor), Strength 0..1. */
	void Rumble(float Strength, float Seconds);
	bool bRumbleEnabled = true;
	void StartRepair();
	void StopRepair(bool bSuccess);
	void UpdateRepair(float Dt);
	FIVRepairGame Repair;
	/** The side this controller plays in the duel (split screen: the second pad plays side B). */
	iv::Side MySide = iv::Side::A;
	FVector2D BerserkAim = FVector2D::ZeroVector;
	bool bPadStrikePrev = false;
	bool bScriptLunge = false, bScriptHold = false, bScriptPress = false;
private:
	AIVMechPawn* Mech() const;
	AIVCombatDirector* GetDirector();
	void UpdateCombatInput(float Dt);
	static iv::SwingSide SideFromStick(const FVector2D& S);
	static iv::Zone ZoneFromStick(const FVector2D& S);

	FVector2D MoveValue = FVector2D::ZeroVector;
	FVector2D LookStick = FVector2D::ZeroVector;
	FVector2D Stick = FVector2D::ZeroVector;     // virtual right stick (combat vector)
	bool bSprint = false;
	float AutoTime = 0.f;
	bool bAuto = false;
	bool bCombatEnabled = true;

	// combat input state
	bool bLockOn = true;
	float LockOffYaw = 0.f, LockOffPitch = 0.f;
	float StrikeHeldTime = 0.f;
	bool bStrikeWasDown = false;
	bool bSideLocked = false;
	iv::SwingSide CurSide = iv::SwingSide::Up;
	iv::SwingSide CurGuardSide = iv::SwingSide::Up;
	iv::Arm CurArm = iv::Arm::R;
	int8 LastStrafe = 1;
	TArray<FVector2D> Trail;
	float TrailAge = 10.f;
	bool bGuardWasDown = false;

	// scripted input for automated tests (-IVScript=strike=1@12;stick=-0.5,0.6@12.1;strike=0@13): bypasses the OS input entirely
	struct FScriptCmd { float T; FString Name; FString Arg; bool bDone = false; };
	TArray<FScriptCmd> ScriptCmd;
	float ScriptTime = 0.f;
	bool bScriptStrike = false, bScriptGuard = false, bScriptStick = false;
	FVector2D ScriptStickVal = FVector2D::ZeroVector;
	int32 ScriptWeapon = -1;
	void RunScript(float Dt);
};

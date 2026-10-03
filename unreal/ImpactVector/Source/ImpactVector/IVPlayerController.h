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
 * Combat controls (keyboard + mouse | gamepad):
 *   LMB tap = quick strike, LMB hold + release = heavy strike | RT
 *   mouse while LMB/RMB held = the "Combat Vector" stick (first flick = swing family, then body sector = target) | right stick
 *   RMB = guard (mouse picks the sector; press again at the right moment to parry) | LT
 *   E = hard stance | Y      Space (+A/D) = dodge | A     C = cancel | B     F = grab | X
 *   Q = switch arm | RB      R = reverse reply | RB      G (hold/release) = heavy weapon | Y      V = ultimate | R3
 *   1-4 = power priority (arms/legs/guard/weapon) | d-pad     Tab = lock-on on/off | LB     Enter = restart the match
 */
UCLASS()
class IMPACTVECTOR_API AIVPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	virtual void BeginPlay() override;
	virtual void SetupInputComponent() override;
	virtual void PlayerTick(float DeltaTime) override;

	float LookSensitivity = 0.11f;      // deg per mouse count
	float StickLookRate = 95.f;         // deg/s at full deflection
	float VectorSensitivity = 0.0045f;  // mouse counts -> virtual stick units

	FVector2D GetCombatStick() const { return Stick; }
	bool IsLockOn() const { return bLockOn; }
	bool IsStrikeDown() const { return bStrikeWasDown; }

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
};

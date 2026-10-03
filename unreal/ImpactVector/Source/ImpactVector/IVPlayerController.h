#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "InputActionValue.h"
#include "IVPlayerController.generated.h"

class UInputAction;
class UInputMappingContext;
class AIVMechPawn;

/** Builds its Enhanced Input assets in code (no editor assets needed) and drives the possessed mech. */
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

private:
	UPROPERTY() TObjectPtr<UInputMappingContext> Mapping;
	UPROPERTY() TObjectPtr<UInputAction> MoveAction;
	UPROPERTY() TObjectPtr<UInputAction> LookAction;
	UPROPERTY() TObjectPtr<UInputAction> SprintAction;

	void OnMove(const FInputActionValue& V) { MoveValue = V.Get<FVector2D>(); }
	void OnMoveEnd(const FInputActionValue&) { MoveValue = FVector2D::ZeroVector; }
	void OnLook(const FInputActionValue& V);
	void OnSprint(const FInputActionValue& V) { bSprint = V.Get<bool>(); }

	AIVMechPawn* Mech() const;

	FVector2D MoveValue = FVector2D::ZeroVector;
	FVector2D LookStick = FVector2D::ZeroVector;
	bool bSprint = false;
	float AutoTime = 0.f;
	bool bAuto = false;
};

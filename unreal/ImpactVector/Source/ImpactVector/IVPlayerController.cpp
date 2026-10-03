#include "IVPlayerController.h"
#include "IVMechPawn.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "InputMappingContext.h"
#include "InputAction.h"
#include "InputModifiers.h"
#include "Misc/CommandLine.h"

AIVMechPawn* AIVPlayerController::Mech() const
{
	return Cast<AIVMechPawn>(GetPawn());
}

void AIVPlayerController::BeginPlay()
{
	Super::BeginPlay();
	bAuto = FParse::Param(FCommandLine::Get(), TEXT("IVAuto"));
	SetInputMode(FInputModeGameOnly());
	bShowMouseCursor = false;
	if (AIVMechPawn* M = Mech())
	{
		M->SetFirstPersonView(true);
	}
}

void AIVPlayerController::SetupInputComponent()
{
	Super::SetupInputComponent();

	Mapping = NewObject<UInputMappingContext>(this, TEXT("IMC_Mech"));

	MoveAction = NewObject<UInputAction>(this, TEXT("IA_Move"));
	MoveAction->ValueType = EInputActionValueType::Axis2D;
	LookAction = NewObject<UInputAction>(this, TEXT("IA_Look"));
	LookAction->ValueType = EInputActionValueType::Axis2D;
	SprintAction = NewObject<UInputAction>(this, TEXT("IA_Sprint"));
	SprintAction->ValueType = EInputActionValueType::Boolean;

	// Move: WASD (X = right, Y = forward) and gamepad left stick
	auto Key2D = [this](const FKey& K, bool bSwizzle, bool bNegate)
	{
		FEnhancedActionKeyMapping& M = Mapping->MapKey(MoveAction, K);
		if (bSwizzle) M.Modifiers.Add(NewObject<UInputModifierSwizzleAxis>(this));
		if (bNegate) M.Modifiers.Add(NewObject<UInputModifierNegate>(this));
	};
	Key2D(EKeys::W, true, false);
	Key2D(EKeys::S, true, true);
	Key2D(EKeys::D, false, false);
	Key2D(EKeys::A, false, true);
	Mapping->MapKey(MoveAction, EKeys::Gamepad_Left2D);

	Mapping->MapKey(LookAction, EKeys::Mouse2D);
	Mapping->MapKey(LookAction, EKeys::Gamepad_Right2D);

	FireAction = NewObject<UInputAction>(this, TEXT("IA_Fire"));
	FireAction->ValueType = EInputActionValueType::Boolean;
	Mapping->MapKey(FireAction, EKeys::LeftMouseButton);
	Mapping->MapKey(FireAction, EKeys::Gamepad_RightTrigger);

	Mapping->MapKey(SprintAction, EKeys::LeftShift);
	Mapping->MapKey(SprintAction, EKeys::Gamepad_LeftThumbstick);

	if (UEnhancedInputLocalPlayerSubsystem* Sub = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer()))
	{
		Sub->AddMappingContext(Mapping, 0);
	}
	if (UEnhancedInputComponent* EIC = Cast<UEnhancedInputComponent>(InputComponent))
	{
		EIC->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AIVPlayerController::OnMove);
		EIC->BindAction(MoveAction, ETriggerEvent::Completed, this, &AIVPlayerController::OnMoveEnd);
		EIC->BindAction(LookAction, ETriggerEvent::Triggered, this, &AIVPlayerController::OnLook);
		EIC->BindAction(FireAction, ETriggerEvent::Started, this, &AIVPlayerController::OnFire);
		InputComponent->BindKey(EKeys::One, IE_Pressed, this, &AIVPlayerController::OnAct1);
		InputComponent->BindKey(EKeys::Two, IE_Pressed, this, &AIVPlayerController::OnAct2);
		InputComponent->BindKey(EKeys::Three, IE_Pressed, this, &AIVPlayerController::OnAct3);
		InputComponent->BindKey(EKeys::Four, IE_Pressed, this, &AIVPlayerController::OnAct4);
		InputComponent->BindKey(EKeys::Five, IE_Pressed, this, &AIVPlayerController::OnAct5);
		InputComponent->BindKey(EKeys::Six, IE_Pressed, this, &AIVPlayerController::OnAct6);
		EIC->BindAction(SprintAction, ETriggerEvent::Triggered, this, &AIVPlayerController::OnSprint);
		EIC->BindAction(SprintAction, ETriggerEvent::Completed, this, &AIVPlayerController::OnSprint);
	}
}

void AIVPlayerController::OnLook(const FInputActionValue& V)
{
	const FVector2D L = V.Get<FVector2D>();
	// Mouse2D delivers per-frame deltas, the gamepad stick a deflection: distinguish by the active key magnitude
	if (AIVMechPawn* M = Mech())
	{
		if (FMath::Abs(L.X) > 1.001f || FMath::Abs(L.Y) > 1.001f)
		{
			M->AddAim(L.X * LookSensitivity, L.Y * LookSensitivity);
			LookStick = FVector2D::ZeroVector;
		}
		else
		{
			LookStick = L;
		}
	}
}

void AIVPlayerController::PlayerTick(float Dt)
{
	Super::PlayerTick(Dt);
	AIVMechPawn* M = Mech();
	if (!M) return;

	FVector2D Move = MoveValue;
	bool bSpr = bSprint;
	if (bAuto)
	{
		// scripted walk for automated captures: forward, slight turn, then strafe
		AutoTime += Dt;
		Move = FVector2D(0.f, AutoTime > 0.5f ? 1.f : 0.f);
		if (AutoTime > 6.f) Move = FVector2D(0.6f, 0.4f);
		if (AutoTime > 3.f && AutoTime < 5.f) M->AddAim(10.f * Dt, 0.f);
	}
	M->SetMoveIntent(Move);
	M->SetSprint(bSpr);
	if (!LookStick.IsNearlyZero(0.05f))
	{
		M->AddAim(LookStick.X * StickLookRate * Dt, LookStick.Y * StickLookRate * Dt);
	}
}

void AIVPlayerController::OnFire(const FInputActionValue&)
{
	if (AIVMechPawn* M = Mech()) M->DebugBlast();
}

void AIVPlayerController::DoAction(FName N)
{
	if (AIVMechPawn* M = Mech()) M->PlayAction(N);
}

#include "IVPlayerController.h"
#include "IVMechPawn.h"
#include "IVCombat.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "InputMappingContext.h"
#include "InputAction.h"
#include "InputModifiers.h"
#include "Misc/CommandLine.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"

AIVMechPawn* AIVPlayerController::Mech() const
{
	return Cast<AIVMechPawn>(GetPawn());
}

AIVCombatDirector* AIVPlayerController::GetDirector()
{
	if (!Director.IsValid())
	{
		for (TActorIterator<AIVCombatDirector> It(GetWorld()); It; ++It) { Director = *It; break; }
	}
	return Director.Get();
}

void AIVPlayerController::BeginPlay()
{
	Super::BeginPlay();
	bAuto = FParse::Param(FCommandLine::Get(), TEXT("IVAuto"));
	{
		FString S;
		if (FParse::Value(FCommandLine::Get(), TEXT("-IVScript="), S, false))
		{
			TArray<FString> Items;
			S.ParseIntoArray(Items, TEXT(";"));
			for (const FString& It : Items)
			{
				FString L, R;
				if (!It.Split(TEXT("@"), &L, &R)) continue;
				FScriptCmd Cm; Cm.T = FCString::Atof(*R);
				if (!L.Split(TEXT("="), &Cm.Name, &Cm.Arg)) Cm.Name = L;
				ScriptCmd.Add(Cm);
			}
		}
	}
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

	FireAction = NewObject<UInputAction>(this, TEXT("IA_DebugBlast"));
	FireAction->ValueType = EInputActionValueType::Boolean;
	Mapping->MapKey(FireAction, EKeys::T);                 // debug: blast the point under the crosshair

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
		// pose test keys on the numpad
		InputComponent->BindKey(EKeys::NumPadOne, IE_Pressed, this, &AIVPlayerController::OnAct1);
		InputComponent->BindKey(EKeys::NumPadTwo, IE_Pressed, this, &AIVPlayerController::OnAct2);
		InputComponent->BindKey(EKeys::NumPadThree, IE_Pressed, this, &AIVPlayerController::OnAct3);
		InputComponent->BindKey(EKeys::NumPadFour, IE_Pressed, this, &AIVPlayerController::OnAct4);
		InputComponent->BindKey(EKeys::NumPadFive, IE_Pressed, this, &AIVPlayerController::OnAct5);
		InputComponent->BindKey(EKeys::NumPadSix, IE_Pressed, this, &AIVPlayerController::OnAct6);
		EIC->BindAction(SprintAction, ETriggerEvent::Triggered, this, &AIVPlayerController::OnSprint);
		EIC->BindAction(SprintAction, ETriggerEvent::Completed, this, &AIVPlayerController::OnSprint);
	}
}

// ---------------------------------------------------------------------------------------------------------------
iv::SwingSide AIVPlayerController::SideFromStick(const FVector2D& S)
{
	if (FMath::Abs(S.Y) >= FMath::Abs(S.X)) return S.Y >= 0.f ? iv::SwingSide::Up : iv::SwingSide::Down;
	return S.X >= 0.f ? iv::SwingSide::Right : iv::SwingSide::Left;
}

// Body sectors of the right stick (pitch 5.2 step 2): up = head, upper diagonals = shoulders, sides = arms,
// centre = torso, lower diagonals = legs, down = reactor (only reachable when the enemy is flanked).
iv::Zone AIVPlayerController::ZoneFromStick(const FVector2D& S)
{
	if (S.Size() < 0.45f) return iv::Zone::Torso;
	const float Ang = FMath::RadiansToDegrees(FMath::Atan2(S.X, S.Y));      // 0 = up, +90 = right
	const float A = FMath::Fmod(Ang + 360.f + 22.5f, 360.f);
	switch (FMath::FloorToInt(A / 45.f) % 8)
	{
	case 0: return iv::Zone::Head;
	case 1: return iv::Zone::ShoulderR;
	case 2: return iv::Zone::ArmR;
	case 3: return iv::Zone::LegR;
	case 4: return iv::Zone::Reactor;
	case 5: return iv::Zone::LegL;
	case 6: return iv::Zone::ArmL;
	default: return iv::Zone::ShoulderL;
	}
}

void AIVPlayerController::OnLook(const FInputActionValue& V)
{
	if (!bCombatEnabled) return;
	const FVector2D L = V.Get<FVector2D>();
	AIVMechPawn* M = Mech();
	if (!M) return;
	const bool bMouse = FMath::Abs(L.X) > 1.001f || FMath::Abs(L.Y) > 1.001f;
	const bool bVectorMode = IsInputKeyDown(EKeys::LeftMouseButton) || IsInputKeyDown(EKeys::RightMouseButton) || GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) > 0.2f || GetInputAnalogKeyState(EKeys::Gamepad_LeftTriggerAxis) > 0.2f;
	if (bMouse)
	{
		if (bVectorMode)
		{
			Stick += FVector2D(L.X, L.Y) * VectorSensitivity;
			if (Stick.Size() > 1.f) Stick = Stick.GetSafeNormal();
		}
		else if (bLockOn && GetDirector())
		{
			LockOffYaw = FMath::Clamp(LockOffYaw + L.X * LookSensitivity, -38.f, 38.f);
			LockOffPitch = FMath::Clamp(LockOffPitch + L.Y * LookSensitivity, -18.f, 18.f);
		}
		else
		{
			M->AddAim(L.X * LookSensitivity, L.Y * LookSensitivity);
		}
		LookStick = FVector2D::ZeroVector;
	}
	else
	{
		LookStick = L;      // gamepad right stick
	}
}

void AIVPlayerController::RunScript(float Dt)
{
	if (ScriptCmd.Num() == 0) return;
	ScriptTime += Dt;
	AIVCombatDirector* Dir = GetDirector();
	for (FScriptCmd& C : ScriptCmd)
	{
		if (C.bDone || ScriptTime < C.T) continue;
		C.bDone = true;
		FIVCombatInput* In = Dir ? &Dir->PlayerIn : nullptr;
		if (C.Name == TEXT("strike")) bScriptStrike = C.Arg == TEXT("1");
		else if (C.Name == TEXT("guard")) bScriptGuard = C.Arg == TEXT("1");
		else if (C.Name == TEXT("stick"))
		{
			FString A, B;
			if (C.Arg.Split(TEXT(","), &A, &B)) { ScriptStickVal = FVector2D(FCString::Atof(*A), FCString::Atof(*B)); bScriptStick = true; }
			else bScriptStick = false;
		}
		else if (C.Name == TEXT("weapon")) ScriptWeapon = FCString::Atoi(*C.Arg);
		else if (C.Name == TEXT("move")) { FString A, B; if (C.Arg.Split(TEXT(","), &A, &B)) MoveValue = FVector2D(FCString::Atof(*A), FCString::Atof(*B)); }
		else if (In && C.Name == TEXT("dodge")) { In->bDodge = true; In->DodgeDir = FCString::Atoi(*C.Arg) < 0 ? -1 : 1; }
		else if (In && C.Name == TEXT("scoop")) In->bScoop = true;
		else if (In && C.Name == TEXT("ult")) In->bUltimate = true;
		else if (In && C.Name == TEXT("cancel")) In->bCancel = true;
		else if (C.Name == TEXT("key") && C.Arg == TEXT("enter")) { /* menus are driven by the flow through real keys only */ }
	}
}

void AIVPlayerController::UpdateCombatInput(float Dt)
{
	RunScript(Dt);
	AIVCombatDirector* Dir = GetDirector();
	AIVMechPawn* M = Mech();
	if (!Dir || !M) return;
	FIVCombatInput& In = Dir->PlayerIn;

	const bool bPadStrike = GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) > 0.4f;
	const bool bPadGuard = GetInputAnalogKeyState(EKeys::Gamepad_LeftTriggerAxis) > 0.4f;
	const bool bStrikeDown = IsInputKeyDown(EKeys::LeftMouseButton) || bPadStrike || bScriptStrike;
	const bool bGuardDown = IsInputKeyDown(EKeys::RightMouseButton) || bPadGuard || bScriptGuard;
	if (bScriptStick) Stick = ScriptStickVal;

	// gamepad right stick drives the combat vector while a trigger is down
	if (bPadStrike || bPadGuard)
	{
		const FVector2D Pad(GetInputAnalogKeyState(EKeys::Gamepad_RightX), GetInputAnalogKeyState(EKeys::Gamepad_RightY));
		Stick = Pad;
		LookStick = FVector2D::ZeroVector;
	}
	if (!bStrikeDown && !bGuardDown)
	{
		Stick = FMath::Vector2DInterpTo(Stick, FVector2D::ZeroVector, Dt, 6.f);     // the virtual stick returns to centre
	}

	// ---- strike (RT / LMB): tap = quick, hold + release = heavy
	if (bStrikeDown)
	{
		StrikeHeldTime += Dt;
		if (!bStrikeWasDown) { bSideLocked = false; CurSide = iv::SwingSide::Up; Stick = FVector2D::ZeroVector; }
		if (!bSideLocked && Stick.Size() > 0.5f) { CurSide = SideFromStick(Stick); bSideLocked = true; }
	}
	const bool bJustReleased = bStrikeWasDown && !bStrikeDown;
	if (bJustReleased && StrikeHeldTime <= 0.18f)
	{
		In.bQuick = true;                 // short press = quick strike on the family chosen by the first flick
		In.Side = bSideLocked ? CurSide : iv::SwingSide::Up;
		In.Target = ZoneFromStick(Stick);
	}
	In.bStrikeHeld = bStrikeDown && StrikeHeldTime > 0.18f;
	In.Side = In.bQuick ? In.Side : CurSide;
	In.Target = In.bQuick ? In.Target : (bSideLocked ? ZoneFromStick(Stick) : iv::Zone::Torso);
	if (!bStrikeDown) StrikeHeldTime = 0.f;
	bStrikeWasDown = bStrikeDown;

	// ---- footwork from the movement keys while striking
	const float Fwd = MoveValue.Y, Str = MoveValue.X;
	In.Footwork = Fwd > 0.4f ? iv::Footwork::StepIn : (Fwd < -0.4f ? iv::Footwork::StepBack : (FMath::Abs(Str) > 0.4f ? iv::Footwork::Turn : iv::Footwork::Hold));
	In.Move = Fwd > 0.3f ? 1 : (Fwd < -0.3f ? -1 : 0);
	if (FMath::Abs(Str) > 0.3f) LastStrafe = Str > 0.f ? 1 : -1;

	// ---- arm: the heavy stroke is the sword hand (right); a tap is a jab with the left fist
	In.Arm = In.bQuick ? iv::Arm::L : iv::Arm::R;

	// ---- guard (LT / RMB)
	In.bGuardHeld = bGuardDown;
	if (bGuardDown && Stick.Size() > 0.4f) CurGuardSide = SideFromStick(Stick);
	In.GuardSide = CurGuardSide;
	In.bHardStance = bGuardDown && (IsInputKeyDown(EKeys::LeftControl) || IsInputKeyDown(EKeys::Gamepad_DPad_Down));

	// ---- sidesteps (beat lateral slashes only) and the other edges
	if (WasInputKeyJustPressed(EKeys::Q) || WasInputKeyJustPressed(EKeys::Gamepad_LeftShoulder)) { In.bDodge = true; In.DodgeDir = -1; }
	if (WasInputKeyJustPressed(EKeys::E) || WasInputKeyJustPressed(EKeys::Gamepad_RightShoulder)) { In.bDodge = true; In.DodgeDir = 1; }
	if (WasInputKeyJustPressed(EKeys::C) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right)) In.bCancel = true;
	if (WasInputKeyJustPressed(EKeys::G) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Left)) In.bGrab = true;
	if (WasInputKeyJustPressed(EKeys::R) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right)) In.bReverse = true;
	if (WasInputKeyJustPressed(EKeys::V) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Top)) In.bUltimate = true;
	if (WasInputKeyJustPressed(EKeys::F) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom)) In.bScoop = true;

	// ---- long-cooldown abilities: press selects, hold charges, release fires
	const bool bK1 = IsInputKeyDown(EKeys::One) || IsInputKeyDown(EKeys::Gamepad_DPad_Up);
	const bool bK2 = IsInputKeyDown(EKeys::Two) || IsInputKeyDown(EKeys::Gamepad_DPad_Left);
	const bool bK3 = IsInputKeyDown(EKeys::Three) || IsInputKeyDown(EKeys::Gamepad_DPad_Right);
	if (WasInputKeyJustPressed(EKeys::One) || WasInputKeyJustPressed(EKeys::Gamepad_DPad_Up)) In.WeaponSelect = 1;
	if (WasInputKeyJustPressed(EKeys::Two) || WasInputKeyJustPressed(EKeys::Gamepad_DPad_Left)) In.WeaponSelect = 0;
	if (WasInputKeyJustPressed(EKeys::Three) || WasInputKeyJustPressed(EKeys::Gamepad_DPad_Right)) In.WeaponSelect = 2;
	In.bWeaponHeld = bK1 || bK2 || bK3 || ScriptWeapon >= 0;
	if (ScriptWeapon >= 0 && In.WeaponSelect < 0) { static const int8 Map[3] = { 1, 0, 2 }; In.WeaponSelect = Map[FMath::Clamp(ScriptWeapon - 1, 0, 2)]; }
	if (WasInputKeyJustPressed(EKeys::Up))    { In.Priority = iv::EnergyPriority::Arms;   In.bSetPriority = true; }
	if (WasInputKeyJustPressed(EKeys::Left))  { In.Priority = iv::EnergyPriority::Legs;   In.bSetPriority = true; }
	if (WasInputKeyJustPressed(EKeys::Down))  { In.Priority = iv::EnergyPriority::Guard;  In.bSetPriority = true; }
	if (WasInputKeyJustPressed(EKeys::Right)) { In.Priority = iv::EnergyPriority::Weapon; In.bSetPriority = true; }

	// ---- the drawn vector, kept for the HUD
	if (bStrikeDown || bGuardDown)
	{
		if (!bStrikeWasDown && !bGuardWasDown) Trail.Reset();
		if (Trail.Num() == 0 || FVector2D::Distance(Trail.Last(), Stick) > 0.015f) Trail.Add(Stick);
		TrailAge = 0.f;
	}
	else
	{
		TrailAge += Dt;
		if (TrailAge > 0.6f) Trail.Reset();
	}
	bGuardWasDown = bGuardDown;

	if (WasInputKeyJustPressed(EKeys::Tab) || WasInputKeyJustPressed(EKeys::Gamepad_RightThumbstick)) { bLockOn = !bLockOn; LockOffYaw = LockOffPitch = 0.f; }
	if (WasInputKeyJustPressed(EKeys::Enter) && Dir->IsMatchOver()) Dir->Restart();
}

void AIVPlayerController::PlayerTick(float Dt)
{
	Super::PlayerTick(Dt);
	AIVMechPawn* M = Mech();
	if (!M) return;

	FVector2D Move = bCombatEnabled ? MoveValue : FVector2D::ZeroVector;
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

	AIVCombatDirector* Dir = GetDirector();
	if (Dir && !bAuto && bCombatEnabled)
	{
		UpdateCombatInput(Dt);
		if (bLockOn && Dir->GetDuel() && !Dir->IsMatchOver())
		{
			// lock-on: aim follows the opponent; the mouse only offsets the view a little, which eases back
			for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It)
			{
				if (*It == M) continue;
				const FVector To = (It->GetActorLocation() + FVector(0, 0, 3800.f)) - M->GetEyeLocation();
				const FRotator R = To.Rotation();
				M->SetAim(R.Yaw + LockOffYaw, R.Pitch + LockOffPitch);
				break;
			}
			const float Back = FMath::Exp(-1.8f * Dt);
			LockOffYaw *= Back; LockOffPitch *= Back;
		}
	}
	if (!LookStick.IsNearlyZero(0.05f) && !(Dir && (IsInputKeyDown(EKeys::Gamepad_RightTriggerAxis) || GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) > 0.2f)))
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

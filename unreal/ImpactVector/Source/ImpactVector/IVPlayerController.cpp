#include "IVPlayerController.h"
#include "IVSettings.h"
#include "IVMechPawn.h"
#include "IVCombat.h"
#include "IVAudio.h"
#include "IVFXManager.h"
#include "GameFramework/ForceFeedbackEffect.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "InputMappingContext.h"
#include "InputAction.h"
#include "InputModifiers.h"
#include "Misc/CommandLine.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"

bool AIVPlayerController::WantsFreeLook() const
{
	return IsInputKeyDown(EKeys::Z) || IsInputKeyDown(EKeys::LeftAlt) || IsInputKeyDown(EKeys::Gamepad_Special_Left);
}

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
	ApplySettings();
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
	if (WantsFreeLook())
	{
		if (bMouse) M->AddLook(L.X * LookSensitivity, L.Y * LookSensitivity); else LookStick = L;
		return;
	}
	const bool bVectorMode = IsInputKeyDown(EKeys::LeftMouseButton) || IsInputKeyDown(EKeys::RightMouseButton) || GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) > 0.2f || GetInputAnalogKeyState(EKeys::Gamepad_LeftTriggerAxis) > 0.2f;
	if (bMouse)
	{
		BerserkAim = (BerserkAim + FVector2D(L.X, L.Y) * 0.05f).GetClampedToMaxSize(1.f);
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
		else if (In && C.Name == TEXT("board")) In->bBoard = true;
		else if (Dir && C.Name == TEXT("rocket")) Dir->FireParryRockets(MySide);
		else if (In && C.Name == TEXT("ult")) In->bUltimate = true;
		else if (In && C.Name == TEXT("cancel")) In->bCancel = true;
		else if (C.Name == TEXT("lunge")) bScriptLunge = C.Arg == TEXT("1");
		else if (C.Name == TEXT("hurt") && Dir && Dir->GetMutableDuel()) { for (int32 k = 0; k < FCString::Atoi(*C.Arg); ++k) Dir->GetMutableDuel()->ExternalHit(MySide, iv::Zone::Reactor, 40.f, 0.f, 1); }
		else if (C.Name == TEXT("repair")) StartRepair();
		else if (C.Name == TEXT("hold")) bScriptHold = C.Arg == TEXT("1");
		else if (C.Name == TEXT("press")) bScriptPress = true;
		else if (C.Name == TEXT("hit")) { if (APawn* Pw = GetPawn()) if (AIVMechPawn* Mp = Cast<AIVMechPawn>(Pw)) if (Mp->GetCockpitFx()) Mp->GetCockpitFx()->Hit(FCString::Atof(*C.Arg), FVector(0, 1, 0), false); }
		else if (In && C.Name == TEXT("jump")) In->bJump = true;
		else if (In && C.Name == TEXT("chop")) In->bChop = true;
		else if (In && C.Name == TEXT("slide")) In->bSlide = true;
		else if (In && C.Name == TEXT("mash")) In->bMash = true;
		else if (In && C.Name == TEXT("berserk")) In->bBerserk = true;
		else if (In && C.Name == TEXT("qte")) { In->bQte = true; In->Side = iv::SwingSide::Right; }
		else if (C.Name == TEXT("key") && C.Arg == TEXT("enter")) { /* menus are driven by the flow through real keys only */ }
	}
}

void AIVPlayerController::UpdateCombatInput(float Dt)
{
	RunScript(Dt);
	AIVCombatDirector* Dir = GetDirector();
	AIVMechPawn* M = Mech();
	if (!Dir || !M) return;
	FIVCombatInput& In = Dir->InputOf(MySide);

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
	if (!Repair.bActive && (WasInputKeyJustPressed(EKeys::H) || WasInputKeyJustPressed(EKeys::Gamepad_Special_Right))) StartRepair();
	if (Repair.bActive) { In = FIVCombatInput(); return; }
	const bool bPadLT = bPadGuard;
	if (WasInputKeyJustPressed(EKeys::V) || (WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Top) && !bPadLT)) In.bUltimate = true;
	if (WasInputKeyJustPressed(EKeys::F) || (WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom) && bPadLT)) In.bScoop = true;
	// ---- v5: lunge (hold B / R3), jetpack jump (Space / A), aerial chop (LMB / RT in the air), slide (X / B), sword-lock mashing, berserk (N / LT+Y)
	In.bLungeHeld = IsInputKeyDown(EKeys::B) || IsInputKeyDown(EKeys::Gamepad_RightThumbstick) || bScriptLunge;
	if (WasInputKeyJustPressed(EKeys::SpaceBar) || (WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom) && !bPadLT)) In.bJump = true;
	const bool bRtEdge = bPadStrike && !bPadStrikePrev;
	if (WasInputKeyJustPressed(EKeys::LeftMouseButton) || bRtEdge) In.bChop = true;
	if (WasInputKeyJustPressed(EKeys::X) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right)) In.bSlide = true;
	if (WasInputKeyJustPressed(EKeys::SpaceBar) || WasInputKeyJustPressed(EKeys::E) || WasInputKeyJustPressed(EKeys::Q) || WasInputKeyJustPressed(EKeys::LeftMouseButton) ||
		WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Left) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right) ||
		WasInputKeyJustPressed(EKeys::Gamepad_LeftShoulder) || WasInputKeyJustPressed(EKeys::Gamepad_RightShoulder) || bRtEdge)
		In.bMash = true;
	if (WasInputKeyJustPressed(EKeys::SpaceBar) || WasInputKeyJustPressed(EKeys::E) || WasInputKeyJustPressed(EKeys::LeftMouseButton) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom) || bRtEdge)
	{
		In.bQte = true;
		if (Dir->GetDuel() && Dir->GetDuel()->berserk().active) In.Side = BerserkAim.Size() > 0.22f ? SideFromStick(BerserkAim) : iv::SwingSide::Right;
	}
	if (WasInputKeyJustPressed(EKeys::N) || (WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Top) && bPadLT)) In.bBerserk = true;
	// boarding: J (pad LT + X) leaves the cockpit; Q / E / LB / RB leap to the other shoulder; the hatch hack uses arrows / WASD, Enter / Space / A, H / B, Backspace / X
	if (WasInputKeyJustPressed(EKeys::J) || (WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Left) && bPadLT)) In.bBoard = true;
	if (Dir->GetBoarding().Active())
	{
		if (WasInputKeyJustPressed(EKeys::Q) || WasInputKeyJustPressed(EKeys::E) || WasInputKeyJustPressed(EKeys::Gamepad_LeftShoulder) || WasInputKeyJustPressed(EKeys::Gamepad_RightShoulder)) In.bBoardSwing = true;
		if (Dir->GetBoarding().phase() == iv::BoardPhase::Hacking)
		{
			if (WasInputKeyJustPressed(EKeys::Left) || WasInputKeyJustPressed(EKeys::A) || WasInputKeyJustPressed(EKeys::Gamepad_DPad_Left)) In.HackDx = -1;
			if (WasInputKeyJustPressed(EKeys::Right) || WasInputKeyJustPressed(EKeys::D) || WasInputKeyJustPressed(EKeys::Gamepad_DPad_Right)) In.HackDx = 1;
			if (WasInputKeyJustPressed(EKeys::Up) || WasInputKeyJustPressed(EKeys::W) || WasInputKeyJustPressed(EKeys::Gamepad_DPad_Up)) In.HackDy = -1;
			if (WasInputKeyJustPressed(EKeys::Down) || WasInputKeyJustPressed(EKeys::S) || WasInputKeyJustPressed(EKeys::Gamepad_DPad_Down)) In.HackDy = 1;
			if (WasInputKeyJustPressed(EKeys::Enter) || WasInputKeyJustPressed(EKeys::SpaceBar) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom)) In.bHackConfirm = true;
			if (WasInputKeyJustPressed(EKeys::H) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right)) In.bHackBack = true;
			if (WasInputKeyJustPressed(EKeys::BackSpace) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Left)) In.bHackAux = true;
			static const bool bBot = FParse::Param(FCommandLine::Get(), TEXT("IVHackBot"));
			if (bBot)
			{
				const iv::HackInput Pi = Dir->GetBoarding().hack().PerfectInput();
				In.HackDx = Pi.dx; In.HackDy = Pi.dy; In.bHackConfirm = Pi.confirm;
			}
		}
	}
	if (!LookStick.IsNearlyZero(0.25f)) BerserkAim = LookStick;
	BerserkAim = FMath::Vector2DInterpTo(BerserkAim, FVector2D::ZeroVector, Dt, 1.6f);
	bPadStrikePrev = bPadStrike;

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
		bTrailGuard = bGuardDown && !bStrikeDown;
	}
	else
	{
		TrailAge += Dt;
		if (TrailAge > 1.1f) Trail.Reset();
	}
	bGuardWasDown = bGuardDown;

	if (WasInputKeyJustPressed(EKeys::Tab) || (WasInputKeyJustPressed(EKeys::Gamepad_DPad_Down) && !bPadGuard)) { bLockOn = !bLockOn; LockOffYaw = LockOffPitch = 0.f; }
	if (WasInputKeyJustPressed(EKeys::Enter) && Dir->IsMatchOver()) Dir->Restart();
}

void AIVPlayerController::PlayerTick(float Dt)
{
	Super::PlayerTick(Dt);
	AIVMechPawn* M = Mech();
	if (!M) return;

	FVector2D Move = (bCombatEnabled && !Repair.bActive) ? MoveValue : FVector2D::ZeroVector;
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
	const bool bFL = WantsFreeLook();
	M->SetFreeLook(bFL);

	AIVCombatDirector* Dir = GetDirector();
	UpdateRepair(Dt);
	if (Dir && !bAuto && bCombatEnabled)
	{
		UpdateCombatInput(Dt);
		if (bLockOn && Dir->GetDuel() && !Dir->IsMatchOver())
		{
			// lock-on: aim follows the opponent; the mouse only offsets the view a little, which eases back
			for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It)
			{
				if (*It == M) continue;
				const FVector To = (It->GetZoneWorldLocation(iv::Zone::Head) - FVector(0, 0, 750.f)) - M->GetEyeLocation();
				const FRotator R = To.Rotation();
				M->SetAim(R.Yaw + LockOffYaw, R.Pitch + LockOffPitch);
				break;
			}
			const float Back = FMath::Exp(-1.8f * Dt);
			LockOffYaw *= Back; LockOffPitch *= Back;
		}
	}
	if (bFL)
	{
		if (!LookStick.IsNearlyZero(0.05f)) M->AddLook(LookStick.X * StickLookRate * Dt, LookStick.Y * StickLookRate * Dt);
	}
	else if (!LookStick.IsNearlyZero(0.05f) && !(Dir && (IsInputKeyDown(EKeys::Gamepad_RightTriggerAxis) || GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) > 0.2f)))
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


// ------------------------------------------------------------------------------------------------ below-deck repair
void AIVPlayerController::StartRepair()
{
	AIVCombatDirector* Dir = GetDirector();
	AIVMechPawn* M = Mech();
	if (!Dir || !M || !Dir->GetDuel() || Repair.bActive || Repair.Cooldown > 0.f) return;
	const iv::Duel& D = *Dir->GetDuel();
	const iv::Fighter& F = D.fighter(MySide);
	if (D.result().over || D.lock().active || D.berserk().active || D.cinematic().active || F.breakdown <= 0) return;
	if (F.posture != iv::Posture::Standing && F.posture != iv::Posture::Staggered) return;
	FIVRepairGame G;
	G.bActive = true;
	G.Level = F.breakdown;
	G.TimeLimit = 20.f + 3.f * F.breakdown;
	Repair = G;
	Dir->SetAutopilot(MySide, true);
	IVAudio::Play2D(GetWorld(), TEXT("cockpit_switch_02"), 1.f);
	IVAudio::Play2D(GetWorld(), TEXT("cockpit_hud_lock"), 0.8f);
}

void AIVPlayerController::StopRepair(bool bSuccess)
{
	AIVCombatDirector* Dir = GetDirector();
	AIVMechPawn* M = Mech();
	Repair.bActive = false;
	Repair.bCheck = false;
	if (Dir) Dir->SetAutopilot(MySide, false);
	if (bSuccess)
	{
		if (Dir) Dir->RepairBreakdown(MySide, 3);
		if (M && M->GetCockpitFx()) M->GetCockpitFx()->Repair(1.f);
		IVAudio::Play2D(GetWorld(), TEXT("cockpit_hud_unlock"), 1.f);
		IVAudio::Play2D(GetWorld(), TEXT("cockpit_switch_04"), 1.f);
	}
	else
	{
		Repair.Cooldown = 6.f;
		IVAudio::Play2D(GetWorld(), TEXT("cockpit_alarm_warning"), 0.9f);
	}
}

void AIVPlayerController::UpdateRepair(float Dt)
{
	FIVRepairGame& G = Repair;
	G.Cooldown = FMath::Max(0.f, G.Cooldown - Dt);
	G.FlashGood = FMath::Max(0.f, G.FlashGood - Dt * 2.5f);
	G.FlashBad = FMath::Max(0.f, G.FlashBad - Dt * 2.5f);
	if (!G.bActive) return;
	AIVCombatDirector* Dir = GetDirector();
	AIVMechPawn* M = Mech();
	if (!Dir || !M || !Dir->GetDuel() || Dir->IsMatchOver()) { StopRepair(false); return; }
	G.Time += Dt;
	const bool bPress = bScriptPress || WasInputKeyJustPressed(EKeys::SpaceBar) || WasInputKeyJustPressed(EKeys::LeftMouseButton) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom) ||
		(GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) > 0.5f && !bPadStrikePrev);
	bPadStrikePrev = GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) > 0.5f;
	const bool bHold = IsInputKeyDown(EKeys::SpaceBar) || IsInputKeyDown(EKeys::LeftMouseButton) || IsInputKeyDown(EKeys::Gamepad_FaceButton_Bottom) || bPadStrikePrev || bScriptHold;
	if (WasInputKeyJustPressed(EKeys::Escape) || WasInputKeyJustPressed(EKeys::H) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right)) { StopRepair(false); G.Cooldown = 1.5f; return; }
	bScriptPress = false;
	G.bWorking = bHold;
	if (bHold) G.Progress += Dt * 0.075f;
	M->AddCockpitImpulse(FMath::RandRange(-1.f, 1.f), FMath::RandRange(-1.f, 1.f), bHold ? 0.12f : 0.05f);
	auto Fail = [&]()
	{
		G.Progress = FMath::Max(0.f, G.Progress - 0.10f);
		G.FlashBad = 1.f;
		IVAudio::Play2D(GetWorld(), IVAudio::Variant(TEXT("cockpit_spark_"), 4), 1.f);
		M->AddCockpitImpulse(0.f, 0.f, 1.2f);
		if (M->GetCockpitFx()) M->GetCockpitFx()->Hit(0.55f, FVector(0, 1, 0), false);
		if (iv::Duel* Du = Dir->GetMutableDuel()) Du->ExternalHit(MySide, iv::Zone::Reactor, 2.5f, 3.f, 4);
	};
	if (!G.bCheck)
	{
		if (bHold)
		{
			G.NextCheck -= Dt;
			if (G.NextCheck <= 0.f)
			{
				G.bCheck = true;
				G.Needle = 0.f;
				G.ZoneStart = FMath::RandRange(110.f, 290.f);
				G.ZoneLen = FMath::RandRange(46.f, 58.f);
				G.GreatLen = 12.f;
				G.NeedleSpeed = 220.f + 28.f * G.Level;
				IVAudio::Play2D(GetWorld(), TEXT("cockpit_hud_lock"), 0.8f, 1.4f);
			}
		}
	}
	else
	{
		G.Needle += G.NeedleSpeed * Dt;
		if (bPress)
		{
			const float Rel = FMath::Fmod(G.Needle - G.ZoneStart + 720.f, 360.f);
			if (Rel < G.ZoneLen && G.Needle >= G.ZoneStart - 1.f)
			{
				const bool bGreat = Rel < G.GreatLen;
				G.Progress += bGreat ? 0.13f : 0.07f;
				G.FlashGood = 1.f;
				IVAudio::Play2D(GetWorld(), TEXT("cockpit_switch_03"), 1.f, bGreat ? 1.3f : 1.f);
			}
			else Fail();
			G.bCheck = false;
			G.NextCheck = FMath::RandRange(1.1f, 2.4f);
		}
		else if (G.Needle > G.ZoneStart + G.ZoneLen + 10.f)
		{
			Fail();
			G.bCheck = false;
			G.NextCheck = FMath::RandRange(1.1f, 2.4f);
		}
	}
	G.Progress = FMath::Clamp(G.Progress, 0.f, 1.f);
	if (G.Progress - G.RepairedMark > 0.2f)
	{
		G.RepairedMark = G.Progress;
		if (M->GetCockpitFx()) M->GetCockpitFx()->Repair(0.45f);
	}
	if (G.Progress >= 1.f) StopRepair(true);
	else if (G.Time >= G.TimeLimit) StopRepair(false);
}


void AIVPlayerController::ApplySettings()
{
	LookSensitivity = 0.11f * IVSettings::Get(TEXT("mouse"));
	StickLookRate = 95.f * IVSettings::Get(TEXT("pad_look"));
	RumbleScale = IVSettings::Get(TEXT("rumble"));
}

void AIVPlayerController::Rumble(float Strength, float Seconds)
{
	Strength *= RumbleScale;
	if (!bRumbleEnabled || Strength <= 0.01f || !IsLocalController()) return;
	UForceFeedbackEffect* Fx = NewObject<UForceFeedbackEffect>(this);
	FForceFeedbackChannelDetails D;
	D.bAffectsLeftLarge = D.bAffectsRightLarge = true;
	D.bAffectsLeftSmall = D.bAffectsRightSmall = Strength > 0.35f;
	D.Curve.GetRichCurve()->AddKey(0.f, FMath::Clamp(Strength, 0.f, 1.f));
	D.Curve.GetRichCurve()->AddKey(0.04f, FMath::Clamp(Strength, 0.f, 1.f));
	D.Curve.GetRichCurve()->AddKey(FMath::Max(Seconds, 0.06f), 0.f);
	Fx->ChannelDetails.Add(D);
	FForceFeedbackParameters P;
	P.Tag = FName(TEXT("iv_rumble"));
	P.bIgnoreTimeDilation = true;
	ClientPlayForceFeedback(Fx, P);
}

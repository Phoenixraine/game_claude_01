"""Game flow: new menu (duel, tutorial, split screen, graphics, exit), split-screen join + versus, graphics presets."""
S = r"F:\IVUnreal\Source\ImpactVector" + "\\"


def patch(path, edits):
    s = open(path, encoding="utf-8").read()
    for a, b in edits:
        assert a in s, (path, a[:90])
        s = s.replace(a, b, 1)
    open(path, "w", encoding="utf-8").write(s)


patch(S + "IVGraphics.cpp", [
    ("		CVI(TEXT(\"r.RayTracing\"), bRt ? 1 : 0);\n", "		CVI(TEXT(\"r.RayTracing.Enable\"), bRt ? 1 : 0);\n"),
])

patch(S + "IVFlow.h", [
    ("enum class EIVFlowState : uint8 { Menu, Tutorial, Duel, Result };", "enum class EIVFlowState : uint8 { Menu, Tutorial, Duel, Result, Join };"),
    ("	FString GetDifficultyName() const;", """	FString GetDifficultyName() const;
	// ---- split screen join screen
	bool IsVersus() const { return bVersus; }
	bool JoinReady(int32 I) const { return I == 0 ? bJoin1 : bJoin2; }
	bool SecondPadPresent() const;
	int32 GetGfxPreset() const { return GfxPreset; }"""),
    ("	void MenuInput();", "	void MenuInput();\n	void EnterJoin();\n	void EnterVersus();\n	void LeaveVersus();\n	void JoinInput();\n	bool bVersus = false, bJoin1 = false, bJoin2 = false;\n	int32 GfxPreset = 3;\n	UPROPERTY() TObjectPtr<AIVPlayerController> Player2;"),
])

patch(S + "IVFlow.cpp", [
    ('#include "IVAudio.h"', '#include "IVAudio.h"\n#include "IVGraphics.h"\n#include "Engine/GameViewportClient.h"\n#include "Engine/LocalPlayer.h"\n#include "GenericPlatform/GenericApplication.h"\n#include "Framework/Application/SlateApplication.h"'),
    ("""	I.Add(TEXT("ОБУЧЕНИЕ"));
	I.Add(FString::Printf(TEXT("ДУЭЛЬ      <  %s  >"), kDifficulty[FMath::Clamp(Difficulty, 0, 2)]));
	I.Add(TEXT("ВЫХОД"));""",
     """	I.Add(FString::Printf(TEXT("ДУЭЛЬ С ИИ      <  %s  >"), kDifficulty[FMath::Clamp(Difficulty, 0, 2)]));
	I.Add(TEXT("ОБУЧЕНИЕ"));
	I.Add(TEXT("СПЛИТ-СКРИН  ·  2 ГЕЙМПАДА"));
	I.Add(FString::Printf(TEXT("ГРАФИКА      <  %s  >"), IVGraphics::PresetName(GfxPreset)));
	I.Add(TEXT("ВЫХОД"));"""),
    ("""	if (Pressed({ EKeys::Up, EKeys::W, EKeys::Gamepad_DPad_Up })) MenuIndex = (MenuIndex + 2) % 3;
	if (Pressed({ EKeys::Down, EKeys::S, EKeys::Gamepad_DPad_Down })) MenuIndex = (MenuIndex + 1) % 3;
	if (MenuIndex == 1)
	{
		if (Pressed({ EKeys::Left, EKeys::A, EKeys::Gamepad_DPad_Left })) Difficulty = FMath::Max(0, Difficulty - 1);
		if (Pressed({ EKeys::Right, EKeys::D, EKeys::Gamepad_DPad_Right })) Difficulty = FMath::Min(2, Difficulty + 1);
	}
	if (Pressed({ EKeys::Enter, EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom, EKeys::LeftMouseButton }))
	{
		if (MenuIndex == 0) EnterTutorial();
		else if (MenuIndex == 1) EnterDuel();
		else UKismetSystemLibrary::QuitGame(this, nullptr, EQuitPreference::Quit, false);
	}""",
     """	const int32 N = 5;
	if (Pressed({ EKeys::Up, EKeys::W, EKeys::Gamepad_DPad_Up, EKeys::Gamepad_LeftStick_Up })) { MenuIndex = (MenuIndex + N - 1) % N; IVAudio::Play2D(GetWorld(), TEXT("ui_move"), 0.7f); }
	if (Pressed({ EKeys::Down, EKeys::S, EKeys::Gamepad_DPad_Down, EKeys::Gamepad_LeftStick_Down })) { MenuIndex = (MenuIndex + 1) % N; IVAudio::Play2D(GetWorld(), TEXT("ui_move"), 0.7f); }
	const bool bLeft = Pressed({ EKeys::Left, EKeys::A, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_LeftStick_Left });
	const bool bRight = Pressed({ EKeys::Right, EKeys::D, EKeys::Gamepad_DPad_Right, EKeys::Gamepad_LeftStick_Right });
	if (MenuIndex == 0)
	{
		if (bLeft) Difficulty = FMath::Max(0, Difficulty - 1);
		if (bRight) Difficulty = FMath::Min(2, Difficulty + 1);
	}
	if (MenuIndex == 3 && (bLeft || bRight))
	{
		GfxPreset = FMath::Clamp(GfxPreset + (bRight ? 1 : -1), 0, IVGraphics::kPresetCount - 1);
		IVGraphics::Apply(GetWorld(), GfxPreset);
		IVGraphics::Save(GfxPreset);
		IVAudio::Play2D(GetWorld(), TEXT("ui_move"), 0.7f);
	}
	if (Pressed({ EKeys::Enter, EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom, EKeys::LeftMouseButton }))
	{
		IVAudio::Play2D(GetWorld(), TEXT("ui_confirm"), 0.8f);
		if (MenuIndex == 0) EnterDuel();
		else if (MenuIndex == 1) EnterTutorial();
		else if (MenuIndex == 2) EnterJoin();
		else if (MenuIndex == 3) { GfxPreset = (GfxPreset + 1) % IVGraphics::kPresetCount; IVGraphics::Apply(GetWorld(), GfxPreset); IVGraphics::Save(GfxPreset); }
		else UKismetSystemLibrary::QuitGame(this, nullptr, EQuitPreference::Quit, false);
	}"""),
    ("void AIVGameFlow::EnterMenu()\n{\n	State = EIVFlowState::Menu;",
     "void AIVGameFlow::EnterMenu()\n{\n	if (bVersus || Player2) LeaveVersus();\n	State = EIVFlowState::Menu;\n	GfxPreset = IVGraphics::Load();"),
    ("void AIVGameFlow::EnterResult()", r'''bool AIVGameFlow::SecondPadPresent() const { return true; }

void AIVGameFlow::EnterJoin()
{
	State = EIVFlowState::Join;
	bJoin1 = bJoin2 = false;
	if (!Player2)
	{
		Player2 = Cast<AIVPlayerController>(UGameplayStatics::CreatePlayer(this, 1, true));
		if (Player2) { Player2->MySide = iv::Side::B; Player2->SetCombatEnabled(false); }
	}
	if (UGameViewportClient* VC = GetWorld()->GetGameViewport()) VC->SetForceDisableSplitscreen(true);
}

void AIVGameFlow::JoinInput()
{
	APlayerController* P1 = UGameplayStatics::GetPlayerController(this, 0);
	if (!P1) return;
	if (P1->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom) || P1->WasInputKeyJustPressed(EKeys::Enter) || P1->WasInputKeyJustPressed(EKeys::SpaceBar)) { bJoin1 = true; IVAudio::Play2D(GetWorld(), TEXT("cockpit_switch_02"), 0.8f); }
	if (Player2 && (Player2->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom) || Player2->WasInputKeyJustPressed(EKeys::Gamepad_RightTriggerAxis))) { bJoin2 = true; IVAudio::Play2D(GetWorld(), TEXT("cockpit_switch_03"), 0.8f); }
	if (FParse::Param(FCommandLine::Get(), TEXT("IVSplitAuto"))) bJoin1 = bJoin2 = true;
	if (bJoin1 && bJoin2) EnterVersus();
}

void AIVGameFlow::EnterVersus()
{
	bVersus = true;
	if (!Player2) { EnterMenu(); return; }
	if (UGameViewportClient* VC = GetWorld()->GetGameViewport()) VC->SetForceDisableSplitscreen(false);
	Player2->Possess(Enemy);
	Enemy->bAIControlled = false;
	Enemy->SetExternalControl(true);
	Enemy->SetPlayerLamps(true);
	Enemy->SetFirstPersonView(true);
	Player2->SetCombatEnabled(true);
	Player2->SetLockOn(true);
	if (AIVPlayerController* P = PC()) { P->SetCombatEnabled(true); P->SetLockOn(true); }
	State = EIVFlowState::Duel;
	SetCam(0);
	if (Dir)
	{
		Dir->ClearPlayerAuto();
		Dir->SetHumanB(true);
		Dir->Restart();
		Dir->SetDummy(iv::DummyMode::Off);
	}
	PlaceMechs(60.f);
	SetBanner(TEXT("ДУЭЛЬ ИГРОКОВ"), TEXT("Игрок 1 — слева  ·  Игрок 2 — справа"), 3.5f);
	DuelClock = 0.f;
	HitsLanded = HitsTaken = Parries = 0;
	EndDelay = -1.f;
	StartBattleMusic();
}

void AIVGameFlow::LeaveVersus()
{
	bVersus = false;
	if (Player2)
	{
		Player2->UnPossess();
		UGameplayStatics::RemovePlayer(Player2, true);
		Player2 = nullptr;
	}
	if (Enemy) { Enemy->SetPlayerLamps(false); Enemy->SetExternalControl(true); }
	if (Dir) Dir->SetHumanB(false);
	if (AIVPlayerController* P = PC()) P->SetLockOn(false);
	if (UGameViewportClient* VC = GetWorld()->GetGameViewport()) VC->SetForceDisableSplitscreen(false);
}

void AIVGameFlow::EnterResult()''', ),
    ("	switch (State)\n	{\n	case EIVFlowState::Menu:\n		MenuInput();",
     "	switch (State)\n	{\n	case EIVFlowState::Join:\n		JoinInput();\n		break;\n	case EIVFlowState::Menu:\n		MenuInput();"),
    ("		if (ResultT > 0.6f && P->WasInputKeyJustPressed(EKeys::Enter)) EnterDuel();\n		if (ResultT > 0.6f && P->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom)) EnterDuel();",
     "		if (ResultT > 0.6f && (P->WasInputKeyJustPressed(EKeys::Enter) || P->WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom))) { if (bVersus) EnterVersus(); else EnterDuel(); }"),
])
# Escape in versus returns to the menu and removes the second player: handled by EnterMenu. Block the old Esc line for the Join state too (it calls EnterMenu).

patch(S + "IVMechPawn.h", [
    ("	void SetFreeLook(bool b) { bFreeLook = b; }", "	void SetFreeLook(bool b) { bFreeLook = b; }\n	/** The opponent's head lamps: dim and aimed at the ground for the AI mech, the full key light for a second human pilot. */\n	void SetPlayerLamps(bool bOn);"),
])
patch(S + "IVMechPawn.cpp", [
    ("void AIVMechPawn::SetFirstPersonView(bool bFirstPerson)", """void AIVMechPawn::SetPlayerLamps(bool bOn)
{
	bLampsDown = !bOn;
	LampPower = bOn ? 1.f : 0.12f;
	LampColor = bOn ? FLinearColor(0.75f, 0.88f, 1.f) : FLinearColor(1.f, 0.28f, 0.12f);
	for (int32 i = 0; i < 2; ++i) if (HeadLamp[i])
	{
		HeadLamp[i]->SetLightColor(LampColor);
		HeadLamp[i]->SetIntensity(70000.f * LampPower);
		HeadLamp[i]->SetVolumetricScatteringIntensity(1.6f * FMath::Sqrt(LampPower));
		HeadLamp[i]->SetRelativeRotation(bOn ? FRotator(-13.f, (i == 0 ? 5.f : -5.f), 0.f) : FRotator(-30.f, (i == 0 ? 16.f : -16.f), 0.f));
	}
}

void AIVMechPawn::SetFirstPersonView(bool bFirstPerson)"""),
    ("	Camera->SetFieldOfView(92.f);\n\n	if (Mode == 0)", "	{\n		UGameViewportClient* VPC = GetWorld() ? GetWorld()->GetGameViewport() : nullptr;\n		const bool bSplit = VPC && VPC->GetCurrentSplitscreenConfiguration() != ESplitScreenType::None;\n		Camera->SetFieldOfView((bSplit ? 70.f : 92.f) - 7.f * Rage);\n	}\n\n	if (Mode == 0)"),
])
patch(S + "IVPlayerController.h", [
    ("	void StartRepair();", "	void SetLockOn(bool b) { bLockOn = b; LockOffYaw = LockOffPitch = 0.f; }\n	void StartRepair();"),
])
patch(S + "IVGameMode.cpp", [
    ('#include "IVAudio.h"', '#include "IVAudio.h"\n#include "IVGraphics.h"'),
    ("	UWorld* W = GetWorld();\n	W->SpawnActor<AIVEnvironment>", "	UWorld* W = GetWorld();\n	IVGraphics::ApplyAtStart(W);\n	W->SpawnActor<AIVEnvironment>"),
])
# the director must not turn the human opponent by itself
patch(S + "IVCombat.cpp", [
    ("	E->SetAim((P->GetActorLocation() - E->GetActorLocation()).Rotation().Yaw, 0.f);", "	if (!bHumanB) E->SetAim((P->GetActorLocation() - E->GetActorLocation()).Rotation().Yaw, 0.f);"),
])
print("flow ok")

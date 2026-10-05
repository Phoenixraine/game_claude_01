import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new):
    assert old in t, old[:90]
    return t.replace(old, new, 1)


h, c = rd("IVFlow.h")
if "Paused" not in h:
    h = rep(h, "enum class EIVFlowState : uint8 { Menu, Tutorial, Duel, Result, Join, Settings };", "enum class EIVFlowState : uint8 { Menu, Tutorial, Duel, Result, Join, Settings, Paused };")
    h = rep(h, "	int32 GetMenuIndex() const { return MenuIndex; }", "	int32 GetMenuIndex() const { return MenuIndex; }\n	int32 GetPauseIndex() const { return PauseIdx; }")
    h = rep(h, "	int32 MenuIndex = 0;", "	int32 MenuIndex = 0;\n	// pause (Esc in a fight or in the tutorial): the world freezes, a small menu offers continue / settings / menu / quit\n	int32 PauseIdx = 0;\n	EIVFlowState PauseReturn = EIVFlowState::Duel;\n	bool bSettingsFromPause = false;\n	void EnterPause();\n	void ExitPause();\n	void PauseInput();")
    wr("IVFlow.h", h, c)

f, c = rd("IVFlow.cpp")
if "AIVGameFlow::EnterPause" not in f:
    f = rep(f, "	if (State != EIVFlowState::Menu && State != EIVFlowState::Settings && P->WasInputKeyJustPressed(EKeys::Escape)) { EnterMenu(); return; }",
            """	if ((State == EIVFlowState::Tutorial || State == EIVFlowState::Duel) && P->WasInputKeyJustPressed(EKeys::Escape) && !(PC() && PC()->IsRepairing())) { EnterPause(); return; }
	if (State != EIVFlowState::Menu && State != EIVFlowState::Settings && State != EIVFlowState::Paused && State != EIVFlowState::Tutorial && State != EIVFlowState::Duel && P->WasInputKeyJustPressed(EKeys::Escape)) { EnterMenu(); return; }""")
    f = rep(f, "	switch (State)\n	{\n	case EIVFlowState::Join:\n		JoinInput();\n		break;", "	switch (State)\n	{\n	case EIVFlowState::Paused:\n		PauseInput();\n		return;                                    // the fight and its timers stand still\n	case EIVFlowState::Join:\n		JoinInput();\n		break;")
    # settings: remember where to return, hold repeat on real time
    f = rep(f, "	if (Pressed({ EKeys::Escape, EKeys::BackSpace, EKeys::Gamepad_FaceButton_Right })) { State = EIVFlowState::Menu; IVAudio::Play2D(GetWorld(), TEXT(\"ui_confirm\"), 0.6f); }",
            "	if (Pressed({ EKeys::Escape, EKeys::BackSpace, EKeys::Gamepad_FaceButton_Right })) { State = bSettingsFromPause ? EIVFlowState::Paused : EIVFlowState::Menu; bSettingsFromPause = false; IVAudio::Play2D(GetWorld(), TEXT(\"ui_confirm\"), 0.6f); }")
    f = rep(f, "SetHold += GetWorld()->GetDeltaSeconds();", "SetHold += FApp::GetDeltaTime();")
    f = rep(f, "void AIVGameFlow::EnterSettings()\n{\n	State = EIVFlowState::Settings;", "void AIVGameFlow::EnterSettings()\n{\n	if (State == EIVFlowState::Paused) bSettingsFromPause = true;\n	State = EIVFlowState::Settings;")
    f = rep(f, "void AIVGameFlow::EnterMenu()\n{\n	if (bVersus || Player2) LeaveVersus();", "void AIVGameFlow::EnterMenu()\n{\n	UGameplayStatics::SetGlobalTimeDilation(this, 1.f);\n	bSettingsFromPause = false;\n	if (bVersus || Player2) LeaveVersus();")
    f += r'''

// ---------------------------------------------------------------------------------------------------- pause
void AIVGameFlow::EnterPause()
{
	PauseReturn = State;
	State = EIVFlowState::Paused;
	PauseIdx = 0;
	UGameplayStatics::SetGlobalTimeDilation(this, 0.0001f);          // everything in the world stops; the menu itself reads real keys
	if (AIVPlayerController* P = PC()) P->SetCombatEnabled(false);
	if (Player2) Player2->SetCombatEnabled(false);
	IVAudio::Play2D(GetWorld(), TEXT("ui_confirm"), 0.6f);
}

void AIVGameFlow::ExitPause()
{
	State = PauseReturn;
	UGameplayStatics::SetGlobalTimeDilation(this, 1.f);
	if (AIVPlayerController* P = PC()) P->SetCombatEnabled(true);
	if (Player2) Player2->SetCombatEnabled(true);
	IVAudio::Play2D(GetWorld(), TEXT("ui_confirm"), 0.6f);
}

void AIVGameFlow::PauseInput()
{
	APlayerController* P = UGameplayStatics::GetPlayerController(this, 0);
	if (!P) return;
	auto Pressed = [P](std::initializer_list<FKey> Keys) { for (const FKey& K : Keys) if (P->WasInputKeyJustPressed(K)) return true; return false; };
	const int32 N = 4;
	if (Pressed({ EKeys::Up, EKeys::W, EKeys::Gamepad_DPad_Up, EKeys::Gamepad_LeftStick_Up })) { PauseIdx = (PauseIdx + N - 1) % N; IVAudio::Play2D(GetWorld(), TEXT("ui_move"), 0.7f); }
	if (Pressed({ EKeys::Down, EKeys::S, EKeys::Gamepad_DPad_Down, EKeys::Gamepad_LeftStick_Down })) { PauseIdx = (PauseIdx + 1) % N; IVAudio::Play2D(GetWorld(), TEXT("ui_move"), 0.7f); }
	if (Pressed({ EKeys::Escape, EKeys::Gamepad_Special_Right, EKeys::Gamepad_FaceButton_Right })) { ExitPause(); return; }
	if (Pressed({ EKeys::Enter, EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom, EKeys::LeftMouseButton }))
	{
		IVAudio::Play2D(GetWorld(), TEXT("ui_confirm"), 0.8f);
		if (PauseIdx == 0) ExitPause();
		else if (PauseIdx == 1) EnterSettings();
		else if (PauseIdx == 2) EnterMenu();
		else UKismetSystemLibrary::QuitGame(this, nullptr, EQuitPreference::Quit, false);
	}
}
'''
    wr("IVFlow.cpp", f, c)
    if '#include "Misc/App.h"' not in f:
        f2, c2 = rd("IVFlow.cpp")
        f2 = f2.replace('#include "IVFlow.h"', '#include "IVFlow.h"\n#include "Misc/App.h"', 1)
        wr("IVFlow.cpp", f2, c2)

hh, c = rd("IVHUD.h")
if "DrawPause" not in hh:
    hh = rep(hh, "	void DrawBoarded(", "	void DrawPause(class AIVGameFlow* Flow);\n	void DrawBoarded(")
    wr("IVHUD.h", hh, c)
hp, c = rd("IVHUD.cpp")
if "AIVHUD::DrawPause" not in hp:
    hp = rep(hp, "	if (Flow && Flow->GetState() == EIVFlowState::Settings) { DrawSettings(Flow); return; }", "	if (Flow && Flow->GetState() == EIVFlowState::Settings) { DrawSettings(Flow); return; }\n	if (Flow && Flow->GetState() == EIVFlowState::Paused) { DrawPause(Flow); return; }")
    hp += r'''

// ------------------------------------------------------------------------------------------------------- pause menu
void AIVHUD::DrawPause(AIVGameFlow* Flow)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float Sx = FMath::Clamp(W / 1600.f, 0.6f, 1.6f);
	const double Tm = FPlatformTime::Seconds();
	DrawRect(FLinearColor(0.f, 0.01f, 0.03f, 0.72f), 0, 0, W, H);
	for (int32 i = 0; i < 12; ++i) DrawRect(FLinearColor(0.f, 0.f, 0.02f, 0.5f * FMath::Pow(1.f - float(i) / 12.f, 2.f)), 0, H * 0.15f * i / 12.f, W, H * 0.15f / 12.f);
	const float CX = W * 0.5f;
	Text(TEXT("ПАУЗА"), CX, H * 0.2f, kWhite, 4.0f * Sx, 2, 1);
	DrawRect(A(kCyan, 0.8f), CX - 260.f * Sx, H * 0.2f + 74.f * Sx, 520.f * Sx, 2.f * Sx);
	static const TCHAR* Items[4] = { TEXT("ПРОДОЛЖИТЬ"), TEXT("НАСТРОЙКИ"), TEXT("МЕНЮ"), TEXT("ВЫЙТИ") };
	const int32 Sel = Flow->GetPauseIndex();
	for (int32 i = 0; i < 4; ++i)
	{
		const float Y = H * 0.38f + i * 78.f * Sx;
		const bool bSel = (i == Sel);
		if (bSel)
		{
			DrawRect(A(kCyan, 0.18f + 0.06f * float(FMath::Sin(Tm * 5.0))), CX - 260.f * Sx, Y - 8.f * Sx, 520.f * Sx, 60.f * Sx);
			DrawRect(A(kCyan, 0.95f), CX - 260.f * Sx, Y - 8.f * Sx, 6.f * Sx, 60.f * Sx);
		}
		Text(Items[i], CX, Y, bSel ? kWhite : A(kWhite, 0.6f), (bSel ? 1.9f : 1.6f) * Sx, 2, 1);
	}
	Text(TEXT("W / S — выбор   ·   Enter — подтвердить   ·   Esc — продолжить"), CX, H * 0.9f, A(kWhite, 0.55f), 0.9f * Sx, 1, 1);
}
'''
    wr("IVHUD.cpp", hp, c)
print("pause patched")

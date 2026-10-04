import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new, cnt=1):
    assert old in t, old[:70]
    return t.replace(old, new, cnt)


# settings order of enemy styles = kRotation order
s, c = rd("IVSettings.cpp")
if "КОНТРБОЙЦОВЩИК" not in s:
  s = rep(s, 'St.Names = { TEXT("АВТО"), TEXT("КОНТРУДАР"), TEXT("ПРОРЫВ"), TEXT("ОХОТНИК ЗА КОНЕЧНОСТЯМИ"), TEXT("ОБМАНЩИК"), TEXT("СТРЕЛОК"), TEXT("ЗАХВАТЧИК") };',
        'St.Names = { TEXT("АВТО"), TEXT("КОНТРБОЙЦОВЩИК"), TEXT("ОХОТНИК НА КОНЕЧНОСТИ"), TEXT("ОБМАНЩИК"), TEXT("ГРОМИЛА"), TEXT("БОРЕЦ"), TEXT("СТРЕЛОК") };')
wr("IVSettings.cpp", s, c)

h, c = rd("IVFlow.h")
if "GetSettingsTab" not in h:
    h = rep(h, "enum class EIVFlowState : uint8 { Menu, Tutorial, Duel, Result, Join };", "enum class EIVFlowState : uint8 { Menu, Tutorial, Duel, Result, Join, Settings };")
    h = rep(h, "	// ---- split screen join screen", "	// ---- settings screen\n	int32 GetSettingsTab() const { return SetTab; }\n	int32 GetSettingsIndex() const { return SetIdx; }\n	// ---- split screen join screen")
    h = rep(h, "	void MenuInput();", "	void MenuInput();\n	void EnterSettings();\n	void SettingsInput();\n	int32 SetTab = 0, SetIdx = 0;\n	float SetHold = 0.f;")
    wr("IVFlow.h", h, c)

f, c = rd("IVFlow.cpp")
if "SettingsInput" not in f:
    f = rep(f, '#include "IVFlow.h"', '#include "IVFlow.h"\n#include "IVSettings.h"')
    # difficulty / style from settings
    f = rep(f, "	const TCHAR* kDifficulty[3] = { TEXT(\"Лёгкий\"), TEXT(\"Нормальный\"), TEXT(\"Жёсткий\") };", "	const TCHAR* kDifficulty[3] = { TEXT(\"Лёгкий\"), TEXT(\"Нормальный\"), TEXT(\"Жёсткий\") };\n	int32 Diff() { return FMath::Clamp(IVSettings::GetInt(TEXT(\"difficulty\")), 0, 2); }")
    f = f.replace("FMath::Clamp(Difficulty, 0, 2)", "Diff()")
    f = rep(f, "		Dir->SetEnemyStyle(kRotation[NextStyle % 6], static_cast<iv::Difficulty>(Diff()));",
            "		const int32 Fixed = IVSettings::GetInt(TEXT(\"enemy_style\"));\n		Dir->SetEnemyStyle(kRotation[(Fixed > 0 ? Fixed - 1 : NextStyle) % 6], static_cast<iv::Difficulty>(Diff()));")
    f = rep(f, "	const TCHAR* StyleNames[6] = { TEXT(\"Контрбойцовщик\"), TEXT(\"Громила\"), TEXT(\"Охотник на конечности\"), TEXT(\"Обманщик\"), TEXT(\"Стрелок\"), TEXT(\"Борец\") };",
            "	const TCHAR* StyleNames[6] = { TEXT(\"Контрбойцовщик\"), TEXT(\"Охотник на конечности\"), TEXT(\"Обманщик\"), TEXT(\"Громила\"), TEXT(\"Борец\"), TEXT(\"Стрелок\") };\n	const int32 FixedS = IVSettings::GetInt(TEXT(\"enemy_style\"));")
    f = rep(f, "StyleNames[NextStyle % 6], kDifficulty", "StyleNames[(FixedS > 0 ? FixedS - 1 : NextStyle) % 6], kDifficulty")
    f = rep(f, "	GfxPreset = IVGraphics::Load();\n", "	GfxPreset = IVSettings::GetInt(TEXT(\"preset\"));\n")
    # menu items
    a = f.index("TArray<FString> AIVGameFlow::GetMenuItems() const")
    b = f.index("FString AIVGameFlow::GetDifficultyName()")
    f = f[:a] + '''TArray<FString> AIVGameFlow::GetMenuItems() const
{
	return { TEXT("ДУЭЛЬ С ИИ"), TEXT("ОБУЧЕНИЕ"), TEXT("СПЛИТ-СКРИН"), TEXT("ГРАФИКА"), TEXT("НАСТРОЙКИ"), TEXT("ВЫХОД") };
}

FString AIVGameFlow::GetMenuValue(int32 I) const
{
	if (I == 0) return kDifficulty[Diff()];
	if (I == 2) return TEXT("2 ГЕЙМПАДА");
	if (I == 3) return IVGraphics::PresetName(GfxPreset);
	return FString();
}

FString AIVGameFlow::GetMenuHint(int32 I) const
{
	switch (I)
	{
	case 0: return TEXT("Дуэль один на один против пилота-ИИ. Меч, броня по зонам, берсерк, абордаж и аварии в отсеках. A / D — сложность.");
	case 1: return TEXT("Пошаговое обучение: стойки, парирование, рывок, бросок здания и вертолёта, ремонт, абордаж.");
	case 2: return TEXT("Два пилота — два геймпада. Каждый стыкуется со своим мехом, экран делится вертикальной линией.");
	case 3: return TEXT("Пресеты от НИЗКОГО до RTX. Тонкая настройка (масштаб рендера, дальность, FPS) — в НАСТРОЙКАХ. A / D — сменить.");
	case 4: return TEXT("Сложность, стиль врага, скорость боя, туман, яркость, дождь, вертолёты, апскейл, дальность прорисовки, управление и многое другое.");
	default: return TEXT("Закрыть игру.");
	}
}

''' + f[b:]
    f = rep(f, "	const int32 N = 5;\n", "	const int32 N = 6;\n")
    f = rep(f, "		if (bLeft) Difficulty = FMath::Max(0, Difficulty - 1);\n		if (bRight) Difficulty = FMath::Min(2, Difficulty + 1);",
            "		if (bLeft) { IVSettings::Set(TEXT(\"difficulty\"), float(Diff() - 1)); }\n		if (bRight) { IVSettings::Set(TEXT(\"difficulty\"), float(Diff() + 1)); }")
    f = rep(f, "		GfxPreset = FMath::Clamp(GfxPreset + (bRight ? 1 : -1), 0, IVGraphics::kPresetCount - 1);\n		IVGraphics::Apply(GetWorld(), GfxPreset);\n		IVGraphics::Save(GfxPreset);",
            "		GfxPreset = FMath::Clamp(GfxPreset + (bRight ? 1 : -1), 0, IVGraphics::kPresetCount - 1);\n		IVSettings::Set(TEXT(\"preset\"), float(GfxPreset));\n		IVSettings::Apply(GetWorld());")
    f = rep(f, "		else if (MenuIndex == 3) { GfxPreset = (GfxPreset + 1) % IVGraphics::kPresetCount; IVGraphics::Apply(GetWorld(), GfxPreset); IVGraphics::Save(GfxPreset); }",
            "		else if (MenuIndex == 3) { GfxPreset = (GfxPreset + 1) % IVGraphics::kPresetCount; IVSettings::Set(TEXT(\"preset\"), float(GfxPreset)); IVSettings::Apply(GetWorld()); }\n		else if (MenuIndex == 4) EnterSettings();")
    # settings input / enter
    f = rep(f, "void AIVGameFlow::Tick(float Dt)\n{", '''void AIVGameFlow::EnterSettings()
{
	State = EIVFlowState::Settings;
	SetIdx = 0;
	SetHold = 0.f;
}

void AIVGameFlow::SettingsInput()
{
	APlayerController* P = UGameplayStatics::GetPlayerController(this, 0);
	if (!P) return;
	auto Pressed = [P](std::initializer_list<FKey> Keys) { for (const FKey& K : Keys) if (P->WasInputKeyJustPressed(K)) return true; return false; };
	auto Down = [P](std::initializer_list<FKey> Keys) { for (const FKey& K : Keys) if (P->IsInputKeyDown(K)) return true; return false; };
	const TArray<int32> Rows = IVSettings::OfTab(SetTab);
	const int32 N = Rows.Num();
	if (Pressed({ EKeys::Up, EKeys::W, EKeys::Gamepad_DPad_Up, EKeys::Gamepad_LeftStick_Up })) { SetIdx = (SetIdx + N - 1) % N; IVAudio::Play2D(GetWorld(), TEXT("ui_move"), 0.6f); }
	if (Pressed({ EKeys::Down, EKeys::S, EKeys::Gamepad_DPad_Down, EKeys::Gamepad_LeftStick_Down })) { SetIdx = (SetIdx + 1) % N; IVAudio::Play2D(GetWorld(), TEXT("ui_move"), 0.6f); }
	if (Pressed({ EKeys::Q, EKeys::Gamepad_LeftShoulder, EKeys::Tab })) { SetTab = (SetTab + IVSettings::kTabCount - 1) % IVSettings::kTabCount; SetIdx = 0; IVAudio::Play2D(GetWorld(), TEXT("ui_move"), 0.6f); }
	if (Pressed({ EKeys::E, EKeys::Gamepad_RightShoulder })) { SetTab = (SetTab + 1) % IVSettings::kTabCount; SetIdx = 0; IVAudio::Play2D(GetWorld(), TEXT("ui_move"), 0.6f); }
	SetIdx = FMath::Clamp(SetIdx, 0, FMath::Max(N - 1, 0));
	const int32 Row = Rows.IsValidIndex(SetIdx) ? Rows[SetIdx] : 0;
	const bool bShift = Down({ EKeys::LeftShift, EKeys::Gamepad_RightTrigger });
	int32 Dir = 0;
	if (Pressed({ EKeys::Left, EKeys::A, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_LeftStick_Left })) { Dir = -1; SetHold = -0.35f; }
	else if (Pressed({ EKeys::Right, EKeys::D, EKeys::Gamepad_DPad_Right, EKeys::Gamepad_LeftStick_Right })) { Dir = 1; SetHold = -0.35f; }
	else if (IVSettings::All()[Row].Kind == IVSettings::EKind::Slider)
	{
		// held key repeats
		const bool bL = Down({ EKeys::Left, EKeys::A, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_LeftStick_Left });
		const bool bR = Down({ EKeys::Right, EKeys::D, EKeys::Gamepad_DPad_Right, EKeys::Gamepad_LeftStick_Right });
		if (bL || bR) { SetHold += GetWorld()->GetDeltaSeconds(); if (SetHold > 0.06f) { SetHold = 0.f; Dir = bR ? 1 : -1; } }
		else SetHold = 0.f;
	}
	if (Pressed({ EKeys::Enter, EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom }) && IVSettings::All()[Row].Kind != IVSettings::EKind::Slider) Dir = 1;
	if (Dir != 0)
	{
		IVSettings::Adjust(Row, Dir, bShift);
		IVSettings::Apply(GetWorld());
		GfxPreset = IVSettings::GetInt(TEXT("preset"));
		IVAudio::Play2D(GetWorld(), TEXT("ui_move"), 0.5f);
	}
	if (Pressed({ EKeys::R, EKeys::Gamepad_FaceButton_Left })) { IVSettings::ResetAll(); IVSettings::Apply(GetWorld()); IVAudio::Play2D(GetWorld(), TEXT("ui_confirm"), 0.8f); }
	if (Pressed({ EKeys::Escape, EKeys::BackSpace, EKeys::Gamepad_FaceButton_Right })) { State = EIVFlowState::Menu; IVAudio::Play2D(GetWorld(), TEXT("ui_confirm"), 0.6f); }
}

void AIVGameFlow::Tick(float Dt)
{''')
    f = rep(f, "	case EIVFlowState::Menu:\n", "	case EIVFlowState::Settings:\n		SettingsInput();\n		break;\n	case EIVFlowState::Menu:\n")
    f = rep(f, "	if (State != EIVFlowState::Menu && P->WasInputKeyJustPressed(EKeys::Escape)) { EnterMenu(); return; }", "	if (State != EIVFlowState::Menu && State != EIVFlowState::Settings && P->WasInputKeyJustPressed(EKeys::Escape)) { EnterMenu(); return; }")
    wr("IVFlow.cpp", f, c)

# ------------------------------------------------------------------ HUD
h, c = rd("IVHUD.h")
if "DrawSettings" not in h:
    h = rep(h, "	void DrawJoin(AIVGameFlow* Flow);", "	void DrawJoin(AIVGameFlow* Flow);\n	void DrawSettings(AIVGameFlow* Flow);")
    wr("IVHUD.h", h, c)
hd, c = rd("IVHUD.cpp")
if "void AIVHUD::DrawSettings" not in hd:
    hd = rep(hd, "	if (Flow && Flow->GetState() == EIVFlowState::Join) { DrawJoin(Flow); return; }", "	if (Flow && Flow->GetState() == EIVFlowState::Join) { DrawJoin(Flow); return; }\n	if (Flow && Flow->GetState() == EIVFlowState::Settings) { DrawSettings(Flow); return; }")
    hd = rep(hd, "void AIVHUD::DrawJoin(AIVGameFlow* Flow)", r'''void AIVHUD::DrawSettings(AIVGameFlow* Flow)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float Sx = FMath::Clamp(W / 1600.f, 0.6f, 1.6f);
	const float Tm = GetWorld()->GetTimeSeconds();
	DrawRect(FLinearColor(0.003f, 0.008f, 0.02f, 0.9f), 0, 0, W, H);
	for (int32 i = 0; i < 8; ++i) DrawRect(A(kCyan, 0.012f), 0, FMath::Frac(Tm * 0.05f + i * 0.125f) * H, W, 2.f);
	const float PX = W * 0.14f, PW = W * 0.72f;
	Text(TEXT("НАСТРОЙКИ"), PX, H * 0.055f, kWhite, 2.8f * Sx, 2);
	DrawLine(PX, H * 0.055f + 66.f * Sx, PX + PW, H * 0.055f + 66.f * Sx, A(kCyan, 0.8f), 2.f);
	// tabs
	float Tx = PX;
	const int32 Tab = Flow->GetSettingsTab();
	for (int32 t = 0; t < IVSettings::kTabCount; ++t)
	{
		const FString N = IVSettings::TabName(t);
		const float Tw = (N.Len() * 15.f + 40.f) * Sx;
		const bool bOn = t == Tab;
		DrawRect(A(bOn ? kCyan : FLinearColor(0.1f, 0.2f, 0.3f), bOn ? 0.35f : 0.18f), Tx, H * 0.055f + 78.f * Sx, Tw, 34.f * Sx);
		if (bOn) DrawRect(kCyan, Tx, H * 0.055f + 78.f * Sx + 32.f * Sx, Tw, 3.f);
		Text(N, Tx + Tw * 0.5f, H * 0.055f + 84.f * Sx, bOn ? kWhite : A(kWhite, 0.55f), 0.95f * Sx, 1, 1);
		Tx += Tw + 8.f * Sx;
	}
	Text(TEXT("Q / E — вкладка"), PX + PW, H * 0.055f + 84.f * Sx, A(kCyan, 0.6f), 0.75f * Sx, 1, 2);
	// rows
	const TArray<int32> Rows = IVSettings::OfTab(Tab);
	const float Y0 = H * 0.055f + 130.f * Sx, RH = 44.f * Sx;
	const int32 Sel = Flow->GetSettingsIndex();
	for (int32 i = 0; i < Rows.Num(); ++i)
	{
		const IVSettings::FSetting& S = IVSettings::All()[Rows[i]];
		const float Y = Y0 + i * RH;
		const bool bSel = i == Sel;
		if (bSel)
		{
			for (int32 k = 0; k < 14; ++k) DrawRect(A(kCyan, 0.2f * (1.f - k / 14.f)), PX + PW * k / 14.f, Y - 3.f, PW / 14.f + 1.f, RH - 4.f * Sx);
			DrawRect(kCyan, PX - 10.f * Sx, Y - 3.f, 4.f * Sx, RH - 4.f * Sx);
		}
		Text(S.Label, PX + 8.f * Sx, Y + 6.f * Sx, bSel ? kWhite : A(kWhite, 0.6f), 0.95f * Sx, 1);
		const float Vx = PX + PW * 0.64f;
		const float Vv = IVSettings::Get(S.Id);
		if (S.Kind == IVSettings::EKind::Slider)
		{
			const float U = (Vv - S.Min) / FMath::Max(S.Max - S.Min, 1e-3f);
			const float BW = PW * 0.2f;
			DrawRect(A(FLinearColor::Black, 0.55f), Vx, Y + 14.f * Sx, BW, 8.f * Sx);
			DrawRect(A(bSel ? kOrange : kCyanDim, 0.95f), Vx, Y + 14.f * Sx, BW * U, 8.f * Sx);
			DrawRect(kWhite, Vx + BW * U - 2.f, Y + 9.f * Sx, 4.f, 18.f * Sx);
			Text(IVSettings::ValueText(Rows[i]), Vx + BW + 16.f * Sx, Y + 6.f * Sx, bSel ? kOrange : A(kOrange, 0.6f), 0.95f * Sx, 1);
		}
		else
		{
			Text(IVSettings::ValueText(Rows[i]), Vx, Y + 6.f * Sx, bSel ? kOrange : A(kOrange, 0.6f), 0.95f * Sx, 1);
			if (bSel) { Text(TEXT("<"), Vx - 22.f * Sx, Y + 4.f * Sx, A(kCyan, 0.8f), 1.1f * Sx, 2, 2); Text(TEXT(">"), Vx + 280.f * Sx, Y + 4.f * Sx, A(kCyan, 0.8f), 1.1f * Sx, 2); }
		}
	}
	// hint
	if (Rows.IsValidIndex(Sel))
	{
		const float HY = H * 0.86f;
		Panel(PX, HY, PW, 56.f * Sx, FLinearColor(0.f, 0.03f, 0.06f, 0.8f), A(kCyan, 0.7f));
		Wrap(IVSettings::All()[Rows[Sel]].Hint, PX + 14.f * Sx, HY + 10.f * Sx, PW - 28.f * Sx, A(kWhite, 0.85f), 0.8f * Sx, 22.f * Sx);
	}
	Text(TEXT("W / S — выбор   ·   A / D — изменить (Shift — быстрее)   ·   Q / E — вкладка   ·   R — сбросить всё   ·   Esc — назад"), W * 0.5f, H - 30.f * Sx, A(kWhite, 0.55f), 0.75f * Sx, 1, 1);
}

void AIVHUD::DrawJoin(AIVGameFlow* Flow)''')
    wr("IVHUD.cpp", hd, c)
print("flow/hud settings patched")

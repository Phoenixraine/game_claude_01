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


h, c = rd("IVHUD.h")
if "DrawBoarded" not in h:
    h = rep(h, "	bool DrawBoarding(class AIVCombatDirector* Dir, float Sx);", "	bool DrawBoarding(class AIVCombatDirector* Dir, iv::Side MySide, float Sx);\n	void DrawBoarded(class AIVCombatDirector* Dir, iv::Side MySide, class AIVPlayerController* PC, float Sx);\n	void DrawUltGauge(class AIVCombatDirector* Dir, iv::Side MySide, float Sx);")
    wr("IVHUD.h", h, c)

p, c = rd("IVHUD.cpp")
if "DrawBoarded" not in p:
    p = rep(p, "	for (TActorIterator<AIVCombatDirector> It2(GetWorld()); It2; ++It2) { bOutside = It2->IsBoardingActive(); break; }",
            "	for (TActorIterator<AIVCombatDirector> It2(GetWorld()); It2; ++It2) { bOutside = It2->IsBoardingActive(MySide) || It2->IsBoardedBy(MySide); break; }")
    p = rep(p, "	if (Dir && Dir->GetDuel() && MySide == iv::Side::A && DrawBoarding(Dir, FMath::Clamp(W / 1600.f, 0.55f, 1.4f))) return;",
            "	if (Dir && Dir->GetDuel() && DrawBoarding(Dir, MySide, FMath::Clamp(W / 1600.f, 0.55f, 1.4f))) return;")
    p = rep(p, "		DrawParryWindow(Dir, MySide, Sx);", "		DrawParryWindow(Dir, MySide, Sx);\n		DrawUltGauge(Dir, MySide, Sx);\n		DrawBoarded(Dir, MySide, PC, Sx);")
    # DrawBoarding generalisation
    p = rep(p, "bool AIVHUD::DrawBoarding(AIVCombatDirector* Dir, float Sx)\n{\n	const iv::Boarding& B = Dir->GetBoarding();", "bool AIVHUD::DrawBoarding(AIVCombatDirector* Dir, iv::Side MySide, float Sx)\n{\n	const iv::Boarding& B = Dir->GetBoarding(MySide);")
    p = rep(p, "			const float R = Dir->GetBoardingCooldown01();", "			const float R = Dir->GetBoardingCooldown01(MySide);")
    p = rep(p, "	case iv::BoardPhase::HookSwing: Cap = TEXT(\"ПРЫЖОК НА ДРУГОЕ ПЛЕЧО\"); break;", "	case iv::BoardPhase::HookSwing: Cap = TEXT(\"ПРЫЖОК НА ДРУГОЕ ПЛЕЧО\"); break;\n	case iv::BoardPhase::Stunned: Cap = TEXT(\"ВАС СБИЛИ С ПЛЕЧА — ПИЛОТ ОГЛУШЁН\"); break;")
    p = rep(p, "	if (B.swatActive())\n	{\n		const float Pu = 0.5f + 0.5f * Pulse(6.f);", "	if (Ph == iv::BoardPhase::Stunned)\n	{\n		DrawRect(FLinearColor(0.6f, 0.4f, 0.f, 0.12f), 0, 0, W, H);\n		Text(FString::Printf(TEXT(\"ВСТАЁТ ЧЕРЕЗ %.1f c — ВАШ МЕХ БЕЗ УПРАВЛЕНИЯ\"), FMath::Max(0, B.phaseLength() - B.phaseTicks()) / 60.f), CX, H * 0.2f, A(kOrange, 0.95f), 1.6f * Sx, 2, 1);\n	}\n	if (B.swatActive())\n	{\n		const float Pu = 0.5f + 0.5f * Pulse(6.f);")
    # ult window in the parry-window HUD (the defender sees the punch coming)
    p = rep(p, "	const iv::AnimState& O = Dir->GetAnim(iv::Other(MySide));\n	if ((O.phase != iv::Phase::Windup",
            """	const iv::AnimState& O = Dir->GetAnim(iv::Other(MySide));
	if (O.ultWindTicks > 0)
	{
		// the opponent's ultimate: a punch under the chest. A fresh LOW guard in a tiny window cancels it (the window is much shorter than a parry's)
		const float CX = Canvas->ClipX * 0.5f, CY = Canvas->ClipY * 0.5f;
		const int32 Win = iv::tune::kUltCounterWindowTicks;
		const int32 Ct = O.ultWindTicks;
		const float R0 = 54.f * Sx, R1 = 170.f * Sx;
		const float U = FMath::Clamp(float(Ct) / float(FMath::Max(1, O.ultWindLen)), 0.f, 1.f);
		const float R = FMath::Lerp(R0, R1, U);
		const bool bIn = Ct <= Win;
		const FLinearColor Cu = bIn ? kGreen : kRed;
		for (int32 k = 0; k < 48; ++k)
		{
			const float a0 = 6.2831853f * k / 48.f, a1 = 6.2831853f * (k + 1) / 48.f;
			DrawLine(CX + FMath::Cos(a0) * R0, CY + FMath::Sin(a0) * R0, CX + FMath::Cos(a1) * R0, CY + FMath::Sin(a1) * R0, A(kGreen, 0.55f), 2.f);
			DrawLine(CX + FMath::Cos(a0) * R, CY + FMath::Sin(a0) * R, CX + FMath::Cos(a1) * R, CY + FMath::Sin(a1) * R, A(Cu, bIn ? 1.f : 0.75f), bIn ? 7.f : 3.f);
		}
		DrawRect(A(kRed, 0.10f + 0.08f * Pulse(5.f)), 0, 0, Canvas->ClipX, Canvas->ClipY);
		DrawLine(CX, CY + R0 + 4.f, CX, CY + R0 + 62.f * Sx, A(kGreen, 0.95f), 6.f);
		DrawLine(CX, CY + R0 + 62.f * Sx, CX - 14.f, CY + R0 + 44.f * Sx, A(kGreen, 0.95f), 5.f);
		DrawLine(CX, CY + R0 + 62.f * Sx, CX + 14.f, CY + R0 + 44.f * Sx, A(kGreen, 0.95f), 5.f);
		Text(bIn ? TEXT("БЛОК СНИЗУ — СЕЙЧАС!") : TEXT("УЛЬТИМЕЙТ ВРАГА! ЖДИ — БЛОК СНИЗУ В ПОСЛЕДНИЙ МОМЕНТ"), CX, CY + R1 + 24.f * Sx, A(Cu, 1.f), (bIn ? 1.6f : 1.0f) * Sx, 2, 1);
		return;
	}
	if ((O.phase != iv::Phase::Windup""")
    p += r'''

// ------------------------------------------------------------------------------------------------------- ultimate gauge and boarded banner
void AIVHUD::DrawUltGauge(AIVCombatDirector* Dir, iv::Side MySide, float Sx)
{
	if (!Dir || !Dir->GetDuel()) return;
	const iv::Fighter& F = Dir->GetDuel()->fighter(MySide);
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float BW = 330.f * Sx, BH = 14.f * Sx, X = W * 0.5f - BW * 0.5f, Y = H - 58.f * Sx;
	const float V = FMath::Clamp(F.ultimate / iv::tune::kUltimateMax, 0.f, 1.f);
	const bool bReady = F.UltimateReady();
	const float Mult = Dir->GetUltimateMultiplier(MySide);
	const FLinearColor C = bReady ? kYellow : kOrange;
	DrawRect(A(FLinearColor::Black, 0.55f), X - 3.f, Y - 3.f, BW + 6.f, BH + 6.f);
	DrawRect(A(C, bReady ? 0.55f + 0.45f * Pulse(4.f) : 0.9f), X, Y, BW * V, BH);
	for (int32 k = 1; k < 10; ++k) DrawRect(A(FLinearColor::Black, 0.7f), X + BW * k / 10.f - 1.f, Y, 2.f, BH);
	Text(FString::Printf(TEXT("УЛЬТИМЕЙТ  %d%%"), int32(V * 100.f)), X, Y - 20.f * Sx, A(C, 0.95f), 0.75f * Sx, 0, 1);
	Text(FString::Printf(TEXT("ЗАРЯД ×%.1f%s"), Mult, Mult > 1.45f ? TEXT("  (КАМБЭК)") : TEXT("")), X + BW, Y - 20.f * Sx, A(Mult > 1.45f ? kGreen : kWhite, 0.75f), 0.7f * Sx, 2, 1);
	if (bReady) Text(TEXT("V — УЛЬТИМЕЙТ"), W * 0.5f, Y + BH + 8.f * Sx, A(kYellow, 0.7f + 0.3f * Pulse(3.f)), 0.8f * Sx, 1, 1);
	else if (V < 0.02f) Text(TEXT("заряд — парирования и контратаки"), W * 0.5f, Y + BH + 6.f * Sx, A(kWhite, 0.3f), 0.55f * Sx, 1, 1);
}

void AIVHUD::DrawBoarded(AIVCombatDirector* Dir, iv::Side MySide, AIVPlayerController* PC, float Sx)
{
	if (!Dir || !Dir->GetDuel()) return;
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float CX = W * 0.5f;
	if (PC && PC->AlertLeft > 0.f)
	{
		const float Pu = 0.5f + 0.5f * Pulse(6.f);
		Text(PC->AlertText, CX, H * 0.12f, A(kRed, 0.6f + 0.4f * Pu), 2.6f * Sx, 2, 1);
	}
	if (!Dir->IsBoardedBy(MySide)) return;
	const iv::Side Foe = iv::Other(MySide);
	const iv::Boarding& B = Dir->GetBoarding(Foe);
	DrawRect(FLinearColor(0.5f, 0.0f, 0.f, 0.12f + 0.06f * Pulse(3.f)), 0, 0, W, H);
	DrawRect(FLinearColor(0, 0, 0, 0.7f), 0, 0, W, H * 0.07f);
	DrawRect(FLinearColor(0, 0, 0, 0.7f), 0, H * 0.93f, W, H * 0.07f);
	if (B.phase() == iv::BoardPhase::Stunned)
	{
		Text(TEXT("ВРАГ ОГЛУШЁН НА ПЛЕЧЕ — ЕГО МЕХ БЕСПОМОЩЕН! БЕЙ!"), CX, H * 0.93f + 8.f * Sx, A(kGreen, 0.95f), 1.2f * Sx, 2, 1);
		return;
	}
	Text(TEXT("НА ВАШЕМ ПЛЕЧЕ ВРАЖЕСКИЙ ПИЛОТ"), CX, H * 0.93f + 4.f * Sx, A(kRed, 0.95f), 1.3f * Sx, 2, 1);
	if (B.swatActive())
	{
		const float Tl = B.swatTicksToImpact() / 60.f;
		Text(FString::Printf(TEXT("РУКА ОПУСКАЕТСЯ НА ПЛЕЧО  ·  %.1f c"), Tl), CX, H * 0.07f + 10.f * Sx, A(kYellow, 0.95f), 1.2f * Sx, 2, 1);
	}
	else
	{
		Text(TEXT("T (D-PAD ВНИЗ) — ХЛОПНУТЬ СЕБЯ ПО ПЛЕЧУ"), CX, H * 0.07f + 10.f * Sx, A(kWhite, 0.9f + 0.1f * Pulse(4.f)), 1.1f * Sx, 2, 1);
	}
	if (B.phase() == iv::BoardPhase::Hacking)
	{
		const float Pg = FMath::Clamp(B.hack().progress(), 0.f, 1.f);
		DrawRect(A(FLinearColor::Black, 0.6f), CX - 220.f * Sx, H * 0.07f + 56.f * Sx, 440.f * Sx, 8.f * Sx);
		DrawRect(A(kRed, 0.95f), CX - 220.f * Sx, H * 0.07f + 56.f * Sx, 440.f * Sx * Pg, 8.f * Sx);
		Text(FString::Printf(TEXT("ВЗЛОМ ВАШЕГО ЛЮКА  %d%%"), int32(Pg * 100.f)), CX, H * 0.07f + 36.f * Sx, A(kRed, 0.9f), 0.8f * Sx, 1, 1);
	}
}
'''
    wr("IVHUD.cpp", p, c)
print("hud patched")

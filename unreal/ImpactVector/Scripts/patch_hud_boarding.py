import io
p = r"F:\IVUnreal\Source\ImpactVector\IVHUD.cpp"
s = io.open(p, encoding="utf-8").read()
crlf = "\r\n" in s
s = s.replace("\r\n", "\n")

# call site: in DrawHUD, right after the Dir/Duel exists; boarding replaces the glass HUD
old = "	if (Dir && Dir->GetDuel())\n	{\n		const iv::Duel& Du = *Dir->GetDuel();\n		const iv::Fighter& FA = Du.fighter(MySide);"
assert old in s
new = ("	if (Dir && Dir->GetDuel() && MySide == iv::Side::A && DrawBoarding(Dir, FMath::Clamp(W / 1600.f, 0.55f, 1.4f))) return;\n" + old)
s = s.replace(old, new, 1)

code = r'''
// ------------------------------------------------------------------------------------------------------- boarding
bool AIVHUD::DrawBoarding(AIVCombatDirector* Dir, float Sx)
{
	const iv::Boarding& B = Dir->GetBoarding();
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float CX = W * 0.5f;
	if (!B.Active())
	{
		// ready / cooldown hint at the bottom centre of the glass
		if (Dir->GetDuel() && !Dir->IsMatchOver())
		{
			const float R = Dir->GetBoardingCooldown01();
			Text(R >= 0.999f ? TEXT("J — ВЫЙТИ ИЗ КАБИНЫ (АБОРДАЖ)") : FString::Printf(TEXT("АБОРДАЖ: ПЕРЕЗАРЯДКА %d%%"), int32(R * 100.f)), CX, H - 32.f * Sx, A(R >= 0.999f ? kGreen : kWhite, R >= 0.999f ? 0.55f + 0.3f * Pulse(1.5f) : 0.35f), 0.7f * Sx, 0, 1);
		}
		return false;
	}
	const iv::BoardPhase Ph = B.phase();
	if (Ph == iv::BoardPhase::Hacking)
	{
		DrawRect(FLinearColor(0.f, 0.02f, 0.04f, 0.9f), 0, 0, W, H);
		DrawHack(B.hack(), Sx);
	}
	else
	{
		// cinematic bars
		DrawRect(FLinearColor(0, 0, 0, 0.85f), 0, 0, W, H * 0.09f);
		DrawRect(FLinearColor(0, 0, 0, 0.85f), 0, H * 0.91f, W, H * 0.09f);
	}
	const TCHAR* Cap = TEXT("");
	switch (Ph)
	{
	case iv::BoardPhase::ClimbOut: Cap = TEXT("ВЫХОД ИЗ КАБИНЫ"); break;
	case iv::BoardPhase::OnShoulder: Cap = TEXT("НА ПЛЕЧЕ МЕХА"); break;
	case iv::BoardPhase::HookLaunch: Cap = TEXT("ЗАПУСК АБОРДАЖНОГО КРЮКА"); break;
	case iv::BoardPhase::HookFlight: Cap = TEXT("ПОЛЁТ НА ТРОСЕ"); break;
	case iv::BoardPhase::Landing: Cap = TEXT("ПРИЗЕМЛЕНИЕ НА ПЛЕЧО ПРОТИВНИКА"); break;
	case iv::BoardPhase::GrenadeThrow: Cap = TEXT("ГРАНАТА В ЛЮК"); break;
	case iv::BoardPhase::Escape: Cap = TEXT("ОТХОД"); break;
	case iv::BoardPhase::WatchBlast: Cap = TEXT("ВЗРЫВ"); break;
	case iv::BoardPhase::ReturnHook: Cap = TEXT("ВЗЛОМ ПРОВАЛЕН — ВОЗВРАТ ПО ТРОСУ"); break;
	case iv::BoardPhase::ClimbIn: Cap = TEXT("ВОЗВРАТ В КАБИНУ"); break;
	case iv::BoardPhase::HookSwing: Cap = TEXT("ПРЫЖОК НА ДРУГОЕ ПЛЕЧО"); break;
	default: break;
	}
	if (Ph != iv::BoardPhase::Hacking)
	{
		Text(Cap, CX, H * 0.91f + 12.f * Sx, A(kWhite, 0.95f), 1.4f * Sx, 2, 1);
		if (B.phaseLength() > 0)
		{
			const float U = FMath::Clamp(float(B.phaseTicks()) / float(B.phaseLength()), 0.f, 1.f);
			DrawRect(A(FLinearColor::Black, 0.6f), CX - 260.f * Sx, H * 0.91f + 52.f * Sx, 520.f * Sx, 5.f * Sx);
			DrawRect(A(kCyan, 0.9f), CX - 260.f * Sx, H * 0.91f + 52.f * Sx, 520.f * Sx * U, 5.f * Sx);
		}
		Text(TEXT("ПИЛОТ СНАРУЖИ  ·  МЕХ НА АВТОПИЛОТЕ"), CX, H * 0.09f + 10.f * Sx, A(kCyan, 0.75f), 0.8f * Sx, 1, 1);
	}
	if (B.swatActive())
	{
		const float Pu = 0.5f + 0.5f * Pulse(6.f);
		DrawRect(FLinearColor(0.7f, 0.02f, 0.f, 0.18f * Pu), 0, 0, W, H);
		Text(TEXT("РУКА ПРОТИВНИКА!"), CX, H * 0.2f, A(kRed, 0.6f + 0.4f * Pu), 3.0f * Sx, 2, 1);
		Text(FString::Printf(TEXT("Q / E — ПРЫЖОК НА ДРУГОЕ ПЛЕЧО  ·  %.1f c"), B.swatTicksToImpact() / 60.f), CX, H * 0.2f + 76.f * Sx, A(kWhite, 0.95f), 1.1f * Sx, 1, 1);
	}
	return Ph == iv::BoardPhase::Hacking;
}

void AIVHUD::DrawHack(const iv::HackGame& G, float Sx)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float CX = W * 0.5f;
	const float PW = 1020.f * Sx, PH = 640.f * Sx, PX = CX - PW * 0.5f, PY = H * 0.5f - PH * 0.5f;
	Panel(PX, PY, PW, PH, FLinearColor(0.f, 0.05f, 0.07f, 0.8f), A(G.alarm() ? kRed : kCyan, 0.9f));
	const TCHAR* Kind = G.stage() == iv::HackStage::Path ? TEXT("МАРШРУТ") : (G.stage() == iv::HackStage::Rhythm ? TEXT("РИТМ") : TEXT("ЧАСТОТА"));
	Text(FString::Printf(TEXT("ВЗЛОМ ЛЮКА  ·  СЛОЙ %d / %d  ·  %s%s"), G.stageIndex() + 1, G.stageCount(), Kind, G.boss() ? TEXT("  ·  ЯДРО") : TEXT("")), PX + 20.f * Sx, PY + 12.f * Sx, A(kWhite, 1.f), 1.2f * Sx, 2);
	// timer, ICE heat, mistakes
	const float Tl = G.timeLimit() > 0 ? FMath::Clamp(float(G.ticksLeft()) / float(G.timeLimit()), 0.f, 1.f) : 0.f;
	auto Bar = [&](float X, float Y, float BW, float V, const FLinearColor& C, const TCHAR* L)
	{
		DrawRect(A(FLinearColor::Black, 0.6f), X, Y, BW, 10.f * Sx);
		DrawRect(A(C, 0.9f), X, Y, BW * FMath::Clamp(V, 0.f, 1.f), 10.f * Sx);
		Text(L, X, Y - 16.f * Sx, A(C, 0.95f), 0.7f * Sx, 0);
	};
	Bar(PX + 20.f * Sx, PY + 72.f * Sx, 300.f * Sx, Tl, Tl < 0.25f ? kRed : kYellow, *FString::Printf(TEXT("ВРЕМЯ  %.1f c"), G.ticksLeft() / 60.f));
	Bar(PX + 350.f * Sx, PY + 72.f * Sx, 300.f * Sx, G.heat(), G.heat() > 0.7f ? kRed : kOrange, TEXT("НАГРЕВ ЛЬДА (ICE)"));
	Text(FString::Printf(TEXT("ОШИБОК: %d    ПОПЫТОК ICE: %d"), G.mistakes(), G.iceTrips()), PX + 690.f * Sx, PY + 60.f * Sx, A(kWhite, 0.85f), 0.8f * Sx, 1);
	DrawRect(A(kCyan, 0.4f), PX + 14.f * Sx, PY + 98.f * Sx, PW - 28.f * Sx, 1.5f);
	const float AY = PY + 112.f * Sx, AH = PH - 190.f * Sx;
	const float ACX = CX;
	switch (G.stage())
	{
	case iv::HackStage::Path:
	{
		const iv::PathLayout& L = G.path();
		if (L.w <= 0 || L.h <= 0) break;
		const float Cs = FMath::Min(PW * 0.8f / L.w, AH / L.h);
		const float X0 = ACX - Cs * L.w * 0.5f, Y0 = AY + (AH - Cs * L.h) * 0.5f;
		for (int32 y = 0; y < L.h; ++y)
			for (int32 x = 0; x < L.w; ++x)
			{
				const uint8 C = L.cell[size_t(y * L.w + x)];
				const float Cx = X0 + x * Cs, Cy = Y0 + y * Cs;
				FLinearColor Col = A(kCyan, 0.07f);
				if (C == 1) Col = FLinearColor(0.5f, 0.1f, 0.08f, 0.8f);
				else if (C == 2) Col = FLinearColor(0.15f, 0.5f, 0.9f, 0.55f);
				if (G.pathVisited(x, y)) Col = A(kGreen, 0.28f);
				DrawRect(Col, Cx + 2.f, Cy + 2.f, Cs - 4.f, Cs - 4.f);
				if (C == 2) Text(TEXT("~"), Cx + Cs * 0.5f, Cy + Cs * 0.2f, A(kWhite, 0.8f), 1.0f * Sx, 1, 1);
			}
		for (int32 k = 0; k < int32(L.keys.Num()) ; ++k) {}
		for (size_t k = 0; k < L.keys.size(); ++k)
		{
			const int32 Idx = L.keys[k];
			const float Cx = X0 + (Idx % L.w) * Cs, Cy = Y0 + (Idx / L.w) * Cs;
			const bool bTaken = int32(k) < G.pathKeysTaken();
			DrawRect(A(bTaken ? kGreen : kYellow, bTaken ? 0.3f : 0.9f), Cx + Cs * 0.25f, Cy + Cs * 0.25f, Cs * 0.5f, Cs * 0.5f);
			Text(FString::Printf(TEXT("%d"), int32(k) + 1), Cx + Cs * 0.5f, Cy + Cs * 0.25f, A(FLinearColor::Black, 0.9f), 0.8f * Sx, 1, 1);
		}
		DrawRect(A(kGreen, 0.8f), X0 + L.sx * Cs + 4.f, Y0 + L.sy * Cs + 4.f, Cs - 8.f, Cs - 8.f);
		Text(TEXT("ВХ"), X0 + (L.sx + 0.5f) * Cs, Y0 + L.sy * Cs + Cs * 0.25f, A(FLinearColor::Black, 1.f), 0.8f * Sx, 1, 1);
		DrawRect(A(kRed, 0.55f + 0.3f * Pulse(2.f)), X0 + L.cx * Cs + 4.f, Y0 + L.cy * Cs + 4.f, Cs - 8.f, Cs - 8.f);
		Text(TEXT("ЯДРО"), X0 + (L.cx + 0.5f) * Cs, Y0 + L.cy * Cs + Cs * 0.25f, A(kWhite, 1.f), 0.7f * Sx, 1, 1);
		const float Px = X0 + G.pathX() * Cs, Py = Y0 + G.pathY() * Cs;
		DrawRect(A(kWhite, 0.95f), Px + Cs * 0.2f, Py + Cs * 0.2f, Cs * 0.6f, Cs * 0.6f);
		Text(TEXT("WASD / стрелки — ход   ·   Backspace — шаг назад (штраф)   ·   ключи — по порядку   ·   ~ лёд скользит дальше"), ACX, PY + PH - 72.f * Sx, A(kWhite, 0.7f), 0.75f * Sx, 1, 1);
		break;
	}
	case iv::HackStage::Rhythm:
	{
		const iv::RhythmLayout& L = G.rhythm();
		const int32 Lanes = 5;
		const float LW = 120.f * Sx, X0 = ACX - LW * Lanes * 0.5f;
		const float HitY = AY + AH - 40.f * Sx;
		const float Px = 3.6f * Sx;   // pixels per tick
		const int32 Now = G.stageTick();
		static const TCHAR* Names2[5] = { TEXT("A  ВЛЕВО"), TEXT("S  ВНИЗ"), TEXT("W  ВВЕРХ"), TEXT("D  ВПРАВО"), TEXT("ENTER") };
		for (int32 k = 0; k < Lanes; ++k)
		{
			DrawRect(A(kCyan, 0.06f), X0 + k * LW + 3.f, AY, LW - 6.f, AH);
			Text(Names2[k], X0 + (k + 0.5f) * LW, HitY + 14.f * Sx, A(kWhite, 0.8f), 0.75f * Sx, 1, 1);
		}
		DrawRect(A(kWhite, 0.8f), X0, HitY, LW * Lanes, 3.f);
		const int32 Win = G.rhythmWindow();
		DrawRect(A(kGreen, 0.12f), X0, HitY - Win * Px, LW * Lanes, 2.f * Win * Px);
		for (size_t i = 0; i < L.impulses.size(); ++i)
		{
			const iv::RhythmImpulse& Im = L.impulses[i];
			const float Y = HitY - float(Im.tick - Now) * Px;
			if (Y < AY - 20.f || Y > AY + AH + 20.f) continue;
			const int32 St = G.rhythmStatus(i);
			const FLinearColor C = St == 1 ? kGreen : (St == 2 ? kRed : kYellow);
			DrawRect(A(C, St == 0 ? 0.95f : 0.3f), X0 + Im.lane * LW + 10.f, Y - 9.f * Sx, LW - 20.f, 18.f * Sx);
		}
		Text(TEXT("Жми кнопку дорожки, когда импульс на белой линии. Промах или лишнее нажатие — ошибка"), ACX, PY + PH - 72.f * Sx, A(kWhite, 0.7f), 0.75f * Sx, 1, 1);
		break;
	}
	default:
	{
		const float R = FMath::Min(AH * 0.46f, 220.f * Sx), CY = AY + AH * 0.5f;
		const int32 N = 72;
		for (int32 k = 0; k < N; ++k)
		{
			const float a0 = 6.2831853f * k / N, a1 = 6.2831853f * (k + 1) / N;
			DrawLine(ACX + FMath::Cos(a0) * R, CY + FMath::Sin(a0) * R, ACX + FMath::Cos(a1) * R, CY + FMath::Sin(a1) * R, A(kCyan, 0.3f), 2.f);
		}
		const float Ice = FMath::DegreesToRadians(G.iceAngle()), Half = FMath::DegreesToRadians(G.freqHalfWidth());
		for (int32 k = 0; k < 24; ++k)
		{
			const float a0 = Ice - Half + 2.f * Half * k / 24.f, a1 = Ice - Half + 2.f * Half * (k + 1) / 24.f;
			DrawLine(ACX + FMath::Cos(a0) * R, CY + FMath::Sin(a0) * R, ACX + FMath::Cos(a1) * R, CY + FMath::Sin(a1) * R, A(kRed, 0.95f), 12.f * Sx);
		}
		const float Hk = FMath::DegreesToRadians(G.hackerAngle());
		DrawLine(ACX, CY, ACX + FMath::Cos(Hk) * R * 1.05f, CY + FMath::Sin(Hk) * R * 1.05f, A(kGreen, 0.95f), 4.f);
		const bool bIn = FMath::Abs(G.freqOffset()) <= G.freqHalfWidth();
		Text(bIn ? TEXT("ЗАХВАТ!") : TEXT("ЖДИ"), ACX, CY - 14.f * Sx, A(bIn ? kGreen : kWhite, 1.f), 1.6f * Sx, 2, 1);
		Text(FString::Printf(TEXT("ЗАМКОВ %d / %d"), G.freqLocks(), G.freq().locks), ACX, CY + 34.f * Sx, A(kWhite, 0.9f), 0.9f * Sx, 1, 1);
		Text(TEXT("ENTER / ПРОБЕЛ — зафиксировать, когда зелёная стрелка внутри красного окна"), ACX, PY + PH - 72.f * Sx, A(kWhite, 0.7f), 0.75f * Sx, 1, 1);
		break;
	}
	}
	Text(TEXT("H — прервать взлом (вернуться по тросу)    ·    Q / E — перепрыгнуть на другое плечо при замахе руки"), ACX, PY + PH - 36.f * Sx, A(kCyan, 0.7f), 0.7f * Sx, 1, 1);
	DrawRect(A(FLinearColor::Black, 0.6f), PX + 20.f * Sx, PY + PH - 14.f * Sx, PW - 40.f * Sx, 6.f * Sx);
	DrawRect(A(kGreen, 0.9f), PX + 20.f * Sx, PY + PH - 14.f * Sx, (PW - 40.f * Sx) * FMath::Clamp(G.progress(), 0.f, 1.f), 6.f * Sx);
}
'''
marker = "// ------------------------------------------------------------------------------------------------------- menu"
assert marker in s
s = s.replace(marker, code + "\n" + marker, 1)
s = s.replace("		for (int32 k = 0; k < int32(L.keys.Num()) ; ++k) {}\n", "")
io.open(p, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)
print("hud patched")

#include "IVHUD.h"
#include "IVMechPawn.h"
#include "IVCombat.h"
#include "IVFlow.h"
#include "IVPlayerController.h"
#include "Engine/Engine.h"
#include "Engine/Canvas.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	const FLinearColor kCyan(0.25f, 0.9f, 1.f, 1.f);
	const FLinearColor kCyanDim(0.15f, 0.55f, 0.75f, 1.f);
	const FLinearColor kOrange(1.f, 0.55f, 0.16f, 1.f);
	const FLinearColor kRed(1.f, 0.25f, 0.18f, 1.f);
	const FLinearColor kYellow(1.f, 0.88f, 0.3f, 1.f);
	const FLinearColor kGreen(0.4f, 1.f, 0.55f, 1.f);
	const FLinearColor kWhite(0.92f, 0.96f, 1.f, 1.f);

	FLinearColor A(FLinearColor C, float Alpha) { C.A = Alpha; return C; }

	const FLinearColor kZoneCol[7] = {
		FLinearColor(0.35f, 0.9f, 1.f, 0.9f), FLinearColor(0.7f, 0.95f, 0.7f, 0.9f), FLinearColor(1.f, 0.9f, 0.35f, 0.92f), FLinearColor(1.f, 0.6f, 0.15f, 0.95f),
		FLinearColor(1.f, 0.22f, 0.12f, 0.95f), FLinearColor(0.38f, 0.06f, 0.05f, 0.95f), FLinearColor(0.1f, 0.02f, 0.02f, 0.9f) };
}

float AIVHUD::Pulse(float Hz) const { return 0.5f + 0.5f * FMath::Sin(GetWorld()->GetTimeSeconds() * Hz * 6.2831853f); }

void AIVHUD::Text(const FString& S, float X, float Y, const FLinearColor& C, float Scale, int32 Font, int32 Align)
{
	UFont* F = Font == 0 ? GEngine->GetSmallFont() : (Font == 1 ? GEngine->GetMediumFont() : GEngine->GetLargeFont());
	float W = 0.f, H = 0.f;
	GetTextSize(S, W, H, F, Scale);
	const float X0 = Align == 1 ? X - W * 0.5f : (Align == 2 ? X - W : X);
	DrawText(S, C, X0, Y, F, Scale);
}

void AIVHUD::Panel(float X, float Y, float W, float H, const FLinearColor& Fill, const FLinearColor& Edge)
{
	DrawRect(Fill, X, Y, W, H);
	DrawLine(X, Y, X + W, Y, Edge, 1.5f);
	DrawLine(X, Y + H, X + W, Y + H, Edge, 1.5f);
	DrawLine(X, Y, X, Y + H, Edge, 1.5f);
	DrawLine(X + W, Y, X + W, Y + H, Edge, 1.5f);
	const float K = FMath::Min(14.f, H * 0.4f);
	DrawLine(X - 4, Y - 4, X - 4 + K, Y - 4, A(Edge, 1.f), 2.5f);
	DrawLine(X - 4, Y - 4, X - 4, Y - 4 + K, A(Edge, 1.f), 2.5f);
	DrawLine(X + W + 4, Y + H + 4, X + W + 4 - K, Y + H + 4, A(Edge, 1.f), 2.5f);
	DrawLine(X + W + 4, Y + H + 4, X + W + 4, Y + H + 4 - K, A(Edge, 1.f), 2.5f);
}

void AIVHUD::Wrap(const FString& S, float X, float Y, float MaxW, const FLinearColor& C, float Scale, float LineH)
{
	TArray<FString> Words;
	S.ParseIntoArray(Words, TEXT(" "));
	FString Line;
	UFont* F = GEngine->GetMediumFont();
	for (const FString& W : Words)
	{
		const FString Try = Line.IsEmpty() ? W : Line + TEXT(" ") + W;
		float TW = 0.f, TH = 0.f;
		GetTextSize(Try, TW, TH, F, Scale);
		if (TW > MaxW && !Line.IsEmpty())
		{
			DrawText(Line, C, X, Y, F, Scale);
			Y += LineH;
			Line = W;
		}
		else Line = Try;
	}
	if (!Line.IsEmpty()) DrawText(Line, C, X, Y, F, Scale);
}

// ------------------------------------------------------------------------------------------------------- main
void AIVHUD::DrawHUD()
{
	Super::DrawHUD();
	if (!Canvas) return;
	AIVGameFlow* Flow = nullptr;
	for (TActorIterator<AIVGameFlow> It(GetWorld()); It; ++It) { Flow = *It; break; }
	if (Flow && Flow->GetState() == EIVFlowState::Menu) { DrawMenu(Flow); return; }

	static IConsoleVariable* Cam = IConsoleManager::Get().FindConsoleVariable(TEXT("iv.Cam"));
	if (Cam && Cam->GetInt() != 0) return;

	AIVMechPawn* Me = Cast<AIVMechPawn>(GetOwningPawn());
	AIVCombatDirector* Dir = nullptr;
	for (TActorIterator<AIVCombatDirector> It(GetWorld()); It; ++It) { Dir = *It; break; }
	AIVPlayerController* PC = Cast<AIVPlayerController>(GetOwningPlayerController());
	const float CX = Canvas->ClipX * 0.5f, CY = Canvas->ClipY * 0.5f;

	// ---- crosshair
	const FLinearColor Blue = A(kCyan, 0.6f);
	DrawLine(CX - 16, CY, CX - 6, CY, Blue, 1.5f);
	DrawLine(CX + 6, CY, CX + 16, CY, Blue, 1.5f);
	DrawLine(CX, CY - 16, CX, CY - 6, Blue, 1.5f);
	DrawLine(CX, CY + 6, CX, CY + 16, Blue, 1.5f);

	if (Me) DrawLockBracket(Me);
	if (PC) DrawTrail(PC);

	if (Dir && Dir->GetDuel())
	{
		const iv::Duel& Du = *Dir->GetDuel();
		const iv::Fighter& FA = Du.fighter(iv::Side::A);
		const iv::Fighter& FB = Du.fighter(iv::Side::B);
		const float W = Canvas->ClipX, H = Canvas->ClipY;
		// player: schematic and bars, lower left (the glass above the dash)
		Panel(26.f, H - 232.f, 260.f, 206.f, FLinearColor(0.f, 0.03f, 0.05f, 0.5f), A(kCyanDim, 0.8f));
		DrawMechDiagram(FA, 120.f, H - 214.f, 52.f, false);
		DrawBars(FA, 176.f, H - 214.f, 100.f);
		Text(TEXT("ТВОЙ МЕХ"), 36.f, H - 226.f, A(kCyan, 0.9f), 0.8f, 0);
		DrawStatuses(FA, 36.f, H - 44.f, false);
		// opponent: schematic top right
		Panel(W - 186.f, 22.f, 160.f, 168.f, FLinearColor(0.05f, 0.f, 0.f, 0.45f), A(kRed, 0.7f));
		DrawMechDiagram(FB, W - 106.f, 38.f, 44.f, true);
		Text(TEXT("ПРОТИВНИК"), W - 176.f, 26.f, A(kRed, 0.95f), 0.8f, 0);
		DrawStatuses(FB, W - 176.f, 172.f, false);
		{
			const float St = FB.res.stability / 100.f;
			DrawRect(FLinearColor(0, 0, 0, 0.55f), W - 176.f, 160.f, 140.f, 6.f);
			DrawRect(A(kRed, 0.9f), W - 176.f, 160.f, 140.f * FMath::Clamp(St, 0.f, 1.f), 6.f);
		}
		DrawAbilities(Dir, FA);
		// the sensors are blinded: dust / glare over the glass
		if (Me)
		{
			const float Bl = Me->GetBlind01();
			if (Bl > 0.f)
			{
				DrawRect(FLinearColor(0.72f, 0.7f, 0.64f, 0.92f * FMath::Min(1.f, Bl * 2.2f)), 0, 0, W, H);
				const float Pu = 0.55f + 0.45f * Pulse(2.f);
				Text(TEXT("ДАТЧИКИ ОСЛЕПЛЕНЫ"), CX, CY - 20.f, A(kRed, Pu * FMath::Min(1.f, Bl * 3.f)), 2.2f, 2, 1);
				Text(TEXT("Блокируй по звуку — сектор замаха не виден"), CX, CY + 50.f, A(FLinearColor(0.1f, 0.1f, 0.12f), Pu * FMath::Min(1.f, Bl * 3.f)), 1.0f, 1, 1);
			}
		}
	}
	if (Flow)
	{
		if (Flow->GetState() == EIVFlowState::Tutorial) DrawTutorial(Flow);
		DrawBanner(Flow);
	}
}

// ------------------------------------------------------------------------------------------------------- menu
void AIVHUD::DrawMenu(AIVGameFlow* Flow)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	// letterbox + side gradient so the fight behind stays visible
	DrawRect(FLinearColor(0, 0, 0, 0.78f), 0, 0, W, H * 0.09f);
	DrawRect(FLinearColor(0, 0, 0, 0.78f), 0, H * 0.91f, W, H * 0.09f);
	for (int32 i = 0; i < 28; ++i)
	{
		const float T = float(i) / 28.f;
		DrawRect(FLinearColor(0.01f, 0.02f, 0.05f, 0.72f * (1.f - T) * (1.f - T)), W * 0.5f * T * 0.62f, H * 0.09f, W * 0.5f * 0.62f / 28.f + 1.f, H * 0.82f);
	}
	const float X = W * 0.07f;
	float Y = H * 0.22f;
	const float Sx = W / 1600.f;
	// title with a glowing outline
	const FString Title = TEXT("IMPACT VECTOR");
	for (int32 k = 0; k < 6; ++k)
	{
		const float A0 = 0.07f * (6 - k);
		Text(Title, X + k * 0.8f, Y + k * 0.8f, A(kCyan, A0), 4.3f * Sx, 2);
		Text(Title, X - k * 0.8f, Y - k * 0.8f, A(kCyan, A0), 4.3f * Sx, 2);
	}
	Text(Title, X, Y, kWhite, 4.3f * Sx, 2);
	DrawLine(X, Y + 112.f * Sx, X + 640.f * Sx, Y + 112.f * Sx, A(kCyan, 0.8f), 2.f);
	Text(TEXT("ДУЭЛЬ ГИГАНТСКИХ МЕХОВ  ·  ТОКИО  ·  ТУМАН И ДОЖДЬ"), X, Y + 124.f * Sx, A(kCyan, 0.85f), 1.2f * Sx, 1);
	Y = H * 0.50f;
	const TArray<FString> Items = Flow->GetMenuItems();
	for (int32 i = 0; i < Items.Num(); ++i)
	{
		const bool bSel = i == Flow->GetMenuIndex();
		const float Yy = Y + i * 78.f * Sx;
		if (bSel)
		{
			DrawRect(A(kCyan, 0.16f + 0.06f * Pulse(2.f)), X - 14.f, Yy - 6.f, 560.f * Sx, 56.f * Sx);
			DrawLine(X - 14.f, Yy - 6.f, X - 14.f, Yy + 50.f * Sx, kCyan, 4.f);
			Text(TEXT("▶"), X + 4.f, Yy + 2.f, kCyan, 1.7f * Sx, 2);
		}
		Text(Items[i], X + 54.f, Yy, bSel ? kWhite : A(kWhite, 0.55f), 1.9f * Sx, 2);
	}
	Text(TEXT("W / S — выбор    ·    A / D — сложность    ·    Enter — старт    ·    Esc — в меню из боя"), X, H * 0.91f - 34.f, A(kWhite, 0.65f), 0.95f * Sx, 1);
	Text(TEXT("Клавиатура + мышь или геймпад"), X, H * 0.91f - 12.f, A(kCyan, 0.55f), 0.8f * Sx, 0);
}

// ------------------------------------------------------------------------------------------------------- tutorial
void AIVHUD::DrawTutorial(AIVGameFlow* Flow)
{
	if (!Flow->HasPrompt()) return;
	const FIVTutorialStep& S = Flow->GetStep();
	const float W = Canvas->ClipX;
	const float PW = FMath::Min(W * 0.62f, 1000.f), PX = (W - PW) * 0.5f, PY = 24.f;
	const float Sx = FMath::Clamp(W / 1600.f, 0.8f, 1.4f);
	const bool bDone = Flow->GetStepDoneFlash() > 0.f;
	const FLinearColor Edge = bDone ? kGreen : kCyan;
	// body height from the amount of text
	const float BodyH = 28.f * Sx * FMath::CeilToFloat(float(S.Body.Len()) * 0.0105f * 1.f / FMath::Max(PW / 1000.f, 0.5f)) + 6.f;
	const float H = 70.f * Sx + BodyH + (S.Keys.IsEmpty() ? 0.f : 30.f * Sx) + 26.f;
	Panel(PX, PY, PW, H, FLinearColor(0.f, 0.03f, 0.06f, 0.72f), A(Edge, 0.9f));
	Text(FString::Printf(TEXT("ШАГ %d / %d"), Flow->GetStepIndex() + 1, Flow->GetStepCount()), PX + 16.f, PY + 8.f, A(Edge, 0.8f), 0.85f * Sx, 0);
	Text(S.Title, PX + 16.f, PY + 24.f * Sx, bDone ? kGreen : kWhite, 1.45f * Sx, 2);
	Wrap(S.Body, PX + 16.f, PY + 62.f * Sx, PW - 32.f, A(kWhite, 0.92f), 0.82f * Sx, 24.f * Sx);
	if (!S.Keys.IsEmpty()) Text(S.Keys, PX + 16.f, PY + H - 54.f * Sx, kOrange, 0.8f * Sx, 1);
	// progress
	const float Pr = Flow->GetStepProgress01();
	DrawRect(FLinearColor(0, 0, 0, 0.6f), PX + 16.f, PY + H - 20.f, PW - 32.f, 7.f);
	DrawRect(bDone ? kGreen : kCyan, PX + 16.f, PY + H - 20.f, (PW - 32.f) * Pr, 7.f);
	if (bDone) Text(TEXT("ВЫПОЛНЕНО"), PX + PW - 16.f, PY + 10.f, kGreen, 1.0f * Sx, 1, 2);
}

// ------------------------------------------------------------------------------------------------------- vector trail
void AIVHUD::DrawTrail(AIVPlayerController* PC)
{
	const TArray<FVector2D>& T = PC->GetTrail();
	const float Fade = PC->IsTrailLive() ? 1.f : PC->GetTrailFade();
	if (T.Num() < 1 || Fade <= 0.f) return;
	const float CX = Canvas->ClipX * 0.5f, CY = Canvas->ClipY * 0.5f;
	const float R = Canvas->ClipY * 0.30f;
	auto P = [&](const FVector2D& V) { return FVector2D(CX + V.X * R, CY - V.Y * R); };
	// guide: the 8 body sectors (head / shoulders / arms / legs / reactor) and the neutral ring
	if (PC->IsTrailLive())
	{
		const FLinearColor G = A(kCyan, 0.16f);
		const int32 N = 40;
		for (int32 i = 0; i < N; ++i)
		{
			const float a0 = i * 6.2831853f / N, a1 = (i + 1) * 6.2831853f / N;
			DrawLine(CX + FMath::Cos(a0) * R * 0.45f, CY + FMath::Sin(a0) * R * 0.45f, CX + FMath::Cos(a1) * R * 0.45f, CY + FMath::Sin(a1) * R * 0.45f, G, 1.f);
			DrawLine(CX + FMath::Cos(a0) * R, CY + FMath::Sin(a0) * R, CX + FMath::Cos(a1) * R, CY + FMath::Sin(a1) * R, A(kCyan, 0.08f), 1.f);
		}
		const TCHAR* Names[8] = { TEXT("ГОЛОВА"), TEXT("ПЛЕЧО"), TEXT("РУКА"), TEXT("НОГА"), TEXT("РЕАКТОР"), TEXT("НОГА"), TEXT("РУКА"), TEXT("ПЛЕЧО") };
		for (int32 i = 0; i < 8; ++i)
		{
			const float Ang = i * 0.7853982f;
			const FVector2D D(FMath::Sin(Ang), FMath::Cos(Ang));
			DrawLine(CX + D.X * R * 0.45f, CY - D.Y * R * 0.45f, CX + D.X * R * 0.58f, CY - D.Y * R * 0.58f, G, 1.f);
			Text(Names[i], CX + D.X * R * 0.72f, CY - D.Y * R * 0.72f - 8.f, A(kCyan, 0.32f), 0.6f, 0, 1);
		}
	}
	// the stroke itself: thick soft pass + bright core, widening towards the head of the stroke
	for (int32 i = 1; i < T.Num(); ++i)
	{
		const FVector2D a = P(T[i - 1]), b = P(T[i]);
		const float K = float(i) / float(T.Num());
		DrawLine(a.X, a.Y, b.X, b.Y, A(kCyan, 0.22f * Fade), 9.f * K + 2.f);
		DrawLine(a.X, a.Y, b.X, b.Y, A(kWhite, (0.35f + 0.65f * K) * Fade), 2.f + 2.f * K);
	}
	const FVector2D Tip = P(T.Last());
	DrawRect(A(kWhite, Fade), Tip.X - 4.f, Tip.Y - 4.f, 8.f, 8.f);
	DrawRect(A(kCyan, 0.35f * Fade), Tip.X - 9.f, Tip.Y - 9.f, 18.f, 18.f);
}

// ------------------------------------------------------------------------------------------------------- diagrams
void AIVHUD::DrawMechDiagram(const iv::Fighter& F, float X, float Y, float S, bool bFront)
{
	struct R { iv::Zone Z; float x, y, w, h; };
	// unit coordinates, seen from behind (left = mech's left)
	const R Parts[] = {
		{ iv::Zone::Head, -0.24f, 0.00f, 0.48f, 0.42f },
		{ iv::Zone::Torso, -0.52f, 0.46f, 1.04f, 0.78f },
		{ iv::Zone::Reactor, -0.18f, 0.62f, 0.36f, 0.30f },
		{ iv::Zone::ShoulderL, -1.00f, 0.46f, 0.44f, 0.34f },
		{ iv::Zone::ShoulderR, 0.56f, 0.46f, 0.44f, 0.34f },
		{ iv::Zone::ArmL, -1.02f, 0.84f, 0.38f, 0.92f },
		{ iv::Zone::ArmR, 0.64f, 0.84f, 0.38f, 0.92f },
		{ iv::Zone::LegL, -0.50f, 1.30f, 0.44f, 1.05f },
		{ iv::Zone::LegR, 0.06f, 1.30f, 0.44f, 1.05f },
	};
	for (const R& P : Parts)
	{
		float x = P.x;
		if (bFront) x = -(P.x + P.w);
		const iv::ZoneState St = F.body.state(P.Z);
		FLinearColor C = kZoneCol[int32(St)];
		if (P.Z == iv::Zone::Reactor && !bFront) C.A *= 0.55f;
		if (St >= iv::ZoneState::Critical && St < iv::ZoneState::Destroyed) C.A *= 0.65f + 0.35f * Pulse(3.f);
		const float x0 = X + x * S, y0 = Y + P.y * S, w = P.w * S, h = P.h * S;
		DrawRect(C, x0, y0, w, h);
		DrawLine(x0, y0, x0 + w, y0, A(kWhite, 0.35f), 1.f);
		DrawLine(x0, y0 + h, x0 + w, y0 + h, A(FLinearColor::Black, 0.6f), 1.f);
		if (St == iv::ZoneState::Severed) { DrawLine(x0, y0, x0 + w, y0 + h, kRed, 2.f); DrawLine(x0 + w, y0, x0, y0 + h, kRed, 2.f); }
	}
}

void AIVHUD::DrawBars(const iv::Fighter& F, float X, float Y, float W)
{
	auto Bar = [&](float Yy, const TCHAR* Label, float V, const FLinearColor& C)
	{
		Text(Label, X, Yy - 1.f, A(C, 0.9f), 0.65f, 0);
		DrawRect(FLinearColor(0, 0, 0, 0.6f), X + 22.f, Yy + 2.f, W - 22.f, 9.f);
		DrawRect(A(C, 0.95f), X + 23.f, Yy + 3.f, (W - 24.f) * FMath::Clamp(V, 0.f, 1.f), 7.f);
	};
	Bar(Y, TEXT("УС"), F.res.stability / 100.f, kCyan);
	Bar(Y + 26.f, TEXT("ТП"), F.res.heat / 100.f, F.res.heat > 65.f ? kRed : kOrange);
	Bar(Y + 52.f, TEXT("ЭН"), F.res.energy / 100.f, kGreen);
	Bar(Y + 78.f, TEXT("УЛ"), F.ultimate / 100.f, F.UltimateReady() ? kYellow : A(kYellow, 0.7f));
	if (F.UltimateReady()) Text(TEXT("V — УЛЬТИМЕЙТ"), X, Y + 100.f, A(kYellow, 0.6f + 0.4f * Pulse(3.f)), 0.8f, 1);
}

void AIVHUD::DrawStatuses(const iv::Fighter& F, float X, float Y, bool)
{
	float Xx = X;
	auto Chip = [&](const TCHAR* S, const FLinearColor& C)
	{
		float W = 0.f, H = 0.f;
		GetTextSize(S, W, H, GEngine->GetSmallFont(), 0.75f);
		DrawRect(A(C, 0.25f + 0.2f * Pulse(3.f)), Xx - 3.f, Y - 2.f, W + 8.f, H + 4.f);
		DrawText(S, C, Xx, Y, GEngine->GetSmallFont(), 0.75f);
		Xx += W + 14.f;
	};
	if (F.Blind()) Chip(TEXT("СЛЕП"), kYellow);
	if (F.strikeLockTicks > 0) Chip(TEXT("РУКИ ЗАБЛОКИРОВАНЫ"), kOrange);
	if (F.burnTicks > 0) Chip(TEXT("ГОРИТ"), kRed);
	if (F.stunImmune > 0) Chip(TEXT("УСТОЙЧИВ"), kCyan);
	if (F.ultimateLocked) Chip(TEXT("УЛЬТ УТРАЧЕН"), kRed);
}

void AIVHUD::DrawAbilities(AIVCombatDirector* Dir, const iv::Fighter& F)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	struct Slot { const TCHAR* Key; const TCHAR* Name; iv::WeaponKind Kind; };
	const Slot Slots[3] = { { TEXT("1"), TEXT("РАКЕТЫ"), iv::WeaponKind::SuppressionRockets }, { TEXT("2"), TEXT("КОПЬЁ"), iv::WeaponKind::RailSpear }, { TEXT("3"), TEXT("ПЛАЗМА"), iv::WeaponKind::PlasmaCannon } };
	const float SW = 92.f, SH = 52.f, Gap = 10.f;
	const float X0 = W * 0.5f - (4 * SW + 3 * Gap) * 0.5f, Y0 = H - 78.f;
	for (int32 i = 0; i < 4; ++i)
	{
		const float X = X0 + i * (SW + Gap);
		float Ready = 1.f;
		FString Key, Name;
		bool bSel = false;
		FLinearColor C = kCyan;
		if (i < 3)
		{
			const iv::WeaponKind K = Slots[i].Kind;
			const int32 Cd = F.CooldownOf(K);
			Ready = 1.f - FMath::Clamp(float(Cd) / float(iv::tune::kWeapons[iv::Index(K)].cooldownTicks), 0.f, 1.f);
			if (F.AmmoOf(K) == 0) Ready = 0.f;
			Key = Slots[i].Key; Name = Slots[i].Name;
			bSel = F.weapon == K;
			C = i == 0 ? kYellow : (i == 1 ? kOrange : kRed);
		}
		else
		{
			Ready = Dir->GetScoopReady01(iv::Side::A);
			Key = TEXT("F"); Name = TEXT("ЗДАНИЕ");
			C = kGreen;
		}
		const bool bReady = Ready >= 0.999f;
		Panel(X, Y0, SW, SH, FLinearColor(0.f, 0.03f, 0.05f, 0.62f), A(bSel ? kWhite : C, bReady ? 0.95f : 0.45f));
		DrawRect(A(C, bReady ? 0.35f + 0.15f * Pulse(2.f) : 0.28f), X + 2.f, Y0 + SH - 2.f - (SH - 4.f) * Ready, SW - 4.f, (SH - 4.f) * Ready);
		Text(Key, X + 8.f, Y0 + 4.f, bReady ? kWhite : A(kWhite, 0.55f), 1.0f, 1);
		Text(Name, X + SW * 0.5f, Y0 + SH - 20.f, bReady ? kWhite : A(kWhite, 0.55f), 0.72f, 0, 1);
		if (!bReady) Text(FString::Printf(TEXT("%d%%"), int32(Ready * 100.f)), X + SW - 6.f, Y0 + 5.f, A(kWhite, 0.65f), 0.7f, 0, 2);
	}
}

void AIVHUD::DrawBanner(AIVGameFlow* Flow)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	if (Flow->GetState() == EIVFlowState::Result)
	{
		const float T = FMath::Clamp(Flow->GetResultTime() / 0.6f, 0.f, 1.f);
		DrawRect(FLinearColor(0.f, 0.f, 0.02f, 0.55f * T), 0, 0, W, H);
		const bool bWin = Flow->GetBanner() == TEXT("ПОБЕДА");
		const FLinearColor C = bWin ? kGreen : kRed;
		Text(Flow->GetBanner(), W * 0.5f, H * 0.30f, A(C, T), 4.2f * W / 1600.f, 2, 1);
		DrawLine(W * 0.3f, H * 0.30f + 120.f, W * 0.7f, H * 0.30f + 120.f, A(C, 0.7f * T), 2.f);
		Text(Flow->GetSubBanner(), W * 0.5f, H * 0.30f + 140.f, A(kWhite, T), 1.1f, 1, 1);
		Text(TEXT("Enter — реванш с новым противником     ·     Esc — главное меню"), W * 0.5f, H * 0.30f + 200.f, A(kCyan, T * (0.6f + 0.4f * Pulse(1.5f))), 1.0f, 1, 1);
		return;
	}
	const float Al = Flow->GetBannerAlpha();
	if (Al <= 0.f) return;
	Text(Flow->GetBanner(), W * 0.5f, H * 0.34f, A(kWhite, Al), 3.6f * W / 1600.f, 2, 1);
	Text(Flow->GetSubBanner(), W * 0.5f, H * 0.34f + 100.f, A(kCyan, Al), 1.1f, 1, 1);
}

void AIVHUD::DrawLockBracket(AIVMechPawn* Me)
{
	for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It)
	{
		if (*It == Me) continue;
		const FVector C = It->GetActorLocation() + FVector(0, 0, 4400);
		const FVector P = Project(C);
		if (P.Z <= 0.f) continue;
		const float Dist = FVector::Dist(C, Me->GetEyeLocation());
		const float Half = FMath::Clamp(5200.f / Dist * Canvas->ClipY * 0.75f, 30.f, 420.f);
		const FLinearColor Col = A(kRed, 0.8f);
		const float L = Half * 0.3f;
		const float X0 = P.X - Half * 0.6f, X1 = P.X + Half * 0.6f, Y0 = P.Y - Half, Y1 = P.Y + Half;
		DrawLine(X0, Y0, X0 + L, Y0, Col, 2.f); DrawLine(X0, Y0, X0, Y0 + L, Col, 2.f);
		DrawLine(X1, Y0, X1 - L, Y0, Col, 2.f); DrawLine(X1, Y0, X1, Y0 + L, Col, 2.f);
		DrawLine(X0, Y1, X0 + L, Y1, Col, 2.f); DrawLine(X0, Y1, X0, Y1 - L, Col, 2.f);
		DrawLine(X1, Y1, X1 - L, Y1, Col, 2.f); DrawLine(X1, Y1, X1, Y1 - L, Col, 2.f);
		Text(FString::Printf(TEXT("%.0f м"), Dist / 100.f), P.X, Y1 + 6.f, A(kRed, 0.85f), 0.8f, 0, 1);
	}
}

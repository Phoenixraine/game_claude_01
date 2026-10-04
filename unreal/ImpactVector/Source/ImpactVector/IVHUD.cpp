#include "IVHUD.h"
#include "IVSettings.h"
#include "GameFramework/WorldSettings.h"
#include "IVHelicopter.h"
#include "EngineUtils.h"
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

	/** A helicopter on a low pass within the scoop's reach: the F action grabs it instead of a building. */
	bool HeliInReach(AHUD* H)
	{
		APawn* P = H->GetOwningPawn();
		if (!P || !H->GetWorld()) return false;
		for (TActorIterator<AIVHelicopter> It(H->GetWorld()); It; ++It)
			if (It->IsGrabbable() && FVector::Dist(It->GetActorLocation(), P->GetActorLocation()) < 16000.f) return true;
		return false;
	}

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
	{	// unobtrusive frame-rate readout in the bottom-left corner of the glass (F3 toggles)
		static float Fps = 60.f, Shown = 60.f, Acc = 0.f;
		const float Dt = GetWorld()->GetDeltaSeconds() / FMath::Max(GetWorld()->GetWorldSettings()->GetEffectiveTimeDilation(), 0.01f);
		if (Dt > 0.f) Fps = FMath::Lerp(Fps, 1.f / Dt, 0.05f);
		Acc += Dt;
		if (Acc > 0.5f) { Acc = 0.f; Shown = Fps; }
		if (APlayerController* Pc0 = GetOwningPlayerController()) if (Pc0->WasInputKeyJustPressed(EKeys::F3)) { IVSettings::Set(TEXT("fps_counter"), IVSettings::GetBool(TEXT("fps_counter")) ? 0.f : 1.f); }
		const bool bShow = IVSettings::GetBool(TEXT("fps_counter"));
		if (bShow)
		{
			const float Sx0 = FMath::Clamp(Canvas->ClipX / 1600.f, 0.6f, 1.6f);
			Text(FString::Printf(TEXT("%d FPS"), FMath::RoundToInt(Shown)), 8.f, Canvas->ClipY - 18.f * Sx0, A(Shown >= 58.f ? kGreen : (Shown >= 40.f ? kYellow : kRed), 0.32f), 0.55f * Sx0, 0, 0);
		}
	}
	AIVGameFlow* Flow = nullptr;
	for (TActorIterator<AIVGameFlow> It(GetWorld()); It; ++It) { Flow = *It; break; }
	if (Flow && Flow->GetState() == EIVFlowState::Menu) { DrawMenu(Flow); return; }
	if (Flow && Flow->GetState() == EIVFlowState::Join) { DrawJoin(Flow); return; }
	if (Flow && Flow->GetState() == EIVFlowState::Settings) { DrawSettings(Flow); return; }

	static IConsoleVariable* Cam = IConsoleManager::Get().FindConsoleVariable(TEXT("iv.Cam"));
	if (Cam && Cam->GetInt() != 0) return;

	AIVMechPawn* Me = Cast<AIVMechPawn>(GetOwningPawn());
	AIVCombatDirector* Dir = nullptr;
	for (TActorIterator<AIVCombatDirector> It(GetWorld()); It; ++It) { Dir = *It; break; }
	AIVPlayerController* PC = Cast<AIVPlayerController>(GetOwningPlayerController());
	const iv::Side MySide = PC ? PC->MySide : iv::Side::A;
	const float CX = Canvas->ClipX * 0.5f, CY = Canvas->ClipY * 0.5f;
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	// the glass HUD fades out while the pilot looks away from the dome (free look)
	const float LookFade = Me ? FMath::Clamp(1.f - (Me->GetLookAmount() - 0.35f) * 1.4f, 0.12f, 1.f) : 1.f;

	// ---- crosshair
	const FLinearColor Blue = A(kCyan, 0.55f * LookFade);
	DrawLine(CX - 14, CY, CX - 5, CY, Blue, 1.5f);
	DrawLine(CX + 5, CY, CX + 14, CY, Blue, 1.5f);
	DrawLine(CX, CY - 14, CX, CY - 5, Blue, 1.5f);
	DrawLine(CX, CY + 5, CX, CY + 14, Blue, 1.5f);

	bool bOutside = false;
	for (TActorIterator<AIVCombatDirector> It2(GetWorld()); It2; ++It2) { bOutside = It2->IsBoardingActive(); break; }
	if (Me && LookFade > 0.3f && !bOutside) DrawLockBracket(Me);
	if (PC) DrawTrail(PC);

	if (Dir && Dir->GetDuel() && MySide == iv::Side::A && DrawBoarding(Dir, FMath::Clamp(W / 1600.f, 0.55f, 1.4f))) return;
	if (Dir && Dir->GetDuel())
	{
		const iv::Duel& Du = *Dir->GetDuel();
		const iv::Fighter& FA = Du.fighter(MySide);
		const iv::Fighter& FB = Du.fighter(iv::Other(MySide));
		const float Sx = FMath::Clamp(W / 1600.f, 0.55f, 1.4f) * IVSettings::Get(TEXT("hud_scale"));
		const float Fd = LookFade;
		UIVCockpitComponent* Ck = Me ? Me->GetCockpitFx() : nullptr;
		const float Alert = Ck ? Ck->GetAlert() : 0.f;
		// ---- the alarm frame: the edges of the glass go red when the cockpit is in trouble
		if (Alert > 0.05f)
		{
			const float Pu = 0.45f + 0.55f * Pulse(Alert > 1.5f ? 3.2f : 1.6f);
			const float T = (18.f + 24.f * Alert) * Sx;
			const FLinearColor R = FLinearColor(1.f, 0.05f, 0.03f, 0.18f * Alert * Pu);
			for (int32 i = 0; i < 6; ++i)
			{
				const float k = float(i) / 6.f, a = R.A * (1.f - k);
				const FLinearColor C(1.f, 0.05f, 0.03f, a);
				DrawRect(C, 0, T * k, W, T / 6.f); DrawRect(C, 0, H - T * (k + 1.f / 6.f), W, T / 6.f);
				DrawRect(C, T * k, 0, T / 6.f, H); DrawRect(C, W - T * (k + 1.f / 6.f), 0, T / 6.f, H);
			}
			if (Alert > 0.6f) Text(Alert > 1.5f ? TEXT("КРИТИЧЕСКИЕ ПОВРЕЖДЕНИЯ") : TEXT("ТРЕВОГА"), CX, 14.f * Sx, A(kRed, Pu * Fd), 1.05f * Sx, 1, 1);
		}
		DrawGlassInfographics(FA, FB, Me, Sx, Fd);
		DrawSpecials(Dir, MySide, PC, Me, Sx);
		DrawParryWindow(Dir, MySide, Sx);
		DrawBreakdown(Dir, MySide, PC, Sx);
		if (PC && PC->IsRepairing()) DrawRepair(PC, FA, Sx);
		// the sensors are blinded: dust / glare over the glass
		if (Me)
		{
			const float Bl = Me->GetBlind01();
			if (Bl > 0.f)
			{
				DrawRect(FLinearColor(0.72f, 0.7f, 0.64f, 0.92f * FMath::Min(1.f, Bl * 2.2f)), 0, 0, W, H);
				const float Pu = 0.55f + 0.45f * Pulse(2.f);
				Text(TEXT("ДАТЧИКИ ОСЛЕПЛЕНЫ"), CX, CY - 20.f, A(kRed, Pu * FMath::Min(1.f, Bl * 3.f)), 2.2f * Sx, 2, 1);
				Text(TEXT("Блокируй по звуку — сектор замаха не виден"), CX, CY + 50.f * Sx, A(FLinearColor(0.1f, 0.1f, 0.12f), Pu * FMath::Min(1.f, Bl * 3.f)), 1.0f * Sx, 1, 1);
			}
		}
	}
	if (Flow)
	{
		if (Flow->GetState() == EIVFlowState::Tutorial) DrawTutorial(Flow);
		DrawBanner(Flow);
	}
}

// ------------------------------------------------------------------------------------------------------- glass infographics
void AIVHUD::DrawGlassInfographics(const iv::Fighter& FA, const iv::Fighter& FB, AIVMechPawn* Me, float Sx, float Fd)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	auto Bracket = [&](float X, float Y, float BW, float BH, const FLinearColor& C, bool bLeft)
	{
		const float K = 16.f * Sx;
		DrawLine(X, Y, X + K, Y, C, 2.f); DrawLine(X, Y, X, Y + K, C, 2.f);
		DrawLine(X + BW, Y + BH, X + BW - K, Y + BH, C, 2.f); DrawLine(X + BW, Y + BH, X + BW, Y + BH - K, C, 2.f);
		DrawLine(X + BW, Y, X + BW - K * 0.5f, Y, A(C, C.A * 0.5f), 1.f); DrawLine(X, Y + BH, X + K * 0.5f, Y + BH, A(C, C.A * 0.5f), 1.f);
		(void)bLeft;
	};
	auto ArmorPct = [](const iv::Fighter& F, iv::Zone Z) { return FMath::Clamp(F.body.layer(Z, iv::Layer::Armor) / iv::tune::kArmorMax[iv::Index(Z)], 0.f, 1.f); };
	struct FLbl { iv::Zone Z; float Dx, Dy; const TCHAR* N; };
	// ---- top left: the own body (seen from behind) with leader lines to the armour percentages
	{
		const float X0 = 22.f * Sx, Y0 = 18.f * Sx, PW = 300.f * Sx, PH = 196.f * Sx;
		Bracket(X0, Y0, PW, PH, A(kCyan, 0.8f * Fd), true);
		DrawRect(FLinearColor(0.f, 0.05f, 0.08f, 0.16f * Fd), X0, Y0, PW, PH);
		Text(TEXT("КОРПУС"), X0 + 8.f * Sx, Y0 + 4.f * Sx, A(kCyan, 0.95f * Fd), 0.8f * Sx, 0);
		const float Ov = FA.body.Integrity();
		Text(FString::Printf(TEXT("%d%%"), int32(Ov * 100.f)), X0 + PW - 10.f * Sx, Y0 + 2.f * Sx, A(Ov < 0.35f ? kRed : kWhite, Fd), 1.5f * Sx, 2, 2);
		DrawMechDiagram(FA, X0 + 96.f * Sx, Y0 + 26.f * Sx, 38.f * Sx, false);
		static const FLbl L[] = { { iv::Zone::Head, 0.f, 0.f, TEXT("ГЛВ") }, { iv::Zone::Torso, 0.f, 0.f, TEXT("КОР") }, { iv::Zone::Reactor, 0.f, 0.f, TEXT("РЕК") },
			{ iv::Zone::ArmL, 0.f, 0.f, TEXT("РУК Л") }, { iv::Zone::ArmR, 0.f, 0.f, TEXT("РУК П") }, { iv::Zone::LegL, 0.f, 0.f, TEXT("НОГ Л") }, { iv::Zone::LegR, 0.f, 0.f, TEXT("НОГ П") } };
		const float Lx = X0 + 176.f * Sx;
		float Ly = Y0 + 34.f * Sx;
		for (const FLbl& Lb : L)
		{
			const float P = ArmorPct(FA, Lb.Z);
			const iv::ZoneState St = FA.body.state(Lb.Z);
			const FLinearColor C = A(kZoneCol[int32(St)], Fd);
			Text(Lb.N, Lx, Ly - 1.f, A(kWhite, 0.8f * Fd), 0.66f * Sx, 0);
			DrawRect(A(FLinearColor::Black, 0.5f * Fd), Lx + 40.f * Sx, Ly + 2.f * Sx, 54.f * Sx, 7.f * Sx);
			DrawRect(C, Lx + 41.f * Sx, Ly + 3.f * Sx, 52.f * Sx * P, 5.f * Sx);
			Text(FString::Printf(TEXT("%d"), int32(P * 100.f)), Lx + 118.f * Sx, Ly - 1.f, A(kWhite, 0.9f * Fd), 0.66f * Sx, 0, 2);
			Ly += 20.f * Sx;
		}
		DrawStatuses(FA, X0 + 8.f * Sx, Y0 + PH - 20.f * Sx, false);
	}
	// ---- top right: the target
	{
		const float PW = 252.f * Sx, PH = 176.f * Sx, X0 = W - PW - 22.f * Sx, Y0 = 18.f * Sx;
		Bracket(X0, Y0, PW, PH, A(kRed, 0.85f * Fd), false);
		DrawRect(FLinearColor(0.08f, 0.f, 0.f, 0.16f * Fd), X0, Y0, PW, PH);
		Text(TEXT("ЦЕЛЬ"), X0 + 8.f * Sx, Y0 + 4.f * Sx, A(kRed, Fd), 0.8f * Sx, 0);
		const float Ov = FB.body.Integrity();
		Text(FString::Printf(TEXT("%d%%"), int32(Ov * 100.f)), X0 + PW - 10.f * Sx, Y0 + 2.f * Sx, A(kWhite, Fd), 1.5f * Sx, 2, 2);
		DrawMechDiagram(FB, X0 + 70.f * Sx, Y0 + 26.f * Sx, 34.f * Sx, true);
		const float St = FB.res.stability / 100.f;
		DrawRect(A(FLinearColor::Black, 0.55f * Fd), X0 + 124.f * Sx, Y0 + 40.f * Sx, 116.f * Sx, 7.f * Sx);
		DrawRect(A(kRed, 0.9f * Fd), X0 + 125.f * Sx, Y0 + 41.f * Sx, 114.f * Sx * FMath::Clamp(St, 0.f, 1.f), 5.f * Sx);
		Text(TEXT("УСТОЙЧИВОСТЬ"), X0 + 124.f * Sx, Y0 + 26.f * Sx, A(kWhite, 0.8f * Fd), 0.6f * Sx, 0);
		float Dist = 0.f;
		if (Me) for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It) if (*It != Me) { Dist = FVector::Dist2D(Me->GetActorLocation(), It->GetActorLocation()) / 100.f; break; }
		Text(FString::Printf(TEXT("%.0f М"), Dist), X0 + 124.f * Sx, Y0 + 62.f * Sx, A(kRed, Fd), 1.2f * Sx, 1, 0);
		Text(FB.posture == iv::Posture::Staggered ? TEXT("ОГЛУШЁН") : (FB.posture == iv::Posture::KnockedDown ? TEXT("СБИТ") : (FB.posture == iv::Posture::Airborne ? TEXT("В ПРЫЖКЕ") : (FB.posture == iv::Posture::Overloaded ? TEXT("БЕЗ ПИТАНИЯ") : TEXT("")))), X0 + 124.f * Sx, Y0 + 92.f * Sx, A(kYellow, Fd * (0.6f + 0.4f * Pulse(3.f))), 0.85f * Sx, 1, 0);
		DrawStatuses(FB, X0 + 8.f * Sx, Y0 + PH - 20.f * Sx, false);
	}
	// ---- bottom left: stability / heat / energy / ultimate
	{
		const float X0 = 26.f * Sx, Y0 = H - 118.f * Sx;
		DrawBars(FA, X0, Y0, 190.f * Sx);
	}
	// ---- bottom right: the weapon rings
	DrawAbilitiesGlass(nullptr, FA, Sx, Fd);
}

void AIVHUD::DrawAbilitiesGlass(AIVCombatDirector*, const iv::Fighter& F, float Sx, float Fd)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	AIVCombatDirector* Dir = nullptr;
	for (TActorIterator<AIVCombatDirector> It(GetWorld()); It; ++It) { Dir = *It; break; }
	AIVPlayerController* PC = Cast<AIVPlayerController>(GetOwningPlayerController());
	const iv::Side MySide = PC ? PC->MySide : iv::Side::A;
	struct Slot { const TCHAR* Key; const TCHAR* Name; iv::WeaponKind Kind; };
	const Slot Slots[3] = { { TEXT("1"), TEXT("РАКЕТЫ"), iv::WeaponKind::SuppressionRockets }, { TEXT("2"), TEXT("КОПЬЁ"), iv::WeaponKind::RailSpear }, { TEXT("3"), TEXT("ПЛАЗМА"), iv::WeaponKind::PlasmaCannon } };
	const float R = 30.f * Sx;
	const float Gap = 86.f * Sx;
	const float X1 = W - 40.f * Sx - R, Y1 = H - 62.f * Sx;
	for (int32 i = 0; i < 4; ++i)
	{
		const float Cx = X1 - (3 - i) * Gap, Cy = Y1;
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
			Ready = Dir ? Dir->GetScoopReady01(MySide) : 1.f;
			Key = TEXT("F"); Name = TEXT("ЗДАНИЕ");
			C = kGreen;
			if (HeliInReach(this)) { Name = TEXT("ВЕРТОЛЁТ"); C = kYellow; }
		}
		const bool bReady = Ready >= 0.999f;
		const int32 N = 36;
		for (int32 k = 0; k < N; ++k)
		{
			const float a0 = -1.5708f + 6.2831853f * k / N, a1 = -1.5708f + 6.2831853f * (k + 1) / N;
			const bool bOn = (float(k) + 0.5f) / N <= Ready;
			DrawLine(Cx + FMath::Cos(a0) * R, Cy + FMath::Sin(a0) * R, Cx + FMath::Cos(a1) * R, Cy + FMath::Sin(a1) * R, A(bSel ? kWhite : C, (bOn ? 0.95f : 0.22f) * Fd), bOn ? 4.f : 2.f);
		}
		Text(Key, Cx, Cy - 11.f * Sx, A(bReady ? kWhite : A(kWhite, 0.5f), Fd), 1.0f * Sx, 1, 1);
		Text(Name, Cx, Cy + R + 4.f * Sx, A(kWhite, (bReady ? 0.85f : 0.45f) * Fd), 0.6f * Sx, 0, 1);
		if (bReady && bSel) DrawLine(Cx - R - 4, Cy + R + 20.f * Sx, Cx + R + 4, Cy + R + 20.f * Sx, A(kWhite, 0.7f * Fd), 1.5f);
	}
}

// ------------------------------------------------------------------------------------------------------- v5 overlays
void AIVHUD::DrawSpecials(AIVCombatDirector* Dir, iv::Side MySide, AIVPlayerController* PC, AIVMechPawn* Me, float Sx)
{
	if (!Dir || !Dir->GetDuel()) return;
	const iv::Duel& Du = *Dir->GetDuel();
	const iv::Fighter& F = Du.fighter(MySide);
	const iv::Fighter& O = Du.fighter(iv::Other(MySide));
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float CX = W * 0.5f, CY = H * 0.5f;
	const float Pu = Pulse(4.f);

	// ---- lunge charge: a ring round the crosshair
	const iv::AnimState& An = Dir->GetAnim(MySide);
	if (An.lungeCharge01 > 0.01f)
	{
		const float R = 62.f * Sx;
		const bool bFull = An.lungeCharge01 >= 0.999f;
		const FLinearColor C = bFull ? A(kYellow, 0.7f + 0.3f * Pu) : A(kOrange, 0.9f);
		const int32 N = 48;
		for (int32 k = 0; k < N; ++k)
		{
			const float a0 = -1.5708f + 6.2831853f * k / N, a1 = -1.5708f + 6.2831853f * (k + 1) / N;
			const bool bOn = (float(k) + 0.5f) / N <= An.lungeCharge01;
			DrawLine(CX + FMath::Cos(a0) * R, CY + FMath::Sin(a0) * R, CX + FMath::Cos(a1) * R, CY + FMath::Sin(a1) * R, bOn ? C : A(kOrange, 0.15f), bOn ? 4.f : 1.5f);
		}
		Text(bFull ? TEXT("ОТПУСКАЙ!") : TEXT("РЫВОК"), CX, CY + R + 8.f * Sx, bFull ? A(kYellow, 0.6f + 0.4f * Pu) : A(kOrange, 0.9f), 0.9f * Sx, 1, 1);
	}
	if (F.posture == iv::Posture::Airborne)
	{
		Text(TEXT("ПОЛЁТ  ·  ЛКМ / RT — РУБКА СВЕРХУ"), CX, H * 0.74f, A(kCyan, 0.9f), 0.9f * Sx, 1, 1);
	}
	if (O.phase == iv::Phase::Strike && O.strike.kind == iv::StrikeKind::AirChop)
		Text(TEXT("РУБКА СВЕРХУ!  X / B — ПОДКАТ,  или БЛОК СВЕРХУ"), CX, H * 0.22f, A(kRed, 0.6f + 0.4f * Pu), 1.2f * Sx, 1, 1);
	if ((O.phase == iv::Phase::Windup || O.phase == iv::Phase::Strike) && O.strike.kind == iv::StrikeKind::Lunge)
		Text(O.phase == iv::Phase::Strike ? TEXT("РЫВОК!  ПРЫЖОК (ПРОБЕЛ / A) ИЛИ БЛОК") : TEXT("ВРАГ ЗАРЯЖАЕТ РЫВОК"), CX, H * 0.22f, A(kRed, 0.6f + 0.4f * Pu), 1.2f * Sx, 1, 1);

	// ---- the sword lock: a tug of war
	if (Du.lock().active)
	{
		const iv::LockState& L = Du.lock();
		const int32 Me_i = iv::Index(MySide);
		const float Mine = L.score[Me_i], Theirs = L.score[1 - Me_i];
		const float Tot = FMath::Max(Mine + Theirs, 1.f);
		const float BW = FMath::Min(W * 0.6f, 640.f * Sx), BH = 20.f * Sx, X0 = CX - BW * 0.5f, Y0 = H * 0.68f;
		DrawRect(A(FLinearColor::Black, 0.6f), X0 - 4, Y0 - 4, BW + 8, BH + 8);
		DrawRect(A(kCyan, 0.9f), X0, Y0, BW * Mine / Tot, BH);
		DrawRect(A(kRed, 0.9f), X0 + BW * Mine / Tot, Y0, BW * Theirs / Tot, BH);
		DrawLine(CX, Y0 - 10, CX, Y0 + BH + 10, A(kWhite, 0.8f), 2.f);
		const float Tp = 1.f - FMath::Clamp(float(L.ticks) / float(iv::tune::kLockTicks), 0.f, 1.f);
		DrawRect(A(kYellow, 0.7f), X0, Y0 + BH + 8.f, BW * Tp, 4.f);
		Text(TEXT("КЛИНЧ КЛИНКОВ — ЖМИ КАК МОЖНО БЫСТРЕЕ!"), CX, Y0 - 56.f * Sx, A(kYellow, 0.7f + 0.3f * Pu), 1.35f * Sx, 1, 1);
		Text(TEXT("ПРОБЕЛ  /  ЛКМ  /  Q E  ·  геймпад: A  X  B  LB  RB"), CX, Y0 - 24.f * Sx, A(kWhite, 0.8f), 0.8f * Sx, 0, 1);
		DrawRect(FLinearColor(1.f, 0.8f, 0.3f, 0.06f + 0.06f * Pu), 0, 0, W, H);
	}

	// ---- berserk
	const iv::BerserkState& B = Du.berserk();
	if (B.active)
	{
		const bool bAtk = B.who == MySide;
		const float Tleft = 1.f - FMath::Clamp(float(B.ticks) / float(iv::tune::kBerserkMaxTicks), 0.f, 1.f);
		const float BW = W * 0.34f;
		DrawRect(A(FLinearColor::Black, 0.55f), CX - BW * 0.5f - 2, 66.f * Sx - 2, BW + 4, 10.f * Sx + 4);
		DrawRect(A(kRed, 0.9f), CX - BW * 0.5f, 66.f * Sx, BW * Tleft, 10.f * Sx);
		Text(bAtk ? TEXT("БЕРСЕРК") : TEXT("ТЕБЯ СХВАТИЛИ"), CX, 38.f * Sx, A(kRed, 0.8f + 0.2f * Pu), 1.7f * Sx, 2, 1);
		for (int32 r = 0; r < iv::tune::kBerserkRounds; ++r)
			DrawRect(r < B.round ? A(bAtk ? kYellow : kGreen, 0.95f) : A(kWhite, 0.25f), CX - (iv::tune::kBerserkRounds * 22.f * Sx) * 0.5f + r * 22.f * Sx, 90.f * Sx, 16.f * Sx, 6.f * Sx);
		if (bAtk && B.stage == iv::BerserkStage::Prompt)
		{
			const float Perfect = float(iv::tune::kBerserkPerfectTick);
			const float R0 = 54.f * Sx;
			const float Rm = FMath::Lerp(R0 + 240.f * Sx, R0, FMath::Clamp(float(B.stageTicks) / Perfect, 0.f, 1.2f));
			const float Err = FMath::Abs(float(B.stageTicks) - Perfect) / float(iv::tune::kBerserkPressWindowTicks);
			const bool bIn = Err <= 1.f;
			const int32 N = 48;
			for (int32 k = 0; k < N; ++k)
			{
				const float a0 = 6.2831853f * k / N, a1 = 6.2831853f * (k + 1) / N;
				DrawLine(CX + FMath::Cos(a0) * R0, CY + FMath::Sin(a0) * R0, CX + FMath::Cos(a1) * R0, CY + FMath::Sin(a1) * R0, A(kWhite, 0.9f), 3.f);
				DrawLine(CX + FMath::Cos(a0) * Rm, CY + FMath::Sin(a0) * Rm, CX + FMath::Cos(a1) * Rm, CY + FMath::Sin(a1) * Rm, bIn ? A(kYellow, 1.f) : A(kRed, 0.9f), 4.f);
			}
			const FVector2D Ai = PC ? PC->GetBerserkAim() : FVector2D::ZeroVector;
			const FVector2D D = Ai.Size() > 0.22f ? Ai.GetSafeNormal() : FVector2D(1.f, 0.f);
			DrawLine(CX, CY, CX + D.X * 90.f * Sx, CY - D.Y * 90.f * Sx, A(kYellow, 0.9f), 4.f);
			DrawRect(A(kYellow, 0.9f), CX + D.X * 90.f * Sx - 6.f, CY - D.Y * 90.f * Sx - 6.f, 12.f, 12.f);
			Text(TEXT("МЫШЬ/СТИК — НАПРАВЛЕНИЕ  ·  ПРОБЕЛ / ЛКМ / E / A — УДАР В МОМЕНТ СОВПАДЕНИЯ"), CX, CY + 150.f * Sx, A(kWhite, 0.85f), 0.85f * Sx, 0, 1);
		}
		else if (!bAtk && B.stage == iv::BerserkStage::Swing)
		{
			static const TCHAR* Names[4] = { TEXT("СВЕРХУ"), TEXT("ВЛЕВО"), TEXT("ВПРАВО"), TEXT("СНИЗУ") };
			const float U = 1.f - FMath::Clamp(float(B.stageTicks) / float(iv::tune::kBerserkSwingTicks), 0.f, 1.f);
			const float R = 70.f * Sx + 120.f * Sx * U;
			for (int32 k = 0; k < 48; ++k)
			{
				const float a0 = 6.2831853f * k / 48, a1 = 6.2831853f * (k + 1) / 48;
				DrawLine(CX + FMath::Cos(a0) * R, CY + FMath::Sin(a0) * R, CX + FMath::Cos(a1) * R, CY + FMath::Sin(a1) * R, A(kRed, 0.9f), 4.f);
			}
			Text(TEXT("ПАРИРУЙ!"), CX, CY - 40.f * Sx, A(kRed, 0.7f + 0.3f * Pu), 2.4f * Sx, 2, 1);
			Text(FString::Printf(TEXT("УДАР %s — ПКМ / LT + ВЕДИ %s"), Names[iv::Index(B.side)], Names[iv::Index(B.side)]), CX, CY + 10.f * Sx, A(kWhite, 0.95f), 1.2f * Sx, 1, 1);
		}
		else if (!bAtk)
		{
			Text(TEXT("ЖДИ УДАРА — БЛОК ПО УКАЗАННОЙ СТОРОНЕ"), CX, CY + 130.f * Sx, A(kWhite, 0.7f), 0.9f * Sx, 0, 1);
		}
	}
	if (F.posture == iv::Posture::Overloaded)
	{
		const float U = FMath::Clamp(float(F.postureTicks) / float(iv::tune::kOverloadTicks), 0.f, 1.f);
		DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.35f), 0, 0, W, H);
		Text(TEXT("ПИТАНИЕ УТРАЧЕНО"), CX, CY - 40.f * Sx, A(kRed, 0.5f + 0.5f * Pu), 2.6f * Sx, 2, 1);
		DrawRect(A(FLinearColor::Black, 0.6f), CX - 200.f * Sx, CY + 20.f * Sx, 400.f * Sx, 10.f * Sx);
		DrawRect(A(kOrange, 0.9f), CX - 200.f * Sx, CY + 20.f * Sx, 400.f * Sx * U, 10.f * Sx);
	}
	else if (F.berserkCooldown > 0 && !B.active) { /* the cooldown is shown on the weapon rings only */ }
	// jetpack fuel hint
	if (F.jumpCooldown > 0 && F.posture == iv::Posture::Standing)
	{
		const float U = 1.f - FMath::Clamp(float(F.jumpCooldown) / float(iv::tune::kJumpCooldownTicks), 0.f, 1.f);
		DrawRect(A(FLinearColor::Black, 0.5f), 26.f * Sx, H - 134.f * Sx, 190.f * Sx, 5.f * Sx);
		DrawRect(A(kCyan, 0.8f), 26.f * Sx, H - 134.f * Sx, 190.f * Sx * U, 5.f * Sx);
		Text(TEXT("ДВИГАТЕЛИ ПРЫЖКА"), 26.f * Sx, H - 150.f * Sx, A(kCyan, 0.6f), 0.55f * Sx, 0);
	}
	(void)Me;
}

void AIVHUD::DrawBreakdown(AIVCombatDirector* Dir, iv::Side MySide, AIVPlayerController* PC, float Sx)
{
	if (!Dir || !Dir->GetDuel()) return;
	const iv::Fighter& F = Dir->GetDuel()->fighter(MySide);
	if (F.breakdown <= 0 || (PC && PC->IsRepairing())) return;
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float Pu = 0.5f + 0.5f * Pulse(2.5f);
	const float BW = 440.f * Sx, BH = 56.f * Sx, X0 = W * 0.5f - BW * 0.5f, Y0 = 52.f * Sx;
	DrawRect(FLinearColor(0.25f, 0.02f, 0.f, 0.35f + 0.25f * Pu), X0, Y0, BW, BH);
	DrawLine(X0, Y0, X0 + BW, Y0, A(kRed, 0.9f), 2.f);
	DrawLine(X0, Y0 + BH, X0 + BW, Y0 + BH, A(kRed, 0.9f), 2.f);
	Text(FString::Printf(TEXT("АВАРИЯ В ОТСЕКЕ ×%d — ТЕРЯЕШЬ БРОНЮ"), F.breakdown), X0 + BW * 0.5f, Y0 + 6.f * Sx, A(kRed, 0.6f + 0.4f * Pu), 1.0f * Sx, 1, 1);
	Text(TEXT("H  /  START — СПУСТИТЬСЯ ВГЛУБЬ МЕХА И ЧИНИТЬ"), X0 + BW * 0.5f, Y0 + 30.f * Sx, A(kWhite, 0.9f), 0.85f * Sx, 0, 1);
}

void AIVHUD::DrawRepair(AIVPlayerController* PC, const iv::Fighter& F, float Sx)
{
	const FIVRepairGame& G = PC->GetRepair();
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float CX = W * 0.5f, CY = H * 0.5f;
	const float Pu = Pulse(3.f);
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.55f), 0, 0, W, H);
	for (int32 i = 0; i < 14; ++i) DrawRect(FLinearColor(1.f, 0.1f, 0.05f, 0.03f * (14 - i) * (0.5f + 0.5f * Pu)), 0, i * 8.f, W, 8.f);
	Text(TEXT("НИЖНИЙ ОТСЕК  ·  РЕМОНТ"), CX, 70.f * Sx, A(kOrange, 1.f), 1.9f * Sx, 2, 1);
	Text(TEXT("УДЕРЖИВАЙ ПРОБЕЛ / ЛКМ / A — ЧИНИШЬ.  НА ДИСКЕ ЖМИ В ЗЕЛЁНУЮ ЗОНУ"), CX, 112.f * Sx, A(kWhite, 0.85f), 0.9f * Sx, 0, 1);
	// progress ring
	const float R = 150.f * Sx;
	const int32 N = 72;
	for (int32 k = 0; k < N; ++k)
	{
		const float a0 = -1.5708f + 6.2831853f * k / N, a1 = -1.5708f + 6.2831853f * (k + 1) / N;
		const bool bOn = (float(k) + 0.5f) / N <= G.Progress;
		DrawLine(CX + FMath::Cos(a0) * R, CY + FMath::Sin(a0) * R, CX + FMath::Cos(a1) * R, CY + FMath::Sin(a1) * R, bOn ? A(kGreen, 0.95f) : A(kWhite, 0.18f), bOn ? 7.f : 3.f);
	}
	Text(FString::Printf(TEXT("%d%%"), int32(G.Progress * 100.f)), CX, CY - 28.f * Sx, A(kWhite, 1.f), 2.8f * Sx, 2, 1);
	Text(G.bWorking ? TEXT("РАБОТА...") : TEXT("ДЕРЖИ КНОПКУ"), CX, CY + 36.f * Sx, A(G.bWorking ? kGreen : kYellow, 0.9f), 1.0f * Sx, 1, 1);
	// skill check disc
	if (G.bCheck)
	{
		const float Rc = 70.f * Sx;
		for (int32 k = 0; k < 72; ++k)
		{
			const float d0 = 5.f * k, d1 = 5.f * (k + 1);
			const float a0 = FMath::DegreesToRadians(d0 - 90.f), a1 = FMath::DegreesToRadians(d1 - 90.f);
			const float Mid = (d0 + d1) * 0.5f;
			float Rel = FMath::Fmod(Mid - G.ZoneStart + 360.f, 360.f);
			const bool bZone = Rel < G.ZoneLen;
			const bool bGreat = Rel < G.GreatLen;
			DrawLine(CX + FMath::Cos(a0) * Rc, CY + 150.f * Sx * 0 + FMath::Sin(a0) * Rc, CX + FMath::Cos(a1) * Rc, CY + FMath::Sin(a1) * Rc, bGreat ? A(kWhite, 1.f) : (bZone ? A(kGreen, 0.95f) : A(kWhite, 0.28f)), bZone ? 9.f : 4.f);
		}
		const float Na = FMath::DegreesToRadians(G.Needle - 90.f);
		DrawLine(CX, CY, CX + FMath::Cos(Na) * Rc, CY + FMath::Sin(Na) * Rc, A(kRed, 1.f), 4.f);
	}
	const float Tp = 1.f - FMath::Clamp(G.Time / G.TimeLimit, 0.f, 1.f);
	DrawRect(A(FLinearColor::Black, 0.6f), CX - 220.f * Sx, CY + 200.f * Sx, 440.f * Sx, 8.f * Sx);
	DrawRect(A(Tp < 0.25f ? kRed : kYellow, 0.9f), CX - 220.f * Sx, CY + 200.f * Sx, 440.f * Sx * Tp, 8.f * Sx);
	Text(TEXT("ESC / B — ВЕРНУТЬСЯ В КАБИНУ"), CX, CY + 220.f * Sx, A(kWhite, 0.6f), 0.7f * Sx, 0, 1);
	if (G.FlashBad > 0.f) DrawRect(FLinearColor(1.f, 0.05f, 0.02f, 0.4f * G.FlashBad), 0, 0, W, H);
	if (G.FlashGood > 0.f) DrawRect(FLinearColor(0.2f, 1.f, 0.4f, 0.25f * G.FlashGood), 0, 0, W, H);
	(void)F;
}


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
			Text(R >= 0.999f ? TEXT("J — ВЫЙТИ ИЗ КАБИНЫ (АБОРДАЖ)") : FString::Printf(TEXT("АБОРДАЖ: ПЕРЕЗАРЯДКА %d%%"), int32(R * 100.f)), CX, H - 16.f * Sx, A(R >= 0.999f ? kGreen : kWhite, R >= 0.999f ? 0.55f + 0.3f * Pulse(1.5f) : 0.35f), 0.7f * Sx, 0, 1);
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
	return true;
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

// ------------------------------------------------------------------------------------------------------- menu
void AIVHUD::DrawMenu(AIVGameFlow* Flow)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float Sx = FMath::Clamp(W / 1600.f, 0.6f, 1.6f);
	const float Tm = GetWorld()->GetTimeSeconds();
	// dark gradient on the left so the text reads, the duel behind stays visible on the right
	for (int32 i = 0; i < 40; ++i)
	{
		const float T = float(i) / 40.f;
		const float X0 = FMath::FloorToFloat(W * 0.62f * i / 40.f), X1 = FMath::FloorToFloat(W * 0.62f * (i + 1) / 40.f);
		DrawRect(FLinearColor(0.004f, 0.01f, 0.03f, 0.86f * FMath::Pow(1.f - T, 2.2f)), X0, 0, X1 - X0, H);
	}
	// vignette bands top / bottom
	for (int32 i = 0; i < 10; ++i)
	{
		const float K = 0.5f * FMath::Pow(1.f - float(i) / 10.f, 2.f);
		const float Y0 = FMath::FloorToFloat(H * 0.12f * i / 10.f), Y1 = FMath::FloorToFloat(H * 0.12f * (i + 1) / 10.f);
		DrawRect(FLinearColor(0.f, 0.f, 0.02f, K), 0, Y0, W, Y1 - Y0);
		DrawRect(FLinearColor(0.f, 0.f, 0.02f, K), 0, H - Y1, W, Y1 - Y0);
	}
	// slow scanline sweep
	{
		const float Sy = FMath::Frac(Tm * 0.07f) * H;
		DrawRect(A(kCyan, 0.035f), 0, Sy, W * 0.7f, 70.f * Sx);
	}
	const float X = W * 0.065f;
	float Y = H * 0.12f;
	// corner brackets
	{
		const float M = 26.f * Sx, L = 46.f * Sx;
		const FLinearColor Cc = A(kCyan, 0.8f);
		DrawLine(M, M, M + L, M, Cc, 2.f); DrawLine(M, M, M, M + L, Cc, 2.f);
		DrawLine(W - M, M, W - M - L, M, Cc, 2.f); DrawLine(W - M, M, W - M, M + L, Cc, 2.f);
		DrawLine(M, H - M, M + L, H - M, Cc, 2.f); DrawLine(M, H - M, M, H - M - L, Cc, 2.f);
		DrawLine(W - M, H - M, W - M - L, H - M, Cc, 2.f); DrawLine(W - M, H - M, W - M, H - M - L, Cc, 2.f);
	}
	// header strip
	Text(TEXT("МЕХ-ДУЭЛЬ  //  ТОКИО-ЗАЛИВ  //  КАНАЛ 07"), X, Y - 40.f * Sx, A(kCyan, 0.75f), 0.85f * Sx, 1);
	Text(FString::Printf(TEXT("%02d:%02d"), int32(Tm / 60.f) % 60, int32(Tm) % 60), W - X, Y - 40.f * Sx, A(kCyan, 0.6f), 0.85f * Sx, 1, 2);
	// title: chromatic split + glow
	const FString Title = TEXT("IMPACT VECTOR");
	const float Gl = 0.5f + 0.5f * FMath::Sin(Tm * 1.7f);
	for (int32 k = 0; k < 7; ++k)
	{
		const float A0 = 0.05f * (7 - k) * (0.7f + 0.3f * Gl);
		Text(Title, X + k * 0.9f, Y + k * 0.9f, A(kCyan, A0), 4.6f * Sx, 2);
		Text(Title, X - k * 0.9f, Y - k * 0.9f, A(kCyan, A0), 4.6f * Sx, 2);
	}
	const float Gj = (FMath::Frac(Tm * 0.37f) < 0.03f) ? 6.f * Sx : 0.f;   // rare glitch
	Text(Title, X - 3.f * Sx - Gj, Y, A(kRed, 0.55f), 4.6f * Sx, 2);
	Text(Title, X + 3.f * Sx + Gj, Y, A(FLinearColor(0.1f, 0.5f, 1.f), 0.55f), 4.6f * Sx, 2);
	Text(Title, X, Y, kWhite, 4.6f * Sx, 2);
	// accent slash under the title
	const float Ly = Y + 116.f * Sx;
	DrawLine(X, Ly, X + 700.f * Sx, Ly, A(kCyan, 0.9f), 2.f);
	DrawLine(X + 700.f * Sx, Ly, X + 740.f * Sx, Ly - 18.f * Sx, A(kCyan, 0.9f), 2.f);
	DrawRect(A(kOrange, 0.95f), X, Ly + 6.f * Sx, 120.f * Sx, 4.f * Sx);
	Text(TEXT("ДУЭЛЬ ГИГАНТСКИХ МЕХОВ  ·  ТУМАН  ·  ДОЖДЬ  ·  НЕОН"), X, Ly + 18.f * Sx, A(kCyan, 0.9f), 1.05f * Sx, 1);

	// items
	const TArray<FString> Items = Flow->GetMenuItems();
	const int32 Sel = Flow->GetMenuIndex();
	const float Y0 = H * 0.43f, Step = 62.f * Sx, IW = 660.f * Sx, IH = 50.f * Sx;
	static float SelY = 0.f;
	SelY = FMath::FInterpTo(SelY, Sel * Step, GetWorld()->GetDeltaSeconds(), 14.f);
	{
		const float By = Y0 + SelY;
		for (int32 i = 0; i < 18; ++i)   // soft horizontal fade of the highlight
		{
			const float T = float(i) / 18.f;
			const float Hx0 = FMath::FloorToFloat(X - 18.f * Sx + IW * i / 18.f), Hx1 = FMath::FloorToFloat(X - 18.f * Sx + IW * (i + 1) / 18.f);
			DrawRect(A(kCyan, (0.2f + 0.05f * Pulse(2.f)) * (1.f - T * T)), Hx0, By - 4.f * Sx, Hx1 - Hx0, IH);
		}
		DrawRect(kCyan, X - 18.f * Sx, By - 4.f * Sx, 5.f * Sx, IH);
		DrawRect(A(kWhite, 0.5f), X - 18.f * Sx, By - 4.f * Sx, IW * 0.5f, 1.5f);
	}
	for (int32 i = 0; i < Items.Num(); ++i)
	{
		const bool bSel = i == Sel;
		const float Yy = Y0 + i * Step;
		Text(FString::Printf(TEXT("%02d"), i + 1), X + 2.f * Sx, Yy + 8.f * Sx, A(bSel ? kCyan : kCyanDim, bSel ? 1.f : 0.7f), 1.0f * Sx, 1);
		Text(Items[i], X + 56.f * Sx, Yy, bSel ? kWhite : A(kWhite, 0.55f), 1.85f * Sx, 2);
		const FString V = Flow->GetMenuValue(i);
		if (!V.IsEmpty())
		{
			const float Vx = X + IW - 40.f * Sx;
			float Vw = 0.f, Vh = 0.f;
			GetTextSize(V, Vw, Vh, GEngine->GetMediumFont(), 1.05f * Sx);
			Text(V, Vx, Yy + 8.f * Sx, bSel ? kOrange : A(kOrange, 0.5f), 1.05f * Sx, 1, 2);
			if (bSel && (i == 0 || i == 3))
			{
				Text(TEXT("<"), Vx - Vw - 18.f * Sx, Yy + 6.f * Sx, A(kCyan, 0.6f + 0.4f * Pulse(3.f)), 1.2f * Sx, 2, 2);
				Text(TEXT(">"), Vx + 14.f * Sx, Yy + 6.f * Sx, A(kCyan, 0.6f + 0.4f * Pulse(3.f)), 1.2f * Sx, 2, 0);
			}
		}
	}

	// description panel (bottom right)
	{
		const float PW = 470.f * Sx, PH = 200.f * Sx, PX = W - PW - 60.f * Sx, PY = H * 0.62f;
		Panel(PX, PY, PW, PH, FLinearColor(0.f, 0.03f, 0.06f, 0.72f), A(kCyan, 0.7f));
		DrawRect(A(kCyan, 0.16f), PX, PY, PW, 30.f * Sx);
		Text(FString::Printf(TEXT("РЕЖИМ  ·  %02d / %02d"), Sel + 1, Items.Num()), PX + 14.f * Sx, PY + 6.f * Sx, A(kCyan, 1.f), 0.9f * Sx, 1);
		Text(Items.IsValidIndex(Sel) ? Items[Sel] : FString(), PX + 14.f * Sx, PY + 44.f * Sx, kWhite, 1.4f * Sx, 2);
		Wrap(Flow->GetMenuHint(Sel), PX + 14.f * Sx, PY + 90.f * Sx, PW - 28.f * Sx, A(kWhite, 0.85f), 0.82f * Sx, 24.f * Sx);
	}

	// key chips
	{
		struct FKey { const TCHAR* K; const TCHAR* L; };
		const FKey Keys[4] = { { TEXT("W / S"), TEXT("ВЫБОР") }, { TEXT("A / D"), TEXT("ИЗМЕНИТЬ") }, { TEXT("ENTER"), TEXT("ЗАПУСК") }, { TEXT("ESC"), TEXT("МЕНЮ ИЗ БОЯ") } };
		float Kx = X;
		const float Ky = H - 70.f * Sx;
		for (const FKey& Kk : Keys)
		{
			const float Kw = (FString(Kk.K).Len() * 13.f + 22.f) * Sx;
			Panel(Kx, Ky, Kw, 28.f * Sx, FLinearColor(0.f, 0.05f, 0.08f, 0.8f), A(kCyan, 0.8f));
			Text(Kk.K, Kx + Kw * 0.5f, Ky + 5.f * Sx, kWhite, 0.8f * Sx, 1, 1);
			Text(Kk.L, Kx + Kw + 10.f * Sx, Ky + 5.f * Sx, A(kWhite, 0.65f), 0.8f * Sx, 1);
			Kx += Kw + 16.f * Sx + FString(Kk.L).Len() * 11.f * Sx;
		}
		Text(TEXT("клавиатура + мышь  ·  геймпад  ·  вибрация"), X, Ky + 34.f * Sx, A(kCyan, 0.5f), 0.7f * Sx, 1);
	}
}

void AIVHUD::DrawSettings(AIVGameFlow* Flow)
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

void AIVHUD::DrawParryWindow(AIVCombatDirector* Dir, iv::Side MySide, float Sx)
{
	if (!Dir || !Dir->GetDuel() || Dir->IsMatchOver()) return;
	const iv::AnimState& O = Dir->GetAnim(iv::Other(MySide));
	if ((O.phase != iv::Phase::Windup && O.phase != iv::Phase::Strike) || O.contactTicks < 0) return;
	if (O.kind != iv::StrikeKind::Heavy && O.kind != iv::StrikeKind::Quick) return;
	const float CX = Canvas->ClipX * 0.5f, CY = Canvas->ClipY * 0.5f;
	const int32 Win = iv::tune::kParryWindowTicks;
	const int32 Ct = O.contactTicks;
	const float R0 = 62.f * Sx, R1 = 150.f * Sx;
	const float U = FMath::Clamp(float(Ct) / 50.f, 0.f, 1.f);
	const float R = FMath::Lerp(R0, R1, U);
	const bool bIn = Ct <= Win;
	const FLinearColor C = bIn ? kGreen : kYellow;
	// target ring (where the window is) and the closing ring
	for (int32 k = 0; k < 48; ++k)
	{
		const float a0 = 6.2831853f * k / 48.f, a1 = 6.2831853f * (k + 1) / 48.f;
		DrawLine(CX + FMath::Cos(a0) * R0, CY + FMath::Sin(a0) * R0, CX + FMath::Cos(a1) * R0, CY + FMath::Sin(a1) * R0, A(kGreen, 0.55f), 3.f);
		DrawLine(CX + FMath::Cos(a0) * R, CY + FMath::Sin(a0) * R, CX + FMath::Cos(a1) * R, CY + FMath::Sin(a1) * R, A(C, bIn ? 0.95f : 0.7f), bIn ? 6.f : 3.f);
	}
	// where to draw the block: an arrow in the swing's direction
	FVector2D D(0, 0);
	switch (O.side) { case iv::SwingSide::Up: D = FVector2D(0, -1); break; case iv::SwingSide::Down: D = FVector2D(0, 1); break; case iv::SwingSide::Left: D = FVector2D(-1, 0); break; default: D = FVector2D(1, 0); break; }
	const FVector2D Pt(CX + D.X * R0 * 1.0f, CY + D.Y * R0 * 1.0f), Tp(CX + D.X * (R0 + 56.f * Sx), CY + D.Y * (R0 + 56.f * Sx));
	DrawLine(Pt.X, Pt.Y, Tp.X, Tp.Y, A(kGreen, 0.95f), 6.f);
	const FVector2D Nn(-D.Y, D.X);
	DrawLine(Tp.X, Tp.Y, Tp.X - D.X * 18.f + Nn.X * 12.f, Tp.Y - D.Y * 18.f + Nn.Y * 12.f, A(kGreen, 0.95f), 5.f);
	DrawLine(Tp.X, Tp.Y, Tp.X - D.X * 18.f - Nn.X * 12.f, Tp.Y - D.Y * 18.f - Nn.Y * 12.f, A(kGreen, 0.95f), 5.f);
	static const TCHAR* Names[4] = { TEXT("ВЕРХ"), TEXT("ВЛЕВО"), TEXT("ВПРАВО"), TEXT("НИЗ") };
	const FString Msg = bIn ? TEXT("БЛОК СЕЙЧАС!") : FString::Printf(TEXT("УДАР %s — ПКМ + ЧЕРТИ %s"), Names[iv::Index(O.side)], Names[iv::Index(O.side)]);
	Text(Msg, CX, CY + R1 + 22.f * Sx, A(C, 0.95f), (bIn ? 1.3f : 0.85f) * Sx, 2, 1);
	Text(FString::Printf(TEXT("%d мс"), int32(Ct * 1000 / iv::kTickHz)), CX, CY - 10.f, A(C, 0.9f), 0.9f * Sx, 1, 1);
}

void AIVHUD::DrawJoin(AIVGameFlow* Flow)
{
	const float W = Canvas->ClipX, H = Canvas->ClipY;
	const float Sx = FMath::Clamp(W / 1600.f, 0.6f, 1.4f);
	DrawRect(FLinearColor(0.f, 0.01f, 0.03f, 0.82f), 0, 0, W, H);
	Text(TEXT("СПЛИТ-СКРИН"), W * 0.5f, H * 0.12f, kWhite, 3.4f * Sx, 2, 1);
	Text(TEXT("ДВА ПИЛОТА  ·  ДВА ГЕЙМПАДА  ·  ЭКРАН РАЗДЕЛЁН ПО ВЕРТИКАЛИ"), W * 0.5f, H * 0.12f + 78.f * Sx, A(kCyan, 0.9f), 1.0f * Sx, 1, 1);
	for (int32 i = 0; i < 2; ++i)
	{
		const bool bReady = Flow->JoinReady(i);
		const FLinearColor C = i == 0 ? kCyan : kRed;
		const float PW = 520.f * Sx, PH = 300.f * Sx, X = W * 0.5f + (i == 0 ? -PW - 30.f * Sx : 30.f * Sx), Y = H * 0.34f;
		Panel(X, Y, PW, PH, FLinearColor(0.f, 0.04f, 0.06f, 0.6f), A(bReady ? kGreen : C, 0.9f));
		Text(i == 0 ? TEXT("ИГРОК 1") : TEXT("ИГРОК 2"), X + PW * 0.5f, Y + 24.f * Sx, A(C, 1.f), 2.2f * Sx, 2, 1);
		Text(i == 0 ? TEXT("Левая половина экрана") : TEXT("Правая половина экрана"), X + PW * 0.5f, Y + 92.f * Sx, A(kWhite, 0.7f), 0.9f * Sx, 1, 1);
		if (bReady) Text(TEXT("ГОТОВ"), X + PW * 0.5f, Y + 160.f * Sx, A(kGreen, 1.f), 3.0f * Sx, 2, 1);
		else
		{
			Text(i == 0 ? TEXT("Нажми  A  на первом геймпаде") : TEXT("Нажми  A  на ВТОРОМ геймпаде"), X + PW * 0.5f, Y + 160.f * Sx, A(kWhite, 0.55f + 0.45f * Pulse(2.f)), 1.1f * Sx, 1, 1);
			if (i == 0) Text(TEXT("(или Enter / Пробел)"), X + PW * 0.5f, Y + 196.f * Sx, A(kWhite, 0.5f), 0.8f * Sx, 0, 1);
		}
	}
	Text(TEXT("Esc — назад в меню"), W * 0.5f, H * 0.88f, A(kWhite, 0.55f), 0.9f * Sx, 0, 1);
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
	// the stroke itself: a smoothed (Catmull-Rom) ribbon with a wide soft glow, a bright core and a hot tip; red-orange for a strike, green-cyan for a block
	{
		const bool bGd = PC->IsTrailGuard();
		const FLinearColor Glow = bGd ? FLinearColor(0.1f, 0.9f, 0.55f) : FLinearColor(1.f, 0.35f, 0.08f);
		const FLinearColor Core = bGd ? FLinearColor(0.75f, 1.f, 0.9f) : FLinearColor(1.f, 0.9f, 0.6f);
		TArray<FVector2D> Pts;
		const int32 N = T.Num();
		for (int32 i = 0; i + 1 < N; ++i)
		{
			const FVector2D P0 = T[FMath::Max(i - 1, 0)], P1 = T[i], P2 = T[i + 1], P3 = T[FMath::Min(i + 2, N - 1)];
			for (int32 k = 0; k < 4; ++k)
			{
				const float u = k / 4.f, u2 = u * u, u3 = u2 * u;
				Pts.Add(0.5f * ((2.f * P1) + (-P0 + P2) * u + (2.f * P0 - 5.f * P1 + 4.f * P2 - P3) * u2 + (-P0 + 3.f * P1 - 3.f * P2 + P3) * u3));
			}
		}
		Pts.Add(T.Last());
		const int32 M = Pts.Num();
		for (int32 i = 1; i < M; ++i)
		{
			const FVector2D a = P(Pts[i - 1]), b = P(Pts[i]);
			const float K = float(i) / float(M);
			const float Wd = 3.f + 7.f * K * K;
			DrawLine(a.X, a.Y, b.X, b.Y, A(Glow, 0.10f * Fade), Wd * 2.8f);
			DrawLine(a.X, a.Y, b.X, b.Y, A(Glow, 0.35f * Fade), Wd * 1.35f);
			DrawLine(a.X, a.Y, b.X, b.Y, A(Core, (0.45f + 0.55f * K) * Fade), Wd * 0.45f);
		}
		const FVector2D Tip = P(T.Last());
		for (int32 g = 3; g >= 1; --g) DrawRect(A(Glow, 0.16f * Fade * (4 - g)), Tip.X - 7.f * g, Tip.Y - 7.f * g, 14.f * g, 14.f * g);
		DrawRect(A(Core, Fade), Tip.X - 5.f, Tip.Y - 5.f, 10.f, 10.f);
		// arrow head along the last segment
		if (M > 3)
		{
			const FVector2D d = (P(Pts[M - 1]) - P(Pts[M - 4])).GetSafeNormal();
			const FVector2D n(-d.Y, d.X);
			DrawLine(Tip.X, Tip.Y, Tip.X - d.X * 22.f + n.X * 11.f, Tip.Y - d.Y * 22.f + n.Y * 11.f, A(Core, Fade), 3.f);
			DrawLine(Tip.X, Tip.Y, Tip.X - d.X * 22.f - n.X * 11.f, Tip.Y - d.Y * 22.f - n.Y * 11.f, A(Core, Fade), 3.f);
		}
		Text(bGd ? TEXT("БЛОК") : TEXT("УДАР"), CX, CY + R + 16.f, A(Glow, 0.9f * Fade), 0.8f, 1, 1);
	}
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
			if (HeliInReach(this)) { Name = TEXT("ВЕРТОЛЁТ"); C = kYellow; }
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

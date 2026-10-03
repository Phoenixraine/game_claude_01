#include "IVHUD.h"
#include "IVMechPawn.h"
#include "IVCombat.h"
#include "IVPlayerController.h"
#include "Engine/Engine.h"
#include "Engine/Canvas.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"

void AIVHUD::DrawHUD()
{
	Super::DrawHUD();
	static IConsoleVariable* Cam = IConsoleManager::Get().FindConsoleVariable(TEXT("iv.Cam"));
	if (!Canvas || (Cam && Cam->GetInt() != 0)) return;

	AIVMechPawn* Me = Cast<AIVMechPawn>(GetOwningPawn());
	const float CX = Canvas->ClipX * 0.5f, CY = Canvas->ClipY * 0.5f;
	const FLinearColor Blue(0.55f, 0.8f, 1.f, 0.55f);

	DrawLine(CX - 14, CY, CX - 5, CY, Blue, 1.5f);
	DrawLine(CX + 5, CY, CX + 14, CY, Blue, 1.5f);
	DrawLine(CX, CY - 14, CX, CY - 5, Blue, 1.5f);
	DrawLine(CX, CY + 5, CX, CY + 14, Blue, 1.5f);

	// ---- combat read-out (temporary) ----
	AIVCombatDirector* Dir = nullptr;
	for (TActorIterator<AIVCombatDirector> It(GetWorld()); It; ++It) { Dir = *It; break; }
	if (Dir && Dir->GetDuel())
	{
		const iv::Duel& Du = *Dir->GetDuel();
		const iv::AnimState& A = Dir->GetAnim(iv::Side::A);
		const iv::AnimState& B = Dir->GetAnim(iv::Side::B);
		auto Bar = [&](float X, float Y, float W, float V, const FLinearColor& C) {
			DrawRect(FLinearColor(0, 0, 0, 0.45f), X, Y, W, 10.f);
			DrawRect(C, X + 1, Y + 1, (W - 2) * FMath::Clamp(V, 0.f, 1.f), 8.f);
		};
		Bar(40.f, Canvas->ClipY - 70.f, 220.f, A.stability01, FLinearColor(0.4f, 0.8f, 1.f, 0.9f));
		Bar(40.f, Canvas->ClipY - 52.f, 220.f, A.heat01, FLinearColor(1.f, 0.55f, 0.2f, 0.9f));
		Bar(40.f, Canvas->ClipY - 34.f, 220.f, A.ultimate01, FLinearColor(1.f, 0.9f, 0.3f, 0.9f));
		Bar(Canvas->ClipX - 260.f, 40.f, 220.f, B.stability01, FLinearColor(1.f, 0.4f, 0.3f, 0.9f));
		Bar(Canvas->ClipX - 260.f, 58.f, 220.f, B.heat01, FLinearColor(1.f, 0.55f, 0.2f, 0.9f));
		// zone states of both fighters (0 intact .. 6 severed): dots
		const FLinearColor Cols[] = { FLinearColor(0.7f, 0.9f, 1.f), FLinearColor(0.9f, 0.9f, 0.6f), FLinearColor(1.f, 0.85f, 0.3f), FLinearColor(1.f, 0.55f, 0.15f), FLinearColor(1.f, 0.2f, 0.1f), FLinearColor(0.35f, 0.05f, 0.05f), FLinearColor(0.f, 0.f, 0.f) };
		for (int32 s = 0; s < 2; ++s)
		{
			for (int32 z = 0; z < iv::kZoneCount; ++z)
			{
				const iv::ZoneState St = Du.fighter(s == 0 ? iv::Side::A : iv::Side::B).body.state(static_cast<iv::Zone>(z));
				const float X = (s == 0 ? 40.f : Canvas->ClipX - 260.f) + z * 24.f;
				const float Y = (s == 0 ? Canvas->ClipY - 100.f : 80.f);
				DrawRect(Cols[static_cast<int32>(St)], X, Y, 18.f, 14.f);
			}
		}
		FString Msg = FString::Printf(TEXT("phase %d  dist %.0f  %s%s"), int32(A.phase), Du.distance(), Dir->IsCinematic() ? TEXT("[CINEMATIC] ") : TEXT(""), A.guardRaised ? TEXT("[GUARD] ") : TEXT(""));
		DrawText(Msg, FLinearColor(0.8f, 0.9f, 1.f, 0.8f), 40.f, Canvas->ClipY - 130.f, nullptr, 1.1f);
		if (Dir->IsMatchOver())
		{
			DrawText(Dir->GetEndText(), FLinearColor(1.f, 0.9f, 0.6f, 1.f), Canvas->ClipX * 0.5f - 120.f, Canvas->ClipY * 0.35f, nullptr, 4.f);
			DrawText(TEXT("Enter - restart"), FLinearColor(0.8f, 0.9f, 1.f, 0.9f), Canvas->ClipX * 0.5f - 80.f, Canvas->ClipY * 0.35f + 80.f, nullptr, 1.5f);
		}
	}

	// target bracket around the nearest other mech
	if (!Me) return;
	for (TActorIterator<AIVMechPawn> It(GetWorld()); It; ++It)
	{
		if (*It == Me) continue;
		const FVector C = It->GetActorLocation() + FVector(0, 0, 400);
		const FVector P = Project(C);
		if (P.Z <= 0.f) continue;
		const float Dist = FVector::Dist(C, Me->GetEyeLocation());
		const float Half = FMath::Clamp(5200.f / Dist * Canvas->ClipY * 0.75f, 30.f, 400.f);
		const FLinearColor Col(1.f, 0.35f, 0.25f, 0.8f);
		const float L = Half * 0.3f;
		const float X0 = P.X - Half * 0.6f, X1 = P.X + Half * 0.6f, Y0 = P.Y - Half, Y1 = P.Y + Half;
		DrawLine(X0, Y0, X0 + L, Y0, Col, 2.f); DrawLine(X0, Y0, X0, Y0 + L, Col, 2.f);
		DrawLine(X1, Y0, X1 - L, Y0, Col, 2.f); DrawLine(X1, Y0, X1, Y0 + L, Col, 2.f);
		DrawLine(X0, Y1, X0 + L, Y1, Col, 2.f); DrawLine(X0, Y1, X0, Y1 - L, Col, 2.f);
		DrawLine(X1, Y1, X1 - L, Y1, Col, 2.f); DrawLine(X1, Y1, X1, Y1 - L, Col, 2.f);
	}
}

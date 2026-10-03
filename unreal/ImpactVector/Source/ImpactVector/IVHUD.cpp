#include "IVHUD.h"
#include "IVMechPawn.h"
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

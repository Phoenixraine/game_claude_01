#pragma once

#include "CoreMinimal.h"
#include "iv/HackGame.h"
#include "GameFramework/HUD.h"
#include "iv/Types.h"
#include "IVHUD.generated.h"

class AIVGameFlow;
class AIVCombatDirector;
class AIVMechPawn;
class AIVPlayerController;
namespace iv { class Fighter; }

/** Canvas HUD: title menu, tutorial prompts, sword-vector trail, mech diagrams, ability slots, statuses and banners. */
UCLASS()
class IMPACTVECTOR_API AIVHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

private:
	void DrawGlassInfographics(const iv::Fighter& FA, const iv::Fighter& FB, AIVMechPawn* Me, float Sx, float Fd);
	void DrawAbilitiesGlass(AIVCombatDirector* Dir, const iv::Fighter& F, float Sx, float Fd);
	void DrawSpecials(AIVCombatDirector* Dir, iv::Side MySide, AIVPlayerController* PC, AIVMechPawn* Me, float Sx);
	void DrawBreakdown(AIVCombatDirector* Dir, iv::Side MySide, AIVPlayerController* PC, float Sx);
	void DrawRepair(AIVPlayerController* PC, const iv::Fighter& F, float Sx);
	bool DrawBoarding(class AIVCombatDirector* Dir, iv::Side MySide, float Sx);
	void DrawBoarded(class AIVCombatDirector* Dir, iv::Side MySide, class AIVPlayerController* PC, float Sx);
	void DrawUltGauge(class AIVCombatDirector* Dir, iv::Side MySide, float Sx);
	void DrawHack(const iv::HackGame& G, float Sx);
	void DrawMenu(AIVGameFlow* Flow);
	void DrawJoin(AIVGameFlow* Flow);
	void DrawSettings(AIVGameFlow* Flow);
	void DrawParryWindow(class AIVCombatDirector* Dir, iv::Side MySide, float Sx);
	void DrawTutorial(AIVGameFlow* Flow);
	void DrawTrail(AIVPlayerController* PC);
	void DrawMechDiagram(const iv::Fighter& F, float X, float Y, float S, bool bFront);
	void DrawBars(const iv::Fighter& F, float X, float Y, float W);
	void DrawAbilities(AIVCombatDirector* Dir, const iv::Fighter& F);
	void DrawStatuses(const iv::Fighter& F, float X, float Y, bool bRight);
	void DrawBanner(AIVGameFlow* Flow);
	void DrawLockBracket(AIVMechPawn* Me);
	void Text(const FString& S, float X, float Y, const FLinearColor& C, float Scale, int32 Font = 1, int32 Align = 0);
	void Panel(float X, float Y, float W, float H, const FLinearColor& Fill, const FLinearColor& Edge);
	void Wrap(const FString& S, float X, float Y, float MaxW, const FLinearColor& C, float Scale, float LineH);
	float Pulse(float Hz) const;
};

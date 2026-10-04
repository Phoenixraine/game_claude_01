"""HUD (glass infographics, v5 overlays) + controller (repair mini-game, helpers)."""
S = r"F:\IVUnreal\Source\ImpactVector" + "\\"


def patch(path, edits):
    s = open(path, encoding="utf-8").read()
    for a, b in edits:
        assert a in s, (path, a[:90])
        s = s.replace(a, b, 1)
    open(path, "w", encoding="utf-8").write(s)


# ---------------- HUD
patch(S + "IVHUD.h", [
    ("	void DrawMenu(AIVGameFlow* Flow);",
     """	void DrawGlassInfographics(const iv::Fighter& FA, const iv::Fighter& FB, AIVMechPawn* Me, float Sx, float Fd);
	void DrawAbilitiesGlass(AIVCombatDirector* Dir, const iv::Fighter& F, float Sx, float Fd);
	void DrawSpecials(AIVCombatDirector* Dir, iv::Side MySide, AIVPlayerController* PC, AIVMechPawn* Me, float Sx);
	void DrawBreakdown(AIVCombatDirector* Dir, iv::Side MySide, AIVPlayerController* PC, float Sx);
	void DrawRepair(AIVPlayerController* PC, const iv::Fighter& F, float Sx);
	void DrawMenu(AIVGameFlow* Flow);"""),
])
h = open(S + "IVHUD.cpp", encoding="utf-8").read()
i = h.index("void AIVHUD::DrawHUD()")
j = h.index("// ------------------------------------------------------------------------------------------------------- menu")
new_main = open(r"F:\IVUnreal\Scripts\hud_main.txt", encoding="utf-8").read()
h = h[:i] + new_main + h[j:]
open(S + "IVHUD.cpp", "w", encoding="utf-8").write(h)

# ---------------- controller
patch(S + "IVPlayerController.h", [
    ("UCLASS()", """/** DbD-style below-deck repair: hold to work, and hit the skill checks that pop up. */
struct FIVRepairGame
{
	bool bActive = false, bWorking = false, bCheck = false;
	float Progress = 0.f, Time = 0.f, TimeLimit = 22.f;
	float Needle = 0.f, NeedleSpeed = 240.f, ZoneStart = 0.f, ZoneLen = 54.f, GreatLen = 12.f;
	float NextCheck = 1.2f, FlashGood = 0.f, FlashBad = 0.f, Cooldown = 0.f, RepairedMark = 0.f;
	int32 Level = 1;
};

UCLASS()"""),
    ("	bool WantsFreeLook() const;", """	bool WantsFreeLook() const;
	bool IsRepairing() const { return Repair.bActive; }
	const FIVRepairGame& GetRepair() const { return Repair; }
	FVector2D GetBerserkAim() const { return BerserkAim; }
	void StartRepair();
	void StopRepair(bool bSuccess);
	void UpdateRepair(float Dt);
	FIVRepairGame Repair;"""),
])
patch(S + "IVPlayerController.cpp", [
    ('#include "IVCombat.h"', '#include "IVCombat.h"\n#include "IVAudio.h"\n#include "IVFXManager.h"'),
    ("	FVector2D Move = bCombatEnabled ? MoveValue : FVector2D::ZeroVector;", "	FVector2D Move = (bCombatEnabled && !Repair.bActive) ? MoveValue : FVector2D::ZeroVector;"),
    ("	AIVCombatDirector* Dir = GetDirector();\n	if (Dir && !bAuto && bCombatEnabled)\n	{\n		UpdateCombatInput(Dt);",
     "	AIVCombatDirector* Dir = GetDirector();\n	UpdateRepair(Dt);\n	if (Dir && !bAuto && bCombatEnabled)\n	{\n		UpdateCombatInput(Dt);"),
    ("	const bool bPadLT = bPadGuard;",
     """	if (!Repair.bActive && (WasInputKeyJustPressed(EKeys::H) || WasInputKeyJustPressed(EKeys::Gamepad_Special_Right))) StartRepair();
	if (Repair.bActive) { In = FIVCombatInput(); return; }
	const bool bPadLT = bPadGuard;"""),
])
c = open(S + "IVPlayerController.cpp", encoding="utf-8").read()
c += r'''

// ------------------------------------------------------------------------------------------------ below-deck repair
void AIVPlayerController::StartRepair()
{
	AIVCombatDirector* Dir = GetDirector();
	AIVMechPawn* M = Mech();
	if (!Dir || !M || !Dir->GetDuel() || Repair.bActive || Repair.Cooldown > 0.f) return;
	const iv::Duel& D = *Dir->GetDuel();
	const iv::Fighter& F = D.fighter(MySide);
	if (D.result().over || D.lock().active || D.berserk().active || D.cinematic().active || F.breakdown <= 0) return;
	if (F.posture != iv::Posture::Standing && F.posture != iv::Posture::Staggered) return;
	FIVRepairGame G;
	G.bActive = true;
	G.Level = F.breakdown;
	G.TimeLimit = 20.f + 3.f * F.breakdown;
	Repair = G;
	Dir->SetAutopilot(MySide, true);
	IVAudio::Play2D(GetWorld(), TEXT("cockpit_switch_02"), 1.f);
	IVAudio::Play2D(GetWorld(), TEXT("cockpit_hud_lock"), 0.8f);
}

void AIVPlayerController::StopRepair(bool bSuccess)
{
	AIVCombatDirector* Dir = GetDirector();
	AIVMechPawn* M = Mech();
	Repair.bActive = false;
	Repair.bCheck = false;
	if (Dir) Dir->SetAutopilot(MySide, false);
	if (bSuccess)
	{
		if (Dir) Dir->RepairBreakdown(MySide, 3);
		if (M && M->GetCockpitFx()) M->GetCockpitFx()->Repair(1.f);
		IVAudio::Play2D(GetWorld(), TEXT("cockpit_hud_unlock"), 1.f);
		IVAudio::Play2D(GetWorld(), TEXT("cockpit_switch_04"), 1.f);
	}
	else
	{
		Repair.Cooldown = 6.f;
		IVAudio::Play2D(GetWorld(), TEXT("cockpit_alarm_warning"), 0.9f);
	}
}

void AIVPlayerController::UpdateRepair(float Dt)
{
	FIVRepairGame& G = Repair;
	G.Cooldown = FMath::Max(0.f, G.Cooldown - Dt);
	G.FlashGood = FMath::Max(0.f, G.FlashGood - Dt * 2.5f);
	G.FlashBad = FMath::Max(0.f, G.FlashBad - Dt * 2.5f);
	if (!G.bActive) return;
	AIVCombatDirector* Dir = GetDirector();
	AIVMechPawn* M = Mech();
	if (!Dir || !M || !Dir->GetDuel() || Dir->IsMatchOver()) { StopRepair(false); return; }
	G.Time += Dt;
	const bool bPress = WasInputKeyJustPressed(EKeys::SpaceBar) || WasInputKeyJustPressed(EKeys::LeftMouseButton) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Bottom) ||
		(GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) > 0.5f && !bPadStrikePrev);
	bPadStrikePrev = GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) > 0.5f;
	const bool bHold = IsInputKeyDown(EKeys::SpaceBar) || IsInputKeyDown(EKeys::LeftMouseButton) || IsInputKeyDown(EKeys::Gamepad_FaceButton_Bottom) || bPadStrikePrev;
	if (WasInputKeyJustPressed(EKeys::Escape) || WasInputKeyJustPressed(EKeys::H) || WasInputKeyJustPressed(EKeys::Gamepad_FaceButton_Right)) { StopRepair(false); G.Cooldown = 1.5f; return; }
	G.bWorking = bHold;
	if (bHold) G.Progress += Dt * 0.075f;
	M->AddCockpitImpulse(FMath::RandRange(-1.f, 1.f), FMath::RandRange(-1.f, 1.f), bHold ? 0.12f : 0.05f);
	auto Fail = [&]()
	{
		G.Progress = FMath::Max(0.f, G.Progress - 0.10f);
		G.FlashBad = 1.f;
		IVAudio::Play2D(GetWorld(), IVAudio::Variant(TEXT("cockpit_spark_"), 4), 1.f);
		M->AddCockpitImpulse(0.f, 0.f, 1.2f);
		if (M->GetCockpitFx()) M->GetCockpitFx()->Hit(0.55f, FVector(0, 1, 0), false);
		if (iv::Duel* Du = Dir->GetMutableDuel()) Du->ExternalHit(MySide, iv::Zone::Reactor, 2.5f, 3.f, 4);
	};
	if (!G.bCheck)
	{
		if (bHold)
		{
			G.NextCheck -= Dt;
			if (G.NextCheck <= 0.f)
			{
				G.bCheck = true;
				G.Needle = 0.f;
				G.ZoneStart = FMath::RandRange(110.f, 290.f);
				G.ZoneLen = FMath::RandRange(46.f, 58.f);
				G.GreatLen = 12.f;
				G.NeedleSpeed = 220.f + 28.f * G.Level;
				IVAudio::Play2D(GetWorld(), TEXT("cockpit_hud_lock"), 0.8f, 1.4f);
			}
		}
	}
	else
	{
		G.Needle += G.NeedleSpeed * Dt;
		if (bPress)
		{
			const float Rel = FMath::Fmod(G.Needle - G.ZoneStart + 720.f, 360.f);
			if (Rel < G.ZoneLen && G.Needle >= G.ZoneStart - 1.f)
			{
				const bool bGreat = Rel < G.GreatLen;
				G.Progress += bGreat ? 0.13f : 0.07f;
				G.FlashGood = 1.f;
				IVAudio::Play2D(GetWorld(), TEXT("cockpit_switch_03"), 1.f, bGreat ? 1.3f : 1.f);
			}
			else Fail();
			G.bCheck = false;
			G.NextCheck = FMath::RandRange(1.1f, 2.4f);
		}
		else if (G.Needle > G.ZoneStart + G.ZoneLen + 10.f)
		{
			Fail();
			G.bCheck = false;
			G.NextCheck = FMath::RandRange(1.1f, 2.4f);
		}
	}
	G.Progress = FMath::Clamp(G.Progress, 0.f, 1.f);
	if (G.Progress - G.RepairedMark > 0.2f)
	{
		G.RepairedMark = G.Progress;
		if (M->GetCockpitFx()) M->GetCockpitFx()->Repair(0.45f);
	}
	if (G.Progress >= 1.f) StopRepair(true);
	else if (G.Time >= G.TimeLimit) StopRepair(false);
}
'''
open(S + "IVPlayerController.cpp", "w", encoding="utf-8").write(c)
print("hud/ctrl ok")

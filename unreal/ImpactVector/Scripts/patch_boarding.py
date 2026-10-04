import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def ins_after(text, key, block):
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if key in l:
            ind = l[:len(l) - len(l.lstrip("\t"))]
            add = [(ind + bl if bl.strip() else bl) for bl in block.strip("\n").split("\n")]
            lines[i + 1:i + 1] = add
            return "\n".join(lines)
    raise AssertionError(key)


def repl(text, old, new):
    assert old in text, old
    return text.replace(old, new, 1)


# ------------------------------------------------------------------ director header
h, crlf = rd("IVCombat.h")
if "GetBoarding" not in h:
    h = repl(h, '#include "iv/Anim.h"', '#include "iv/Anim.h"\n#include "iv/Boarding.h"')
    h = repl(h, "class AIVMechPawn;", "class AIVMechPawn;\nclass AIVPilotFigure;")
    h = repl(h, "	bool bJump = false, bChop = false, bSlide = false, bMash = false, bBerserk = false, bQte = false;",
             "	bool bJump = false, bChop = false, bSlide = false, bMash = false, bBerserk = false, bQte = false;\n"
             "	// boarding: start / leap to the other shoulder / hatch-hack directions and buttons (edges)\n"
             "	bool bBoard = false, bBoardSwing = false;\n"
             "	int8 HackDx = 0, HackDy = 0;\n"
             "	bool bHackConfirm = false, bHackBack = false, bHackAux = false;")
    h = repl(h, "	FIVCombatEventSignature OnEvent;",
             "	FIVCombatEventSignature OnEvent;\n"
             "	const iv::Boarding& GetBoarding() const { return Board; }\n"
             "	bool IsBoardingActive() const { return Board.Active(); }\n"
             "	float GetBoardingCooldown01() const { return Board.cooldownLeft() > 0 ? 1.f - FMath::Clamp(float(Board.cooldownLeft()) / float(iv::tune::kBoardCooldownTicks), 0.f, 1.f) : 1.f; }")
    h = repl(h, "	void ApplyHitStop(float Seconds, float Dilation);",
             "	void ApplyHitStop(float Seconds, float Dilation);\n"
             "	iv::Boarding Board;\n"
             "	iv::BoardingInput BoardIn;\n"
             "	TWeakObjectPtr<AIVPilotFigure> Pilot;\n"
             "	bool bBoardCamOn = false;\n"
             "	FVector BoardCamFrom = FVector::ZeroVector, BoardCamAt = FVector::ZeroVector;\n"
             "	float BoardBlastFlash = 0.f;\n"
             "	void UpdateBoardingPresentation(float Dt);\n"
             "	void HandleBoardingEvent(const iv::Event& Ev);")
    wr("IVCombat.h", h, crlf)

# ------------------------------------------------------------------ director cpp
c, crlf = rd("IVCombat.cpp")
if "UpdateBoardingPresentation" not in c:
    c = repl(c, '#include "IVHelicopter.h"', '#include "IVHelicopter.h"\n#include "IVBoarding.h"')
    c = ins_after(c, "PlayerIn2 = FIVCombatInput();", """{
	iv::BoardingConfig Bc;
	Bc.owner = iv::Side::A;
	Bc.enemyArchetype = BotStyle;
	Bc.enemyDifficulty = BotLevel;
	Bc.seed = BotSeed + 3;
	Board = iv::Boarding(Bc);
	BoardIn = iv::BoardingInput();
	if (AIVPilotFigure* PF = Pilot.Get()) PF->Hide();
	if (Player.IsValid()) Player->SetBoardCam(false, FVector::ZeroVector, FVector::ZeroVector, 60.f);
	bBoardCamOn = false;
}""")
    c = ins_after(c, "iv::Input A = BuildInput(PlayerIn, bFirstOfFrame);", """if (PlayerIn.bBoard) BoardIn.start = true;
if (PlayerIn.bBoardSwing) BoardIn.swing = true;
if (PlayerIn.HackDx) BoardIn.hack.dx = PlayerIn.HackDx;
if (PlayerIn.HackDy) BoardIn.hack.dy = PlayerIn.HackDy;
if (PlayerIn.bHackConfirm) BoardIn.hack.confirm = true;
if (PlayerIn.bHackBack) BoardIn.hack.back = true;
if (PlayerIn.bHackAux) BoardIn.hack.aux = true;""")
    # the autopilot replaces the human input while the pilot is outside
    c = ins_after(c, "if (PlayerBot.IsValid()) { A = PlayerBot->Decide", "A = Board.Filter(*Duel, A);")
    c = ins_after(c, "Duel->Step(A, B, W);", "Board.Step(*Duel, BoardIn);\nBoardIn = iv::BoardingInput();")
    c = ins_after(c, "PlayerIn2.bJump = PlayerIn2.bChop", "PlayerIn.bBoard = PlayerIn.bBoardSwing = PlayerIn.bHackConfirm = PlayerIn.bHackBack = PlayerIn.bHackAux = false;\nPlayerIn.HackDx = PlayerIn.HackDy = 0;")
    c = ins_after(c, "Anim[0] = iv::MakeAnimState(Duel->fighter(iv::Side::A));", "UpdateBoardingPresentation(Dt);")
    # events
    c = repl(c, "void AIVCombatDirector::Dispatch(const iv::Event& Ev)\n{", "void AIVCombatDirector::Dispatch(const iv::Event& Ev)\n{\n	HandleBoardingEvent(Ev);")
    c += r'''

// ---------------------------------------------------------------------------------------------------------- boarding
void AIVCombatDirector::HandleBoardingEvent(const iv::Event& Ev)
{
	using iv::EventType;
	AIVMechPawn* P = Player.Get();
	AIVMechPawn* E = Enemy.Get();
	UWorld* W = GetWorld();
	if (!P || !E) return;
	switch (Ev.type)
	{
	case EventType::BoardingStarted:
		IVAudio::Play2D(W, TEXT("cockpit_alarm_warning"), 0.8f);
		IVAudio::Play3D(W, TEXT("mech_hydraulic_release"), P->GetActorLocation() + FVector(0, 0, 4000.f), 1.f, 0.8f);
		break;
	case EventType::HookFired:
		IVAudio::Play3D(W, TEXT("env_missile_incoming"), P->GetZoneWorldLocation(iv::Zone::ArmR), 1.f, 1.5f);
		break;
	case EventType::HookLanded:
		IVAudio::Play3D(W, TEXT("block_impact"), E->GetZoneWorldLocation(Ev.a ? iv::Zone::ShoulderR : iv::Zone::ShoulderL), 1.f);
		if (AIVFXManager* FX = AIVFXManager::Get(W)) FX->SpawnSparks(E->GetZoneWorldLocation(Ev.a ? iv::Zone::ShoulderR : iv::Zone::ShoulderL), FVector::UpVector, 60, 5000.f);
		break;
	case EventType::GrenadeThrown:
		IVAudio::Play2D(W, TEXT("cockpit_hud_lock"), 0.8f);
		break;
	case EventType::BoardingBlast:
	{
		const FVector At = E->GetZoneWorldLocation(Ev.zone);
		if (AIVFXManager* FX = AIVFXManager::Get(W))
		{
			FX->SpawnExplosion(At, 2.4f);
			FX->SpawnChunks(At, FVector(0, 0, 1), 12, EIVChunk::Armor, 4.f, 5500.f, 1.f, 1.3f);
			FX->SpawnChunks(At, FVector(0, 0, 1), 6, EIVChunk::Steel, 3.f, 5000.f, 0.9f, 1.3f);
		}
		IVAudio::Play3D(W, TEXT("env_distant_boom_01"), At, 1.f);
		IVAudio::Play3D(W, TEXT("env_missile_explosion"), At, 1.f);
		E->AddCockpitImpulse(0.f, 0.f, 1.2f);
		BoardBlastFlash = 1.f;
		break;
	}
	case EventType::BoardingSwatTelegraph:
		IVAudio::Play2D(W, TEXT("cockpit_alarm_critical"), 1.f);
		break;
	case EventType::BoardingSwatImpact:
		IVAudio::Play3D(W, TEXT("hit_lowfreq_thump_heavy"), P->GetActorLocation(), 1.f);
		break;
	case EventType::BoardingSwingOk:
		IVAudio::Play3D(W, TEXT("mech_hydraulic_release"), P->GetActorLocation(), 0.8f, 1.4f);
		break;
	case EventType::BoardingShock:
		if (AIVFXManager* FX = AIVFXManager::Get(W)) FX->SpawnSparks(P->GetActorLocation() + FVector(0, 0, 5000.f), FVector::UpVector, 30, 4000.f);
		break;
	case EventType::BoardingEnded:
		IVAudio::Play2D(W, Ev.a == int32(iv::BoardingOutcome::Success) ? TEXT("cockpit_hud_unlock") : TEXT("cockpit_alarm_warning"), 1.f);
		break;
	default: break;
	}
}

void AIVCombatDirector::UpdateBoardingPresentation(float Dt)
{
	AIVMechPawn* P = Player.Get();
	AIVMechPawn* E = Enemy.Get();
	if (!P || !E) return;
	BoardBlastFlash = FMath::Max(0.f, BoardBlastFlash - Dt * 1.5f);
	const iv::BoardPhase Ph = Board.phase();
	const bool bShow = Board.Active();
	if (!bShow)
	{
		if (bBoardCamOn)
		{
			bBoardCamOn = false;
			P->SetBoardCam(false, FVector::ZeroVector, FVector::ZeroVector, 60.f);
			if (AIVPilotFigure* PF = Pilot.Get()) PF->Hide();
		}
		return;
	}
	if (!Pilot.IsValid())
	{
		FActorSpawnParameters Sp;
		Sp.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Pilot = GetWorld()->SpawnActor<AIVPilotFigure>(P->GetActorLocation(), FRotator::ZeroRotator, Sp);
	}
	AIVPilotFigure* PF = Pilot.Get();
	if (!PF) return;
	const iv::Arm Sh = Board.shoulder();
	const iv::Zone OwnZ = Sh == iv::Arm::R ? iv::Zone::ShoulderR : iv::Zone::ShoulderL;
	const iv::Zone OwnArm = Sh == iv::Arm::R ? iv::Zone::ArmR : iv::Zone::ArmL;
	const iv::Zone OtherZ = Sh == iv::Arm::R ? iv::Zone::ShoulderL : iv::Zone::ShoulderR;
	FIVBoardView V;
	V.Phase = Ph;
	V.U = Board.phaseLength() > 0 ? FMath::Clamp(float(Board.phaseTicks()) / float(Board.phaseLength()), 0.f, 1.f) : 0.f;
	V.Cockpit = P->GetZoneWorldLocation(iv::Zone::Head) - FVector(0, 0, 300.f);
	V.OwnShoulder = P->GetZoneWorldLocation(OwnZ) + FVector(0, 0, 300.f);
	V.OwnWrist = P->GetZoneWorldLocation(OwnArm);
	V.EnemyUp = FVector::UpVector;
	V.EnemyShoulder = E->GetZoneWorldLocation(OwnZ);
	V.EnemyHatch = V.EnemyShoulder + FVector(0, 0, 420.f);
	V.EnemyOtherShoulder = E->GetZoneWorldLocation(OtherZ) + FVector(0, 0, 420.f);
	V.Away = (P->GetActorLocation() - E->GetActorLocation()).GetSafeNormal2D();
	PF->Present(V, Dt);

	// camera
	const FVector Focus = PF->GetPilotLocation();
	const FVector Side = FVector::CrossProduct(V.Away, FVector::UpVector).GetSafeNormal();
	const FVector Up(0, 0, 1);
	const FVector ToHatch = (V.EnemyHatch - Focus).GetSafeNormal();
	FVector From = Focus, At = Focus;
	float Fov = 55.f;
	using BP = iv::BoardPhase;
	switch (Ph)
	{
	case BP::ClimbOut: case BP::OnShoulder: case BP::ClimbIn:
		From = V.Cockpit - P->GetActorForwardVector() * 3600.f + P->GetActorRightVector() * 2000.f + Up * 900.f;
		At = (Focus + V.OwnShoulder) * 0.5f;
		break;
	case BP::HookLaunch:
		From = V.OwnShoulder + Side * 3800.f + Up * 500.f;
		At = (V.OwnShoulder + V.EnemyHatch) * 0.5f;
		Fov = 62.f;
		break;
	case BP::HookFlight: case BP::ReturnHook: case BP::HookSwing:
		From = Focus - ToHatch * 2600.f + Side * 1000.f + Up * 600.f;
		At = Focus + ToHatch * 1500.f;
		Fov = 60.f;
		break;
	case BP::Landing: case BP::Hacking: case BP::GrenadeThrow:
		From = Focus + V.Away * 1800.f + Side * 600.f + Up * 700.f;
		At = V.EnemyHatch + Up * 100.f;
		Fov = 50.f;
		break;
	case BP::Escape: case BP::WatchBlast:
		From = Focus + V.Away * 2600.f + Side * 900.f + Up * 150.f;
		At = (V.EnemyHatch * 0.7f + Focus * 0.3f);
		Fov = 58.f;
		break;
	default: break;
	}
	if (Board.swatActive())
	{
		const iv::Zone HandZ = Board.swatShoulder() == iv::Arm::R ? iv::Zone::ArmR : iv::Zone::ArmL;
		const FVector Hand = E->GetZoneWorldLocation(HandZ);
		From = Focus + V.Away * 1500.f + Side * 400.f + Up * 500.f;
		At = Hand * 0.6f + Focus * 0.4f;
		Fov = 70.f;
	}
	if (!bBoardCamOn) { BoardCamFrom = From; BoardCamAt = At; }
	BoardCamFrom = FMath::VInterpTo(BoardCamFrom, From, Dt, 5.f);
	BoardCamAt = FMath::VInterpTo(BoardCamAt, At, Dt, 7.f);
	bBoardCamOn = true;
	P->SetBoardCam(true, BoardCamFrom, BoardCamAt, Fov);
}
'''
    wr("IVCombat.cpp", c, crlf)

# ------------------------------------------------------------------ pawn
ph, crlf = rd("IVMechPawn.h")
if "SetBoardCam" not in ph:
    ph = ins_after(ph, "bool IsInCinematic() const { return bCine; }", """/** Outside camera while the pilot is on the grapple (boarding). */
void SetBoardCam(bool bOn, const FVector& From, const FVector& At, float Fov) { bBoardCam = bOn; BoardFrom = From; BoardAt = At; BoardFov = Fov; }""")
    ph = ins_after(ph, "bool bCine = false;", "bool bBoardCam = false;\nFVector BoardFrom = FVector::ZeroVector, BoardAt = FVector::ZeroVector;\nfloat BoardFov = 60.f;")
    wr("IVMechPawn.h", ph, crlf)
pc, crlf = rd("IVMechPawn.cpp")
if "bBoardCam" not in pc:
    OLD = "\tif (bCine)\n\t{\n\t\tSetFirstPersonView(false);"
    NEW = ("\tif (bBoardCam && !bCine)\n\t{\n\t\tSetFirstPersonView(false);\n\t\tCamera->SetFieldOfView(BoardFov);\n"
           "\t\tCamera->SetWorldLocationAndRotation(BoardFrom, (BoardAt - BoardFrom).Rotation());\n\t\treturn;\n\t}\n") + OLD
    pc = repl(pc, OLD, NEW)
    wr("IVMechPawn.cpp", pc, crlf)
print("boarding patched")

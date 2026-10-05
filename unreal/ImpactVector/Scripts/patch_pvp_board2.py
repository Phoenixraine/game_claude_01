import io, re
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new):
    assert old in t, old[:90]
    return t.replace(old, new, 1)


d, c = rd("IVCombat.cpp")
if "UpdateVictimCam" in d and "void AIVCombatDirector::UpdateVictimCam" not in d:
    a = d.index("void AIVCombatDirector::UpdateBoardingPresentation(float Dt)")
    endmark = "	P->SetBoardCam(true, BoardCamFrom, BoardCamAt, Fov);\n}"
    b = d.index(endmark, a) + len(endmark)
    f = d[a:b]
    f = f.replace("void AIVCombatDirector::UpdateBoardingPresentation(float Dt)", "void AIVCombatDirector::UpdateBoardingPresentation(float Dt, iv::Side Owner)")
    f = rep(f, "	AIVMechPawn* P = Player.Get();\n	AIVMechPawn* E = Enemy.Get();\n	if (!P || !E) return;\n	BoardBlastFlash = FMath::Max(0.f, BoardBlastFlash - Dt * 1.5f);\n	const iv::BoardPhase Ph = Board.phase();\n	const bool bShow = Board.Active();",
            "	const int32 Idx = iv::Index(Owner);\n	AIVMechPawn* P = PawnOf(Owner);\n	AIVMechPawn* E = PawnOf(iv::Other(Owner));\n	if (!P || !E) return;\n	const iv::Boarding& Brd = Board[Idx];\n	if (Owner == iv::Side::A) BoardBlastFlash = FMath::Max(0.f, BoardBlastFlash - Dt * 1.5f);\n	const iv::BoardPhase Ph = Brd.phase();\n	const bool bShow = Brd.Active();")
    f = f.replace("Board.", "Brd.")
    f = re.sub(r"\bbBoardCamOn\b", "bBoardCamOn[Idx]", f)
    f = re.sub(r"\bBoardCamFrom\b", "BoardCamFrom[Idx]", f)
    f = re.sub(r"\bBoardCamAt\b", "BoardCamAt[Idx]", f)
    f = re.sub(r"\bPilot\b", "Pilot[Idx]", f)
    f = rep(f, "	case BP::Landing: case BP::Hacking: case BP::GrenadeThrow:", "	case BP::Landing: case BP::Hacking: case BP::GrenadeThrow: case BP::Stunned:")
    new = f + """

// What the DEFENDER sees while an enemy pilot sits on his mech: a camera over his own head looking down at the shoulder where the stranger is.
void AIVCombatDirector::UpdateVictimCam(float Dt, iv::Side Owner)
{
	const iv::Side Vic = iv::Other(Owner);
	const int32 Vi = iv::Index(Vic), Oi = iv::Index(Owner);
	AIVMechPawn* V = PawnOf(Vic);
	if (!V) return;
	const bool bWant = Board[Oi].Active() && IsHuman(Vic) && !Board[Vi].Active();
	if (!bWant)
	{
		if (bVictimCamOn[Vi])
		{
			bVictimCamOn[Vi] = false;
			if (!Board[Vi].Active()) V->SetBoardCam(false, FVector::ZeroVector, FVector::ZeroVector, 60.f);
		}
		return;
	}
	const iv::Arm Sh = Board[Oi].shoulder();
	const FVector Shoulder = V->GetZoneWorldLocation(Sh == iv::Arm::R ? iv::Zone::ShoulderR : iv::Zone::ShoulderL);
	AIVPilotFigure* PF = Pilot[Oi].Get();
	const FVector Focus = PF ? PF->GetPilotLocation() : Shoulder + FVector(0, 0, 300.f);
	const FVector Head = V->GetZoneWorldLocation(iv::Zone::Head);
	const FVector Fwd = V->GetActorForwardVector(), Rt = V->GetActorRightVector();
	FVector From = Head + FVector(0, 0, 450.f) - Fwd * 1500.f + Rt * (Sh == iv::Arm::R ? -700.f : 700.f);
	FVector At = (Shoulder + Focus) * 0.5f;
	float Fov = 66.f;
	if (Board[Oi].swatActive())
	{
		const float U = 1.f - float(Board[Oi].swatTicksToImpact()) / float(FMath::Max(1, iv::tune::kHumanSwatWindupTicks));
		Fov = 66.f - 10.f * FMath::Clamp(U, 0.f, 1.f);     // tension: the view narrows as the hand comes down
	}
	if (!bVictimCamOn[Vi]) { VictimCamFrom[Vi] = From; VictimCamAt[Vi] = At; }
	VictimCamFrom[Vi] = FMath::VInterpTo(VictimCamFrom[Vi], From, Dt, 5.f);
	VictimCamAt[Vi] = FMath::VInterpTo(VictimCamAt[Vi], At, Dt, 7.f);
	bVictimCamOn[Vi] = true;
	V->SetBoardCam(true, VictimCamFrom[Vi], VictimCamAt[Vi], Fov);
}

float AIVCombatDirector::GetUltimateMultiplier(iv::Side S) const
{
	if (!Duel.IsValid()) return 1.f;
	const float I = FMath::Clamp(Duel->fighter(S).body.Integrity(), 0.f, 1.f);
	return 1.f + (iv::tune::kUltComebackMax - 1.f) * (1.f - I);
}

// The ultimate's windup punch and its counter (core v6).
void AIVCombatDirector::HandleUltimateEvent(const iv::Event& Ev)
{
	using iv::EventType;
	UWorld* W = GetWorld();
	AIVMechPawn* Actor = PawnOf(Ev.actor);
	AIVMechPawn* Other = PawnOf(iv::Other(Ev.actor));
	if (!Actor || !Other) return;
	switch (Ev.type)
	{
	case EventType::UltimateStarted:
		IVAudio::Play3D(W, TEXT("mech_weapon_charge_peak"), Actor->GetZoneWorldLocation(iv::Zone::ArmL), 1.f, 0.6f);
		IVAudio::Play3D(W, TEXT("mech_hydraulic_release"), Actor->GetActorLocation(), 1.f, 0.7f);
		if (Other->IsLocallyControlled()) IVAudio::Play2D(W, TEXT("cockpit_alarm_critical"), 0.9f);
		break;
	case EventType::UltimateCountered:
	{
		// Ev.actor is the defender: his guard takes the fist; the attacker's ultimate is gone
		const FVector At = Other->GetZoneWorldLocation(iv::Zone::ArmL);
		if (AIVFXManager* FX = AIVFXManager::Get(W))
		{
			FX->SpawnSparks(At, FVector(0, 0, 1), 120, 8000.f, 3.f);
			FX->SpawnFlash(At, FLinearColor(0.7f, 0.9f, 1.f), 4.0e5f, 0.2f, 14000.f);
			FX->SpawnDust(At, 2400.f, 16, 0.9f);
		}
		IVAudio::Play3D(W, TEXT("parry_clang"), At, 1.f, 0.7f);
		IVAudio::Play3D(W, TEXT("hit_lowfreq_thump_heavy"), At, 1.f);
		Actor->AddCockpitImpulse(0.f, 0.f, 0.8f);
		Other->AddCockpitImpulse(0.f, 0.f, 0.5f);
		ApplyHitStop(0.2f, 0.1f);
		if (Actor->IsLocallyControlled()) IVAudio::Play2D(W, TEXT("cockpit_hud_unlock"), 1.f);
		break;
	}
	case EventType::UltimateCancelled:
		IVAudio::Play3D(W, TEXT("mech_stabilizer_whine"), Other->GetActorLocation(), 0.8f, 0.6f);
		break;
	default: break;
	}
}
"""
    d = d[:a] + new + d[b:]
    d = rep(d, "void AIVCombatDirector::Dispatch(const iv::Event& Ev)\n{\n	HandleBoardingEvent(Ev);", "void AIVCombatDirector::Dispatch(const iv::Event& Ev)\n{\n	HandleBoardingEvent(Ev);\n	HandleUltimateEvent(Ev);")
    wr("IVCombat.cpp", d, c)
print("director presentation patched")

import io
SRC = r"F:\IVUnreal\Source\ImpactVector"
CORE = r"F:\IVRepo\core"


def rd(base, n):
    s = io.open(base + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(base, n, s, crlf):
    io.open(base + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new):
    assert old in t, old[:90]
    return t.replace(old, new, 1)


# ---- core accessor
b, c = rd(CORE, "include/iv/Boarding.h")
if "swatTotalTicks" not in b:
    b = rep(b, "  int swatTicksToImpact() const { return swat_.ticksToImpact; }", "  int swatTicksToImpact() const { return swat_.ticksToImpact; }\n  int swatTotalTicks() const { return swat_.total; }")
    wr(CORE, "include/iv/Boarding.h", b, c)

# ---- pawn header
h, c = rd(SRC, "IVMechPawn.h")
if "SlapSm" not in h:
    h = rep(h, "	void StartRocketArm() { RocketArmT = 0.001f; }", """	void StartRocketArm() { RocketArmT = 0.001f; }
	/** Boarding defence: the free hand rises and comes down on the shoulder where the enemy pilot sits. U 0..1 follows the telegraph; 0 = none. */
	void SetSlap(float U, bool bRightShoulderTarget) { SlapU = U; bSlapRight = bRightShoulderTarget; }
	/** The pilot is outside and lies stunned: the empty mech slumps (kneeling, lights low). */
	void SetPoweredDown(bool b) { bPoweredDown = b; }""")
    h = rep(h, "	float RocketArmT = 0.f;", "	float RocketArmT = 0.f;\n	float SlapU = 0.f, SlapSm = 0.f, SlapPrev = 0.f, SlapHoldT = 0.f;\n	bool bSlapRight = true, bPoweredDown = false;")
    wr(SRC, "IVMechPawn.h", h, c)

p, c = rd(SRC, "IVMechPawn.cpp")
if "SlapSm" not in p:
    # powered-down slump overrides every other pose
    p = rep(p, "	if (S.posture == iv::Posture::KnockedDown)\n	{\n		bLegs = true;", "	if (bPoweredDown)\n	{\n		bLegs = true;\n		if (const FIVPoseAngles* K = P(TEXT(\"kneel\"))) Target = FIVPoseAngles::Lerp(*Guard, *K, 0.6f);\n	}\n	else if (S.posture == iv::Posture::KnockedDown)\n	{\n		bLegs = true;")
    # ultimate windup punch (state driven)
    p = rep(p, "	else if (S.phase != iv::Phase::Idle)\n	{\n		const float U = S.progress;", """	else if (S.ultWindTicks > 0)
	{
		// the ultimate's windup: the off hand draws back and drives a punch under the chest (the last quarter is the strike)
		const float Uw = 1.f - float(S.ultWindTicks) / float(FMath::Max(1, S.ultWindLen));
		const FIVPoseAngles* W = P(TEXT("quick_palm_l_windup"));
		const FIVPoseAngles* K = P(TEXT("quick_palm_l_strike"));
		if (W && K) Target = Uw < 0.75f ? FIVPoseAngles::Lerp(*Guard, *W, Ease(Uw / 0.75f)) : FIVPoseAngles::Lerp(*W, *K, Ease((Uw - 0.75f) / 0.25f));
		bLegs = true;
		if (FVector* Th = Target.Joint.Find(FName(TEXT("pelvis")))) Th->X += 6.f * FMath::Sin(Uw * 3.14159f);
	}
	else if (S.phase != iv::Phase::Idle)
	{
		const float U = S.progress;""")
    # slap overlay, right after the rocket arm overlay
    p = rep(p, "	// hit kick: torso recoil on top of everything, decays quickly", """	// boarding defence: the hand opposite to the stranger's shoulder rises, then comes across and slaps it. Slow and readable.
	{
		float Tgt = SlapU;
		if (SlapPrev > 0.9f && SlapU < 0.05f) SlapHoldT = 0.5f;          // the impact beat: the hand stays on the shoulder for a moment
		SlapPrev = SlapU;
		if (SlapHoldT > 0.f) { SlapHoldT -= Dt; Tgt = 1.f; }
		SlapSm = FMath::FInterpTo(SlapSm, Tgt, Dt, Tgt > SlapSm ? 12.f : 5.f);
		if (SlapSm > 0.01f)
		{
			const bool bR = bSlapRight;                              // the stranger sits on our right shoulder: the LEFT hand slaps it
			const float Ww = Ease(FMath::Clamp(SlapSm / 0.72f, 0.f, 1.f));
			const float Sw = Ease(FMath::Clamp((SlapSm - 0.72f) / 0.28f, 0.f, 1.f));
			const float Wt = FMath::Clamp(SlapSm * 4.f, 0.f, 1.f);
			auto Mir = [&](const FVector& V) { return bR ? V : FVector(V.X, -V.Y, -V.Z); };
			const TCHAR* Ua = bR ? TEXT("upperarm_l") : TEXT("upperarm_r");
			const TCHAR* Fa = bR ? TEXT("forearm_l") : TEXT("forearm_r");
			const TCHAR* Ha = bR ? TEXT("hand_l") : TEXT("hand_r");
			auto Drive = [&](const TCHAR* Name, const FVector& Wind, const FVector& Hit)
			{
				if (FVector* Cur = Pose.Joint.Find(FName(Name)))
				{
					const FVector T = FMath::Lerp(FMath::Lerp(*Cur, Mir(Wind), Ww), Mir(Hit), Sw);
					*Cur = FMath::Lerp(*Cur, T, Wt);
				}
			};
			Drive(Ua, FVector(-165.f, -5.f, 0.f), FVector(-84.f, -64.f, 18.f));
			Drive(Fa, FVector(-12.f, 0.f, 0.f), FVector(-62.f, 0.f, 0.f));
			Drive(Ha, FVector(-10.f, 0.f, 0.f), FVector(-20.f, 0.f, 0.f));
			if (FVector* Tt = Pose.Joint.Find(FName(TEXT("torso")))) Tt->Y += (bR ? -1.f : 1.f) * 10.f * Sw * Wt;   // the body turns into the slap
		}
	}
	// hit kick: torso recoil on top of everything, decays quickly""")
    wr(SRC, "IVMechPawn.cpp", p, c)

# ---- pilot figure: lying stunned on the shoulder
f, c = rd(SRC, "IVBoarding.cpp")
if "P::Stunned" not in f:
    f = rep(f, "	float Kneel = 0.f;\n	const FVector Up(0, 0, 1);", "	float Kneel = 0.f, Lie = 0.f;\n	const FVector Up(0, 0, 1);")
    f = rep(f, "	case P::GrenadeThrow:\n		Pos = V.EnemyHatch + V.EnemyUp * 110.f;", "	case P::Stunned:\n		// slapped off his feet: lies on the shoulder, dazed, the cable hanging slack\n		Pos = V.EnemyHatch + V.EnemyUp * 40.f + Up * 14.f * FMath::Sin(Tm * 2.2f);\n		Lie = 1.f; bCable = true; Sag = 140.f;\n		break;\n	case P::GrenadeThrow:\n		Pos = V.EnemyHatch + V.EnemyUp * 110.f;")
    f = rep(f, "	const FRotator Rot(bFly ? -22.f : 0.f, Facing.Rotation().Yaw, 0.f);", "	const FRotator Rot(bFly ? -22.f : (Lie > 0.5f ? 82.f : 0.f), Facing.Rotation().Yaw, Lie > 0.5f ? 6.f * FMath::Sin(Tm * 3.1f) : 0.f);")
    wr(SRC, "IVBoarding.cpp", f, c)

# ---- director: drive slap + slump, swat impact effects
d, c = rd(SRC, "IVCombat.cpp")
if "SetSlap" not in d:
    d = rep(d, "	for (int32 s = 0; s < 2; ++s) { UpdateBoardingPresentation(Dt, s == 0 ? iv::Side::A : iv::Side::B); UpdateVictimCam(Dt, s == 0 ? iv::Side::A : iv::Side::B); }",
            """	for (int32 s = 0; s < 2; ++s) { UpdateBoardingPresentation(Dt, s == 0 ? iv::Side::A : iv::Side::B); UpdateVictimCam(Dt, s == 0 ? iv::Side::A : iv::Side::B); }
	for (int32 s = 0; s < 2; ++s)
	{
		// the boarded mech slaps its own shoulder; the owner's empty mech slumps while its pilot lies stunned
		AIVMechPawn* Owner = PawnOf(s == 0 ? iv::Side::A : iv::Side::B);
		AIVMechPawn* Victim = PawnOf(s == 0 ? iv::Side::B : iv::Side::A);
		if (!Owner || !Victim) continue;
		const iv::Boarding& Bd = Board[s];
		if (Bd.swatActive()) Victim->SetSlap(1.f - float(Bd.swatTicksToImpact()) / float(FMath::Max(1, Bd.swatTotalTicks())), Bd.swatShoulder() == iv::Arm::R);
		else Victim->SetSlap(0.f, Victim->IsSlapRight());
		const bool bStun = Bd.Active() && Bd.phase() == iv::BoardPhase::Stunned;
		Owner->SetPoweredDown(bStun);
		if (bStun && FMath::FRand() < Dt * 4.f)
			if (AIVFXManager* FX = AIVFXManager::Get(GetWorld())) FX->SpawnSparks(Owner->GetZoneWorldLocation(iv::Zone::Torso) + FVector(0, 0, 400.f), FVector::UpVector, 14, 4000.f);
	}""")
    d = rep(d, "	case EventType::BoardingSwatImpact:\n		IVAudio::Play3D(W, TEXT(\"hit_lowfreq_thump_heavy\"), P->GetActorLocation(), 1.f);\n		break;",
            """	case EventType::BoardingSwatImpact:
	{
		const iv::Zone Sz = Ev.b ? iv::Zone::ShoulderR : iv::Zone::ShoulderL;
		const FVector At = E->GetZoneWorldLocation(Sz);
		IVAudio::Play3D(W, TEXT("hit_lowfreq_thump_heavy"), At, 1.f);
		IVAudio::Play3D(W, TEXT("hit_metal_contact_heavy"), At, 1.f, 0.8f);
		E->AddCockpitImpulse(0.f, 0.f, Ev.a ? 0.9f : 0.5f);
		if (AIVFXManager* FX = AIVFXManager::Get(W))
		{
			FX->SpawnDust(At, 2200.f, 18, 1.0f);
			FX->SpawnSparks(At + FVector(0, 0, 300.f), FVector::UpVector, Ev.a ? 90 : 30, 6000.f, 2.f);
			if (Ev.a) FX->SpawnFlash(At, FLinearColor(1.f, 0.7f, 0.3f), 3.0e5f, 0.2f, 12000.f);
		}
		break;
	}
	case EventType::BoardingSmashed:
		if (Ev.b) IVAudio::Play2D(W, TEXT("cockpit_alarm_critical"), 0.9f);   // the pilot was slapped down, not killed
		break;""")
    wr(SRC, "IVCombat.cpp", d, c)
print("pawn / pilot / director fx patched")

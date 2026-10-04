"""UE pawn: poses/FX for lunge, jump, chop, slide, overload, rage; FX manager jets; hull Rage param."""
SRC = r"F:\IVUnreal\Source\ImpactVector" + "\\"


def patch(path, edits):
    s = open(path, encoding="utf-8").read()
    for a, b in edits:
        assert a in s, (path, a[:90])
        s = s.replace(a, b, 1)
    open(path, "w", encoding="utf-8").write(s)


patch(SRC + "IVFXManager.h", [
    ("	void SpawnFlame(const FVector& Center, float Radius, int32 Count, float Strength = 1.f);",
     "	void SpawnFlame(const FVector& Center, float Radius, int32 Count, float Strength = 1.f);\n	/** A directed burst of flame (jetpack nozzle): Dir is the exhaust direction. */\n	void SpawnJet(const FVector& Pos, const FVector& Dir, int32 Count, float Speed, float Size);"),
])
patch(SRC + "IVFXManager.cpp", [
    ("void AIVFXManager::SpawnFlash(",
     """void AIVFXManager::SpawnJet(const FVector& Pos, const FVector& Dir, int32 Count, float Speed, float Size)
{
	for (int32 i = 0; i < Count && Flames.Num() < MaxFlames; ++i)
	{
		FIVFlame F;
		F.Pos = Pos + Rng.VRand() * Size * 0.15f;
		F.Vel = Dir * Speed * Rng.FRandRange(0.7f, 1.1f) + Rng.VRand() * Speed * 0.08f;
		F.Life = Rng.FRandRange(0.25f, 0.55f);
		F.Size0 = Size * Rng.FRandRange(0.5f, 0.8f);
		F.Size1 = Size * Rng.FRandRange(1.2f, 1.9f);
		F.Roll = Rng.FRandRange(0.f, 360.f);
		F.Rise = 0.f;
		F.Heat = Rng.FRandRange(0.8f, 1.f);
		F.Seed = Rng.FRand();
		Flames.Add(F);
	}
}

void AIVFXManager::SpawnFlash("""),
])

patch(SRC + "IVMechPawn.h", [
    ("	void StartCinematic(AIVMechPawn* Subject, float Seconds, int32 Kind);",
     """	// v5 presentation
	void SetRage(float R) { RageTarget = R; }
	float GetRage() const { return Rage; }
	void PlayBerserkSwing(iv::SwingSide Side);
	void StartCounterPunch(AIVMechPawn* Victim);
	void StartLockPose(bool bOn);
	float GetAirLift() const { return AirLift; }
	void StartCinematic(AIVMechPawn* Subject, float Seconds, int32 Kind);"""),
    ("	void UpdateDamageFX(float Dt);",
     "	void UpdateDamageFX(float Dt);\n	void UpdateV5Fx(float Dt);\n	float Rage = 0.f, RageTarget = 0.f, AirLift = 0.f, JetAcc = 0.f, LungeFxAcc = 0.f;"),
])

patch(SRC + "IVMechPawn.cpp", [
    ("	const FString Side = SideName(S.side);",
     "	const FString Side = (S.kind == iv::StrikeKind::Lunge) ? FString(TEXT(\"right\")) : ((S.kind == iv::StrikeKind::AirChop) ? FString(TEXT(\"up\")) : FString(SideName(S.side)));"),
    ("	else if (S.posture == iv::Posture::Staggered || S.posture == iv::Posture::ShutDown)\n	{\n		bLegs = true;\n		if (const FIVPoseAngles* K = P(TEXT(\"kneel\"))) Target = FIVPoseAngles::Lerp(*Guard, *K, S.posture == iv::Posture::ShutDown ? 0.9f : 0.45f * FMath::Sin(FMath::Clamp(S.postureProgress, 0.f, 1.f) * 3.14159f));\n	}",
     """	else if (S.posture == iv::Posture::Staggered || S.posture == iv::Posture::ShutDown || S.posture == iv::Posture::Overloaded)
	{
		bLegs = true;
		if (const FIVPoseAngles* K = P(TEXT("kneel"))) Target = FIVPoseAngles::Lerp(*Guard, *K, (S.posture == iv::Posture::ShutDown || S.posture == iv::Posture::Overloaded) ? 0.9f : 0.45f * FMath::Sin(FMath::Clamp(S.postureProgress, 0.f, 1.f) * 3.14159f));
	}
	else if (S.posture == iv::Posture::Sliding)
	{
		bLegs = true;
		if (const FIVPoseAngles* K = P(TEXT("kneel"))) Target = FIVPoseAngles::Lerp(*Guard, *K, 0.8f);
	}"""),
    ("	// smooth towards the target (fast, but never a pop) and merge into the locomotion pose\n	if (!bCombatPoseInit) { CombatPose = *Guard; bCombatPoseInit = true; }\n	const float K = 1.f - FMath::Exp(-16.f * Dt);\n	CombatPose = FIVPoseAngles::Lerp(CombatPose, Target, K);",
     """	if (S.posture == iv::Posture::Airborne || S.posture == iv::Posture::Sliding) bLegs = true;
	// smooth towards the target (fast, but never a pop) and merge into the locomotion pose
	if (!bCombatPoseInit) { CombatPose = *Guard; bCombatPoseInit = true; }
	const float K = 1.f - FMath::Exp(-16.f * Dt);
	CombatPose = FIVPoseAngles::Lerp(CombatPose, Target, K);
	if (S.posture == iv::Posture::Airborne)
	{
		// the legs fold up under the jump-jets
		const float Tuck = FMath::Pow(FMath::Sin(FMath::Clamp(S.airProgress, 0.f, 1.f) * 3.14159f), 0.6f);
		for (const TCHAR* N : { TEXT("thigh_l"), TEXT("thigh_r") }) if (FVector* V = CombatPose.Joint.Find(FName(N))) V->X += -42.f * Tuck;
		for (const TCHAR* N : { TEXT("shin_l"), TEXT("shin_r") }) if (FVector* V = CombatPose.Joint.Find(FName(N))) V->X += 66.f * Tuck;
		for (const TCHAR* N : { TEXT("foot_l"), TEXT("foot_r") }) if (FVector* V = CombatPose.Joint.Find(FName(N))) V->X += -24.f * Tuck;
	}"""),
    ("	FHitResult G;\n	FCollisionQueryParams Q(SCENE_QUERY_STAT(IVGround), false, this);\n	const FVector P = GetActorLocation();\n	if (GetWorld()->LineTraceSingleByChannel(G, P + FVector(0, 0, 3000), P - FVector(0, 0, 12000), ECC_WorldStatic, Q))\n	{\n		SetActorLocation(FVector(P.X, P.Y, G.ImpactPoint.Z + 4100.f));\n	}",
     """	FHitResult G;
	FCollisionQueryParams Q(SCENE_QUERY_STAT(IVGround), false, this);
	const FVector P = GetActorLocation();
	const float LiftTarget = (CombatAnim.posture == iv::Posture::Airborne) ? 3400.f * FMath::Sin(3.14159f * FMath::Clamp(CombatAnim.airProgress, 0.f, 1.f)) : 0.f;
	AirLift = FMath::FInterpTo(AirLift, LiftTarget, Dt, 12.f);
	if (GetWorld()->LineTraceSingleByChannel(G, P + FVector(0, 0, 3000), P - FVector(0, 0, 16000), ECC_WorldStatic, Q))
	{
		SetActorLocation(FVector(P.X, P.Y, G.ImpactPoint.Z + 4100.f + AirLift));
	}"""),
    ("	UpdateBladeTrail(Dt);\n	if (IsLocallyControlled() || GetIVCam() != 0)\n	{",
     "	UpdateBladeTrail(Dt);\n	UpdateV5Fx(Dt);\n	if (IsLocallyControlled() || GetIVCam() != 0)\n	{"),
    ("void AIVMechPawn::UpdateBladeTrail(float Dt)\n{",
     """void AIVMechPawn::UpdateV5Fx(float Dt)
{
	Rage = FMath::FInterpTo(Rage, RageTarget, Dt, 2.5f);
	if (HullMID) HullMID->SetScalarParameterValue(TEXT("Rage"), Rage);
	AIVFXManager* FX = AIVFXManager::Get(GetWorld());
	if (!FX) return;
	// jump-jets: two nozzles on the back, exhaust straight down
	if (CombatAnim.posture == iv::Posture::Airborne)
	{
		JetAcc += Dt;
		while (JetAcc > 0.025f)
		{
			JetAcc -= 0.025f;
			const FVector Base = GetActorLocation() - FVector(0, 0, 2400.f) - GetActorForwardVector() * 700.f;
			for (int32 s = -1; s <= 1; s += 2) FX->SpawnJet(Base + GetActorRightVector() * (450.f * s), FVector(0.f, 0.f, -1.f), 2, 5200.f, 700.f);
		}
		if (JetAcc < 0.f) JetAcc = 0.f;
	}
	// the charge of a lunge: the blade burns hot and the joints vent
	if (CombatAnim.lungeCharge01 > 0.f)
	{
		SetSwordHeat(0.8f + 1.6f * CombatAnim.lungeCharge01);
		LungeFxAcc += Dt;
		if (LungeFxAcc > 0.12f)
		{
			LungeFxAcc = 0.f;
			FX->SpawnSparks(GetZoneWorldLocation(iv::Zone::ArmR), FVector::UpVector, 3 + int32(8 * CombatAnim.lungeCharge01), 2600.f);
		}
	}
	else if (CombatAnim.kind == iv::StrikeKind::Lunge && CombatAnim.phase == iv::Phase::Strike)
	{
		FVector B, T; GetBladeSegment(B, T);
		FX->SpawnSparks(T, -GetActorForwardVector(), 6, 5000.f);
	}
	// an overloaded mech smokes and sparks while it waits for the power
	if (CombatAnim.posture == iv::Posture::Overloaded)
	{
		LungeFxAcc += Dt;
		if (LungeFxAcc > 0.2f)
		{
			LungeFxAcc = 0.f;
			FX->SpawnSmoke(GetZoneWorldLocation(iv::Zone::Torso), 600.f, 2, 0.8f);
			FX->SpawnSparks(GetZoneWorldLocation(iv::Zone::Reactor), FVector::UpVector, 5, 3500.f);
		}
	}
}

void AIVMechPawn::PlayBerserkSwing(iv::SwingSide Side)
{
	const FString Sd = SideName(Side);
	PlaySequence({ FName(*FString::Printf(TEXT("swing_%s_r_windup"), *Sd)), FName(*FString::Printf(TEXT("swing_%s_r_commit"), *Sd)),
		FName(*FString::Printf(TEXT("swing_%s_r_strike_end"), *Sd)), FName(TEXT("grab_clamp")) }, { 0.28f, 0.1f, 0.18f, 0.5f });
}

void AIVMechPawn::StartCounterPunch(AIVMechPawn* Victim)
{
	PlaySequence({ FName(TEXT("quick_piston_r_windup")), FName(TEXT("quick_piston_r_strike")), FName(TEXT("quick_piston_r_strike")), FName(TEXT("guard_neutral")) }, { 0.45f, 0.14f, 0.5f, 0.9f });
	AddVelocityImpulse(GetActorForwardVector() * 1500.f);   // a short run-up
	if (Victim)
	{
		Victim->PlaySequence({ FName(TEXT("knockdown_fall")), FName(TEXT("knockdown_down")), FName(TEXT("knockdown_down")), FName(TEXT("kneel")) }, { 0.45f, 1.2f, 1.6f, 2.f });
		TWeakObjectPtr<AIVMechPawn> V(Victim);
		FTimerHandle H;
		GetWorld()->GetTimerManager().SetTimer(H, FTimerDelegate::CreateLambda([V]()
		{
			if (!V.IsValid()) return;
			if (AIVFXManager* FX = AIVFXManager::Get(V->GetWorld())) FX->SpawnExplosion(V->GetZoneWorldLocation(iv::Zone::Torso), 1.1f);
			V->AddCockpitImpulse(0.f, 1.f, 2.f);
			V->AddVelocityImpulse(-V->GetActorForwardVector() * 1800.f);
		}), 0.55f, false);
	}
}

void AIVMechPawn::StartLockPose(bool bOn)
{
	if (bOn) PlaySequence({ FName(TEXT("block_up")), FName(TEXT("block_up")) }, { 0.2f, 6.f });
	else PlaySequence({ FName(TEXT("guard_neutral")) }, { 0.4f });
}

void AIVMechPawn::UpdateBladeTrail(float Dt)
{"""),
])

# hull material: Rage
M = r"F:\IVUnreal\Scripts\build_materials.py"
s = open(M, encoding="utf-8").read()
s = s.replace('accamt = scalar(m, "AccentAmount", 1.0, -1500, 980)', 'accamt = scalar(m, "AccentAmount", 1.0, -1500, 980)\n    rage = scalar(m, "Rage", 0.0, -1500, 1080)', 1)
s = s.replace('names = ["UVA", "UVB", "VC", "VCA", "Tint", "Accent", "Glow", "Wear", "Damage", "AccAmt"]', 'names = ["UVA", "UVB", "VC", "VCA", "Tint", "Accent", "Glow", "Wear", "Damage", "AccAmt", "Rage"]', 1)
s = s.replace('(wear, ""), (dmg, ""), (accamt, "")]\n    common = """', '(wear, ""), (dmg, ""), (accamt, ""), (rage, "")]\n    common = """', 1)
s = s.replace('return Glow * (em * (0.7 + 0.3 * n) + ember * 0.5);"', 'return Glow * (em * (0.7 + 0.3 * n) + ember * 0.5) * (1.0 + Rage * 2.2) + float3(1.0, 0.08, 0.02) * Rage * (edge * 6.0 + 0.6 * smoothstep(0.55, 0.9, n));"', 1)
open(M, "w", encoding="utf-8").write(s)
print("pawn v5 ok")

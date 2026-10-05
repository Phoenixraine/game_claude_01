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


# ============================================================================================ header
h, c = rd("IVCombat.h")
if "BoardIn[2]" not in h:
    h = rep(h, "	bool bBoard = false, bBoardSwing = false;", "	bool bBoard = false, bBoardSwing = false;\n	bool bBoardSwat = false;           // the DEFENDER's button: slap the shoulder the enemy pilot sits on (human defenders only)")
    h = rep(h, """	const iv::Boarding& GetBoarding() const { return Board; }
	bool IsBoardingActive() const { return Board.Active(); }
	float GetBoardingCooldown01() const { return Board.cooldownLeft() > 0 ? 1.f - FMath::Clamp(float(Board.cooldownLeft()) / float(iv::tune::kBoardCooldownTicks), 0.f, 1.f) : 1.f; }""",
            """	/** Boarding is symmetric: Board[s] is the boarding OWNED by side s (its pilot leaves s's cockpit and climbs onto the other mech). */
	const iv::Boarding& GetBoarding(iv::Side S = iv::Side::A) const { return Board[iv::Index(S)]; }
	bool IsBoardingActive(iv::Side S = iv::Side::A) const { return Board[iv::Index(S)].Active(); }
	/** True while an enemy pilot sits on S's mech (S is the defender). */
	bool IsBoardedBy(iv::Side Victim) const { return Board[iv::Index(iv::Other(Victim))].Active(); }
	float GetBoardingCooldown01(iv::Side S = iv::Side::A) const { const iv::Boarding& B = Board[iv::Index(S)]; return B.cooldownLeft() > 0 ? 1.f - FMath::Clamp(float(B.cooldownLeft()) / float(iv::tune::kBoardCooldownTicks), 0.f, 1.f) : 1.f; }
	/** Ultimate gauge multiplier of a fighter right now (comeback: grows as its hull integrity falls). */
	float GetUltimateMultiplier(iv::Side S) const;""")
    h = rep(h, """	iv::Boarding Board;
	iv::BoardingInput BoardIn;
	TWeakObjectPtr<AIVPilotFigure> Pilot;
	bool bBoardCamOn = false;
	FVector BoardCamFrom = FVector::ZeroVector, BoardCamAt = FVector::ZeroVector;
	float BoardBlastFlash = 0.f;
	void UpdateBoardingPresentation(float Dt);""",
            """	iv::Boarding Board[2];
	iv::BoardingInput BoardIn[2];
	TWeakObjectPtr<AIVPilotFigure> Pilot[2];
	bool bBoardCamOn[2] = { false, false };
	FVector BoardCamFrom[2] = { FVector::ZeroVector, FVector::ZeroVector }, BoardCamAt[2] = { FVector::ZeroVector, FVector::ZeroVector };
	bool bVictimCamOn[2] = { false, false };
	FVector VictimCamFrom[2] = { FVector::ZeroVector, FVector::ZeroVector }, VictimCamAt[2] = { FVector::ZeroVector, FVector::ZeroVector };
	float BoardBlastFlash = 0.f;
	bool IsHuman(iv::Side S) const { return S == iv::Side::A ? !PlayerBot.IsValid() : bHumanB; }
	void UpdateBoardingPresentation(float Dt, iv::Side Owner);
	void UpdateVictimCam(float Dt, iv::Side Owner);
	void HandleUltimateEvent(const iv::Event& Ev);""")
    wr("IVCombat.h", h, c)

# ============================================================================================ source
d, c = rd("IVCombat.cpp")
if "BoardIn[0]" not in d:
    # --- Restart
    a = d.index("	{\n		iv::BoardingConfig Bc;")
    b = d.index("	UGameplayStatics::SetGlobalTimeDilation(this, 1.f);\n	ScoopCooldown[0]", a)
    d = d[:a] + """	for (int32 s = 0; s < 2; ++s)
	{
		const iv::Side Owner = s == 0 ? iv::Side::A : iv::Side::B;
		iv::BoardingConfig Bc;
		Bc.owner = Owner;
		Bc.ownerIsAi = !IsHuman(Owner);
		Bc.enemyIsHuman = IsHuman(iv::Other(Owner));      // a person defends by slapping his own shoulder; the AI by its own random swats
		Bc.enemyArchetype = BotStyle;
		Bc.enemyDifficulty = BotLevel;
		Bc.seed = BotSeed + 3 + s;
		Board[s] = iv::Boarding(Bc);
		BoardIn[s] = iv::BoardingInput();
		if (AIVPilotFigure* PF = Pilot[s].Get()) PF->Hide();
		if (AIVMechPawn* Pw = PawnOf(Owner)) Pw->SetBoardCam(false, FVector::ZeroVector, FVector::ZeroVector, 60.f);
		bBoardCamOn[s] = bVictimCamOn[s] = false;
	}
""" + d[b:]
    # --- StepOnce input
    old = d[d.index("	if (PlayerIn.bBoard) BoardIn.start = true;"):d.index("	iv::World W;\n	W.proximity[0]")]
    new = """	auto FeedBoard = [&](FIVCombatInput& In, iv::BoardingInput& Bi)
	{
		if (In.bBoard) Bi.start = true;
		if (In.bBoardSwing) Bi.swing = true;
		if (In.HackDx) Bi.hack.dx = In.HackDx;
		if (In.HackDy) Bi.hack.dy = In.HackDy;
		if (In.bHackConfirm) Bi.hack.confirm = true;
		if (In.bHackBack) Bi.hack.back = true;
		if (In.bHackAux) Bi.hack.aux = true;
	};
	FeedBoard(PlayerIn, BoardIn[0]);
	if (bHumanB) FeedBoard(PlayerIn2, BoardIn[1]);
	// the defender's slap button goes to the boarding that sits on his mech
	if (PlayerIn2.bBoardSwat && bHumanB) BoardIn[0].swat = true;
	if (PlayerIn.bBoardSwat) BoardIn[1].swat = true;
	if (PlayerBot.IsValid()) { A = PlayerBot->Decide(iv::MakeObservation(*Duel, iv::Side::A)); P->SetMoveIntent(FVector2D(0.f, float(A.move))); }
	A = Board[0].Filter(*Duel, A);
	iv::Input B = bHumanB ? BuildInput(PlayerIn2, bFirstOfFrame) : Bot->Decide(iv::MakeObservation(*Duel, iv::Side::B));
	B = Board[1].Filter(*Duel, B);
"""
    d = d.replace(old, new, 1)
    d = rep(d, "	Duel->Step(A, B, W);\n	Board.Step(*Duel, BoardIn);\n	BoardIn = iv::BoardingInput();", "	Duel->Step(A, B, W);\n	Board[0].Step(*Duel, BoardIn[0]);\n	Board[1].Step(*Duel, BoardIn[1]);\n	BoardIn[0] = iv::BoardingInput();\n	BoardIn[1] = iv::BoardingInput();")
    d = rep(d, "		PlayerIn.bBoard = PlayerIn.bBoardSwing = PlayerIn.bHackConfirm = PlayerIn.bHackBack = PlayerIn.bHackAux = false;\n		PlayerIn.HackDx = PlayerIn.HackDy = 0;",
            "		PlayerIn.bBoard = PlayerIn.bBoardSwing = PlayerIn.bHackConfirm = PlayerIn.bHackBack = PlayerIn.bHackAux = PlayerIn.bBoardSwat = false;\n		PlayerIn.HackDx = PlayerIn.HackDy = 0;\n		PlayerIn2.bBoard = PlayerIn2.bBoardSwing = PlayerIn2.bHackConfirm = PlayerIn2.bHackBack = PlayerIn2.bHackAux = PlayerIn2.bBoardSwat = false;\n		PlayerIn2.HackDx = PlayerIn2.HackDy = 0;")
    d = rep(d, "	UpdateBoardingPresentation(Dt);\n	Anim[1] = iv::MakeAnimState(Duel->fighter(iv::Side::B));", "	for (int32 s = 0; s < 2; ++s) { UpdateBoardingPresentation(Dt, s == 0 ? iv::Side::A : iv::Side::B); UpdateVictimCam(Dt, s == 0 ? iv::Side::A : iv::Side::B); }\n	Anim[1] = iv::MakeAnimState(Duel->fighter(iv::Side::B));")
    # --- boarding events: owner-relative
    d = rep(d, """	AIVMechPawn* P = Player.Get();
	AIVMechPawn* E = Enemy.Get();
	UWorld* W = GetWorld();
	if (!P || !E) return;
	AIVPlayerController* Pc = P ? Cast<AIVPlayerController>(P->GetController()) : nullptr;""",
            """	AIVMechPawn* P = PawnOf(Ev.actor);                    // the pilot's own mech (the boarding owner)
	AIVMechPawn* E = PawnOf(iv::Other(Ev.actor));         // the mech being boarded
	UWorld* W = GetWorld();
	if (!P || !E) return;
	AIVPlayerController* Pc = P ? Cast<AIVPlayerController>(P->GetController()) : nullptr;
	AIVPlayerController* Ec = Cast<AIVPlayerController>(E->GetController());   // the defender""")
    d = rep(d, "		if (Ev.type == EventType::BoardingSwatTelegraph) Pc->Rumble(0.5f, 0.3f);", "		if (Ev.type == EventType::BoardingSwatTelegraph) Pc->Rumble(0.5f, 0.3f);")
    d = rep(d, "	switch (Ev.type)\n	{\n	case EventType::BoardingStarted:\n		IVAudio::Play2D(W, TEXT(\"cockpit_alarm_warning\"), 0.8f);",
            "	if (Ec)\n	{\n		if (Ev.type == EventType::BoardingStarted) { Ec->Rumble(0.8f, 0.5f); Ec->ShowAlert(TEXT(\"ВАС ВЗЯЛИ НА АБОРДАЖ!\"), 3.5f); }\n		else if (Ev.type == EventType::BoardingSwatImpact) Ec->Rumble(0.7f, 0.4f);\n	}\n	switch (Ev.type)\n	{\n	case EventType::BoardingStarted:\n		IVAudio::Play2D(W, TEXT(\"cockpit_alarm_warning\"), 0.8f);\n		if (Ec) IVAudio::Play2D(W, TEXT(\"cockpit_alarm_critical\"), 1.f);")
    wr("IVCombat.cpp", d, c)
print("director core part patched")

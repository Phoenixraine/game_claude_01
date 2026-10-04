"""UE combat director: v5 inputs, second human (split-screen), v5 event presentation."""
H = r"F:\IVUnreal\Source\ImpactVector\IVCombat.h"
C = r"F:\IVUnreal\Source\ImpactVector\IVCombat.cpp"


def patch(path, edits):
    s = open(path, encoding="utf-8").read()
    for a, b in edits:
        assert a in s, (path, a[:90])
        s = s.replace(a, b, 1)
    open(path, "w", encoding="utf-8").write(s)


patch(H, [
    ("	bool bQuick = false, bCancel = false, bGrab = false, bSwitchArm = false, bReverse = false, bDodge = false, bUltimate = false, bSetPriority = false;\n};",
     """	bool bQuick = false, bCancel = false, bGrab = false, bSwitchArm = false, bReverse = false, bDodge = false, bUltimate = false, bSetPriority = false;
	// v5
	bool bLungeHeld = false;
	bool bJump = false, bChop = false, bSlide = false, bMash = false, bBerserk = false, bQte = false;
};"""),
    ("	FIVCombatInput PlayerIn;\n",
     """	FIVCombatInput PlayerIn;
	FIVCombatInput PlayerIn2;         // side B when a second human plays (split screen)
	bool bHumanB = false;
	void SetHumanB(bool b);
	FIVCombatInput& InputOf(iv::Side S) { return S == iv::Side::A ? PlayerIn : PlayerIn2; }
	/** Below-deck repair: the mech runs on autopilot while the pilot is away. */
	void SetAutopilot(iv::Side S, bool bOn);
	void RepairBreakdown(iv::Side S, int32 Levels);
	float GetLungeCharge01(iv::Side S) const { return Anim[iv::Index(S)].lungeCharge01; }
"""),
])

patch(C, [
    ("		I.priority = P.Priority;\n		if (bEdges)\n		{",
     """		I.priority = P.Priority;
		I.lungeHeld = P.bLungeHeld;
		if (bEdges)
		{
			I.jump = P.bJump; I.chop = P.bChop; I.slide = P.bSlide; I.mash = P.bMash; I.berserk = P.bBerserk; I.qte = P.bQte;"""),
    # director: human B
    ("	const iv::Input B = Bot->Decide(iv::MakeObservation(*Duel, iv::Side::B));\n	iv::World W;",
     "	const iv::Input B = bHumanB ? BuildInput(PlayerIn2, bFirstOfFrame) : Bot->Decide(iv::MakeObservation(*Duel, iv::Side::B));\n	iv::World W;"),
    ("		PlayerIn.bQuick = PlayerIn.bCancel = PlayerIn.bGrab = PlayerIn.bSwitchArm = PlayerIn.bReverse = PlayerIn.bDodge = PlayerIn.bUltimate = PlayerIn.bSetPriority = false;\n",
     """		PlayerIn.bQuick = PlayerIn.bCancel = PlayerIn.bGrab = PlayerIn.bSwitchArm = PlayerIn.bReverse = PlayerIn.bDodge = PlayerIn.bUltimate = PlayerIn.bSetPriority = false;
		PlayerIn.bJump = PlayerIn.bChop = PlayerIn.bSlide = PlayerIn.bMash = PlayerIn.bBerserk = PlayerIn.bQte = false;
		PlayerIn2.bQuick = PlayerIn2.bCancel = PlayerIn2.bGrab = PlayerIn2.bSwitchArm = PlayerIn2.bReverse = PlayerIn2.bDodge = PlayerIn2.bUltimate = PlayerIn2.bSetPriority = false;
		PlayerIn2.bJump = PlayerIn2.bChop = PlayerIn2.bSlide = PlayerIn2.bMash = PlayerIn2.bBerserk = PlayerIn2.bQte = false;
"""),
    ("	// the enemy walks as its AI wants (the core's own distance integration is overridden every tick)\n	E->SetMoveIntent(FVector2D(0.f, float(B.move)));",
     "	// the enemy walks as its AI wants (the core's own distance integration is overridden every tick)\n	if (!bHumanB) E->SetMoveIntent(FVector2D(0.f, float(B.move)));"),
    ("	PlayerIn = FIVCombatInput();\n	UGameplayStatics::SetGlobalTimeDilation(this, 1.f);",
     "	PlayerIn = FIVCombatInput();\n	PlayerIn2 = FIVCombatInput();\n	UGameplayStatics::SetGlobalTimeDilation(this, 1.f);"),
    ("	Duel = MakeUnique<iv::Duel>(BotSeed, true);\n	Bot = MakeUnique<iv::Ai>(BotStyle, BotLevel, BotSeed + 7);",
     """	Duel = MakeUnique<iv::Duel>(BotSeed, true);
	Bot = MakeUnique<iv::Ai>(BotStyle, BotLevel, BotSeed + 7);
	Duel->SetAiLevel(iv::Side::B, bHumanB ? -1 : static_cast<int>(BotLevel));
	Duel->SetAiLevel(iv::Side::A, PlayerBot.IsValid() ? static_cast<int>(BotLevel) : -1);"""),
    ("void AIVCombatDirector::EnableAutoPlayer(iv::Archetype Style, iv::Difficulty Level)\n{\n	PlayerBot = MakeUnique<iv::Ai>(Style, Level, BotSeed + 99);\n}",
     """void AIVCombatDirector::EnableAutoPlayer(iv::Archetype Style, iv::Difficulty Level)
{
	PlayerBot = MakeUnique<iv::Ai>(Style, Level, BotSeed + 99);
	if (Duel.IsValid()) Duel->SetAiLevel(iv::Side::A, static_cast<int>(Level));
}

void AIVCombatDirector::SetHumanB(bool b)
{
	bHumanB = b;
	if (Duel.IsValid()) Duel->SetAiLevel(iv::Side::B, b ? -1 : static_cast<int>(BotLevel));
	if (Enemy.IsValid()) Enemy->SetExternalControl(true);
}

void AIVCombatDirector::SetAutopilot(iv::Side S, bool bOn)
{
	if (Duel.IsValid()) Duel->fighter(S).set_autopilot(bOn);
}

void AIVCombatDirector::RepairBreakdown(iv::Side S, int32 Levels)
{
	if (!Duel.IsValid()) return;
	Duel->RepairBreakdown(S, Levels);
}"""),
])
print("combat a ok")

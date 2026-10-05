import io
SRC = r"F:\IVUnreal\Source\ImpactVector"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new):
    assert old in t, old[:90]
    return t.replace(old, new, 1)


h, c = rd("IVPlayerController.h")
if "AlertLeft" not in h:
    h = rep(h, "	void Rumble(float Strength, float Seconds);", "	void Rumble(float Strength, float Seconds);\n	/** A big banner on this player's HUD (\"you are being boarded\"). */\n	void ShowAlert(const FString& Text, float Seconds) { AlertText = Text; AlertLeft = Seconds; }\n	FString AlertText;\n	float AlertLeft = 0.f;\n	bool bScriptLoaded = false;")
    wr("IVPlayerController.h", h, c)

p, c = rd("IVPlayerController.cpp")
if "bScriptLoaded" not in p:
    a = p.index("	{\n		FString S;\n		if (FParse::Value(FCommandLine::Get(), TEXT(\"-IVScript=\"), S, false))")
    b = p.index("	SetInputMode(FInputModeGameOnly());", a)
    p = p[:a] + p[b:]
    p = rep(p, "	if (ScriptCmd.Num() == 0) return;\n	ScriptTime += Dt;",
            """	if (!bScriptLoaded)
	{
		// each player has his own script: -IVScript= for side A, -IVScript2= for side B (the second pilot of a versus duel)
		bScriptLoaded = true;
		FString S;
		if (FParse::Value(FCommandLine::Get(), MySide == iv::Side::B ? TEXT("-IVScript2=") : TEXT("-IVScript="), S, false))
		{
			TArray<FString> Items;
			S.ParseIntoArray(Items, TEXT(";"));
			for (const FString& It : Items)
			{
				FString L, R;
				if (!It.Split(TEXT("@"), &L, &R)) continue;
				FScriptCmd Cm; Cm.T = FCString::Atof(*R);
				if (!L.Split(TEXT("="), &Cm.Name, &Cm.Arg)) Cm.Name = L;
				ScriptCmd.Add(Cm);
			}
		}
	}
	if (AlertLeft > 0.f) AlertLeft -= Dt;
	if (ScriptCmd.Num() == 0) return;
	ScriptTime += Dt;""")
    p = rep(p, "		FIVCombatInput* In = Dir ? &Dir->PlayerIn : nullptr;", "		FIVCombatInput* In = Dir ? &Dir->InputOf(MySide) : nullptr;")
    p = rep(p, '		else if (In && C.Name == TEXT("board")) In->bBoard = true;', '		else if (In && C.Name == TEXT("board")) In->bBoard = true;\n		else if (In && C.Name == TEXT("swat")) In->bBoardSwat = true;\n		else if (In && C.Name == TEXT("swing")) In->bBoardSwing = true;')
    p = rep(p, "	if (Dir->GetBoarding().Active())\n	{", "	if (Dir->IsBoardedBy(MySide) && (WasInputKeyJustPressed(EKeys::T) || WasInputKeyJustPressed(EKeys::Gamepad_DPad_Down))) In.bBoardSwat = true;   // the defender slaps his own shoulder\n	if (Dir->GetBoarding(MySide).Active())\n	{")
    p = rep(p, "		if (Dir->GetBoarding().phase() == iv::BoardPhase::Hacking)", "		if (Dir->GetBoarding(MySide).phase() == iv::BoardPhase::Hacking)")
    p = rep(p, "				const iv::HackInput Pi = Dir->GetBoarding().hack().PerfectInput();", "				const iv::HackInput Pi = Dir->GetBoarding(MySide).hack().PerfectInput();")
    wr("IVPlayerController.cpp", p, c)
print("pc patched")

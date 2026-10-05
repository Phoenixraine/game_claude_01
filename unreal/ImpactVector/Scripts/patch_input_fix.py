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
if "SideFromDrawn" not in h:
    h = rep(h, "	static iv::SwingSide SideFromStick(const FVector2D& S);", "	static iv::SwingSide SideFromStick(const FVector2D& S);\n	/** The stroke the player DREW (mouse / stick, +Y = up) -> the sector of the cut: a cut drawn downwards is an overhead chop (side Up), drawn to the right\n	 *  it comes from the left (side Left), and so on. The same mapping is used for the guard, so a block is drawn along the enemy's cut. */\n	static iv::SwingSide SideFromDrawn(const FVector2D& S);\n	void OnLookEnd(const FInputActionValue& V) { LookStick = FVector2D::ZeroVector; }")
    wr("IVPlayerController.h", h, c)

p, c = rd("IVPlayerController.cpp")
if "SideFromDrawn" not in p:
    p = rep(p, "iv::Zone AIVPlayerController::ZoneFromStick(const FVector2D& S)\n{", """iv::SwingSide AIVPlayerController::SideFromDrawn(const FVector2D& S)
{
	if (FMath::Abs(S.Y) >= FMath::Abs(S.X)) return S.Y >= 0.f ? iv::SwingSide::Down : iv::SwingSide::Up;      // drawn up = a rising cut, drawn down = an overhead chop
	return S.X >= 0.f ? iv::SwingSide::Left : iv::SwingSide::Right;                                           // drawn right = the cut sweeps to the right (starts on the left)
}

iv::Zone AIVPlayerController::ZoneFromStick(const FVector2D& S)
{""")
    # mouse detection: a mouse never moves the gamepad axes. Small mouse deltas (< 1 count) used to be taken for the pad stick -> the camera drifted and no stroke was drawn.
    p = rep(p, "	const bool bMouse = FMath::Abs(L.X) > 1.001f || FMath::Abs(L.Y) > 1.001f;", "	const bool bMouse = FMath::Abs(GetInputAnalogKeyState(EKeys::Gamepad_RightX)) < 0.02f && FMath::Abs(GetInputAnalogKeyState(EKeys::Gamepad_RightY)) < 0.02f;   // no stick deflection = the mouse")
    p = rep(p, "		EIC->BindAction(LookAction, ETriggerEvent::Triggered, this, &AIVPlayerController::OnLook);", "		EIC->BindAction(LookAction, ETriggerEvent::Triggered, this, &AIVPlayerController::OnLook);\n		EIC->BindAction(LookAction, ETriggerEvent::Completed, this, &AIVPlayerController::OnLookEnd);")
    p = rep(p, "		if (!bSideLocked && Stick.Size() > 0.5f) { CurSide = SideFromStick(Stick); bSideLocked = true; }", "		if (!bSideLocked && Stick.Size() > 0.35f) { CurSide = SideFromDrawn(Stick); bSideLocked = true; }")
    p = rep(p, "	if (bJustReleased && StrikeHeldTime <= 0.18f)", "	if (bJustReleased && StrikeHeldTime <= 0.22f)")
    p = rep(p, "	In.bStrikeHeld = bStrikeDown && StrikeHeldTime > 0.18f;", "	In.bStrikeHeld = bStrikeDown && StrikeHeldTime > 0.22f;")
    p = rep(p, "	if (bGuardDown && Stick.Size() > 0.4f) CurGuardSide = SideFromStick(Stick);", "	if (bGuardDown && Stick.Size() > 0.3f) CurGuardSide = SideFromDrawn(Stick);")
    wr("IVPlayerController.cpp", p, c)

hd, c = rd("IVHUD.cpp")
if "ВНИЗ\"), TEXT(\"ВПРАВО\"), TEXT(\"ВЛЕВО\"), TEXT(\"ВВЕРХ\")" not in hd:
    hd = rep(hd, "	switch (O.side) { case iv::SwingSide::Up: D = FVector2D(0, -1); break; case iv::SwingSide::Down: D = FVector2D(0, 1); break; case iv::SwingSide::Left: D = FVector2D(-1, 0); break; default: D = FVector2D(1, 0); break; }",
            "	// the block is DRAWN along the enemy's cut: an overhead chop (side Up) is met by a stroke drawn downwards, and so on\n	switch (O.side) { case iv::SwingSide::Up: D = FVector2D(0, 1); break; case iv::SwingSide::Down: D = FVector2D(0, -1); break; case iv::SwingSide::Left: D = FVector2D(1, 0); break; default: D = FVector2D(-1, 0); break; }")
    hd = rep(hd, '	static const TCHAR* Names[4] = { TEXT("ВЕРХ"), TEXT("ВЛЕВО"), TEXT("ВПРАВО"), TEXT("НИЗ") };\n	const FString Msg = bIn ? TEXT("БЛОК СЕЙЧАС!") : FString::Printf(TEXT("УДАР %s — ПКМ + ЧЕРТИ %s"), Names[iv::Index(O.side)], Names[iv::Index(O.side)]);',
            '	static const TCHAR* Names[4] = { TEXT("ВНИЗ"), TEXT("ВПРАВО"), TEXT("ВЛЕВО"), TEXT("ВВЕРХ") };   // by side index: the direction to draw\n	const FString Msg = bIn ? TEXT("БЛОК СЕЙЧАС!") : FString::Printf(TEXT("РУБЯТ — ПКМ И ЧЕРТИ %s"), Names[iv::Index(O.side)]);')
    wr("IVHUD.cpp", hd, c)

# tutorial: the quick-strike step must put the dummy inside the fist's reach (22 units; the old placement of 26 made every jab whiff)
f, c = rd("IVFlow.cpp")
old = "	if (S.Goal != ETutGoal::Walk && Dir->GetDuel() && Dir->GetDuel()->distance() > 40.f) PlaceMechs(26.f);"
if old in f:
    f = rep(f, old, "	if (S.Goal == ETutGoal::QuickHit && Dir->GetDuel() && Dir->GetDuel()->distance() > 18.f) PlaceMechs(13.f);\n	else if (S.Goal != ETutGoal::Walk && Dir->GetDuel() && Dir->GetDuel()->distance() > 40.f) PlaceMechs(26.f);")
    wr("IVFlow.cpp", f, c)
print("input fix patched")

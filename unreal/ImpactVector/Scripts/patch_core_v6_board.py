import io
SRC = r"F:\IVRepo\core"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new):
    assert old in t, old[:80]
    return t.replace(old, new, 1)


t, c = rd("include/iv/Tuning.h")
if "kBoardStunTicks" not in t:
    t = rep(t, "constexpr int kMaxSwatsPerBoarding = 2;", "constexpr int kMaxSwatsPerBoarding = 2;\n// v6: a human defender slaps his own shoulder by hand. The slap is slow (a readable telegraph); a caught pilot lies stunned on the shoulder, his\n// empty mech is dead weight (no defence, no movement, takes extra damage), then he gets up and goes back to the cockpit.\nconstexpr int kHumanSwatWindupTicks = MsToTicks(1100);\nconstexpr int kHumanMaxSwats = 3;\nconstexpr int kBoardStunTicks = MsToTicks(5000);")
    wr("include/iv/Tuning.h", t, c)

h, c = rd("include/iv/Boarding.h")
if "Stunned" not in h:
    h = rep(h, "ReturnHook, ClimbIn, Smashed, Done, HookSwing };", "ReturnHook, ClimbIn, Smashed, Done, HookSwing, Stunned };")
    h = rep(h, "enum class BoardingOutcome : uint8_t { None, Success, HackFailed, HackTimeout, Smashed, Aborted };", "enum class BoardingOutcome : uint8_t { None, Success, HackFailed, HackTimeout, Smashed, Aborted, Slapped };")
    h = rep(h, "  bool swing = false;          // edge: leap to the other shoulder (only works inside the window after a swat telegraph)", "  bool swing = false;          // edge: leap to the other shoulder (only works inside the window after a swat telegraph)\n  bool swat = false;           // v6 edge, from the DEFENDER (cfg.enemyIsHuman): slap the shoulder the pilot sits on")
    h = rep(h, "  float swatChanceMult = 1.f;", "  bool enemyIsHuman = false;                           // v6: the defender is a person: no random swats, he slaps by pressing `swat`\n  bool lethalSwat = false;                             // v4 behaviour: a caught pilot is crushed and the match ends (v6 default: stunned for 5 s)\n  float swatChanceMult = 1.f;")
    wr("include/iv/Boarding.h", h, c)

b, c = rd("src/Boarding.cpp")
if "void Boarding::Slap" not in b:
    b = rep(b, '"Escape", "WatchBlast", "ReturnHook", "ClimbIn", "Smashed", "Done", "HookSwing"};', '"Escape", "WatchBlast", "ReturnHook", "ClimbIn", "Smashed", "Done", "HookSwing", "Stunned"};')
    # autopilot: while stunned the empty mech does nothing at all
    b = rep(b, "  if (!Active()) return playerInput;\n  Input in = auto_.Decide(MakeObservation(duel, cfg_.owner));",
            "  if (!Active()) return playerInput;\n  if (phase_ == BoardPhase::Stunned) return Input();   // v6: the pilot lies on the shoulder: the mech is dead weight\n  Input in = auto_.Decide(MakeObservation(duel, cfg_.owner));")
    # swat start for a human defender
    b = rep(b, "  if (!swat_.active) {\n    if (swatsDone_ >= tune::kMaxSwatsPerBoarding || swatCooldown_ > 0 || !SwatEligible()) return;",
            """  if (!swat_.active && cfg_.enemyIsHuman) {
    if (!in.swat || swatsDone_ >= tune::kHumanMaxSwats || swatCooldown_ > 0 || !SwatEligible()) return;
    if (foe.posture != Posture::Standing || Gone(foe.body.state(ArmZone(Other(shoulder_))))) return;
    swat_.active = true;
    swat_.shoulder = shoulder_;
    swat_.total = tune::kHumanSwatWindupTicks;
    swat_.ticksToImpact = swat_.total;
    swat_.adjusted = 0;
    ++swatsDone_;
    Emit(d, EventType::BoardingSwatTelegraph, ShoulderIdx(shoulder_), swat_.ticksToImpact, static_cast<float>(swatsDone_ - 1));
    return;
  }
  if (!swat_.active) {
    if (swatsDone_ >= tune::kMaxSwatsPerBoarding || swatCooldown_ > 0 || !SwatEligible()) return;""")
    # impact: stun instead of kill
    b = rep(b, "  if (onIt) Smash(d);\n}", "  if (onIt) {\n    if (cfg_.lethalSwat) Smash(d);\n    else Slap(d);\n  }\n}")
    b = rep(b, "void Boarding::Smash(Duel& d) {", """// v6: the caught pilot lies stunned on the shoulder; the empty mech is helpless for kBoardStunTicks, then he returns along the hook.
void Boarding::Slap(Duel& d) {
  Emit(d, EventType::BoardingSmashed, ShoulderIdx(shoulder_), 1);   // b = 1: non-lethal
  swat_ = Swat();
  ghostTicks_ = -1;
  hack_ = HackGame();
  outcome_ = BoardingOutcome::Slapped;
  Enter(d, BoardPhase::Stunned, tune::kBoardStunTicks);
}

void Boarding::Smash(Duel& d) {""")
    # phases: Stunned -> ReturnHook
    b = rep(b, "    case BoardPhase::ReturnHook:\n      if (done) Enter(d, BoardPhase::ClimbIn, tune::kBoardClimbInTicks);\n      break;",
            "    case BoardPhase::Stunned:\n      if (done) Enter(d, BoardPhase::ReturnHook, tune::kBoardReturnHookTicks);\n      break;\n    case BoardPhase::ReturnHook:\n      if (done) Enter(d, BoardPhase::ClimbIn, tune::kBoardClimbInTicks);\n      break;")
    # no hack input / swat processing while stunned: StepSwat is harmless (swat_ inactive, human needs eligibility); keep shoulder checks off
    b = rep(b, "    default: break;   // swinging, or the hatch is already open and the grenade is on its way: nothing to retarget", "    default: break;   // swinging, stunned, or the hatch is already open and the grenade is on its way: nothing to retarget")
    wr("src/Boarding.cpp", b, c)
    h, c = rd("include/iv/Boarding.h")
    h = rep(h, "  void Smash(Duel& d);", "  void Smash(Duel& d);\n  void Slap(Duel& d);")
    wr("include/iv/Boarding.h", h, c)

# existing tests keep the lethal behaviour
tb, c = rd("tests/test_boarding.cpp")
if "lethalSwat" not in tb:
    import re
    tb = tb.replace("BoardingConfig c;", "BoardingConfig c;\n    c.lethalSwat = true;   // the v4 rules these tests describe", 2)
    wr("tests/test_boarding.cpp", tb, c)
print("boarding v6 patched")

import io
T = r"F:\IVRepo\core\tests"


def rd(n):
    s = io.open(T + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(T + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new):
    assert old in t, old[:80]
    return t.replace(old, new, 1)


s, c = rd("test_v2.cpp")
if "RunUltWind" not in s:
    s = rep(s, "void FillUltimate(Fighter& f) { f.ultimate = tune::kUltimateMax; }", "void FillUltimate(Fighter& f) { f.ultimate = tune::kUltimateMax; }\n// v6: the button starts a windup punch; this runs it to the contact (nobody countered)\nvoid RunUltWind(Rig& r) { r.Step(tune::kUltWindupTicks); }")
    a = s.index("IV_TEST(Ultimate, GainsComeFromSkillMoreThanFromSuffering)")
    b = s.index("IV_TEST(Ultimate, ButtonDoesNothingWithAnEmptyGauge)")
    s = s[:a] + """IV_TEST(Ultimate, OnlyCountersChargeTheGaugeAndTheyChargeItMoreWhenHurt) {
  IV_CHECK(tune::kUltGainIntercept >= tune::kUltGainParry);
  IV_CHECK_EQ(tune::kUltGainHit, 0.f);                      // v6: plain hits do not charge it
  IV_CHECK(tune::kUltGainUltCounter > tune::kUltGainParry);
  // comeback: the same gain is bigger for a fighter with less hull integrity
  Rig r(1, 12.f);
  StepContext ctx;
  ctx.log = &r.duel.log();
  r.A().GainUltimate(10.f, ctx);
  const float healthy = r.A().ultimate;
  IV_CHECK_NEAR(healthy, 10.f, 1e-3f);
  while (r.B().body.Integrity() > 0.4f) r.B().TakeHit(Zone::Torso, 30.f, StrikeKind::Heavy, 0.f, ctx);
  r.B().GainUltimate(10.f, ctx);
  IV_CHECK(r.B().ultimate > healthy * 1.3f);
  IV_CHECK(r.B().ultimate <= 10.f * tune::kUltComebackMax + 1e-3f);
  // a landed plain hit gives the attacker nothing
  Rig q(1, 12.f);
  q.StartHeavyA(SwingSide::Up, Zone::Torso);
  q.StepUntil([&] { return q.Count(EventType::StrikeContact) > 0; });
  IV_CHECK_EQ(q.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));
  IV_CHECK_EQ(q.A().ultimate, 0.f);
  IV_CHECK_EQ(q.B().ultimate, 0.f);
}

""" + s[b:]
    s = rep(s, "  r.a.ultimate = true;\n  r.a.target = Zone::Torso;\n  r.Step();\n  IV_CHECK_EQ(r.Count(EventType::UltimateUsed), 1);",
            "  r.a.ultimate = true;\n  r.a.target = Zone::Torso;\n  r.Step();\n  IV_CHECK_EQ(r.Count(EventType::UltimateStarted), 1);   // v6: the punch comes first\n  IV_CHECK_EQ(r.A().ultimate, 0.f);\n  IV_CHECK(!r.duel.cinematic().active);\n  RunUltWind(r);\n  IV_CHECK_EQ(r.Count(EventType::UltimateUsed), 1);")
    s = rep(s, "  r.a.ultimate = true;\n  r.Step();\n  const Tick t0", "  r.a.ultimate = true;\n  r.Step();\n  RunUltWind(r);\n  const Tick t0")
    s = rep(s, "  r.a.ultimate = true;\n  r.Step();\n  r.Step(tune::kUltimateCinematicTicks + 2);", "  r.a.ultimate = true;\n  r.Step();\n  RunUltWind(r);\n  r.Step(tune::kUltimateCinematicTicks + 2);")
    s = rep(s, "  q.Step();\n  const int endIdx", "  q.Step();\n  RunUltWind(q);\n  const int endIdx")
    wr("test_v2.cpp", s, c)

s, c = rd("test_v3.cpp")
if "kUltWindupTicks" not in s:
    s = rep(s, "    r.a.target = Zone::Head;\n    r.Step();\n    IV_CHECK(r.duel.cinematic().kind == CinematicKind::UltimateSever);", "    r.a.target = Zone::Head;\n    r.Step();\n    r.Step(tune::kUltWindupTicks);\n    IV_CHECK(r.duel.cinematic().kind == CinematicKind::UltimateSever);")
    s += """

// ---------------------------------------------------------------- v6: countering the ultimate
namespace {
// A starts the ultimate; returns once the windup is `leftTicks` away from contact.
void StartUltAndWait(Rig& r, int leftTicks) {
  r.A().ultimate = tune::kUltimateMax;
  r.a.ultimate = true;
  r.a.target = Zone::Torso;
  r.Step();
  r.Step(tune::kUltWindupTicks - leftTicks - 1);
}
}  // namespace

IV_TEST(UltimateCounter, FreshLowGuardInTheTinyWindowCancelsTheUltimateAndChargesTheDefender) {
  Rig r(1, 20.f);
  StartUltAndWait(r, 3);
  IV_CHECK_EQ(r.Count(EventType::UltimateStarted), 1);
  IV_CHECK(r.A().ultWind > 0);
  r.b.guardHeld = true;
  r.b.guardSide = SwingSide::Down;
  r.Step(4);
  IV_CHECK_EQ(r.Count(EventType::UltimateCountered), 1);
  IV_CHECK_EQ(r.Count(EventType::UltimateUsed), 0);
  IV_CHECK(!r.duel.cinematic().active);
  IV_CHECK(!r.B().body.severed(Zone::ArmL));
  IV_CHECK(r.B().ultimate >= tune::kUltGainUltCounter - 1e-3f);
  IV_CHECK_EQ(r.A().ultimate, 0.f);                       // the attacker lost the gauge
  IV_CHECK(r.A().res.stability < 100.f);
  IV_CHECK(r.B().counterTicks > 0 || r.A().phase == Phase::Recovery);
}

IV_TEST(UltimateCounter, WrongSideTooEarlyOrAlreadyHeldDoesNotCounter) {
  {   // a high guard
    Rig r(1, 20.f);
    StartUltAndWait(r, 3);
    r.b.guardHeld = true;
    r.b.guardSide = SwingSide::Up;
    r.Step(4);
    IV_CHECK_EQ(r.Count(EventType::UltimateCountered), 0);
    IV_CHECK_EQ(r.Count(EventType::UltimateUsed), 1);
  }
  {   // pressed too early (outside the tiny window)
    Rig r(1, 20.f);
    StartUltAndWait(r, tune::kUltWindupTicks / 2);
    r.b.guardHeld = true;
    r.b.guardSide = SwingSide::Down;
    r.Step(tune::kUltWindupTicks);
    IV_CHECK_EQ(r.Count(EventType::UltimateCountered), 0);
    IV_CHECK_EQ(r.Count(EventType::UltimateUsed), 1);
  }
}

IV_TEST(UltimateCounter, TheWindowIsMuchSmallerThanTheParryWindow) {
  IV_CHECK(tune::kUltCounterWindowTicks < tune::kParryWindowTicks);
  IV_CHECK(tune::kUltCounterWindowTicks >= 3);
}
"""
    wr("test_v3.cpp", s, c)
print("tests patched")

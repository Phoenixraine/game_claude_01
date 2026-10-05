import io, re
SRC = r"F:\IVRepo\core"


def rd(n):
    s = io.open(SRC + "\\" + n, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), ("\r\n" in s)


def wr(n, s, crlf):
    io.open(SRC + "\\" + n, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)


def rep(t, old, new, cnt=1):
    assert old in t, old[:80]
    return t.replace(old, new, cnt)


# ---------------------------------------------------------------- Tuning
t, c = rd("include/iv/Tuning.h")
if "kUltWindupTicks" not in t:
    t = rep(t, "constexpr float kUltGainParry = 6.f;                   // successful parry (the parrying fighter)",
            "constexpr float kUltGainParry = 14.f;                  // successful parry (the parrying fighter)")
    t = rep(t, "constexpr float kUltGainIntercept = 8.f;               // successful intercept (the interceptor)",
            "constexpr float kUltGainIntercept = 16.f;              // successful intercept (the interceptor)")
    t = rep(t, "constexpr float kUltGainCriticalHit = 1.5f;              // landing a hit on a zone that is Critical or worse",
            "constexpr float kUltGainCriticalHit = 0.f;              // v6: plain hits no longer charge the gauge, only counters do")
    t = rep(t, "constexpr float kUltGainHit = 0.45f;                     // any landed hit", "constexpr float kUltGainHit = 0.f;                        // any landed hit (v6: 0)")
    t = rep(t, "constexpr float kUltGainTakenPerDamage = 0.02f;         // receiving damage (small, capped per hit)", "constexpr float kUltGainTakenPerDamage = 0.f;            // receiving damage (v6: 0)")
    t = rep(t, "constexpr float kUltGainTakenCap = 0.3f;", "constexpr float kUltGainTakenCap = 0.f;")
    t = rep(t, "constexpr float kUltGainClash = 3.f;", "constexpr float kUltGainClash = 4.f;")
    t = rep(t, "constexpr float kUltimateStabilityHit = 70.f;", """constexpr float kUltimateStabilityHit = 70.f;
// v6 (owner's rules, 2026-10-05): the ultimate starts with a punch under the chest that can be countered in a tiny window; a successful
// counter cancels it. The gauge is charged by counters only (parry, intercept, a counter strike that lands, countering the ultimate itself),
// multiplied by a comeback factor that grows as the fighter's hull integrity falls.
constexpr int kUltWindupTicks = MsToTicks(800);        // the punch is coming: the defender may counter it near the end of this time
constexpr int kUltCounterWindowTicks = 6;              // 100 ms: much tighter than kParryWindowTicks. The guard must be pressed afresh, low (SwingSide::Down)
constexpr float kUltGainCounterHit = 12.f;             // a counter strike (inner line after a parry / intercept) that lands
constexpr float kUltGainUltCounter = 30.f;             // countering the ultimate itself
constexpr float kUltComebackMax = 2.5f;                // gauge multiplier at zero integrity (1.0 at full integrity)
constexpr float kUltCounterStability = 30.f;           // the cancelled attacker loses its tempo
constexpr float kAiUltCounterChance[kDifficultyCount] = {0.1f, 0.3f, 0.55f};""")
    wr("include/iv/Tuning.h", t, c)

# ---------------------------------------------------------------- Events (appended at the very end of the enum)
e, c = rd("include/iv/Events.h")
if "UltimateStarted" not in e:
    # find the last enumerator line before the closing brace of EventType
    m = re.search(r"enum class EventType[^{]*\{(.*?)\n\};", e, re.S)
    assert m, "EventType enum"
    body_end = m.end() - 3          # position of "\n};"
    e = e[:body_end] + "\n  // ---- v6: ultimate with a counter window, boarding defence. Appended. ----\n  UltimateStarted,        // actor: attacker, zone: target, a: windup ticks, b: counter window ticks - the punch under the chest begins\n  UltimateCountered,      // actor: the defender who countered, value: 1 - the ultimate is cancelled\n  UltimateCancelled,      // actor: attacker: the windup was broken (stagger / knock-down)" + e[body_end:]
    wr("include/iv/Events.h", e, c)

# ---------------------------------------------------------------- Fighter
f, c = rd("include/iv/Fighter.h")
if "ultWind" not in f:
    f = rep(f, "  bool ultimatePending = false; // the ultimate button was accepted this tick; Duel resolves it", "  bool ultimatePending = false; // the ultimate button was accepted this tick; Duel resolves it\n  int ultWind = 0;              // v6: ticks left of the ultimate's windup punch (0 = none)\n  int ultWindLen = 0;")
    wr("include/iv/Fighter.h", f, c)
fc, c = rd("src/Fighter.cpp")
if "ultWind" not in fc:
    fc = rep(fc, "  ultimate = 0.f;\n  ultimatePending = false;\n  protectedTicks = 0;", "  ultimate = 0.f;\n  ultimatePending = false;\n  ultWind = ultWindLen = 0;\n  protectedTicks = 0;")
    fc = rep(fc, "  if (amount <= 0.f) return;\n  const bool was = UltimateReady();", "  if (amount <= 0.f) return;\n  // comeback: the less hull integrity is left, the faster the gauge fills\n  amount *= 1.f + (tune::kUltComebackMax - 1.f) * (1.f - std::min(1.f, std::max(0.f, body.Integrity())));\n  const bool was = UltimateReady();")
    wr("src/Fighter.cpp", fc, c)

# ---------------------------------------------------------------- Anim
a, c = rd("include/iv/Anim.h")
if "ultWindTicks" not in a:
    a = rep(a, "  float ultimate01 = 0.f;\n", "  float ultimate01 = 0.f;\n  int ultWindTicks = 0;                 // v6: ticks left of the ultimate's punch (0 = none)\n  int ultWindLen = 0;\n")
    wr("include/iv/Anim.h", a, c)
ac, c = rd("src/Anim.cpp")
if "ultWindTicks" not in ac:
    ac = rep(ac, "  a.ultimate01 = Unit(f.ultimate / tune::kUltimateMax);", "  a.ultimate01 = Unit(f.ultimate / tune::kUltimateMax);\n  a.ultWindTicks = f.ultWind;\n  a.ultWindLen = f.ultWindLen;")
    wr("src/Anim.cpp", ac, c)

# ---------------------------------------------------------------- Duel
dh, c = rd("include/iv/Duel.h")
if "StartUltimate" not in dh:
    dh = rep(dh, "  void ResolveUltimate(int ai, const World& w);", "  void ResolveUltimate(int ai, const World& w);\n  void StartUltimate(int ai, const World& w);\n  void StepUltimateWind(int ai, const World& w);")
    wr("include/iv/Duel.h", dh, c)
d, c = rd("src/Duel.cpp")
if "Duel::StartUltimate" not in d:
    d = rep(d, "    for (int i = 0; i < 2; ++i)\n      if (f_[i].ultimatePending && !cinematic_.active) ResolveUltimate(i, world);",
            "    for (int i = 0; i < 2; ++i)\n      if (f_[i].ultimatePending && f_[i].ultWind == 0 && !cinematic_.active) StartUltimate(i, world);\n    for (int i = 0; i < 2; ++i)\n      if (f_[i].ultWind > 0 && !cinematic_.active) StepUltimateWind(i, world);")
    # counter strike gain
    d = rep(d, "      if (hr.dealt > 0.f) {\n        GainUltimate(ai, tune::kUltGainHit + (hr.after >= ZoneState::Critical ? tune::kUltGainCriticalHit : 0.f), w);\n      }\n      break;",
            "      if (hr.dealt > 0.f) {\n        GainUltimate(ai, tune::kUltGainHit + (hr.after >= ZoneState::Critical ? tune::kUltGainCriticalHit : 0.f), w);\n        if (atk.strike.innerLine) GainUltimate(ai, tune::kUltGainCounterHit, w);   // v6: a counter that lands charges the gauge\n      }\n      break;")
    d = rep(d, "void Duel::ResolveUltimate(int ai, const World& w) {", '''// v6: the button starts a windup (a punch under the chest). The gauge is spent at once; the defender may counter near the end of it.
void Duel::StartUltimate(int ai, const World& w) {
  Fighter& atk = f_[ai];
  (void)w;
  Zone z = atk.ultimateTarget;
  atk.ConsumeUltimate();
  atk.ultWind = atk.ultWindLen = tune::kUltWindupTicks;
  atk.phase = Phase::Recovery;   // locked while the punch comes (the attacker cannot start anything else)
  atk.phaseTicks = 0;
  atk.recoveryLen = tune::kUltWindupTicks + 2;
  Emit(EventType::UltimateStarted, atk.side(), z, tune::kUltWindupTicks, tune::kUltCounterWindowTicks);
}

void Duel::StepUltimateWind(int ai, const World& w) {
  Fighter& atk = f_[ai];
  Fighter& def = f_[1 - ai];
  if (atk.posture != Posture::Standing) {   // staggered / knocked down mid-punch: the ultimate is lost
    atk.ultWind = 0;
    Emit(EventType::UltimateCancelled, atk.side(), Zone::Torso);
    return;
  }
  if (--atk.ultWind > 0) return;
  // contact: a fresh low guard pressed inside the tiny window cancels it
  const Modifiers& dm = def.body.modifiers();
  const bool hasArm = dm.arm[0].blockStrength > 0.f || dm.arm[1].blockStrength > 0.f;
  const bool counter = def.GuardReady() && !def.guard.hard && hasArm && def.guard.side == SwingSide::Down && tick_ - def.guard.pressTick < tune::kUltCounterWindowTicks;
  if (counter) {
    const StepContext actx = Ctx(ai, w);
    Emit(EventType::UltimateCountered, def.side(), Zone::Torso, 1);
    atk.LoseStability(tune::kUltCounterStability, actx);
    atk.phase = Phase::Recovery;
    atk.phaseTicks = 0;
    atk.recoveryLen = tune::kHeavyRecoveryTicks;
    def.res.Spend(tune::kParryEnergy);
    GainUltimate(1 - ai, tune::kUltGainUltCounter, w);
    def.counterTicks = tune::kCounterWindowTicks;
    return;
  }
  atk.ultimatePending = true;   // not countered: the cinematic follows
  ResolveUltimate(ai, w);
}

void Duel::ResolveUltimate(int ai, const World& w) {''')
    wr("src/Duel.cpp", d, c)

# ---------------------------------------------------------------- AI
ah, c = rd("include/iv/Ai.h")
if "ultTicksLeft" not in ah:
    ah = rep(ah, "  bool chargeSound = false;             // pitch §8", "  int ultTicksLeft = -1;                // v6: ticks left of the opponent's ultimate punch (-1 = none)\n  bool chargeSound = false;             // pitch §8")
    ah = rep(ah, "  bool grabAnswered_ = false;", "  bool grabAnswered_ = false;\n  bool ultReact_ = false;\n  bool ultCounter_ = false;")
    wr("include/iv/Ai.h", ah, c)
ap, c = rd("src/Ai.cpp")
if "ultTicksLeft" not in ap:
    ap = rep(ap, "  v.chargeSound = op.phase == Phase::Windup", "  v.ultTicksLeft = op.ultWind > 0 ? op.ultWind : -1;\n  v.chargeSound = op.phase == Phase::Windup")
    ap = rep(ap, "  h = Mix(h, static_cast<uint64_t>(v.guardSide));", "  h = Mix(h, static_cast<uint64_t>(v.guardSide));\n  h = Mix(h, static_cast<uint64_t>(v.ultTicksLeft + 1));")
    ap = rep(ap, "bool Ai::Defend(const OppView& seen, const Observation& cur, Input* in) {\n  const SelfView& self = cur.self;\n",
            """bool Ai::Defend(const OppView& seen, const Observation& cur, Input* in) {
  const SelfView& self = cur.self;
  // v6: the opponent's ultimate punch. Some pilots read it and answer with a fresh low guard right before it lands.
  if (seen.ultTicksLeft >= 0) {
    if (!ultReact_) {
      ultReact_ = true;
      ultCounter_ = Roll() < tune::kAiUltCounterChance[static_cast<int>(difficulty_)];
    }
    if (ultCounter_) {
      const int eta = seen.ultTicksLeft - delay_;
      in->guardSide = SwingSide::Down;
      in->guardHeld = eta <= tune::kUltCounterWindowTicks / 2 + parryJitter_ / 2;   // released until then so the press is fresh
      return true;
    }
  } else {
    ultReact_ = false;
  }
""")
    wr("src/Ai.cpp", ap, c)
print("core v6 ult patched")

"""Core v5, part C: Duel.h / Duel.cpp hooks (the state machines live in the new Special.cpp)."""
H = r"F:\IVRepo\core\include\iv\Duel.h"
C = r"F:\IVRepo\core\src\Duel.cpp"


def patch(path, edits):
    s = open(path, encoding="utf-8").read()
    for a, b in edits:
        assert a in s, (path, a[:90])
        s = s.replace(a, b, 1)
    open(path, "w", encoding="utf-8").write(s)


patch(H, [
    ("class Duel {\n public:",
     """// v5: the blades locked after a blocked lunge: both sides mash the button, the leader strikes the other.
struct LockState {
  bool active = false;
  Side attacker = Side::A;   // the one who rushed
  int kind = 0;              // 0 plain block, 1 parry, 2 hard stance
  int ticks = 0;
  float score[2] = {0.f, 0.f};
};

// v5: berserk: the attacker holds the foe; each blow needs a timing press, the foe must parry every one.
enum class BerserkStage : uint8_t { Prompt, Swing };
struct BerserkState {
  bool active = false;
  Side who = Side::A;
  BerserkStage stage = BerserkStage::Prompt;
  int round = 0;
  int ticks = 0;
  int stageTicks = 0;
  SwingSide side = SwingSide::Up;
  float quality = 0.f;
  Tick swingStart = 0;
};

class Duel {
 public:"""),
    ("  EventLog& log() { return log_; }\n  const EventLog& log() const { return log_; }\n",
     """  EventLog& log() { return log_; }
  const EventLog& log() const { return log_; }
  // v5. aiLevel: -1 = a human (all presses come from the Input), 0..2 = Duel plays the lock mashing, the berserk parries and the repairs by itself.
  void SetAiLevel(Side s, int aiLevel) { aiLevel_[Index(s)] = aiLevel; }
  int ai_level(Side s) const { return aiLevel_[Index(s)]; }
  const LockState& lock() const { return lock_; }
  const BerserkState& berserk() const { return berserk_; }
  void RepairBreakdown(Side s, int levels);
"""),
    ("    Zone zone = Zone::Torso;\n    float raw = 0.f;\n  };",
     "    Zone zone = Zone::Torso;\n    float raw = 0.f;\n    int lockKind = 0;\n  };"),
    ("  void EmitHit(const Fighter& def,",
     """  // v5 (Special.cpp)
  void StartLock(int atk, int kind);
  void StepLock(const Input* const* in);
  void ResolveLock();
  bool TryStartBerserk(int who);
  void StepBerserk(const Input* const* in);
  void EndBerserk(bool overload, int reason);
  void BerserkPrompt();
  void EmitHit(const Fighter& def,"""),
    ("  int timeLimit_ = 0;\n};", """  int timeLimit_ = 0;
  int aiLevel_[2] = {-1, -1};
  LockState lock_;
  BerserkState berserk_;
  bool gpHeld_[2] = {false, false};
  SwingSide gpSide_[2] = {SwingSide::Up, SwingSide::Up};
  Tick gpTick_[2] = {-100000, -100000};
};"""),
])

patch(C, [
    ("  clinch_ = ClinchState();\n  cinematic_ = CinematicState();",
     "  clinch_ = ClinchState();\n  lock_ = LockState();\n  berserk_ = BerserkState();\n  gpHeld_[0] = gpHeld_[1] = false;\n  gpTick_[0] = gpTick_[1] = -100000;\n  cinematic_ = CinematicState();"),
    ("  for (int i = 0; i < 2; ++i) f_[i].Step(*in[i], Ctx(i, world));\n",
     """  for (int i = 0; i < 2; ++i)   // v5: the berserk grab
    if (in[i]->berserk) TryStartBerserk(i);
  for (int i = 0; i < 2; ++i) {   // v5: raw guard presses (the berserk parry reads them)
    if (in[i]->guardHeld && (!gpHeld_[i] || in[i]->guardSide != gpSide_[i])) gpTick_[i] = tick_;
    gpHeld_[i] = in[i]->guardHeld;
    gpSide_[i] = in[i]->guardSide;
  }
  for (int i = 0; i < 2; ++i) f_[i].Step(*in[i], Ctx(i, world));
  for (int i = 0; i < 2; ++i) {   // v5: an AI mech repairs its own breakdown after a while
    if (aiLevel_[i] >= 0 && f_[i].breakdown > 0 && f_[i].breakdownAge >= tune::kBreakdownAiRepairTicks) f_[i].RepairBreakdown(1, Ctx(i, world));
  }
"""),
    ("  if (clinch_.active) {\n    if (++clinch_.ticks >= tune::kClinchTicks) ResolveClinch(world);\n  } else {",
     """  if (lock_.active) {
    StepLock(in);
  } else if (berserk_.active) {
    StepBerserk(in);
  } else if (clinch_.active) {
    if (++clinch_.ticks >= tune::kClinchTicks) ResolveClinch(world);
  } else {"""),
    # decide
    ("  const bool grab = s.kind == StrikeKind::Grab;\n",
     """  const bool grab = s.kind == StrikeKind::Grab;
  const bool lunge = s.kind == StrikeKind::Lunge;
  const bool chop = s.kind == StrikeKind::AirChop;
  const bool special = lunge || chop;
  // v5: the jetpack jump goes over the rush, the slide goes under the aerial chop; neither can be dodged sideways
  if (lunge && def.JumpEvading()) {
    d.outcome = Outcome::Jumped;
    return d;
  }
  if (chop && def.SlideEvading()) {
    d.outcome = Outcome::Slid;
    return d;
  }
"""),
    ("  if (!grab && def.phase == Phase::Strike && def.strike.kind != StrikeKind::Grab && def.strike.strikeTick >= 1 &&",
     "  if (!grab && !special && def.phase == Phase::Strike && def.strike.kind != StrikeKind::Grab && def.strike.kind != StrikeKind::Lunge && def.strike.strikeTick >= 1 &&"),
    ("  if (!grab && def.Evading() && IsLateralSwing(s.side)) {",
     "  if (!grab && !special && def.Evading() && IsLateralSwing(s.side)) {"),
    ("  const Modifiers& dm = def.body.modifiers();\n  const bool defHasArm = dm.arm[0].blockStrength > 0.f || dm.arm[1].blockStrength > 0.f;",
     """  const Modifiers& dm = def.body.modifiers();
  const bool defHasArm = dm.arm[0].blockStrength > 0.f || dm.arm[1].blockStrength > 0.f;
  if (lunge) {   // v5: any lateral guard stops the rush: the blades lock. A late press still counts as a parry.
    if (def.GuardReady() && !def.guard.hard && defHasArm && IsLateralSwing(def.guard.side) && tick_ - def.guard.pressTick < tune::kParryWindowTicks) {
      d.outcome = Outcome::Locked;
      d.lockKind = 1;
      return d;
    }
    if (def.HardStanceActive() && def.posture == Posture::Standing) {
      d.outcome = Outcome::Locked;
      d.lockKind = 2;
      return d;
    }
    if (def.GuardReady() && def.guard.age >= tune::kBlockRaiseTicks && IsLateralSwing(def.guard.side) && defHasArm) {
      d.outcome = Outcome::Locked;
      d.lockKind = 0;
      return d;
    }
    d.outcome = Outcome::Hit;
    return d;
  }"""),
    # apply
    ("    case Outcome::Clashed:   // resolved by ApplyClash before Apply is reached; listed so -Werror=switch passes on gcc\n      break;",
     """    case Outcome::Clashed:   // resolved by ApplyClash before Apply is reached; listed so -Werror=switch passes on gcc
      break;
    case Outcome::Jumped:
      Emit(EventType::JumpEvadedLunge, ds, d.zone, 1);
      atk.LoseStability(tune::kLungeWhiffStability, actx);
      break;
    case Outcome::Slid:
      Emit(EventType::SlideEvadedChop, ds, d.zone);
      atk.LoseStability(tune::kChopWhiffStability, actx);
      def.counterTicks = tune::kCounterWindowTicks;
      break;
    case Outcome::Locked:
      StartLock(ai, d.lockKind);
      break;"""),
    ("      const float stab = kind == StrikeKind::Quick ? tune::kQuickStabilityHit : d.raw * tune::kHitStabilityFactor;",
     "      const float stab = kind == StrikeKind::Quick ? tune::kQuickStabilityHit : (kind == StrikeKind::Lunge ? tune::kLungeStabilityHit : (kind == StrikeKind::AirChop ? tune::kAirChopStabilityHit : d.raw * tune::kHitStabilityFactor));"),
])
print("part C ok")

"""Core v5, part D: the AI answers the lunge / aerial chop and sometimes rushes itself."""
H = r"F:\IVRepo\core\include\iv\Ai.h"
C = r"F:\IVRepo\core\src\Ai.cpp"
T = r"F:\IVRepo\core\include\iv\Tuning.h"


def patch(path, edits):
    s = open(path, encoding="utf-8").read()
    for a, b in edits:
        assert a in s, (path, a[:90])
        s = s.replace(a, b, 1)
    open(path, "w", encoding="utf-8").write(s)


patch(T, [("constexpr int kBreakdownAiRepairTicks = MsToTicks(9000);",
           """constexpr int kBreakdownAiRepairTicks = MsToTicks(9000);
// AI use of the new moves.
constexpr float kAiJumpChance[kDifficultyCount] = {0.12f, 0.35f, 0.65f};     // jumps over a lunge instead of blocking it
constexpr float kAiSlideChance[kDifficultyCount] = {0.15f, 0.40f, 0.70f};    // slides under an aerial chop
constexpr float kAiLungePerTick[kDifficultyCount] = {0.0004f, 0.0007f, 0.0010f};   // chance per free tick to start charging a lunge""")])

patch(H, [("  int moving_ = 0;          // -1 opening, 0 holding, +1 closing (hysteresis state)\n",
           """  int moving_ = 0;          // -1 opening, 0 holding, +1 closing (hysteresis state)
  // v5
  bool lungeJump_ = false;      // decided to jump over the incoming lunge
  bool jumpPressed_ = false;
  bool chopSlide_ = false;      // decided to slide under the incoming aerial chop
  bool chopSlid_ = false;
  int lungeLeft_ = 0;           // ticks of charge still to hold
""")])

patch(C, [
    ("  const bool threat = (seen.phase == Phase::Windup || seen.phase == Phase::Strike) && seen.posture == Posture::Standing;",
     "  const bool threat = (seen.phase == Phase::Windup || seen.phase == Phase::Strike) && (seen.posture == Posture::Standing || seen.posture == Posture::Airborne);"),
    ("""    grabAnswered_ = false;
    reaction_ = Reaction::None;
    return false;
  }""",
     """    grabAnswered_ = false;
    reaction_ = Reaction::None;
    lungeJump_ = jumpPressed_ = chopSlide_ = chopSlid_ = false;
    return false;
  }"""),
    ("  // A grab is a slow, visible reach (pitch §12): hit the grabbing arm before it closes, a block does not help.",
     """  // v5: a charged lunge cannot be sidestepped: block it (the blades lock) or, for good pilots, jump over it at the right moment.
  if (seen.kind == StrikeKind::Lunge && (seen.phase == Phase::Windup || seen.phase == Phase::Strike)) {
    const int di = static_cast<int>(difficulty_);
    if (!reacted_) {
      reacted_ = true;
      lungeJump_ = Roll() < tune::kAiJumpChance[di];
    }
    if (seen.phase == Phase::Strike && lungeJump_ && !jumpPressed_ && seen.strikeTicksLeft >= 0) {
      const int eta = seen.strikeTicksLeft - delay_;
      if (eta <= 22 + parryJitter_ && eta >= 4) {
        in->jump = true;
        jumpPressed_ = true;
      }
    }
    in->guardHeld = !jumpPressed_;
    in->guardSide = (seen.side == SwingSide::Left || seen.side == SwingSide::Right) ? seen.side : SwingSide::Left;
    return true;
  }
  if (seen.kind == StrikeKind::AirChop && seen.phase == Phase::Strike) {
    const int di = static_cast<int>(difficulty_);
    if (!reacted_) {
      reacted_ = true;
      chopSlide_ = Roll() < tune::kAiSlideChance[di];
    }
    if (chopSlide_ && !chopSlid_) {
      in->slide = true;
      chopSlid_ = true;
    } else if (!chopSlide_) {
      in->guardHeld = true;
      in->guardSide = SwingSide::Up;
    }
    return true;
  }
  // A grab is a slow, visible reach (pitch §12): hit the grabbing arm before it closes, a block does not help."""),
    ("  if (self.phase != Phase::Idle) return;\n  const float reach = tune::kHeavyReach + (st.stepIn ? tune::kStepInReachBonus : 0.f) - 4.f;",
     """  if (self.phase != Phase::Idle) { lungeLeft_ = 0; return; }
  // v5: charging / releasing a lunge
  if (lungeLeft_ > 0) {
    in->lungeHeld = true;
    --lungeLeft_;
    return;
  }
  if (cooldown_ == 0 && self.posture == Posture::Standing && cur.distance >= 16.f && cur.distance <= tune::kLungeReach - tune::kLungeRushDistance + 14.f &&
      self.stability > 55.f && self.energy > 45.f && !seen.guardUp && (seen.phase == Phase::Idle || seen.phase == Phase::Recovery) && seen.posture == Posture::Standing) {
    const float mult = archetype_ == Archetype::Breaker ? 2.f : (archetype_ == Archetype::Gunner ? 0.3f : (archetype_ == Archetype::Grappler ? 1.5f : 1.f));
    if (Roll() < tune::kAiLungePerTick[static_cast<int>(difficulty_)] * mult) {
      lungeLeft_ = tune::kLungeChargeTicks + 6 + static_cast<int>(rng_.Below(10));
      in->lungeHeld = true;
      cooldown_ = st.cooldown * 3;
      return;
    }
  }
  const float reach = tune::kHeavyReach + (st.stepIn ? tune::kStepInReachBonus : 0.f) - 4.f;"""),
])
print("part D ok")

"""Core v5, part A: enums, events, tuning, Input/Fighter declarations."""
import re
R = r"F:\IVRepo\core\include\iv"


def patch(path, edits):
    s = open(path, encoding="utf-8").read()
    for a, b in edits:
        assert a in s, (path, a[:80])
        s = s.replace(a, b, 1)
    open(path, "w", encoding="utf-8").write(s)


patch(R + r"\Types.h", [
    ("enum class StrikeKind : uint8_t { Heavy, Quick, Grab };", "// v5: Lunge = the charged horizontal rush (blocked -> sword lock, only a jetpack jump avoids it), AirChop = the overhead chop from the jump.\nenum class StrikeKind : uint8_t { Heavy, Quick, Grab, Lunge, AirChop };"),
    ("enum class Posture : uint8_t { Standing, Staggered, KnockedDown, Dodging, Clinched, ShutDown };",
     "// v5: Airborne = jetpack jump, Sliding = the slide under an aerial chop, Overloaded = powered down after a berserk.\nenum class Posture : uint8_t { Standing, Staggered, KnockedDown, Dodging, Clinched, ShutDown, Airborne, Sliding, Overloaded };"),
])

patch(R + r"\Events.h", [
    ("  BoardingShock,          // the mech was hit while the pilot was outside: value: ticks lost\n};",
     """  BoardingShock,          // the mech was hit while the pilot was outside: value: ticks lost
  // ---- v5: lunge / jump / slide / sword lock / berserk / breakdown (STATUS, owner's ideas of 2026-10-04). Appended. ----
  LungeCharging,          // actor: the rusher started the charge
  JumpStarted,            // actor: jetpack jump
  JumpEvadedLunge,        // actor: the jumper, the rush went under
  AirChopStarted,         // actor: the overhead chop from the air begins
  SlideStarted,           // actor
  SlideEvadedChop,        // actor: the slider
  LockStarted,            // actor: the attacker, a: 0 plain block, 1 parry, 2 hard stance - the blades lock, mash the button
  LockResolved,           // actor: the winner, value: margin of presses, a: 1 if the margin was a landslide
  BerserkStarted,         // actor: the berserker
  BerserkPrompt,          // actor: attacker, a: round (0-based), b: ticks until the perfect press
  BerserkSwing,           // actor: attacker, a: round, b: SwingSide, value: timing quality 0..1
  BerserkParryPrompt,     // actor: defender, a: SwingSide to guard, b: ticks until contact
  BerserkParried,         // actor: defender, a: round
  BerserkPierce,          // actor: attacker, zone, value: damage - the defender missed a parry
  BerserkOverload,        // actor: the berserker is out of power, a: 0 missed press, 1 time over, 2 everything was parried
  CounterPunch,           // actor: the punisher, value: damage
  BerserkEnded,           // actor: berserker, a: 0 pierce, 1 overload
  BreakdownStarted,       // actor: the damaged side, a: level 1..3
  BreakdownTick,          // actor, value: damage dealt
  BreakdownRepaired,      // actor
};"""),
])

patch(R + r"\Tuning.h", [
    ("// ---------------------------------------------------------------- movement (pitch §11)",
     """// ---------------------------------------------------------------- v5: lunge, jump, slide, sword lock, berserk, breakdown
// Lunge: hold the rush button for ~1 s, release: a horizontal rush slash. Only a block (-> sword lock) or a jetpack jump avoids it.
constexpr int kLungeChargeTicks = MsToTicks(1000);
constexpr int kLungeCommitTicks = MsToTicks(120);
constexpr int kLungeStrikeTicks = MsToTicks(480);
constexpr int kLungeRecoveryTicks = MsToTicks(1500);
constexpr float kLungeDamage = 34.f;                      // about two heavy strikes (kHeavyDamage = 17.5)
constexpr float kLungeReach = 46.f;
constexpr float kLungeRushDistance = 26.f;                // gap closed during the rush
constexpr float kLungeEnergy = 18.f;
constexpr float kLungeWhiffStability = 42.f;              // the rusher that is jumped over stumbles
constexpr float kLungeStabilityHit = 30.f;
// Jetpack jump: the only counter to the lunge besides the block; from the air an overhead chop is possible.
constexpr int kJumpAirTicks = MsToTicks(1000);
constexpr int kJumpEvadeFromTicks = MsToTicks(110);
constexpr int kJumpEvadeToTicks = MsToTicks(720);
constexpr float kJumpEnergy = 16.f;
constexpr int kJumpCooldownTicks = MsToTicks(2600);
constexpr int kAirChopMinTicks = MsToTicks(250);
constexpr int kAirChopStrikeTicks = MsToTicks(280);
constexpr int kAirChopRecoveryTicks = MsToTicks(1000);
constexpr float kAirChopDamage = 27.f;
constexpr float kAirChopReach = 34.f;
constexpr float kAirChopStabilityHit = 24.f;
// Slide: ducks under the aerial chop.
constexpr int kSlideTicks = MsToTicks(760);
constexpr int kSlideEvadeTicks = MsToTicks(560);
constexpr float kSlideEnergy = 9.f;
constexpr float kChopWhiffStability = 40.f;
// Sword lock (a blocked lunge): both mash the button; the leader strikes the other.
constexpr int kLockTicks = MsToTicks(3400);
constexpr int kLockMinTicks = MsToTicks(900);
constexpr float kLockLead = 16.f;                          // presses of lead that end the lock early
constexpr float kLockBonusBlock = 2.f;                     // starting points of the defender
constexpr float kLockBonusParry = 6.f;
constexpr float kLockBonusHard = 4.f;
constexpr float kLockWinDamage = 30.f;
constexpr float kLockWinStability = 60.f;
constexpr float kLockArmDamage = 12.f;
constexpr float kLockAiMashPerTick[kDifficultyCount] = {0.10f, 0.14f, 0.17f};
// Berserk: the attacker grabs the foe and strikes with a timing QTE; the foe must parry every blow, a single miss = a piercing blow.
constexpr float kBerserkMinEnergy = 50.f;
constexpr float kBerserkMinStability = 30.f;
constexpr float kBerserkRange = 30.f;
constexpr int kBerserkMaxTicks = MsToTicks(15000);
constexpr int kBerserkRounds = 5;                          // all parried -> overload
constexpr int kBerserkPromptTicks = MsToTicks(1100);       // the ring closes after this long
constexpr int kBerserkPerfectTick = MsToTicks(800);        // best moment to press
constexpr int kBerserkPressWindowTicks = MsToTicks(220);   // +- around the perfect tick
constexpr int kBerserkSwingTicks = MsToTicks(620);         // from the press to the contact
constexpr int kBerserkParryWindowTicks = MsToTicks(520);   // the defender's guard must be (re)pressed this late or later after the swing starts
constexpr int kBerserkParryLeadTicks = MsToTicks(120);     // ...but not earlier than this before the swing starts
constexpr float kBerserkParryEnergy = 6.f;
constexpr float kPierceDamage = 62.f;
constexpr float kPierceStability = 100.f;
constexpr int kBerserkCooldownTicks = MsToTicks(45000);
constexpr int kOverloadTicks = MsToTicks(4200);
constexpr float kCounterPunchDamage = 32.f;
constexpr float kCounterPunchStability = 100.f;
constexpr float kBerserkAiParry[kDifficultyCount] = {0.55f, 0.75f, 0.90f};
// Breakdown (damaged systems keep eating the mech until the pilot goes below deck and repairs them).
constexpr int kBreakdownPeriodTicks = MsToTicks(5000);
constexpr float kBreakdownDamage = 3.5f;                   // per level
constexpr int kBreakdownMaxLevel = 3;
constexpr int kBreakdownAiRepairTicks = MsToTicks(9000);

// ---------------------------------------------------------------- movement (pitch §11)"""),
])

patch(R + r"\Fighter.h", [
    ("  EnergyPriority priority = EnergyPriority::Guard;\n};",
     """  EnergyPriority priority = EnergyPriority::Guard;
  // v5.
  bool lungeHeld = false;             // hold ~1 s, release: the rush slash
  bool jump = false;                  // edge: jetpack jump
  bool chop = false;                  // edge: overhead chop while airborne
  bool slide = false;                 // edge: slide (ducks under an aerial chop)
  bool mash = false;                  // edge: sword lock button mashing
  bool berserk = false;               // edge: start berserk
  bool qte = false;                   // edge: berserk strike confirm
};"""),
    ("  Clashed,      // v3: two blades met on the same line; both strikes stopped\n};",
     "  Clashed,      // v3: two blades met on the same line; both strikes stopped\n  Jumped,       // v5: the lunge went under a jetpack jump\n  Slid,         // v5: the aerial chop was slid under\n  Locked,       // v5: the lunge was blocked: sword lock\n};"),
    ("  void ClashBreak(const StepContext& ctx);\n",
     """  void ClashBreak(const StepContext& ctx);
  // v5
  bool TryJump(const StepContext& ctx);
  bool TrySlide(const StepContext& ctx);
  bool JumpEvading() const { return posture == Posture::Airborne && airTicks >= tune::kJumpEvadeFromTicks && airTicks <= tune::kJumpEvadeToTicks; }
  bool SlideEvading() const { return posture == Posture::Sliding && slideTicks < tune::kSlideEvadeTicks; }
  void EnterOverload(const StepContext& ctx);
  void AddBreakdown(int levels, const StepContext& ctx);
  void RepairBreakdown(int levels, const StepContext& ctx);
"""),
    ("  Tick lastHitTick = -100000;\n",
     """  int airTicks = 0;             // v5: ticks since the jump started
  int slideTicks = 0;           // v5
  int jumpCooldown = 0;         // v5
  int berserkCooldown = 0;      // v5
  int breakdown = 0;            // v5: level 0..3, drains the mech until repaired
  int breakdownAcc = 0;
  int breakdownAge = 0;
  Tick lastHitTick = -100000;
"""),
    ("  void HandleWeapon(const Input& in, const StepContext& ctx);\n",
     "  void HandleWeapon(const Input& in, const StepContext& ctx);\n  void StepAirSlide(const Input& in, const StepContext& ctx);\n"),
])

patch(R + r"\Anim.h", [
    ("  float ultimate01 = 0.f;\n};", "  float ultimate01 = 0.f;\n  // v5\n  float airProgress = 0.f;              // 0..1 of the jetpack jump\n  float slideProgress = 0.f;\n  float lungeCharge01 = 0.f;            // while charging the rush\n  int breakdown = 0;\n};"),
])
print("part A ok")

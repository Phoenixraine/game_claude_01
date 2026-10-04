// v5 rules: the charged lunge, the jetpack jump and aerial chop, the slide, the sword lock, berserk and the breakdown.
#include <cmath>

#include "TestUtil.h"

using namespace ivtest;

namespace {
void ClearV5(Rig& r) {
  r.a.jump = r.a.chop = r.a.slide = r.a.mash = r.a.berserk = r.a.qte = false;
  r.b.jump = r.b.chop = r.b.slide = r.b.mash = r.b.berserk = r.b.qte = false;
}
// A charges the lunge for `hold` ticks, releases and steps until the strike is in flight.
void StartLungeA(Rig& r, int hold = tune::kLungeChargeTicks + 4) {
  r.a.lungeHeld = true;
  r.Step(hold);
  r.a.lungeHeld = false;
  r.StepUntil([&] { return r.A().phase == Phase::Strike; });
}
void StepClear(Rig& r, int n = 1) {
  for (int i = 0; i < n; ++i) {
    r.Step();
    ClearV5(r);
  }
}
}  // namespace

IV_TEST(Lunge, AShortPressDoesNothing) {
  Rig r(1, 20.f);
  r.a.lungeHeld = true;
  r.Step(tune::kLungeChargeTicks / 3);
  r.a.lungeHeld = false;
  r.Step(120);
  IV_CHECK_EQ(r.Count(EventType::LungeCharging), 1);
  IV_CHECK_EQ(r.Count(EventType::Committed), 0);
  IV_CHECK_EQ(r.Count(EventType::StrikeContact), 0);
}

IV_TEST(Lunge, ChargedLungeHitsHardAndLeavesALongRecovery) {
  Rig r(1, 22.f);
  StartLungeA(r);
  IV_CHECK(r.A().strike.kind == StrikeKind::Lunge);
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 200);
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));
  float dealt = 0.f;
  for (const Event& e : r.duel.log().events()) if (e.type == EventType::Hit && e.actor == Side::B) dealt += e.value;
  IV_CHECK(dealt > 1.6f * tune::kHeavyDamage);
  r.Step(5);
  IV_CHECK(r.A().recoveryLen >= tune::kLungeRecoveryTicks / 2);
}

IV_TEST(Lunge, ASidestepCannotAvoidIt) {
  Rig r(1, 22.f);
  StartLungeA(r);
  r.b.dodge = true;
  r.b.dodgeDir = 1;
  r.Step();
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 200);
  IV_CHECK_EQ(r.Count(EventType::Evaded), 0);
  IV_CHECK(r.LastOutcome(Side::A) == static_cast<int>(Outcome::Hit));
}

IV_TEST(Jump, GoesOverTheLungeAndTheRusherStumbles) {
  Rig r(1, 22.f);
  StartLungeA(r);
  const float stabBefore = r.A().res.stability;
  // jump with enough lead time that the evade window is open at the moment of contact
  r.b.jump = true;
  StepClear(r, 1);
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 300);
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Jumped));
  IV_CHECK_EQ(r.Count(EventType::JumpEvadedLunge), 1);
  IV_CHECK(r.A().res.stability < stabBefore - 20.f);
  IV_CHECK_EQ(r.Count(EventType::Hit), 0);
}

IV_TEST(Jump, TooEarlyOrTooLateStillGetsHit) {
  {
    Rig r(1, 22.f);
    r.a.lungeHeld = true;
    r.Step(tune::kLungeChargeTicks / 2);
    r.b.jump = true;                    // jumped while the lunge is still charging: the air time is over before the contact
    StepClear(r, 1);
    r.a.lungeHeld = true;
    r.Step(tune::kLungeChargeTicks / 2 + 4);
    r.a.lungeHeld = false;
    r.Step(400);
    IV_CHECK(r.Count(EventType::Hit) > 0);
  }
  {
    Rig r(1, 22.f);
    StartLungeA(r);
    r.StepUntil([&] { return r.A().TicksToContact() <= 3; }, 100);
    r.b.jump = true;                    // far too late
    StepClear(r, 1);
    r.Step(100);
    IV_CHECK(r.Count(EventType::Hit) > 0);
  }
}

IV_TEST(Jump, NeedsEnergyAndHasACooldown) {
  Rig r(1, 40.f);
  r.b.jump = true;
  StepClear(r, 1);
  IV_CHECK(r.B().posture == Posture::Airborne);
  r.Step(tune::kJumpAirTicks + 10);
  IV_CHECK(r.B().posture == Posture::Standing);
  r.b.jump = true;
  StepClear(r, 1);
  IV_CHECK(r.B().posture == Posture::Standing);   // cooldown
  Rig q(1, 40.f);
  q.B().res.energy = 2.f;
  q.b.jump = true;
  StepClear(q, 1);
  IV_CHECK(q.B().posture == Posture::Standing);   // no fuel
}

IV_TEST(Lock, ABlockedLungeLocksTheBladesAndTheMasherWins) {
  Rig r(1, 22.f);
  r.b.guardHeld = true;
  r.b.guardSide = SwingSide::Left;
  r.Step(tune::kBlockRaiseTicks + 6);
  StartLungeA(r);
  r.StepUntil([&] { return r.duel.lock().active; }, 300);
  IV_CHECK(r.duel.lock().active);
  IV_CHECK_EQ(r.Count(EventType::LockStarted), 1);
  IV_CHECK(r.A().posture == Posture::Clinched && r.B().posture == Posture::Clinched);
  // A mashes every other tick, B does nothing
  for (int i = 0; i < 600 && r.duel.lock().active; ++i) {
    r.a.mash = (i % 2 == 0);
    StepClear(r, 1);
  }
  IV_CHECK(!r.duel.lock().active);
  IV_CHECK_EQ(r.Count(EventType::LockResolved), 1);
  bool aWon = false;
  for (const Event& e : r.duel.log().events()) if (e.type == EventType::LockResolved && e.actor == Side::A) aWon = true;
  IV_CHECK(aWon);
  IV_CHECK(r.Count(EventType::Hit) >= 1);
  IV_CHECK(r.B().res.stability < 60.f);
}

IV_TEST(Lock, TheDefenderCanWinByMashingHarder) {
  Rig r(1, 22.f);
  r.b.guardHeld = true;
  r.b.guardSide = SwingSide::Right;
  r.Step(tune::kBlockRaiseTicks + 6);
  StartLungeA(r);
  r.StepUntil([&] { return r.duel.lock().active; }, 300);
  for (int i = 0; i < 600 && r.duel.lock().active; ++i) {
    r.b.mash = true;
    r.a.mash = (i % 4 == 0);
    StepClear(r, 1);
  }
  bool bWon = false;
  for (const Event& e : r.duel.log().events()) if (e.type == EventType::LockResolved && e.actor == Side::B) bWon = true;
  IV_CHECK(bWon);
}

IV_TEST(Lock, AParryGivesTheDefenderAHeadStart) {
  Rig r(1, 22.f);
  StartLungeA(r);
  r.b.guardHeld = true;                  // pressed just before the contact: a parry
  r.b.guardSide = SwingSide::Left;
  r.StepUntil([&] { return r.A().TicksToContact() <= 4; }, 100);
  r.b.guardSide = SwingSide::Right;
  StepClear(r, 1);
  r.StepUntil([&] { return r.duel.lock().active; }, 100);
  IV_CHECK(r.duel.lock().active);
  IV_CHECK(r.duel.lock().kind == 1 || r.duel.lock().kind == 0);
  IV_CHECK(r.duel.lock().score[1] >= tune::kLockBonusBlock);
}

IV_TEST(Lock, AnAiDefenderMashesByItself) {
  Rig r(1, 22.f);
  r.duel.SetAiLevel(Side::B, 1);
  r.b.guardHeld = true;
  r.b.guardSide = SwingSide::Left;
  r.Step(tune::kBlockRaiseTicks + 6);
  StartLungeA(r);
  r.StepUntil([&] { return r.duel.lock().active; }, 300);
  r.Step(tune::kLockTicks + 10);
  IV_CHECK(!r.duel.lock().active);
  IV_CHECK(r.Count(EventType::LockResolved) == 1);
}

IV_TEST(AirChop, ChopFromTheJumpHitsAndASlideDucksUnderIt) {
  {
    Rig r(1, 22.f);
    r.a.jump = true;
    StepClear(r, tune::kAirChopMinTicks + 4);
    IV_CHECK(r.A().posture == Posture::Airborne);
    r.a.chop = true;
    StepClear(r, 1);
    IV_CHECK_EQ(r.Count(EventType::AirChopStarted), 1);
    r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 200);
    IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));
    IV_CHECK(r.Count(EventType::Hit) >= 1);
  }
  {
    Rig r(1, 22.f);
    r.a.jump = true;
    StepClear(r, tune::kAirChopMinTicks + 4);
    r.a.chop = true;
    StepClear(r, 1);
    r.b.slide = true;
    StepClear(r, 1);
    IV_CHECK(r.B().posture == Posture::Sliding);
    r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 200);
    IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Slid));
    IV_CHECK_EQ(r.Count(EventType::SlideEvadedChop), 1);
  }
}

IV_TEST(AirChop, AGuardOnTheTopSideBlocksTheChop) {
  Rig r(1, 22.f);
  r.b.guardHeld = true;
  r.b.guardSide = SwingSide::Up;
  r.a.jump = true;
  StepClear(r, tune::kAirChopMinTicks + 4);
  r.a.chop = true;
  StepClear(r, 1);
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 200);
  const int o = r.LastOutcome(Side::A);
  IV_CHECK(o == static_cast<int>(Outcome::Blocked) || o == static_cast<int>(Outcome::Parried));
}

// ------------------------------------------------------------------------------------------- berserk

IV_TEST(Berserk, NeedsEnergyRangeAndNoCooldown) {
  Rig far(1, 60.f);
  far.a.berserk = true;
  StepClear(far, 1);
  IV_CHECK(!far.duel.berserk().active);
  Rig weak(1, 15.f);
  weak.A().res.energy = 20.f;
  weak.a.berserk = true;
  StepClear(weak, 1);
  IV_CHECK(!weak.duel.berserk().active);
  Rig ok(1, 15.f);
  ok.a.berserk = true;
  StepClear(ok, 1);
  IV_CHECK(ok.duel.berserk().active);
  IV_CHECK(ok.A().posture == Posture::Clinched && ok.B().posture == Posture::Clinched);
  IV_CHECK(ok.A().protectedTicks > 1000);
  ok.b.berserk = true;    // the foe cannot start one too
  StepClear(ok, 1);
  IV_CHECK(ok.duel.berserk().who == Side::A);
}

namespace {
// Presses the QTE exactly at the perfect tick. Returns after the swing has started.
void PressPerfect(Rig& r, SwingSide side) {
  r.StepUntil([&] { return r.duel.berserk().stageTicks >= tune::kBerserkPerfectTick - 1; }, 400);
  r.a.qte = true;
  r.a.side = side;
  StepClear(r, 1);
}
}  // namespace

IV_TEST(Berserk, AMissedParryIsPierced) {
  Rig r(1, 15.f);
  r.a.berserk = true;
  StepClear(r, 1);
  PressPerfect(r, SwingSide::Left);
  IV_CHECK(r.duel.berserk().stage == BerserkStage::Swing);
  IV_CHECK_EQ(r.Count(EventType::BerserkParryPrompt), 1);
  r.Step(tune::kBerserkSwingTicks + 5);
  IV_CHECK_EQ(r.Count(EventType::BerserkPierce), 1);
  IV_CHECK(!r.duel.berserk().active);
  IV_CHECK(r.B().posture == Posture::Staggered || r.B().posture == Posture::KnockedDown);
  float dealt = 0.f;
  for (const Event& e : r.duel.log().events()) if (e.type == EventType::Hit && e.actor == Side::B) dealt += e.value;
  IV_CHECK(dealt > 3.f * tune::kHeavyDamage);
  IV_CHECK(r.A().berserkCooldown > 0);
}

IV_TEST(Berserk, ACorrectParryOnTimeDefendsEveryBlowButTheLastOverloadsTheAttacker) {
  Rig r(1, 15.f);
  r.a.berserk = true;
  StepClear(r, 1);
  for (int round = 0; round < tune::kBerserkRounds; ++round) {
    IV_CHECK(r.duel.berserk().active);
    IV_CHECK(r.duel.berserk().stage == BerserkStage::Prompt);
    PressPerfect(r, SwingSide::Right);
    r.b.guardHeld = false;
    StepClear(r, 2);
    r.b.guardHeld = true;               // pressed right after the swing starts, on the right side
    r.b.guardSide = SwingSide::Right;
    r.Step(tune::kBerserkSwingTicks + 3);
    r.b.guardHeld = false;
    r.Step(2);
  }
  IV_CHECK_EQ(r.Count(EventType::BerserkParried), tune::kBerserkRounds);
  IV_CHECK_EQ(r.Count(EventType::BerserkPierce), 0);
  IV_CHECK_EQ(r.Count(EventType::BerserkOverload), 1);
  IV_CHECK_EQ(r.Count(EventType::CounterPunch), 1);
  IV_CHECK(r.A().posture == Posture::Overloaded);
  IV_CHECK(r.A().res.energy < 1.f);
  r.Step(tune::kOverloadTicks + 5);
  IV_CHECK(r.A().posture == Posture::Standing);
}

IV_TEST(Berserk, WrongSideOrEarlyGuardDoesNotParry) {
  Rig r(1, 15.f);
  r.a.berserk = true;
  StepClear(r, 1);
  r.b.guardHeld = true;                 // held for ages on the right side: pre-holding does not count
  r.b.guardSide = SwingSide::Right;
  PressPerfect(r, SwingSide::Right);
  r.Step(tune::kBerserkSwingTicks + 3);
  IV_CHECK_EQ(r.Count(EventType::BerserkPierce), 1);
  Rig w(1, 15.f);
  w.a.berserk = true;
  StepClear(w, 1);
  PressPerfect(w, SwingSide::Right);
  StepClear(w, 2);
  w.b.guardHeld = true;
  w.b.guardSide = SwingSide::Left;      // the wrong side
  w.Step(tune::kBerserkSwingTicks + 3);
  IV_CHECK_EQ(w.Count(EventType::BerserkPierce), 1);
}

IV_TEST(Berserk, NoPressMeansOverload) {
  Rig r(1, 15.f);
  r.a.berserk = true;
  StepClear(r, 1);
  r.Step(tune::kBerserkPromptTicks + 60);
  IV_CHECK_EQ(r.Count(EventType::BerserkOverload), 1);
  IV_CHECK(r.A().posture == Posture::Overloaded);
  IV_CHECK(!r.duel.berserk().active);
}

IV_TEST(Berserk, TheBerserkerIsUntouchableAndAnAiFoeParriesByChance) {
  int pierces = 0, parried = 0;
  for (uint64_t seed = 1; seed <= 12; ++seed) {
    Rig r(seed, 15.f);
    r.duel.SetAiLevel(Side::B, 1);
    r.a.berserk = true;
    StepClear(r, 1);
    const float hpBefore = TotalHp(r.A());
    for (int round = 0; round < tune::kBerserkRounds + 1 && r.duel.berserk().active; ++round) {
      PressPerfect(r, SwingSide::Up);
      r.Step(tune::kBerserkSwingTicks + 3);
    }
    pierces += r.Count(EventType::BerserkPierce);
    parried += r.Count(EventType::BerserkParried);
    r.Step(10);
    // only the counter-punch after an overload may hurt the berserker
    if (r.Count(EventType::CounterPunch) == 0) IV_CHECK(TotalHp(r.A()) >= hpBefore - 0.001f);
  }
  IV_CHECK(parried > 0);
  IV_CHECK(pierces > 0);
}

// ------------------------------------------------------------------------------------------ breakdown

IV_TEST(Breakdown, ACriticalZoneStartsADrainThatRepairStops) {
  Rig r(1, 22.f);
  for (int i = 0; i < 12 && r.Count(EventType::BreakdownStarted) == 0; ++i) {
    const HitReport hr = r.duel.ExternalHit(Side::B, Zone::Reactor, 40.f, 0.f, 1);
    (void)hr;
  }
  IV_CHECK(r.Count(EventType::BreakdownStarted) >= 1);
  IV_CHECK(r.B().breakdown >= 1);
  const float hp0 = TotalHp(r.B());
  r.Step(tune::kBreakdownPeriodTicks * 2 + 5);
  IV_CHECK(r.Count(EventType::BreakdownTick) >= 2);
  IV_CHECK(TotalHp(r.B()) < hp0);
  r.duel.RepairBreakdown(Side::B, 3);
  IV_CHECK_EQ(r.B().breakdown, 0);
  IV_CHECK_EQ(r.Count(EventType::BreakdownRepaired), 1);
  const int ticks = r.Count(EventType::BreakdownTick);
  r.Step(tune::kBreakdownPeriodTicks + 5);
  IV_CHECK_EQ(r.Count(EventType::BreakdownTick), ticks);
}

IV_TEST(Breakdown, AnAiMechRepairsItselfAfterAWhile) {
  Rig r(1, 22.f);
  r.duel.SetAiLevel(Side::B, 1);
  for (int i = 0; i < 12 && r.B().breakdown == 0; ++i) r.duel.ExternalHit(Side::B, Zone::Reactor, 40.f, 0.f, 1);
  IV_CHECK(r.B().breakdown >= 1);
  r.Step(tune::kBreakdownAiRepairTicks * 4);
  IV_CHECK_EQ(r.B().breakdown, 0);
}

IV_TEST(Special, TheOldRulesAreUntouchedWithoutTheNewInputs) {
  Rig r(1, 20.f);
  r.StartHeavyA(SwingSide::Up, Zone::Torso);
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 200);
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));
  IV_CHECK_EQ(r.Count(EventType::LockStarted), 0);
  IV_CHECK_EQ(r.Count(EventType::BerserkStarted), 0);
}

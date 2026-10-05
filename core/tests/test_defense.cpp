// Module 4: blocks, hard stance, parry, dodge, interception, reverse chain, clinch (pitch §6, §7).
#include "TestUtil.h"

using namespace iv;
using namespace ivtest;

namespace {

// Puts `who` straight into the last tick of a heavy strike so the next Step resolves its contact.
void ForceStrike(Rig& r, Side who, SwingSide side, Zone target, bool innerLine = false, Arm arm = Arm::R) {
  Fighter& f = r.duel.fighter(who);
  f.phase = Phase::Strike;
  f.strike = StrikeState();
  f.strike.kind = StrikeKind::Heavy;
  f.strike.side = side;
  f.strike.target = target;
  f.strike.arm = arm;
  f.strike.released = true;
  f.strike.strikeLen = 1;
  f.strike.strikeTick = 0;
  f.strike.innerLine = innerLine;
  f.lastArm = arm;
}

float Lost(const Rig& r, Side who) { return TotalHp(Fighter(who)) - TotalHp(r.duel.fighter(who)); }

// Runs A's heavy strike at B and returns B's lost hit points. `setup` is called once the strike is in flight.
template <class Setup>
float StrikeAtB(Rig& r, SwingSide side, Zone target, Setup setup) {
  r.StartHeavyA(side, target);
  setup(r);
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 100);
  return Lost(r, Side::B);
}

}  // namespace

IV_TEST(Defense, BlockOnTheRightSideCutsDamageAndCostsStabilityAndArmLoad) {
  Rig open;
  const float openLoss = StrikeAtB(open, SwingSide::Left, Zone::Torso, [](Rig&) {});
  IV_CHECK_EQ(open.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));

  Rig blk;
  blk.b.guardHeld = true;
  blk.b.guardSide = SwingSide::Left;
  blk.Step(tune::kBlockRaiseTicks + 2);
  const float stab = blk.B().res.stability;
  const float blockLoss = StrikeAtB(blk, SwingSide::Left, Zone::Torso, [](Rig&) {});
  IV_CHECK_EQ(blk.LastOutcome(Side::A), static_cast<int>(Outcome::Blocked));
  IV_CHECK(blockLoss < openLoss * 0.7f);        // pitch §6: strongly reduced...
  IV_CHECK(blockLoss > 0.f);                    // ...but not free
  IV_CHECK(blk.B().res.stability < stab - 5.f); // pitch §6: still costs stability
  IV_CHECK(blk.B().body.layer(Zone::ArmL, Layer::Armor) < tune::kArmorMax[Index(Zone::ArmL)]);  // the blocking arm is loaded
  IV_CHECK_EQ(blk.Count(EventType::Blocked), 1);
}

IV_TEST(Defense, BlockOnTheWrongSideDoesNothing) {
  Rig r;
  r.b.guardHeld = true;
  r.b.guardSide = SwingSide::Right;
  r.Step(tune::kBlockRaiseTicks + 2);
  StrikeAtB(r, SwingSide::Up, Zone::Torso, [](Rig&) {});
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));
}

IV_TEST(Defense, GuardRaisedTooLateIsNotYetABlock) {
  Rig r;
  r.StartHeavyA(SwingSide::Up, Zone::Torso);
  // Raise the guard so that fewer than kBlockRaiseTicks of age exist, but outside the parry window too.
  r.StepUntil([&] { return r.A().TicksToContact() == tune::kParryWindowTicks + 4; });
  r.b.guardHeld = true;
  r.b.guardSide = SwingSide::Up;
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 100);
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));
}

IV_TEST(Defense, PressingLtJustBeforeContactParriesAndOpensACounterWindow) {
  Rig r;
  r.StartHeavyA(SwingSide::Up, Zone::Torso);
  r.StepUntil([&] { return r.A().TicksToContact() == 5; });
  r.b.guardHeld = true;
  r.b.guardSide = SwingSide::Up;
  const float stabA = r.A().res.stability;
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 100);
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Parried));
  IV_CHECK_EQ(r.Count(EventType::ParrySuccess), 1);
  IV_CHECK_NEAR(Lost(r, Side::B), 0.0, 1e-4);                  // no damage taken
  IV_CHECK(r.A().res.stability < stabA - tune::kParryStabilityHit + 1.f);  // the attacker's tempo breaks
  IV_CHECK(r.B().counterTicks > 0);                             // pitch §6: a short counter window opens
  IV_CHECK(r.B().res.stability > 90.f);                         // the parry itself is almost free
}

IV_TEST(Defense, ParryWindowHasTheConfiguredWidth) {
  // Press LT k ticks before contact; the set of k that parry must be the 0..kParryWindowTicks range.
  int parried = 0;
  int widest = -1;
  for (int k = 0; k <= tune::kParryWindowTicks + 6; ++k) {
    Rig r;
    r.StartHeavyA(SwingSide::Up, Zone::Torso);
    r.StepUntil([&] { return r.A().TicksToContact() == k + 1; });
    r.b.guardHeld = true;
    r.b.guardSide = SwingSide::Up;
    r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 100);
    if (r.LastOutcome(Side::A) == static_cast<int>(Outcome::Parried)) {
      ++parried;
      widest = k;
    }
  }
  IV_CHECK_EQ(widest, tune::kParryWindowTicks - 1);  // one tick of the window is used up by the press itself
  IV_CHECK_EQ(parried, tune::kParryWindowTicks);
  IV_CHECK(tune::kParryWindowTicks >= MsToTicks(140) && tune::kParryWindowTicks <= MsToTicks(320)  );  // pitch §6
}

IV_TEST(Defense, ParryOnTheWrongSectorFails) {
  Rig r;
  r.StartHeavyA(SwingSide::Up, Zone::Torso);
  r.StepUntil([&] { return r.A().TicksToContact() == 4; });
  r.b.guardHeld = true;
  r.b.guardSide = SwingSide::Down;
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 100);
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));
}

IV_TEST(Defense, InnerLineCounterIgnoresOrdinaryBlockAndParry) {
  // Same setup twice; only `innerLine` differs (pitch §7 "внутренняя линия").
  for (int inner = 0; inner < 2; ++inner) {
    Rig r;
    r.a.guardHeld = true;
    r.a.guardSide = SwingSide::Up;
    r.Step(tune::kBlockRaiseTicks + 10);
    ForceStrike(r, Side::B, SwingSide::Up, Zone::Torso, inner == 1);
    r.Step();
    IV_CHECK_EQ(r.LastOutcome(Side::B), static_cast<int>(inner == 1 ? Outcome::Hit : Outcome::Blocked));
  }
  for (int inner = 0; inner < 2; ++inner) {  // a guard pressed this very tick parries an ordinary strike, not a counter
    Rig p;
    ForceStrike(p, Side::B, SwingSide::Up, Zone::Torso, inner == 1);
    p.a.guardHeld = true;
    p.a.guardSide = SwingSide::Up;
    p.Step();
    IV_CHECK_EQ(p.LastOutcome(Side::B), static_cast<int>(inner == 1 ? Outcome::Hit : Outcome::Parried));
  }
}

IV_TEST(Defense, CounterStrikeAfterAParryTravelsTheInnerLine) {
  Rig r;
  r.StartHeavyA(SwingSide::Up, Zone::Torso);
  r.StepUntil([&] { return r.A().TicksToContact() == 5; });
  r.b.guardHeld = true;
  r.b.guardSide = SwingSide::Up;
  r.StepUntil([&] { return r.Count(EventType::ParrySuccess) > 0; }, 100);
  r.b.guardHeld = false;
  r.b.quick = true;
  r.b.side = SwingSide::Left;
  r.Step();
  IV_CHECK(r.B().strike.innerLine);
  IV_CHECK(r.B().strike.kind == StrikeKind::Quick);
  IV_CHECK_EQ(r.B().counterTicks, 0);  // consumed by the counter
}

IV_TEST(Defense, HardStanceStopsMostDamageButExposesLegsAndGrabs) {
  auto run = [](Zone target, bool grab, Outcome* out) {
    Rig r(1, grab ? 10.f : 20.f);
    r.b.guardHeld = true;
    r.b.hardStance = true;
    r.b.guardSide = SwingSide::Up;
    r.Step(tune::kHardStanceRaiseTicks + 2);
    IV_CHECK(r.B().HardStanceActive());
    if (grab) {
      r.a.toGrab = true;
      r.a.target = target;
      r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 200);
    } else {
      r.StartHeavyA(SwingSide::Down, target);
      r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 100);
    }
    *out = static_cast<Outcome>(r.LastOutcome(Side::A));
    return Lost(r, Side::B);
  };
  Outcome oTorso, oLeg, oGrab;
  const float torso = run(Zone::Torso, false, &oTorso);
  const float leg = run(Zone::LegL, false, &oLeg);
  run(Zone::Torso, true, &oGrab);
  IV_CHECK(oTorso == Outcome::HardStanceBlocked);
  IV_CHECK(oLeg == Outcome::HardStanceBlocked);
  IV_CHECK(leg > torso * 3.f);  // pitch §6: "открывает ноги"
  IV_CHECK(oGrab == Outcome::Grabbed);  // pitch §6: "уязвим для захвата"
}

IV_TEST(Defense, HardStanceDrainsEnergyAndRootsTheMech) {
  Rig r;
  r.b.guardHeld = true;
  r.b.hardStance = true;
  r.b.move = 1;
  const float e0 = r.B().res.energy;
  const float dist = r.duel.distance();
  r.Step(60);
  IV_CHECK(r.B().res.energy < e0 - 8.f);       // pitch §6: "расходует много энергии"
  IV_CHECK_NEAR(r.duel.distance(), dist, 1e-4);  // and the mech does not move
  r.b.dodge = true;
  r.Step();
  IV_CHECK_EQ(r.Count(EventType::Dodge), 0);     // no dodging from a hard stance
  // Out of energy the stance collapses.
  r.B().res.energy = 0.f;
  r.Step();
  IV_CHECK(!r.B().guard.hard);
  IV_CHECK_EQ(r.Count(EventType::HardStanceOff), 1);
}

IV_TEST(Defense, DodgeAvoidsLateralSlashesButNotChopsFromAbove) {
  auto run = [](SwingSide side) {
    Rig r;
    r.StartHeavyA(side, Zone::Torso);
    r.StepUntil([&] { return r.A().TicksToContact() == 8; });
    r.b.dodge = true;
    r.b.dodgeDir = 1;
    r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 100);
    return r.LastOutcome(Side::A);
  };
  IV_CHECK_EQ(run(SwingSide::Left), static_cast<int>(Outcome::Evaded));   // v3: the torso turn + half step beats a lateral slash
  IV_CHECK_EQ(run(SwingSide::Right), static_cast<int>(Outcome::Evaded));
  IV_CHECK_EQ(run(SwingSide::Up), static_cast<int>(Outcome::Hit));        // ...but not a chop from above
  IV_CHECK_EQ(run(SwingSide::Down), static_cast<int>(Outcome::Hit));
}

IV_TEST(Defense, DodgeNeedsTimingAndLeavesTheMechExposedAfterwards) {
  Rig r;
  r.b.dodge = true;
  r.Step();
  IV_CHECK(r.B().posture == Posture::Dodging);
  r.Step(tune::kDodgeEvadeTicks + 1);
  IV_CHECK(!r.B().Evading());
  IV_CHECK(r.B().posture == Posture::Dodging);  // pitch §6: one heavy step, then it must stabilise
  // A strike that lands after the evade window but before stabilisation connects.
  ForceStrike(r, Side::A, SwingSide::Up, Zone::Torso);
  r.Step();
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));
  r.Step(tune::kDodgeStabilizeTicks);
  IV_CHECK(r.B().posture != Posture::Dodging);
}

IV_TEST(Defense, DodgeTurnsTheOpponentAndLegDamageRemovesDodges) {
  Rig r;
  r.b.dodge = true;
  r.b.dodgeDir = 1;
  r.Step();
  IV_CHECK_NEAR(std::fabs(r.A().flank), tune::kDodgeFlankDeg, 1e-3);  // A must now re-face B
  r.Step(200);
  IV_CHECK(std::fabs(r.A().flank) < tune::kDodgeFlankDeg);            // and does, slowly (pitch §11)

  Rig lame;
  lame.B().body.ApplyDamage(Zone::LegL, 1000.f, StrikeKind::Heavy);
  lame.B().body.ApplyDamage(Zone::LegR, 1000.f, StrikeKind::Heavy);
  lame.b.dodge = true;
  lame.Step();
  IV_CHECK_EQ(lame.Count(EventType::Dodge), 0);                        // pitch §9: destroyed legs cannot dodge
  Rig half;
  half.B().body.ApplyDamage(Zone::LegL, 145.f, StrikeKind::Heavy);  // Critical: one push-off direction is left
  IV_CHECK(half.B().body.state(Zone::LegL) == ZoneState::Critical);
  half.b.dodge = true;
  half.b.dodgeDir = -1;
  half.Step();
  IV_CHECK_EQ(half.Count(EventType::Dodge), 1);                        // one working leg still allows one direction
  half.Step(80);
  half.b.dodge = true;
  half.b.dodgeDir = 1;
  half.Step();
  IV_CHECK_EQ(half.Count(EventType::Dodge), 1);
}

IV_TEST(Defense, InterceptWindowHasTheConfiguredWidthAndIsPunished) {
  int intercepted = 0;
  int hitsOnDefender = 0;
  for (int k = 0; k < 30; ++k) {
    Rig r;
    r.StartHeavyA(SwingSide::Up, Zone::Torso);
    r.StepUntil([&] { return r.A().TicksToContact() == k + 1; });
    r.b.quick = true;  // B launches a quick strike on a meeting line
    r.b.side = SwingSide::Up;
    r.b.target = Zone::Torso;
    r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 100);
    const Event* first = nullptr;
    for (const Event& e : r.duel.log().events())
      if (e.type == EventType::StrikeContact) {
        first = &e;
        break;
      }
    if (first != nullptr && first->actor == Side::A && first->b == static_cast<int>(Outcome::Intercepted)) {
      ++intercepted;
      IV_CHECK(r.duel.chain().active);
      IV_CHECK(r.duel.chain().who == Side::A);
      IV_CHECK(r.B().strike.innerLine);
      IV_CHECK(r.A().body.layer(Zone::ArmR, Layer::Armor) < tune::kArmorMax[Index(Zone::ArmR)]);  // the clash hurts the attacker's arm
    } else if (first != nullptr && first->actor == Side::A && first->b == static_cast<int>(Outcome::Hit)) {
      ++hitsOnDefender;  // too early or too late: the attacker lands (pitch §7: a mistake means a near-full hit)
    }
  }
  IV_CHECK(intercepted >= 1);
  IV_CHECK(intercepted <= tune::kInterceptWindowTicks);  // pitch §7: "перехват 90-140 мс"
  IV_CHECK(hitsOnDefender >= 1);   // a mistimed counter means a near-full hit (the longer v3 swing leaves fewer such timings)
}

IV_TEST(Defense, InterceptOnTheWrongLineDoesNotWork) {
  // Against a Down swing an Up counter is not a meeting line.
  Rig r;
  r.StartHeavyA(SwingSide::Down, Zone::LegL);
  bool any = false;
  for (int k = 0; k < 30; ++k) {
    Rig t;
    t.StartHeavyA(SwingSide::Down, Zone::LegL);
    t.StepUntil([&] { return t.A().TicksToContact() == k + 1; });
    t.b.quick = true;
    t.b.side = SwingSide::Up;
    t.StepUntil([&] { return t.Count(EventType::StrikeContact) > 0; }, 100);
    if (t.Count(EventType::InterceptSuccess) > 0) any = true;
  }
  IV_CHECK(!any);
}

IV_TEST(Defense, ReverseChainAllowsTwoAnswersThenClinch) {
  Rig r;
  r.A().res.energy = 100.f;
  r.B().res.energy = 100.f;
  // Open the chain directly: A was intercepted, B's counter is in flight.
  ForceStrike(r, Side::A, SwingSide::Up, Zone::Torso);
  r.B().phase = Phase::Strike;
  r.B().strike = StrikeState();
  r.B().strike.kind = StrikeKind::Quick;
  r.B().strike.side = SwingSide::Up;
  r.B().strike.arm = Arm::R;
  r.B().strike.strikeLen = 40;
  r.B().strike.strikeTick = 3;
  r.B().strike.released = true;
  r.Step();
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Intercepted));
  IV_CHECK(r.duel.chain().active);
  IV_CHECK(r.duel.chain().who == Side::A);
  IV_CHECK_EQ(r.duel.chain().windowLeft, tune::kReverseWindowTicks[0]);

  const float eA0 = r.A().res.energy;
  r.a.reverse = true;  // reply 1 by A with the other arm
  r.Step();
  IV_CHECK_EQ(r.Count(EventType::ReverseChain), 1);
  {
    int step = 0;
    for (const Event& e : r.duel.log().events())
      if (e.type == EventType::ReverseChain) step = e.a;
    IV_CHECK_EQ(step, 1);  // v2: ReverseChain{step}
  }
  IV_CHECK(r.duel.chain().active);
  IV_CHECK(r.duel.chain().who == Side::B);
  IV_CHECK_EQ(r.duel.chain().windowLeft, tune::kReverseWindowTicks[1]);  // pitch §7: each window is shorter
  IV_CHECK(tune::kReverseWindowTicks[1] < tune::kReverseWindowTicks[0]);
  const float cost1 = eA0 - r.A().res.energy;
  IV_CHECK(r.B().phase == Phase::Recovery);  // B's counter was redirected

  const float eB0 = r.B().res.energy;
  r.b.reverse = true;  // reply 2 by B
  r.Step();
  IV_CHECK_EQ(r.Count(EventType::ReverseChain), 2);
  const float cost2 = eB0 - r.B().res.energy;
  IV_CHECK(cost2 > cost1);  // pitch §7: bigger energy bill each time
  IV_CHECK_EQ(r.Count(EventType::Clinch), 1);
  IV_CHECK(r.duel.clinch().active);
  IV_CHECK(r.A().posture == Posture::Clinched && r.B().posture == Posture::Clinched);

  // A third reverse is impossible: the chain is closed and the clinch decides.
  r.a.reverse = true;
  r.Step();
  IV_CHECK_EQ(r.Count(EventType::ReverseChain), 2);
  IV_CHECK(!r.duel.chain().active);
}

IV_TEST(Defense, ReverseDamageGrowsWithDepthAndMissingTheWindowEndsTheChain) {
  Rig r;
  ForceStrike(r, Side::A, SwingSide::Up, Zone::Torso);
  r.B().phase = Phase::Strike;
  r.B().strike = StrikeState();
  r.B().strike.kind = StrikeKind::Quick;
  r.B().strike.side = SwingSide::Up;
  r.B().strike.strikeLen = 60;
  r.B().strike.strikeTick = 2;
  r.B().strike.released = true;
  r.Step();
  IV_CHECK(r.duel.chain().active);
  // Nobody answers: the window runs out and the chain closes.
  r.Step(tune::kReverseWindowTicks[0] + 1);
  IV_CHECK(!r.duel.chain().active);
  IV_CHECK_EQ(r.Count(EventType::ReverseChain), 0);

  const float d1 = tune::kReverseDamage * (1.f + tune::kReverseDepthDamageGrowth * 0.f);
  const float d2 = tune::kReverseDamage * (1.f + tune::kReverseDepthDamageGrowth * 1.f);
  IV_CHECK(d2 > d1);  // pitch §7: "более серьёзное наказание за ошибку"
}

IV_TEST(Defense, FailedReverseCostsStabilityAndClosesTheChain) {
  Rig r;
  ForceStrike(r, Side::A, SwingSide::Up, Zone::Torso);
  r.B().phase = Phase::Strike;
  r.B().strike = StrikeState();
  r.B().strike.kind = StrikeKind::Quick;
  r.B().strike.side = SwingSide::Up;
  r.B().strike.strikeLen = 60;
  r.B().strike.strikeTick = 2;
  r.B().strike.released = true;
  r.Step();
  IV_CHECK(r.duel.chain().active);
  r.A().res.energy = 0.f;  // cannot pay for the answer
  const float stab = r.A().res.stability;
  r.a.reverse = true;
  r.Step();
  IV_CHECK_EQ(r.Count(EventType::ReverseFailed), 1);
  IV_CHECK(r.A().res.stability < stab);
  IV_CHECK(!r.duel.chain().active);
  IV_CHECK_EQ(r.Count(EventType::ReverseChain), 0);
}

IV_TEST(Defense, ReverseNeedsTheOtherArmToBeUsable) {
  Rig r;
  r.A().body.ApplyDamage(Zone::ArmL, 1000.f, StrikeKind::Heavy);  // A's only spare arm is gone
  ForceStrike(r, Side::A, SwingSide::Up, Zone::Torso, false, Arm::R);
  r.B().phase = Phase::Strike;
  r.B().strike = StrikeState();
  r.B().strike.kind = StrikeKind::Quick;
  r.B().strike.side = SwingSide::Up;
  r.B().strike.strikeLen = 60;
  r.B().strike.strikeTick = 2;
  r.B().strike.released = true;
  r.Step();
  r.a.reverse = true;
  r.Step();
  IV_CHECK_EQ(r.Count(EventType::ReverseChain), 0);
  IV_CHECK_EQ(r.Count(EventType::ReverseFailed), 1);
}

IV_TEST(Defense, ClinchIsWonByStabilityAndTheLoserIsStaggered) {
  Rig r;
  r.A().res.stability = 90.f;
  r.B().res.stability = 30.f;
  r.A().EnterClinch();
  r.B().EnterClinch();
  // Start the clinch through the Duel API by faking the end of a chain.
  ForceStrike(r, Side::A, SwingSide::Up, Zone::Torso);
  r.A().LeaveClinch();
  r.B().LeaveClinch();
  Rig c;
  c.A().res.stability = 90.f;
  c.B().res.stability = 30.f;
  ForceStrike(c, Side::A, SwingSide::Up, Zone::Torso);
  c.B().phase = Phase::Strike;
  c.B().strike = StrikeState();
  c.B().strike.kind = StrikeKind::Quick;
  c.B().strike.side = SwingSide::Up;
  c.B().strike.strikeLen = 99;
  c.B().strike.strikeTick = 2;
  c.B().strike.released = true;
  c.Step();
  c.a.reverse = true;
  c.Step();
  c.b.reverse = true;
  c.A().res.energy = c.B().res.energy = 100.f;
  c.Step();
  IV_CHECK(c.duel.clinch().active);
  c.Step(tune::kClinchTicks + 2);
  IV_CHECK(!c.duel.clinch().active);
  IV_CHECK_EQ(c.Count(EventType::ClinchResolved), 1);
  IV_CHECK(c.A().posture == Posture::Standing);
  // The weaker side lost the contest: A (more stable) is the winner recorded in the event.
  bool aWon = false;
  for (const Event& e : c.duel.log().events())
    if (e.type == EventType::ClinchResolved) aWon = e.actor == Side::A;
  IV_CHECK(aWon);
}

IV_TEST(Defense, ClinchOutcomeFollowsWallProximityAndSlamsTheLoser) {
  auto run = [](float proxA, float proxB, bool* aWins, int* slams) {
    Rig c;
    c.world.proximity[0] = proxA;
    c.world.proximity[1] = proxB;
    c.A().res.energy = c.B().res.energy = 100.f;
    ForceStrike(c, Side::A, SwingSide::Up, Zone::Torso);
    c.B().phase = Phase::Strike;
    c.B().strike = StrikeState();
    c.B().strike.kind = StrikeKind::Quick;
    c.B().strike.side = SwingSide::Up;
    c.B().strike.strikeLen = 99;
    c.B().strike.strikeTick = 2;
    c.B().strike.released = true;
    c.Step();
    c.a.reverse = true;
    c.Step();
    c.b.reverse = true;
    c.Step();
    c.A().res.stability = c.B().res.stability = 100.f;  // isolate the wall effect from earlier chain damage
    c.Step(tune::kClinchTicks + 2);
    *aWins = false;
    for (const Event& e : c.duel.log().events())
      if (e.type == EventType::ClinchResolved) *aWins = e.actor == Side::A;
    *slams = c.Count(EventType::WallSlam);
  };
  bool aWins = false;
  int slams = 0;
  run(0.9f, 0.0f, &aWins, &slams);  // A has its back to a wall
  IV_CHECK(!aWins);
  run(0.0f, 0.9f, &aWins, &slams);
  IV_CHECK(aWins);
  IV_CHECK_EQ(slams, 1);            // pitch §12: pressed into the building
  run(0.0f, 0.0f, &aWins, &slams);
  IV_CHECK_EQ(slams, 0);
}

IV_TEST(Defense, ZeroStabilityStaggersAndASecondCollapseKnocksTheMechDown) {
  Rig r;
  Fighter& b = r.B();
  const StepContext ctx = [&] {
    StepContext c;
    c.log = &r.duel.log();
    return c;
  }();
  b.TakeHit(Zone::Torso, 1.f, StrikeKind::Heavy, 200.f, ctx);
  IV_CHECK(b.posture == Posture::Staggered);
  IV_CHECK_EQ(r.Count(EventType::StaggerBegin), 1);
  b.TakeHit(Zone::Torso, 1.f, StrikeKind::Heavy, 200.f, ctx);  // stability hits zero again while staggered
  IV_CHECK(b.posture == Posture::KnockedDown);
  IV_CHECK_EQ(r.Count(EventType::Knockdown), 1);

  // A downed mech takes more damage, stays down for the configured time and then gets up.
  Rig up, down;
  const StepContext c2 = [&] {
    StepContext c;
    c.log = &down.duel.log();
    return c;
  }();
  down.B().posture = Posture::KnockedDown;
  const float dUp = up.B().TakeHit(Zone::Torso, 20.f, StrikeKind::Heavy, 0.f, c2).dealt;
  const float dDown = down.B().TakeHit(Zone::Torso, 20.f, StrikeKind::Heavy, 0.f, c2).dealt;
  IV_CHECK(dDown > dUp);
  down.Step(tune::kKnockdownTicks + 2);
  IV_CHECK(down.B().posture == Posture::Standing);
  IV_CHECK_EQ(down.Count(EventType::GotUp), 1);
}

IV_TEST(Defense, GuardEnergyPriorityLowersDamageTakenAndBlocksAreNotFree) {
  Rig guard, arms;
  arms.B().res.priority = EnergyPriority::Arms;
  const float g = StrikeAtB(guard, SwingSide::Up, Zone::Torso, [](Rig&) {});
  const float a = StrikeAtB(arms, SwingSide::Up, Zone::Torso, [](Rig&) {});
  IV_CHECK(g < a);  // pitch §10: Guard priority lowers structural damage
  // Holding a guard burns energy even when nothing hits it (pitch §6: passive defence must not be safe).
  Rig idle;
  idle.b.guardHeld = true;
  const float e0 = idle.B().res.energy;
  idle.Step(120);
  IV_CHECK(idle.B().res.energy < e0 + 120 * tune::kEnergyRegenPerTick - 1.f);
}

// The pitch gives the defence windows in milliseconds; the tick values must stay inside those ranges (60 Hz => 16.7 ms/tick).
IV_TEST(Defense, WindowsStayInsideThePitchRangesInMilliseconds) {
  const auto ms = [](int ticks) { return ticks * 1000.0 / kTickHz; };
  IV_CHECK(ms(tune::kParryWindowTicks) >= 140.0 && ms(tune::kParryWindowTicks) <= 320.0);          // pitch §6
  IV_CHECK(ms(tune::kInterceptWindowTicks) >= 90.0 && ms(tune::kInterceptWindowTicks) <= 140.0);   // pitch §6 / §7
  IV_CHECK(ms(tune::kReverseWindowTicks[0]) >= 70.0 && ms(tune::kReverseWindowTicks[0]) <= 110.0);  // pitch §6
  IV_CHECK(ms(tune::kReverseWindowTicks[1]) >= 70.0 && ms(tune::kReverseWindowTicks[1]) <= 110.0);
}

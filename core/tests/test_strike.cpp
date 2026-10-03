// Module 3: Combat Vector strike formation (pitch §5, §8).
#include "TestUtil.h"

using namespace iv;
using namespace ivtest;

IV_TEST(Strike, HeavyStrikeWalksThroughAllPhasesInOrder) {
  Rig r;
  r.a.strikeHeld = true;
  r.a.side = SwingSide::Up;
  r.a.target = Zone::Torso;
  r.Step();
  IV_CHECK(r.A().phase == Phase::Windup);
  r.Step(tune::kWindupMinTicks - 1);
  IV_CHECK(r.A().phase == Phase::Windup);
  r.a.strikeHeld = false;
  Phase seen[5];
  int n = 0;
  Phase last = r.A().phase;
  seen[n++] = last;
  for (int i = 0; i < 300 && !(last == Phase::Idle && n > 1); ++i) {
    r.Step();
    if (r.A().phase != last) {
      last = r.A().phase;
      if (n < 5) seen[n++] = last;
    }
  }
  IV_CHECK_EQ(n, 5);
  IV_CHECK(seen[0] == Phase::Windup);
  IV_CHECK(seen[1] == Phase::Strike);
  IV_CHECK(seen[2] == Phase::Contact || seen[2] == Phase::Recovery);
  IV_CHECK(r.Count(EventType::WindupStarted) == 1);
  IV_CHECK(r.Count(EventType::Committed) == 1);
  IV_CHECK(r.Count(EventType::StrikeContact) == 1);
}

IV_TEST(Strike, ReleasingBeforeMinimumWindupCommitsNothing) {
  Rig r;
  r.a.strikeHeld = true;
  r.Step(tune::kWindupMinTicks - 4);
  r.a.strikeHeld = false;
  r.Step(1);
  IV_CHECK(r.A().phase == Phase::Recovery);  // short abort recovery only
  IV_CHECK_EQ(r.Count(EventType::Committed), 0);
  r.Step(tune::kAbortRecoveryTicks + 1);
  IV_CHECK(r.A().phase == Phase::Idle);
  IV_CHECK_EQ(r.Count(EventType::StrikeContact), 0);
}

IV_TEST(Strike, CancelWhileHoldingIsFree) {
  Rig r;
  r.a.strikeHeld = true;
  r.Step(tune::kWindupMinTicks + 5);
  const float heat = r.A().res.heat;
  const float stab = r.A().res.stability;
  r.a.cancel = true;
  r.Step();
  IV_CHECK(r.A().phase == Phase::Idle);
  IV_CHECK(r.A().res.heat <= heat + 1.f);  // charge heat only, no cancel cost
  IV_CHECK(r.A().res.stability >= stab);
  IV_CHECK_EQ(r.Count(EventType::CancelCheap), 1);
  IV_CHECK_EQ(r.Count(EventType::EmergencyBrake), 0);
}

IV_TEST(Strike, CancelJustBeforeTheCommitPointIsCheap) {
  Rig r;
  r.a.strikeHeld = true;
  r.Step(tune::kWindupMinTicks);
  r.a.strikeHeld = false;
  r.Step();  // release tick
  // Run until exactly one tick before the commit point passes.
  r.StepUntil([&] { return r.A().strike.sinceRelease == tune::kCommitDelayTicks - 1; });
  IV_CHECK(r.A().phase == Phase::Windup);
  const float stab = r.A().res.stability;
  const float heat = r.A().res.heat;
  r.a.cancel = true;
  r.Step();
  IV_CHECK(r.A().phase == Phase::Recovery);
  IV_CHECK_EQ(r.Count(EventType::Committed), 0);
  IV_CHECK_EQ(r.Count(EventType::EmergencyBrake), 0);
  IV_CHECK_NEAR(r.A().res.heat - heat, tune::kCheapCancelHeat, 0.2);
  IV_CHECK(r.A().res.stability >= stab);
}

IV_TEST(Strike, CancelExactlyOnTheCommitTickIsAnEmergencyBrake) {
  Rig r;
  r.a.strikeHeld = true;
  r.Step(tune::kWindupMinTicks);
  r.a.strikeHeld = false;
  r.StepUntil([&] { return r.A().phase == Phase::Strike; });  // the commit point has just passed
  IV_CHECK_EQ(r.Count(EventType::Committed), 1);
  const float stab = r.A().res.stability;
  const float heat = r.A().res.heat;
  r.a.cancel = true;
  r.Step();
  IV_CHECK_EQ(r.Count(EventType::EmergencyBrake), 1);
  IV_CHECK(r.A().phase == Phase::Recovery);
  IV_CHECK(heat + tune::kEmergencyBrakeHeat - 1.f <= r.A().res.heat);
  IV_CHECK(r.A().res.stability <= stab - tune::kEmergencyBrakeStability + 1.f);
  IV_CHECK_EQ(r.Count(EventType::StrikeContact), 0);  // the strike never reaches the enemy
}

IV_TEST(Strike, QuickStrikeIsFastWeakAndInterruptsALongWindup) {
  Rig r;
  r.b.strikeHeld = true;  // B starts a long heavy windup
  r.b.side = SwingSide::Up;
  r.Step(10);
  IV_CHECK(r.B().phase == Phase::Windup);
  r.a.quick = true;
  r.a.side = SwingSide::Left;
  r.a.target = Zone::Torso;
  int ticks = 0;
  while (r.Count(EventType::StrikeContact) == 0 && ticks < 100) {
    r.Step();
    ++ticks;
  }
  IV_CHECK(ticks <= tune::kQuickWindupTicks + tune::kQuickStrikeTicks + 2);
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));
  IV_CHECK(r.B().phase == Phase::Recovery);  // windup broken (pitch §5.3)
  IV_CHECK_EQ(r.Count(EventType::Interrupted), 1);
  const float quickDmg = TotalHp(Fighter(Side::B)) - TotalHp(r.B());
  IV_CHECK(quickDmg > 0.f && quickDmg < tune::kHeavyDamage);
}

IV_TEST(Strike, ChangingTargetBeforeCommitIsAFeintThatCostsHeatAndSlows) {
  Rig r;
  r.a.strikeHeld = true;
  r.a.target = Zone::Head;
  r.Step(5);
  const float heat = r.A().res.heat;
  r.a.target = Zone::LegL;
  r.Step();
  IV_CHECK_EQ(r.Count(EventType::Feint), 1);
  IV_CHECK(r.A().res.heat >= heat + tune::kFeintHeat - 0.5f);
  IV_CHECK(r.A().strike.target == Zone::LegL);
  IV_CHECK(r.A().feintSlow > 0);
}

IV_TEST(Strike, FrequentFeintsCostDoubleHeatAndAccumulate) {
  Rig r;
  r.a.strikeHeld = true;
  r.a.target = Zone::Head;
  r.Step(3);
  float heatBefore = r.A().res.heat;
  const Zone seq[] = {Zone::LegL, Zone::Head, Zone::LegR, Zone::ShoulderL};
  float costs[4];
  for (int i = 0; i < 4; ++i) {
    r.a.target = seq[i];
    r.Step();
    costs[i] = r.A().res.heat - heatBefore;
    heatBefore = r.A().res.heat;
  }
  IV_CHECK_EQ(r.A().feints, 4);
  IV_CHECK(costs[3] > costs[0] * 1.5f);  // beyond kMaxFeintsBeforePenalty each feint costs double
}

IV_TEST(Strike, FeintCanTurnAWindupIntoAGrabButNotAfterCommit) {
  Rig r;
  r.a.strikeHeld = true;
  r.Step(6);
  r.a.toGrab = true;
  r.Step();
  IV_CHECK(r.A().strike.kind == StrikeKind::Grab);
  IV_CHECK_EQ(r.Count(EventType::Feint), 1);

  Rig late;
  late.StartHeavyA(SwingSide::Up, Zone::Torso);
  IV_CHECK(late.A().phase == Phase::Strike);
  late.a.toGrab = true;
  late.a.target = Zone::Head;
  late.Step();
  IV_CHECK(late.A().strike.kind == StrikeKind::Heavy);
  IV_CHECK_EQ(late.Count(EventType::Feint), 0);  // pitch §8: feints only exist before the commit point
}

IV_TEST(Strike, ArmSwitchFeintMovesTheStrikeToTheOtherArm) {
  Rig r;
  r.a.strikeHeld = true;
  r.a.arm = Arm::R;
  r.Step(5);
  r.a.switchArm = true;
  r.Step();
  IV_CHECK(r.A().strike.arm == Arm::L);
  IV_CHECK_EQ(r.Count(EventType::Feint), 1);
  // A destroyed left arm cannot take the strike over.
  Rig r2;
  r2.A().body.ApplyDamage(Zone::ArmL, 1000.f, StrikeKind::Heavy);
  r2.a.strikeHeld = true;
  r2.a.arm = Arm::R;
  r2.Step(5);
  r2.a.switchArm = true;
  r2.Step();
  IV_CHECK(r2.A().strike.arm == Arm::R);
  IV_CHECK_EQ(r2.Count(EventType::Feint), 0);
}

IV_TEST(Strike, PoseAfterSideSwingForbidsAnUpSwingUntilTheArmIsReturned) {
  Rig r;
  r.StartHeavyA(SwingSide::Left, Zone::Torso);
  r.StepUntil([&] { return r.A().phase == Phase::Idle; });
  IV_CHECK(r.A().pose[Index(Arm::R)] == ArmPose::CrossedLeft);
  IV_CHECK(!r.A().SwingAllowedByPose(Arm::R, SwingSide::Up));
  IV_CHECK(r.A().SwingAllowedByPose(Arm::R, SwingSide::Right));  // the backhand is natural
  IV_CHECK(r.A().SwingAllowedByPose(Arm::L, SwingSide::Up));     // the other arm is free

  // An Up swing from the crossed pose needs the arm returned first: a longer minimum windup.
  r.a.strikeHeld = true;
  r.a.side = SwingSide::Up;
  r.Step();
  IV_CHECK(r.A().strike.minHold >= tune::kWindupMinTicks + tune::kPoseReturnTicks);
  IV_CHECK_EQ(r.Count(EventType::PoseReturn), 1);
  r.a.strikeHeld = false;
  r.StepUntil([&] { return r.A().phase == Phase::Idle; });

  // The backhand has no extra delay.
  Rig r2;
  r2.StartHeavyA(SwingSide::Left, Zone::Torso);
  r2.StepUntil([&] { return r2.A().phase == Phase::Idle; });
  r2.a.strikeHeld = true;
  r2.a.side = SwingSide::Right;
  r2.Step();
  IV_CHECK(r2.A().strike.minHold < tune::kWindupMinTicks + tune::kPoseReturnTicks);
}

IV_TEST(Strike, PoseReturnsToNeutralAfterIdling) {
  Rig r;
  r.StartHeavyA(SwingSide::Up, Zone::Head);
  r.StepUntil([&] { return r.A().phase == Phase::Idle; });
  IV_CHECK(r.A().pose[Index(Arm::R)] == ArmPose::Raised);
  r.Step(tune::kPoseDecayTicks + 2);
  IV_CHECK(r.A().pose[Index(Arm::R)] == ArmPose::Neutral);
  IV_CHECK(r.A().SwingAllowedByPose(Arm::R, SwingSide::Down));
}

IV_TEST(Strike, DamagedElbowRemovesTheLowSwing) {
  Rig r;
  r.A().body.ApplyDamage(Zone::ArmR, tune::kArmorMax[Index(Zone::ArmR)] + 5.f, StrikeKind::Heavy);  // Damaged
  IV_CHECK(r.A().body.state(Zone::ArmR) == ZoneState::Damaged);
  r.a.strikeHeld = true;
  r.a.side = SwingSide::Down;
  r.a.arm = Arm::R;
  r.Step();
  // The right arm may not swing Down any more, so the strike falls to the intact left arm.
  IV_CHECK(r.A().strike.arm == Arm::L);
  // With both arms damaged the swing cannot start at all.
  Rig r2;
  r2.A().body.ApplyDamage(Zone::ArmR, tune::kArmorMax[Index(Zone::ArmR)] + 5.f, StrikeKind::Heavy);
  r2.A().body.ApplyDamage(Zone::ArmL, tune::kArmorMax[Index(Zone::ArmL)] + 5.f, StrikeKind::Heavy);
  r2.a.strikeHeld = true;
  r2.a.side = SwingSide::Down;
  r2.Step(3);
  IV_CHECK(r2.A().phase == Phase::Idle);
  IV_CHECK_EQ(r2.Count(EventType::WindupStarted), 0);
}

IV_TEST(Strike, StepInAddsPowerAndReachHoldDoesNot) {
  auto land = [](Footwork fw, float distance) {
    Rig r(1, distance);
    r.a.footwork = fw;
    r.a.strikeHeld = true;
    r.a.side = SwingSide::Up;
    r.a.target = Zone::Torso;
    r.Step(tune::kWindupMinTicks);
    r.a.strikeHeld = false;
    r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; });
    return TotalHp(Fighter(Side::B)) - TotalHp(r.B());
  };
  const float hold = land(Footwork::Hold, 20.f);
  const float step = land(Footwork::StepIn, 20.f);
  const float back = land(Footwork::StepBack, 20.f);
  IV_CHECK(step > hold);  // pitch §11: stepping into the blow adds force
  IV_CHECK(back < hold);  // a retreating poke is weaker
  // A strike from just outside the plain reach only connects with a step in.
  const float far = tune::kHeavyReach + 3.f;
  IV_CHECK_NEAR(land(Footwork::Hold, far), 0.0, 1e-4);
  IV_CHECK(land(Footwork::StepIn, far) > 0.f);
}

IV_TEST(Strike, StepInWithLowStabilityOverextends) {
  Rig r;
  r.A().res.stability = tune::kStepInMinStability - 5.f;
  r.a.footwork = Footwork::StepIn;
  r.a.strikeHeld = true;
  r.Step(tune::kWindupMinTicks);
  r.a.strikeHeld = false;
  r.StepUntil([&] { return r.A().phase == Phase::Strike; });
  IV_CHECK(r.A().strike.plant == FootPlant::Overextended);
}

IV_TEST(Strike, ChargedStrikeHitsHarderAndRunsHotterThanAMinimumOne) {
  auto land = [](int extraHold, float* heatOut) {
    Rig r;
    r.a.strikeHeld = true;
    r.a.side = SwingSide::Up;
    r.a.target = Zone::Torso;
    r.Step(tune::kWindupMinTicks + extraHold);
    r.a.strikeHeld = false;
    r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; });
    *heatOut = r.A().res.heat;
    return TotalHp(Fighter(Side::B)) - TotalHp(r.B());
  };
  float h0 = 0.f, h1 = 0.f;
  const float minimal = land(0, &h0);
  const float charged = land(tune::kWindupMaxChargeTicks, &h1);
  IV_CHECK(charged > minimal * 1.5f);
  IV_CHECK(h1 > h0);
}

IV_TEST(Strike, MissingAtRangeCostsTheAttackerStability) {
  Rig r(1, 100.f);
  r.StartHeavyA(SwingSide::Up, Zone::Torso);
  const float stab = r.A().res.stability;
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; });
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Whiff));
  IV_CHECK(r.A().res.stability < stab);
  IV_CHECK_EQ(r.Count(EventType::Whiff), 1);
}

IV_TEST(Strike, ReactorOnlyReachableFromBehind) {
  auto strikeReactor = [](float flank) {
    Rig r;
    r.B().flank = flank;
    r.StartHeavyA(SwingSide::Left, Zone::Reactor);
    r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; });
    return r.B().body.layer(Zone::Reactor, Layer::Armor) < tune::kArmorMax[Index(Zone::Reactor)];
  };
  IV_CHECK(!strikeReactor(0.f));    // from the front the blow lands on the torso instead
  IV_CHECK(strikeReactor(140.f));   // pitch §9: getting behind opens the rear zone
}

IV_TEST(Strike, UnnaturalSwingTargetPairsDoLessDamage) {
  auto dmg = [](SwingSide side, Zone target) {
    Rig r;
    r.StartHeavyA(side, target);
    r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; });
    return r.A().strike.kind == StrikeKind::Heavy ? r.A().StrikeDamage() : 0.f;
  };
  IV_CHECK(dmg(SwingSide::Down, Zone::LegL) > dmg(SwingSide::Up, Zone::LegL));
  IV_CHECK(dmg(SwingSide::Up, Zone::Head) > dmg(SwingSide::Down, Zone::Head));
}

IV_TEST(Strike, HeatSlowsTheSwingAndWeakensTheBlow) {
  Rig cool, hot;
  hot.A().res.heat = tune::kHeatMax;
  IV_CHECK(hot.A().res.HeatPerformance() < 1.f);
  cool.a.strikeHeld = hot.a.strikeHeld = true;
  cool.Step();
  hot.Step();
  IV_CHECK(hot.A().strike.minHold > cool.A().strike.minHold);  // slower windup at high heat (pitch §10)
  IV_CHECK(hot.A().StrikeDamage() < cool.A().StrikeDamage());
}

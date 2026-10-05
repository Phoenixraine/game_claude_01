// Boarding (TASK-017, STATUS §6B): denial rules, the full success / failure / timeout lines, the enemy hand, autopilot, symmetry, determinism, fuzz.
#include "TestUtil.h"
#include <cstring>
#include "iv/Boarding.h"

using namespace ivtest;

namespace {

struct BRig {
  Duel duel;
  Boarding bd;
  Input a, b;
  World world;
  BoardingInput bi;
  bool bot = false;        // perfect hacker: confirm whenever the stub game says so
  Side owner;

  explicit BRig(Side o = Side::A, uint64_t seed = 7, Difficulty d = Difficulty::Normal, float swat = 0.f, Archetype arch = Archetype::Counterpuncher)
      : duel(seed, true), bd(MakeCfg(o, seed, d, swat, arch)), owner(o) {
    duel.set_distance(40.f);
  }
  static BoardingConfig MakeCfg(Side o, uint64_t seed, Difficulty d, float swat, Archetype arch) {
    BoardingConfig c;
    c.lethalSwat = true;   // the v4 rules these tests describe
    c.owner = o;
    c.seed = seed;
    c.enemyDifficulty = d;
    c.enemyArchetype = arch;
    c.swatChanceMult = swat;
    return c;
  }
  Fighter& Me() { return duel.fighter(owner); }
  Fighter& Foe() { return duel.fighter(Other(owner)); }
  Input& MyIn() { return owner == Side::A ? a : b; }

  void Tick() {
    if (bot && bd.phase() == BoardPhase::Hacking) bi.hack = bd.hack().PerfectInput();
    const Input mine = bd.Filter(duel, MyIn());
    const Input other = owner == Side::A ? b : a;
    if (owner == Side::A) duel.Step(mine, other, world);
    else duel.Step(other, mine, world);
    bd.Step(duel, bi);
    ClearEdges(a);
    ClearEdges(b);
    bi.start = bi.swing = bi.swat = false;
    bi.hack = HackInput();
  }
  void Run(int n) {
    for (int i = 0; i < n; ++i) Tick();
  }
  template <class Pred>
  bool Until(Pred p, int maxTicks = 6000) {
    for (int i = 0; i < maxTicks; ++i) {
      if (p()) return true;
      Tick();
    }
    return p();
  }
  void Start() {
    bi.start = true;
    Tick();
  }
  int Count(EventType t) const { return duel.log().CountOf(t); }
  const Event* Find(EventType t, int nth = 0) const {
    for (const Event& e : duel.log().events())
      if (e.type == t && nth-- == 0) return &e;
    return nullptr;
  }
  bool Finished() const { return !bd.Active(); }
};

}  // namespace

// ---------------------------------------------------------------------------------------------- start rules

IV_TEST(Boarding, StartsFromQuietStandingAndSpendsEnergy) {
  BRig r;
  const float e0 = r.Me().res.energy;
  r.Start();
  IV_CHECK(r.bd.Active());
  IV_CHECK(r.bd.phase() == BoardPhase::ClimbOut);
  IV_CHECK(r.Me().autopilot);
  IV_CHECK(r.Me().res.energy < e0 - tune::kBoardEnergyCost * 0.5f);
  IV_CHECK_EQ(r.Count(EventType::BoardingStarted), 1);
  IV_CHECK_EQ(r.Count(EventType::BoardingDenied), 0);
}

IV_TEST(Boarding, DeniedInClinch) {
  BRig r;
  r.Me().EnterClinch();
  r.Start();
  IV_CHECK(!r.bd.Active());
  IV_CHECK(r.bd.lastDenied() == BoardingDenied::Clinch);
  IV_CHECK_EQ(r.Count(EventType::BoardingDenied), 1);
  IV_CHECK(!r.Me().autopilot);
}

IV_TEST(Boarding, DeniedWhileAStrikeIsInProgress) {
  BRig r;
  r.MyIn().strikeHeld = true;
  r.MyIn().side = SwingSide::Left;
  r.Run(5);
  IV_CHECK(r.Me().phase == Phase::Windup);
  r.Start();
  IV_CHECK(!r.bd.Active());
  IV_CHECK(r.bd.lastDenied() == BoardingDenied::Busy);
}

IV_TEST(Boarding, DeniedWhileWeaponChargesOrStaggered) {
  BRig r;
  r.MyIn().weaponHeld = true;
  r.Run(10);
  IV_CHECK(r.Me().weaponCharging);
  r.Start();
  IV_CHECK(r.bd.lastDenied() == BoardingDenied::Busy);
  r.MyIn().weaponHeld = false;
  r.Run(5);
  StepContext sc;
  sc.log = &r.duel.log();
  r.Me().ForceStagger(sc);
  IV_CHECK(r.Me().posture == Posture::Staggered);
  r.Start();
  IV_CHECK(r.bd.lastDenied() == BoardingDenied::Stunned);
  IV_CHECK(!r.bd.Active());
}

IV_TEST(Boarding, DeniedForEnergyAndStability) {
  BRig r;
  r.Me().res.energy = tune::kBoardEnergyCost - 1.f;
  r.Start();
  IV_CHECK(r.bd.lastDenied() == BoardingDenied::NoEnergy);
  r.Me().res.energy = 100.f;
  r.Me().res.stability = tune::kBoardMinStability - 1.f;
  r.Start();
  IV_CHECK(r.bd.lastDenied() == BoardingDenied::NoStability);
  IV_CHECK(!r.bd.Active());
  r.Me().res.stability = 100.f;
  r.Start();
  IV_CHECK(r.bd.Active());
}

IV_TEST(Boarding, DestroyedShoulderMovesTheHatchOrDeniesWhenBothAreGone) {
  BRig r;
  r.Foe().body.ApplyDamage(Zone::ShoulderR, 2000.f, StrikeKind::Heavy);
  IV_CHECK(r.Foe().body.lost(Zone::ShoulderR));
  r.bi.shoulder = Arm::R;
  r.Start();
  IV_CHECK(r.bd.Active());
  IV_CHECK(r.bd.shoulder() == Arm::L);   // the hatch moves to the opposite side
  BRig q;
  q.Foe().body.ApplyDamage(Zone::ShoulderR, 2000.f, StrikeKind::Heavy);
  q.Foe().body.ApplyDamage(Zone::ShoulderL, 2000.f, StrikeKind::Heavy);
  q.Start();
  IV_CHECK(!q.bd.Active());
  IV_CHECK(q.bd.lastDenied() == BoardingDenied::NoTarget);
}

IV_TEST(Boarding, DeniedAfterMatchEndAndForAiOwner) {
  BRig r;
  r.duel.ForceEnd(Side::B, EndReason::ReactorDestroyed);
  r.Start();
  IV_CHECK(r.bd.lastDenied() == BoardingDenied::MatchOver);
  BoardingConfig c;
    c.lethalSwat = true;   // the v4 rules these tests describe
  c.ownerIsAi = true;
  Boarding ai(c);
  Duel d(3, true);
  BoardingInput bi;
  bi.start = true;
  d.Step(Input(), Input());
  ai.Step(d, bi);
  IV_CHECK(!ai.Active());
  IV_CHECK(ai.lastDenied() == BoardingDenied::AiDisabled);
  IV_CHECK(!tune::kAiBoardingEnabled);
}

// ---------------------------------------------------------------------------------------------- the lines

IV_TEST(Boarding, FullSuccessBlastsTheEnemyShoulder) {
  BRig r;
  r.bot = true;
  const float hp0 = TotalHp(r.Foe());
  r.Start();
  IV_CHECK(r.Until([&] { return r.Finished(); }, 20000));
  IV_CHECK(r.bd.outcome() == BoardingOutcome::Success);
  IV_CHECK(r.bd.phase() == BoardPhase::Done);
  IV_CHECK(!r.Me().autopilot);
  IV_CHECK_EQ(r.Count(EventType::HackResultEvt), 1);
  IV_CHECK_EQ(r.Count(EventType::GrenadeThrown), 1);
  IV_CHECK_EQ(r.Count(EventType::BoardingBlast), 1);
  const Event* blast = r.Find(EventType::BoardingBlast);
  IV_CHECK(blast != nullptr);
  if (blast) {
    IV_CHECK(blast->zone == ShoulderZone(r.bd.shoulder()));
    IV_CHECK(blast->value > 0.5f * tune::kGrenadeDamageMin);
    IV_CHECK(blast->value <= tune::kGrenadeDamageMax + 0.01f);
  }
  const float lost = hp0 - TotalHp(r.Foe());
  IV_CHECK(lost >= 1.0f * tune::kHeavyDamage);   // well above a quick poke
  IV_CHECK(lost <= 2.3f * tune::kHeavyDamage + 1.f);
  IV_CHECK(r.Foe().burnTicks > 0);
  IV_CHECK(r.bd.cooldownLeft() >= MsToTicks(44000));
  IV_CHECK_EQ(r.Count(EventType::BoardingEnded), 1);
  IV_CHECK(r.Find(EventType::BoardingEnded)->a == static_cast<int>(BoardingOutcome::Success));
}

IV_TEST(Boarding, PhaseOrderAndLengthsComeFromTuning) {
  BRig r;
  r.bot = true;
  r.Start();
  IV_CHECK(r.Until([&] { return r.Finished(); }, 20000));
  const BoardPhase order[] = {BoardPhase::ClimbOut, BoardPhase::OnShoulder, BoardPhase::HookLaunch, BoardPhase::HookFlight, BoardPhase::Landing,
                              BoardPhase::Hacking,  BoardPhase::GrenadeThrow, BoardPhase::Escape,   BoardPhase::WatchBlast, BoardPhase::ClimbIn};
  const int lens[] = {tune::kBoardClimbOutTicks, tune::kBoardOnShoulderTicks, tune::kBoardHookLaunchTicks, tune::kBoardHookFlightTicks, tune::kBoardLandingTicks,
                      0, tune::kBoardGrenadeThrowTicks, tune::kBoardEscapeTicks, tune::kBoardWatchBlastTicks, tune::kBoardClimbInTicks};
  int k = 0;
  for (const Event& e : r.duel.log().events()) {
    if (e.type != EventType::BoardingPhase) continue;
    IV_CHECK(k < 10);
    if (k >= 10) break;
    IV_CHECK_EQ(e.a, static_cast<int>(order[k]));
    IV_CHECK_EQ(e.b, lens[k]);
    ++k;
  }
  IV_CHECK_EQ(k, 10);
  IV_CHECK_EQ(r.Count(EventType::HookFired), 1);
  IV_CHECK_EQ(r.Count(EventType::HookLanded), 1);
}

IV_TEST(Boarding, FailedHackReturnsWithoutDamagingTheEnemy) {
  BRig r;
  const float hp0 = TotalHp(r.Foe());
  r.Start();
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::Hacking; }));
  const float e0 = r.Me().res.energy;
  r.bi.hack.back = true;
  r.Tick();
  IV_CHECK(r.bd.phase() == BoardPhase::ReturnHook);
  IV_CHECK(r.Me().res.energy <= e0 - tune::kBoardPenaltyEnergy + 3.f);   // a few ticks of regen may have been added
  IV_CHECK(r.Until([&] { return r.Finished(); }, 4000));
  IV_CHECK(r.bd.outcome() == BoardingOutcome::HackFailed);
  IV_CHECK_EQ(r.Count(EventType::GrenadeThrown), 0);
  IV_CHECK_EQ(r.Count(EventType::BoardingBlast), 0);
  IV_CHECK_NEAR(TotalHp(r.Foe()), hp0, 0.001);
  IV_CHECK(r.bd.cooldownLeft() > tune::kBoardCooldownTicks - 200);
  IV_CHECK(!r.Me().autopilot);
}

IV_TEST(Boarding, TimeoutReturnsAndMarksIt) {
  BRig r;
  r.Start();
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::Hacking; }));
  const int limit = r.bd.hack().timeLimit();
  int n = 0;
  while (r.bd.phase() == BoardPhase::Hacking && n < limit + 100) {
    r.Tick();
    ++n;
  }
  IV_CHECK(r.bd.phase() == BoardPhase::ReturnHook);
  IV_CHECK(n >= limit - 5 && n <= limit + 5);
  IV_CHECK(r.Until([&] { return r.Finished(); }, 4000));
  IV_CHECK(r.bd.outcome() == BoardingOutcome::HackTimeout);
  IV_CHECK_EQ(r.Find(EventType::HackResultEvt)->a, static_cast<int>(HackState::Timeout));
}

IV_TEST(Boarding, GrenadeDamageGrowsWithQualityAndIsCapped) {
  IV_CHECK_NEAR(Boarding::GrenadeDamage(0.f), tune::kGrenadeDamageMin, 1e-4);
  IV_CHECK_NEAR(Boarding::GrenadeDamage(1.f), tune::kGrenadeDamageMax, 1e-4);
  IV_CHECK(Boarding::GrenadeDamage(0.6f) > Boarding::GrenadeDamage(0.3f));
  IV_CHECK(Boarding::GrenadeDamage(5.f) <= tune::kGrenadeDamageMax);
  IV_CHECK(tune::kGrenadeDamageMin >= 1.5f * tune::kHeavyDamage);
  IV_CHECK(tune::kGrenadeDamageMax <= 2.2f * tune::kHeavyDamage + 0.1f);
  IV_CHECK(tune::kBoardCooldownTicks >= MsToTicks(45000));
}

IV_TEST(Boarding, ShockCostsHackTime) {
  BRig r;
  r.Start();
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::Hacking; }));
  const int left0 = r.bd.hack().ticksLeft();
  r.duel.ExternalHit(r.owner, Zone::Torso, 4.f, 5.f, 0);
  r.Tick();
  IV_CHECK_EQ(r.Count(EventType::BoardingShock), 1);
  IV_CHECK(r.bd.hack().ticksLeft() < left0 - 40);
  IV_CHECK(r.bd.Active());   // the pilot is shaken, not killed
}

// ---------------------------------------------------------------------------------------------- the enemy hand

namespace {
BRig* RunToTelegraph(BRig& r) {
  r.bot = true;
  r.Start();
  r.Until([&] { return r.bd.phase() == BoardPhase::Hacking; });
  r.bot = false;
  r.bd.set_swat_chance_mult(1000.f);
  r.Until([&] { return r.bd.swatActive(); }, 400);
  return &r;
}
}  // namespace

IV_TEST(Boarding, SwatThenTimelySwingMovesToTheOtherShoulderAndKeepsProgress) {
  BRig r(Side::A, 11, Difficulty::Normal, 0.f);
  r.bot = true;
  r.Start();
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::Hacking; }));
  IV_CHECK(r.Until([&] { return r.bd.hack().progress() >= 0.5f; }, 3000));
  const float before = r.bd.hack().progress();
  const Arm onto = r.bd.shoulder();
  r.bot = false;
  r.bd.set_swat_chance_mult(1000.f);
  IV_CHECK(r.Until([&] { return r.bd.swatActive(); }, 600));
  IV_CHECK_EQ(r.Count(EventType::BoardingSwatTelegraph), 1);
  const Event* tg = r.Find(EventType::BoardingSwatTelegraph);
  IV_CHECK_EQ(tg->a, Index(onto));
  IV_CHECK_EQ(tg->b, tune::kSwatWindupTicks[static_cast<int>(Difficulty::Normal)]);
  IV_CHECK(r.Until([&] { return r.bd.swatTicksToImpact() <= tune::kSwingWindowTicks - 5; }, 800));
  r.bi.swing = true;
  r.Tick();
  IV_CHECK(r.bd.phase() == BoardPhase::HookSwing);
  IV_CHECK(r.bd.shoulder() == Other(onto));
  IV_CHECK(!r.bd.swatActive());
  IV_CHECK_EQ(r.Count(EventType::BoardingSwingOk), 1);
  IV_CHECK_NEAR(r.Find(EventType::BoardingSwingOk)->value, before * tune::kSwingKeepProgress, 0.1);
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::Hacking; }, 200));
  IV_CHECK(r.bd.hack().progress() <= before * tune::kSwingKeepProgress + 0.1f);
  IV_CHECK(r.bd.hack().progress() > 0.f);
  IV_CHECK_EQ(r.bd.hack().rerolls(), 1);
  r.Run(tune::kSwatWindupTicks[1]);   // the old swat would have landed by now: it hits the empty shoulder
  IV_CHECK(r.Count(EventType::BoardingSwatImpact) >= 1);
  IV_CHECK(!r.duel.result().over);
}

IV_TEST(Boarding, SwatWithoutPressSmashesThePilotAndEndsTheMatch) {
  BRig r(Side::A, 5, Difficulty::Hard, 0.f);
  RunToTelegraph(r);
  IV_CHECK(r.bd.swatActive());
  IV_CHECK(r.Until([&] { return r.duel.result().over; }, 600));
  IV_CHECK(r.duel.result().over);
  IV_CHECK(r.duel.result().reason == EndReason::PilotLost);
  IV_CHECK(r.duel.result().loser == Side::A);
  IV_CHECK(r.bd.phase() == BoardPhase::Smashed);
  IV_CHECK(r.bd.outcome() == BoardingOutcome::Smashed);
  IV_CHECK_EQ(r.Count(EventType::BoardingSmashed), 1);
  IV_CHECK_EQ(r.Count(EventType::MatchEnd), 1);
  IV_CHECK(r.Find(EventType::MatchEnd)->a == static_cast<int>(EndReason::PilotLost));
  IV_CHECK(!r.Me().autopilot);
  IV_CHECK(std::strcmp(Name(EndReason::PilotLost), "PilotLost") == 0);
}

IV_TEST(Boarding, PressTooLateIsIgnoredAndTheHandLands) {
  BRig r(Side::A, 5, Difficulty::Normal, 0.f);
  RunToTelegraph(r);
  IV_CHECK(r.bd.swatActive());
  IV_CHECK(r.Until([&] { return r.bd.swatTicksToImpact() < tune::kSwingMinTicks; }, 600));
  r.bi.swing = true;
  r.Tick();
  IV_CHECK(r.bd.phase() != BoardPhase::HookSwing);
  IV_CHECK(r.Until([&] { return r.duel.result().over; }, 100));
  IV_CHECK(r.duel.result().reason == EndReason::PilotLost);
}

IV_TEST(Boarding, PressTooEarlyMakesTheEnemyReAimOnce) {
  BRig r(Side::A, 5, Difficulty::Easy, 0.f);   // Easy: a long telegraph so there is room before the window opens
  RunToTelegraph(r);
  IV_CHECK(r.bd.swatActive());
  const Arm first = r.bd.shoulder();
  r.Run(tune::kSwatReadyTicks + 5);
  IV_CHECK(r.bd.swatTicksToImpact() > tune::kSwingWindowTicks);
  r.bi.swing = true;
  r.Tick();
  IV_CHECK(r.bd.phase() == BoardPhase::HookSwing);
  IV_CHECK(r.bd.shoulder() == Other(first));
  IV_CHECK(r.bd.swatActive());                                   // the hand follows
  IV_CHECK_EQ(r.Count(EventType::BoardingSwatAdjusted), 1);
  IV_CHECK(r.bd.swatTicksToImpact() >= tune::kBoardHookSwingTicks);
  // a second early press (now on the new shoulder, still in the "early" zone) is ignored: only one re-aim per swat
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::Hacking; }, 200));
  r.bi.swing = true;
  const int before = r.Count(EventType::BoardingSwatAdjusted);
  r.Tick();
  if (r.bd.swatTicksToImpact() > tune::kSwingWindowTicks) {
    IV_CHECK_EQ(r.Count(EventType::BoardingSwatAdjusted), before);
    IV_CHECK(r.bd.phase() == BoardPhase::Hacking);
  }
  // a correct press inside the window saves the pilot
  IV_CHECK(r.Until([&] { return r.bd.swatTicksToImpact() <= tune::kSwingWindowTicks - 4; }, 800));
  r.bi.swing = true;
  r.Tick();
  IV_CHECK(r.bd.phase() == BoardPhase::HookSwing);
  r.Run(100);
  IV_CHECK(!r.duel.result().over);
}

IV_TEST(Boarding, PressInTheVeryFirstMomentsIsIgnored) {
  BRig r(Side::A, 5, Difficulty::Easy, 0.f);
  RunToTelegraph(r);
  IV_CHECK(r.bd.swatActive());
  r.Run(2);
  r.bi.swing = true;
  r.Tick();
  IV_CHECK(r.bd.phase() == BoardPhase::Hacking);
  IV_CHECK_EQ(r.Count(EventType::BoardingSwingOk), 0);
}

IV_TEST(Boarding, SwingPressWithoutAnySwatDoesNothing) {
  BRig r;
  r.bot = true;
  r.Start();
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::Hacking; }));
  const Arm s = r.bd.shoulder();
  r.bi.swing = true;
  r.Tick();
  IV_CHECK(r.bd.phase() == BoardPhase::Hacking);
  IV_CHECK(r.bd.shoulder() == s);
}

IV_TEST(Boarding, TelegraphLengthsMeetTheTaskMinimums) {
  IV_CHECK(tune::kSwatWindupTicks[static_cast<int>(Difficulty::Easy)] >= MsToTicks(900));
  IV_CHECK(tune::kSwatWindupTicks[static_cast<int>(Difficulty::Hard)] >= MsToTicks(600));
  for (int d = 0; d < kDifficultyCount; ++d) IV_CHECK(tune::kSwatWindupTicks[d] > tune::kSwingWindowTicks - 1 || d == 2);
  IV_CHECK(tune::kSwingWindowTicks > tune::kSwingMinTicks);
}

IV_TEST(Boarding, WithoutAnotherShoulderTheSwingButtonRetreatsInstead) {
  BRig r(Side::A, 5, Difficulty::Normal, 0.f);
  r.Foe().body.ApplyDamage(Zone::ShoulderL, 2000.f, StrikeKind::Heavy);   // only the right shoulder is left
  r.bi.shoulder = Arm::R;
  RunToTelegraph(r);
  IV_CHECK(r.bd.swatActive());
  IV_CHECK(r.Until([&] { return r.bd.swatTicksToImpact() <= tune::kSwingWindowTicks - 4; }, 400));
  r.bi.swing = true;
  r.Tick();
  IV_CHECK(r.bd.phase() == BoardPhase::ReturnHook);
  IV_CHECK(!r.bd.swatActive());
  r.Run(200);
  IV_CHECK(!r.duel.result().over);
  IV_CHECK(r.bd.outcome() == BoardingOutcome::HackFailed);
  IV_CHECK_EQ(r.Count(EventType::BoardingSwingOk), 0);
  BRig q(Side::A, 5, Difficulty::Normal, 0.f);   // and without the press the same situation is lethal
  q.Foe().body.ApplyDamage(Zone::ShoulderL, 2000.f, StrikeKind::Heavy);
  q.bi.shoulder = Arm::R;
  RunToTelegraph(q);
  IV_CHECK(q.Until([&] { return q.duel.result().over; }, 600));
  IV_CHECK(q.duel.result().reason == EndReason::PilotLost);
}

IV_TEST(Boarding, SwatsAreLimitedAndHaveAGracePeriod) {
  BRig r(Side::A, 21, Difficulty::Hard, 0.f);
  r.bot = false;
  r.Start();
  r.bd.set_swat_chance_mult(1000.f);
  int firstTelegraph = -1;
  int ticks = 0;
  // The pilot always answers correctly: count the swats over a long hack.
  while (r.bd.Active() && ticks < 4000) {
    if (r.bd.swatActive() && r.bd.swatTicksToImpact() <= tune::kSwingWindowTicks - 4 && r.bd.phase() != BoardPhase::HookSwing) r.bi.swing = true;
    r.Tick();
    ++ticks;
    if (firstTelegraph < 0 && r.Count(EventType::BoardingSwatTelegraph) > 0) firstTelegraph = ticks;
  }
  IV_CHECK(r.Count(EventType::BoardingSwatTelegraph) <= tune::kMaxSwatsPerBoarding);
  IV_CHECK(r.Count(EventType::BoardingSwatTelegraph) >= 1);
  IV_CHECK(!r.duel.result().over);
  // no telegraph earlier than the late flight: ClimbOut + OnShoulder + HookLaunch + 70 % of the flight
  const int minStart = tune::kBoardClimbOutTicks + tune::kBoardOnShoulderTicks + tune::kBoardHookLaunchTicks + tune::kBoardHookFlightTicks * 7 / 10;
  IV_CHECK(firstTelegraph >= minStart);
}

IV_TEST(Boarding, EnemyWithoutTheSwattingArmCannotSwat) {
  BRig r(Side::A, 5, Difficulty::Hard, 0.f);
  r.bi.shoulder = Arm::R;
  r.Foe().body.ApplyDamage(Zone::ArmL, 2000.f, StrikeKind::Heavy);   // the hand that would reach the right shoulder
  r.bot = true;
  r.Start();
  r.bd.set_swat_chance_mult(1000.f);
  IV_CHECK(r.Until([&] { return r.Finished(); }, 20000));
  IV_CHECK_EQ(r.Count(EventType::BoardingSwatTelegraph), 0);
  IV_CHECK(r.bd.outcome() == BoardingOutcome::Success);
}

IV_TEST(Boarding, ShoulderDestroyedDuringTheHackSwingsToTheOtherOne) {
  BRig r;
  r.bot = true;
  r.Start();
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::Hacking; }));
  r.bot = false;
  const Arm s = r.bd.shoulder();
  r.Foe().body.ApplyDamage(ShoulderZone(s), 2000.f, StrikeKind::Heavy);
  r.Tick();
  IV_CHECK(r.bd.phase() == BoardPhase::HookSwing);
  IV_CHECK(r.bd.shoulder() == Other(s));
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::Hacking; }, 200));
  // the other one goes too: the pilot has nowhere to stand and returns
  r.Foe().body.ApplyDamage(ShoulderZone(Other(s)), 2000.f, StrikeKind::Heavy);
  r.Tick();
  IV_CHECK(r.bd.phase() == BoardPhase::ReturnHook);
  IV_CHECK(r.Until([&] { return r.Finished(); }, 4000));
  IV_CHECK(r.bd.outcome() == BoardingOutcome::HackFailed);
}

IV_TEST(Boarding, ShoulderDestroyedBeforeTheHookRetargets) {
  BRig r;
  r.bi.shoulder = Arm::L;
  r.Start();
  IV_CHECK(r.bd.shoulder() == Arm::L);
  r.Foe().body.ApplyDamage(Zone::ShoulderL, 2000.f, StrikeKind::Heavy);
  r.Run(3);
  IV_CHECK(r.bd.shoulder() == Arm::R);
  IV_CHECK(r.bd.phase() == BoardPhase::ClimbOut);
}

IV_TEST(Boarding, BlastFallsBackToTheArmWhenTheShoulderIsGone) {
  BRig r;
  r.bot = true;
  r.Start();
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::GrenadeThrow; }, 20000));
  const Arm s = r.bd.shoulder();
  r.Foe().body.ApplyDamage(ShoulderZone(s), 2000.f, StrikeKind::Heavy);   // the hatch hangs open already
  IV_CHECK(Boarding::BlastZone(r.duel, r.owner == Side::A ? Side::B : Side::A, s) == ArmZone(s));
  IV_CHECK(r.Until([&] { return r.Finished(); }, 4000));
  IV_CHECK_EQ(r.Count(EventType::BoardingBlast), 1);
  IV_CHECK(r.Find(EventType::BoardingBlast)->zone == ArmZone(s));
}

// ---------------------------------------------------------------------------------------------- autopilot, symmetry, determinism

IV_TEST(Boarding, AutopilotNeverAttacksAndDefends) {
  BRig r;
  r.duel.set_distance(14.f);
  r.Start();
  // the player keeps mashing attack buttons; the enemy keeps swinging heavy blows at the torso
  int attackerTicks = 0;
  for (int i = 0; i < 1500 && r.bd.Active(); ++i) {
    r.MyIn().strikeHeld = true;
    r.MyIn().weaponHeld = true;
    r.MyIn().ultimate = true;
    r.MyIn().quick = (i % 7) == 0;
    r.b.strikeHeld = (i % 120) < 60;
    r.b.side = (i / 120) % 2 ? SwingSide::Left : SwingSide::Down;
    r.b.target = Zone::Torso;
    r.Tick();
    if (r.Me().phase == Phase::Windup || r.Me().phase == Phase::Strike || r.Me().phase == Phase::Contact || r.Me().weaponCharging) ++attackerTicks;
  }
  IV_CHECK_EQ(attackerTicks, 0);
  IV_CHECK_EQ(r.Count(EventType::WindupStarted) > 0 ? 1 : 0, 1);   // the enemy did swing
  int mine = 0;
  for (const Event& e : r.duel.log().events())
    if (e.actor == r.owner && (e.type == EventType::WindupStarted || e.type == EventType::WeaponCharging || e.type == EventType::UltimateUsed)) ++mine;
  IV_CHECK_EQ(mine, 0);
  int defended = 0;
  for (const Event& e : r.duel.log().events())
    if (e.actor == r.owner && (e.type == EventType::Blocked || e.type == EventType::ParrySuccess || e.type == EventType::Evaded || e.type == EventType::Dodge || e.type == EventType::HardStanceOn)) ++defended;
  IV_CHECK(defended > 0);
}

IV_TEST(Boarding, DuelStripsOffensiveInputsOfAnAutopilotFighter) {
  Duel d(3, true);
  d.set_distance(30.f);
  d.fighter(Side::A).set_autopilot(true);
  Input in;
  in.strikeHeld = true;
  in.quick = true;
  in.weaponHeld = true;
  in.ultimate = true;
  for (int i = 0; i < 120; ++i) d.Step(in, Input());
  IV_CHECK_EQ(d.log().CountOf(EventType::WindupStarted), 0);
  IV_CHECK(d.fighter(Side::A).phase == Phase::Idle);
  d.fighter(Side::A).set_autopilot(false);
  in.weaponHeld = false;
  in.ultimate = false;
  for (int i = 0; i < 30; ++i) d.Step(in, Input());
  IV_CHECK(d.fighter(Side::A).phase != Phase::Idle);
}

IV_TEST(Boarding, WorksForSideB) {
  BRig r(Side::B, 9);
  r.bot = true;
  const float hp0 = TotalHp(r.duel.fighter(Side::A));
  r.Start();
  IV_CHECK(r.Until([&] { return r.Finished(); }, 20000));
  IV_CHECK(r.bd.outcome() == BoardingOutcome::Success);
  IV_CHECK(TotalHp(r.duel.fighter(Side::A)) < hp0);
  IV_CHECK(r.Find(EventType::BoardingBlast)->actor == Side::B);
  IV_CHECK(!r.duel.fighter(Side::B).autopilot);
}

IV_TEST(Boarding, SmashedPilotOfSideBLosesForSideB) {
  BRig r(Side::B, 9, Difficulty::Hard, 0.f);
  RunToTelegraph(r);
  IV_CHECK(r.Until([&] { return r.duel.result().over; }, 600));
  IV_CHECK(r.duel.result().loser == Side::B);
  IV_CHECK(r.duel.result().reason == EndReason::PilotLost);
}

namespace {
struct RunSummary {
  uint64_t logHash, bdHash;
  int ticks;
};
RunSummary ScriptedRun(uint64_t seed) {
  BRig r(Side::A, seed, Difficulty::Hard, 6.f);
  r.bot = false;
  Rng ctl(seed * 31 + 1);
  r.Start();
  int t = 0;
  for (; t < 5000 && !r.duel.result().over; ++t) {
    if (r.bd.phase() == BoardPhase::Hacking && ctl.Chance(0.9f)) r.bi.hack = r.bd.hack().PerfectInput();
    if (r.bd.swatActive() && r.bd.swatTicksToImpact() < tune::kSwingWindowTicks - 6) r.bi.swing = true;
    r.Tick();
  }
  return {r.duel.log().hash(), r.bd.Hash(), t};
}
}  // namespace

IV_TEST(Boarding, DeterministicForEqualSeedAndInput) {
  const RunSummary a = ScriptedRun(77);
  const RunSummary b = ScriptedRun(77);
  IV_CHECK_EQ(a.logHash, b.logHash);
  IV_CHECK_EQ(a.bdHash, b.bdHash);
  IV_CHECK_EQ(a.ticks, b.ticks);
  const RunSummary c = ScriptedRun(78);
  IV_CHECK(c.logHash != a.logHash || c.bdHash != a.bdHash);
}

// ---------------------------------------------------------------------------------------------- fuzz

IV_TEST(Boarding, FuzzRandomInputsNeverHangAndAlwaysSettle) {
  int boardings = 0, smashed = 0, successes = 0;
  long long ticksRun = 0;
  int reasons[8] = {};
  const int kRuns = 2000;
  for (int run = 0; run < kRuns; ++run) {
    const uint64_t seed = 5000 + static_cast<uint64_t>(run);
    Rng ctl(seed * 977 + 13);
    BRig r(ctl.Chance(0.5f) ? Side::A : Side::B, seed, static_cast<Difficulty>(ctl.Below(3)), 1.f + static_cast<float>(ctl.Below(8)),
           static_cast<Archetype>(ctl.Below(kArchetypeCount)));
    r.duel.set_distance(25.f + static_cast<float>(ctl.Below(40)));
    const int total = 5 * 60 * kTickHz;   // five minutes of game time
    int was = 0;
    for (int t = 0; t < total && !r.duel.result().over; ++t) {
      // random player and enemy intent
      Input& me = r.MyIn();
      me.strikeHeld = ctl.Chance(0.05f);
      me.side = static_cast<SwingSide>(ctl.Below(4));
      me.guardHeld = ctl.Chance(0.4f);
      me.quick = ctl.Chance(0.02f);
      me.dodge = ctl.Chance(0.01f);
      me.weaponHeld = ctl.Chance(0.01f);
      Input& foe = r.owner == Side::A ? r.b : r.a;
      foe.strikeHeld = ctl.Chance(0.04f);
      foe.side = static_cast<SwingSide>(ctl.Below(4));
      foe.guardHeld = ctl.Chance(0.3f);
      r.bi.start = ctl.Chance(0.01f);
      r.bi.swing = ctl.Chance(0.05f);
      r.bi.shoulder = ctl.Chance(0.5f) ? Arm::L : Arm::R;
      r.bi.hack.confirm = ctl.Chance(0.2f);
      r.bi.hack.back = ctl.Chance(0.0005f);
      const bool wasActive = r.bd.Active();
      r.Tick();
      ++ticksRun;
      if (!wasActive && r.bd.Active()) ++was;
      if (ctl.Chance(0.001f)) r.Foe().body.ApplyDamage(ctl.Chance(0.5f) ? Zone::ShoulderL : Zone::ShoulderR, 3000.f, StrikeKind::Heavy);
    }
    boardings += was;
    ++reasons[static_cast<int>(r.duel.result().reason)];
    // let it settle with no further starts: the boarding must reach Idle / Done / Smashed on its own
    r.bi = BoardingInput();
    r.bot = true;
    int guard = 0;
    while (r.bd.Active() && !r.duel.result().over && guard < 8000) {
      r.Tick();
      ++guard;
    }
    IV_CHECK(!r.bd.Active());
    if (r.bd.outcome() == BoardingOutcome::Smashed) ++smashed;
    if (r.bd.outcome() == BoardingOutcome::Success) ++successes;
    IV_CHECK(r.bd.phase() == BoardPhase::Idle || r.bd.phase() == BoardPhase::Done || r.bd.phase() == BoardPhase::Smashed);
    IV_CHECK(!r.Me().autopilot);
  }
  IV_CHECK(boardings > 500);   // the fuzz really boarded
  IV_CHECK(ticksRun > static_cast<long long>(kRuns) * 3 * 60 * kTickHz / 5);   // and really ran for minutes of game time (some duels end early)
  std::printf("    fuzz: %d runs, %lld ticks, %d boardings, %d successes, %d smashed; end reasons none/reactor/cockpit/immobile/power/arms/time/pilot: %d %d %d %d %d %d %d %d\n", kRuns, ticksRun, boardings, successes, smashed, reasons[0], reasons[1], reasons[2], reasons[3], reasons[4], reasons[5], reasons[6], reasons[7]);
}


// ---------------------------------------------------------------------------------------------- v6: the human defender slaps his own shoulder
namespace {
BoardingConfig HumanCfg(Side o, uint64_t seed) {
  BoardingConfig c;
  c.owner = o;
  c.seed = seed;
  c.enemyIsHuman = true;
  c.swatChanceMult = 0.f;
  return c;
}
void RunToHacking(BRig& r) {
  r.Start();
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::Hacking; }, 2000));
  r.Run(tune::kSwatGraceTicks + 5);
}
}  // namespace

IV_TEST(BoardingV6, ADefenderWhoDoesNotPressNeverSwats) {
  BRig r(Side::A, 11);
  r.bd = Boarding(HumanCfg(Side::A, 11));
  RunToHacking(r);
  r.Run(600);
  IV_CHECK(!r.bd.swatActive());
  IV_CHECK_EQ(r.Count(EventType::BoardingSwatTelegraph), 0);
}

IV_TEST(BoardingV6, ASlapStunsThePilotFor5SecondsTheEmptyMechIsHelplessThenHeReturns) {
  BRig r(Side::A, 11);
  r.bd = Boarding(HumanCfg(Side::A, 11));
  RunToHacking(r);
  r.bi.swat = true;
  r.Tick();
  IV_CHECK(r.bd.swatActive());
  IV_CHECK_EQ(r.Count(EventType::BoardingSwatTelegraph), 1);
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::Stunned; }, tune::kHumanSwatWindupTicks + 10));
  IV_CHECK(r.bd.outcome() == BoardingOutcome::Slapped);
  IV_CHECK_EQ(r.Count(EventType::BoardingSmashed), 1);
  IV_CHECK(!r.duel.result().over);
  // while he lies there the empty mech does nothing at all
  const Input idle = r.bd.Filter(r.duel, r.MyIn());
  IV_CHECK(!idle.guardHeld && !idle.dodge && idle.move == 0 && !idle.strikeHeld);
  IV_CHECK(r.Me().autopilot);   // takes extra damage (kAutopilotDamageMult)
  r.Run(tune::kBoardStunTicks / 2);
  IV_CHECK(r.bd.phase() == BoardPhase::Stunned);
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::ReturnHook; }, tune::kBoardStunTicks));
  // exactly 5 s on the shoulder
  int stunTick = -1, returnTick = -1;
  for (const Event& e : r.duel.log().events()) {
    if (e.type != EventType::BoardingPhase) continue;
    if (e.a == static_cast<int>(BoardPhase::Stunned)) stunTick = e.tick;
    if (e.a == static_cast<int>(BoardPhase::ReturnHook)) returnTick = e.tick;
  }
  IV_CHECK(stunTick >= 0 && returnTick > stunTick);
  IV_CHECK_NEAR(static_cast<float>(returnTick - stunTick), static_cast<float>(tune::kBoardStunTicks), 3.f);
  IV_CHECK(r.Until([&] { return !r.bd.Active(); }, tune::kBoardReturnHookTicks + tune::kBoardClimbInTicks + 20));
  IV_CHECK(r.bd.phase() == BoardPhase::Done);
  IV_CHECK(r.bd.outcome() == BoardingOutcome::Slapped);
  IV_CHECK(!r.Me().autopilot);
  IV_CHECK(!r.duel.result().over);
  IV_CHECK(r.bd.cooldownLeft() > 0);
}

IV_TEST(BoardingV6, TheEmptyMechCanBeHitHardWhileThePilotLiesStunned) {
  BRig r(Side::A, 11);
  r.bd = Boarding(HumanCfg(Side::A, 11));
  RunToHacking(r);
  r.bi.swat = true;
  r.Tick();
  IV_CHECK(r.Until([&] { return r.bd.phase() == BoardPhase::Stunned; }, tune::kHumanSwatWindupTicks + 10));
  const float hp0 = TotalHp(r.Me());
  r.duel.set_distance(8.f);
  r.b.strikeHeld = true;
  r.b.side = SwingSide::Up;
  r.b.target = Zone::Torso;
  r.Run(tune::kWindupMinTicks);
  r.b.strikeHeld = false;
  r.Run(120);
  IV_CHECK(TotalHp(r.Me()) < hp0 - 5.f);
  IV_CHECK(r.bd.phase() == BoardPhase::Stunned || r.bd.phase() == BoardPhase::ReturnHook);
}

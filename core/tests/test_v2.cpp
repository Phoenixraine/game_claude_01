// v2 (TASK-001 update): heavy weapons, ultimate and cinematics, presentation events, animation state, training dummy.
#include "TestUtil.h"
#include "iv/Anim.h"

using namespace iv;
using namespace ivtest;

namespace {
// Holds the weapon button until the charge is complete, then releases it. Returns the ticks used.
int ChargeAndFire(Rig& r, int extra = 0) {
  const int need = r.A().WeaponProf().chargeTicks + extra;
  r.a.weaponHeld = true;
  r.a.target = Zone::Torso;
  int used = 0;
  while (used < need + 600 && r.A().weaponCharge < static_cast<float>(need)) {
    r.Step();
    ++used;
  }
  r.a.weaponHeld = false;
  r.Step();
  return used + 1;
}

void FillUltimate(Fighter& f) { f.ultimate = tune::kUltimateMax; }
// v6: the button starts a windup punch; this runs it to the contact (nobody countered)
void RunUltWind(Rig& r) { r.Step(tune::kUltWindupTicks); }

const Event* Find(const Rig& r, EventType t, int from = 0) {
  const auto& ev = r.duel.log().events();
  for (size_t i = static_cast<size_t>(from); i < ev.size(); ++i)
    if (ev[i].type == t) return &ev[i];
  return nullptr;
}
int IndexOf(const Rig& r, EventType t) {
  const auto& ev = r.duel.log().events();
  for (size_t i = 0; i < ev.size(); ++i)
    if (ev[i].type == t) return static_cast<int>(i);
  return -1;
}
}  // namespace

// ------------------------------------------------------------------------------------------------ weapons

IV_TEST(Weapons, ProfilesDescribeThreeDistinctWeaponsWithLargeCooldowns) {
  const auto& rail = tune::kWeapons[Index(WeaponKind::RailSpear)];
  const auto& rock = tune::kWeapons[Index(WeaponKind::SuppressionRockets)];
  const auto& plasma = tune::kWeapons[Index(WeaponKind::PlasmaCannon)];
  IV_CHECK(rail.chargeTicks > plasma.chargeTicks && plasma.chargeTicks > rock.chargeTicks);  // rail is the slowest to charge
  IV_CHECK(rail.locksLegs && !rock.locksLegs && !plasma.locksLegs);
  IV_CHECK(rock.salvo > 1 && rock.ammo > 0 && rail.ammo < 0 && plasma.ammo < 0);
  IV_CHECK(plasma.heatPerShot > rail.heatPerShot && plasma.heatPerShot > rock.heatPerShot);
  for (const auto& w : tune::kWeapons) IV_CHECK(w.cooldownTicks >= MsToTicks(5000));  // "large reload"
  IV_CHECK(rail.damage > plasma.damage && plasma.damage > rock.damage);
}

IV_TEST(Weapons, ChargingRailSpearLocksTheLegs) {
  Rig r(1, 60.f);
  r.duel.SetLoadout(Side::A, WeaponKind::RailSpear);
  r.a.weaponHeld = true;
  r.Step(5);
  IV_CHECK(r.A().weaponCharging);
  IV_CHECK(r.A().LegsLocked());
  const float d0 = r.duel.distance();
  r.a.move = 1;
  r.Step(30);
  IV_CHECK_NEAR(r.duel.distance(), d0, 1e-4f);  // no stepping while the feet are fixed
  r.a.dodge = true;
  r.Step();
  IV_CHECK(r.A().posture == Posture::Standing);  // and no dodge either
  IV_CHECK(MakeAnimState(r.A()).legsLocked);
}

IV_TEST(Weapons, PlasmaCannonDoesNotLockTheLegsButRunsHot) {
  Rig r(2, 60.f);
  r.duel.SetLoadout(Side::A, WeaponKind::PlasmaCannon);
  r.a.weaponHeld = true;
  r.Step(5);
  IV_CHECK(r.A().weaponCharging);
  IV_CHECK(!r.A().LegsLocked());
  Rig q(2, 60.f);
  q.duel.SetLoadout(Side::A, WeaponKind::PlasmaCannon);
  const float h0 = q.A().res.heat;
  ChargeAndFire(q);
  IV_CHECK(q.Count(EventType::WeaponFired) == 1);
  IV_CHECK(q.A().res.heat > h0 + tune::kWeapons[Index(WeaponKind::PlasmaCannon)].heatPerShot * 0.5f);
}

IV_TEST(Weapons, ShotStartsTheCooldownAndBlocksTheNextCharge) {
  Rig r(3, 60.f);
  ChargeAndFire(r);
  IV_CHECK_EQ(r.Count(EventType::WeaponFired), 1);
  const Event* fired = Find(r, EventType::WeaponFired);
  IV_CHECK(fired != nullptr && fired->b == Index(WeaponKind::RailSpear));
  // the cut-scene plays first; afterwards the cooldown is running and charging is refused
  r.StepUntil([&] { return !r.duel.cinematic().active; });
  IV_CHECK(r.A().weaponCooldown > 0);
  const int charges = r.Count(EventType::WeaponCharging);
  r.a.weaponHeld = true;
  r.Step(200);
  IV_CHECK_EQ(r.Count(EventType::WeaponCharging), charges);
  IV_CHECK(!r.A().weaponCharging);
}

IV_TEST(Weapons, CooldownEndsWithAWeaponReadyEventAndTheWeaponWorksAgain) {
  Rig r(4, 60.f);
  ChargeAndFire(r);
  r.a.weaponHeld = false;
  r.StepUntil([&] { return !r.duel.cinematic().active; });
  r.StepUntil([&] { return r.A().weaponCooldown == 0; }, 5000);
  IV_CHECK_EQ(r.Count(EventType::WeaponReady), 1);
  r.A().res.heat = 0.f;
  r.a.weaponHeld = true;
  r.Step(3);
  IV_CHECK(r.A().weaponCharging);
}

IV_TEST(Weapons, RocketRackRunsDryAfterThreeSalvos) {
  Rig r(5, 60.f);
  r.duel.SetLoadout(Side::A, WeaponKind::SuppressionRockets);
  IV_CHECK_EQ(r.A().weaponAmmo, 3);
  for (int shot = 0; shot < 3; ++shot) {
    ChargeAndFire(r);
    r.a.weaponHeld = false;
    r.StepUntil([&] { return !r.duel.cinematic().active; });
    r.StepUntil([&] { return r.A().weaponCooldown == 0; }, 5000);
    r.A().res.heat = 0.f;
  }
  IV_CHECK_EQ(r.Count(EventType::WeaponFired), 3);
  IV_CHECK_EQ(r.Count(EventType::WeaponEmpty), 1);
  IV_CHECK_EQ(r.A().weaponAmmo, 0);
  const int c = r.Count(EventType::WeaponCharging);
  r.a.weaponHeld = true;
  r.Step(120);
  IV_CHECK_EQ(r.Count(EventType::WeaponCharging), c);  // out of rockets
}

IV_TEST(Weapons, SalvoReportsTheNumberOfHitsAndNeverMoreThanTheSalvo) {
  int total = 0;
  for (uint64_t seed = 1; seed <= 12; ++seed) {
    Rig r(seed, 60.f);
    r.duel.SetLoadout(Side::A, WeaponKind::SuppressionRockets);
    ChargeAndFire(r);
    const Event* e = Find(r, EventType::WeaponFired);
    IV_CHECK(e != nullptr);
    IV_CHECK(e->a >= 0 && e->a <= tune::kWeapons[Index(WeaponKind::SuppressionRockets)].salvo);
    IV_CHECK_EQ(e->b, Index(WeaponKind::SuppressionRockets));
    total += e->a;
  }
  IV_CHECK(total > 12);  // most rockets land at this range
}

IV_TEST(Weapons, ReleasingTooEarlyFiresNothingAndCostsNoCooldown) {
  Rig r(6, 60.f);
  r.a.weaponHeld = true;
  r.Step(40);
  r.a.weaponHeld = false;
  r.Step(2);
  IV_CHECK_EQ(r.Count(EventType::WeaponFired), 0);
  IV_CHECK_EQ(r.A().weaponCooldown, 0);
  IV_CHECK(!r.duel.cinematic().active);
}

IV_TEST(Weapons, ShotAtPointBlankRangeMisses) {
  Rig r(7, tune::kWeaponMinDistance - 4.f);
  ChargeAndFire(r);
  const Event* e = Find(r, EventType::WeaponFired);
  IV_CHECK(e != nullptr);
  IV_CHECK_EQ(e->a, 0);
}

IV_TEST(Weapons, ADamagingHitBreaksTheCharge) {
  Rig r(8, 20.f);
  r.a.weaponHeld = true;
  r.Step(30);
  IV_CHECK(r.A().weaponCharging);
  const StepContext ctx = {};
  r.A().TakeHit(Zone::Torso, 10.f, StrikeKind::Heavy, 5.f, ctx);
  IV_CHECK(!r.A().weaponCharging);
  r.a.weaponHeld = false;
  r.Step(3);
  IV_CHECK_EQ(r.Count(EventType::WeaponFired), 0);
}

// ------------------------------------------------------------------------------------------------ ultimate

IV_TEST(Ultimate, GaugeStartsEmptyClampsAndAnnouncesReadinessOnce) {
  Rig r;
  IV_CHECK_EQ(r.A().ultimate, 0.f);
  StepContext ctx;
  ctx.log = &r.duel.log();
  r.A().GainUltimate(60.f, ctx);
  IV_CHECK(!r.A().UltimateReady());
  r.A().GainUltimate(60.f, ctx);
  IV_CHECK(r.A().UltimateReady());
  IV_CHECK_EQ(r.A().ultimate, tune::kUltimateMax);
  r.A().GainUltimate(10.f, ctx);
  IV_CHECK_EQ(r.Count(EventType::UltimateReady), 1);
}

IV_TEST(Ultimate, OnlyCountersChargeTheGaugeAndTheyChargeItMoreWhenHurt) {
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
  for (int i = 0; i < 60 && r.B().body.Integrity() > 0.4f; ++i) {
    r.B().TakeHit(Zone::Torso, 30.f, StrikeKind::Heavy, 0.f, ctx);
    r.B().TakeHit(Zone::ArmL, 30.f, StrikeKind::Heavy, 0.f, ctx);
    r.B().TakeHit(Zone::LegR, 30.f, StrikeKind::Heavy, 0.f, ctx);
  }
  IV_CHECK(r.B().body.Integrity() < 0.95f);
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

IV_TEST(Ultimate, ButtonDoesNothingWithAnEmptyGauge) {
  Rig r;
  r.a.ultimate = true;
  r.Step(3);
  IV_CHECK_EQ(r.Count(EventType::UltimateUsed), 0);
  IV_CHECK(!r.duel.cinematic().active);
}

IV_TEST(Ultimate, FullGaugeTriggersTheCinematicAndConsumesTheGauge) {
  Rig r(1, 30.f);
  FillUltimate(r.A());
  const float before = TotalHp(r.B());
  r.a.ultimate = true;
  r.a.target = Zone::Torso;
  r.Step();
  IV_CHECK_EQ(r.Count(EventType::UltimateStarted), 1);   // v6: the punch comes first
  IV_CHECK_EQ(r.A().ultimate, 0.f);
  IV_CHECK(!r.duel.cinematic().active);
  RunUltWind(r);
  IV_CHECK_EQ(r.Count(EventType::UltimateUsed), 1);
  IV_CHECK_EQ(r.A().ultimate, 0.f);
  IV_CHECK(r.duel.cinematic().active);
  IV_CHECK(r.duel.cinematic().kind == CinematicKind::UltimateSever || r.duel.cinematic().kind == CinematicKind::UltimateBisect);
  const Event* b = Find(r, EventType::CinematicBegin);
  IV_CHECK(b != nullptr && (b->a == static_cast<int>(CinematicKind::UltimateSever) || b->a == static_cast<int>(CinematicKind::UltimateBisect)) && b->b == tune::kUltimateCinematicTicks);
  IV_CHECK(TotalHp(r.B()) < before - 20.f);
  IV_CHECK(Find(r, EventType::HitEvent) != nullptr);
}

IV_TEST(Ultimate, FightIsFrozenDuringTheCutAndInputsAreIgnored) {
  Rig r(1, 30.f);
  FillUltimate(r.A());
  r.a.ultimate = true;
  r.Step();
  RunUltWind(r);
  const Tick t0 = r.duel.tick();
  const float d0 = r.duel.distance();
  r.b.strikeHeld = true;
  r.b.move = 1;
  r.Step(tune::kUltimateCinematicTicks - 3);
  IV_CHECK(r.duel.cinematic().active);
  IV_CHECK(r.B().phase == Phase::Idle);
  IV_CHECK_NEAR(r.duel.distance(), d0, 1e-5f);
  IV_CHECK(r.duel.tick() > t0);  // the clock still runs: the cut has a fixed duration
  IV_CHECK_EQ(Find(r, EventType::WindupStarted) == nullptr ? 0 : 1, 0);
}

IV_TEST(Ultimate, CutEndsWithTheTargetStaggeredAndTheShooterProtected) {
  Rig r(1, 30.f);
  FillUltimate(r.A());
  r.a.ultimate = true;
  r.Step();
  RunUltWind(r);
  r.Step(tune::kUltimateCinematicTicks + 2);
  IV_CHECK(!r.duel.cinematic().active);
  IV_CHECK_EQ(r.Count(EventType::CinematicEnd), 1);
  IV_CHECK(r.B().posture == Posture::Staggered || r.B().posture == Posture::KnockedDown);
  IV_CHECK(r.A().protectedTicks > 0);
  StepContext ctx;
  const float hp = TotalHp(r.A());
  const HitReport h = r.A().TakeHit(Zone::Torso, 50.f, StrikeKind::Heavy, 50.f, ctx);
  IV_CHECK_EQ(h.dealt, 0.f);
  IV_CHECK_EQ(TotalHp(r.A()), hp);
  r.Step(tune::kCinematicProtectTicks + 2);
  IV_CHECK_EQ(r.A().protectedTicks, 0);
  IV_CHECK(r.A().TakeHit(Zone::Torso, 5.f, StrikeKind::Heavy, 0.f, ctx).dealt > 0.f);
}

IV_TEST(Ultimate, MatchEndWaitsForTheCutToFinish) {
  Rig q(1, 30.f);
  // the opponent's reactor is nearly gone and the ultimate hits it from behind: the match must end only after the cut
  FillUltimate(q.A());
  q.B().flank = 180.f;
  q.a.ultimate = true;
  q.a.target = Zone::Reactor;
  for (int z = 0; z < 2; ++z) q.B().body.ApplyDamage(Zone::Reactor, 60.f, StrikeKind::Quick);
  q.Step();
  RunUltWind(q);
  const int endIdx = IndexOf(q, EventType::MatchEnd);
  if (endIdx >= 0) {
    IV_CHECK(IndexOf(q, EventType::CinematicEnd) >= 0);
    IV_CHECK(IndexOf(q, EventType::CinematicEnd) < endIdx);
  }
  q.Step(tune::kUltimateCinematicTicks + 3);
  IV_CHECK(q.duel.result().over);
  IV_CHECK(IndexOf(q, EventType::CinematicEnd) < IndexOf(q, EventType::MatchEnd));
}

IV_TEST(Ultimate, WeaponShotsCutToTheirOwnCinematicKind) {
  const CinematicKind expect[3] = {CinematicKind::RailSpear, CinematicKind::SuppressionRockets, CinematicKind::PlasmaCannon};
  for (int k = 0; k < kWeaponKindCount; ++k) {
    Rig r(9, 60.f);
    r.duel.SetLoadout(Side::A, static_cast<WeaponKind>(k));
    ChargeAndFire(r);
    IV_CHECK(r.duel.cinematic().active);
    IV_CHECK(r.duel.cinematic().kind == expect[k]);
    const Event* b = Find(r, EventType::CinematicBegin);
    IV_CHECK(b != nullptr);
    IV_CHECK_EQ(b->b, tune::kWeapons[k].cinematicTicks);
    IV_CHECK(tune::kWeapons[k].cinematicTicks >= MsToTicks(1500) && tune::kWeapons[k].cinematicTicks <= MsToTicks(3500));  // 1.5-3.5 s
  }
}

// ---------------------------------------------------------------------------------------- presentation

IV_TEST(Presentation, EveryLandedHitProducesAHitEventWithAllFields) {
  Rig r(1, 12.f);
  r.StartHeavyA(SwingSide::Right, Zone::Torso);
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; });
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));
  const Event* e = Find(r, EventType::HitEvent);
  IV_CHECK(e != nullptr);
  HitInfo h;
  IV_CHECK(DecodeHit(*e, &h));
  IV_CHECK(h.attacker == Side::A);
  IV_CHECK(h.zone == Zone::Torso);
  IV_CHECK(h.layer == Layer::Armor);
  IV_CHECK(h.direction == SwingSide::Right);
  IV_CHECK(!h.wasBlocked && !h.wasParried);
  IV_CHECK(h.damage > 0.f && h.stabilityDamage > 0.f);
  IV_CHECK(h.severity >= ZoneState::Intact);
  const Event* plain = Find(r, EventType::Hit);
  IV_CHECK(plain != nullptr && std::fabs(plain->value - h.damage) < 1e-4f);
}

IV_TEST(Presentation, BlockedHitsAreFlaggedAndParriesCarryZeroDamage) {
  Rig r(1, 12.f);
  r.b.guardHeld = true;
  r.b.guardSide = SwingSide::Up;
  r.Step(tune::kBlockRaiseTicks + 4);
  r.StartHeavyA(SwingSide::Up, Zone::Torso);
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; });
  IV_CHECK(r.LastOutcome(Side::A) == static_cast<int>(Outcome::Blocked) || r.LastOutcome(Side::A) == static_cast<int>(Outcome::Parried));
  bool sawFlag = false;
  for (const Event& e : r.duel.log().events()) {
    HitInfo h;
    if (DecodeHit(e, &h) && (h.wasBlocked || h.wasParried)) sawFlag = true;
  }
  IV_CHECK(sawFlag);
}

IV_TEST(Presentation, ArmourPlatesComeOffOneByOneAsTheArmourDrains) {
  Rig r;
  StepContext ctx;
  ctx.log = &r.duel.log();
  const int plates = tune::kArmorPlates[Index(Zone::ArmL)];
  for (int i = 0; i < 40 && r.B().body.layer(Zone::ArmL, Layer::Armor) > 0.f; ++i) r.B().TakeHit(Zone::ArmL, 3.f, StrikeKind::Quick, 0.f, ctx);
  IV_CHECK_EQ(r.Count(EventType::ArmorPlateLost), plates);
  bool seen[16] = {};
  for (const Event& e : r.duel.log().events()) {
    if (e.type != EventType::ArmorPlateLost) continue;
    IV_CHECK(e.zone == Zone::ArmL);
    IV_CHECK(e.a >= 0 && e.a < plates && !seen[e.a]);
    IV_CHECK_EQ(e.b, plates);
    seen[e.a] = true;
  }
}

IV_TEST(Presentation, ReactorBreachAndSystemFailuresAnnounceThemselvesOnce) {
  Rig r;
  StepContext ctx;
  ctx.log = &r.duel.log();
  for (int i = 0; i < 60 && r.B().body.state(Zone::Reactor) < ZoneState::Critical; ++i) r.B().TakeHit(Zone::Reactor, 5.f, StrikeKind::Quick, 0.f, ctx);
  IV_CHECK_EQ(r.Count(EventType::ReactorBreach), 1);
  int power = 0;
  for (const Event& e : r.duel.log().events())
    if (e.type == EventType::SystemFailure && e.a == static_cast<int>(SystemId::Power)) ++power;
  IV_CHECK_EQ(power, 1);
  for (int i = 0; i < 60 && r.B().body.state(Zone::ArmR) < ZoneState::Critical; ++i) r.B().TakeHit(Zone::ArmR, 5.f, StrikeKind::Quick, 0.f, ctx);
  int arm = 0;
  for (const Event& e : r.duel.log().events())
    if (e.type == EventType::SystemFailure && e.a == static_cast<int>(SystemId::ArmR)) ++arm;
  IV_CHECK_EQ(arm, 1);
}

IV_TEST(Presentation, StaggerBeginAndEndAreBalancedAndKnockdownFollowsASecondCollapse) {
  Rig r;
  StepContext ctx;
  ctx.log = &r.duel.log();
  r.A().LoseStability(500.f, ctx);
  IV_CHECK_EQ(r.Count(EventType::StaggerBegin), 1);
  r.Step(tune::kStaggerTicks + 2);
  IV_CHECK_EQ(r.Count(EventType::StaggerEnd), 1);
  r.A().LoseStability(500.f, ctx);                      // v3: right after a stagger the mech shrugs off more stability loss
  IV_CHECK_EQ(r.Count(EventType::StaggerBegin), 1);
  r.Step(tune::kStunImmuneTicks + 2);
  r.A().LoseStability(500.f, ctx);
  r.A().LoseStability(500.f, ctx);
  IV_CHECK_EQ(r.Count(EventType::Knockdown), 1);
}

IV_TEST(Presentation, EnergyShiftNamesBothPriorities) {
  Rig r;
  r.a.setPriority = true;
  r.a.priority = EnergyPriority::Legs;
  const EnergyPriority from = r.A().res.priority;
  r.Step();
  r.a.setPriority = false;
  r.StepUntil([&] { return r.Count(EventType::EnergyShift) > 0; }, 600);
  const Event* e = Find(r, EventType::EnergyShift);
  IV_CHECK(e != nullptr);
  IV_CHECK_EQ(e->a, static_cast<int>(EnergyPriority::Legs));
  IV_CHECK_EQ(e->b, static_cast<int>(from));
}

IV_TEST(Presentation, ExtraPayloadIsPartOfTheDeterminismHash) {
  EventLog a(false), b(false);
  Event e;
  e.type = EventType::HitEvent;
  a.Push(e);
  e.c = PackHitFlags(SwingSide::Left, true, false);
  b.Push(e);
  IV_CHECK(a.hash() != b.hash());
  Event f = e;
  f.value2 = 12.5f;
  EventLog c(false);
  c.Push(f);
  IV_CHECK(c.hash() != b.hash());
  HitInfo h;
  Event g;
  g.type = EventType::HitEvent;
  g.c = PackHitFlags(SwingSide::Down, true, true);
  IV_CHECK(DecodeHit(g, &h));
  IV_CHECK(h.direction == SwingSide::Down && h.wasBlocked && h.wasParried);
  g.type = EventType::Hit;
  IV_CHECK(!DecodeHit(g, &h));
}

// ----------------------------------------------------------------------------------------------- anim

IV_TEST(Anim, IdleFighterHasZeroProgressAndNeutralPoses) {
  Rig r;
  const AnimState a = MakeAnimState(r.A());
  IV_CHECK(a.phase == Phase::Idle);
  IV_CHECK_EQ(a.progress, 0.f);
  IV_CHECK(!a.committed);
  IV_CHECK(a.pose[0] == ArmPose::Neutral && a.pose[1] == ArmPose::Neutral);
  IV_CHECK(a.posture == Posture::Standing);
  IV_CHECK(a.stability01 > 0.99f && a.heat01 < 0.01f && a.ultimate01 == 0.f);
}

IV_TEST(Anim, WindupProgressRisesMonotonicallyAndCommitsOnRelease) {
  Rig r;
  r.a.strikeHeld = true;
  r.a.side = SwingSide::Left;
  r.a.target = Zone::ArmR;
  r.a.arm = Arm::L;
  float last = -1.f;
  for (int i = 0; i < tune::kWindupMinTicks; ++i) {
    r.Step();
    const AnimState a = MakeAnimState(r.A());
    IV_CHECK(a.phase == Phase::Windup);
    IV_CHECK(a.progress >= last - 1e-6f);
    IV_CHECK(!a.committed);
    IV_CHECK(a.side == SwingSide::Left && a.arm == Arm::L && a.target == Zone::ArmR && a.kind == StrikeKind::Heavy);
    last = a.progress;
  }
  IV_CHECK(last > 0.9f);
  r.Step(20);
  IV_CHECK(MakeAnimState(r.A()).charge > 0.f);
  r.a.strikeHeld = false;
  r.Step();
  IV_CHECK(MakeAnimState(r.A()).committed);
}

IV_TEST(Anim, StrikeContactAndRecoveryProgressThroughTheirPhases) {
  Rig r(1, 12.f);
  r.StartHeavyA(SwingSide::Up, Zone::Torso);
  float last = -1.f;
  int n = 0;
  while (r.A().phase == Phase::Strike && n < 200) {
    const AnimState a = MakeAnimState(r.A());
    IV_CHECK(a.committed);
    IV_CHECK(a.progress >= last - 1e-6f && a.progress >= 0.f && a.progress <= 1.f);
    last = a.progress;
    r.Step();
    ++n;
  }
  IV_CHECK(n > 5);
  r.StepUntil([&] { return r.A().phase == Phase::Contact || r.A().phase == Phase::Recovery; });
  float rlast = -1.f;
  r.StepUntil([&] { return r.A().phase == Phase::Recovery; });
  while (r.A().phase == Phase::Recovery) {
    const AnimState a = MakeAnimState(r.A());
    IV_CHECK(a.progress >= rlast - 1e-6f);
    rlast = a.progress;
    r.Step();
  }
  IV_CHECK(rlast > 0.8f);
}

IV_TEST(Anim, ArmPoseAfterAHeavyStrikeFollowsTheSwing) {
  Rig r(1, 12.f);
  r.StartHeavyA(SwingSide::Up, Zone::Torso);
  r.StepUntil([&] { return r.A().phase == Phase::Recovery; });
  IV_CHECK(MakeAnimState(r.A()).pose[Index(Arm::R)] == ArmPose::Raised);
}

IV_TEST(Anim, WeaponChargeAndCooldownAreReportedForTheCockpit) {
  Rig r(2, 60.f);
  r.a.weaponHeld = true;
  r.Step(10);
  const float p1 = MakeAnimState(r.A()).weaponChargeProgress;
  r.Step(30);
  const AnimState a = MakeAnimState(r.A());
  IV_CHECK(a.weaponCharging && a.weaponChargeProgress > p1 && a.weaponChargeProgress < 1.f);
  IV_CHECK(a.weapon == WeaponKind::RailSpear);
  IV_CHECK_EQ(a.weaponCooldown01, 0.f);
  Rig q(2, 60.f);
  ChargeAndFire(q);
  q.StepUntil([&] { return !q.duel.cinematic().active; });
  IV_CHECK(MakeAnimState(q.A()).weaponCooldown01 > 0.9f);
  q.Step(300);
  IV_CHECK(MakeAnimState(q.A()).weaponCooldown01 < 0.95f);
}

IV_TEST(Anim, DodgeShiftsTheBodySidewaysWithTheRightSign) {
  Rig r(1, 30.f);
  r.a.dodge = true;
  r.a.dodgeDir = -1;
  r.Step(3);
  const AnimState left = MakeAnimState(r.A());
  IV_CHECK(left.posture == Posture::Dodging);
  IV_CHECK(left.lateralShift < 0.f);
  IV_CHECK(left.postureProgress > 0.f);
  Rig q(1, 30.f);
  q.a.dodge = true;
  q.a.dodgeDir = 1;
  q.Step(3);
  IV_CHECK(MakeAnimState(q.A()).lateralShift > 0.f);
}

IV_TEST(Anim, FootworkMovesTheWeightForwardOrBack) {
  Rig r(1, 12.f);
  r.a.strikeHeld = true;
  r.a.footwork = Footwork::StepIn;
  r.Step(tune::kWindupMinTicks);
  IV_CHECK(MakeAnimState(r.A()).weightShift > 0.f);
  Rig q(1, 12.f);
  q.a.strikeHeld = true;
  q.a.footwork = Footwork::StepBack;
  q.Step(tune::kWindupMinTicks);
  IV_CHECK(MakeAnimState(q.A()).weightShift < 0.f);
}

IV_TEST(Anim, StaggerAndGaugesAreNormalised) {
  Rig r;
  StepContext ctx;
  r.A().LoseStability(500.f, ctx);
  r.Step(30);
  const AnimState a = MakeAnimState(r.A());
  IV_CHECK(a.posture == Posture::Staggered);
  IV_CHECK(a.postureProgress > 0.f && a.postureProgress < 1.f);
  IV_CHECK(a.stability01 >= 0.f && a.stability01 <= 1.f && a.heat01 >= 0.f && a.heat01 <= 1.f && a.ultimate01 >= 0.f && a.ultimate01 <= 1.f);
}

// ---------------------------------------------------------------------------------------------- dummy

IV_TEST(Dummy, OffByDefaultAndTheInputOfTheDuelIsUsed) {
  Rig r(1, 12.f);
  IV_CHECK(r.duel.dummy(Side::B).mode() == DummyMode::Off);
  r.b.strikeHeld = true;
  r.Step(5);
  IV_CHECK(r.B().phase == Phase::Windup);
}

IV_TEST(Dummy, PassiveDummyNeverActsAndOverridesTheInputs) {
  Rig r(1, 12.f);
  r.duel.SetDummy(Side::B, DummyMode::Passive);
  r.b.strikeHeld = true;  // ignored: the dummy controller owns side B
  r.Step(300);
  IV_CHECK_EQ(r.Count(EventType::WindupStarted), 0);
  IV_CHECK(r.B().phase == Phase::Idle);
  r.StartHeavyA(SwingSide::Up, Zone::Torso);
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; });
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));  // takes the hit without reacting
}

IV_TEST(Dummy, ScriptedDummyPlaysItsAttackListInOrder) {
  Rig r(1, 12.f);
  r.duel.SetDummy(Side::B, DummyMode::Scripted);
  IV_CHECK_EQ(static_cast<int>(r.duel.dummy(Side::B).script().size()), 5);
  r.Step(tune::kDummyScriptGapTicks + 60);
  const Event* first = Find(r, EventType::WindupStarted);
  IV_CHECK(first != nullptr && first->actor == Side::B);
  IV_CHECK_EQ(first->a, static_cast<int>(StrikeKind::Heavy));
  IV_CHECK_EQ(first->b, static_cast<int>(SwingSide::Up));
  r.StepUntil([&] { return r.Count(EventType::WindupStarted) >= 2; }, 3000);
  int idx = 0;
  const Event* second = nullptr;
  for (const Event& e : r.duel.log().events())
    if (e.type == EventType::WindupStarted && ++idx == 2) second = &e;
  IV_CHECK(second != nullptr && second->b == static_cast<int>(SwingSide::Right));
}

IV_TEST(Dummy, CustomScriptsAreFollowed) {
  Rig r(1, 12.f);
  std::vector<DummyStepDef> s;
  DummyStepDef d;
  d.waitTicks = 30;
  d.kind = StrikeKind::Quick;
  d.side = SwingSide::Down;
  d.arm = Arm::L;
  s.push_back(d);
  r.duel.dummy(Side::B).SetScript(s);
  r.duel.SetDummy(Side::B, DummyMode::Scripted);
  r.duel.dummy(Side::B).SetScript(s);
  r.Step(80);
  const Event* e = Find(r, EventType::WindupStarted);
  IV_CHECK(e != nullptr && e->a == static_cast<int>(StrikeKind::Quick));
}

IV_TEST(Dummy, BlockOnlyDummyRaisesTheRightGuardAfterAHumanReactionTime) {
  Rig r(1, 12.f);
  r.duel.SetDummy(Side::B, DummyMode::BlockOnly);
  r.Step(120);
  IV_CHECK(!r.B().guard.held);  // nothing to react to
  r.a.strikeHeld = true;
  r.a.side = SwingSide::Right;
  r.a.target = Zone::Torso;
  r.Step(tune::kDummyReactionTicks - 4);
  IV_CHECK(!r.B().guard.held);  // too early: it needs time to see the sector
  r.Step(10);
  IV_CHECK(r.B().guard.held);
  IV_CHECK(r.B().guard.side == SwingSide::Right);
  r.Step(tune::kWindupMinTicks);   // keep winding up until a release is legal
  r.a.strikeHeld = false;
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; });
  IV_CHECK(r.LastOutcome(Side::A) == static_cast<int>(Outcome::Blocked) || r.LastOutcome(Side::A) == static_cast<int>(Outcome::Parried));
  IV_CHECK_EQ(r.Count(EventType::WindupStarted), 1);  // the dummy itself never attacks
}

IV_TEST(Dummy, TheDummyIsRepairedInsteadOfEndingTheLesson) {
  Rig r(1, 12.f);
  r.duel.SetDummy(Side::B, DummyMode::Passive);
  StepContext ctx;
  for (int i = 0; i < 400; ++i) r.B().TakeHit(Zone::Reactor, 30.f, StrikeKind::Heavy, 0.f, ctx);
  IV_CHECK(r.B().body.lost(Zone::Reactor));
  r.Step();
  IV_CHECK(!r.duel.result().over);
  IV_CHECK(!r.B().body.lost(Zone::Reactor));
  IV_CHECK(r.B().posture == Posture::Standing);
}

IV_TEST(Dummy, TheTrainerCanStillBeBeatenOnTheOtherSide) {
  Rig r(1, 12.f);
  r.duel.SetDummy(Side::B, DummyMode::Passive);
  StepContext ctx;
  for (int i = 0; i < 400; ++i) r.A().TakeHit(Zone::Reactor, 30.f, StrikeKind::Heavy, 0.f, ctx);
  r.Step();
  IV_CHECK(r.duel.result().over);
  IV_CHECK(r.duel.result().loser == Side::A);
}

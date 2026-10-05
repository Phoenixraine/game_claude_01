// v3 sword-duel rules: clashing blades, lateral-only dodge with a counter window, no chained stun,
// weapon statuses, ultimate variants, external hits, AI mimic and blindness.
#include <cmath>

#include "TestUtil.h"
#include "iv/Ai.h"

using namespace ivtest;

namespace {
// Both fighters wind up and release at the same moment on the given lines.
void BothStrike(Rig& r, SwingSide sa, SwingSide sb, int holdA, int holdB) {
  r.a.strikeHeld = r.b.strikeHeld = true;
  r.a.side = sa;
  r.b.side = sb;
  r.a.target = r.b.target = Zone::Torso;
  const int hold = holdA > holdB ? holdA : holdB;
  for (int i = 0; i < hold; ++i) {
    if (i >= holdA) r.a.strikeHeld = false;
    if (i >= holdB) r.b.strikeHeld = false;
    r.Step();
  }
  r.a.strikeHeld = r.b.strikeHeld = false;
}
}  // namespace

IV_TEST(Clash, SimultaneousHeavyStrikesOnTheSameLineStopEachOther) {
  Rig r(1, 18.f);
  BothStrike(r, SwingSide::Up, SwingSide::Up, tune::kWindupMinTicks, tune::kWindupMinTicks);
  r.StepUntil([&] { return r.Count(EventType::BladesClash) > 0; }, 200);
  IV_CHECK_EQ(r.Count(EventType::BladesClash), 1);
  IV_CHECK_EQ(r.Count(EventType::Hit), 0);                      // nobody is hurt: a double block
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Clashed));
  IV_CHECK_EQ(r.LastOutcome(Side::B), static_cast<int>(Outcome::Clashed));
  IV_CHECK(r.A().phase == Phase::Recovery && r.B().phase == Phase::Recovery);
  IV_CHECK(r.A().recoveryLen == tune::kClashRecoveryTicks);
  r.Step(tune::kClashRecoveryTicks + 5);
  IV_CHECK_EQ(r.Count(EventType::Hit), 0);                      // and the strikes do not land afterwards
}

IV_TEST(Clash, ScreenSidesMeetAcrossTheMiddle) {
  Rig r(1, 18.f);
  BothStrike(r, SwingSide::Left, SwingSide::Right, tune::kWindupMinTicks, tune::kWindupMinTicks);
  r.StepUntil([&] { return r.Count(EventType::BladesClash) > 0; }, 200);
  IV_CHECK_EQ(r.Count(EventType::BladesClash), 1);
}

IV_TEST(Clash, DifferentLinesStillTrade) {
  Rig r(1, 18.f);
  BothStrike(r, SwingSide::Up, SwingSide::Down, tune::kWindupMinTicks, tune::kWindupMinTicks);
  r.Step(200);
  IV_CHECK_EQ(r.Count(EventType::BladesClash), 0);
  IV_CHECK(r.Count(EventType::Hit) >= 2);
}

IV_TEST(Clash, StrikesFarApartInTimeDoNotClash) {
  Rig r(1, 18.f);
  BothStrike(r, SwingSide::Up, SwingSide::Up, tune::kWindupMinTicks, tune::kWindupMinTicks + 40);
  r.Step(300);
  IV_CHECK_EQ(r.Count(EventType::BladesClash), 0);
}

IV_TEST(Dodge, EvadingALateralSlashDoesNotOpenACounterWindow) {
  Rig r(1, 18.f);
  r.StartHeavyA(SwingSide::Right, Zone::Torso);
  r.StepUntil([&] { return r.A().TicksToContact() == 8; });
  r.b.dodge = true;
  r.b.dodgeDir = -1;
  r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 100);
  IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Evaded));
  // v6: the dodge only saves the mech: no counter window, a strike right after is an ordinary one
  IV_CHECK_EQ(r.B().counterTicks, 0);
  r.b.quick = true;
  r.b.side = SwingSide::Up;
  r.Step();
  IV_CHECK(!r.B().strike.innerLine);
}

IV_TEST(Dodge, ChopsFromAboveAndRisingCutsFollowTheDodge) {
  for (SwingSide s : {SwingSide::Up, SwingSide::Down}) {
    Rig r(1, 18.f);
    r.StartHeavyA(s, Zone::Torso);
    r.StepUntil([&] { return r.A().TicksToContact() == 8; });
    r.b.dodge = true;
    r.StepUntil([&] { return r.Count(EventType::StrikeContact) > 0; }, 100);
    IV_CHECK_EQ(r.LastOutcome(Side::A), static_cast<int>(Outcome::Hit));
    IV_CHECK(r.B().counterTicks == 0);
  }
}

IV_TEST(Stun, NoChainedStaggerRightAfterRecovering) {
  Rig r;
  StepContext ctx;
  ctx.log = &r.duel.log();
  r.A().LoseStability(500.f, ctx);
  IV_CHECK(r.A().posture == Posture::Staggered);
  r.Step(tune::kStaggerTicks + 2);
  IV_CHECK(r.A().posture == Posture::Standing);
  IV_CHECK(r.A().stunImmune > 0);
  for (int i = 0; i < 6; ++i) r.A().LoseStability(60.f, ctx);
  IV_CHECK(r.A().posture == Posture::Standing);                  // hit again and again: damage lands, the mech stays on its feet
  IV_CHECK(r.A().res.stability >= tune::kStunImmuneFloor - 0.001f);
  r.Step(tune::kStunImmuneTicks + 2);
  IV_CHECK_EQ(r.A().stunImmune, 0);
  r.A().LoseStability(500.f, ctx);
  IV_CHECK(r.A().posture == Posture::Staggered);                 // once the grace period is over it can stagger again
}

IV_TEST(Status, RailSpearJamsTheArmsRocketsBlindPlasmaBurns) {
  const WeaponKind kinds[3] = {WeaponKind::RailSpear, WeaponKind::SuppressionRockets, WeaponKind::PlasmaCannon};
  const StatusKind expect[3] = {StatusKind::StrikeLock, StatusKind::Blind, StatusKind::Burn};
  for (int k = 0; k < 3; ++k) {
    int sawStatus = 0;
    for (uint64_t seed = 1; seed <= 12 && sawStatus == 0; ++seed) {   // rockets can miss: try a few seeds
      Rig r(seed, 40.f);
      r.duel.SetLoadout(Side::A, kinds[k]);
      r.a.weaponHeld = true;
      r.a.target = Zone::Torso;
      r.Step(tune::kWeapons[k].chargeTicks * 2 + 10);
      r.a.weaponHeld = false;
      r.Step(4);
      for (const Event& e : r.duel.log().events())
        if (e.type == EventType::StatusApplied && e.actor == Side::B && e.a == static_cast<int>(expect[k])) ++sawStatus;
      if (sawStatus > 0) {
        if (k == 0) IV_CHECK(r.B().strikeLockTicks > 0);
        if (k == 1) IV_CHECK(r.B().Blind());
        if (k == 2) IV_CHECK(r.B().burnTicks > 0);
      }
    }
    IV_CHECK(sawStatus > 0);
  }
}

IV_TEST(Status, StrikeLockBlocksNewStrikesButNotTheGuard) {
  Rig r;
  StepContext ctx;
  ctx.log = &r.duel.log();
  r.B().ApplyStatus(StatusKind::StrikeLock, 90, ctx);
  r.b.strikeHeld = true;
  r.b.side = SwingSide::Up;
  r.Step(20);
  IV_CHECK(r.B().phase == Phase::Idle);
  r.b.strikeHeld = false;
  r.b.guardHeld = true;
  r.Step(2);
  IV_CHECK(r.B().guard.held);
  r.b.guardHeld = false;
  r.Step(100);
  IV_CHECK_EQ(r.B().strikeLockTicks, 0);
  r.b.strikeHeld = true;
  r.Step(2);
  IV_CHECK(r.B().phase == Phase::Windup);
}

IV_TEST(Status, BurningHurtsTheTorsoAndHeatsTheReactor) {
  Rig r;
  StepContext ctx;
  ctx.log = &r.duel.log();
  const float armor0 = r.B().body.layer(Zone::Torso, Layer::Armor);
  const float heat0 = r.B().res.heat;
  r.B().ApplyStatus(StatusKind::Burn, 240, ctx);
  r.Step(250);
  IV_CHECK(r.B().body.layer(Zone::Torso, Layer::Armor) < armor0);
  IV_CHECK(r.B().res.heat > heat0 + 5.f);
  IV_CHECK(r.Count(EventType::BurnTick) >= 6);
  IV_CHECK_EQ(r.B().burnTicks, 0);
}

IV_TEST(Ultimate, WeakenedTargetIsCutInHalfHealthyOneLosesItsOffHandArm) {
  {   // healthy target
    Rig r(1, 20.f);
    r.A().ultimate = tune::kUltimateMax;
    r.a.ultimate = true;
    r.a.target = Zone::Head;
    r.Step();
    r.Step(tune::kUltWindupTicks);
    IV_CHECK(r.duel.cinematic().kind == CinematicKind::UltimateSever);
    IV_CHECK_EQ(r.Count(EventType::UltimateSever), 1);
    IV_CHECK(r.B().body.severed(Zone::ArmL));
    IV_CHECK(r.B().ultimateLocked);
    r.Step(tune::kUltimateCinematicTicks + 2);
    IV_CHECK(!r.duel.result().over);
    r.B().ultimate = tune::kUltimateMax;
    r.b.ultimate = true;
    r.Step(3);
    IV_CHECK_EQ(r.Count(EventType::UltimateUsed), 1);            // only the first one: the victim's button is dead
  }
  {   // weakened target
    Rig r(1, 20.f);
    for (int z = 0; z < kZoneCount; ++z)
      if (static_cast<Zone>(z) != Zone::Reactor) r.B().body.ApplyDamage(static_cast<Zone>(z), 140.f, StrikeKind::Quick);   // v6: the windup takes time, so the target must be alive during it
    r.B().body.ApplyDamage(Zone::Reactor, 60.f, StrikeKind::Quick);
    IV_CHECK(r.B().body.Integrity() < tune::kUltimateKillFraction + 0.1f);
    r.A().ultimate = tune::kUltimateMax;
    r.a.ultimate = true;
    r.a.target = Zone::Head;
    r.Step();
    r.Step(tune::kUltWindupTicks);
    IV_CHECK(r.duel.cinematic().kind == CinematicKind::UltimateBisect);
    IV_CHECK_EQ(r.Count(EventType::UltimateFinisher), 1);
    r.Step(tune::kUltimateCinematicTicks + 2);
    IV_CHECK(r.duel.result().over);
    IV_CHECK(r.duel.result().loser == Side::B);
  }
}

IV_TEST(External, ThrownDebrisHurtsAndBlindsAndIsAnnounced) {
  Rig r;
  const HitReport hr = r.duel.ExternalHit(Side::B, Zone::Head, tune::kDebrisDamage, tune::kDebrisStability, 0, StatusKind::Blind, tune::kDebrisBlindTicks);
  IV_CHECK(hr.dealt > 0.f);
  IV_CHECK_EQ(r.Count(EventType::ExternalHit), 1);
  IV_CHECK_EQ(r.Count(EventType::HitEvent), 1);
  IV_CHECK(r.B().Blind());
  IV_CHECK_EQ(r.B().blindTicks, tune::kDebrisBlindTicks);
}

IV_TEST(Ai, BlindPilotCannotReadTheSectorAndMimicsThePlayersLine) {
  // Observation carries the blind flag.
  Rig r;
  StepContext ctx;
  ctx.log = &r.duel.log();
  r.B().ApplyStatus(StatusKind::Blind, 120, ctx);
  IV_CHECK(MakeObservation(r.duel, Side::B).self.blinded);
  IV_CHECK(!MakeObservation(r.duel, Side::A).self.blinded);
  // A hard AI that has just seen the player's Right swing repeats Right more often than chance alone would.
  int mimic = 0, trials = 0;
  for (uint64_t seed = 1; seed <= 40; ++seed) {
    Rig q(seed, 24.f);
    Ai bot(Archetype::Counterpuncher, Difficulty::Hard, seed);
    q.a.strikeHeld = true;
    q.a.side = SwingSide::Right;
    q.a.target = Zone::Torso;
    for (int i = 0; i < 400; ++i) {
      const Input bi = bot.Decide(MakeObservation(q.duel, Side::B));
      q.b = bi;
      if (i == 40) q.a.strikeHeld = false;
      if (i > 120) q.a.strikeHeld = false;
      q.duel.Step(q.a, q.b, q.world);
      ClearEdges(q.a);
      ClearEdges(q.b);
    }
    for (const Event& e : q.duel.log().events())
      if (e.type == EventType::WindupStarted && e.actor == Side::B && e.a == static_cast<int>(StrikeKind::Heavy)) {
        ++trials;
        if (e.b == static_cast<int>(SwingSide::Right)) ++mimic;
        break;
      }
  }
  IV_CHECK(trials >= 10);
  IV_CHECK(mimic * 3 >= trials);   // at least a third of the first answers repeat the player's line (chance alone gives about a quarter)
}

IV_TEST(Weapons, SwitchingWeaponsKeepsEachCooldownRunning) {
  Rig r(1, 40.f);
  r.duel.SetLoadout(Side::A, WeaponKind::RailSpear);
  r.a.weaponHeld = true;
  r.Step(tune::kWeapons[0].chargeTicks * 2 + 10);
  r.a.weaponHeld = false;
  r.Step(3);
  r.StepUntil([&] { return !r.duel.cinematic().active && r.A().phase == Phase::Idle; }, 3000);
  IV_CHECK(r.A().weaponCooldown > 0);
  const int railLeft = r.A().weaponCooldown;
  IV_CHECK(r.duel.SelectWeapon(Side::A, WeaponKind::PlasmaCannon));
  IV_CHECK_EQ(r.A().weaponCooldown, 0);                           // plasma is ready: switching does not refresh the rail
  IV_CHECK(r.A().CooldownOf(WeaponKind::RailSpear) == railLeft);
  r.Step(120);
  IV_CHECK(r.A().CooldownOf(WeaponKind::RailSpear) == railLeft - 120);
  IV_CHECK(r.duel.SelectWeapon(Side::A, WeaponKind::RailSpear));
  IV_CHECK(r.A().weaponCooldown == railLeft - 120);
}


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

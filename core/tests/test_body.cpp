#include "TestFramework.h"
#include "iv/Body.h"
#include "iv/Tuning.h"

using namespace iv;

namespace {
// Total hit points of a zone over all three layers.
float Total(Zone z) {
  const int i = Index(z);
  return tune::kArmorMax[i] + tune::kMechanismMax[i] + tune::kSystemMax[i];
}
}  // namespace

IV_TEST(Body, StartsIntactWithNeutralModifiers) {
  Body b;
  for (int z = 0; z < kZoneCount; ++z) IV_CHECK(b.state(static_cast<Zone>(z)) == ZoneState::Intact);
  const Modifiers& m = b.modifiers();
  IV_CHECK_NEAR(m.arm[0].swingSpeed, 1.0, 1e-6);
  IV_CHECK_NEAR(m.stepSpeed, 1.0, 1e-6);
  IV_CHECK(m.dodgeLeft && m.dodgeRight && m.canRam);
  IV_CHECK_EQ(m.blindSectors, 0);
  IV_CHECK(b.CheckEnd(false) == EndReason::None);
}

IV_TEST(Body, DamageConsumesArmorThenMechanismThenSystem) {
  Body b;
  const Zone z = Zone::Torso;
  const int i = Index(z);
  b.ApplyDamage(z, tune::kArmorMax[i] - 1.f, StrikeKind::Heavy);
  IV_CHECK_NEAR(b.layer(z, Layer::Armor), 1.0, 1e-4);
  IV_CHECK_NEAR(b.layer(z, Layer::Mechanism), tune::kMechanismMax[i], 1e-4);
  b.ApplyDamage(z, 11.f, StrikeKind::Heavy);  // 1 armour left + 10 into the mechanism
  IV_CHECK_NEAR(b.layer(z, Layer::Armor), 0.0, 1e-4);
  IV_CHECK_NEAR(b.layer(z, Layer::Mechanism), tune::kMechanismMax[i] - 10.f, 1e-3);
  IV_CHECK_NEAR(b.layer(z, Layer::System), tune::kSystemMax[i], 1e-4);
}

IV_TEST(Body, StatesProgressMonotonically) {
  Body b;
  const Zone z = Zone::LegL;
  ZoneState prev = b.state(z);
  bool seen[kZoneStateCount] = {};
  seen[static_cast<int>(prev)] = true;
  for (int n = 0; n < 200 && b.state(z) != ZoneState::Destroyed; ++n) {
    b.ApplyDamage(z, 3.f, StrikeKind::Heavy);
    IV_CHECK(b.state(z) >= prev);
    prev = b.state(z);
    seen[static_cast<int>(prev)] = true;
  }
  // Every state between Intact and Destroyed is visited when damage trickles in.
  for (int s = static_cast<int>(ZoneState::Intact); s <= static_cast<int>(ZoneState::Destroyed); ++s) IV_CHECK(seen[s]);
}

IV_TEST(Body, ExposedMeansArmourGoneMechanismUntouched) {
  Body b;
  b.ApplyDamage(Zone::ArmR, tune::kArmorMax[Index(Zone::ArmR)], StrikeKind::Heavy);
  IV_CHECK(b.state(Zone::ArmR) == ZoneState::Exposed);
  b.ApplyDamage(Zone::ArmR, 5.f, StrikeKind::Heavy);
  IV_CHECK(b.state(Zone::ArmR) == ZoneState::Damaged);
}

IV_TEST(Body, LimbIsSeveredOnlyAfterDestroyed) {
  Body b;
  const Zone z = Zone::ArmL;
  // A hit that leaves the zone merely Critical must never sever, however large the follow-up rules are.
  b.ApplyDamage(z, Total(z) - 5.f, StrikeKind::Heavy);
  IV_CHECK(b.state(z) == ZoneState::Critical);
  IV_CHECK(!b.severed(z));
  // The hit that destroys the zone does not sever it in the same blow.
  DamageResult r = b.ApplyDamage(z, 5.f, StrikeKind::Heavy);
  IV_CHECK(b.state(z) == ZoneState::Destroyed);
  IV_CHECK(!r.severed);
  // Now a follow-up heavy hit tears it off.
  r = b.ApplyDamage(z, tune::kSeverMinDamage, StrikeKind::Heavy);
  IV_CHECK(r.severed);
  IV_CHECK(b.state(z) == ZoneState::Severed);
}

IV_TEST(Body, QuickHitsAndSmallHitsCannotSever) {
  Body b;
  const Zone z = Zone::LegR;
  b.ApplyDamage(z, Total(z), StrikeKind::Heavy);
  IV_CHECK(b.state(z) == ZoneState::Destroyed);
  DamageResult r = b.ApplyDamage(z, 50.f, StrikeKind::Quick);
  IV_CHECK(r.ignored && !r.severed);
  r = b.ApplyDamage(z, tune::kSeverMinDamage - 1.f, StrikeKind::Heavy);
  IV_CHECK(r.ignored && !r.severed);
  IV_CHECK(b.state(z) == ZoneState::Destroyed);
}

IV_TEST(Body, OnlyLimbsCanBeSevered) {
  Body b;
  const Zone zones[] = {Zone::Head, Zone::Torso, Zone::Reactor, Zone::ShoulderL, Zone::ShoulderR};
  for (Zone z : zones) {
    b.ApplyDamage(z, Total(z), StrikeKind::Heavy);
    const DamageResult r = b.ApplyDamage(z, 100.f, StrikeKind::Heavy);
    IV_CHECK(!r.severed);
    IV_CHECK(b.state(z) == ZoneState::Destroyed);
  }
}

IV_TEST(Body, SeveredZoneIgnoresFurtherDamage) {
  Body b;
  const Zone z = Zone::ArmR;
  b.ApplyDamage(z, Total(z), StrikeKind::Grab);
  b.ApplyDamage(z, 40.f, StrikeKind::Grab);
  IV_CHECK(b.severed(z));
  const DamageResult r = b.ApplyDamage(z, 40.f, StrikeKind::Heavy);
  IV_CHECK(r.ignored);
  IV_CHECK(b.state(z) == ZoneState::Severed);
}

IV_TEST(Body, ShoulderDamageSlowsSwingAndShortensReach) {
  Body b;
  const float speed0 = b.modifiers().arm[1].swingSpeed;
  const float reach0 = b.modifiers().arm[1].reach;
  const float block0 = b.modifiers().arm[1].blockStrength;
  b.ApplyDamage(Zone::ShoulderR, tune::kArmorMax[Index(Zone::ShoulderR)] + 10.f, StrikeKind::Heavy);  // Damaged
  const ArmMods& a = b.modifiers().arm[1];
  IV_CHECK(a.swingSpeed < speed0);
  IV_CHECK(a.reach < reach0);
  IV_CHECK(a.blockStrength < block0);
  IV_CHECK_NEAR(b.modifiers().arm[0].swingSpeed, 1.0, 1e-6);  // the other arm is untouched
}

IV_TEST(Body, DamagedElbowLimitsAttackSetAndDestroyedHandLosesGrab) {
  Body b;
  IV_CHECK_EQ(b.modifiers().arm[0].allowedSides, 0b1111);
  const Zone z = Zone::ArmL;
  b.ApplyDamage(z, tune::kArmorMax[Index(z)] + 5.f, StrikeKind::Heavy);  // Damaged
  IV_CHECK_EQ(b.modifiers().arm[0].allowedSides, 0b0111);
  b.ApplyDamage(z, 40.f, StrikeKind::Heavy);  // mechanism nearly gone -> Critical
  IV_CHECK(b.state(z) == ZoneState::Critical);
  IV_CHECK_EQ(b.modifiers().arm[0].allowedSides, 0b0011);
  IV_CHECK(b.modifiers().arm[0].canGrab);
  b.ApplyDamage(z, 100.f, StrikeKind::Heavy);
  IV_CHECK(b.state(z) == ZoneState::Destroyed);
  IV_CHECK(!b.modifiers().arm[0].canGrab);
  IV_CHECK(!b.modifiers().arm[0].usable);
  IV_CHECK_EQ(b.modifiers().arm[0].allowedSides, 0);
}

IV_TEST(Body, LegDamageSlowsRemovesDodgesAndRam) {
  Body b;
  const float step0 = b.modifiers().stepSpeed;
  b.ApplyDamage(Zone::LegL, tune::kArmorMax[Index(Zone::LegL)] + 10.f, StrikeKind::Heavy);  // Damaged
  IV_CHECK(b.modifiers().stepSpeed < step0);
  IV_CHECK(b.modifiers().canRam);  // Damaged still allows a ram
  b.ApplyDamage(Zone::LegL, 60.f, StrikeKind::Heavy);  // Critical
  IV_CHECK(!b.modifiers().canRam);
  // A hurt left leg cannot push off for a dodge to the right, but the mech can still dodge left.
  IV_CHECK(!b.modifiers().dodgeRight);
  IV_CHECK(b.modifiers().dodgeLeft);
  IV_CHECK(b.modifiers().turnRate < 1.f);
  IV_CHECK(b.modifiers().stabilityRecovery < 1.f);
}

IV_TEST(Body, HeadDamageDelaysLockAndBlindsSectors) {
  Body b;
  const int base = b.modifiers().targetLockDelayTicks;
  b.ApplyDamage(Zone::Head, tune::kArmorMax[Index(Zone::Head)] + 10.f, StrikeKind::Heavy);
  IV_CHECK(b.modifiers().targetLockDelayTicks > base);
  IV_CHECK_EQ(b.modifiers().blindSectors, 0);
  b.ApplyDamage(Zone::Head, 40.f, StrikeKind::Heavy);  // Critical
  IV_CHECK(b.state(Zone::Head) == ZoneState::Critical);
  IV_CHECK((b.modifiers().blindSectors & (1 << Index(SwingSide::Left))) != 0);
  const float acc = b.modifiers().weaponAccuracy;
  IV_CHECK(acc < tune::kWeaponBaseAccuracy);
  b.ApplyDamage(Zone::Head, 100.f, StrikeKind::Heavy);  // Destroyed
  IV_CHECK((b.modifiers().blindSectors & (1 << Index(SwingSide::Right))) != 0);
  IV_CHECK(b.modifiers().weaponAccuracy < acc);
}

IV_TEST(Body, EveryModifierIsMonotoneInZoneState) {
  // Walk each zone from healthy to Destroyed and require that no modifier ever improves.
  for (int zi = 0; zi < kZoneCount; ++zi) {
    const Zone z = static_cast<Zone>(zi);
    Body b;
    Modifiers prev = b.modifiers();
    for (int n = 0; n < 400 && b.state(z) != ZoneState::Destroyed; ++n) {
      b.ApplyDamage(z, 2.f, StrikeKind::Heavy);
      const Modifiers& m = b.modifiers();
      for (int a = 0; a < 2; ++a) {
        IV_CHECK(m.arm[a].swingSpeed <= prev.arm[a].swingSpeed + 1e-6f);
        IV_CHECK(m.arm[a].power <= prev.arm[a].power + 1e-6f);
        IV_CHECK(m.arm[a].reach <= prev.arm[a].reach + 1e-6f);
        IV_CHECK(m.arm[a].blockStrength <= prev.arm[a].blockStrength + 1e-6f);
        IV_CHECK(!(m.arm[a].canGrab && !prev.arm[a].canGrab));
        IV_CHECK(!(m.arm[a].canRetarget && !prev.arm[a].canRetarget));
        IV_CHECK((m.arm[a].allowedSides & ~prev.arm[a].allowedSides) == 0);
      }
      IV_CHECK(m.stepSpeed <= prev.stepSpeed + 1e-6f);
      IV_CHECK(m.turnRate <= prev.turnRate + 1e-6f);
      IV_CHECK(m.stabilityRecovery <= prev.stabilityRecovery + 1e-6f);
      IV_CHECK(m.coolingEff <= prev.coolingEff + 1e-6f);
      IV_CHECK(!(m.dodgeLeft && !prev.dodgeLeft));
      IV_CHECK(!(m.dodgeRight && !prev.dodgeRight));
      IV_CHECK(!(m.canRam && !prev.canRam));
      IV_CHECK(m.targetLockDelayTicks >= prev.targetLockDelayTicks);
      IV_CHECK((prev.blindSectors & ~m.blindSectors) == 0);
      IV_CHECK(m.weaponAccuracy <= prev.weaponAccuracy + 1e-6f);
      prev = m;
    }
  }
}

IV_TEST(Body, ReactorDestroyedEndsMatch) {
  Body b;
  b.ApplyDamage(Zone::Reactor, Total(Zone::Reactor), StrikeKind::Heavy);
  IV_CHECK(b.CheckEnd(false) == EndReason::ReactorDestroyed);
}

IV_TEST(Body, CockpitCriticalEndsMatch) {
  Body b;
  b.ApplyDamage(Zone::Torso, Total(Zone::Torso), StrikeKind::Heavy);
  IV_CHECK(b.CheckEnd(false) == EndReason::CockpitCritical);
}

IV_TEST(Body, LosingBothLegsEndsMatchButOneLegDoesNot) {
  Body b;
  b.ApplyDamage(Zone::LegL, Total(Zone::LegL), StrikeKind::Heavy);
  IV_CHECK(b.CheckEnd(false) == EndReason::None);  // pitch §9: one destroyed leg does not end the fight
  b.ApplyDamage(Zone::LegR, Total(Zone::LegR), StrikeKind::Heavy);
  IV_CHECK(b.CheckEnd(false) == EndReason::TotalImmobility);
}

IV_TEST(Body, PowerLossEndsMatch) {
  Body b;
  IV_CHECK(b.CheckEnd(true) == EndReason::PowerLoss);
}

IV_TEST(Body, BothArmsLostPlusImmobilisedEndsMatch) {
  Body b;
  b.ApplyDamage(Zone::ArmL, Total(Zone::ArmL), StrikeKind::Heavy);
  b.ApplyDamage(Zone::ArmR, Total(Zone::ArmR), StrikeKind::Heavy);
  IV_CHECK(b.CheckEnd(false) == EndReason::None);  // armless but still mobile: the fight goes on
  b.ApplyDamage(Zone::LegR, Total(Zone::LegR), StrikeKind::Heavy);
  IV_CHECK(b.CheckEnd(false) == EndReason::ArmsLostImmobilised);
}

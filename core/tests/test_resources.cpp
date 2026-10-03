#include "TestFramework.h"
#include "iv/Resources.h"

using namespace iv;

namespace {
Modifiers Healthy() { return Body().modifiers(); }
}  // namespace

IV_TEST(Resources, StabilityNeverDropsBelowZeroAndReportsTheCrossing) {
  Resources r;
  IV_CHECK(!r.LoseStability(30.f));
  IV_CHECK_NEAR(r.stability, 70.0, 1e-4);
  IV_CHECK(r.LoseStability(500.f));  // crosses zero exactly once
  IV_CHECK_NEAR(r.stability, 0.0, 1e-6);
  IV_CHECK(!r.LoseStability(10.f));  // already at zero: no second crossing
}

IV_TEST(Resources, StabilityRegeneratesAndIsCapped) {
  Resources r;
  const Modifiers m = Healthy();
  r.LoseStability(50.f);
  r.Tick(m, 0, 1.f, true);
  IV_CHECK(r.stability > 50.f);
  for (int i = 0; i < 100000; ++i) r.Tick(m, 0, 1.f, true);
  IV_CHECK_NEAR(r.stability, tune::kStabilityMax, 1e-4);
}

IV_TEST(Resources, NoStabilityRegenWhileUnderLoad) {
  Resources r;
  const Modifiers m = Healthy();
  r.LoseStability(50.f);
  for (int i = 0; i < 300; ++i) r.Tick(m, 0, 1.f, false);
  IV_CHECK_NEAR(r.stability, 50.0, 1e-4);
}

IV_TEST(Resources, DamagedLegsRecoverStabilitySlower) {
  Body hurt;
  hurt.ApplyDamage(Zone::LegL, 200.f, StrikeKind::Heavy);
  hurt.ApplyDamage(Zone::LegR, 200.f, StrikeKind::Heavy);
  Resources a, b;
  a.LoseStability(60.f);
  b.LoseStability(60.f);
  for (int i = 0; i < 200; ++i) {
    a.Tick(Healthy(), 0, 1.f, true);
    b.Tick(hurt.modifiers(), 0, 1.f, true);
  }
  IV_CHECK(a.stability > b.stability);
}

IV_TEST(Resources, HeatWarningLeakAndShutdownThresholds) {
  Resources r;
  const Modifiers m = Healthy();
  r.AddHeat(tune::kHeatWarnAt + 1.f);
  ResourceTickResult t = r.Tick(m, 0, 1.f, true);
  IV_CHECK(t.heatWarningStarted);
  IV_CHECK(!t.coolantLeakStarted);
  r.AddHeat(tune::kHeatLeakAt - r.heat + 1.f);
  t = r.Tick(m, 0, 1.f, true);
  IV_CHECK(t.coolantLeakStarted);
  IV_CHECK(r.coolantLeak);
  // Keep the reactor at maximum heat: shutdown must arrive after exactly kShutdownTicks.
  bool shutdown = false;
  int ticks = 0;
  while (!shutdown && ticks < 10000) {
    r.AddHeat(1000.f);
    shutdown = r.Tick(m, 0, 1.f, true).shutdown;
    ++ticks;
  }
  IV_CHECK(shutdown);
  IV_CHECK_EQ(ticks, tune::kShutdownTicks);
}

IV_TEST(Resources, ShutdownTimerResetsWhenHeatDrops) {
  Resources r;
  const Modifiers m = Healthy();
  for (int i = 0; i < tune::kShutdownTicks - 5; ++i) {
    r.AddHeat(1000.f);
    r.Tick(m, 0, 1.f, true);
  }
  r.heat = 50.f;
  IV_CHECK(!r.Tick(m, 0, 1.f, true).shutdown);
  IV_CHECK_EQ(r.overheatTicks, 0);
  IV_CHECK(!r.shutdown);
}

IV_TEST(Resources, CoolantLeakAndDamagedDrivesChangeHeatBalance) {
  Resources healthy, leaking, drives;
  const Modifiers m = Healthy();
  healthy.heat = leaking.heat = drives.heat = 60.f;
  leaking.coolantLeak = true;
  for (int i = 0; i < 100; ++i) {
    healthy.Tick(m, 0, 1.f, true);
    leaking.Tick(m, 0, 1.f, true);
    drives.Tick(m, 4, 1.f, true);
  }
  IV_CHECK(healthy.heat < 60.f);
  IV_CHECK(leaking.heat > healthy.heat);  // slower cooling
  IV_CHECK(drives.heat > healthy.heat);   // pitch §10: damaged drives add heat
}

IV_TEST(Resources, WaterCoolsFasterThanDryAir) {
  Resources dry, wet;
  const Modifiers m = Healthy();
  dry.heat = wet.heat = 50.f;
  for (int i = 0; i < 100; ++i) {
    dry.Tick(m, 0, 1.f, true);
    wet.Tick(m, 0, 3.f, true);
  }
  IV_CHECK(wet.heat < dry.heat);
}

IV_TEST(Resources, HeatPerformancePenaltyIsMonotone) {
  Resources r;
  IV_CHECK_NEAR(r.HeatPerformance(), 1.0, 1e-6);
  float prev = 1.f;
  for (float h = 0.f; h <= tune::kHeatMax; h += 5.f) {
    r.heat = h;
    IV_CHECK(r.HeatPerformance() <= prev + 1e-6f);
    prev = r.HeatPerformance();
  }
  r.heat = tune::kHeatMax;
  IV_CHECK_NEAR(r.HeatPerformance(), tune::kHeatMinPerformance, 1e-6);
}

IV_TEST(Resources, EnergyPrioritySwitchIsDelayedNotInstant) {
  Resources r;
  const Modifiers m = Healthy();
  IV_CHECK(r.priority == EnergyPriority::Guard);
  IV_CHECK(r.RequestPriority(EnergyPriority::Arms));
  IV_CHECK(r.priority == EnergyPriority::Guard);  // still the old distribution
  IV_CHECK_EQ(r.switchTicksLeft, tune::kEnergySwitchTicks);
  bool switched = false;
  int ticks = 0;
  while (!switched && ticks < 1000) {
    switched = r.Tick(m, 0, 1.f, true).prioritySwitched;
    ++ticks;
  }
  IV_CHECK_EQ(ticks, tune::kEnergySwitchTicks);
  IV_CHECK(r.priority == EnergyPriority::Arms);
}

IV_TEST(Resources, RepeatedOrRedundantPriorityRequestsAreIgnored) {
  Resources r;
  IV_CHECK(!r.RequestPriority(EnergyPriority::Guard));  // already active
  IV_CHECK(r.RequestPriority(EnergyPriority::Legs));
  IV_CHECK(!r.RequestPriority(EnergyPriority::Legs));   // already switching to it
  IV_CHECK(r.RequestPriority(EnergyPriority::Weapon));  // retarget mid-switch restarts the delay
  IV_CHECK_EQ(r.switchTicksLeft, tune::kEnergySwitchTicks);
}

IV_TEST(Resources, SpendRefusesWhenEmptyAndDeductsNothing) {
  Resources r;
  r.energy = 5.f;
  IV_CHECK(!r.Spend(6.f));
  IV_CHECK_NEAR(r.energy, 5.0, 1e-6);
  IV_CHECK(r.Spend(5.f));
  IV_CHECK_NEAR(r.energy, 0.0, 1e-6);
}

IV_TEST(Resources, PriorityMultipliersFollowThePitch) {
  Resources r;
  r.priority = EnergyPriority::Arms;
  IV_CHECK(r.ArmsMult() > 1.f);
  IV_CHECK(r.LegsMult() < 1.f);  // pitch §8: arms-heavy mechs move worse
  r.priority = EnergyPriority::Legs;
  IV_CHECK(r.LegsMult() > 1.f);
  IV_CHECK(r.ArmsMult() < 1.f);
  r.priority = EnergyPriority::Guard;
  IV_CHECK(r.DamageTakenMult() < 1.f);
  r.priority = EnergyPriority::Weapon;
  IV_CHECK(r.WeaponChargeMult() > 1.f);
  IV_CHECK(r.DamageTakenMult() >= 1.f);
}

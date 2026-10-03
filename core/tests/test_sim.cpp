// Whole-match invariants over the headless simulation (the same loop ivsim runs).
#include "TestUtil.h"
#include "iv/Ai.h"

using namespace iv;
using namespace ivtest;

namespace {
bool Sane(const Fighter& f) {
  const Resources& r = f.res;
  if (!(r.stability >= 0.f && r.stability <= tune::kStabilityMax)) return false;
  if (!(r.heat >= 0.f && r.heat <= tune::kHeatMax)) return false;
  if (!(r.energy >= 0.f && r.energy <= tune::kEnergyMax)) return false;
  for (int z = 0; z < kZoneCount; ++z)
    for (int l = 0; l < kLayerCount; ++l) {
      const float v = f.body.layer(static_cast<Zone>(z), static_cast<Layer>(l));
      if (!(v >= 0.f)) return false;
    }
  return true;
}
}  // namespace

IV_TEST(Sim, EveryPairFinishesWithSaneStateAndExactlyOneMatchEnd) {
  for (int a = 0; a < kArchetypeCount; ++a)
    for (int b = 0; b < kArchetypeCount; ++b) {
      Duel duel(77 + static_cast<uint64_t>(a * 6 + b), true);
      duel.set_time_limit(tune::kMatchTimeLimitTicks);
      Ai aa(static_cast<Archetype>(a), Difficulty::Normal, 1000 + static_cast<uint64_t>(a)),
          ab(static_cast<Archetype>(b), Difficulty::Normal, 2000 + static_cast<uint64_t>(b));
      bool sane = true;
      while (!duel.result().over) {
        duel.Step(aa.Decide(MakeObservation(duel, Side::A)), ab.Decide(MakeObservation(duel, Side::B)));
        if (!Sane(duel.fighter(Side::A)) || !Sane(duel.fighter(Side::B))) sane = false;
      }
      IV_CHECK(sane);
      IV_CHECK_EQ(duel.log().CountOf(EventType::MatchEnd), 1);
      IV_CHECK(duel.result().reason != EndReason::None);
      // Events are time-ordered.
      Tick prev = 0;
      bool ordered = true;
      for (const Event& e : duel.log().events()) {
        if (e.tick < prev) ordered = false;
        prev = e.tick;
      }
      IV_CHECK(ordered);
    }
}

IV_TEST(Sim, AFinishedMatchIgnoresFurtherInput) {
  Duel duel(3, true);
  duel.fighter(Side::B).body.ApplyDamage(Zone::Reactor, 10000.f, StrikeKind::Heavy);
  duel.Step(Input(), Input());
  IV_CHECK(duel.result().over);
  IV_CHECK(duel.result().reason == EndReason::ReactorDestroyed);
  IV_CHECK(duel.result().loser == Side::B);
  const uint64_t h = duel.log().hash();
  const Tick t = duel.tick();
  Input in;
  in.strikeHeld = true;
  for (int i = 0; i < 100; ++i) duel.Step(in, in);
  IV_CHECK(duel.log().hash() == h);
  IV_CHECK_EQ(duel.tick(), t);
}

IV_TEST(Sim, SimultaneousLossIsADraw) {
  Duel duel(3, true);
  duel.fighter(Side::A).body.ApplyDamage(Zone::Torso, 10000.f, StrikeKind::Heavy);
  duel.fighter(Side::B).body.ApplyDamage(Zone::Reactor, 10000.f, StrikeKind::Heavy);
  duel.Step(Input(), Input());
  IV_CHECK(duel.result().over && duel.result().draw);
}

IV_TEST(Sim, OverheatingForTooLongShutsTheMechDownAndLosesTheMatch) {
  Duel duel(3, true);
  Fighter& a = duel.fighter(Side::A);
  for (int t = 0; t < tune::kShutdownTicks + 30 && !duel.result().over; ++t) {
    a.res.heat = tune::kHeatMax;  // a hot mech that keeps getting heated
    duel.Step(Input(), Input());
  }
  IV_CHECK(duel.result().over);
  IV_CHECK(duel.result().reason == EndReason::PowerLoss);
  IV_CHECK(duel.result().loser == Side::A);
  IV_CHECK_EQ(duel.log().CountOf(EventType::Shutdown), 1);
}

IV_TEST(Sim, TimeLimitEndsAStalemateAsADraw) {
  Duel duel(3, true);
  duel.set_time_limit(600);
  while (!duel.result().over) duel.Step(Input(), Input());
  IV_CHECK(duel.result().draw);
  IV_CHECK(duel.result().reason == EndReason::TimeLimit);
  IV_CHECK_EQ(duel.tick(), 600);
}

IV_TEST(Sim, WaterCoolingLetsAHotMechRecoverFaster) {
  Rig dry, wet;
  wet.world.coolingMult[0] = 3.f;
  dry.A().res.heat = wet.A().res.heat = 60.f;
  dry.Step(600);
  wet.Step(600);
  IV_CHECK(wet.A().res.heat < dry.A().res.heat);
}

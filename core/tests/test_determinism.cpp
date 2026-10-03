// Determinism: fixed 60 Hz step, own seeded PRNG, no clock (CLAUDE.md). Same seed + same inputs = same event history.
#include "TestUtil.h"
#include "iv/Ai.h"
#include "iv/Rng.h"

using namespace iv;
using namespace ivtest;

namespace {

struct RunResult {
  uint64_t hash = 0;
  uint64_t count = 0;
  int ticks = 0;
  EndReason reason = EndReason::None;
  bool draw = false;
  Side loser = Side::A;
};

RunResult RunAiDuel(Archetype a, Archetype b, Difficulty d, uint64_t seed, int maxTicks) {
  Duel duel(seed, false);  // not even storing events: only the running hash
  duel.set_time_limit(maxTicks);
  Ai aa(a, d, seed * 2 + 1), ab(b, d, seed * 2 + 2);
  while (!duel.result().over) {
    const Input ia = aa.Decide(MakeObservation(duel, Side::A));
    const Input ib = ab.Decide(MakeObservation(duel, Side::B));
    duel.Step(ia, ib);
  }
  RunResult r;
  r.hash = duel.log().hash();
  r.count = duel.log().count();
  r.ticks = duel.tick();
  r.reason = duel.result().reason;
  r.draw = duel.result().draw;
  r.loser = duel.result().loser;
  return r;
}

// Random but reproducible human-like input generator for stress runs.
Input RandomInput(Rng& rng) {
  Input in;
  in.strikeHeld = rng.Chance(0.35f);
  in.side = static_cast<SwingSide>(rng.Below(4));
  in.target = static_cast<Zone>(rng.Below(kZoneCount));
  in.footwork = static_cast<Footwork>(rng.Below(4));
  in.arm = rng.Chance(0.5f) ? Arm::L : Arm::R;
  in.quick = rng.Chance(0.05f);
  in.cancel = rng.Chance(0.03f);
  in.toGrab = rng.Chance(0.02f);
  in.switchArm = rng.Chance(0.03f);
  in.reverse = rng.Chance(0.1f);
  in.guardHeld = rng.Chance(0.3f);
  in.guardSide = static_cast<SwingSide>(rng.Below(4));
  in.hardStance = rng.Chance(0.1f);
  in.move = static_cast<int8_t>(static_cast<int>(rng.Below(3)) - 1);
  in.dodge = rng.Chance(0.03f);
  in.dodgeDir = rng.Chance(0.5f) ? -1 : 1;
  in.weaponHeld = rng.Chance(0.1f);
  in.ultimate = rng.Chance(0.02f);
  in.setPriority = rng.Chance(0.01f);
  in.priority = static_cast<EnergyPriority>(rng.Below(4));
  return in;
}

uint64_t RunRandomInputs(uint64_t seed, int ticks) {
  Duel duel(seed, false);
  Rng a(seed + 1), b(seed + 2);
  for (int t = 0; t < ticks; ++t) duel.Step(RandomInput(a), RandomInput(b));
  return duel.log().hash();
}

// v2 stress: every weapon, a pre-filled ultimate gauge and a training dummy in the mix; returns (hash, cinematics seen).
struct V2Run {
  uint64_t hash;
  int cinematics;
  int ultimates;
};
V2Run RunV2(uint64_t seed, int ticks, bool dummy) {
  Duel duel(seed, true);
  duel.SetLoadout(Side::A, static_cast<WeaponKind>(seed % kWeaponKindCount));
  duel.SetLoadout(Side::B, static_cast<WeaponKind>((seed / 3) % kWeaponKindCount));
  duel.fighter(Side::A).ultimate = tune::kUltimateMax;
  if (dummy) duel.SetDummy(Side::B, DummyMode::Scripted);
  Rng a(seed + 1), b(seed + 2);
  for (int t = 0; t < ticks; ++t) {
    duel.Step(RandomInput(a), RandomInput(b));
    if (t % 1500 == 0) duel.fighter(Side::A).ultimate = tune::kUltimateMax;
  }
  V2Run r;
  r.hash = duel.log().hash();
  r.cinematics = duel.log().CountOf(EventType::CinematicBegin);
  r.ultimates = duel.log().CountOf(EventType::UltimateUsed);
  return r;
}

}  // namespace

IV_TEST(Determinism, V2WeaponsUltimateCinematicsAndDummyAreReproducible) {
  int cinematics = 0, ultimates = 0;
  for (uint64_t seed = 1; seed <= 9; ++seed) {
    const V2Run r1 = RunV2(seed, 8000, seed % 2 == 0);
    const V2Run r2 = RunV2(seed, 8000, seed % 2 == 0);
    IV_CHECK(r1.hash == r2.hash);
    IV_CHECK_EQ(r1.cinematics, r2.cinematics);
    cinematics += r1.cinematics;
    ultimates += r1.ultimates;
  }
  IV_CHECK(cinematics > 5);   // the scenarios really exercise the cut-scenes
  IV_CHECK(ultimates > 0);
  IV_CHECK(RunV2(1, 8000, false).hash != RunV2(2, 8000, false).hash);
}

IV_TEST(Determinism, SameSeedAndInputsGiveTheSameEventHistoryForEveryArchetypePair) {
  for (int a = 0; a < kArchetypeCount; ++a)
    for (int b = 0; b < kArchetypeCount; ++b) {
      const RunResult r1 = RunAiDuel(static_cast<Archetype>(a), static_cast<Archetype>(b), Difficulty::Normal, 1234, 60 * 60 * 6);
      const RunResult r2 = RunAiDuel(static_cast<Archetype>(a), static_cast<Archetype>(b), Difficulty::Normal, 1234, 60 * 60 * 6);
      IV_CHECK(r1.hash == r2.hash);
      IV_CHECK(r1.count == r2.count);
      IV_CHECK_EQ(r1.ticks, r2.ticks);
      IV_CHECK(r1.reason == r2.reason);
      IV_CHECK(r1.count > 10);
    }
}

IV_TEST(Determinism, DifferentSeedsGiveDifferentHistories) {
  int differing = 0;
  for (uint64_t s = 1; s <= 10; ++s) {
    const RunResult r1 = RunAiDuel(Archetype::Trickster, Archetype::Breaker, Difficulty::Hard, s, 60 * 60 * 6);
    const RunResult r2 = RunAiDuel(Archetype::Trickster, Archetype::Breaker, Difficulty::Hard, s + 100, 60 * 60 * 6);
    if (r1.hash != r2.hash) ++differing;
  }
  IV_CHECK_EQ(differing, 10);
}

IV_TEST(Determinism, RandomInputStressRunsAreReproducible) {
  for (uint64_t seed = 1; seed <= 8; ++seed) {
    IV_CHECK(RunRandomInputs(seed, 6000) == RunRandomInputs(seed, 6000));
  }
  IV_CHECK(RunRandomInputs(1, 6000) != RunRandomInputs(2, 6000));
}

IV_TEST(Determinism, ResetReproducesTheRunInTheSameObject) {
  Duel duel(5, true);
  Rng a(10), b(11);
  for (int t = 0; t < 3000; ++t) duel.Step(RandomInput(a), RandomInput(b));
  const uint64_t h1 = duel.log().hash();
  duel.Reset(5);
  Rng a2(10), b2(11);
  for (int t = 0; t < 3000; ++t) duel.Step(RandomInput(a2), RandomInput(b2));
  IV_CHECK(duel.log().hash() == h1);
}

IV_TEST(Determinism, RecordingEventsDoesNotChangeTheHash) {
  Duel keep(8, true), drop(8, false);
  Rng a(1), b(2), a2(1), b2(2);
  for (int t = 0; t < 4000; ++t) {
    keep.Step(RandomInput(a), RandomInput(b));
    drop.Step(RandomInput(a2), RandomInput(b2));
  }
  IV_CHECK(keep.log().hash() == drop.log().hash());
  IV_CHECK(keep.log().count() == drop.log().count());
  IV_CHECK(keep.log().events().size() == keep.log().count());
  IV_CHECK(drop.log().events().empty());
}

IV_TEST(Determinism, RngIsAFixedSequenceIndependentOfAnyClock) {
  Rng r(42);
  const uint32_t first = r.Next();
  Rng r2(42);
  IV_CHECK_EQ(first, r2.Next());
  // Known-answer values of this exact PCG32 seeding: if they ever change, every recorded replay breaks.
  Rng k(1);
  IV_CHECK_EQ(k.Next(), 0xf063dc4bu);
  IV_CHECK_EQ(k.Next(), 0xb1241f91u);
  IV_CHECK_EQ(k.Next(), 0xf842f2c2u);
  Rng b(7);
  IV_CHECK_EQ(b.Below(1000), 593u);
  // Bounded draws stay in range and look uniform enough.
  Rng u(7);
  int buckets[4] = {};
  for (int i = 0; i < 40000; ++i) ++buckets[u.Below(4)];
  for (int i = 0; i < 4; ++i) IV_CHECK(buckets[i] > 9500 && buckets[i] < 10500);
  for (int i = 0; i < 1000; ++i) {
    const float x = u.Unit();
    IV_CHECK(x >= 0.f && x < 1.f);
  }
}

// Module 5: AI sees only what a human sees, reacts no faster than ~200 ms, archetypes differ (pitch §20, §8).
#include <cstring>
#include <type_traits>

#include "TestUtil.h"
#include "iv/Ai.h"

using namespace iv;
using namespace ivtest;

// The AI's entry point takes an Observation and nothing else: the opponent's Input, held duration
// of a windup and target zone cannot reach it through the API (pitch §20 "Бот не должен читать кнопки игрока").
static_assert(std::is_same<decltype(&Ai::Decide), Input (Ai::*)(const Observation&)>::value, "Ai::Decide must take only an Observation");

namespace {

bool SameInput(const Input& a, const Input& b) {
  return a.strikeHeld == b.strikeHeld && a.side == b.side && a.target == b.target && a.footwork == b.footwork && a.arm == b.arm &&
         a.quick == b.quick && a.cancel == b.cancel && a.toGrab == b.toGrab && a.switchArm == b.switchArm && a.reverse == b.reverse &&
         a.guardHeld == b.guardHeld && a.guardSide == b.guardSide && a.hardStance == b.hardStance && a.move == b.move &&
         a.dodge == b.dodge && a.dodgeDir == b.dodgeDir && a.weaponHeld == b.weaponHeld && a.setPriority == b.setPriority &&
         a.priority == b.priority;
}

// Scripted opponent: starts a heavy windup at tick `start`, holds it for `hold` ticks and releases.
Input Scripted(int t, int start, int hold, Zone target) {
  Input in;
  if (t >= start && t < start + hold) {
    in.strikeHeld = true;
    in.side = SwingSide::Up;
    in.target = target;
  }
  return in;
}

}  // namespace

IV_TEST(Ai, ObservationDoesNotChangeWithTheOpponentsHiddenTargetChoice) {
  // Two worlds that differ only in which zone B is secretly aiming at while winding up.
  Duel d1(7), d2(7);
  d1.set_distance(20.f);
  d2.set_distance(20.f);
  bool allEqual = true;
  for (int t = 0; t < 40; ++t) {
    d1.Step(Input(), Scripted(t, 3, 30, Zone::Head));
    d2.Step(Input(), Scripted(t, 3, 30, Zone::LegL));
    if (HashObservation(MakeObservation(d1, Side::A)) != HashObservation(MakeObservation(d2, Side::A))) allEqual = false;
  }
  IV_CHECK(allEqual);
  IV_CHECK(d1.fighter(Side::B).strike.target != d2.fighter(Side::B).strike.target);  // the worlds really differ
}

IV_TEST(Ai, ObservationHidesOpponentStabilityHeatAndEnergyNumbers) {
  Duel d1(1), d2(1);
  d2.fighter(Side::B).res.energy = 10.f;
  d2.fighter(Side::B).res.stability = 80.f;
  d2.fighter(Side::B).res.heat = 20.f;
  d1.Step(Input(), Input());
  d2.Step(Input(), Input());
  // Raw numbers are not part of what A can see...
  const Observation o1 = MakeObservation(d1, Side::A);
  const Observation o2 = MakeObservation(d2, Side::A);
  IV_CHECK(HashObservation(o1) == HashObservation(o2));
  // ...but the visible symptom is: a swaying mech is noticed, an overheating one steams.
  d2.fighter(Side::B).res.stability = 20.f;
  IV_CHECK(MakeObservation(d2, Side::A).opp.unsteady);
  d2.fighter(Side::B).res.heat = 90.f;
  d2.Step(Input(), Input());
  IV_CHECK(MakeObservation(d2, Side::A).opp.heatWarning);
}

IV_TEST(Ai, DecisionsDoNotDependOnTheOpponentsHiddenIntent) {
  // Same seeds, same observable history, different secret target choice: identical AI inputs.
  for (int arch = 0; arch < kArchetypeCount; ++arch) {
    Duel d1(11), d2(11);
    d1.set_distance(20.f);
    d2.set_distance(20.f);
    Ai a1(static_cast<Archetype>(arch), Difficulty::Hard, 99), a2(static_cast<Archetype>(arch), Difficulty::Hard, 99);
    bool same = true;
    for (int t = 0; t < 120; ++t) {
      const Input i1 = a1.Decide(MakeObservation(d1, Side::A));
      const Input i2 = a2.Decide(MakeObservation(d2, Side::A));
      if (!SameInput(i1, i2)) same = false;
      d1.Step(i1, Scripted(t, 5, 40, Zone::Head));
      d2.Step(i2, Scripted(t, 5, 40, Zone::LegR));
    }
    IV_CHECK(same);
  }
}

IV_TEST(Ai, ReactionDelayNeverBelowTheMinimumOnAnyDifficulty) {
  for (int a = 0; a < kArchetypeCount; ++a)
    for (int d = 0; d < kDifficultyCount; ++d) {
      Ai ai(static_cast<Archetype>(a), static_cast<Difficulty>(d), 5);
      IV_CHECK(ai.reactionDelay() >= tune::kMinReactionTicks);
    }
  IV_CHECK(tune::kMinReactionTicks >= MsToTicks(190));  // pitch §20: nothing near an impossible 50 ms
  Ai easy(Archetype::Counterpuncher, Difficulty::Easy, 1), normal(Archetype::Counterpuncher, Difficulty::Normal, 1),
      hard(Archetype::Counterpuncher, Difficulty::Hard, 1);
  IV_CHECK(easy.reactionDelay() > normal.reactionDelay());
  IV_CHECK(normal.reactionDelay() > hard.reactionDelay());
}

IV_TEST(Ai, FirstReactionToAnAttackComesNoEarlierThanTheReactionDelay) {
  for (int d = 0; d < kDifficultyCount; ++d) {
    for (int arch = 0; arch < kArchetypeCount; ++arch) {
      const int start = 30;
      Duel base(3), atk(3);
      base.set_distance(18.f);
      atk.set_distance(18.f);
      Ai ab(static_cast<Archetype>(arch), static_cast<Difficulty>(d), 21), aa(static_cast<Archetype>(arch), static_cast<Difficulty>(d), 21);
      int firstDiff = -1;
      for (int t = 0; t < 200 && firstDiff < 0; ++t) {
        const Input ib = ab.Decide(MakeObservation(base, Side::A));
        const Input ia = aa.Decide(MakeObservation(atk, Side::A));
        if (!SameInput(ib, ia)) firstDiff = t;
        base.Step(ib, Input());
        atk.Step(ia, Scripted(t, start, 60, Zone::Torso));
      }
      // B's windup exists in the world from step `start`; A must not act on it before `delay` ticks have passed.
      IV_CHECK(firstDiff < 0 || firstDiff >= start + aa.reactionDelay());
    }
  }
}

IV_TEST(Ai, DifficultyChangesReadingAndPositioningNotDamage) {
  const int di[3] = {0, 1, 2};
  for (int i = 1; i < 3; ++i) {
    IV_CHECK(tune::kAnalysisDepth[di[i]] > tune::kAnalysisDepth[di[i - 1]]);
    IV_CHECK(tune::kPositionQuality[di[i]] > tune::kPositionQuality[di[i - 1]]);
    IV_CHECK(tune::kParryTimingJitter[di[i]] < tune::kParryTimingJitter[di[i - 1]]);
    IV_CHECK(tune::kReactionTicks[di[i]] < tune::kReactionTicks[di[i - 1]]);
  }
  // Same strike, same state, same damage no matter who pilots the attacker: Fighter has no difficulty input at all.
  Fighter f1(Side::A), f2(Side::A);
  f1.strike.kind = f2.strike.kind = StrikeKind::Heavy;
  IV_CHECK_NEAR(f1.StrikeDamage(), f2.StrikeDamage(), 1e-6);
}

namespace {
struct Profile {
  int heavy = 0, quick = 0, grabs = 0, feints = 0, shots = 0, firstAttackTick = 100000;
  int zone[kZoneCount] = {};
  int contacts = 0;
};

void Harvest(const Duel& duel, Profile* p) {
  for (const Event& e : duel.log().events()) {
    if (e.actor == Side::A && e.type == EventType::Committed) {
      if (e.a == static_cast<int>(StrikeKind::Heavy)) ++p->heavy;
      else if (e.a == static_cast<int>(StrikeKind::Quick)) ++p->quick;
      else ++p->grabs;
    }
    if (e.actor == Side::A && e.type == EventType::WindupStarted) p->firstAttackTick = std::min(p->firstAttackTick, e.tick);
    if (e.actor == Side::A && e.type == EventType::Feint) ++p->feints;
    if (e.actor == Side::A && e.type == EventType::WeaponFired) ++p->shots;
    if (e.actor == Side::A && e.type == EventType::StrikeContact) {
      ++p->zone[Index(e.zone)];
      ++p->contacts;
    }
  }
}

// Fights a passive dummy for `ticks` ticks; a defeated dummy is replaced by a fresh match.
Profile RunAgainstDummy(Archetype a, uint64_t seed, int ticks) {
  Duel duel(seed, true);
  duel.set_distance(40.f);
  Ai ai(a, Difficulty::Normal, seed);
  Profile p;
  uint64_t round = 0;
  for (int t = 0; t < ticks; ++t) {
    duel.Step(ai.Decide(MakeObservation(duel, Side::A)), Input());
    if (duel.result().over) {
      Harvest(duel, &p);
      duel.Reset(seed + ++round);
      duel.set_distance(40.f);
    }
  }
  Harvest(duel, &p);
  return p;
}

Profile Sum(Archetype a, int ticks) {
  Profile total;
  for (uint64_t s = 1; s <= 6; ++s) {
    const Profile p = RunAgainstDummy(a, s, ticks);
    total.heavy += p.heavy;
    total.quick += p.quick;
    total.grabs += p.grabs;
    total.feints += p.feints;
    total.shots += p.shots;
    total.contacts += p.contacts;
    total.firstAttackTick = std::min(total.firstAttackTick, p.firstAttackTick);
    for (int z = 0; z < kZoneCount; ++z) total.zone[z] += p.zone[z];
  }
  return total;
}

float Share(const Profile& p, std::initializer_list<Zone> zones) {
  int n = 0;
  for (Zone z : zones) n += p.zone[Index(z)];
  return p.contacts > 0 ? static_cast<float>(n) / static_cast<float>(p.contacts) : 0.f;
}
}  // namespace

IV_TEST(Ai, ArchetypesHaveDistinctStyles) {
  const int ticks = 3600 * 2;
  const Profile breaker = Sum(Archetype::Breaker, ticks);
  const Profile hunter = Sum(Archetype::LimbHunter, ticks);
  const Profile trickster = Sum(Archetype::Trickster, ticks);
  const Profile gunner = Sum(Archetype::Gunner, ticks);
  const Profile grappler = Sum(Archetype::Grappler, ticks);
  const Profile counter = Sum(Archetype::Counterpuncher, ticks);

  IV_CHECK(breaker.contacts > 20 && hunter.contacts > 20);
  IV_CHECK(Share(breaker, {Zone::Torso}) > Share(hunter, {Zone::Torso}));  // pitch §20: the Breaker presses the centre
  IV_CHECK(Share(hunter, {Zone::ArmL, Zone::ArmR, Zone::LegL, Zone::LegR}) > Share(breaker, {Zone::ArmL, Zone::ArmR, Zone::LegL, Zone::LegR}));
  IV_CHECK(trickster.feints > breaker.feints * 2);                         // pitch §20: feints and delays
  IV_CHECK(gunner.shots > 0 && breaker.shots == 0);                        // pitch §20: the Gunner uses the weapon
  IV_CHECK(grappler.grabs > breaker.grabs);                                // pitch §20: the Grappler looks for the grab
  IV_CHECK(counter.heavy + counter.quick < breaker.heavy + breaker.quick);  // pitch §20: the Counterpuncher rarely starts
}

IV_TEST(Ai, HabitMemoryLearnsWhatTheOpponentDoesAfterABlock) {
  Ai ai(Archetype::Counterpuncher, Difficulty::Hard, 4);
  HabitResponse r;
  float share = 0.f;
  r = ai.memory().Likely(HabitContext::AfterBlocked, &share);
  IV_CHECK(share == 0.f);  // no data yet
  // Synthetic observation stream: my strike is blocked, and the opponent then walks away (move -1), four times.
  Observation o;
  for (int round = 0; round < 4; ++round) {
    for (int k = 0; k < 120; ++k) {
      o.tick = round * 400 + k;
      o.distance = 25.f;
      o.self.sinceOwn = k;  // my last strike resolved at tick round*400
      o.self.lastOwnOutcome = Outcome::Blocked;
      o.opp.move = k >= 5 ? -1 : 0;
      ai.Decide(o);
    }
    o.self.sinceOwn = 100000;
    for (int k = 120; k < 400; ++k) {
      o.tick = round * 400 + k;
      o.opp.move = 0;
      ai.Decide(o);
    }
  }
  r = ai.memory().Likely(HabitContext::AfterBlocked, &share);
  IV_CHECK(r == HabitResponse::Retreat);
  IV_CHECK(share >= 0.75f);
  IV_CHECK(ai.memory().total[static_cast<int>(HabitContext::AfterBlocked)] >= 3);
}

IV_TEST(Ai, ComboMemoryCountsWhichSwingFollowsWhich) {
  Ai ai(Archetype::Counterpuncher, Difficulty::Hard, 4);
  Observation o;
  int tick = 0;
  auto swing = [&](SwingSide side) {
    for (int k = 0; k < 40; ++k) {  // visible windup
      o.tick = tick++;
      o.opp.phase = Phase::Windup;
      o.opp.side = side;
      ai.Decide(o);
    }
    for (int k = 0; k < 40; ++k) {  // idle gap
      o.tick = tick++;
      o.opp.phase = Phase::Idle;
      ai.Decide(o);
    }
  };
  for (int i = 0; i < 4; ++i) {
    swing(SwingSide::Up);
    swing(SwingSide::Right);  // "after an Up swing he always follows with Right"
  }
  IV_CHECK(ai.memory().combo[Index(SwingSide::Up)][Index(SwingSide::Right)] >= 3);
  IV_CHECK_EQ(ai.memory().combo[Index(SwingSide::Up)][Index(SwingSide::Left)], 0);
}

IV_TEST(Ai, LimbHunterTargetsDestroyedLimbsForSevering) {
  Duel duel(2, true);
  duel.set_distance(20.f);
  duel.fighter(Side::B).body.ApplyDamage(Zone::ArmL, 1000.f, StrikeKind::Heavy);  // Destroyed, not yet severed
  Ai ai(Archetype::LimbHunter, Difficulty::Hard, 2);
  for (int t = 0; t < 3600 * 3 && !duel.fighter(Side::B).body.severed(Zone::ArmL); ++t) {
    duel.Step(ai.Decide(MakeObservation(duel, Side::A)), Input());
    if (duel.result().over) break;
  }
  IV_CHECK(duel.fighter(Side::B).body.severed(Zone::ArmL));  // pitch §12: hit or grab finishes the broken joint
  IV_CHECK(duel.log().CountOf(EventType::LimbSevered) >= 1);
}

IV_TEST(Ai, DefendingAiBlocksOrParriesAnObviousHeavyStrike) {
  // A Hard Counterpuncher facing repeated heavy swings should defend a good share of them.
  Duel duel(9, true);
  duel.set_distance(20.f);
  Ai ai(Archetype::Counterpuncher, Difficulty::Hard, 9);
  int t = 0;
  for (int swing = 0; swing < 12 && !duel.result().over; ++swing) {
    for (int k = 0; k < 130; ++k, ++t) {
      Input in;
      if (k < tune::kWindupMinTicks + 4) {
        in.strikeHeld = true;
        in.side = SwingSide::Up;
        in.target = Zone::Torso;
      }
      duel.Step(ai.Decide(MakeObservation(duel, Side::A)), in);
    }
    for (int k = 0; k < 400; ++k, ++t) duel.Step(ai.Decide(MakeObservation(duel, Side::A)), Input());  // let both settle
  }
  int hits = 0, defended = 0;
  for (const Event& e : duel.log().events()) {
    if (e.type != EventType::StrikeContact || e.actor != Side::B) continue;
    if (e.b == static_cast<int>(Outcome::Hit)) ++hits;
    else if (e.b != static_cast<int>(Outcome::Whiff)) ++defended;
  }
  IV_CHECK(hits + defended >= 6);
  IV_CHECK(defended > hits);
}

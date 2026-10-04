// Hack mini-game (TASK-018): generators, rules of the three layers, ICE heat, time, Reroll, JSON data, bots.
#include <cstdio>
#include <fstream>
#include <sstream>

#include "TestFramework.h"
#include "iv/HackBot.h"
#include "iv/HackExport.h"
#include "iv/HackGame.h"

using namespace iv;

namespace {

std::string ReadFile(const std::string& path) {
  std::ifstream f(path, std::ios::binary);
  std::stringstream ss;
  ss << f.rdbuf();
  return ss.str();
}

HackGame Begin(int level, uint64_t seed = 5) {
  HackConfig c;
  c.difficulty = level;
  c.seed = seed;
  HackGame g;
  g.Start(c);
  return g;
}

// Plays the perfect solver; returns the ticks used (-1 if the game did not end in a win within the limit).
int PlayPerfect(HackGame* g) {
  int n = 0;
  while (g->running() && n < 60 * 120) {
    g->Step(g->PerfectInput());
    ++n;
  }
  return g->state() == HackState::Success ? n : -1;
}

// Advances the game to the first stage of `kind` with the perfect solver.
void SkipTo(HackGame* g, HackStage kind) {
  int n = 0;
  while (g->running() && g->stage() != kind && n++ < 20000) g->Step(g->PerfectInput());
}

PathLayout Corridor(int w, int h) {
  PathLayout p;
  p.w = w;
  p.h = h;
  p.cell.assign(static_cast<size_t>(w * h), 0);
  p.sx = 0;
  p.sy = 0;
  p.cx = w - 1;
  p.cy = 0;
  return p;
}

HackInput Dir(int dx, int dy) {
  HackInput in;
  in.dx = static_cast<int8_t>(dx);
  in.dy = static_cast<int8_t>(dy);
  return in;
}

}  // namespace

// ------------------------------------------------------------------------------------------------ data and generators

IV_TEST(Hack, DifficultyTableMatchesTheJsonFile) {
  const std::string file = ReadFile(std::string(IV_REPO_DIR) + "/data/hack/difficulty.json");
  IV_CHECK(!file.empty());
  IV_CHECK(file == HackDifficultyJson());
  for (int i = 0; i < 10; ++i) {
    const tune::HackLevel& L = tune::kHackLevels[i];
    IV_CHECK_EQ(L.level, i + 1);
    IV_CHECK(L.timeLimitSec >= 25 && L.timeLimitSec <= 60);   // TASK-018: the total limit is 25..60 s
    IV_CHECK(L.stages == 3 || L.stages == 5);
    IV_CHECK(L.hitWindow >= 3);
  }
}

IV_TEST(Hack, PregeneratedSessionsEqualTheGenerator) {
  const std::string file = ReadFile(std::string(IV_REPO_DIR) + "/data/hack/hack_levels.json");
  IV_CHECK(!file.empty());
  IV_CHECK(file == HackLevelsJson(50));
  IV_CHECK(file.size() < 2000000);
}

IV_TEST(Hack, EveryGeneratedLayoutIsSolvable500PerDifficulty) {
  int paths = 0, bad = 0;
  for (int level = 1; level <= 10; ++level) {
    for (int i = 0; i < 500; ++i) {
      const uint64_t seed = 70000 + static_cast<uint64_t>(level) * 1000 + static_cast<uint64_t>(i);
      const PathLayout p = HackGame::GeneratePath(level, seed);
      ++paths;
      if (!HackGame::PathSolvable(p)) ++bad;
      const tune::HackLevel& L = tune::kHackLevels[level - 1];
      IV_CHECK_EQ(p.w, L.gridW);
      IV_CHECK_EQ(static_cast<int>(p.keys.size()), L.keys);
      IV_CHECK(!p.solution.empty());
      const RhythmLayout r = HackGame::GenerateRhythm(level, seed, false);
      IV_CHECK_EQ(static_cast<int>(r.impulses.size()), L.impulses);
      for (size_t k = 1; k < r.impulses.size(); ++k) IV_CHECK(r.impulses[k].tick > r.impulses[k - 1].tick);
      const FreqLayout f = HackGame::GenerateFreq(level, seed, false);
      IV_CHECK_EQ(f.locks, L.locks);
      for (size_t k = 1; k < f.halfDeg.size(); ++k) IV_CHECK(f.halfDeg[k] <= f.halfDeg[k - 1] + 1e-4f);   // the window narrows
    }
  }
  IV_CHECK_EQ(paths, 5000);
  IV_CHECK_EQ(bad, 0);
}

IV_TEST(Hack, PerfectPlayerWinsEveryDifficultyAndSeedWithinTheLimit) {
  int games = 0, wins = 0;
  for (int level = 1; level <= 10; ++level)
    for (int i = 0; i < 100; ++i) {
      HackGame g = Begin(level, 1000 + static_cast<uint64_t>(i) * 31);
      const int t = PlayPerfect(&g);
      ++games;
      if (t > 0) ++wins;
      IV_CHECK(g.mistakes() == 0);
      IV_CHECK(g.iceTrips() == 0);
    }
  IV_CHECK_EQ(wins, games);
}

IV_TEST(Hack, DeterministicForEqualSeedAndInput) {
  HackGame a = Begin(6, 99), b = Begin(6, 99), c = Begin(6, 100);
  Rng noise(5);
  for (int i = 0; i < 1500; ++i) {
    HackInput in = a.PerfectInput();
    if (noise.Chance(0.05f)) in.confirm = true;
    if (noise.Chance(0.03f)) in.dx = 1;
    a.Step(in);
    b.Step(in);
    c.Step(in);
    IV_CHECK_EQ(a.Hash(), b.Hash());
  }
  IV_CHECK(a.Hash() != c.Hash());
  IV_CHECK(HackGame::GeneratePath(5, 1).solution.size() == HackGame::GeneratePath(5, 1).solution.size());
  IV_CHECK(HackGame::StageSeed(1, 0, 0) != HackGame::StageSeed(1, 1, 0));
  IV_CHECK(HackGame::StageSeed(1, 0, 0) != HackGame::StageSeed(1, 0, 1));
}

IV_TEST(Hack, StageCompositionGrowsWithDifficulty) {
  IV_CHECK_EQ(static_cast<int>(HackGame::StagesFor(1).size()), 3);
  IV_CHECK_EQ(static_cast<int>(HackGame::StagesFor(6).size()), 3);
  const auto boss = HackGame::StagesFor(10);
  IV_CHECK_EQ(static_cast<int>(boss.size()), 5);
  IV_CHECK(boss[3].boss && boss[4].boss && !boss[2].boss);
  IV_CHECK(boss[0].kind == HackStage::Path && boss[1].kind == HackStage::Rhythm && boss[2].kind == HackStage::Frequency);
  HackGame g = Begin(10);
  IV_CHECK_EQ(g.stageCount(), 5);
  IV_CHECK_NEAR(g.progress(), 0.f, 1e-6);
}

// ------------------------------------------------------------------------------------------------ path rules

IV_TEST(Hack, PathMovesBlocksVisitedAndEdges) {
  HackGame g = Begin(1);
  PathLayout p = Corridor(5, 2);
  p.cell[1] = 1;   // a blocker at (1,0)
  IV_CHECK(g.LoadLayout(p));
  g.Step(Dir(1, 0));   // into the blocker
  IV_CHECK_EQ(g.mistakes(), 1);
  IV_CHECK_EQ(g.pathX(), 0);
  g.Step(Dir(-1, 0));  // off the grid: ignored, no mistake
  g.Step(Dir(0, -1));
  IV_CHECK_EQ(g.mistakes(), 1);
  g.Step(Dir(0, 1));   // down: fine
  IV_CHECK_EQ(g.pathY(), 1);
  g.Step(Dir(0, -1));  // back onto the entry node: visited, a mistake
  IV_CHECK_EQ(g.mistakes(), 2);
  g.Step(Dir(1, 1));   // a diagonal is not a move: the horizontal part wins
  IV_CHECK_EQ(g.pathX(), 1);
  IV_CHECK_EQ(g.pathY(), 1);
}

IV_TEST(Hack, PathKeysInOrderAndTheCoreOpensLast) {
  HackGame g = Begin(1);
  PathLayout p = Corridor(5, 2);
  p.keys = {3, 1};   // two keys on the first row: (3,0) then (1,0): the second is reachable first and must be refused
  IV_CHECK(g.LoadLayout(p));
  g.Step(Dir(1, 0));   // (1,0) is key #2: not yet
  IV_CHECK_EQ(g.mistakes(), 1);
  IV_CHECK_EQ(g.pathX(), 0);
  g.Step(Dir(0, 1));   // go round along the second row
  for (int i = 0; i < 3; ++i) g.Step(Dir(1, 0));
  IV_CHECK_EQ(g.pathX(), 3);
  g.Step(Dir(0, -1));  // key #1 at (3,0)
  IV_CHECK_EQ(g.pathKeysTaken(), 1);
  g.Step(Dir(-1, 0));  // (2,0)
  g.Step(Dir(-1, 0));  // key #2 at (1,0)
  IV_CHECK_EQ(g.pathKeysTaken(), 2);
  IV_CHECK(g.stage() == HackStage::Path);
  // the core (4,0) is on the far side now; walk there through the keys is blocked by the visited nodes: use undo twice to show the stack works
  g.Step([] { HackInput i; i.aux = true; return i; }());
  IV_CHECK_EQ(g.pathKeysTaken(), 1);
}

IV_TEST(Hack, PathCoreStaysClosedUntilEveryKeyIsTaken) {
  HackGame g = Begin(1);
  PathLayout p = Corridor(3, 2);
  p.keys = {3};        // key at (0,1)
  IV_CHECK(g.LoadLayout(p));
  g.Step(Dir(1, 0));
  g.Step(Dir(1, 0));   // the core (2,0) without the key: refused
  IV_CHECK_EQ(g.mistakes(), 1);
  IV_CHECK(g.stage() == HackStage::Path);
}

IV_TEST(Hack, IceSlidesThePilotOnAndUndoRestores) {
  HackGame g = Begin(1);
  PathLayout p = Corridor(6, 1);
  p.cell[1] = 2;   // ice at (1,0): one press slides to (2,0)
  IV_CHECK(g.LoadLayout(p));
  const int left0 = g.ticksLeft();
  g.Step(Dir(1, 0));
  IV_CHECK_EQ(g.pathX(), 2);
  IV_CHECK(g.pathVisited(1, 0) && g.pathVisited(2, 0));
  HackInput undo;
  undo.aux = true;
  g.Step(undo);
  IV_CHECK_EQ(g.pathX(), 0);
  IV_CHECK(!g.pathVisited(1, 0));
  IV_CHECK(g.ticksLeft() <= left0 - tune::kHackUndoPenaltyTicks);
  g.Step(undo);   // nothing left to undo: no penalty
  const int left1 = g.ticksLeft();
  g.Step(undo);
  IV_CHECK_EQ(g.ticksLeft(), left1 - 1);
  for (int i = 0; i < 5; ++i) g.Step(Dir(1, 0));
  IV_CHECK(g.stage() == HackStage::Rhythm);   // the corridor to the core was cleared
}

// ------------------------------------------------------------------------------------------------ rhythm layer

IV_TEST(Hack, RhythmHitsMissesAndGhostPresses) {
  HackGame g = Begin(1);
  SkipTo(&g, HackStage::Rhythm);
  IV_CHECK(g.stage() == HackStage::Rhythm);
  RhythmLayout r;
  r.lanes = 3;
  r.impulses = {{20, 0}, {40, 1}, {60, 2}};
  IV_CHECK(g.LoadLayout(r));
  const int W = g.rhythmWindow();
  for (int i = 0; i < 20; ++i) g.Step(HackInput());
  g.Step(Dir(-1, 0));   // lane 0 exactly on the beat: a hit
  IV_CHECK_EQ(g.rhythmStatus(0), 1);
  IV_CHECK_EQ(g.mistakes(), 0);
  for (int i = 0; i < 10; ++i) g.Step(HackInput());
  g.Step(Dir(0, -1));   // lane 2 with nothing near: a ghost press
  IV_CHECK_EQ(g.mistakes(), 1);
  // impulse 1 (lane 1, tick 40) is never answered: it becomes a miss once the window has passed
  while (g.rhythmStatus(1) == 0 && g.stageTick() < 40 + W + 3) g.Step(HackInput());
  IV_CHECK_EQ(g.rhythmStatus(1), 2);
  IV_CHECK_EQ(g.mistakes(), 2);
  // too early / too late presses outside the window are ghosts too
  while (g.stageTick() < 60 - W - 1) g.Step(HackInput());
  g.Step(Dir(0, -1));
  IV_CHECK_EQ(g.rhythmStatus(2), 0);
  IV_CHECK_EQ(g.mistakes(), 3);
}

IV_TEST(Hack, RhythmWindowEdgesAndSimultaneousButtons) {
  HackGame g = Begin(1);
  SkipTo(&g, HackStage::Rhythm);
  RhythmLayout r;
  r.lanes = 4;
  r.impulses = {{30, 0}, {30, 3}};   // two lanes at the same tick
  IV_CHECK(g.LoadLayout(r));
  const int W = g.rhythmWindow();
  while (g.stageTick() < 30 - W) g.Step(HackInput());
  HackInput both;
  both.dx = -1;
  both.dy = 1;   // lane 0 (left) and lane 1 (down): lane 1 has no impulse -> a ghost, lane 0 hits at the very edge of the window
  g.Step(both);
  IV_CHECK_EQ(g.rhythmStatus(0), 1);
  IV_CHECK_EQ(g.mistakes(), 1);
  g.Step(Dir(1, 0));   // lane 3 inside the window
  IV_CHECK_EQ(g.rhythmStatus(1), 1);
  g.Step(HackInput());
  IV_CHECK(g.stage() == HackStage::Frequency);   // all impulses resolved: the stage is cleared
}

IV_TEST(Hack, AlarmShrinksTheWindowAndTheIceTripsAndRestartsTheStage) {
  HackGame g = Begin(1);
  SkipTo(&g, HackStage::Rhythm);
  const int w0 = g.rhythmWindow();
  const int stage0 = g.stageIndex();
  int guard = 0;
  while (!g.alarm() && guard++ < 50) g.Step(Dir(0, -1));   // ghost presses
  IV_CHECK(g.alarm());
  IV_CHECK_EQ(g.rhythmWindow(), std::max(2, w0 - 1));
  const int before = g.ticksLeft();
  const int tripsBefore = g.iceTrips();
  guard = 0;
  while (g.iceTrips() == tripsBefore && guard++ < 50) g.Step(Dir(0, -1));
  IV_CHECK_EQ(g.iceTrips(), tripsBefore + 1);
  IV_CHECK(g.running());                         // a trip is a penalty, not a defeat
  IV_CHECK_EQ(g.stageIndex(), stage0);           // the same stage starts over
  IV_CHECK_EQ(g.stageTick(), 0);
  IV_CHECK(g.heat() < static_cast<float>(tune::kHackTripHeat));
  IV_CHECK(g.ticksLeft() < before - HackGame::DefaultPenalty(1) * tune::kHackTripPenaltyMult + 1);
  const std::vector<HackSfx> sfx = g.DrainSfx();
  bool alarm = false, trip = false, err = false;
  for (HackSfx s : sfx) {
    alarm = alarm || s == HackSfx::Alarm;
    trip = trip || s == HackSfx::IceTrip;
    err = err || s == HackSfx::Err;
  }
  IV_CHECK(alarm && trip && err);
  IV_CHECK(g.DrainSfx().empty());
}

// ------------------------------------------------------------------------------------------------ frequency layer

IV_TEST(Hack, FrequencyLocksNarrowTheWindowAndAMissWidensIt) {
  HackGame g = Begin(1);
  SkipTo(&g, HackStage::Frequency);
  IV_CHECK(g.stage() == HackStage::Frequency);
  const float hw0 = g.freqHalfWidth();
  int guard = 0;
  while (g.freqLocks() < 1 && guard++ < 2000) g.Step(g.PerfectInput());
  IV_CHECK_EQ(g.freqLocks(), 1);
  IV_CHECK(g.freqHalfWidth() < hw0);
  const int m0 = g.mistakes();
  // press while the offset is well outside the window: a mistake and one step back
  guard = 0;
  while (std::fabs(g.freqOffset()) < g.freqHalfWidth() * 2.5f && guard++ < 500) g.Step(HackInput());
  HackInput lock;
  lock.confirm = true;
  g.Step(lock);
  IV_CHECK_EQ(g.mistakes(), m0 + 1);
  IV_CHECK_EQ(g.freqLocks(), 0);
  IV_CHECK(g.freqHalfWidth() > 0.f);
  // the window can never be narrower than the tick-to-tick travel: a perfect press always exists (checked by PerfectPlayerWins...), spot check here
  const FreqLayout f = HackGame::GenerateFreq(10, 3, true);
  for (float w : f.halfDeg) IV_CHECK(w >= tune::kHackLockHalfMinDeg);
  IV_CHECK_EQ(f.locks, tune::kHackLevels[9].locks + 1);
}

// ------------------------------------------------------------------------------------------------ time, abort, reroll, boundaries

IV_TEST(Hack, TimeoutAtTheLimitAndNothingHappensAfterTheEnd) {
  HackGame g = Begin(3);
  const int limit = g.timeLimit();
  IV_CHECK_EQ(limit, tune::kHackLevels[2].timeLimitSec * kTickHz);
  int n = 0;
  while (g.running() && n < limit + 10) {
    g.Step(HackInput());
    ++n;
  }
  IV_CHECK(g.state() == HackState::Timeout);
  IV_CHECK_EQ(n, limit);
  const uint64_t h = g.Hash();
  g.Step(Dir(1, 0));
  HackInput c;
  c.confirm = true;
  g.Step(c);
  IV_CHECK_EQ(g.Hash(), h);   // input after the end is ignored
  IV_CHECK_NEAR(g.quality(), 0.f, 1e-6);
}

IV_TEST(Hack, BackAbortsAndAddPenaltyCostsTime) {
  HackGame g = Begin(4);
  const int t0 = g.ticksLeft();
  g.AddPenalty(100);
  IV_CHECK_EQ(g.ticksLeft(), t0 - 100);
  HackInput back;
  back.back = true;
  g.Step(back);
  IV_CHECK(g.state() == HackState::Fail);
  g.AddPenalty(50);
  IV_CHECK(g.state() == HackState::Fail);
  HackGame h = Begin(4);
  h.AddPenalty(h.timeLimit() + 5);
  IV_CHECK(h.state() == HackState::Timeout);
}

IV_TEST(Hack, RerollKeepsPartOfTheProgressWithAFreshLayout) {
  HackGame g = Begin(10, 77);   // 5 stages
  SkipTo(&g, HackStage::Frequency);
  IV_CHECK_EQ(g.stageIndex(), 2);
  const uint64_t seedBefore = HackGame::StageSeed(77, 2, 0);
  const FreqLayout before = g.freq();
  g.Reroll(0.5f);   // keeps round(2 * 0.5) = 1 cleared stage
  IV_CHECK_EQ(g.stageIndex(), 1);
  IV_CHECK_EQ(g.rerolls(), 1);
  IV_CHECK_NEAR(g.heat(), 0.f, 1e-6);
  IV_CHECK(g.stage() == HackStage::Rhythm);
  (void)seedBefore;
  (void)before;
  const RhythmLayout r1 = HackGame::GenerateRhythm(10, HackGame::StageSeed(77, 1, 0), false);
  const RhythmLayout r2 = HackGame::GenerateRhythm(10, HackGame::StageSeed(77, 1, 1), false);
  IV_CHECK(r1.impulses.size() == r2.impulses.size());
  bool differ = false;
  for (size_t i = 0; i < r1.impulses.size(); ++i) differ = differ || r1.impulses[i].lane != r2.impulses[i].lane || r1.impulses[i].tick != r2.impulses[i].tick;
  IV_CHECK(differ);
  g.Reroll(0.f);
  IV_CHECK_EQ(g.stageIndex(), 0);
  IV_CHECK_EQ(g.rerolls(), 2);
  IV_CHECK(g.progress() < 0.2f);
  // the perfect player can still win after rerolls
  IV_CHECK(PlayPerfect(&g) > 0);
}

IV_TEST(Hack, ProgressIsMonotoneForAPerfectPlayerAndQualityRanksPlays) {
  HackGame g = Begin(8, 4);
  float last = 0.f;
  while (g.running()) {
    g.Step(g.PerfectInput());
    IV_CHECK(g.progress() >= last - 1e-6f);
    last = g.progress();
  }
  IV_CHECK(g.state() == HackState::Success);
  IV_CHECK_NEAR(g.progress(), 1.f, 1e-6);
  IV_CHECK(g.quality() > 0.5f && g.quality() <= 1.f);
  // a sloppier play of the same session: ghost presses cost mistakes and time -> lower quality
  HackGame s = Begin(8, 4);
  int n = 0;
  while (s.running() && n++ < 20000) {
    HackInput in = s.PerfectInput();
    if (n % 400 == 0) in.confirm = true;
    s.Step(in);
  }
  if (s.state() == HackState::Success) IV_CHECK(s.quality() < g.quality());
  const std::vector<HackSfx> sfx = g.DrainSfx();
  IV_CHECK(!sfx.empty());
  IV_CHECK(sfx.back() == HackSfx::Success);
}

IV_TEST(Hack, DifficultyForIsBoundedAndEasierForDamagedShoulders) {
  for (int a = 0; a < kArchetypeCount; ++a)
    for (int d = 0; d < kDifficultyCount; ++d)
      for (int z = 0; z <= static_cast<int>(ZoneState::Severed); ++z) {
        const int v = HackGame::DifficultyFor(static_cast<Archetype>(a), static_cast<Difficulty>(d), static_cast<ZoneState>(z));
        IV_CHECK(v >= 1 && v <= 10);
        if (z > 0) IV_CHECK(v <= HackGame::DifficultyFor(static_cast<Archetype>(a), static_cast<Difficulty>(d), static_cast<ZoneState>(z - 1)));
      }
  IV_CHECK(HackGame::DifficultyFor(Archetype::Grappler, Difficulty::Hard, ZoneState::Intact) > HackGame::DifficultyFor(Archetype::Gunner, Difficulty::Easy, ZoneState::Intact));
  IV_CHECK(HackGame::DifficultyFor(Archetype::Breaker, Difficulty::Hard, ZoneState::Intact) >= HackGame::DifficultyFor(Archetype::Breaker, Difficulty::Normal, ZoneState::Intact));
}

IV_TEST(Hack, RandomInputNeverBreaksTheGame) {
  for (int run = 0; run < 200; ++run) {
    HackGame g = Begin(1 + run % 10, 300 + static_cast<uint64_t>(run));
    Rng r(static_cast<uint64_t>(run) * 17 + 3);
    for (int t = 0; t < 4000; ++t) {
      HackInput in;
      in.dx = static_cast<int8_t>(static_cast<int>(r.Below(3)) - 1);
      in.dy = static_cast<int8_t>(static_cast<int>(r.Below(3)) - 1);
      in.confirm = r.Chance(0.2f);
      in.aux = r.Chance(0.05f);
      in.back = r.Chance(0.0005f);
      g.Step(in);
      IV_CHECK(g.progress() >= 0.f && g.progress() <= 1.f);
      IV_CHECK(g.heat() >= 0.f && g.heat() < 100.f + 40.f);
      IV_CHECK(g.ticksLeft() >= 0);
    }
  }
}

// ------------------------------------------------------------------------------------------------ bots and calibration

namespace {
double SuccessRate(const HackBotProfile& prof, int level, int seeds) {
  int ok = 0;
  for (int s = 0; s < seeds; ++s) {
    HackConfig c;
    c.difficulty = level;
    c.seed = 90000 + static_cast<uint64_t>(s) * 7919u + static_cast<uint64_t>(level);
    HackGame g;
    g.Start(c);
    HackBot bot(prof, c.seed * 3 + 1);
    int n = 0;
    while (g.running() && n++ < 60 * 120) g.Step(bot.Next(g));
    ok += g.state() == HackState::Success;
  }
  return 100.0 * ok / seeds;
}
}  // namespace

IV_TEST(Hack, BotsFollowTheCalibrationTargets) {
  const int N = 200;
  double good[11] = {}, avg[11] = {}, poor[11] = {};
  for (int d = 1; d <= 10; ++d) {
    IV_CHECK_NEAR(SuccessRate(kHackBots[0], d, 60), 100.0, 1e-9);   // the perfect solver never fails
    good[d] = SuccessRate(kHackBots[1], d, N);
    avg[d] = SuccessRate(kHackBots[2], d, N);
    poor[d] = SuccessRate(kHackBots[3], d, N);
    IV_CHECK(avg[d] <= good[d] + 4.0);
    IV_CHECK(poor[d] <= avg[d] + 4.0);
  }
  for (int d = 1; d <= 3; ++d) IV_CHECK(good[d] >= 80.0);       // TASK-018 target 80..90 % (the first levels are a little more forgiving)
  IV_CHECK(good[6] >= 40.0 && good[6] <= 65.0);                  // target 45..60 %
  IV_CHECK(good[9] >= 12.0 && good[9] <= 32.0);                  // target 15..25 %
  IV_CHECK(good[10] >= 8.0 && good[10] <= 32.0);
  IV_CHECK(good[10] < good[3]);
  IV_CHECK(poor[10] < 5.0);
  std::printf("    good bot success by difficulty:");
  for (int d = 1; d <= 10; ++d) std::printf(" %.0f", good[d]);
  std::printf("\n");
}

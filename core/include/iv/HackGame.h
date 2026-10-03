// Hatch-hacking mini-game logic (STATUS §6B 4, TASK-017 interface, TASK-018 content).
//
// The game layer shows it full screen while the pilot sits on the enemy shoulder. The core owns the rules, the timer, the mistakes, the ICE
// heat and the quality; the screen only draws what the accessors expose and forwards `HackInput`. Deterministic: same config + same
// inputs = same state. No exceptions, no clocks, own PRNG.
//
// A session is a chain of stages (the table `tune::kHackLevels`, one row per difficulty 1..10):
//   Path       route a chain of nodes from the entry to the core on a grid: blockers, ice nodes that slide you on, keys to take in order
//   Rhythm     3..5 lanes of impulses run to the hit line: press the lane's button inside the window (miss or ghost press = mistake)
//   Frequency  two sectors rotate against each other: lock when your sector sits in the ICE window; every landed lock narrows the window
// Mistakes cost time and raise the ICE heat; at the alarm level the windows tighten; at 100 the ICE trips and the current stage restarts
// (a time penalty, never an instant defeat). Success = all stages cleared before the time limit.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "iv/Rng.h"
#include "iv/Tuning.h"
#include "iv/Types.h"

namespace iv {

enum class HackState : uint8_t { Idle, Running, Success, Fail, Timeout };
enum class HackStage : uint8_t { Path, Rhythm, Frequency };

// Sound / animation cues for the audio layer: hack_tick, hack_ok, hack_err, hack_alarm, hack_stage_clear, hack_success, hack_fail (+ the ICE trip).
enum class HackSfx : uint8_t { Tick, Ok, Err, Alarm, StageClear, Success, Fail, IceTrip };

// One tick of player intent. Direction fields are the direction pressed THIS tick (the screen sends one tick per press); on a pad they come
// from the stick / d-pad, on a keyboard from the arrows or WASD. Everything is reachable with the 4 directions + 2 buttons (no pointer).
struct HackInput {
  int8_t dx = 0;          // -1 / +1: left / right
  int8_t dy = 0;          // -1 / +1: up / down
  bool confirm = false;   // edge: main action (frequency: lock; rhythm: lane 5)
  bool back = false;      // edge: abort the hack (a failure: the pilot returns along the grapple)
  bool aux = false;       // edge: path: step back one move (costs time)
};

struct HackConfig {
  int difficulty = 5;               // 1..10
  uint64_t seed = 1;
  int timeLimitTicks = 0;           // 0 = the row of the table
  int mistakePenaltyTicks = 0;      // 0 = the row of the table
};

struct HackStep { int8_t dx = 0, dy = 0; };

struct PathLayout {
  int w = 0, h = 0;
  std::vector<uint8_t> cell;                  // w*h: 0 empty, 1 blocker, 2 ice (index y*w + x)
  int sx = 0, sy = 0, cx = 0, cy = 0;         // entry and core
  std::vector<int> keys;                      // key cell indices, to be taken in this order
  std::vector<int> route;                     // the reference route (cell indices from the entry to the core)
  std::vector<HackStep> solution;             // reference presses (an ice node costs no extra press)
};

struct RhythmImpulse { int tick; int lane; };
struct RhythmLayout {
  int lanes = 3;
  bool boss = false;
  std::vector<RhythmImpulse> impulses;        // ticks counted from the stage start (the first one is kHackLeadTicks)
};

struct FreqLayout {
  int locks = 3;
  bool boss = false;
  float hackerStart = 0.f, iceStart = 0.f;    // degrees
  float hackerSpeed = 0.f, iceSpeed = 0.f;    // degrees per tick (hacker turns +, ICE turns -)
  std::vector<float> halfDeg;                 // window half-width of every lock (narrowing)
};

struct HackStageSpec { HackStage kind; bool boss; };

class HackGame {
 public:
  HackGame() = default;
  void Start(const HackConfig& cfg);
  // Advances one 60 Hz tick. Ignored unless Running.
  void Step(const HackInput& in);

  // New layout after a swing to the other shoulder: keeps `keep` (0..1) of the cleared stages, the current stage is rebuilt, the heat resets.
  void Reroll(float keep);
  // Replaces the layout of the CURRENT stage (same kind) and restarts it: playing a pre-generated session from data/hack/hack_levels.json, tests.
  bool LoadLayout(const PathLayout& p);
  bool LoadLayout(const RhythmLayout& r);
  bool LoadLayout(const FreqLayout& f);
  // Time lost outside the player's control (the mech was hit while the pilot hangs on the hatch).
  void AddPenalty(int ticks);

  // ---- state for the screen ------------------------------------------------------------------
  HackState state() const { return state_; }
  bool running() const { return state_ == HackState::Running; }
  float progress() const;
  int mistakes() const { return mistakes_; }
  int ticksLeft() const { return ticksLeft_; }
  int timeLimit() const { return limit_; }
  int difficulty() const { return diff_; }
  int rerolls() const { return rerolls_; }
  int iceTrips() const { return trips_; }
  float heat() const { return heat_; }
  bool alarm() const { return alarm_; }
  float quality() const;      // 0..1 from time left, mistakes and ICE trips; 0 until the game is won
  int stageIndex() const { return stageIdx_; }
  int stageCount() const { return static_cast<int>(stages_.size()); }
  HackStage stage() const { return stages_.empty() ? HackStage::Path : stages_[static_cast<size_t>(stageIdx_ < stageCount() ? stageIdx_ : stageCount() - 1)].kind; }
  bool boss() const { return !stages_.empty() && stages_[static_cast<size_t>(stageIdx_ < stageCount() ? stageIdx_ : stageCount() - 1)].boss; }
  int stageTick() const { return stageTick_; }

  // Path layer.
  const PathLayout& path() const { return path_; }
  int pathX() const { return px_; }
  int pathY() const { return py_; }
  bool pathVisited(int x, int y) const { return pvis_.empty() ? false : pvis_[static_cast<size_t>(y * path_.w + x)] != 0; }
  int pathKeysTaken() const { return pkey_; }
  // Rhythm layer: status 0 pending, 1 hit, 2 missed.
  const RhythmLayout& rhythm() const { return rhythm_; }
  int rhythmStatus(size_t i) const { return i < rstat_.size() ? rstat_[i] : 0; }
  int rhythmWindow() const;                      // current +- window in ticks (smaller during the alarm)
  // Frequency layer.
  const FreqLayout& freq() const { return freq_; }
  int freqLocks() const { return fk_; }
  float hackerAngle() const { return fa_; }
  float iceAngle() const { return fc_; }
  float freqHalfWidth() const;                   // half-width of the window of the current lock (degrees)
  float freqOffset() const;                      // signed angle from the ICE window centre to the hacker marker, -180..180

  // Input a perfect player would give on this very tick (bots, tests, the calibration tool).
  HackInput PerfectInput() const;
  bool WantsConfirm() const { return PerfectInput().confirm; }
  // Cues raised since the last call (audio / animation).
  std::vector<HackSfx> DrainSfx();

  uint64_t Hash() const;

  // How hard the hatch is: the enemy archetype and difficulty set the base, a damaged shoulder makes it easier (1..10).
  static int DifficultyFor(Archetype arch, Difficulty diff, ZoneState shoulder);
  static int DefaultTimeLimit(int difficulty);
  static int DefaultPenalty(int difficulty);

  // ---- pure generators (the same ones the game uses; exported to data/hack/hack_levels.json) ----
  static std::vector<HackStageSpec> StagesFor(int difficulty);
  static PathLayout GeneratePath(int difficulty, uint64_t seed);
  static RhythmLayout GenerateRhythm(int difficulty, uint64_t seed, bool boss);
  static FreqLayout GenerateFreq(int difficulty, uint64_t seed, bool boss);
  static uint64_t StageSeed(uint64_t seed, int stage, int reroll);
  // Replays the reference solution of a layout through the real rules: true when it clears the stage.
  static bool PathSolvable(const PathLayout& p);
  // Minimal ticks a perfect player needs for a stage (path: one press per tick).
  static int PathMinTicks(const PathLayout& p) { return static_cast<int>(p.solution.size()); }
  static int RhythmMinTicks(const RhythmLayout& r) { return r.impulses.empty() ? 0 : r.impulses.back().tick + 1; }

 private:
  struct Move { std::vector<int> cells; int keyBefore; int8_t dx, dy; };

  void EnterStage(int idx, bool regenerate);
  void StepPath(const HackInput& in);
  void StepRhythm(const HackInput& in);
  void StepFreq(const HackInput& in);
  int PathMove(int dx, int dy);   // 0 ignored (off the grid), 1 mistake, 2 moved
  void PathUndo();
  void Mistake();
  void StageClear();
  void Sfx(HackSfx s) { sfx_.push_back(s); }
  float FreqSpeedMult() const;

  HackState state_ = HackState::Idle;
  HackConfig cfg_;
  int diff_ = 5;
  int limit_ = 0;
  int penalty_ = 0;
  int ticksLeft_ = 0;
  int mistakes_ = 0;
  int rerolls_ = 0;
  int trips_ = 0;
  float heat_ = 0.f;
  bool alarm_ = false;
  std::vector<HackStageSpec> stages_;
  int stageIdx_ = 0;
  int stageTick_ = 0;
  // path state
  PathLayout path_;
  std::vector<uint8_t> pvis_;
  std::vector<Move> pmoves_;
  int px_ = 0, py_ = 0, pkey_ = 0;
  // rhythm state
  RhythmLayout rhythm_;
  std::vector<uint8_t> rstat_;
  // frequency state
  FreqLayout freq_;
  int fk_ = 0;
  float fa_ = 0.f, fc_ = 0.f;
  std::vector<HackSfx> sfx_;
};

}  // namespace iv

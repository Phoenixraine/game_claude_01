// Hatch-hacking mini-game logic (STATUS §6B 4, TASK-017 interface / TASK-018 content).
//
// The game layer shows it full screen while the pilot is on the enemy shoulder. The core only owns the rules: the timer, the mistakes,
// the progress and the quality. Deterministic: same config + same inputs = same state. No exceptions, no clocks.
//
// NOTE: this is the minimal "signal sync" rule set that makes the boarding state machine testable (TASK-017). TASK-018 replaces the
// inside of HackGame with the three-layer game (path, rhythm, frequency) but keeps this public interface.
#pragma once

#include <cstdint>

#include "iv/Rng.h"
#include "iv/Tuning.h"
#include "iv/Types.h"

namespace iv {

enum class HackState : uint8_t { Idle, Running, Success, Fail, Timeout };

// One tick of player intent. Edge flags are true for one tick. Works on keyboard/mouse and on a pad (no pointer needed).
struct HackInput {
  int8_t dx = 0;          // -1 / +1: left / right (stick, arrows, A/D)
  int8_t dy = 0;          // -1 / +1: up / down
  bool confirm = false;   // edge: main action (stub: "lock the signal")
  bool back = false;      // edge: abort the hack (counts as a failure; the pilot returns along the grapple)
  bool aux = false;       // edge: second action (unused by the stub)
};

struct HackConfig {
  int difficulty = 5;               // 1..10
  uint64_t seed = 1;
  int timeLimitTicks = 0;           // 0 = the default of the difficulty (60 s at 1 .. 25 s at 10)
  int mistakePenaltyTicks = 0;      // 0 = default of the difficulty
};

class HackGame {
 public:
  HackGame() = default;
  void Start(const HackConfig& cfg);
  // Advances one 60 Hz tick. Ignored unless Running.
  void Step(const HackInput& in);

  // Starts a fresh layout (the pilot swung to the other shoulder): keeps `keep` (0..1) of the progress, re-rolls the rest.
  void Reroll(float keep);
  // Time lost outside the player's control (the mech was hit while the pilot hangs on the hatch).
  void AddPenalty(int ticks);

  HackState state() const { return state_; }
  bool running() const { return state_ == HackState::Running; }
  float progress() const { return N_ > 0 ? static_cast<float>(hits_) / static_cast<float>(N_) : 0.f; }
  int mistakes() const { return mistakes_; }
  int ticksLeft() const { return ticksLeft_; }
  int timeLimit() const { return limit_; }
  int difficulty() const { return diff_; }
  int rerolls() const { return rerolls_; }
  // 0..1, from the time left and the mistakes; 0 until the game is won.
  float quality() const;

  // Stub layout, for the screen and for bots: the marker sweeps the track, `confirm` inside the window locks one signal.
  float marker() const { return pos_; }
  float windowCenter() const { return wc_; }
  float windowHalfWidth() const { return ww_; }
  bool WantsConfirm() const;   // a perfect player would press now
  uint64_t Hash() const;

  // How hard the hatch is: the enemy archetype and difficulty set the base, a damaged shoulder makes it easier (1..10).
  static int DifficultyFor(Archetype arch, Difficulty diff, ZoneState shoulder);
  static int DefaultTimeLimit(int difficulty);
  static int DefaultPenalty(int difficulty);

 private:
  void NewWindow();

  HackState state_ = HackState::Idle;
  int diff_ = 5;
  int limit_ = 0;
  int penalty_ = 0;
  int ticksLeft_ = 0;
  int N_ = 1;
  int hits_ = 0;
  int mistakes_ = 0;
  int rerolls_ = 0;
  float pos_ = 0.f;
  float vel_ = 0.f;
  float wc_ = 0.5f;
  float ww_ = 0.1f;
  Rng rng_;
};

}  // namespace iv

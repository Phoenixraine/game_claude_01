// Players for the hack mini-game (calibration, boarding balance, tests). A bot sees exactly what the screen shows (HackGame accessors) and
// answers with a HackInput. Human-like bots have a reaction time (ticks at 60 Hz) and an error rate; the perfect bot is the solver.
#pragma once

#include <cstdint>
#include <vector>

#include "iv/HackGame.h"
#include "iv/Rng.h"

namespace iv {

struct HackBotProfile {
  const char* name;
  int reactionTicks;   // 0 = perfect
  float errorRate;     // chance of a wrong action per decision (a wrong step, a missed impulse, a skipped lock)
};

// TASK-018: perfect 0 ms / 0 %, good human 180 ms / 3 %, average 260 ms / 10 %, poor 350 ms / 25 %.
constexpr HackBotProfile kHackBots[4] = {{"perfect", 0, 0.f}, {"good", 11, 0.03f}, {"average", 16, 0.10f}, {"poor", 21, 0.25f}};

class HackBot {
 public:
  HackBot(const HackBotProfile& profile, uint64_t seed);
  // One tick: look at the game, give the input of this tick. Call once per game tick, before HackGame::Step.
  HackInput Next(const HackGame& g);

 private:
  struct Plan { int tick; int lane; bool skip; };
  void Replan(const HackGame& g);
  float Gauss();

  HackBotProfile prof_;
  Rng rng_;
  int stage_ = -1;
  int rerolls_ = -1;
  int lastStageTick_ = 0;
  int idle_ = 0;           // ticks left before the bot acts (reading the new stage, thinking)
  int gap_ = 0;            // ticks left until the next key press on the path
  std::vector<Plan> plan_;
  size_t planPos_ = 0;
  float aim_ = 0.f;        // frequency: the offset at which the next lock is pressed
  bool skipLock_ = false;
  float prevOff_ = 0.f;
  bool havePrev_ = false;
};

}  // namespace iv

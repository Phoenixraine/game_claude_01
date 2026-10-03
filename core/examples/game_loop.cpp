// The game loop from docs/CORE_API.md, runnable: a scripted "player" against an AI bot, 60 Hz fixed step.
// It is built and run by CTest so the documented example can never drift away from the API.
#include <cstdio>

#include "iv/Ai.h"

using namespace iv;

namespace {

Duel duel(/*seed*/ 42);                                   // player = Side::A, bot = Side::B
Ai bot(Archetype::Counterpuncher, Difficulty::Normal, /*seed*/ 7);
int eventsSeen = 0;

void Dispatch(const Event&) { ++eventsSeen; }             // the game turns events into sound / VFX / camera shake

// Stand-in for the gamepad: hold RT on an upper-right swing, release it, repeat; walk toward the bot.
Input ReadPlayer(int tick) {
  Input in;
  in.move = 1;
  const int cycle = tick % 150;
  if (cycle < 30) {
    in.strikeHeld = true;
    in.side = SwingSide::Up;
    in.target = Zone::Torso;
    in.footwork = Footwork::StepIn;
  }
  return in;
}

void FixedTick60Hz(const Input& playerInput, const World& world) {  // call exactly 60 times per second
  const Input botInput = bot.Decide(MakeObservation(duel, Side::B));  // the bot only sees an Observation
  duel.Step(playerInput, botInput, world);
  for (const Event& e : duel.log().events()) Dispatch(e);
  duel.log().Clear();
}

}  // namespace

int main() {
  duel.set_time_limit(10 * 60 * kTickHz);
  World world;
  for (int t = 0; !duel.result().over; ++t) FixedTick60Hz(ReadPlayer(t), world);
  const MatchResult& r = duel.result();
  std::printf("match over after %.1f s of game time: %s (%s), %d events dispatched\n", duel.tick() / static_cast<double>(kTickHz), Name(r.reason),
              r.draw ? "draw" : (r.loser == Side::A ? "bot wins" : "player wins"), eventsSeen);
  return r.over && eventsSeen > 0 ? 0 : 1;
}

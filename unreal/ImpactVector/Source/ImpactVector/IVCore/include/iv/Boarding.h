// Boarding (STATUS §6B, TASK-017): one button, the pilot leaves the cockpit, hooks onto the enemy shoulder, hacks the hatch next to the
// shoulder/arm joint, drops a grenade and flies back. The core owns rules and timings only; Unreal plays the animations from the events.
//
// Game loop (see docs/CORE_API.md, section "Абордаж"):
//   Input a = boarding.Filter(duel, playerInput);     // BEFORE Duel::Step: the autopilot drives the owner's mech while the pilot is outside
//   duel.Step(a, b, world);
//   boarding.Step(duel, boardingInput);               // AFTER Duel::Step: an external observer, never changes the fight except the blast
// The API is symmetric: `owner` may be Side::A or Side::B. The AI is not allowed to board yet (tune::kAiBoardingEnabled).
#pragma once

#include <cstdint>

#include "iv/Ai.h"
#include "iv/Duel.h"
#include "iv/HackGame.h"
#include "iv/Rng.h"
#include "iv/Types.h"

namespace iv {

// Order of the values up to HookSwing is a contract with the animation layer; new values go at the end.
enum class BoardPhase : uint8_t { Idle, ClimbOut, OnShoulder, HookLaunch, HookFlight, Landing, Hacking, GrenadeThrow, Escape, WatchBlast, ReturnHook, ClimbIn, Smashed, Done, HookSwing };

enum class BoardingDenied : uint8_t { None, AlreadyActive, MatchOver, Clinch, Busy, Stunned, Cinematic, Cooldown, NoEnergy, NoStability, NoTarget, AiDisabled };

enum class BoardingOutcome : uint8_t { None, Success, HackFailed, HackTimeout, Smashed, Aborted };

struct BoardingInput {
  bool start = false;          // edge: the boarding button
  bool swing = false;          // edge: leap to the other shoulder (only works inside the window after a swat telegraph)
  Arm shoulder = Arm::R;       // preferred hatch side at the start (the other one is used if this shoulder is destroyed)
  HackInput hack;              // forwarded to the mini-game while Hacking
};

struct BoardingConfig {
  Side owner = Side::A;
  bool ownerIsAi = false;                              // an AI owner is refused while tune::kAiBoardingEnabled is false
  Archetype enemyArchetype = Archetype::Counterpuncher; // sets the hack difficulty and how often the enemy hand swats
  Difficulty enemyDifficulty = Difficulty::Normal;      // also the length of the swat telegraph
  uint64_t seed = 1;
  float swatChanceMult = 1.f;                           // scales the enemy hand's chance (0 = never swats): difficulty option and test hook
};

class Boarding {
 public:
  explicit Boarding(const BoardingConfig& cfg = BoardingConfig());
  void Reset(uint64_t seed);

  // Call before Duel::Step. While the pilot is outside, the result is the owner's defensive autopilot (block / dodge / guard, never an attack);
  // otherwise `playerInput` is returned unchanged.
  Input Filter(const Duel& duel, const Input& playerInput);
  // Call after Duel::Step, once per tick. Frozen while a cinematic cut plays.
  void Step(Duel& duel, const BoardingInput& in);

  BoardPhase phase() const { return phase_; }
  // True while the pilot is outside (Smashed ends the match and is not "active").
  bool Active() const { return phase_ != BoardPhase::Idle && phase_ != BoardPhase::Done && phase_ != BoardPhase::Smashed; }
  int phaseTicks() const { return phaseTick_; }
  int phaseLength() const { return phaseLen_; }
  Arm shoulder() const { return shoulder_; }                // the shoulder the pilot is on / heads to
  int cooldownLeft() const { return cooldown_; }
  BoardingDenied lastDenied() const { return lastDenied_; }
  BoardingOutcome outcome() const { return outcome_; }
  const HackGame& hack() const { return hack_; }
  bool swatActive() const { return swat_.active; }
  int swatTicksToImpact() const { return swat_.ticksToImpact; }
  Arm swatShoulder() const { return swat_.shoulder; }
  int swatsThisBoarding() const { return swatsDone_; }
  const BoardingConfig& config() const { return cfg_; }
  void set_swat_chance_mult(float m) { cfg_.swatChanceMult = m; }
  uint64_t Hash() const;

  // Zone of the enemy that gets the grenade: the shoulder, or the arm if the shoulder is already gone.
  static Zone BlastZone(const Duel& duel, Side enemy, Arm shoulder);
  static float GrenadeDamage(float quality);

 private:
  struct Swat {
    bool active = false;
    Arm shoulder = Arm::R;
    int total = 0;
    int ticksToImpact = 0;
    int adjusted = 0;
  };

  void Emit(Duel& d, EventType t, int a = 0, int b = 0, float v = 0.f, Zone z = Zone::Torso);
  void Enter(Duel& d, BoardPhase p, int len);
  BoardingDenied CanStart(const Duel& d, const BoardingInput& in, Arm* chosen) const;
  void Begin(Duel& d, Arm shoulder);
  void Finish(Duel& d, BoardingOutcome o);
  void ForcedSwing(Duel& d);
  void AbortToReturn(Duel& d, HackState why);
  void Smash(Duel& d);
  void StepSwat(Duel& d, const BoardingInput& in);
  void DoSwing(Duel& d, bool early);
  void BeginHack(Duel& d);
  void StepHack(Duel& d, const BoardingInput& in);
  void CheckShoulder(Duel& d);
  bool SwatEligible() const;
  bool UsableShoulder(const Duel& d, Arm a) const;

  BoardingConfig cfg_;
  Rng rng_;
  Ai auto_;
  BoardPhase phase_ = BoardPhase::Idle;
  int phaseTick_ = 0;
  int phaseLen_ = 0;
  Arm shoulder_ = Arm::R;
  int cooldown_ = 0;
  BoardingDenied lastDenied_ = BoardingDenied::None;
  BoardingOutcome outcome_ = BoardingOutcome::None;
  HackGame hack_;
  Swat swat_;
  int swatsDone_ = 0;
  int swatCooldown_ = 0;
  int swatCheck_ = 0;
  int sinceLanding_ = 0;
  int shocks_ = 0;
  Tick lastHit_ = -100000;
  float lastProgressSent_ = 0.f;
  float quality_ = 0.f;
  bool blastDone_ = false;
  BoardPhase resume_ = BoardPhase::Landing;   // where a finished swing goes on
  int ghostTicks_ = -1;                       // the swat that was dodged still lands on the empty shoulder (for the animation)
  Arm ghostShoulder_ = Arm::R;
};

const char* Name(BoardPhase p);
const char* Name(BoardingDenied d);

}  // namespace iv

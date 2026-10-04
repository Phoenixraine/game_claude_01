// Module 5: opponent AI (pitch §20, §8).
//
// The AI is fed ONLY an `Observation`: what a human pilot could see, hear and feel. It never
// receives the opponent's `Input`, the target zone of a swing that has not landed, the opponent's
// stability / heat / energy numbers or the held duration of a windup. Difficulty changes reaction
// delay, habit-reading depth and positioning, never damage (pitch §20).
#pragma once

#include <cstdint>
#include <vector>

#include "iv/Duel.h"
#include "iv/Rng.h"
#include "iv/Types.h"

namespace iv {

// Own cockpit instruments and bodily feel.
struct SelfView {
  Posture posture = Posture::Standing;
  Phase phase = Phase::Idle;
  float stability = 0.f;
  float heat = 0.f;
  float energy = 0.f;
  ZoneState zones[kZoneCount] = {};
  ArmPose pose[2] = {ArmPose::Neutral, ArmPose::Neutral};
  EnergyPriority priority = EnergyPriority::Guard;
  bool guardHeld = false;
  int guardAge = 0;
  bool hardStance = false;
  int counterTicks = 0;        // open counter window after a parry
  int strikeTicksLeft = -1;    // own strike in flight (-1 otherwise)
  bool weaponCharging = false;
  float weaponChargeFrac = 0.f;
  bool weaponReady = true;      // v2: cooldown over and ammo left
  bool ultimateReady = false;   // v2: the gauge is full
  Outcome lastOwnOutcome = Outcome::Whiff;
  Zone lastOwnTarget = Zone::Torso;
  int sinceOwn = 100000;       // ticks since own last strike landed / missed
  Outcome lastIncomingOutcome = Outcome::Whiff;
  Zone lastIncomingZone = Zone::Torso;
  int sinceIncoming = 100000;
  float flank = 0.f;
  float proximity = 0.f;
  bool armUsable[2] = {true, true};
  uint8_t allowedSides[2] = {0b1111, 0b1111};  // own arms: which swing families still work
  bool canGrab = true;
  bool windupReady = false;    // own heavy windup has reached its minimum length
  bool blinded = false;        // v3: rockets / debris in the sensors: the opponent's swing sector cannot be read
  bool strikeLocked = false;   // v3: arm actuators jammed
};

// What can be seen or heard of the opponent. Deliberately has no target zone, no windup duration,
// no stability / heat / energy numbers and no input state.
struct OppView {
  Posture posture = Posture::Standing;
  Phase phase = Phase::Idle;
  StrikeKind kind = StrikeKind::Heavy;  // valid while winding up or striking
  SwingSide side = SwingSide::Up;       // the visible swing sector (pitch §8 "физические признаки")
  Arm arm = Arm::R;
  bool chargeSound = false;             // pitch §8 "звук набирающего давление привода"
  int strikeTicksLeft = -1;             // visible arm travel: only once the strike is committed
  bool stepping = false;                // committed with a step in
  ArmPose pose[2] = {ArmPose::Neutral, ArmPose::Neutral};
  EnergyPriority priority = EnergyPriority::Guard;  // glowing power lines (pitch §8 "Энергетические признаки")
  bool switching = false;               // energy flow in progress (visible)
  EnergyPriority pendingPriority = EnergyPriority::Guard;
  ZoneState zones[kZoneCount] = {};     // visible damage
  bool guardUp = false;
  SwingSide guardSide = SwingSide::Up;
  bool hardStance = false;
  bool weaponCharging = false;          // open shoulder + charge tone (pitch §13)
  bool unsteady = false;                // visibly swaying
  bool heatWarning = false;             // steam / glow
  int8_t move = 0;                      // walking toward (+1) / away (-1)
  float flank = 0.f;                    // how far the opponent's front is turned off this mech
};

struct Observation {
  Tick tick = 0;
  float distance = 0.f;
  SelfView self;
  OppView opp;
  bool chainOpen = false;   // a reverse window is open (visible clash)
  bool chainMine = false;
};

// Builds what `viewer` can perceive right now. This is the only bridge from simulation state to the AI.
Observation MakeObservation(const Duel& duel, Side viewer);
uint64_t HashObservation(const Observation& o);

// Habit memory (pitch §8 "Поведенческое чтение"): what the opponent tends to do after a given event.
enum class HabitContext : uint8_t { AfterBlocked, AfterMissed, AfterLegHit, WhenUnsteady, Count };
enum class HabitResponse : uint8_t { Retreat, Advance, Hold, QuickStrike, HeavyStrike, Guard, HardStance, Count };
constexpr int kHabitContexts = static_cast<int>(HabitContext::Count);
constexpr int kHabitResponses = static_cast<int>(HabitResponse::Count);

struct HabitMemory {
  int resp[kHabitContexts][kHabitResponses] = {};
  int total[kHabitContexts] = {};
  int combo[4][4] = {};  // swing side that followed a previous swing side
  int comboTotal[4] = {};

  // Most likely response in a context and its share; `count` guards against tiny samples.
  HabitResponse Likely(HabitContext c, float* share) const;
};

class Ai {
 public:
  Ai(Archetype archetype, Difficulty difficulty, uint64_t seed);

  // One tick of decision making. `current` carries own state up to date; opponent information is
  // read from the observation `reactionDelay()` ticks ago (pitch §20: never faster than ~200 ms).
  Input Decide(const Observation& current);

  int reactionDelay() const { return delay_; }
  Archetype archetype() const { return archetype_; }
  Difficulty difficulty() const { return difficulty_; }
  const HabitMemory& memory() const { return memory_; }

 private:
  struct Script {
    bool active = false;
    int holdLeft = 0;
    SwingSide side = SwingSide::Up;
    Zone target = Zone::Torso;
    Arm arm = Arm::R;
    Footwork foot = Footwork::Hold;
    bool feintDone = false;
    int tick = 0;
  };
  enum class Reaction : uint8_t { None, Block, Parry, Dodge, Intercept, HardStance };

  void UpdateMemory(const Observation& cur, const Observation& old);
  void ChooseReaction(const OppView& seen, const SelfView& self);
  bool Defend(const OppView& seen, const Observation& cur, Input* in);
  void Offend(const Observation& cur, const OppView& seen, Input* in);
  Zone PickTarget(const OppView& seen, const SelfView& self);
  void PickStrike(const Observation& cur, const OppView& seen);
  SwingSide PredictOppSide();
  float Roll() { return rng_.Unit(); }

  Archetype archetype_;
  Difficulty difficulty_;
  Rng rng_;
  int delay_;
  std::vector<Observation> history_;
  HabitMemory memory_;

  // opponent-attack tracking (from the delayed view)
  bool oppAttacking_ = false;
  Reaction reaction_ = Reaction::None;
  SwingSide lastOppSide_ = SwingSide::Up;
  Tick lastOppSideTick_ = -100000;
  int parryJitter_ = 0;
  bool parryPressed_ = false;
  bool grabAnswer_ = false;     // decided to hit a grabbing arm
  bool grabAnswered_ = false;
  bool reacted_ = false;       // dodge / intercept already fired for this attack
  int priorityCooldown_ = 0;

  // habit watch
  bool watching_ = false;
  HabitContext watchCtx_ = HabitContext::AfterBlocked;
  Tick watchStart_ = 0;
  Tick lastOwnSeen_ = -100000;
  bool prevUnsteady_ = false;

  Script script_;
  int cooldown_ = 0;
  int chase_ = 0;           // follow-up window after predicting a retreat
  SwingSide guardSide_ = SwingSide::Up;
  int guardRethink_ = 0;
  bool guardIdle_ = false;
  int reverseUntil_ = -1;
  int reverseFrom_ = -1;
  bool weaponSeen_ = false;     // the opponent is charging its launcher (visible shoulder + tone)
  Tick weaponSeenTick_ = 0;
  bool rushing_ = false;
  bool weaponDodged_ = false;
  int weaponJitter_ = 0;
  int moving_ = 0;          // -1 opening, 0 holding, +1 closing (hysteresis state)
  // v5
  bool lungeJump_ = false;      // decided to jump over the incoming lunge
  bool jumpPressed_ = false;
  bool chopSlide_ = false;      // decided to slide under the incoming aerial chop
  bool chopSlid_ = false;
  int lungeLeft_ = 0;           // ticks of charge still to hold
};

}  // namespace iv

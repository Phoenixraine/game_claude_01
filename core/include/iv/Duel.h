// Module 3 and 4 (two-fighter half): contact resolution, defence outcomes, reverse chain, clinch,
// match end (pitch §5-§7, §14). Duel owns two Fighters, the gap between them and the event log.
#pragma once

#include "iv/Dummy.h"
#include "iv/Events.h"
#include "iv/Fighter.h"
#include "iv/Rng.h"
#include "iv/Types.h"

namespace iv {

// World data supplied by the game layer each tick (obstacles, water). Defaults describe an empty arena.
struct World {
  float proximity[2] = {0.f, 0.f};     // pitch §7: how close a wall / building is behind each fighter, 0..1
  float coolingMult[2] = {1.f, 1.f};   // pitch §10: rain / water raise cooling
};

// pitch §7: counter-on-counter chain. `who` may answer within `windowLeft` ticks.
struct Chain {
  bool active = false;
  Side who = Side::A;
  int depth = 0;       // replies made so far (max tune::kMaxReverseReplies)
  int windowLeft = 0;
};

struct ClinchState {
  bool active = false;
  int ticks = 0;
};

// v2: a scripted external camera cut (weapon with a long cooldown, or the ultimate). The fight is frozen while it plays.
struct CinematicState {
  bool active = false;
  CinematicKind kind = CinematicKind::None;
  Side who = Side::A;        // the fighter that triggered it
  int ticks = 0;             // elapsed
  int length = 0;
  bool stunTarget = false;   // the opponent is staggered when the cut ends
};

struct MatchResult {
  bool over = false;
  bool draw = false;
  Side loser = Side::A;
  EndReason reason = EndReason::None;
};

// v5: the blades locked after a blocked lunge: both sides mash the button, the leader strikes the other.
struct LockState {
  bool active = false;
  Side attacker = Side::A;   // the one who rushed
  int kind = 0;              // 0 plain block, 1 parry, 2 hard stance
  int ticks = 0;
  float score[2] = {0.f, 0.f};
};

// v5: berserk: the attacker holds the foe; each blow needs a timing press, the foe must parry every one.
enum class BerserkStage : uint8_t { Prompt, Swing };
struct BerserkState {
  bool active = false;
  Side who = Side::A;
  BerserkStage stage = BerserkStage::Prompt;
  int round = 0;
  int ticks = 0;
  int stageTicks = 0;
  SwingSide side = SwingSide::Up;
  float quality = 0.f;
  Tick swingStart = 0;
};

class Duel {
 public:
  explicit Duel(uint64_t seed = 1, bool keepEvents = true);
  void Reset(uint64_t seed);

  // Advances the world by one 60 Hz tick. Does nothing once the match is over.
  void Step(const Input& a, const Input& b, const World& world = World());

  Fighter& fighter(Side s) { return f_[Index(s)]; }
  const Fighter& fighter(Side s) const { return f_[Index(s)]; }
  float distance() const { return distance_; }
  void set_distance(float d) { distance_ = d; }
  Tick tick() const { return tick_; }
  const MatchResult& result() const { return result_; }
  const Chain& chain() const { return chain_; }
  const ClinchState& clinch() const { return clinch_; }
  const CinematicState& cinematic() const { return cinematic_; }
  // v2 loadout and training dummy.
  void SetLoadout(Side s, WeaponKind k) { f_[Index(s)].SetLoadout(k); }
  bool SelectWeapon(Side s, WeaponKind k) { return f_[Index(s)].SelectWeapon(k); }
  void SetDummy(Side s, DummyMode m) { dummy_[Index(s)].Set(m); }
  // v3: damage that comes from the world (thrown debris, a crash into a building, a fall). `source`: 0 debris, 1 crash, 2 fall.
  HitReport ExternalHit(Side victim, Zone zone, float damage, float stability, int source, StatusKind status = StatusKind::Count, int statusTicks = 0);
  Dummy& dummy(Side s) { return dummy_[Index(s)]; }
  // v4: ends the match from outside (boarding: the pilot was crushed). No-op once the match is over.
  void ForceEnd(Side loser, EndReason reason);
  EventLog& log() { return log_; }
  const EventLog& log() const { return log_; }
  // v5. aiLevel: -1 = a human (all presses come from the Input), 0..2 = Duel plays the lock mashing, the berserk parries and the repairs by itself.
  void SetAiLevel(Side s, int aiLevel) { aiLevel_[Index(s)] = aiLevel; }
  int ai_level(Side s) const { return aiLevel_[Index(s)]; }
  const LockState& lock() const { return lock_; }
  const BerserkState& berserk() const { return berserk_; }
  void RepairBreakdown(Side s, int levels);
  // Headless sims: end the match as a draw after this many ticks (0 = no limit).
  void set_time_limit(int ticks) { timeLimit_ = ticks; }

 private:
  struct Decision {
    Outcome outcome = Outcome::Whiff;
    Zone zone = Zone::Torso;
    float raw = 0.f;
    int lockKind = 0;
  };

  StepContext Ctx(int i, const World& w) const;
  Decision Decide(int atk) const;
  void Apply(int atk, const Decision& d, const World& w);
  void ApplyClash(int first, const World& w);
  void ResolveWeapon(int atk, const World& w);
  void StepChain(const Input* const* in, const World& w);
  void TryReply(int who, const Input& in, const World& w);
  void StartClinch();
  void ResolveClinch(const World& w);
  void CheckEnd();
  void StartCinematic(CinematicKind k, Side who, int length, bool stun);
  void StepCinematic();
  void ResolveUltimate(int ai, const World& w);
  // v5 (Special.cpp)
  void StartLock(int atk, int kind);
  void StepLock(const Input* const* in);
  void ResolveLock();
  bool TryStartBerserk(int who);
  void StepBerserk(const Input* const* in);
  void EndBerserk(bool overload, int reason);
  void BerserkPrompt();
  void EmitHit(const Fighter& def, Side attacker, Zone zone, const HitReport& r, float stability, SwingSide dir, bool blocked, bool parried);
  void GainUltimate(int who, float amount, const World& w);
  void Emit(EventType t, Side actor, Zone z = Zone::Torso, int a = 0, int b = 0, float v = 0.f);

  Fighter f_[2];
  float distance_ = tune::kStartDistance;
  Tick tick_ = 0;
  Chain chain_;
  ClinchState clinch_;
  CinematicState cinematic_;
  Dummy dummy_[2];
  MatchResult result_;
  EventLog log_;
  Rng rng_;
  int timeLimit_ = 0;
  int aiLevel_[2] = {-1, -1};
  LockState lock_;
  BerserkState berserk_;
  bool gpHeld_[2] = {false, false};
  SwingSide gpSide_[2] = {SwingSide::Up, SwingSide::Up};
  Tick gpTick_[2] = {-100000, -100000};
};

}  // namespace iv

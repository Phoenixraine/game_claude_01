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
  void SetDummy(Side s, DummyMode m) { dummy_[Index(s)].Set(m); }
  Dummy& dummy(Side s) { return dummy_[Index(s)]; }
  EventLog& log() { return log_; }
  const EventLog& log() const { return log_; }
  // Headless sims: end the match as a draw after this many ticks (0 = no limit).
  void set_time_limit(int ticks) { timeLimit_ = ticks; }

 private:
  struct Decision {
    Outcome outcome = Outcome::Whiff;
    Zone zone = Zone::Torso;
    float raw = 0.f;
  };

  StepContext Ctx(int i, const World& w) const;
  Decision Decide(int atk) const;
  void Apply(int atk, const Decision& d, const World& w);
  void ResolveWeapon(int atk, const World& w);
  void StepChain(const Input* const* in, const World& w);
  void TryReply(int who, const Input& in, const World& w);
  void StartClinch();
  void ResolveClinch(const World& w);
  void CheckEnd();
  void StartCinematic(CinematicKind k, Side who, int length, bool stun);
  void StepCinematic();
  void ResolveUltimate(int ai, const World& w);
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
};

}  // namespace iv

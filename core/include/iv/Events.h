// Event stream: the core's only output besides the polled state. Events are plain structs so the
// Unreal layer can turn each one into a sound, a VFX, a cockpit shake or a UI warning.
#pragma once

#include <cmath>
#include <cstdint>
#include <vector>

#include "iv/Types.h"

namespace iv {

enum class EventType : uint8_t {
  WindupStarted,     // a: StrikeKind, b: SwingSide
  Committed,         // strike passed the commit point
  CancelCheap,       // B before the commit point
  EmergencyBrake,    // B after the commit point
  Feint,             // a: feint count so far
  Interrupted,       // a windup/strike was broken by a hit (pitch §5.3)
  StrikeContact,     // a: StrikeKind, b: Outcome
  Hit,               // zone: zone hit, value: damage dealt
  Blocked,           // value: damage after block
  ParrySuccess,      // actor: the defender who parried
  InterceptSuccess,  // actor: the interceptor
  Evaded,
  Whiff,
  Dodge,             // a: direction
  ZoneState,         // zone, a: new ZoneState, b: previous ZoneState
  LimbSevered,       // zone
  StaggerBegin,
  StaggerEnd,
  Knockdown,
  GotUp,
  HeatWarning,
  CoolantLeak,
  Shutdown,
  EnergyFlow,        // a: EnergyPriority being switched to (visible to the opponent)
  EnergyShift,       // a: EnergyPriority now active (to), b: the previous one (from)
  ReverseChain,      // a: step = reply depth (1 or 2)
  ReverseFailed,
  Clinch,            // clinch begins
  ClinchResolved,    // actor: winner, value: score margin
  WallSlam,          // value: damage
  HardStanceOn,
  HardStanceOff,
  GrabHit,
  WeaponCharging,
  WeaponFired,       // a: 1 if hit
  WeaponInterrupted,
  PoseReturn,        // a: ArmPose being returned from
  // ---- v2: presentation events (the Unreal layer turns each into animation / sound / VFX / cockpit damage) ----
  HitEvent,          // actor: attacker, zone, a: Layer reached, b: ZoneState after, c: flags (see HitInfo), value: damage, value2: stability damage
  ArmorPlateLost,    // zone, a: plate index (0-based), b: plates in the zone
  ReactorBreach,     // the Reactor zone was breached (state >= Damaged for the first time) - blue glow / coolant on the cockpit
  SystemFailure,     // a: SystemId that failed
  UltimateReady,     // actor: the gauge just became full
  UltimateUsed,
  CinematicBegin,    // actor: who triggered it, a: CinematicKind, b: duration in ticks
  CinematicEnd,
  WeaponReady,       // a: WeaponKind: the cooldown is over
  WeaponEmpty,       // a: WeaponKind: no ammo left
  MatchEnd,          // a: EndReason, actor: the fighter that lost (or Side::A on a draw with b == 1)
};

struct Event {
  Tick tick = 0;
  EventType type = EventType::WindupStarted;
  Side actor = Side::A;
  Zone zone = Zone::Torso;
  int32_t a = 0;
  int32_t b = 0;
  float value = 0.0f;
  int32_t c = 0;        // v2: extra payload (HitEvent flags)
  float value2 = 0.0f;  // v2: extra payload (HitEvent stability damage)
};

// Flags packed in Event::c of a HitEvent.
struct HitInfo {
  Side attacker = Side::A;
  Zone zone = Zone::Torso;
  Layer layer = Layer::Armor;     // deepest layer the hit reached
  ZoneState severity = ZoneState::Intact;
  SwingSide direction = SwingSide::Up;
  float damage = 0.f;
  float stabilityDamage = 0.f;
  bool wasBlocked = false;
  bool wasParried = false;
};
constexpr int32_t PackHitFlags(SwingSide dir, bool blocked, bool parried) {
  return static_cast<int32_t>(dir) | (blocked ? 4 : 0) | (parried ? 8 : 0);
}

// Decodes a HitEvent (returns false for any other event type).
inline bool DecodeHit(const Event& e, HitInfo* out) {
  if (e.type != EventType::HitEvent) return false;
  out->attacker = e.actor;
  out->zone = e.zone;
  out->layer = static_cast<Layer>(e.a);
  out->severity = static_cast<ZoneState>(e.b);
  out->direction = static_cast<SwingSide>(e.c & 3);
  out->wasBlocked = (e.c & 4) != 0;
  out->wasParried = (e.c & 8) != 0;
  out->damage = e.value;
  out->stabilityDamage = e.value2;
  return true;
}

// Collects events and folds every one of them into a running FNV-1a hash. The hash is what the
// determinism test compares, so recording the full list can be switched off for long headless runs.
class EventLog {
 public:
  explicit EventLog(bool keep = true) : keep_(keep) {}

  void Push(const Event& e) {
    Mix(static_cast<uint64_t>(static_cast<uint32_t>(e.tick)));
    Mix(static_cast<uint64_t>(e.type));
    Mix(static_cast<uint64_t>(e.actor));
    Mix(static_cast<uint64_t>(e.zone));
    Mix(static_cast<uint64_t>(static_cast<uint32_t>(e.a)));
    Mix(static_cast<uint64_t>(static_cast<uint32_t>(e.b)));
    Mix(static_cast<uint64_t>(static_cast<int64_t>(std::llround(static_cast<double>(e.value) * 1000.0))));
    Mix(static_cast<uint64_t>(static_cast<uint32_t>(e.c)));
    Mix(static_cast<uint64_t>(static_cast<int64_t>(std::llround(static_cast<double>(e.value2) * 1000.0))));
    ++count_;
    if (keep_) events_.push_back(e);
  }

  void Clear() {
    events_.clear();
    hash_ = kOffset;
    count_ = 0;
  }

  const std::vector<Event>& events() const { return events_; }
  uint64_t hash() const { return hash_; }
  uint64_t count() const { return count_; }

  // Number of kept events of a given type (test helper).
  int CountOf(EventType t) const {
    int n = 0;
    for (const Event& e : events_)
      if (e.type == t) ++n;
    return n;
  }

 private:
  static constexpr uint64_t kOffset = 1469598103934665603ULL;
  void Mix(uint64_t v) {
    for (int i = 0; i < 8; ++i) {
      hash_ ^= (v >> (i * 8)) & 0xffu;
      hash_ *= 1099511628211ULL;
    }
  }

  bool keep_;
  std::vector<Event> events_;
  uint64_t hash_ = kOffset;
  uint64_t count_ = 0;
};

}  // namespace iv

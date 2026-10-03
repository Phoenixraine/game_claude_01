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
  Parried,
  Intercepted,       // actor: the interceptor
  Evaded,
  Whiff,
  Dodge,             // a: direction
  ZoneState,         // zone, a: new ZoneState, b: previous ZoneState
  LimbSevered,       // zone
  Staggered,
  KnockedDown,
  GotUp,
  HeatWarning,
  CoolantLeak,
  Shutdown,
  EnergyFlow,        // a: EnergyPriority being switched to (visible to the opponent)
  EnergySwitched,    // a: EnergyPriority now active
  ReverseReply,      // a: reply depth (1 or 2)
  ReverseFailed,
  ClinchStart,
  ClinchResolved,    // actor: winner, value: score margin
  WallSlam,          // value: damage
  HardStanceOn,
  HardStanceOff,
  GrabHit,
  WeaponCharging,
  WeaponFired,       // a: 1 if hit
  WeaponInterrupted,
  PoseReturn,        // a: ArmPose being returned from
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
};

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

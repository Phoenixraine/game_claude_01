// Scenario helpers shared by the module tests: a two-fighter rig with auto-cleared edge inputs.
#pragma once

#include "TestFramework.h"
#include "iv/Duel.h"

namespace ivtest {

using namespace iv;

inline void ClearEdges(Input& in) {
  in.quick = in.cancel = in.toGrab = in.switchArm = in.reverse = in.dodge = in.setPriority = false;
}

struct Rig {
  Duel duel;
  Input a, b;
  World world;

  explicit Rig(uint64_t seed = 1, float distance = 20.f) : duel(seed, true) { duel.set_distance(distance); }

  Fighter& A() { return duel.fighter(Side::A); }
  Fighter& B() { return duel.fighter(Side::B); }

  void Step(int n = 1) {
    for (int i = 0; i < n; ++i) {
      duel.Step(a, b, world);
      ClearEdges(a);
      ClearEdges(b);
    }
  }

  template <class Pred>
  int StepUntil(Pred pred, int maxTicks = 2000) {
    for (int i = 0; i < maxTicks; ++i) {
      if (pred()) return i;
      Step();
    }
    return pred() ? maxTicks : -1;
  }

  int Count(EventType t) const { return duel.log().CountOf(t); }

  // Last StrikeContact outcome logged for `actor` (-1 if none).
  int LastOutcome(Side actor) const {
    int out = -1;
    for (const Event& e : duel.log().events())
      if (e.type == EventType::StrikeContact && e.actor == actor) out = e.b;
    return out;
  }

  // A holds RT on (side, target) long enough, then releases and waits until the strike is in flight.
  void StartHeavyA(SwingSide side, Zone target, int hold = tune::kWindupMinTicks, Arm arm = Arm::R) {
    a.strikeHeld = true;
    a.side = side;
    a.target = target;
    a.arm = arm;
    Step(hold);
    a.strikeHeld = false;
    StepUntil([&] { return A().phase == Phase::Strike; });
  }
};

inline float TotalHp(const Fighter& f) {
  float t = 0.f;
  for (int z = 0; z < kZoneCount; ++z)
    for (int l = 0; l < kLayerCount; ++l) t += f.body.layer(static_cast<Zone>(z), static_cast<Layer>(l));
  return t;
}

}  // namespace ivtest

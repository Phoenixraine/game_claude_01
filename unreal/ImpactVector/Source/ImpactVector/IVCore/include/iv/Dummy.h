// v2: training dummy controller (tutorial, TASK-006 update). It produces an Input like a player or the AI would, but follows
// a fixed behaviour: stand still, play a fixed attack script, or only raise a block against what it can see.
#pragma once

#include <vector>

#include "iv/Fighter.h"
#include "iv/Types.h"

namespace iv {

struct DummyStepDef {
  int waitTicks = 0;                       // pause before this attack starts
  StrikeKind kind = StrikeKind::Heavy;     // Heavy or Quick
  SwingSide side = SwingSide::Up;
  Arm arm = Arm::R;
  int holdTicks = 20;                      // heavy windup length before the release
};

class Dummy {
 public:
  void Set(DummyMode m);
  DummyMode mode() const { return mode_; }
  void SetScript(const std::vector<DummyStepDef>& s);
  const std::vector<DummyStepDef>& script() const { return script_; }
  void Reset();

  // One tick of intent. `self` and `opp` are only used for what a human could see (phase, visible swing side).
  Input Next(const Fighter& self, const Fighter& opp, Tick now);

 private:
  void DefaultScript();

  DummyMode mode_ = DummyMode::Off;
  std::vector<DummyStepDef> script_;
  size_t index_ = 0;
  int timer_ = 0;
  int holdLeft_ = 0;
  bool attacking_ = false;
  int seenFor_ = 0;
  SwingSide seenSide_ = SwingSide::Up;
};

}  // namespace iv

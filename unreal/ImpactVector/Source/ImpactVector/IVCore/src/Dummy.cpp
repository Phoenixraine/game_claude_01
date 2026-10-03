#include "iv/Dummy.h"

namespace iv {

void Dummy::DefaultScript() {
  script_.clear();
  const int gap = tune::kDummyScriptGapTicks;
  script_.push_back({gap, StrikeKind::Heavy, SwingSide::Up, Arm::R, tune::kWindupMinTicks + 6});
  script_.push_back({gap, StrikeKind::Heavy, SwingSide::Right, Arm::R, tune::kWindupMinTicks + 6});
  script_.push_back({gap, StrikeKind::Quick, SwingSide::Up, Arm::L, 0});
  script_.push_back({gap, StrikeKind::Heavy, SwingSide::Left, Arm::L, tune::kWindupMinTicks + 6});
  script_.push_back({gap, StrikeKind::Heavy, SwingSide::Down, Arm::R, tune::kWindupMinTicks + 6});
}

void Dummy::Set(DummyMode m) {
  mode_ = m;
  Reset();
  if (m == DummyMode::Scripted && script_.empty()) DefaultScript();
}

void Dummy::SetScript(const std::vector<DummyStepDef>& s) {
  script_ = s;
  Reset();
}

void Dummy::Reset() {
  index_ = 0;
  timer_ = 0;
  holdLeft_ = 0;
  attacking_ = false;
  seenFor_ = 0;
  seenSide_ = SwingSide::Up;
}

Input Dummy::Next(const Fighter& self, const Fighter& opp, Tick) {
  Input in;
  switch (mode_) {
    case DummyMode::Off:
    case DummyMode::Passive: break;
    case DummyMode::BlockOnly: {
      // Reacts only to what is visible: a heavy windup or strike on a given sector, after a human-like delay.
      const bool threat = (opp.phase == Phase::Windup || opp.phase == Phase::Strike) && opp.strike.kind != StrikeKind::Grab;
      if (threat) {
        if (opp.strike.side != seenSide_) seenFor_ = 0;
        seenSide_ = opp.strike.side;
        ++seenFor_;
      } else {
        seenFor_ = 0;
      }
      if (threat && seenFor_ >= tune::kDummyReactionTicks) {
        in.guardHeld = true;
        in.guardSide = seenSide_;
      }
      break;
    }
    case DummyMode::Scripted: {
      if (script_.empty() || self.posture != Posture::Standing) break;
      const DummyStepDef& st = script_[index_ % script_.size()];
      if (!attacking_) {
        if (self.phase != Phase::Idle) break;
        if (++timer_ >= st.waitTicks) {
          attacking_ = true;
          holdLeft_ = st.holdTicks;
          timer_ = 0;
          if (st.kind == StrikeKind::Quick) {
            in.quick = true;
            in.side = st.side;
            in.arm = st.arm;
            in.target = Zone::Torso;
            attacking_ = false;
            ++index_;
          }
        }
      } else {
        in.side = st.side;
        in.arm = st.arm;
        in.target = Zone::Torso;
        if (holdLeft_ > 0) {
          in.strikeHeld = true;
          --holdLeft_;
        } else {
          attacking_ = false;  // RT released: the heavy strike commits
          ++index_;
        }
      }
      break;
    }
  }
  return in;
}

}  // namespace iv

// v2: animation state for the Unreal layer (the procedural animation of anim/ needs exact phases and progress).
#pragma once

#include "iv/Fighter.h"
#include "iv/Types.h"

namespace iv {

struct AnimState {
  // Strike state machine.
  Phase phase = Phase::Idle;            // Idle, Windup, Strike, Contact, Recovery
  float progress = 0.f;                 // 0..1 within the current phase (Windup: toward the commit point; Idle: 0)
  bool committed = false;               // the commit point has been passed (RT released): the strike can no longer be cancelled cheaply
  StrikeKind kind = StrikeKind::Heavy;
  SwingSide side = SwingSide::Up;
  Arm arm = Arm::R;
  Zone target = Zone::Torso;
  float charge = 0.f;                   // 0..1 extra hold beyond the minimum windup (more power)
  // Arms and legs.
  ArmPose pose[2] = {ArmPose::Neutral, ArmPose::Neutral};
  FootPlant footPlant = FootPlant::Planted;
  float weightShift = 0.f;              // -1 (back) .. +1 (forward): where the body weight is, along the facing axis
  float lateralShift = 0.f;             // -1 (left) .. +1 (right): sidestep / turn
  bool legsLocked = false;              // feet fixed by a charging weapon (RailSpear)
  // Whole body.
  Posture posture = Posture::Standing;
  float postureProgress = 0.f;          // stagger / knockdown / dodge progress 0..1
  bool guardRaised = false;
  SwingSide guardSide = SwingSide::Up;
  bool hardStance = false;
  // Weapon and gauges (cockpit and HUD).
  bool weaponCharging = false;
  float weaponChargeProgress = 0.f;
  WeaponKind weapon = WeaponKind::RailSpear;
  float weaponCooldown01 = 0.f;         // 1 right after a shot, 0 when ready
  float stability01 = 1.f;
  float heat01 = 0.f;
  float ultimate01 = 0.f;
  // v5
  float airProgress = 0.f;              // 0..1 of the jetpack jump
  float slideProgress = 0.f;
  float lungeCharge01 = 0.f;            // while charging the rush
  int breakdown = 0;
};

AnimState MakeAnimState(const Fighter& f);

}  // namespace iv

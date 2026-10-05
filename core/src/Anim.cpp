#include "iv/Anim.h"

#include <algorithm>

namespace iv {

namespace {
float Unit(float v) { return std::max(0.f, std::min(1.f, v)); }
float Ratio(int a, int b) { return b > 0 ? Unit(static_cast<float>(a) / static_cast<float>(b)) : 1.f; }
}  // namespace

AnimState MakeAnimState(const Fighter& f) {
  AnimState a;
  a.phase = f.phase;
  a.kind = f.strike.kind;
  a.side = f.strike.side;
  a.arm = f.strike.arm;
  a.target = f.strike.target;
  a.pose[0] = f.pose[0];
  a.pose[1] = f.pose[1];
  a.footPlant = f.strike.plant;
  a.posture = f.posture;
  a.guardRaised = f.guard.held;
  a.guardSide = f.guard.side;
  a.hardStance = f.HardStanceActive();
  a.weaponCharging = f.weaponCharging;
  a.weapon = f.weapon;
  a.legsLocked = f.LegsLocked();
  a.stability01 = Unit(f.res.stability / tune::kStabilityMax);
  a.heat01 = Unit(f.res.heat / tune::kHeatMax);
  a.ultimate01 = Unit(f.ultimate / tune::kUltimateMax);
  a.ultWindTicks = f.ultWind;
  a.ultWindLen = f.ultWindLen;
  const tune::WeaponProfile& wp = f.WeaponProf();
  a.weaponChargeProgress = Unit(f.weaponCharge / static_cast<float>(wp.chargeTicks));
  a.weaponCooldown01 = wp.cooldownTicks > 0 ? Unit(static_cast<float>(f.weaponCooldown) / static_cast<float>(wp.cooldownTicks)) : 0.f;

  switch (f.phase) {
    case Phase::Idle: a.progress = 0.f; break;
    case Phase::Windup:
      a.committed = f.strike.released;
      // before the release: how far the minimum windup has come; after it: the commit delay
      a.progress = f.strike.released ? Ratio(f.strike.sinceRelease, f.strike.commitDelay) : Ratio(f.strike.held, f.strike.minHold);
      if (f.strike.released) a.contactTicks = std::max(0, f.strike.commitDelay - f.strike.sinceRelease) + std::max(f.strike.strikeLen, 1);
      a.charge = Unit(static_cast<float>(f.strike.charge) / static_cast<float>(tune::kWindupMaxChargeTicks));
      break;
    case Phase::Strike:
      a.committed = true;
      a.progress = Ratio(f.strike.strikeTick, f.strike.strikeLen);
      a.contactTicks = std::max(0, f.strike.strikeLen - f.strike.strikeTick);
      a.charge = Unit(static_cast<float>(f.strike.charge) / static_cast<float>(tune::kWindupMaxChargeTicks));
      break;
    case Phase::Contact:
      a.committed = true;
      a.progress = 1.f;
      break;
    case Phase::Recovery: a.progress = Ratio(f.phaseTicks, f.recoveryLen); break;
  }

  // Weight shift follows the footwork of the current/last strike; a dodge moves the body sideways.
  const float ph = a.phase == Phase::Idle ? 0.f : a.progress;
  switch (f.strike.foot) {
    case Footwork::StepIn: a.weightShift = 0.6f * ph; break;
    case Footwork::StepBack: a.weightShift = -0.6f * ph; break;
    case Footwork::Turn: a.lateralShift = 0.5f * ph; break;
    case Footwork::Hold: break;
  }
  if (f.posture == Posture::Dodging) {
    a.postureProgress = Ratio(f.dodgeTicks, tune::kDodgeEvadeTicks + tune::kDodgeStabilizeTicks);
    a.lateralShift = static_cast<float>(f.dodgeSide) * Unit(Ratio(f.dodgeTicks, tune::kDodgeEvadeTicks));
  } else if (f.posture == Posture::Staggered) {
    a.postureProgress = Ratio(f.postureTicks, tune::kStaggerTicks);
  } else if (f.posture == Posture::KnockedDown) {
    a.postureProgress = Ratio(f.postureTicks, tune::kKnockdownTicks);
  } else if (f.posture == Posture::Overloaded) {
    a.postureProgress = Ratio(f.postureTicks, tune::kOverloadTicks);
  }
  a.airProgress = f.posture == Posture::Airborne ? Ratio(f.airTicks, tune::kJumpAirTicks) : 0.f;
  a.slideProgress = f.posture == Posture::Sliding ? Ratio(f.slideTicks, tune::kSlideTicks) : 0.f;
  a.lungeCharge01 = (f.phase == Phase::Windup && f.strike.kind == StrikeKind::Lunge) ? Ratio(f.strike.held, tune::kLungeChargeTicks) : 0.f;
  a.breakdown = f.breakdown;
  return a;
}

}  // namespace iv

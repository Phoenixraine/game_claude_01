#include "iv/Fighter.h"

#include <algorithm>
#include <cmath>

namespace iv {

namespace {
int RoundTicks(float v) { return std::max(1, static_cast<int>(std::lround(v))); }
float Clamp(float v, float lo, float hi) { return std::max(lo, std::min(hi, v)); }
}  // namespace

ArmPose PoseAfter(StrikeKind kind, SwingSide side) {
  if (kind != StrikeKind::Heavy) return ArmPose::Neutral;  // jabs and grabs retract at once (pitch §5.3)
  switch (side) {
    case SwingSide::Up: return ArmPose::Raised;
    case SwingSide::Left: return ArmPose::CrossedLeft;
    case SwingSide::Right: return ArmPose::CrossedRight;
    case SwingSide::Down: return ArmPose::Low;
  }
  return ArmPose::Neutral;
}

bool IsInterceptLine(SwingSide attack, SwingSide counter) {
  return ((tune::kInterceptLines[Index(attack)] >> Index(counter)) & 1u) != 0;
}

Zone GuardZone(SwingSide s) {
  switch (s) {
    case SwingSide::Up: return Zone::ShoulderL;
    case SwingSide::Left: return Zone::ArmL;
    case SwingSide::Right: return Zone::ArmR;
    case SwingSide::Down: return Zone::ArmR;
  }
  return Zone::ArmL;
}

void Fighter::Reset() {
  autopilot = false;
  body.Reset();
  res = Resources();
  posture = Posture::Standing;
  postureTicks = 0;
  dodgeTicks = 0;
  dodgeDirNow = 0;
  phase = Phase::Idle;
  phaseTicks = 0;
  recoveryLen = 0;
  strike = StrikeState();
  lastArm = Arm::R;
  pose[0] = pose[1] = ArmPose::Neutral;
  poseIdle[0] = poseIdle[1] = 0;
  guard = GuardState();
  counterTicks = 0;
  feints = feintDecay = feintSlow = 0;
  flank = 0.f;
  lastMove = 0;
  proximity = 0.f;
  moveDelta = 0.f;
  contactPending = false;
  firePending = false;
  contactResolved = false;
  weaponCharging = false;
  weaponCharge = 0.f;
  weaponTarget = Zone::Torso;
  weaponAmmo = WeaponProf().ammo;
  weaponCooldown = 0;
  for (int k = 0; k < kWeaponKindCount; ++k) {
    savedCooldown[k] = 0;
    savedAmmo[k] = tune::kWeapons[k].ammo;
  }
  ultimate = 0.f;
  ultimatePending = false;
  protectedTicks = 0;
  stunImmune = blindTicks = strikeLockTicks = burnTicks = 0;
  ultimateLocked = false;
  airTicks = slideTicks = jumpCooldown = berserkCooldown = 0;
  breakdown = breakdownAcc = breakdownAge = 0;
  lastHitTick = -100000;
  lastOwnOutcome = lastIncomingOutcome = Outcome::Whiff;
  lastOwnTarget = lastIncomingZone = Zone::Torso;
  lastOwnTick = lastIncomingTick = -100000;
}

void Fighter::Emit(const StepContext& ctx, EventType t, Zone z, int a, int b, float v) const {
  if (ctx.log == nullptr) return;
  Event e;
  e.tick = ctx.now;
  e.type = t;
  e.actor = side_;
  e.zone = z;
  e.a = a;
  e.b = b;
  e.value = v;
  ctx.log->Push(e);
}

int Fighter::ScaledTicks(int base, float speed) const { return RoundTicks(static_cast<float>(base) / std::max(0.2f, speed)); }

float Fighter::SwingSpeed(Arm a) const {
  return body.modifiers().arm[Index(a)].swingSpeed * res.HeatPerformance() * (feintSlow > 0 ? tune::kFeintSlowMult : 1.f);
}

float Fighter::MoveSpeed() const {
  return tune::kMoveSpeedPerTick * body.modifiers().stepSpeed * res.LegsMult() * res.HeatPerformance() *
         (feintSlow > 0 ? tune::kFeintSlowMult : 1.f);
}

Arm Fighter::PickArm(Arm wanted, SwingSide s, bool* ok) const {
  const Modifiers& m = body.modifiers();
  const Arm order[2] = {wanted, Other(wanted)};
  for (Arm a : order) {
    const ArmMods& am = m.arm[Index(a)];
    if (am.usable && ((am.allowedSides >> Index(s)) & 1u) != 0) {
      *ok = true;
      return a;
    }
  }
  *ok = false;
  return wanted;
}

int Fighter::PoseReturnPenalty(Arm a, SwingSide s) const { return SwingAllowedByPose(a, s) ? 0 : tune::kPoseReturnTicks; }

int Fighter::TicksToContact() const { return phase == Phase::Strike ? std::max(0, strike.strikeLen - strike.strikeTick) : 0; }

float Fighter::StrikeReach() const {
  float base = tune::kHeavyReach;
  switch (strike.kind) {
    case StrikeKind::Heavy: base = tune::kHeavyReach; break;
    case StrikeKind::Quick: base = tune::kQuickReach; break;
    case StrikeKind::Grab: base = tune::kGrabReach; break;
    case StrikeKind::Lunge: base = tune::kLungeReach; break;
    case StrikeKind::AirChop: base = tune::kAirChopReach; break;
  }
  base *= body.modifiers().arm[Index(strike.arm)].reach;
  if (strike.plant == FootPlant::Stepped || strike.plant == FootPlant::Overextended) base += tune::kStepInReachBonus;
  return base;
}

float Fighter::StrikeDamage() const {
  const StrikeState& s = strike;
  float base = 0.f;
  switch (s.kind) {
    case StrikeKind::Heavy:
      base = tune::kHeavyDamage * (1.f + tune::kChargeDamageBonus * static_cast<float>(s.charge) / static_cast<float>(tune::kWindupMaxChargeTicks));
      break;
    case StrikeKind::Quick: base = tune::kQuickDamage; break;
    case StrikeKind::Grab: base = tune::kGrabDamage; break;
    case StrikeKind::Lunge: base = tune::kLungeDamage; break;
    case StrikeKind::AirChop: base = tune::kAirChopDamage; break;
  }
  const bool natural = ((tune::kNaturalTargets[Index(s.side)] >> Index(s.target)) & 1u) != 0;
  float d = base * body.modifiers().arm[Index(s.arm)].power * res.ArmsMult() * res.HeatPerformance();
  d *= tune::kPlantPower[static_cast<int>(s.plant)];
  d *= natural ? 1.f : tune::kUnnaturalTargetMult;
  d *= tune::kZoneDamageMult[Index(s.target)];
  if (s.innerLine) d *= tune::kInnerLineDamageMult;
  return d;
}

// ------------------------------------------------------------------------------------ stepping

void Fighter::Step(const Input& in, const StepContext& ctx) {
  contactPending = false;
  firePending = false;
  ultimatePending = false;
  dodgeDirNow = 0;
  moveDelta = 0.f;
  proximity = ctx.proximity;
  lastMove = in.move;
  if (protectedTicks > 0) --protectedTicks;
  if (stunImmune > 0) --stunImmune;
  if (jumpCooldown > 0) --jumpCooldown;
  if (berserkCooldown > 0) --berserkCooldown;
  if (breakdown > 0) {   // v5: damaged systems keep eating the mech until the pilot repairs them
    ++breakdownAge;
    if (++breakdownAcc >= tune::kBreakdownPeriodTicks) {
      breakdownAcc = 0;
      const DamageResult bd = body.ApplyDamage(breakdown >= 2 ? Zone::Reactor : Zone::Torso, tune::kBreakdownDamage * static_cast<float>(breakdown), StrikeKind::Quick);
      Emit(ctx, EventType::BreakdownTick, Zone::Reactor, breakdown, 0, bd.dealt);
      if (bd.before != bd.after) Emit(ctx, EventType::ZoneState, breakdown >= 2 ? Zone::Reactor : Zone::Torso, static_cast<int>(bd.after), static_cast<int>(bd.before));
      res.AddHeat(2.f * static_cast<float>(breakdown));
    }
  }
  if (blindTicks > 0 && --blindTicks == 0) Emit(ctx, EventType::StatusEnded, Zone::Head, static_cast<int>(StatusKind::Blind));
  if (strikeLockTicks > 0 && --strikeLockTicks == 0) Emit(ctx, EventType::StatusEnded, Zone::ArmR, static_cast<int>(StatusKind::StrikeLock));
  if (burnTicks > 0) {
    res.AddHeat(tune::kBurnHeatPerTick);
    if (burnTicks % tune::kBurnPeriodTicks == 0) {
      const DamageResult bd = body.ApplyDamage(Zone::Torso, tune::kBurnDamage, StrikeKind::Quick);
      Emit(ctx, EventType::BurnTick, Zone::Torso, 0, 0, bd.dealt);
      if (bd.before != bd.after) Emit(ctx, EventType::ZoneState, Zone::Torso, static_cast<int>(bd.after), static_cast<int>(bd.before));
    }
    if (--burnTicks == 0) Emit(ctx, EventType::StatusEnded, Zone::Torso, static_cast<int>(StatusKind::Burn));
  }
  if (weaponCooldown > 0 && --weaponCooldown == 0) Emit(ctx, EventType::WeaponReady, Zone::ShoulderR, Index(weapon));
  for (int k = 0; k < kWeaponKindCount; ++k)
    if (k != Index(weapon) && savedCooldown[k] > 0 && --savedCooldown[k] == 0) Emit(ctx, EventType::WeaponReady, Zone::ShoulderR, k);

  if (in.setPriority && res.RequestPriority(in.priority)) Emit(ctx, EventType::EnergyFlow, Zone::Torso, static_cast<int>(in.priority));

  switch (posture) {
    case Posture::Staggered:
      if (++postureTicks >= tune::kStaggerTicks) {
        posture = Posture::Standing;
        res.stability = std::max(res.stability, tune::kStaggerResetStability);
        stunImmune = tune::kStunImmuneTicks;
        Emit(ctx, EventType::StaggerEnd);
      }
      break;
    case Posture::KnockedDown:
      if (++postureTicks >= tune::kKnockdownTicks) {
        posture = Posture::Standing;
        res.stability = std::max(res.stability, tune::kKnockdownResetStability);
        stunImmune = tune::kStunImmuneAfterKnockdownTicks;
        Emit(ctx, EventType::GotUp);
      }
      break;
    case Posture::Dodging:
      if (++dodgeTicks >= tune::kDodgeEvadeTicks + tune::kDodgeStabilizeTicks) posture = Posture::Standing;
      break;
    case Posture::Overloaded:
      if (++postureTicks >= tune::kOverloadTicks) {
        posture = Posture::Standing;
        res.energy = std::max(res.energy, 25.f);
        res.stability = std::max(res.stability, 45.f);
        stunImmune = tune::kStunImmuneTicks;
        Emit(ctx, EventType::GotUp);
      }
      break;
    case Posture::Airborne:
    case Posture::Sliding:
      StepAirSlide(in, ctx);
      break;
    default: break;
  }

  if (posture == Posture::Standing) {
    HandleGuard(in, ctx);
    if (counterTicks > 0) --counterTicks;
    switch (phase) {
      case Phase::Idle:
        if (in.dodge) {
          TryDodge(in, ctx);
        }
        if (posture == Posture::Standing && phase == Phase::Idle && !weaponCharging) {   // v5: the jetpack and the slide
          if (in.jump) TryJump(ctx);
          else if (in.slide) TrySlide(ctx);
        }
        if (posture == Posture::Standing && phase == Phase::Idle && !weaponCharging && !in.weaponHeld && strikeLockTicks == 0) {
          if (in.quick) BeginStrike(in, StrikeKind::Quick, ctx);
          else if (in.toGrab && !in.strikeHeld) BeginStrike(in, StrikeKind::Grab, ctx);
          else if (in.lungeHeld && !in.strikeHeld) BeginStrike(in, StrikeKind::Lunge, ctx);
          else if (in.strikeHeld) BeginStrike(in, StrikeKind::Heavy, ctx);
        }
        break;
      case Phase::Windup: HandleWindup(in, ctx); break;
      case Phase::Strike: HandleStrike(in, ctx); break;
      case Phase::Contact:
        // Contact is visible for exactly one tick. Duel resolves it and presets recoveryLen through
        // FinishStrike; a stand-alone fighter that was never resolved just recovers normally.
        if (contactResolved) {
          phase = Phase::Recovery;
          phaseTicks = 0;
        } else {
          StartRecovery(tune::kHeavyRecoveryTicks, ctx);
        }
        contactResolved = false;
        break;
      case Phase::Recovery:
        if (++phaseTicks >= recoveryLen) {
          phase = Phase::Idle;
          phaseTicks = 0;
        }
        break;
    }
    HandleWeapon(in, ctx);
    if (in.ultimate && UltimateReady() && !ultimateLocked && !weaponCharging && (phase == Phase::Idle || phase == Phase::Recovery)) {
      ultimatePending = true;
      ultimateTarget = in.target;
    }

    if (in.move != 0 && !guard.hard && !weaponCharging) {
      float mult = 0.f;
      switch (phase) {
        case Phase::Idle: mult = 1.f; break;
        case Phase::Recovery: mult = tune::kRecoveryMoveMult; break;
        case Phase::Windup: mult = tune::kWindupMoveMult; break;
        default: break;
      }
      if (in.move < 0) mult *= tune::kRetreatSpeedMult;  // pitch §11: stepping back is slower than stepping in
      moveDelta -= static_cast<float>(in.move) * MoveSpeed() * mult;
    }
    if (strike.plant == FootPlant::Retreated && phase == Phase::Recovery && phaseTicks < 20) moveDelta += tune::kStepBackDistance / 20.f;
  } else if (posture != Posture::Clinched) {
    if (guard.hard) Emit(ctx, EventType::HardStanceOff);
    guard = GuardState();
    weaponCharging = false;
    weaponCharge = 0.f;
  }

  const bool regen = posture != Posture::Clinched && !guard.held && phase != Phase::Windup;
  const EnergyPriority prioBefore = res.priority;
  const ResourceTickResult t = res.Tick(body.modifiers(), body.DamagedLimbs(), ctx.coolingMult, regen);
  if (t.heatWarningStarted) Emit(ctx, EventType::HeatWarning, Zone::Reactor);
  if (t.coolantLeakStarted) {
    Emit(ctx, EventType::CoolantLeak, Zone::Reactor);
    Emit(ctx, EventType::SystemFailure, Zone::Reactor, static_cast<int>(SystemId::Cooling));
  }
  if (t.prioritySwitched) Emit(ctx, EventType::EnergyShift, Zone::Torso, static_cast<int>(res.priority), static_cast<int>(prioBefore));
  if (t.shutdown) {
    posture = Posture::ShutDown;
    Emit(ctx, EventType::Shutdown, Zone::Reactor);
    Emit(ctx, EventType::SystemFailure, Zone::Reactor, static_cast<int>(SystemId::Power));
  }

  // Re-facing the opponent (pitch §11: no instant 180s).
  if (posture == Posture::Standing && flank != 0.f) {
    const float rate = tune::kFlankTurnDegPerTick * body.modifiers().turnRate * res.LegsMult();
    flank = std::fabs(flank) <= rate ? 0.f : flank - (flank > 0.f ? rate : -rate);
  }

  // Post-strike pose relaxes back to Neutral while the arm is idle (pitch §5.4).
  for (int a = 0; a < 2; ++a) {
    if (phase == Phase::Idle && pose[a] != ArmPose::Neutral && ++poseIdle[a] >= tune::kPoseDecayTicks) {
      pose[a] = ArmPose::Neutral;
      poseIdle[a] = 0;
    }
  }
  if (feints > 0 && --feintDecay <= 0) {
    --feints;
    feintDecay = tune::kFeintDecayTicks;
  }
  if (feintSlow > 0) --feintSlow;
}

void Fighter::HandleGuard(const Input& in, const StepContext& ctx) {
  const bool canGuard = (phase == Phase::Idle || phase == Phase::Recovery) && !weaponCharging && !in.weaponHeld;
  if (in.guardHeld && canGuard) {
    if (!guard.held || in.guardSide != guard.side) {
      if (guard.hard) Emit(ctx, EventType::HardStanceOff);
      guard.held = true;
      guard.side = in.guardSide;
      guard.age = 0;
      guard.pressTick = ctx.now;
      guard.hard = false;
      guard.hardAge = 0;
    } else {
      ++guard.age;
    }
    if (!res.Spend(tune::kGuardEnergyPerTick)) {
      if (guard.hard) Emit(ctx, EventType::HardStanceOff);
      guard = GuardState();
      return;
    }
    if (in.hardStance) {
      if (!guard.hard) {
        if (res.stability >= tune::kHardStanceMinStability && res.energy > 5.f) {
          guard.hard = true;
          guard.hardAge = 0;
          Emit(ctx, EventType::HardStanceOn);
        }
      } else if (!res.Spend(tune::kHardStanceEnergyPerTick)) {
        guard.hard = false;
        Emit(ctx, EventType::HardStanceOff);
      } else {
        ++guard.hardAge;
      }
    } else if (guard.hard) {
      guard.hard = false;
      Emit(ctx, EventType::HardStanceOff);
    }
  } else {
    if (guard.hard) Emit(ctx, EventType::HardStanceOff);
    guard = GuardState();
  }
}

void Fighter::BeginStrike(const Input& in, StrikeKind kind, const StepContext& ctx) {
  const Modifiers& m = body.modifiers();
  bool ok = false;
  Arm arm = in.arm;
  if (kind == StrikeKind::Lunge) {
    if (res.energy < tune::kLungeEnergy) return;
    arm = PickArm(Arm::R, SwingSide::Right, &ok);
  } else if (kind == StrikeKind::Heavy) {
    arm = PickArm(in.arm, in.side, &ok);
  } else if (kind == StrikeKind::Quick) {
    ok = m.arm[Index(in.arm)].usable || m.arm[Index(Other(in.arm))].usable;
    arm = m.arm[Index(in.arm)].usable ? in.arm : Other(in.arm);
  } else {
    ok = m.arm[Index(in.arm)].canGrab || m.arm[Index(Other(in.arm))].canGrab;  // pitch §9: a destroyed hand cannot grab
    arm = m.arm[Index(in.arm)].canGrab ? in.arm : Other(in.arm);
  }
  if (!ok) return;

  if (guard.hard) Emit(ctx, EventType::HardStanceOff);
  guard = GuardState();

  strike = StrikeState();
  strike.kind = kind;
  strike.side = kind == StrikeKind::Lunge ? (IsLateralSwing(in.side) ? in.side : SwingSide::Right) : in.side;
  strike.target = kind == StrikeKind::Lunge ? Zone::Torso : in.target;
  strike.arm = arm;
  strike.foot = in.footwork;
  lastArm = arm;
  const float speed = SwingSpeed(arm);
  if (kind == StrikeKind::Lunge) {
    strike.minHold = tune::kLungeChargeTicks;
    strike.commitDelay = tune::kLungeCommitTicks;
    strike.held = 1;
    Emit(ctx, EventType::LungeCharging);
  } else if (kind == StrikeKind::Heavy) {
    const int penalty = PoseReturnPenalty(arm, in.side);
    strike.minHold = ScaledTicks(tune::kWindupMinTicks, speed) + penalty;
    strike.commitDelay = tune::kCommitDelayTicks;
    strike.held = 1;
    if (penalty > 0) Emit(ctx, EventType::PoseReturn, Zone::Torso, static_cast<int>(pose[Index(arm)]));
  } else {
    strike.released = true;
    strike.commitDelay = ScaledTicks(kind == StrikeKind::Quick ? tune::kQuickWindupTicks : tune::kGrabWindupTicks, speed);
  }
  if (counterTicks > 0 && kind != StrikeKind::Grab) {
    strike.innerLine = true;  // pitch §6: a counter after a parry travels the inner line
    counterTicks = 0;
  }
  phase = Phase::Windup;
  phaseTicks = 0;
  Emit(ctx, EventType::WindupStarted, Zone::Torso, static_cast<int>(kind), Index(in.side));
}

void Fighter::RegisterFeint(const StepContext& ctx) {
  res.AddHeat(tune::kFeintHeat * (feints >= tune::kMaxFeintsBeforePenalty ? 2.f : 1.f));
  ++feints;
  feintDecay = tune::kFeintDecayTicks;
  feintSlow = tune::kFeintSlowTicks;
  Emit(ctx, EventType::Feint, Zone::Torso, feints);
}

void Fighter::HandleWindup(const Input& in, const StepContext& ctx) {
  StrikeState& s = strike;
  ++phaseTicks;
  const Modifiers& m = body.modifiers();
  const bool lunge = s.kind == StrikeKind::Lunge;
  const bool holding = lunge ? in.lungeHeld : in.strikeHeld;
  if (!s.released) {
    // Still holding RT: everything up to the release is free to change or cancel (pitch §5.2, §8).
    if (in.cancel) {
      Emit(ctx, EventType::CancelCheap, Zone::Torso, 0);
      phase = Phase::Idle;
      phaseTicks = 0;
      return;
    }
    const ArmMods& am = m.arm[Index(s.arm)];
    if (!lunge && in.toGrab && am.canGrab) {
      s.kind = StrikeKind::Grab;  // pitch §8: turn the swing into a grab
      s.released = true;
      s.sinceRelease = 0;
      s.commitDelay = ScaledTicks(tune::kGrabWindupTicks, SwingSpeed(s.arm));
      RegisterFeint(ctx);
      return;
    }
    if (!lunge) {
      if (in.switchArm) {
        const Arm other = Other(s.arm);
        const ArmMods& om = m.arm[Index(other)];
        if (am.canRetarget && om.usable && ((om.allowedSides >> Index(s.side)) & 1u) != 0) {
          s.arm = other;
          lastArm = other;
          s.minHold = ScaledTicks(tune::kWindupMinTicks, SwingSpeed(other)) + PoseReturnPenalty(other, s.side);
          RegisterFeint(ctx);
        }
      } else if (in.strikeHeld && am.canRetarget && (in.target != s.target || in.side != s.side)) {
        // Only while RT is still held: the stick springs back to centre on release and must not count as a feint.
        bool changed = false;
        if (in.target != s.target) {
          s.target = in.target;
          changed = true;
        }
        if (in.side != s.side && ((am.allowedSides >> Index(in.side)) & 1u) != 0) {
          s.side = in.side;
          s.minHold = ScaledTicks(tune::kWindupMinTicks, SwingSpeed(s.arm)) + PoseReturnPenalty(s.arm, s.side);
          changed = true;
        }
        if (changed) RegisterFeint(ctx);
      }
    }
    if (holding) {
      ++s.held;
      s.foot = lunge ? Footwork::StepIn : in.footwork;
      if (s.held > s.minHold) {
        s.charge = std::min(s.held - s.minHold, tune::kWindupMaxChargeTicks);
        res.AddHeat(tune::kHeavyChargeHeatPerTick * (lunge ? 0.5f : 1.f));
      }
    } else if (s.held < s.minHold) {
      // Released before the windup was long enough: nothing is committed.
      Emit(ctx, EventType::CancelCheap, Zone::Torso, 1);
      phase = Phase::Recovery;
      phaseTicks = 0;
      recoveryLen = tune::kAbortRecoveryTicks;
    } else {
      s.released = true;
      s.sinceRelease = 0;
      s.foot = lunge ? Footwork::StepIn : in.footwork;
    }
    return;
  }

  // RT released (or quick / grab path): the commit delay is running.
  if (in.cancel && s.sinceRelease < s.commitDelay) {
    res.AddHeat(tune::kCheapCancelHeat);
    Emit(ctx, EventType::CancelCheap, Zone::Torso, 2);
    phase = Phase::Recovery;
    phaseTicks = 0;
    recoveryLen = tune::kAbortRecoveryTicks;
    return;
  }
  if (++s.sinceRelease < s.commitDelay) return;

  // ---- commit point passed: the strike is irreversible (pitch §5.2 (4)) ----
  switch (s.foot) {
    case Footwork::StepIn:
      s.plant = res.stability >= tune::kStepInMinStability && m.stepSpeed >= 0.4f ? FootPlant::Stepped : FootPlant::Overextended;
      break;
    case Footwork::Hold: s.plant = FootPlant::Planted; break;
    case Footwork::Turn: s.plant = FootPlant::Turned; break;
    case Footwork::StepBack: s.plant = FootPlant::Retreated; break;
  }
  if (s.plant == FootPlant::Turned) flank = Clamp(flank + (s.arm == Arm::L ? 1.f : -1.f) * tune::kTurnAngleDeg, -180.f, 180.f);
  int len = tune::kHeavyStrikeTicks;
  switch (s.kind) {
    case StrikeKind::Heavy: len = tune::kHeavyStrikeTicks; break;
    case StrikeKind::Quick: len = tune::kQuickStrikeTicks; break;
    case StrikeKind::Grab: len = tune::kGrabStrikeTicks; break;
    case StrikeKind::Lunge: len = tune::kLungeStrikeTicks; break;
    case StrikeKind::AirChop: len = tune::kAirChopStrikeTicks; break;
  }
  s.strikeLen = ScaledTicks(len, SwingSpeed(s.arm));
  s.strikeTick = 0;
  phase = Phase::Strike;
  phaseTicks = 0;
  if (s.kind == StrikeKind::Heavy) res.AddHeat(tune::kHeavyReleaseHeat);
  if (s.kind == StrikeKind::Lunge) {
    res.Spend(tune::kLungeEnergy);
    res.AddHeat(tune::kHeavyReleaseHeat * 2.f);
  }
  Emit(ctx, EventType::Committed, Zone::Torso, static_cast<int>(s.kind), static_cast<int>(s.plant));
  LoseStability(tune::kPlantStabilityCost[static_cast<int>(s.plant)], ctx);
}

void Fighter::HandleStrike(const Input& in, const StepContext& ctx) {
  StrikeState& s = strike;
  if (in.cancel) {
    // pitch §5.2 (4): after the commit point B becomes an emergency brake, not a free cancel.
    res.AddHeat(tune::kEmergencyBrakeHeat);
    Emit(ctx, EventType::EmergencyBrake, Zone::Torso);
    phase = Phase::Recovery;
    phaseTicks = 0;
    recoveryLen = tune::kEmergencyBrakeRecoveryTicks;
    LoseStability(tune::kEmergencyBrakeStability, ctx);
    return;
  }
  if (s.kind == StrikeKind::Lunge) moveDelta -= tune::kLungeRushDistance / static_cast<float>(std::max(1, s.strikeLen));
  else if (s.plant == FootPlant::Stepped || s.plant == FootPlant::Overextended) moveDelta -= tune::kStepInDistance / static_cast<float>(std::max(1, s.strikeLen));
  ++phaseTicks;
  if (++s.strikeTick >= s.strikeLen) {
    phase = Phase::Contact;
    phaseTicks = 0;
    contactPending = true;
  }
}

int Fighter::ComputeRecovery(int baseTicks) const {
  const float legs = std::max(0.35f, body.modifiers().stabilityRecovery) * res.LegsMult();
  const float f = tune::kPlantRecoveryMult[static_cast<int>(strike.plant)] * tune::kPoseRecoveryMult[static_cast<int>(pose[Index(strike.arm)])] / legs;
  return RoundTicks(static_cast<float>(baseTicks) * f);
}

void Fighter::StartRecovery(int baseTicks, const StepContext&) {
  phase = Phase::Recovery;
  phaseTicks = 0;
  recoveryLen = ComputeRecovery(baseTicks);
}

void Fighter::FinishStrike(Outcome outcome, const StepContext& ctx) {
  const int a = Index(strike.arm);
  pose[a] = PoseAfter(strike.kind, strike.side);
  poseIdle[a] = 0;
  int base = tune::kHeavyRecoveryTicks;
  switch (strike.kind) {
    case StrikeKind::Heavy: base = tune::kHeavyRecoveryTicks; break;
    case StrikeKind::Quick: base = tune::kQuickRecoveryTicks; break;
    case StrikeKind::Grab: base = tune::kGrabRecoveryTicks; break;
    case StrikeKind::Lunge: base = tune::kLungeRecoveryTicks; break;
    case StrikeKind::AirChop: base = tune::kAirChopRecoveryTicks; break;
  }
  switch (outcome) {
    case Outcome::Whiff:
    case Outcome::Evaded: base = RoundTicks(static_cast<float>(base) * 1.3f); break;
    case Outcome::Parried:
    case Outcome::GrabParried: base += tune::kParryRecoveryBonusTicks; break;
    case Outcome::Intercepted: base = tune::kInterceptedRecoveryTicks; break;
    case Outcome::Jumped:
    case Outcome::Slid: base = RoundTicks(static_cast<float>(base) * 1.5f); break;
    default: break;
  }
  (void)ctx;
  recoveryLen = ComputeRecovery(base);
  contactResolved = true;  // the phase stays Contact until the next tick (pitch §5: Strike -> Contact -> Recovery)
}

void Fighter::HandleWeapon(const Input& in, const StepContext& ctx) {
  const tune::WeaponProfile& wp = WeaponProf();
  const bool can = posture == Posture::Standing && body.state(Zone::ShoulderR) < ZoneState::Destroyed;
  if (weaponCharging) {
    if (!can || phase != Phase::Idle) {
      weaponCharging = false;
      weaponCharge = 0.f;
      return;
    }
    if (in.weaponHeld) {
      weaponCharge += res.WeaponChargeMult();
      res.AddHeat(tune::kWeaponChargeHeatPerTick);
      weaponTarget = in.target;
    } else {
      weaponCharging = false;
      if (weaponCharge >= static_cast<float>(wp.chargeTicks)) firePending = true;
      else weaponCharge = 0.f;
    }
  } else if (in.weaponHeld && can && phase == Phase::Idle && !guard.held && weaponCooldown == 0 && weaponAmmo != 0) {
    weaponCharging = true;
    weaponCharge = 0.f;
    weaponTarget = in.target;
    Emit(ctx, EventType::WeaponCharging, Zone::ShoulderR, Index(weapon));
  }
}

void Fighter::FinishWeapon(const StepContext& ctx) {
  const tune::WeaponProfile& wp = WeaponProf();
  weaponCharge = 0.f;
  weaponCharging = false;
  res.AddHeat(wp.heatPerShot);
  phase = Phase::Recovery;
  phaseTicks = 0;
  recoveryLen = wp.recoveryTicks;
  weaponCooldown = wp.cooldownTicks;
  if (weaponAmmo > 0 && --weaponAmmo == 0) Emit(ctx, EventType::WeaponEmpty, Zone::ShoulderR, Index(weapon));
}

void Fighter::SetLoadout(WeaponKind k) {
  weapon = k;
  weaponAmmo = WeaponProf().ammo;
  weaponCooldown = 0;
  for (int i = 0; i < kWeaponKindCount; ++i) {
    savedCooldown[i] = 0;
    savedAmmo[i] = tune::kWeapons[i].ammo;
  }
  weaponCharging = false;
  weaponCharge = 0.f;
}

bool Fighter::SelectWeapon(WeaponKind k) {
  if (k == weapon) return true;
  if (weaponCharging || phase != Phase::Idle || posture != Posture::Standing) return false;
  savedCooldown[Index(weapon)] = weaponCooldown;
  savedAmmo[Index(weapon)] = weaponAmmo;
  weapon = k;
  weaponCooldown = savedCooldown[Index(k)];
  weaponAmmo = savedAmmo[Index(k)];
  return true;
}

void Fighter::GainUltimate(float amount, const StepContext& ctx) {
  if (amount <= 0.f) return;
  const bool was = UltimateReady();
  ultimate = std::min(tune::kUltimateMax, ultimate + amount);
  if (!was && UltimateReady()) Emit(ctx, EventType::UltimateReady);
}

void Fighter::TryDodge(const Input& in, const StepContext& ctx) {
  if (posture != Posture::Standing || phase != Phase::Idle || weaponCharging || guard.hard) return;
  const Modifiers& m = body.modifiers();
  const bool allowed = in.dodgeDir < 0 ? m.dodgeLeft : m.dodgeRight;  // pitch §9: damaged legs lose dodges
  if (!allowed || !res.Spend(tune::kDodgeEnergy)) return;
  guard = GuardState();
  res.AddHeat(tune::kDodgeHeat);
  posture = Posture::Dodging;
  dodgeTicks = 0;
  dodgeDirNow = in.dodgeDir < 0 ? -1 : 1;
  dodgeSide = dodgeDirNow;
  Emit(ctx, EventType::Dodge, Zone::Torso, dodgeDirNow);
  // pitch §6: a dodge is one heavy step; the cost lands on stability, and the mech is exposed afterwards.
  res.LoseStability(tune::kDodgeStability);
}

// ------------------------------------------------------------------------------- taking damage

void Fighter::EnterStagger(const StepContext& ctx) {
  posture = Posture::Staggered;
  postureTicks = 0;
  airTicks = slideTicks = 0;
  res.stability = tune::kStaggerHoldStability;
  if (phase != Phase::Contact) {
    phase = Phase::Idle;
    phaseTicks = 0;
  }
  if (guard.hard) Emit(ctx, EventType::HardStanceOff);
  guard = GuardState();
  weaponCharging = false;
  weaponCharge = 0.f;
  Emit(ctx, EventType::StaggerBegin);
}

void Fighter::EnterKnockdown(const StepContext& ctx) {
  posture = Posture::KnockedDown;
  postureTicks = 0;
  if (phase != Phase::Contact) {
    phase = Phase::Idle;
    phaseTicks = 0;
  }
  guard = GuardState();
  weaponCharging = false;
  weaponCharge = 0.f;
  Emit(ctx, EventType::Knockdown);
}

void Fighter::LoseStability(float amount, const StepContext& ctx) {
  if (stunImmune > 0 && (posture == Posture::Standing || posture == Posture::Dodging || posture == Posture::Airborne || posture == Posture::Sliding)) {   // v3: no chained stun
    if (amount > 0.f) res.stability = std::max(std::min(res.stability, tune::kStunImmuneFloor), res.stability - amount);
    return;
  }
  if (!res.LoseStability(amount)) return;
  if (posture == Posture::Staggered) EnterKnockdown(ctx);
  else if (posture == Posture::Standing || posture == Posture::Dodging || posture == Posture::Airborne || posture == Posture::Sliding) EnterStagger(ctx);
}

void Fighter::Interrupt(int recoveryTicks, const StepContext& ctx) {
  Emit(ctx, EventType::Interrupted, Zone::Torso, static_cast<int>(phase));
  phase = Phase::Recovery;
  phaseTicks = 0;
  recoveryLen = recoveryTicks;
  contactPending = false;
}

HitReport Fighter::TakeHit(Zone zone, float damage, StrikeKind kind, float stabilityHit, const StepContext& ctx) {
  HitReport r;
  if (protectedTicks > 0) return r;  // v2: the shooter is untouchable for a moment after an external cut
  float dmg = damage * res.DamageTakenMult();
  if (autopilot) dmg *= tune::kAutopilotDamageMult;   // v4: nobody braces the empty mech (boarding)
  if (posture == Posture::Staggered) dmg *= tune::kStaggerDamageMult;
  else if (posture == Posture::KnockedDown) dmg *= tune::kKnockdownDamageMult;

  const DamageResult d = body.ApplyDamage(zone, dmg, kind);
  r.dealt = d.dealt;
  r.severed = d.severed;
  r.before = d.before;
  r.after = d.after;
  r.layer = d.deepest;
  if (!d.ignored) {
    Emit(ctx, EventType::Hit, zone, 0, 0, d.dealt);
    if (d.before != d.after) Emit(ctx, EventType::ZoneState, zone, static_cast<int>(d.after), static_cast<int>(d.before));
    if (d.severed) Emit(ctx, EventType::LimbSevered, zone);
    // v2 presentation: armour plates come off in equal steps as the Armor layer drains.
    const int plates = tune::kArmorPlates[Index(zone)];
    const float maxArmor = tune::kArmorMax[Index(zone)];
    const int lostBefore = static_cast<int>(std::floor((1.f - d.armorBefore / maxArmor) * static_cast<float>(plates) + 0.0001f));
    const int lostAfter = static_cast<int>(std::floor((1.f - d.armorAfter / maxArmor) * static_cast<float>(plates) + 0.0001f));
    for (int k = lostBefore; k < std::min(lostAfter, plates); ++k) Emit(ctx, EventType::ArmorPlateLost, zone, k, plates);
    if (zone == Zone::Reactor && d.before < ZoneState::Damaged && d.after >= ZoneState::Damaged) Emit(ctx, EventType::ReactorBreach, zone);
    if (d.before < ZoneState::Critical && d.after >= ZoneState::Critical) {
      int sys = -1;
      switch (zone) {
        case Zone::Head: sys = static_cast<int>(SystemId::Sensors); break;
        case Zone::Reactor: sys = static_cast<int>(SystemId::Power); break;
        case Zone::ArmL: sys = static_cast<int>(SystemId::ArmL); break;
        case Zone::ArmR: sys = static_cast<int>(SystemId::ArmR); break;
        case Zone::LegL: sys = static_cast<int>(SystemId::LegL); break;
        case Zone::LegR: sys = static_cast<int>(SystemId::LegR); break;
        case Zone::ShoulderR: sys = static_cast<int>(SystemId::Weapon); break;
        default: break;
      }
      if (sys >= 0) Emit(ctx, EventType::SystemFailure, zone, sys);
      if (zone != Zone::Head) AddBreakdown(zone == Zone::Reactor || zone == Zone::Torso ? 2 : 1, ctx);
    }
    GainUltimate(std::min(tune::kUltGainTakenCap, d.dealt * tune::kUltGainTakenPerDamage), ctx);
  }
  lastHitTick = ctx.now;

  // pitch §5.3: a hit breaks a long windup; a strike that is almost home still trades.
  if (phase == Phase::Windup || (phase == Phase::Strike && TicksToContact() > tune::kStrikeTradeWindowTicks)) {
    Interrupt(tune::kInterruptedRecoveryTicks, ctx);
    r.interrupted = true;
  }
  if (weaponCharging) {
    weaponCharging = false;
    weaponCharge = 0.f;
    Emit(ctx, EventType::WeaponInterrupted);
  }
  const Posture before = posture;
  LoseStability(stabilityHit, ctx);
  r.staggered = before != Posture::Staggered && posture == Posture::Staggered;
  r.knockedDown = before != Posture::KnockedDown && posture == Posture::KnockedDown;
  return r;
}

void Fighter::ApplyStatus(StatusKind k, int ticks, const StepContext& ctx) {
  switch (k) {
    case StatusKind::Blind: blindTicks = std::max(blindTicks, ticks); break;
    case StatusKind::StrikeLock:
      strikeLockTicks = std::max(strikeLockTicks, ticks);
      if (phase == Phase::Windup || phase == Phase::Strike) Interrupt(tune::kInterruptedRecoveryTicks, ctx);
      break;
    case StatusKind::Burn: burnTicks = std::max(burnTicks, ticks); break;
    default: return;
  }
  Emit(ctx, EventType::StatusApplied, k == StatusKind::Blind ? Zone::Head : Zone::Torso, static_cast<int>(k), ticks);
}

void Fighter::ClashBreak(const StepContext& ctx) {
  const bool wasStriking = phase == Phase::Windup || phase == Phase::Strike || phase == Phase::Contact;
  if (wasStriking) {
    const int a = Index(strike.arm);
    pose[a] = PoseAfter(strike.kind, strike.side);
    poseIdle[a] = 0;
  }
  phase = Phase::Recovery;
  phaseTicks = 0;
  recoveryLen = tune::kClashRecoveryTicks;
  contactPending = false;
  contactResolved = false;
  res.AddHeat(tune::kClashHeat);
  LoseStability(tune::kClashStability, ctx);
}

bool Fighter::TryJump(const StepContext& ctx) {
  if (posture != Posture::Standing || phase != Phase::Idle || weaponCharging || guard.hard || jumpCooldown > 0) return false;
  if (!body.modifiers().dodgeLeft && !body.modifiers().dodgeRight) return false;   // ruined legs cannot jump
  if (!res.Spend(tune::kJumpEnergy)) return false;
  guard = GuardState();
  res.AddHeat(tune::kDodgeHeat * 1.5f);
  posture = Posture::Airborne;
  airTicks = 0;
  jumpCooldown = tune::kJumpCooldownTicks;
  Emit(ctx, EventType::JumpStarted);
  return true;
}

bool Fighter::TrySlide(const StepContext& ctx) {
  if (posture != Posture::Standing || phase != Phase::Idle || weaponCharging || guard.hard) return false;
  if (!body.modifiers().dodgeLeft && !body.modifiers().dodgeRight) return false;
  if (!res.Spend(tune::kSlideEnergy)) return false;
  guard = GuardState();
  posture = Posture::Sliding;
  slideTicks = 0;
  Emit(ctx, EventType::SlideStarted);
  return true;
}

void Fighter::StepAirSlide(const Input& in, const StepContext& ctx) {
  if (posture == Posture::Sliding) {
    if (++slideTicks >= tune::kSlideTicks) {
      posture = Posture::Standing;
      slideTicks = 0;
    }
    return;
  }
  // airborne
  ++airTicks;
  if (phase == Phase::Idle && in.chop && airTicks >= tune::kAirChopMinTicks && body.modifiers().arm[Index(Arm::R)].usable) {
    strike = StrikeState();
    strike.kind = StrikeKind::AirChop;
    strike.side = SwingSide::Up;
    strike.target = in.target == Zone::Reactor ? Zone::Torso : in.target;
    strike.arm = Arm::R;
    strike.plant = FootPlant::Planted;
    strike.strikeLen = ScaledTicks(tune::kAirChopStrikeTicks, SwingSpeed(Arm::R));
    strike.strikeTick = 0;
    strike.released = true;
    phase = Phase::Strike;
    phaseTicks = 0;
    Emit(ctx, EventType::AirChopStarted);
    Emit(ctx, EventType::Committed, Zone::Torso, static_cast<int>(StrikeKind::AirChop), 0);
  }
  if (phase == Phase::Strike) {
    ++phaseTicks;
    moveDelta -= 14.f / static_cast<float>(std::max(1, strike.strikeLen));
    if (++strike.strikeTick >= strike.strikeLen) {
      phase = Phase::Contact;
      phaseTicks = 0;
      contactPending = true;
    }
  } else if (phase == Phase::Contact) {
    if (contactResolved) {
      phase = Phase::Recovery;
      phaseTicks = 0;
    } else {
      StartRecovery(tune::kAirChopRecoveryTicks, ctx);
    }
    contactResolved = false;
  } else if (phase == Phase::Recovery) {
    if (++phaseTicks >= recoveryLen) {
      phase = Phase::Idle;
      phaseTicks = 0;
    }
  }
  if (airTicks >= tune::kJumpAirTicks && phase != Phase::Strike && phase != Phase::Contact) {
    posture = Posture::Standing;   // landed; a chop recovery (if any) goes on
    airTicks = 0;
    LoseStability(4.f, ctx);
  }
}

void Fighter::EnterOverload(const StepContext& ctx) {
  posture = Posture::Overloaded;
  postureTicks = 0;
  phase = Phase::Idle;
  phaseTicks = 0;
  guard = GuardState();
  weaponCharging = false;
  weaponCharge = 0.f;
  contactPending = false;
  res.energy = 0.f;
  berserkCooldown = tune::kBerserkCooldownTicks;
  Emit(ctx, EventType::Shutdown, Zone::Reactor, 1);
}

void Fighter::AddBreakdown(int levels, const StepContext& ctx) {
  const int before = breakdown;
  breakdown = std::min(tune::kBreakdownMaxLevel, breakdown + levels);
  if (breakdown > before) {
    if (before == 0) breakdownAcc = 0;
    breakdownAge = 0;
    Emit(ctx, EventType::BreakdownStarted, Zone::Reactor, breakdown);
  }
}

void Fighter::RepairBreakdown(int levels, const StepContext& ctx) {
  if (breakdown == 0) return;
  breakdown = std::max(0, breakdown - levels);
  if (breakdown == 0) {
    breakdownAcc = 0;
    Emit(ctx, EventType::BreakdownRepaired, Zone::Reactor);
  }
}

void Fighter::EnterClinch() {
  posture = Posture::Clinched;
  postureTicks = 0;
  phase = Phase::Idle;
  phaseTicks = 0;
  guard = GuardState();
  weaponCharging = false;
  weaponCharge = 0.f;
  contactPending = false;
}

void Fighter::LeaveClinch() {
  if (posture == Posture::Clinched) posture = Posture::Standing;
}

}  // namespace iv

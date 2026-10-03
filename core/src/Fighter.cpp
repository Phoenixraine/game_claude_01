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
  float base = strike.kind == StrikeKind::Heavy ? tune::kHeavyReach : strike.kind == StrikeKind::Quick ? tune::kQuickReach : tune::kGrabReach;
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
  dodgeDirNow = 0;
  moveDelta = 0.f;
  proximity = ctx.proximity;
  lastMove = in.move;

  if (in.setPriority && res.RequestPriority(in.priority)) Emit(ctx, EventType::EnergyFlow, Zone::Torso, static_cast<int>(in.priority));

  switch (posture) {
    case Posture::Staggered:
      if (++postureTicks >= tune::kStaggerTicks) {
        posture = Posture::Standing;
        res.stability = std::max(res.stability, tune::kStaggerResetStability);
      }
      break;
    case Posture::KnockedDown:
      if (++postureTicks >= tune::kKnockdownTicks) {
        posture = Posture::Standing;
        res.stability = std::max(res.stability, tune::kKnockdownResetStability);
        Emit(ctx, EventType::GotUp);
      }
      break;
    case Posture::Dodging:
      if (++dodgeTicks >= tune::kDodgeEvadeTicks + tune::kDodgeStabilizeTicks) posture = Posture::Standing;
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
        if (posture == Posture::Standing && phase == Phase::Idle && !weaponCharging && !in.weaponHeld) {
          if (in.quick) BeginStrike(in, StrikeKind::Quick, ctx);
          else if (in.toGrab && !in.strikeHeld) BeginStrike(in, StrikeKind::Grab, ctx);
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

    if (in.move != 0 && !guard.hard && !weaponCharging) {
      float mult = 0.f;
      switch (phase) {
        case Phase::Idle: mult = 1.f; break;
        case Phase::Recovery: mult = tune::kRecoveryMoveMult; break;
        case Phase::Windup: mult = tune::kWindupMoveMult; break;
        default: break;
      }
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
  const ResourceTickResult t = res.Tick(body.modifiers(), body.DamagedLimbs(), ctx.coolingMult, regen);
  if (t.heatWarningStarted) Emit(ctx, EventType::HeatWarning, Zone::Reactor);
  if (t.coolantLeakStarted) Emit(ctx, EventType::CoolantLeak, Zone::Reactor);
  if (t.prioritySwitched) Emit(ctx, EventType::EnergySwitched, Zone::Torso, static_cast<int>(res.priority));
  if (t.shutdown) {
    posture = Posture::ShutDown;
    Emit(ctx, EventType::Shutdown, Zone::Reactor);
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
  if (kind == StrikeKind::Heavy) {
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
  strike.side = in.side;
  strike.target = in.target;
  strike.arm = arm;
  strike.foot = in.footwork;
  lastArm = arm;
  const float speed = SwingSpeed(arm);
  if (kind == StrikeKind::Heavy) {
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
  if (!s.released) {
    // Still holding RT: everything up to the release is free to change or cancel (pitch §5.2, §8).
    if (in.cancel) {
      Emit(ctx, EventType::CancelCheap, Zone::Torso, 0);
      phase = Phase::Idle;
      phaseTicks = 0;
      return;
    }
    const ArmMods& am = m.arm[Index(s.arm)];
    if (in.toGrab && am.canGrab) {
      s.kind = StrikeKind::Grab;  // pitch §8: turn the swing into a grab
      s.released = true;
      s.sinceRelease = 0;
      s.commitDelay = ScaledTicks(tune::kGrabWindupTicks, SwingSpeed(s.arm));
      RegisterFeint(ctx);
      return;
    }
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
    if (in.strikeHeld) {
      ++s.held;
      s.foot = in.footwork;
      if (s.held > s.minHold) {
        s.charge = std::min(s.held - s.minHold, tune::kWindupMaxChargeTicks);
        res.AddHeat(tune::kHeavyChargeHeatPerTick);
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
      s.foot = in.footwork;
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
  const int len = s.kind == StrikeKind::Heavy ? tune::kHeavyStrikeTicks : s.kind == StrikeKind::Quick ? tune::kQuickStrikeTicks : tune::kGrabStrikeTicks;
  s.strikeLen = ScaledTicks(len, SwingSpeed(s.arm));
  s.strikeTick = 0;
  phase = Phase::Strike;
  phaseTicks = 0;
  if (s.kind == StrikeKind::Heavy) res.AddHeat(tune::kHeavyReleaseHeat);
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
  if (s.plant == FootPlant::Stepped || s.plant == FootPlant::Overextended) moveDelta -= tune::kStepInDistance / static_cast<float>(std::max(1, s.strikeLen));
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
  int base = strike.kind == StrikeKind::Heavy ? tune::kHeavyRecoveryTicks : strike.kind == StrikeKind::Quick ? tune::kQuickRecoveryTicks : tune::kGrabRecoveryTicks;
  switch (outcome) {
    case Outcome::Whiff:
    case Outcome::Evaded: base = RoundTicks(static_cast<float>(base) * 1.3f); break;
    case Outcome::Parried:
    case Outcome::GrabParried: base += tune::kParryRecoveryBonusTicks; break;
    case Outcome::Intercepted: base = tune::kInterceptedRecoveryTicks; break;
    default: break;
  }
  (void)ctx;
  recoveryLen = ComputeRecovery(base);
  contactResolved = true;  // the phase stays Contact until the next tick (pitch §5: Strike -> Contact -> Recovery)
}

void Fighter::HandleWeapon(const Input& in, const StepContext& ctx) {
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
      if (weaponCharge >= static_cast<float>(tune::kWeaponChargeTicks)) firePending = true;
      else weaponCharge = 0.f;
    }
  } else if (in.weaponHeld && can && phase == Phase::Idle && !guard.held) {
    weaponCharging = true;
    weaponCharge = 0.f;
    weaponTarget = in.target;
    Emit(ctx, EventType::WeaponCharging);
  }
}

void Fighter::FinishWeapon(const StepContext&) {
  weaponCharge = 0.f;
  weaponCharging = false;
  res.AddHeat(tune::kWeaponFireHeat);
  phase = Phase::Recovery;
  phaseTicks = 0;
  recoveryLen = tune::kWeaponRecoveryTicks;
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
  Emit(ctx, EventType::Dodge, Zone::Torso, dodgeDirNow);
  // pitch §6: a dodge is one heavy step; the cost lands on stability, and the mech is exposed afterwards.
  res.LoseStability(tune::kDodgeStability);
}

// ------------------------------------------------------------------------------- taking damage

void Fighter::EnterStagger(const StepContext& ctx) {
  posture = Posture::Staggered;
  postureTicks = 0;
  res.stability = tune::kStaggerHoldStability;
  if (phase != Phase::Contact) {
    phase = Phase::Idle;
    phaseTicks = 0;
  }
  if (guard.hard) Emit(ctx, EventType::HardStanceOff);
  guard = GuardState();
  weaponCharging = false;
  weaponCharge = 0.f;
  Emit(ctx, EventType::Staggered);
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
  Emit(ctx, EventType::KnockedDown);
}

void Fighter::LoseStability(float amount, const StepContext& ctx) {
  if (!res.LoseStability(amount)) return;
  if (posture == Posture::Staggered) EnterKnockdown(ctx);
  else if (posture == Posture::Standing || posture == Posture::Dodging) EnterStagger(ctx);
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
  float dmg = damage * res.DamageTakenMult();
  if (posture == Posture::Staggered) dmg *= tune::kStaggerDamageMult;
  else if (posture == Posture::KnockedDown) dmg *= tune::kKnockdownDamageMult;

  const DamageResult d = body.ApplyDamage(zone, dmg, kind);
  r.dealt = d.dealt;
  r.severed = d.severed;
  r.before = d.before;
  r.after = d.after;
  if (!d.ignored) {
    Emit(ctx, EventType::Hit, zone, 0, 0, d.dealt);
    if (d.before != d.after) Emit(ctx, EventType::ZoneState, zone, static_cast<int>(d.after), static_cast<int>(d.before));
    if (d.severed) Emit(ctx, EventType::LimbSevered, zone);
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

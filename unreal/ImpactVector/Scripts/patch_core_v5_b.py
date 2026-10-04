"""Core v5, part B: Fighter.cpp (lunge, jump, slide, overload, breakdown)."""
P = r"F:\IVRepo\core\src\Fighter.cpp"
s = open(P, encoding="utf-8").read()


def rep(a, b, cnt=1):
    global s
    assert a in s, a[:90]
    s = s.replace(a, b, cnt)


def replace_between(start, end, new):
    global s
    i = s.index(start)
    j = s.index(end, i)
    s = s[:i] + new + s[j:]


# ---- reset
rep("  ultimateLocked = false;\n  lastHitTick = -100000;", "  ultimateLocked = false;\n  airTicks = slideTicks = jumpCooldown = berserkCooldown = 0;\n  breakdown = breakdownAcc = breakdownAge = 0;\n  lastHitTick = -100000;")

# ---- reach / damage
rep("  float base = strike.kind == StrikeKind::Heavy ? tune::kHeavyReach : strike.kind == StrikeKind::Quick ? tune::kQuickReach : tune::kGrabReach;",
    """  float base = tune::kHeavyReach;
  switch (strike.kind) {
    case StrikeKind::Heavy: base = tune::kHeavyReach; break;
    case StrikeKind::Quick: base = tune::kQuickReach; break;
    case StrikeKind::Grab: base = tune::kGrabReach; break;
    case StrikeKind::Lunge: base = tune::kLungeReach; break;
    case StrikeKind::AirChop: base = tune::kAirChopReach; break;
  }""")
rep("    case StrikeKind::Grab: base = tune::kGrabDamage; break;\n  }", "    case StrikeKind::Grab: base = tune::kGrabDamage; break;\n    case StrikeKind::Lunge: base = tune::kLungeDamage; break;\n    case StrikeKind::AirChop: base = tune::kAirChopDamage; break;\n  }")

# ---- step: timers, breakdown, postures
rep("  if (stunImmune > 0) --stunImmune;\n",
    """  if (stunImmune > 0) --stunImmune;
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
""")
rep("    case Posture::Dodging:\n      if (++dodgeTicks >= tune::kDodgeEvadeTicks + tune::kDodgeStabilizeTicks) posture = Posture::Standing;\n      break;\n    default: break;",
    """    case Posture::Dodging:
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
    default: break;""")
rep("""        if (in.dodge) {
          TryDodge(in, ctx);
        }
        if (posture == Posture::Standing && phase == Phase::Idle && !weaponCharging && !in.weaponHeld && strikeLockTicks == 0) {
          if (in.quick) BeginStrike(in, StrikeKind::Quick, ctx);
          else if (in.toGrab && !in.strikeHeld) BeginStrike(in, StrikeKind::Grab, ctx);
          else if (in.strikeHeld) BeginStrike(in, StrikeKind::Heavy, ctx);
        }""",
    """        if (in.dodge) {
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
        }""")

# ---- BeginStrike
rep("""  bool ok = false;
  Arm arm = in.arm;
  if (kind == StrikeKind::Heavy) {
    arm = PickArm(in.arm, in.side, &ok);
  } else if (kind == StrikeKind::Quick) {""",
    """  bool ok = false;
  Arm arm = in.arm;
  if (kind == StrikeKind::Lunge) {
    if (res.energy < tune::kLungeEnergy) return;
    arm = PickArm(Arm::R, SwingSide::Right, &ok);
  } else if (kind == StrikeKind::Heavy) {
    arm = PickArm(in.arm, in.side, &ok);
  } else if (kind == StrikeKind::Quick) {""")
rep("""  strike.kind = kind;
  strike.side = in.side;
  strike.target = in.target;""",
    """  strike.kind = kind;
  strike.side = kind == StrikeKind::Lunge ? (IsLateralSwing(in.side) ? in.side : SwingSide::Right) : in.side;
  strike.target = kind == StrikeKind::Lunge ? Zone::Torso : in.target;""")
rep("""  if (kind == StrikeKind::Heavy) {
    const int penalty = PoseReturnPenalty(arm, in.side);""",
    """  if (kind == StrikeKind::Lunge) {
    strike.minHold = tune::kLungeChargeTicks;
    strike.commitDelay = tune::kLungeCommitTicks;
    strike.held = 1;
    Emit(ctx, EventType::LungeCharging);
  } else if (kind == StrikeKind::Heavy) {
    const int penalty = PoseReturnPenalty(arm, in.side);""")

# ---- HandleWindup (whole function)
replace_between("void Fighter::HandleWindup(const Input& in, const StepContext& ctx) {", "void Fighter::HandleStrike(const Input& in, const StepContext& ctx) {", r'''void Fighter::HandleWindup(const Input& in, const StepContext& ctx) {
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

''')

# ---- HandleStrike: the rush
rep("  if (s.plant == FootPlant::Stepped || s.plant == FootPlant::Overextended) moveDelta -= tune::kStepInDistance / static_cast<float>(std::max(1, s.strikeLen));",
    "  if (s.kind == StrikeKind::Lunge) moveDelta -= tune::kLungeRushDistance / static_cast<float>(std::max(1, s.strikeLen));\n  else if (s.plant == FootPlant::Stepped || s.plant == FootPlant::Overextended) moveDelta -= tune::kStepInDistance / static_cast<float>(std::max(1, s.strikeLen));")

# ---- FinishStrike
rep("  int base = strike.kind == StrikeKind::Heavy ? tune::kHeavyRecoveryTicks : strike.kind == StrikeKind::Quick ? tune::kQuickRecoveryTicks : tune::kGrabRecoveryTicks;",
    """  int base = tune::kHeavyRecoveryTicks;
  switch (strike.kind) {
    case StrikeKind::Heavy: base = tune::kHeavyRecoveryTicks; break;
    case StrikeKind::Quick: base = tune::kQuickRecoveryTicks; break;
    case StrikeKind::Grab: base = tune::kGrabRecoveryTicks; break;
    case StrikeKind::Lunge: base = tune::kLungeRecoveryTicks; break;
    case StrikeKind::AirChop: base = tune::kAirChopRecoveryTicks; break;
  }""")
rep("    case Outcome::Intercepted: base = tune::kInterceptedRecoveryTicks; break;\n    default: break;",
    "    case Outcome::Intercepted: base = tune::kInterceptedRecoveryTicks; break;\n    case Outcome::Jumped:\n    case Outcome::Slid: base = RoundTicks(static_cast<float>(base) * 1.5f); break;\n    default: break;")

# ---- stagger from the air
rep("  else if (posture == Posture::Standing || posture == Posture::Dodging) EnterStagger(ctx);\n}",
    "  else if (posture == Posture::Standing || posture == Posture::Dodging || posture == Posture::Airborne || posture == Posture::Sliding) EnterStagger(ctx);\n}")
rep("  if (stunImmune > 0 && (posture == Posture::Standing || posture == Posture::Dodging)) {",
    "  if (stunImmune > 0 && (posture == Posture::Standing || posture == Posture::Dodging || posture == Posture::Airborne || posture == Posture::Sliding)) {")
rep("void Fighter::EnterStagger(const StepContext& ctx) {\n  posture = Posture::Staggered;\n  postureTicks = 0;",
    "void Fighter::EnterStagger(const StepContext& ctx) {\n  posture = Posture::Staggered;\n  postureTicks = 0;\n  airTicks = slideTicks = 0;")

# ---- breakdown trigger in TakeHit
rep("      if (sys >= 0) Emit(ctx, EventType::SystemFailure, zone, sys);\n    }",
    "      if (sys >= 0) Emit(ctx, EventType::SystemFailure, zone, sys);\n      if (zone != Zone::Head) AddBreakdown(zone == Zone::Reactor || zone == Zone::Torso ? 2 : 1, ctx);\n    }")

# ---- new functions
rep("void Fighter::EnterClinch() {", r'''bool Fighter::TryJump(const StepContext& ctx) {
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

void Fighter::EnterClinch() {''')

open(P, "w", encoding="utf-8").write(s)
print("part B ok")

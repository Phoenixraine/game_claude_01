#include "iv/Duel.h"

#include <algorithm>
#include <cmath>

namespace iv {

namespace {
float Clamp(float v, float lo, float hi) { return std::max(lo, std::min(hi, v)); }
}  // namespace

Duel::Duel(uint64_t seed, bool keepEvents) : f_{Fighter(Side::A), Fighter(Side::B)}, log_(keepEvents), rng_(seed) { Reset(seed); }

void Duel::Reset(uint64_t seed) {
  f_[0].Reset();
  f_[1].Reset();
  distance_ = tune::kStartDistance;
  tick_ = 0;
  chain_ = Chain();
  clinch_ = ClinchState();
  lock_ = LockState();
  berserk_ = BerserkState();
  gpHeld_[0] = gpHeld_[1] = false;
  gpTick_[0] = gpTick_[1] = -100000;
  cinematic_ = CinematicState();
  dummy_[0].Reset();
  dummy_[1].Reset();
  result_ = MatchResult();
  log_.Clear();
  rng_.Seed(seed);
}

StepContext Duel::Ctx(int i, const World& w) const {
  StepContext c;
  c.now = tick_;
  c.distance = distance_;
  c.proximity = w.proximity[i];
  c.coolingMult = w.coolingMult[i];
  c.log = const_cast<EventLog*>(&log_);
  return c;
}

void Duel::Emit(EventType t, Side actor, Zone z, int a, int b, float v) {
  Event e;
  e.tick = tick_;
  e.type = t;
  e.actor = actor;
  e.zone = z;
  e.a = a;
  e.b = b;
  e.value = v;
  log_.Push(e);
}

void Duel::Step(const Input& a, const Input& b, const World& world) {
  if (result_.over) return;
  if (cinematic_.active) {  // v2: the fight is frozen while an external cut plays
    StepCinematic();
    ++tick_;
    if (!result_.over && timeLimit_ > 0 && tick_ >= timeLimit_) {
      result_.over = true;
      result_.draw = true;
      result_.reason = EndReason::TimeLimit;
      Emit(EventType::MatchEnd, Side::A, Zone::Torso, static_cast<int>(EndReason::TimeLimit), 1);
    }
    return;
  }
  Input dummyIn[2];
  Input autoIn[2];
  const Input* in[2] = {&a, &b};
  for (int i = 0; i < 2; ++i) {   // v4: a mech whose pilot is outside only defends; whatever the caller sends, no strike, weapon or ultimate starts
    if (f_[i].autopilot) {
      autoIn[i] = *in[i];
      autoIn[i].strikeHeld = autoIn[i].quick = autoIn[i].toGrab = autoIn[i].switchArm = autoIn[i].reverse = false;
      autoIn[i].weaponHeld = autoIn[i].ultimate = false;
      in[i] = &autoIn[i];
    }
  }
  for (int i = 0; i < 2; ++i) {
    if (dummy_[i].mode() != DummyMode::Off) {
      dummyIn[i] = dummy_[i].Next(f_[i], f_[1 - i], tick_);
      in[i] = &dummyIn[i];
    }
  }

  for (int i = 0; i < 2; ++i)   // v5: the berserk grab
    if (in[i]->berserk) TryStartBerserk(i);
  for (int i = 0; i < 2; ++i) {   // v5: raw guard presses (the berserk parry reads them)
    if (in[i]->guardHeld && (!gpHeld_[i] || in[i]->guardSide != gpSide_[i])) gpTick_[i] = tick_;
    gpHeld_[i] = in[i]->guardHeld;
    gpSide_[i] = in[i]->guardSide;
  }
  for (int i = 0; i < 2; ++i) f_[i].Step(*in[i], Ctx(i, world));
  for (int i = 0; i < 2; ++i) {   // v5: an AI mech repairs its own breakdown after a while
    if (aiLevel_[i] >= 0 && f_[i].breakdown > 0 && f_[i].breakdownAge >= tune::kBreakdownAiRepairTicks) f_[i].RepairBreakdown(1, Ctx(i, world));
  }

  distance_ = Clamp(distance_ + f_[0].moveDelta + f_[1].moveDelta, tune::kMinDistance, tune::kMaxDistance);

  // A sidestep makes the opponent turn to re-face (pitch §6 "зайти к повреждённому боку").
  for (int i = 0; i < 2; ++i) {
    if (f_[i].dodgeDirNow != 0) {
      Fighter& o = f_[1 - i];
      o.flank = Clamp(o.flank + static_cast<float>(f_[i].dodgeDirNow) * tune::kDodgeFlankDeg, -180.f, 180.f);
    }
  }

  if (lock_.active) {
    StepLock(in);
  } else if (berserk_.active) {
    StepBerserk(in);
  } else if (clinch_.active) {
    if (++clinch_.ticks >= tune::kClinchTicks) ResolveClinch(world);
  } else {
    if (chain_.active) StepChain(in, world);

    Decision d[2];
    bool has[2] = {false, false};
    for (int i = 0; i < 2; ++i) {
      if (f_[i].contactPending) {
        d[i] = Decide(i);  // both decisions are made from the pre-resolution state: simultaneous strikes trade
        has[i] = true;
      }
    }
    // v3: blades that meet on the same line stop each other (one resolution for both strikes).
    bool clashed = false;
    for (int i = 0; i < 2; ++i) {
      if (has[i] && d[i].outcome == Outcome::Clashed && !clashed) {
        ApplyClash(i, world);
        clashed = true;
      }
    }
    for (int i = 0; i < 2; ++i)
      if (has[i] && d[i].outcome != Outcome::Clashed) Apply(i, d[i], world);
    for (int i = 0; i < 2; ++i)
      if (f_[i].firePending) ResolveWeapon(i, world);
    for (int i = 0; i < 2; ++i)
      if (f_[i].ultimatePending && !cinematic_.active) ResolveUltimate(i, world);
  }

  if (!cinematic_.active) CheckEnd();
  ++tick_;
  if (!result_.over && timeLimit_ > 0 && tick_ >= timeLimit_) {
    result_.over = true;
    result_.draw = true;
    result_.reason = EndReason::TimeLimit;
    Emit(EventType::MatchEnd, Side::A, Zone::Torso, static_cast<int>(EndReason::TimeLimit), 1);
  }
}

// ----------------------------------------------------------------------------- contact outcome

Duel::Decision Duel::Decide(int ai) const {
  const Fighter& atk = f_[ai];
  const Fighter& def = f_[1 - ai];
  const StrikeState& s = atk.strike;
  Decision d;
  d.zone = s.target;
  if (d.zone == Zone::Reactor && std::fabs(def.flank) < tune::kRearAngleDeg) d.zone = Zone::Torso;  // pitch §9: only from behind
  d.raw = atk.StrikeDamage();

  if (distance_ > atk.StrikeReach()) {
    d.outcome = Outcome::Whiff;
    return d;
  }
  const bool grab = s.kind == StrikeKind::Grab;
  const bool lunge = s.kind == StrikeKind::Lunge;
  const bool chop = s.kind == StrikeKind::AirChop;
  const bool special = lunge || chop;
  // v5: the jetpack jump goes over the rush, the slide goes under the aerial chop; neither can be dodged sideways
  if (lunge && def.JumpEvading()) {
    d.outcome = Outcome::Jumped;
    return d;
  }
  if (chop && def.SlideEvading()) {
    d.outcome = Outcome::Slid;
    return d;
  }

  // v3: two blades arrive within a few ticks of each other on the same line: they clash (double block).
  if (s.kind == StrikeKind::Heavy && def.phase == Phase::Strike && def.strike.kind == StrikeKind::Heavy && !def.contactPending && !s.innerLine &&
      def.TicksToContact() <= tune::kClashWindowTicks && SameLine(s.side, def.strike.side) && distance_ <= def.StrikeReach()) {
    d.outcome = Outcome::Clashed;
    return d;
  }
  if (s.kind == StrikeKind::Heavy && def.contactPending && def.strike.kind == StrikeKind::Heavy && SameLine(s.side, def.strike.side) && distance_ <= def.StrikeReach()) {
    d.outcome = Outcome::Clashed;
    return d;
  }

  // pitch §7 "Перехват": the defender committed a strike just now, on a line that meets this one.
  if (!grab && !special && def.phase == Phase::Strike && def.strike.kind != StrikeKind::Grab && def.strike.kind != StrikeKind::Lunge && def.strike.strikeTick >= 1 &&
      def.strike.strikeTick <= tune::kInterceptWindowTicks && IsInterceptLine(s.side, def.strike.side)) {
    d.outcome = Outcome::Intercepted;
    return d;
  }
  // v3 "Уклонение": the torso turn + half step gets out of lateral slashes; chops and rising cuts follow the mech; grabs too.
  if (!grab && !special && def.Evading() && IsLateralSwing(s.side)) {
    d.outcome = Outcome::Evaded;
    return d;
  }
  const Modifiers& dm = def.body.modifiers();
  const bool defHasArm = dm.arm[0].blockStrength > 0.f || dm.arm[1].blockStrength > 0.f;
  if (lunge) {   // v5: any lateral guard stops the rush: the blades lock. A late press still counts as a parry.
    if (def.GuardReady() && !def.guard.hard && defHasArm && IsLateralSwing(def.guard.side) && tick_ - def.guard.pressTick < tune::kParryWindowTicks) {
      d.outcome = Outcome::Locked;
      d.lockKind = 1;
      return d;
    }
    if (def.HardStanceActive() && def.posture == Posture::Standing) {
      d.outcome = Outcome::Locked;
      d.lockKind = 2;
      return d;
    }
    if (def.GuardReady() && def.guard.age >= tune::kBlockRaiseTicks && IsLateralSwing(def.guard.side) && defHasArm) {
      d.outcome = Outcome::Locked;
      d.lockKind = 0;
      return d;
    }
    d.outcome = Outcome::Hit;
    return d;
  }
  // pitch §6 "Парирование": LT pressed right before contact on the right sector. Not against inner-line counters (pitch §7).
  if (def.GuardReady() && !def.guard.hard && defHasArm && !s.innerLine && tick_ - def.guard.pressTick < tune::kParryWindowTicks &&
      (grab || def.guard.side == s.side)) {
    d.outcome = grab ? Outcome::GrabParried : Outcome::Parried;
    return d;
  }
  if (def.HardStanceActive() && def.posture == Posture::Standing) {
    d.outcome = grab ? Outcome::Grabbed : Outcome::HardStanceBlocked;  // pitch §6: the hard stance is vulnerable to grabs
    return d;
  }
  if (!grab && def.GuardReady() && def.guard.age >= tune::kBlockRaiseTicks && def.guard.side == s.side && !s.innerLine && defHasArm) {
    d.outcome = Outcome::Blocked;
    return d;
  }
  d.outcome = grab ? Outcome::Grabbed : Outcome::Hit;
  return d;
}

void Duel::Apply(int ai, const Decision& d, const World& w) {
  Fighter& atk = f_[ai];
  Fighter& def = f_[1 - ai];
  const StepContext actx = Ctx(ai, w);
  const StepContext dctx = Ctx(1 - ai, w);
  const Side as = atk.side();
  const Side ds = def.side();
  const StrikeKind kind = atk.strike.kind;
  Emit(EventType::StrikeContact, as, d.zone, static_cast<int>(kind), static_cast<int>(d.outcome), d.raw);
  atk.lastOwnOutcome = d.outcome;
  atk.lastOwnTarget = d.zone;
  atk.lastOwnTick = tick_;
  def.lastIncomingOutcome = d.outcome;
  def.lastIncomingZone = d.zone;
  def.lastIncomingTick = tick_;

  switch (d.outcome) {
    case Outcome::Whiff:
      Emit(EventType::Whiff, as, d.zone);
      atk.LoseStability(tune::kWhiffStability, actx);
      break;
    case Outcome::Evaded:
      Emit(EventType::Evaded, ds, d.zone);
      atk.LoseStability(tune::kWhiffStability * 0.6f, actx);
      // v6: a dodge only saves the mech; it does NOT open a counter (the mech must finish the side-step and settle first)
      break;
    case Outcome::Parried:
    case Outcome::GrabParried:
      Emit(EventType::ParrySuccess, ds, d.zone);
      EmitHit(def, as, d.zone, HitReport(), 0.f, atk.strike.side, false, true);
      GainUltimate(1 - ai, tune::kUltGainParry, w);
      atk.LoseStability(tune::kParryStabilityHit, actx);
      def.counterTicks = tune::kCounterWindowTicks;
      def.res.Spend(tune::kParryEnergy);
      break;
    case Outcome::Intercepted: {
      Emit(EventType::InterceptSuccess, ds, d.zone);
      // The interceptor's strike carries on as an inner-line counter; the attacker's striking arm takes the clash.
      const float clash = def.StrikeDamage() * tune::kInterceptArmDamage;
      const HitReport cr = atk.TakeHit(ArmZone(atk.strike.arm), clash, StrikeKind::Quick, tune::kInterceptStabilityHit, actx);
      EmitHit(atk, ds, ArmZone(atk.strike.arm), cr, tune::kInterceptStabilityHit, def.strike.side, false, false);
      GainUltimate(1 - ai, tune::kUltGainIntercept, w);
      def.strike.innerLine = true;
      def.res.Spend(tune::kInterceptEnergy);
      chain_.active = true;
      chain_.who = as;
      chain_.depth = 0;
      chain_.windowLeft = tune::kReverseWindowTicks[0];
      break;
    }
    case Outcome::Hit: {
      const float stab = kind == StrikeKind::Quick ? tune::kQuickStabilityHit : (kind == StrikeKind::Lunge ? tune::kLungeStabilityHit : (kind == StrikeKind::AirChop ? tune::kAirChopStabilityHit : d.raw * tune::kHitStabilityFactor));
      const HitReport hr = def.TakeHit(d.zone, d.raw, kind, stab, dctx);
      EmitHit(def, as, d.zone, hr, stab, atk.strike.side, false, false);
      if (hr.dealt > 0.f) {
        GainUltimate(ai, tune::kUltGainHit + (hr.after >= ZoneState::Critical ? tune::kUltGainCriticalHit : 0.f), w);
      }
      break;
    }
    case Outcome::Blocked: {
      const ArmMods& am = def.body.modifiers().arm[Index(GuardArm(def.guard.side))];
      const float strength = std::max(0.4f, am.blockStrength * def.res.ArmsMult());
      const float through = std::min(1.f, tune::kBlockDamageMult / strength);
      Emit(EventType::Blocked, ds, d.zone, 0, 0, d.raw * through);
      const HitReport h1 = def.TakeHit(d.zone, d.raw * through, kind, 0.f, dctx);
      EmitHit(def, as, d.zone, h1, 0.f, atk.strike.side, true, false);
      const float armStab = d.raw * tune::kBlockStabilityFactor / strength;
      const HitReport h2 = def.TakeHit(GuardZone(def.guard.side), d.raw * tune::kBlockArmLoad, StrikeKind::Quick, armStab, dctx);
      EmitHit(def, as, GuardZone(def.guard.side), h2, armStab, atk.strike.side, true, false);
      break;
    }
    case Outcome::HardStanceBlocked: {
      const float mult = IsLegZone(d.zone) ? tune::kHardStanceLegDamageMult : tune::kHardStanceDamageMult;
      Emit(EventType::Blocked, ds, d.zone, 1, 0, d.raw * mult);
      const float hs = d.raw * tune::kHardStanceStabilityFactor;
      const HitReport hr = def.TakeHit(d.zone, d.raw * mult, kind, hs, dctx);
      EmitHit(def, as, d.zone, hr, hs, atk.strike.side, true, false);
      break;
    }
    case Outcome::Clashed:   // resolved by ApplyClash before Apply is reached; listed so -Werror=switch passes on gcc
      break;
    case Outcome::Jumped:
      Emit(EventType::JumpEvadedLunge, ds, d.zone, 1);
      atk.LoseStability(tune::kLungeWhiffStability, actx);
      break;
    case Outcome::Slid:
      Emit(EventType::SlideEvadedChop, ds, d.zone);
      atk.LoseStability(tune::kChopWhiffStability, actx);
      def.counterTicks = tune::kCounterWindowTicks;
      break;
    case Outcome::Locked:
      StartLock(ai, d.lockKind);
      break;
    case Outcome::Grabbed: {
      Emit(EventType::GrabHit, as, d.zone);
      atk.res.AddHeat(tune::kGrabHeat);
      // pitch §12: a destroyed limb can be torn off by a grab.
      const bool tear = IsLimbZone(d.zone) && def.body.state(d.zone) == ZoneState::Destroyed;
      const HitReport hr = def.TakeHit(d.zone, tear ? tune::kSeverMinDamage : d.raw, StrikeKind::Grab, tune::kGrabStability, dctx);
      EmitHit(def, as, d.zone, hr, tune::kGrabStability, atk.strike.side, false, false);
      if (hr.dealt > 0.f) GainUltimate(ai, tune::kUltGainHit, w);
      break;
    }
  }
  atk.FinishStrike(d.outcome, actx);
}

void Duel::ApplyClash(int first, const World& w) {
  Fighter& a = f_[first];
  Fighter& b = f_[1 - first];
  const StepContext actx = Ctx(first, w);
  const StepContext bctx = Ctx(1 - first, w);
  Emit(EventType::BladesClash, a.side(), Zone::Torso, Index(a.strike.side), Index(b.strike.side), distance_);
  Emit(EventType::StrikeContact, a.side(), Zone::Torso, static_cast<int>(a.strike.kind), static_cast<int>(Outcome::Clashed), 0.f);
  Emit(EventType::StrikeContact, b.side(), Zone::Torso, static_cast<int>(b.strike.kind), static_cast<int>(Outcome::Clashed), 0.f);
  a.lastOwnOutcome = Outcome::Clashed;
  b.lastOwnOutcome = Outcome::Clashed;
  a.lastIncomingOutcome = Outcome::Clashed;
  b.lastIncomingOutcome = Outcome::Clashed;
  a.lastOwnTick = b.lastOwnTick = a.lastIncomingTick = b.lastIncomingTick = tick_;
  a.ClashBreak(actx);
  b.ClashBreak(bctx);
  GainUltimate(first, tune::kUltGainClash, w);
  GainUltimate(1 - first, tune::kUltGainClash, w);
}

HitReport Duel::ExternalHit(Side victim, Zone zone, float damage, float stability, int source, StatusKind status, int statusTicks) {
  Fighter& v = f_[Index(victim)];
  World w;
  const StepContext vctx = Ctx(Index(victim), w);
  const HitReport hr = v.TakeHit(zone, damage, StrikeKind::Heavy, stability, vctx);
  Emit(EventType::ExternalHit, victim, zone, source, 0, hr.dealt);
  EmitHit(v, Other(victim), zone, hr, stability, SwingSide::Down, false, false);
  if (status != StatusKind::Count && statusTicks > 0) v.ApplyStatus(status, statusTicks, vctx);
  if (!cinematic_.active) CheckEnd();
  return hr;
}

void Duel::ResolveWeapon(int ai, const World& w) {
  Fighter& atk = f_[ai];
  Fighter& def = f_[1 - ai];
  const StepContext actx = Ctx(ai, w);
  const StepContext dctx = Ctx(1 - ai, w);
  const tune::WeaponProfile& wp = atk.WeaponProf();
  const WeaponKind kind = atk.weapon;
  static const Zone kSpread[] = {Zone::Torso, Zone::ShoulderL, Zone::ShoulderR, Zone::ArmL, Zone::ArmR, Zone::LegL, Zone::LegR, Zone::Head};
  const float accuracy = Clamp(atk.body.modifiers().weaponAccuracy * wp.accuracy, 0.f, 1.f);
  int hits = 0;
  for (int k = 0; k < wp.salvo; ++k) {
    bool hit = false;
    if (distance_ >= tune::kWeaponMinDistance) {
      float chance = accuracy;
      if (def.Evading()) chance = wp.salvo > 1 ? chance * tune::kWeaponEvadeHitMult : 0.f;
      hit = rng_.Chance(chance);
    }
    if (!hit) continue;
    ++hits;
    Zone z = k == 0 ? atk.weaponTarget : kSpread[rng_.Below(static_cast<uint32_t>(sizeof(kSpread) / sizeof(kSpread[0])))];
    if (z == Zone::Reactor && std::fabs(def.flank) < tune::kRearAngleDeg) z = Zone::Torso;
    float dmg = wp.damage;
    if (def.GuardReady() && def.guard.age >= tune::kBlockRaiseTicks) dmg *= wp.blockMult;
    if (def.HardStanceActive()) dmg *= tune::kHardStanceDamageMult * 2.f;
    const float stab = dmg * tune::kHitStabilityFactor * wp.stabilityFactor / 0.6f;
    const HitReport hr = def.TakeHit(z, dmg, StrikeKind::Heavy, stab, dctx);
    EmitHit(def, atk.side(), z, hr, stab, SwingSide::Up, false, false);
    if (hr.dealt > 0.f) GainUltimate(ai, tune::kUltGainHit + (hr.after >= ZoneState::Critical ? tune::kUltGainCriticalHit : 0.f), w);
  }
  if (hits > 0) {   // v3: every long-cooldown weapon also does something besides damage
    switch (kind) {
      case WeaponKind::RailSpear: def.ApplyStatus(StatusKind::StrikeLock, tune::kStrikeLockTicks, dctx); break;
      case WeaponKind::SuppressionRockets: def.ApplyStatus(StatusKind::Blind, tune::kBlindTicks, dctx); break;
      case WeaponKind::PlasmaCannon: def.ApplyStatus(StatusKind::Burn, tune::kBurnTicks, dctx); break;
      default: break;
    }
  }
  Emit(EventType::WeaponFired, atk.side(), atk.weaponTarget, hits, Index(kind));
  atk.FinishWeapon(actx);
  // v2: every heavy weapon cuts to an external camera; a hit target is left staggered afterwards.
  StartCinematic(CinematicOf(kind), atk.side(), wp.cinematicTicks, hits > 0);
}

void Duel::ResolveUltimate(int ai, const World& w) {
  Fighter& atk = f_[ai];
  Fighter& def = f_[1 - ai];
  const StepContext actx = Ctx(ai, w);
  const StepContext dctx = Ctx(1 - ai, w);
  Zone z = atk.ultimateTarget;
  if (z == Zone::Reactor && std::fabs(def.flank) < tune::kRearAngleDeg) z = Zone::Torso;
  atk.ConsumeUltimate();
  Emit(EventType::UltimateUsed, atk.side(), z);
  // v3: punch under the chest (the target reels), jump, bring the blade down on the head.
  // A weakened target is cut in half; a healthy one raises its off-hand arm and loses it (and with it the ultimate).
  const float integrity = def.body.Integrity();
  CinematicKind ck = CinematicKind::Ultimate;
  if (integrity < tune::kUltimateKillFraction) {
    Emit(EventType::UltimateFinisher, atk.side(), Zone::Torso);
    const HitReport hr = def.TakeHit(Zone::Torso, 9999.f, StrikeKind::Heavy, 0.f, dctx);
    EmitHit(def, atk.side(), Zone::Torso, hr, 0.f, SwingSide::Up, false, false);
    ck = CinematicKind::UltimateBisect;
  } else {
    const HitReport h1 = def.TakeHit(z, tune::kUltimateDamage, StrikeKind::Heavy, tune::kUltimateStabilityHit, dctx);
    EmitHit(def, atk.side(), z, h1, tune::kUltimateStabilityHit, SwingSide::Up, false, false);
    if (!def.body.severed(Zone::ArmL)) {
      def.TakeHit(Zone::ArmL, tune::kUltimateSeverDamage * 4.f, StrikeKind::Heavy, 0.f, dctx);   // destroyed...
      const HitReport h2 = def.TakeHit(Zone::ArmL, tune::kUltimateSeverDamage, StrikeKind::Heavy, 0.f, dctx);   // ...and torn off
      EmitHit(def, atk.side(), Zone::ArmL, h2, 0.f, SwingSide::Down, false, false);
    }
    def.ultimateLocked = true;
    def.ultimate = 0.f;
    Emit(EventType::UltimateSever, atk.side(), Zone::ArmL);
    ck = CinematicKind::UltimateSever;
  }
  atk.phase = Phase::Recovery;
  atk.phaseTicks = 0;
  atk.recoveryLen = tune::kHeavyRecoveryTicks;
  (void)actx;
  StartCinematic(ck, atk.side(), tune::kUltimateCinematicTicks, true);
}

void Duel::StartCinematic(CinematicKind k, Side who, int length, bool stun) {
  cinematic_.active = true;
  cinematic_.kind = k;
  cinematic_.who = who;
  cinematic_.ticks = 0;
  cinematic_.length = length;
  cinematic_.stunTarget = stun;
  Emit(EventType::CinematicBegin, who, Zone::Torso, static_cast<int>(k), length);
}

void Duel::StepCinematic() {
  if (++cinematic_.ticks < cinematic_.length) return;
  const int who = Index(cinematic_.who);
  cinematic_.active = false;
  Emit(EventType::CinematicEnd, cinematic_.who, Zone::Torso, static_cast<int>(cinematic_.kind));
  World w;
  if (cinematic_.stunTarget) f_[1 - who].ForceStagger(Ctx(1 - who, w));
  f_[who].protectedTicks = tune::kCinematicProtectTicks;
  CheckEnd();
}

void Duel::GainUltimate(int who, float amount, const World& w) { f_[who].GainUltimate(amount, Ctx(who, w)); }

void Duel::EmitHit(const Fighter& def, Side attacker, Zone zone, const HitReport& r, float stability, SwingSide dir, bool blocked, bool parried) {
  Event e;
  e.tick = tick_;
  e.type = EventType::HitEvent;
  e.actor = attacker;
  e.zone = zone;
  e.a = static_cast<int32_t>(r.layer);
  e.b = static_cast<int32_t>(def.body.state(zone));
  e.c = PackHitFlags(dir, blocked, parried);
  e.value = r.dealt;
  e.value2 = stability;
  log_.Push(e);
}

// ------------------------------------------------------------------------------- reverse chain

void Duel::StepChain(const Input* const* in, const World& w) {
  const int who = Index(chain_.who);
  if (in[who]->reverse) {
    TryReply(who, *in[who], w);
  } else if (--chain_.windowLeft <= 0) {
    chain_.active = false;  // nobody answered in time; the intercepting strike lands as usual
  }
}

void Duel::TryReply(int who, const Input& in, const World& w) {
  Fighter& r = f_[who];
  Fighter& o = f_[1 - who];
  const StepContext rctx = Ctx(who, w);
  const StepContext octx = Ctx(1 - who, w);
  const int depth = chain_.depth;  // replies already made
  const Arm arm = Other(r.lastArm);
  const float cost = tune::kReverseEnergyBase * static_cast<float>(1 + depth);  // pitch §7: more energy each time
  const bool ok = r.posture == Posture::Standing && r.body.modifiers().arm[Index(arm)].usable && r.res.Spend(cost);
  if (!ok) {
    Emit(EventType::ReverseFailed, r.side(), Zone::Torso, depth + 1);
    r.LoseStability(tune::kReverseFailStability * static_cast<float>(1 + depth), rctx);  // pitch §7: bigger penalty for a miss
    chain_.active = false;
    return;
  }
  chain_.depth = depth + 1;
  r.lastArm = arm;
  r.phase = Phase::Recovery;
  r.phaseTicks = 0;
  r.recoveryLen = tune::kQuickRecoveryTicks;

  Zone zone = in.target;
  if (zone == Zone::Reactor && std::fabs(o.flank) < tune::kRearAngleDeg) zone = Zone::Torso;
  const float dmg = tune::kReverseDamage * (1.f + tune::kReverseDepthDamageGrowth * static_cast<float>(depth)) *
                    r.body.modifiers().arm[Index(arm)].power * r.res.ArmsMult();
  if (o.phase == Phase::Strike || o.phase == Phase::Windup) o.Interrupt(tune::kInterceptedRecoveryTicks, octx);
  Emit(EventType::ReverseChain, r.side(), zone, chain_.depth);
  o.TakeHit(zone, dmg, StrikeKind::Quick, dmg * tune::kHitStabilityFactor, octx);

  if (chain_.depth >= tune::kMaxReverseReplies) {
    chain_.active = false;
    StartClinch();  // pitch §7: after the second answer the arms lock and a physical clinch begins
  } else {
    chain_.who = Other(r.side());
    chain_.windowLeft = tune::kReverseWindowTicks[std::min(chain_.depth, 1)];
  }
}

// ----------------------------------------------------------------------------------- clinch

void Duel::StartClinch() {
  for (int i = 0; i < 2; ++i) f_[i].EnterClinch();
  clinch_.active = true;
  clinch_.ticks = 0;
  distance_ = tune::kMinDistance;
  chain_.active = false;
  Emit(EventType::Clinch, Side::A);
}

void Duel::ResolveClinch(const World& w) {
  float score[2];
  for (int i = 0; i < 2; ++i) {
    const Fighter& f = f_[i];
    const Modifiers& m = f.body.modifiers();
    score[i] = tune::kClinchWStability * f.res.stability / tune::kStabilityMax +
               tune::kClinchWAngle * (1.f - std::fabs(f.flank) / 180.f) + tune::kClinchWLegs * m.stepSpeed +
               tune::kClinchWArms * 0.5f * (m.arm[0].blockStrength + m.arm[1].blockStrength) +
               tune::kClinchWMove * static_cast<float>(f.lastMove) - tune::kClinchWWall * w.proximity[i];
  }
  int winner = score[0] >= score[1] ? 0 : 1;
  if (std::fabs(score[0] - score[1]) < 1e-6f) winner = rng_.Below(2) == 0 ? 0 : 1;
  const int loser = 1 - winner;
  const float margin = std::fabs(score[0] - score[1]);

  for (int i = 0; i < 2; ++i) f_[i].LeaveClinch();
  clinch_.active = false;
  Emit(EventType::ClinchResolved, f_[winner].side(), Zone::Torso, 0, 0, margin);

  const StepContext lctx = Ctx(loser, w);
  f_[winner].res.AddHeat(tune::kClinchWinnerHeat);
  f_[loser].LoseStability(tune::kClinchLoserStability, lctx);
  // pitch §12 "прижимать к зданию": a clearly won clinch against a wall slams the loser into it.
  if (margin >= tune::kWallSlamMargin && w.proximity[loser] >= tune::kWallSlamProximity) {
    Emit(EventType::WallSlam, f_[winner].side(), Zone::Torso, 0, 0, tune::kWallSlamDamage);
    f_[loser].TakeHit(Zone::Torso, tune::kWallSlamDamage, StrikeKind::Heavy, 0.f, lctx);
  }
  for (int i = 0; i < 2; ++i) {
    f_[i].phase = Phase::Recovery;
    f_[i].phaseTicks = 0;
    f_[i].recoveryLen = tune::kQuickRecoveryTicks;
  }
}

// -------------------------------------------------------------------------------------- end

void Duel::ForceEnd(Side loser, EndReason reason) {
  if (result_.over) return;
  result_.over = true;
  result_.draw = false;
  result_.loser = loser;
  result_.reason = reason;
  Emit(EventType::MatchEnd, loser, Zone::Torso, static_cast<int>(reason), 0);
}

void Duel::CheckEnd() {
  if (result_.over) return;
  EndReason r0 = f_[0].body.CheckEnd(f_[0].res.shutdown);
  EndReason r1 = f_[1].body.CheckEnd(f_[1].res.shutdown);
  // v2: a training dummy is repaired instead of ending the lesson.
  EndReason* rr[2] = {&r0, &r1};
  for (int i = 0; i < 2; ++i) {
    if (dummy_[i].mode() != DummyMode::Off && *rr[i] != EndReason::None) {
      f_[i].body.Reset();
      f_[i].res = Resources();
      f_[i].posture = Posture::Standing;
      *rr[i] = EndReason::None;
    }
  }
  if (r0 == EndReason::None && r1 == EndReason::None) return;
  result_.over = true;
  if (r0 != EndReason::None && r1 != EndReason::None) {
    result_.draw = true;
    result_.reason = r0;
    Emit(EventType::MatchEnd, Side::A, Zone::Torso, static_cast<int>(r0), 1);
  } else {
    result_.loser = r0 != EndReason::None ? Side::A : Side::B;
    result_.reason = r0 != EndReason::None ? r0 : r1;
    Emit(EventType::MatchEnd, result_.loser, Zone::Torso, static_cast<int>(result_.reason), 0);
  }
}

}  // namespace iv

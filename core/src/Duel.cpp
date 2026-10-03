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
  const Input* in[2] = {&a, &b};

  for (int i = 0; i < 2; ++i) f_[i].Step(*in[i], Ctx(i, world));

  distance_ = Clamp(distance_ + f_[0].moveDelta + f_[1].moveDelta, tune::kMinDistance, tune::kMaxDistance);

  // A sidestep makes the opponent turn to re-face (pitch §6 "зайти к повреждённому боку").
  for (int i = 0; i < 2; ++i) {
    if (f_[i].dodgeDirNow != 0) {
      Fighter& o = f_[1 - i];
      o.flank = Clamp(o.flank + static_cast<float>(f_[i].dodgeDirNow) * tune::kDodgeFlankDeg, -180.f, 180.f);
    }
  }

  if (clinch_.active) {
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
    for (int i = 0; i < 2; ++i)
      if (has[i]) Apply(i, d[i], world);
    for (int i = 0; i < 2; ++i)
      if (f_[i].firePending) ResolveWeapon(i, world);
  }

  CheckEnd();
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

  // pitch §7 "Перехват": the defender committed a strike just now, on a line that meets this one.
  if (!grab && def.phase == Phase::Strike && def.strike.kind != StrikeKind::Grab && def.strike.strikeTick >= 1 &&
      def.strike.strikeTick <= tune::kInterceptWindowTicks && IsInterceptLine(s.side, def.strike.side)) {
    d.outcome = Outcome::Intercepted;
    return d;
  }
  // pitch §6 "Уклонение": gets out of straight strikes, but not wide swings or grabs.
  if (!grab && def.Evading() && IsLinearSwing(s.side)) {
    d.outcome = Outcome::Evaded;
    return d;
  }
  const Modifiers& dm = def.body.modifiers();
  const bool defHasArm = dm.arm[0].blockStrength > 0.f || dm.arm[1].blockStrength > 0.f;
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
      break;
    case Outcome::Parried:
    case Outcome::GrabParried:
      Emit(EventType::Parried, ds, d.zone);
      atk.LoseStability(tune::kParryStabilityHit, actx);
      def.counterTicks = tune::kCounterWindowTicks;
      def.res.Spend(tune::kParryEnergy);
      break;
    case Outcome::Intercepted: {
      Emit(EventType::Intercepted, ds, d.zone);
      // The interceptor's strike carries on as an inner-line counter; the attacker's striking arm takes the clash.
      const float clash = def.StrikeDamage() * tune::kInterceptArmDamage;
      atk.TakeHit(ArmZone(atk.strike.arm), clash, StrikeKind::Quick, tune::kInterceptStabilityHit, actx);
      def.strike.innerLine = true;
      def.res.Spend(tune::kInterceptEnergy);
      chain_.active = true;
      chain_.who = as;
      chain_.depth = 0;
      chain_.windowLeft = tune::kReverseWindowTicks[0];
      break;
    }
    case Outcome::Hit: {
      const float stab = kind == StrikeKind::Quick ? tune::kQuickStabilityHit : d.raw * tune::kHitStabilityFactor;
      def.TakeHit(d.zone, d.raw, kind, stab, dctx);
      break;
    }
    case Outcome::Blocked: {
      const ArmMods& am = def.body.modifiers().arm[Index(GuardArm(def.guard.side))];
      const float strength = std::max(0.4f, am.blockStrength * def.res.ArmsMult());
      const float through = std::min(1.f, tune::kBlockDamageMult / strength);
      Emit(EventType::Blocked, ds, d.zone, 0, 0, d.raw * through);
      def.TakeHit(d.zone, d.raw * through, kind, 0.f, dctx);
      def.TakeHit(GuardZone(def.guard.side), d.raw * tune::kBlockArmLoad, StrikeKind::Quick, d.raw * tune::kBlockStabilityFactor / strength, dctx);
      break;
    }
    case Outcome::HardStanceBlocked: {
      const float mult = IsLegZone(d.zone) ? tune::kHardStanceLegDamageMult : tune::kHardStanceDamageMult;
      Emit(EventType::Blocked, ds, d.zone, 1, 0, d.raw * mult);
      def.TakeHit(d.zone, d.raw * mult, kind, d.raw * tune::kHardStanceStabilityFactor, dctx);
      break;
    }
    case Outcome::Grabbed: {
      Emit(EventType::GrabHit, as, d.zone);
      atk.res.AddHeat(tune::kGrabHeat);
      // pitch §12: a destroyed limb can be torn off by a grab.
      const bool tear = IsLimbZone(d.zone) && def.body.state(d.zone) == ZoneState::Destroyed;
      def.TakeHit(d.zone, tear ? tune::kSeverMinDamage : d.raw, StrikeKind::Grab, tune::kGrabStability, dctx);
      break;
    }
  }
  atk.FinishStrike(d.outcome, actx);
}

void Duel::ResolveWeapon(int ai, const World& w) {
  Fighter& atk = f_[ai];
  Fighter& def = f_[1 - ai];
  const StepContext actx = Ctx(ai, w);
  const StepContext dctx = Ctx(1 - ai, w);
  bool hit = false;
  if (distance_ >= tune::kWeaponMinDistance && !def.Evading()) hit = rng_.Chance(atk.body.modifiers().weaponAccuracy);
  Emit(EventType::WeaponFired, atk.side(), atk.weaponTarget, hit ? 1 : 0);
  if (hit) {
    Zone z = atk.weaponTarget;
    if (z == Zone::Reactor && std::fabs(def.flank) < tune::kRearAngleDeg) z = Zone::Torso;
    float dmg = tune::kWeaponDamage;
    if (def.GuardReady() && def.guard.age >= tune::kBlockRaiseTicks) dmg *= tune::kWeaponBlockMult;
    if (def.HardStanceActive()) dmg *= tune::kHardStanceDamageMult * 2.f;
    def.TakeHit(z, dmg, StrikeKind::Heavy, dmg * tune::kHitStabilityFactor, dctx);
  }
  atk.FinishWeapon(actx);
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
  Emit(EventType::ReverseReply, r.side(), zone, chain_.depth);
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
  Emit(EventType::ClinchStart, Side::A);
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

void Duel::CheckEnd() {
  if (result_.over) return;
  const EndReason r0 = f_[0].body.CheckEnd(f_[0].res.shutdown);
  const EndReason r1 = f_[1].body.CheckEnd(f_[1].res.shutdown);
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

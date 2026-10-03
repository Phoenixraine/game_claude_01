#include "iv/Ai.h"

#include <algorithm>
#include <cmath>

#include "iv/Fighter.h"
#include "iv/Tuning.h"

namespace iv {

// ------------------------------------------------------------------------------ observation

namespace {

void FillZones(const Body& b, ZoneState (&out)[kZoneCount]) {
  for (int z = 0; z < kZoneCount; ++z) out[z] = b.state(static_cast<Zone>(z));
}

uint64_t Mix(uint64_t h, uint64_t v) {
  for (int i = 0; i < 8; ++i) {
    h ^= (v >> (i * 8)) & 0xffu;
    h *= 1099511628211ULL;
  }
  return h;
}

uint64_t Q(float v) { return static_cast<uint64_t>(static_cast<int64_t>(std::llround(static_cast<double>(v) * 1000.0))); }

}  // namespace

Observation MakeObservation(const Duel& duel, Side viewer) {
  const Fighter& me = duel.fighter(viewer);
  const Fighter& op = duel.fighter(Other(viewer));
  Observation o;
  o.tick = duel.tick();
  o.distance = duel.distance();
  o.chainOpen = duel.chain().active;
  o.chainMine = duel.chain().active && duel.chain().who == viewer;

  SelfView& s = o.self;
  s.posture = me.posture;
  s.phase = me.phase;
  s.stability = me.res.stability;
  s.heat = me.res.heat;
  s.energy = me.res.energy;
  FillZones(me.body, s.zones);
  s.pose[0] = me.pose[0];
  s.pose[1] = me.pose[1];
  s.priority = me.res.priority;
  s.guardHeld = me.guard.held;
  s.guardAge = me.guard.age;
  s.hardStance = me.guard.hard;
  s.counterTicks = me.counterTicks;
  s.strikeTicksLeft = me.phase == Phase::Strike ? me.TicksToContact() : -1;
  s.weaponCharging = me.weaponCharging;
  s.weaponChargeFrac = me.weaponCharge / static_cast<float>(tune::kWeaponChargeTicks);
  s.lastOwnOutcome = me.lastOwnOutcome;
  s.lastOwnTarget = me.lastOwnTarget;
  s.sinceOwn = duel.tick() - me.lastOwnTick;
  s.lastIncomingOutcome = me.lastIncomingOutcome;
  s.lastIncomingZone = me.lastIncomingZone;
  s.sinceIncoming = duel.tick() - me.lastIncomingTick;
  s.flank = me.flank;
  s.proximity = me.proximity;
  for (int a = 0; a < 2; ++a) {
    s.armUsable[a] = me.body.modifiers().arm[a].usable;
    s.allowedSides[a] = me.body.modifiers().arm[a].allowedSides;
  }
  s.canGrab = me.body.modifiers().arm[0].canGrab || me.body.modifiers().arm[1].canGrab;
  s.windupReady = me.phase == Phase::Windup && !me.strike.released && me.strike.held >= me.strike.minHold;

  // Opponent: only what is visible or audible.
  OppView& v = o.opp;
  v.posture = op.posture;
  v.phase = op.phase;
  const bool swinging = op.phase == Phase::Windup || op.phase == Phase::Strike || op.phase == Phase::Contact;
  if (swinging) {
    v.kind = op.strike.kind;
    v.side = op.strike.side;
    v.arm = op.strike.arm;
  }
  v.chargeSound = op.phase == Phase::Windup && op.strike.kind == StrikeKind::Heavy && op.strike.held >= tune::kChargeAudibleTicks;
  v.strikeTicksLeft = op.phase == Phase::Strike ? op.TicksToContact() : -1;
  v.stepping = op.phase == Phase::Strike && (op.strike.plant == FootPlant::Stepped || op.strike.plant == FootPlant::Overextended);
  v.pose[0] = op.pose[0];
  v.pose[1] = op.pose[1];
  v.priority = op.res.priority;
  v.switching = op.res.switchTicksLeft > 0;
  v.pendingPriority = op.res.pending;
  FillZones(op.body, v.zones);
  v.guardUp = op.guard.held;
  v.guardSide = op.guard.side;
  v.hardStance = op.HardStanceActive();
  v.weaponCharging = op.weaponCharging;
  v.unsteady = op.res.stability < 35.f;
  v.heatWarning = op.res.heatWarning;
  v.move = op.lastMove;
  v.flank = op.flank;
  return o;
}

uint64_t HashObservation(const Observation& o) {
  uint64_t h = 1469598103934665603ULL;
  h = Mix(h, static_cast<uint64_t>(o.tick));
  h = Mix(h, Q(o.distance));
  h = Mix(h, (o.chainOpen ? 1u : 0u) | (o.chainMine ? 2u : 0u));
  const SelfView& s = o.self;
  h = Mix(h, static_cast<uint64_t>(s.posture));
  h = Mix(h, static_cast<uint64_t>(s.phase));
  h = Mix(h, Q(s.stability));
  h = Mix(h, Q(s.heat));
  h = Mix(h, Q(s.energy));
  for (int z = 0; z < kZoneCount; ++z) h = Mix(h, static_cast<uint64_t>(s.zones[z]));
  h = Mix(h, static_cast<uint64_t>(s.priority));
  h = Mix(h, static_cast<uint64_t>(s.strikeTicksLeft + 1));
  const OppView& v = o.opp;
  h = Mix(h, static_cast<uint64_t>(v.posture));
  h = Mix(h, static_cast<uint64_t>(v.phase));
  h = Mix(h, static_cast<uint64_t>(v.kind));
  h = Mix(h, static_cast<uint64_t>(v.side));
  h = Mix(h, static_cast<uint64_t>(v.arm));
  h = Mix(h, v.chargeSound ? 1u : 0u);
  h = Mix(h, static_cast<uint64_t>(v.strikeTicksLeft + 1));
  h = Mix(h, v.stepping ? 1u : 0u);
  h = Mix(h, static_cast<uint64_t>(v.pose[0]) | (static_cast<uint64_t>(v.pose[1]) << 8));
  h = Mix(h, static_cast<uint64_t>(v.priority));
  h = Mix(h, v.switching ? 1u : 0u);
  for (int z = 0; z < kZoneCount; ++z) h = Mix(h, static_cast<uint64_t>(v.zones[z]));
  h = Mix(h, (v.guardUp ? 1u : 0u) | (v.hardStance ? 2u : 0u) | (v.weaponCharging ? 4u : 0u) | (v.unsteady ? 8u : 0u));
  h = Mix(h, static_cast<uint64_t>(v.guardSide));
  h = Mix(h, static_cast<uint64_t>(static_cast<int>(v.move) + 1));
  h = Mix(h, Q(v.flank));
  return h;
}

HabitResponse HabitMemory::Likely(HabitContext c, float* share) const {
  const int ci = static_cast<int>(c);
  int best = static_cast<int>(HabitResponse::Hold);
  int bestN = 0;
  for (int r = 0; r < kHabitResponses; ++r) {
    if (resp[ci][r] > bestN) {
      bestN = resp[ci][r];
      best = r;
    }
  }
  *share = total[ci] >= 3 ? static_cast<float>(bestN) / static_cast<float>(total[ci]) : 0.f;
  return static_cast<HabitResponse>(best);
}

// ------------------------------------------------------------------------------------- style

namespace {

struct Style {
  float aggression;   // chance per ready tick to start an attack
  float punish;       // aggression multiplier while the opponent is recovering
  float preferred;    // preferred distance
  float heavy;        // P(heavy) when attacking, else quick
  float grab;         // P(grab) when in grab reach
  float feint;        // P(feint) per heavy
  float weapon;       // P(start charging the weapon) per ready tick when far
  int cooldown;       // ticks between attacks
  int chargeMax;      // extra charge ticks
  float zoneW[kZoneCount];  // Head, Torso, Reactor, ShL, ShR, ArmL, ArmR, LegL, LegR
  float react[5];     // Block, Parry, Dodge, Intercept, HardStance
  float guardIdle;
  EnergyPriority prio;
  bool stepIn;
  float counter;
  float rush;         // P(charging in to break a weapon charge) when the opponent charges the launcher (pitch §13)
  bool kite;          // opens the distance when crowded (backing away is slow, so only a ranged style tries it)
  float flank;        // P(per ready tick) of sidestepping to the opponent's back while he recovers (pitch §6 "зайти к повреждённому боку")
};

const Style kStyles[kArchetypeCount] = {
    // Counterpuncher: waits, punishes mistakes (pitch §20).
    {0.0025f, 30.f, 22.f, 0.65f, 0.02f, 0.10f, 0.f, 80, 10, {0.10f, 0.35f, 0.05f, 0.10f, 0.10f, 0.10f, 0.10f, 0.05f, 0.05f},
     {0.35f, 0.25f, 0.05f, 0.30f, 0.f}, 0.85f, EnergyPriority::Guard, false, 0.9f, 0.4f, false, 0.f},
    // Breaker: pushes the centre and the space (pitch §20 "Разрушитель").
    {0.013f, 3.f, 18.f, 0.85f, 0.03f, 0.05f, 0.f, 45, 25, {0.10f, 0.50f, 0.10f, 0.08f, 0.08f, 0.04f, 0.04f, 0.03f, 0.03f},
     {0.55f, 0.10f, 0.10f, 0.10f, 0.15f}, 0.35f, EnergyPriority::Arms, true, 0.4f, 0.9f, false, 0.f},
    // LimbHunter: arms and legs first (pitch §20 "Охотник за конечностями").
    {0.012f, 3.f, 20.f, 0.55f, 0.04f, 0.12f, 0.f, 50, 15, {0.05f, 0.14f, 0.02f, 0.13f, 0.13f, 0.17f, 0.17f, 0.09f, 0.09f},
     {0.40f, 0.20f, 0.25f, 0.15f, 0.f}, 0.5f, EnergyPriority::Arms, false, 0.5f, 0.7f, false, 0.004f},
    // Trickster: feints and delays (pitch §20 "Обманщик").
    {0.016f, 3.f, 20.f, 0.50f, 0.08f, 0.55f, 0.f, 40, 15, {0.12f, 0.25f, 0.05f, 0.12f, 0.12f, 0.12f, 0.12f, 0.05f, 0.05f},
     {0.30f, 0.15f, 0.35f, 0.20f, 0.f}, 0.4f, EnergyPriority::Legs, false, 0.6f, 0.6f, false, 0.012f},
    // Gunner: keeps the range and prepares the weapon (pitch §20 "Стрелок").
    {0.010f, 3.f, 70.f, 0.50f, 0.f, 0.05f, 0.03f, 60, 10, {0.10f, 0.35f, 0.05f, 0.10f, 0.10f, 0.10f, 0.10f, 0.05f, 0.05f},
     {0.50f, 0.10f, 0.35f, 0.05f, 0.f}, 0.4f, EnergyPriority::Weapon, false, 0.3f, 0.3f, true, 0.f},
    // Grappler: closes the gap and looks for the grab (pitch §20 "Борец").
    {0.014f, 3.f, 10.f, 0.45f, 0.30f, 0.15f, 0.f, 45, 15, {0.05f, 0.30f, 0.05f, 0.08f, 0.08f, 0.14f, 0.14f, 0.08f, 0.08f},
     {0.30f, 0.10f, 0.05f, 0.15f, 0.40f}, 0.5f, EnergyPriority::Legs, true, 0.5f, 0.9f, false, 0.004f},
};

SwingSide SideFromIndex(int i) { return static_cast<SwingSide>(i); }

bool NaturalPair(SwingSide s, Zone z) { return ((tune::kNaturalTargets[Index(s)] >> Index(z)) & 1u) != 0; }

}  // namespace

// --------------------------------------------------------------------------------------- Ai

Ai::Ai(Archetype archetype, Difficulty difficulty, uint64_t seed)
    : archetype_(archetype),
      difficulty_(difficulty),
      rng_(seed, 0x9e3779b97f4a7c15ULL + static_cast<uint64_t>(archetype) * 7919u + static_cast<uint64_t>(difficulty)),
      delay_(std::max(tune::kMinReactionTicks, tune::kReactionTicks[static_cast<int>(difficulty)])) {}

SwingSide Ai::PredictOppSide() {
  const float depth = tune::kAnalysisDepth[static_cast<int>(difficulty_)];
  const int last = Index(lastOppSide_);
  if (memory_.comboTotal[last] >= 2 && Roll() < depth) {
    int best = 0;
    for (int i = 1; i < 4; ++i)
      if (memory_.combo[last][i] > memory_.combo[last][best]) best = i;
    return SideFromIndex(best);
  }
  return SideFromIndex(static_cast<int>(rng_.Below(4)));
}

void Ai::UpdateMemory(const Observation& cur, const Observation& old) {
  const OppView& seen = old.opp;
  const float quality = tune::kAnalysisDepth[static_cast<int>(difficulty_)];
  (void)quality;

  // New event of my own that the opponent may answer in a habitual way.
  const SelfView& s = cur.self;
  const Tick ownTick = cur.tick - s.sinceOwn;
  if (ownTick != lastOwnSeen_ && s.sinceOwn < 5) {
    lastOwnSeen_ = ownTick;
    bool start = true;
    HabitContext ctx = HabitContext::AfterBlocked;
    if (s.lastOwnOutcome == Outcome::Blocked || s.lastOwnOutcome == Outcome::HardStanceBlocked) ctx = HabitContext::AfterBlocked;
    else if (s.lastOwnOutcome == Outcome::Whiff || s.lastOwnOutcome == Outcome::Evaded) ctx = HabitContext::AfterMissed;
    else if (s.lastOwnOutcome == Outcome::Hit && IsLegZone(s.lastOwnTarget)) ctx = HabitContext::AfterLegHit;
    else start = false;
    if (start && !watching_) {
      watching_ = true;
      watchCtx_ = ctx;
      watchStart_ = cur.tick;
    }
  }
  if (seen.unsteady && !prevUnsteady_ && !watching_) {
    watching_ = true;
    watchCtx_ = HabitContext::WhenUnsteady;
    watchStart_ = cur.tick;
  }
  prevUnsteady_ = seen.unsteady;

  if (watching_ && old.tick >= watchStart_) {
    int resp = -1;
    if (seen.phase == Phase::Windup || seen.phase == Phase::Strike) resp = static_cast<int>(seen.kind == StrikeKind::Quick ? HabitResponse::QuickStrike : HabitResponse::HeavyStrike);
    else if (seen.hardStance) resp = static_cast<int>(HabitResponse::HardStance);
    else if (seen.guardUp) resp = static_cast<int>(HabitResponse::Guard);
    else if (seen.move < 0) resp = static_cast<int>(HabitResponse::Retreat);
    else if (seen.move > 0) resp = static_cast<int>(HabitResponse::Advance);
    if (resp < 0 && cur.tick - watchStart_ > 90 + delay_) resp = static_cast<int>(HabitResponse::Hold);
    if (resp >= 0) {
      ++memory_.resp[static_cast<int>(watchCtx_)][resp];
      ++memory_.total[static_cast<int>(watchCtx_)];
      watching_ = false;
    }
  }
}

void Ai::ChooseReaction(const OppView& seen, const SelfView& self) {
  const Style& st = kStyles[static_cast<int>(archetype_)];
  float w[5];
  for (int i = 0; i < 5; ++i) w[i] = st.react[i];
  const bool linear = IsLinearSwing(seen.side);
  if (!linear) w[2] = 0.f;                                  // a dodge does not beat wide swings (pitch §6)
  if (self.stability > 60.f) w[4] *= 0.3f;                  // hard stance is for when the mech is in trouble
  if (self.stability < 35.f) w[4] = w[4] * 3.f + 0.2f;
  if (self.energy < 25.f) { w[3] = 0.f; w[4] = 0.f; }
  // Easy pilots stick to the plain block; harder ones mix in the timing-based answers.
  const float skill = tune::kAnalysisDepth[static_cast<int>(difficulty_)];
  w[1] *= 0.3f + 0.6f * skill;
  w[3] *= 0.2f + 0.6f * skill;
  w[2] *= 0.4f + 0.6f * skill;
  float sum = 0.f;
  for (int i = 0; i < 5; ++i) sum += w[i];
  float r = Roll() * sum;
  int pick = 0;
  for (int i = 0; i < 5; ++i) {
    if (r < w[i]) { pick = i; break; }
    r -= w[i];
    pick = i;
  }
  static const Reaction kMap[5] = {Reaction::Block, Reaction::Parry, Reaction::Dodge, Reaction::Intercept, Reaction::HardStance};
  reaction_ = sum <= 0.f ? Reaction::Block : kMap[pick];
}

bool Ai::Defend(const OppView& seen, const Observation& cur, Input* in) {
  const SelfView& self = cur.self;
  const bool threat = (seen.phase == Phase::Windup || seen.phase == Phase::Strike) && seen.posture == Posture::Standing;
  if (!threat) {
    oppAttacking_ = false;
    parryPressed_ = false;
    reacted_ = false;
    grabAnswered_ = false;
    reaction_ = Reaction::None;
    return false;
  }
  if (!oppAttacking_) {
    oppAttacking_ = true;
    parryPressed_ = false;
    reacted_ = false;
    // Combo memory: which swing family tends to follow which (pitch §8).
    if (cur.tick - lastOppSideTick_ < 240) {
      ++memory_.combo[Index(lastOppSide_)][Index(seen.side)];
      ++memory_.comboTotal[Index(lastOppSide_)];
    }
    lastOppSide_ = seen.side;
    lastOppSideTick_ = cur.tick;
    ChooseReaction(seen, self);
    const float j = tune::kParryTimingJitter[static_cast<int>(difficulty_)];
    parryJitter_ = static_cast<int>(std::lround((Roll() * 2.f - 1.f) * j));
    // A free windup can still be dropped when the opponent obviously started first.
    if (script_.active && self.phase == Phase::Windup && Roll() < 0.8f * tune::kPositionQuality[static_cast<int>(difficulty_)]) {
      in->cancel = true;
      script_.active = false;
      cooldown_ += 20;
    }
  }
  if (self.phase != Phase::Idle && self.phase != Phase::Recovery) return false;  // busy: nothing to do now

  // A grab is a slow, visible reach (pitch §12): hit the grabbing arm before it closes, a block does not help.
  if (seen.kind == StrikeKind::Grab && (seen.phase == Phase::Windup || seen.phase == Phase::Strike)) {
    const float skill = tune::kAnalysisDepth[static_cast<int>(difficulty_)];
    if (!reacted_) {
      reacted_ = true;
      grabAnswer_ = Roll() < 0.15f + 0.45f * skill;
    }
    if (grabAnswer_ && !grabAnswered_ && cur.distance <= tune::kQuickReach) {
      in->quick = true;
      in->side = SwingSide::Up;
      in->target = Zone::Torso;
      in->arm = Roll() < 0.5f ? Arm::L : Arm::R;
      if (!self.armUsable[Index(in->arm)]) in->arm = Other(in->arm);
      grabAnswered_ = true;
    }
    return true;
  }
  const int eta = seen.strikeTicksLeft >= 0 ? seen.strikeTicksLeft - delay_ : -1;  // observation is `delay_` ticks old
  const bool etaKnown = seen.strikeTicksLeft >= 0;
  in->guardSide = seen.side;
  switch (reaction_) {
    case Reaction::Block:
    case Reaction::None:
      in->guardHeld = true;
      return true;
    case Reaction::HardStance:
      in->guardHeld = true;
      in->hardStance = true;
      return true;
    case Reaction::Parry: {
      const int pressAt = (tune::kParryWindowTicks - 1) / 2 + parryJitter_;
      if (etaKnown && eta <= pressAt) parryPressed_ = true;
      if (etaKnown && eta < -2) parryPressed_ = true;  // too late for timing: at least raise the guard
      in->guardHeld = parryPressed_;
      return true;
    }
    case Reaction::Dodge:
      if (etaKnown && !reacted_ && eta <= tune::kDodgeEvadeTicks / 2 + parryJitter_ && eta >= -3) {
        in->dodge = true;
        in->dodgeDir = Roll() < 0.5f ? -1 : 1;
        reacted_ = true;
      } else if (!etaKnown || eta > 0) {
        in->guardHeld = false;
      }
      return true;
    case Reaction::Intercept: {
      const int pressAt = tune::kQuickWindupTicks + 1 + tune::kInterceptWindowTicks / 2 + parryJitter_;
      if (etaKnown && !reacted_ && eta <= pressAt && eta >= 3) {
        const uint8_t lines = tune::kInterceptLines[Index(seen.side)];
        SwingSide pick = seen.side;
        for (int i = 0; i < 4; ++i)
          if ((lines >> i) & 1u) { pick = SideFromIndex(i); break; }
        in->quick = true;
        in->side = pick;
        in->target = Zone::Torso;
        in->arm = Roll() < 0.5f ? Arm::L : Arm::R;
        if (!self.armUsable[Index(in->arm)]) in->arm = Other(in->arm);
        reacted_ = true;
        reverseFrom_ = cur.tick + 1 + tune::kQuickWindupTicks + 3;
        reverseUntil_ = reverseFrom_ + tune::kReverseWindowTicks[1] + 4;
      } else if (etaKnown && !reacted_ && eta < 3) {
        in->guardHeld = true;  // missed the chance: fall back to a late guard
      }
      return true;
    }
  }
  return true;
}

Zone Ai::PickTarget(const OppView& seen, const SelfView& self) {
  const Style& st = kStyles[static_cast<int>(archetype_)];
  (void)self;
  float w[kZoneCount];
  for (int z = 0; z < kZoneCount; ++z) {
    w[z] = st.zoneW[z];
    const ZoneState zs = seen.zones[z];
    if (zs == ZoneState::Severed) w[z] = 0.f;
    // pitch §12: a destroyed limb is worth tearing off.
    if (zs == ZoneState::Destroyed && IsLimbZone(static_cast<Zone>(z))) w[z] += 0.8f;
    // pitch §9: finish what is already open.
    if (zs >= ZoneState::Exposed && zs < ZoneState::Destroyed) w[z] *= 1.25f;
    if (zs == ZoneState::Destroyed && !IsLimbZone(static_cast<Zone>(z))) w[z] *= 0.2f;
  }
  w[Index(Zone::Reactor)] = std::fabs(seen.flank) >= tune::kRearAngleDeg ? w[Index(Zone::Reactor)] + 1.5f : 0.f;
  float sum = 0.f;
  for (int z = 0; z < kZoneCount; ++z) sum += w[z];
  if (sum <= 0.f) return Zone::Torso;
  float r = Roll() * sum;
  for (int z = 0; z < kZoneCount; ++z) {
    if (r < w[z]) return static_cast<Zone>(z);
    r -= w[z];
  }
  return Zone::Torso;
}

void Ai::PickStrike(const Observation& cur, const OppView& seen) {
  const Style& st = kStyles[static_cast<int>(archetype_)];
  const SelfView& self = cur.self;
  const float quality = tune::kPositionQuality[static_cast<int>(difficulty_)];
  script_ = Script();
  script_.active = true;
  script_.target = PickTarget(seen, self);

  // Arm: a usable one whose pose does not force a return, if possible.
  Arm arm = Roll() < 0.5f ? Arm::L : Arm::R;
  if (!self.armUsable[Index(arm)]) arm = Other(arm);
  script_.arm = arm;

  // Side: allowed by the arm, natural for the target, and reachable from the current pose.
  float w[4];
  float sum = 0.f;
  for (int i = 0; i < 4; ++i) {
    const SwingSide sd = SideFromIndex(i);
    float x = ((self.allowedSides[Index(arm)] >> i) & 1u) ? 1.f : 0.f;
    x *= NaturalPair(sd, script_.target) ? 1.f : 0.25f;
    const bool poseOk = ((tune::kPoseAllowed[static_cast<int>(self.pose[Index(arm)])] >> i) & 1u) != 0;
    x *= poseOk ? 1.f : (1.f - 0.85f * quality);  // pitch §5.4: a good pilot reads his own arm pose
    w[i] = x;
    sum += x;
  }
  if (sum <= 0.f) {
    const Arm other = Other(arm);
    if (self.armUsable[Index(other)]) {
      script_.arm = other;
      for (int i = 0; i < 4; ++i) w[i] = ((self.allowedSides[Index(other)] >> i) & 1u) ? 1.f : 0.f, sum += w[i];
    }
  }
  if (sum <= 0.f) {
    script_.active = false;
    return;
  }
  float r = Roll() * sum;
  int side = 0;
  for (int i = 0; i < 4; ++i) {
    if (r < w[i]) { side = i; break; }
    r -= w[i];
    side = i;
  }
  script_.side = SideFromIndex(side);

  const float stepRange = tune::kHeavyReach + tune::kStepInReachBonus;
  if (st.stepIn && cur.distance > tune::kHeavyReach - 4.f && cur.distance <= stepRange && self.stability >= tune::kStepInMinStability + 10.f) script_.foot = Footwork::StepIn;
  else if (Roll() < 0.12f) script_.foot = Footwork::Turn;
  else if (Roll() < 0.08f) script_.foot = Footwork::StepBack;
  else script_.foot = Footwork::Hold;
  script_.holdLeft = static_cast<int>(rng_.Below(static_cast<uint32_t>(st.chargeMax) + 1u));
}

void Ai::Offend(const Observation& cur, const OppView& seen, Input* in) {
  const Style& st = kStyles[static_cast<int>(archetype_)];
  const SelfView& self = cur.self;
  const float depth = tune::kAnalysisDepth[static_cast<int>(difficulty_)];

  // ---- a strike is being wound up: keep driving it ----
  if (script_.active) {
    if (self.phase == Phase::Windup) {
      in->strikeHeld = true;
      in->side = script_.side;
      in->target = script_.target;
      in->arm = script_.arm;
      in->footwork = script_.foot;
      if (!script_.feintDone && self.windupReady && Roll() < st.feint * 0.05f) {
        // pitch §8: change the target, turn into a grab, or switch the side before the commit point.
        const float r = Roll();
        if (r < 0.5f) script_.target = PickTarget(seen, self);
        else if (r < 0.75f && self.canGrab) in->toGrab = true;
        else script_.side = SideFromIndex(static_cast<int>(rng_.Below(4)));
        in->target = script_.target;
        in->side = script_.side;
        script_.feintDone = true;
      }
      if (self.windupReady) {
        if (script_.holdLeft > 0) --script_.holdLeft;
        else in->strikeHeld = false;  // release: commit
      }
      return;
    }
    if (self.phase == Phase::Idle && script_.tick == 0) {
      // first tick: start the windup
    }
    if (self.phase != Phase::Idle) {
      script_.active = false;  // the strike left the windup (or was broken)
      cooldown_ = st.cooldown + static_cast<int>(rng_.Below(static_cast<uint32_t>(st.cooldown / 2 + 1)));
      if (self.phase == Phase::Strike) {
        reverseFrom_ = cur.tick + std::max(0, self.strikeTicksLeft);
        reverseUntil_ = reverseFrom_ + tune::kReverseWindowTicks[0];
      }
      return;
    }
    in->strikeHeld = true;
    in->side = script_.side;
    in->target = script_.target;
    in->arm = script_.arm;
    in->footwork = script_.foot;
    ++script_.tick;
    return;
  }

  if (self.phase != Phase::Idle) return;
  const float reach = tune::kHeavyReach + (st.stepIn ? tune::kStepInReachBonus : 0.f) - 4.f;

  // ---- counter window after a parry (pitch §6): the inner-line counter is the Counterpuncher's bread and butter ----
  if (self.counterTicks > 0 && cur.distance <= reach) {
    const float p = std::min(1.f, st.counter * tune::kCounterChance[static_cast<int>(difficulty_)] * 1.6f + 0.1f);
    if (Roll() < p) {
      if (Roll() < 0.6f) {
        PickStrike(cur, seen);
        if (script_.active) {
          in->strikeHeld = true;
          in->side = script_.side;
          in->target = script_.target;
          in->arm = script_.arm;
          in->footwork = script_.foot;
        }
      } else {
        in->quick = true;
        in->target = PickTarget(seen, self);
        in->side = SideFromIndex(static_cast<int>(rng_.Below(4)));
        in->arm = Roll() < 0.5f ? Arm::L : Arm::R;
        if (!self.armUsable[Index(in->arm)]) in->arm = Other(in->arm);
        cooldown_ = std::max(12, st.cooldown / 3);
      }
      return;
    }
  }
  if (cooldown_ > 0) return;

  // ---- weapon (pitch §13) ----
  if (st.weapon > 0.f) {
    const bool oppThreat = seen.phase == Phase::Windup || seen.phase == Phase::Strike;
    if (self.weaponCharging) {
      in->weaponHeld = true;
      in->target = Zone::Torso;
      if (oppThreat && cur.distance < tune::kHeavyReach + 10.f) in->weaponHeld = false;  // abort: the enemy is on me
      else if (self.weaponChargeFrac >= 1.f) {
        in->weaponHeld = false;  // release: fire
        in->target = PickTarget(seen, self);
      }
      return;
    }
    if (!oppThreat && cur.distance >= tune::kWeaponMinDistance + 4.f && self.armUsable[1] && self.zones[Index(Zone::ShoulderR)] < ZoneState::Destroyed && Roll() < st.weapon) {
      in->weaponHeld = true;
      in->target = Zone::Torso;
      return;
    }
  }

  // ---- melee ----
  float chance = st.aggression;
  if (seen.posture == Posture::Staggered || seen.posture == Posture::KnockedDown) chance *= 8.f;
  else if (seen.phase == Phase::Recovery) chance *= st.punish;
  else if (seen.phase == Phase::Windup || seen.phase == Phase::Strike) chance = 0.f;
  if (chase_ > 0) chance = std::max(chance, 0.25f);
  if (self.stability < 25.f) chance *= 0.3f;
  // The opponent's back is open (pitch §9): take the quick shot at the reactor while the angle lasts.
  const bool rear = std::fabs(seen.flank) >= tune::kRearAngleDeg;
  if (rear && cur.distance <= tune::kQuickReach - 2.f && Roll() < 0.35f + 0.5f * depth) {
    in->quick = true;
    in->target = Zone::Reactor;
    in->side = SideFromIndex(static_cast<int>(rng_.Below(4)));
    in->arm = Roll() < 0.5f ? Arm::L : Arm::R;
    if (!self.armUsable[Index(in->arm)]) in->arm = Other(in->arm);
    cooldown_ = std::max(8, st.cooldown / 4);
    return;
  }
  // A long quiet spell makes every style restless, so stalemates end (pitch §26 "Combat Lab" pacing).
  const int quiet = std::min(self.sinceOwn, self.sinceIncoming);
  if (quiet > 600) chance *= 1.f + std::min(3.f, static_cast<float>(quiet - 600) / 400.f);
  if (cur.distance > reach || Roll() >= chance) return;

  // Habit-based exploitation (pitch §8 "Поведенческое чтение").
  float share = 0.f;
  bool useGrab = false;
  if (seen.unsteady && Roll() < depth) {
    const HabitResponse r = memory_.Likely(HabitContext::WhenUnsteady, &share);
    if (r == HabitResponse::HardStance && share >= 0.5f) useGrab = true;  // hard stance is open to grabs
  }
  if (seen.hardStance && self.canGrab) useGrab = true;
  const bool grabbing = (useGrab || Roll() < st.grab) && cur.distance <= tune::kGrabReach + 2.f && self.canGrab;
  if (grabbing) {
    in->toGrab = true;
    in->target = PickTarget(seen, self);
    in->arm = Roll() < 0.5f ? Arm::L : Arm::R;
    cooldown_ = st.cooldown;
    return;
  }
  if (Roll() < st.heavy && chase_ == 0) {
    PickStrike(cur, seen);
    if (script_.active) {
      in->strikeHeld = true;
      in->side = script_.side;
      in->target = script_.target;
      in->arm = script_.arm;
      in->footwork = script_.foot;
    }
  } else {
    in->quick = true;
    in->target = PickTarget(seen, self);
    in->side = SideFromIndex(static_cast<int>(rng_.Below(4)));
    in->arm = Roll() < 0.5f ? Arm::L : Arm::R;
    if (!self.armUsable[Index(in->arm)]) in->arm = Other(in->arm);
    cooldown_ = std::max(12, st.cooldown / 3);
  }
}

Input Ai::Decide(const Observation& cur) {
  Input in;
  const Style& st = kStyles[static_cast<int>(archetype_)];
  const int di = static_cast<int>(difficulty_);
  history_.push_back(cur);
  if (static_cast<int>(history_.size()) > delay_ + 1) history_.erase(history_.begin());
  const Observation& old = history_.front();  // pitch §20: the opponent as it was `delay_` ticks ago
  const OppView& seen = old.opp;
  const SelfView& self = cur.self;

  if (cooldown_ > 0) --cooldown_;
  if (chase_ > 0) --chase_;
  if (priorityCooldown_ > 0) --priorityCooldown_;
  UpdateMemory(cur, old);

  if (self.posture != Posture::Standing) {
    in.move = (archetype_ == Archetype::Breaker || archetype_ == Archetype::Grappler) ? 1 : -1;  // clinch push (pitch §7)
    script_.active = false;
    return in;
  }

  // Energy distribution (pitch §10): follow the style, fall back to Guard when the mech is shaking.
  EnergyPriority want = st.prio;
  if (self.stability < 30.f) want = EnergyPriority::Guard;
  if (want != self.priority && priorityCooldown_ == 0 && !(archetype_ == Archetype::Gunner && self.weaponCharging)) {
    in.setPriority = true;
    in.priority = want;
    priorityCooldown_ = 200;
  }

  // Anticipated reverse presses (pitch §7): timed from the AI's own strike, never from the opponent's input.
  if (reverseFrom_ >= 0 && cur.tick >= reverseFrom_ && cur.tick <= reverseUntil_) {
    const float p = std::min(1.f, st.counter * tune::kCounterChance[di] * 0.45f);
    if (Roll() < p) {
      in.reverse = true;
      in.target = Zone::Torso;
    }
  }
  if (reverseUntil_ >= 0 && cur.tick > reverseUntil_) reverseFrom_ = reverseUntil_ = -1;

  // The opponent charges its weapon (pitch §13): break the charge up close, or sidestep the shot on its known timing.
  if (seen.weaponCharging) {
    if (!weaponSeen_) {
      weaponSeen_ = true;
      weaponSeenTick_ = old.tick;
      weaponDodged_ = false;
      rushing_ = Roll() < st.rush * (0.3f + 0.7f * tune::kAnalysisDepth[di]);
      weaponJitter_ = static_cast<int>(std::lround((Roll() * 2.f - 1.f) * tune::kParryTimingJitter[di]));
    }
    if (rushing_) {
      chase_ = std::max(chase_, 15);
    } else if (!weaponDodged_ && (self.phase == Phase::Idle || self.phase == Phase::Recovery)) {
      const float mult = seen.priority == EnergyPriority::Weapon ? tune::kPrioWeaponCharge : 1.f;
      const Tick fireAt = weaponSeenTick_ + static_cast<Tick>(static_cast<float>(tune::kWeaponChargeTicks) / mult);
      if (cur.tick >= fireAt - tune::kDodgeEvadeTicks / 2 + weaponJitter_) {
        in.dodge = true;
        in.dodgeDir = Roll() < 0.5f ? -1 : 1;
        weaponDodged_ = true;
      }
    }
  } else {
    weaponSeen_ = false;
    rushing_ = false;
  }

  const bool defending = Defend(seen, cur, &in);
  if (!defending) {
    // Neutral: keep a guard up against the quick strikes that cannot be reacted to (pitch §20).
    if (guardRethink_ > 0) --guardRethink_;
    if (guardRethink_ == 0) {
      guardRethink_ = 40 + static_cast<int>(rng_.Below(30));
      guardIdle_ = Roll() < st.guardIdle;
      guardSide_ = PredictOppSide();
    }
    const bool near = cur.distance < tune::kHeavyReach + tune::kStepInReachBonus + 12.f;
    if (guardIdle_ && near && !script_.active && (self.phase == Phase::Idle || self.phase == Phase::Recovery) && !self.weaponCharging) {
      in.guardHeld = true;
      in.guardSide = guardSide_;
    }
    // After a blocked strike a reader chases a habitual retreat (pitch §8).
    if (self.sinceOwn < 4 && (self.lastOwnOutcome == Outcome::Blocked) && Roll() < tune::kAnalysisDepth[di]) {
      float share = 0.f;
      if (memory_.Likely(HabitContext::AfterBlocked, &share) == HabitResponse::Retreat && share >= 0.5f) chase_ = 40;
    }
    // After a miss, expect the counter: guard up on the predicted side.
    if (self.sinceOwn < 4 && (self.lastOwnOutcome == Outcome::Whiff || self.lastOwnOutcome == Outcome::Evaded)) {
      float share = 0.f;
      const HabitResponse r = memory_.Likely(HabitContext::AfterMissed, &share);
      if (r == HabitResponse::QuickStrike && share >= 0.4f && Roll() < tune::kAnalysisDepth[di]) {
        guardIdle_ = true;
        guardRethink_ = 50;
      }
    }
    // Circle to the opponent's back while he recovers (pitch §6, §9): the turned mech exposes its rear zone for a while.
    if (st.flank > 0.f && self.phase == Phase::Idle && !script_.active && (seen.phase == Phase::Recovery || seen.posture != Posture::Standing) &&
        cur.distance <= tune::kHeavyReach + 6.f && std::fabs(seen.flank) < tune::kRearAngleDeg &&
        Roll() < st.flank * (0.5f + tune::kAnalysisDepth[di])) {
      in.dodge = true;
      in.dodgeDir = Roll() < 0.5f ? -1 : 1;
    }
    // Do not drop the guard in the middle of nothing if I am about to swing: Offend decides.
    const bool wasGuard = in.guardHeld;
    Offend(cur, seen, &in);
    if (in.strikeHeld || in.quick || in.toGrab || in.weaponHeld) {
      if (!in.weaponHeld || self.weaponCharging) in.guardHeld = false;
      if (in.strikeHeld || in.quick || in.toGrab) in.guardHeld = false;
    } else {
      in.guardHeld = wasGuard;
    }
  }

  // ---- movement: keep the preferred distance (pitch §11) ----
  // Hysteresis: start closing / opening only outside the tolerance band, but run all the way to the
  // preferred distance. Stopping at the band edge would park melee styles just outside their own reach.
  if (!script_.active && !self.weaponCharging && !in.hardStance) {
    float pref = st.preferred;
    // The band must end inside the style's own strike reach, otherwise both pilots park just out of range.
    const float styleReach = tune::kHeavyReach + (st.stepIn ? tune::kStepInReachBonus : 0.f) - 4.f;
    const float tol = std::max(1.f, std::min(3.f + (1.f - tune::kPositionQuality[di]) * 6.f, styleReach - pref - 1.f));
    if (seen.phase == Phase::Recovery || seen.posture != Posture::Standing) pref -= 4.f;  // close in on a recovering enemy
    if (chase_ > 0) pref = 10.f;
    if (cur.distance > pref + tol) moving_ = 1;
    else if (cur.distance < pref - tol) moving_ = st.kite && cur.distance > styleReach - 4.f ? -1 : 0;
    else if ((moving_ > 0 && cur.distance <= pref) || (moving_ < 0 && cur.distance >= pref)) moving_ = 0;
    in.move = static_cast<int8_t>(moving_);
    // Dodging stands still: the sidestep is the movement (pitch §6).
    if (defending && reaction_ == Reaction::Dodge) in.move = 0;
  }
  return in;
}

}  // namespace iv

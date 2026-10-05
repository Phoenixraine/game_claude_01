#include "iv/Boarding.h"

#include <algorithm>
#include <cmath>

namespace iv {

namespace {
bool Gone(ZoneState s) { return s >= ZoneState::Destroyed; }
int ShoulderIdx(Arm a) { return Index(a); }
}  // namespace

const char* Name(BoardPhase p) {
  static const char* const kNames[] = {"Idle", "ClimbOut", "OnShoulder", "HookLaunch", "HookFlight", "Landing", "Hacking", "GrenadeThrow",
                                       "Escape", "WatchBlast", "ReturnHook", "ClimbIn", "Smashed", "Done", "HookSwing", "Stunned"};
  return kNames[static_cast<int>(p)];
}

const char* Name(BoardingDenied d) {
  static const char* const kNames[] = {"None", "AlreadyActive", "MatchOver", "Clinch", "Busy", "Stunned", "Cinematic", "Cooldown", "NoEnergy", "NoStability", "NoTarget", "AiDisabled"};
  return kNames[static_cast<int>(d)];
}

Boarding::Boarding(const BoardingConfig& cfg) : cfg_(cfg), rng_(cfg.seed, 0x424f415244ULL), auto_(Archetype::Counterpuncher, Difficulty::Easy, cfg.seed ^ 0x9e3779b97f4a7c15ULL) { Reset(cfg.seed); }

void Boarding::Reset(uint64_t seed) {
  cfg_.seed = seed;
  rng_.Seed(seed, 0x424f415244ULL);
  auto_ = Ai(Archetype::Counterpuncher, Difficulty::Easy, seed ^ 0x9e3779b97f4a7c15ULL);
  phase_ = BoardPhase::Idle;
  phaseTick_ = phaseLen_ = 0;
  shoulder_ = Arm::R;
  cooldown_ = 0;
  lastDenied_ = BoardingDenied::None;
  outcome_ = BoardingOutcome::None;
  hack_ = HackGame();
  swat_ = Swat();
  swatsDone_ = swatCooldown_ = swatCheck_ = sinceLanding_ = shocks_ = 0;
  lastHit_ = -100000;
  lastProgressSent_ = 0.f;
  quality_ = 0.f;
  blastDone_ = false;
  resume_ = BoardPhase::Landing;
  ghostTicks_ = -1;
}

void Boarding::Emit(Duel& d, EventType t, int a, int b, float v, Zone z) {
  Event e;
  e.tick = d.tick();
  e.type = t;
  e.actor = cfg_.owner;
  e.zone = z;
  e.a = a;
  e.b = b;
  e.value = v;
  d.log().Push(e);
}

void Boarding::Enter(Duel& d, BoardPhase p, int len) {
  phase_ = p;
  phaseTick_ = 0;
  phaseLen_ = len;
  Emit(d, EventType::BoardingPhase, static_cast<int>(p), len);
}

bool Boarding::UsableShoulder(const Duel& d, Arm a) const { return !Gone(d.fighter(Other(cfg_.owner)).body.state(ShoulderZone(a))); }

float Boarding::GrenadeDamage(float quality) {
  const float q = std::max(0.f, std::min(1.f, quality));
  return std::min(tune::kGrenadeDamageMax, tune::kGrenadeDamageMin + (tune::kGrenadeDamageMax - tune::kGrenadeDamageMin) * q);
}

Zone Boarding::BlastZone(const Duel& d, Side enemy, Arm shoulder) {
  const Fighter& e = d.fighter(enemy);
  return Gone(e.body.state(ShoulderZone(shoulder))) ? ArmZone(shoulder) : ShoulderZone(shoulder);
}

// ------------------------------------------------------------------------------------------------ autopilot

Input Boarding::Filter(const Duel& duel, const Input& playerInput) {
  if (!Active()) return playerInput;
  if (phase_ == BoardPhase::Stunned) return Input();   // v6: the pilot lies on the shoulder: the mech is dead weight
  Input in = auto_.Decide(MakeObservation(duel, cfg_.owner));
  in.strikeHeld = in.quick = in.toGrab = in.switchArm = in.reverse = false;   // the empty mech only defends
  in.weaponHeld = in.ultimate = false;
  return in;
}

// ------------------------------------------------------------------------------------------------ start

BoardingDenied Boarding::CanStart(const Duel& d, const BoardingInput& in, Arm* chosen) const {
  if (Active()) return BoardingDenied::AlreadyActive;
  if (cfg_.ownerIsAi && !tune::kAiBoardingEnabled) return BoardingDenied::AiDisabled;
  if (d.result().over) return BoardingDenied::MatchOver;
  if (d.cinematic().active) return BoardingDenied::Cinematic;
  const Fighter& me = d.fighter(cfg_.owner);
  if (d.clinch().active || me.posture == Posture::Clinched) return BoardingDenied::Clinch;
  if (me.phase != Phase::Idle || me.weaponCharging || me.ultimatePending) return BoardingDenied::Busy;
  if (me.posture != Posture::Standing) return BoardingDenied::Stunned;
  if (cooldown_ > 0) return BoardingDenied::Cooldown;
  if (me.res.energy < tune::kBoardEnergyCost) return BoardingDenied::NoEnergy;
  if (me.res.stability < tune::kBoardMinStability) return BoardingDenied::NoStability;
  const Arm pick = UsableShoulder(d, in.shoulder) ? in.shoulder : Other(in.shoulder);
  if (!UsableShoulder(d, pick)) return BoardingDenied::NoTarget;
  *chosen = pick;
  return BoardingDenied::None;
}

void Boarding::Begin(Duel& d, Arm shoulder) {
  Fighter& me = d.fighter(cfg_.owner);
  me.res.Spend(tune::kBoardEnergyCost);
  me.set_autopilot(true);
  shoulder_ = shoulder;
  outcome_ = BoardingOutcome::None;
  hack_ = HackGame();
  swat_ = Swat();
  swatsDone_ = 0;
  swatCooldown_ = 0;
  swatCheck_ = 0;
  sinceLanding_ = 0;
  shocks_ = 0;
  lastHit_ = me.lastHitTick;
  lastProgressSent_ = 0.f;
  quality_ = 0.f;
  blastDone_ = false;
  ghostTicks_ = -1;
  Emit(d, EventType::BoardingStarted, ShoulderIdx(shoulder));
  Enter(d, BoardPhase::ClimbOut, tune::kBoardClimbOutTicks);
}

void Boarding::Finish(Duel& d, BoardingOutcome o) {
  d.fighter(cfg_.owner).set_autopilot(false);
  outcome_ = o;
  swat_ = Swat();
  ghostTicks_ = -1;
  cooldown_ = (o == BoardingOutcome::HackFailed || o == BoardingOutcome::HackTimeout) ? tune::kBoardCooldownFailTicks : tune::kBoardCooldownTicks;
  Emit(d, EventType::BoardingEnded, static_cast<int>(o));
  phase_ = o == BoardingOutcome::Smashed ? BoardPhase::Smashed : BoardPhase::Done;
  phaseTick_ = 0;
  phaseLen_ = 0;
}

// v6: the caught pilot lies stunned on the shoulder; the empty mech is helpless for kBoardStunTicks, then he returns along the hook.
void Boarding::Slap(Duel& d) {
  Emit(d, EventType::BoardingSmashed, ShoulderIdx(shoulder_), 1);   // b = 1: non-lethal
  swat_ = Swat();
  ghostTicks_ = -1;
  hack_ = HackGame();
  outcome_ = BoardingOutcome::Slapped;
  Enter(d, BoardPhase::Stunned, tune::kBoardStunTicks);
}

void Boarding::Smash(Duel& d) {
  Emit(d, EventType::BoardingSmashed, ShoulderIdx(shoulder_));
  Finish(d, BoardingOutcome::Smashed);
  d.ForceEnd(cfg_.owner, EndReason::PilotLost);
}

// ------------------------------------------------------------------------------------------------ the enemy hand

bool Boarding::SwatEligible() const {
  switch (phase_) {
    case BoardPhase::HookFlight: return phaseLen_ > 0 && phaseTick_ * 10 >= phaseLen_ * 7;   // the last 30 % of the flight
    case BoardPhase::Landing: return sinceLanding_ >= tune::kSwatGraceTicks;
    case BoardPhase::Hacking: return sinceLanding_ >= tune::kSwatGraceTicks;
    default: return false;
  }
}

void Boarding::DoSwing(Duel& d, bool early) {
  const Arm other = Other(shoulder_);
  float kept = 0.f;
  resume_ = phase_ == BoardPhase::Hacking ? BoardPhase::Hacking : BoardPhase::Landing;
  if (phase_ == BoardPhase::Hacking) {
    hack_.Reroll(tune::kSwingKeepProgress);
    kept = hack_.progress();
    lastProgressSent_ = kept;
  }
  shoulder_ = other;
  Emit(d, EventType::BoardingSwingOk, ShoulderIdx(shoulder_), 0, kept);
  Enter(d, BoardPhase::HookSwing, tune::kBoardHookSwingTicks);
  if (early) {
    // The press came before the window opened: the hook flies, the enemy hand follows once (the telegraph restarts on the new shoulder).
    ++swat_.adjusted;
    swat_.shoulder = shoulder_;
    swat_.ticksToImpact = tune::kBoardHookSwingTicks + swat_.total;
    Emit(d, EventType::BoardingSwatAdjusted, ShoulderIdx(shoulder_), swat_.ticksToImpact);
  } else {
    ghostTicks_ = std::max(1, swat_.ticksToImpact);   // the cancelled swat still comes down on the shoulder the pilot just left
    ghostShoulder_ = Other(shoulder_);
    swat_.active = false;
  }
}

void Boarding::ForcedSwing(Duel& d) {
  // The shoulder under the pilot was destroyed: the hook pulls him to the other one (same cost as a swing, no swat bookkeeping).
  const bool wasActive = swat_.active;
  const Swat keep = swat_;
  DoSwing(d, false);
  ghostTicks_ = -1;
  swat_ = wasActive ? keep : Swat();
  if (swat_.active) swat_.shoulder = shoulder_;
}

void Boarding::StepSwat(Duel& d, const BoardingInput& in) {
  const Side enemy = Other(cfg_.owner);
  const Fighter& foe = d.fighter(enemy);
  if (ghostTicks_ >= 0 && --ghostTicks_ < 0) Emit(d, EventType::BoardingSwatImpact, 0, ShoulderIdx(ghostShoulder_));
  if (swatCooldown_ > 0) --swatCooldown_;

  if (!swat_.active && cfg_.enemyIsHuman) {
    if (!in.swat || swatsDone_ >= tune::kHumanMaxSwats || swatCooldown_ > 0 || !SwatEligible()) return;
    if (foe.posture != Posture::Standing || Gone(foe.body.state(ArmZone(Other(shoulder_))))) return;
    swat_.active = true;
    swat_.shoulder = shoulder_;
    swat_.total = tune::kHumanSwatWindupTicks;
    swat_.ticksToImpact = swat_.total;
    swat_.adjusted = 0;
    ++swatsDone_;
    Emit(d, EventType::BoardingSwatTelegraph, ShoulderIdx(shoulder_), swat_.ticksToImpact, static_cast<float>(swatsDone_ - 1));
    return;
  }
  if (!swat_.active) {
    if (swatsDone_ >= tune::kMaxSwatsPerBoarding || swatCooldown_ > 0 || !SwatEligible()) return;
    if (++swatCheck_ < tune::kSwatCheckTicks) return;
    swatCheck_ = 0;
    const int di = static_cast<int>(cfg_.enemyDifficulty);
    const float p = tune::kSwatChance[di] * tune::kSwatArchetypeMult[static_cast<int>(cfg_.enemyArchetype)] * cfg_.swatChanceMult;
    if (!rng_.Chance(p)) return;
    // The enemy slaps the shoulder with the opposite hand: no arm, no swat.
    if (foe.posture != Posture::Standing || Gone(foe.body.state(ArmZone(Other(shoulder_))))) return;
    swat_.active = true;
    swat_.shoulder = shoulder_;
    swat_.total = tune::kSwatWindupTicks[di];
    swat_.ticksToImpact = swat_.total;
    swat_.adjusted = 0;
    ++swatsDone_;
    Emit(d, EventType::BoardingSwatTelegraph, ShoulderIdx(shoulder_), swat_.ticksToImpact, static_cast<float>(swatsDone_ - 1));
    return;
  }

  // A swing press: only inside the window, and only while the pilot is hanging on a shoulder (not mid-swing).
  if (in.swing && phase_ != BoardPhase::HookSwing) {
    const int elapsed = swat_.total - swat_.ticksToImpact;
    if (elapsed >= tune::kSwatReadyTicks && swat_.ticksToImpact >= tune::kSwingMinTicks) {
      const bool canSwing = UsableShoulder(d, Other(shoulder_));
      if (swat_.ticksToImpact <= tune::kSwingWindowTicks) {
        if (canSwing) {
          DoSwing(d, false);
          swatCooldown_ = tune::kSwatCooldownTicks;
        } else {
          // No other shoulder to leap to: the same button pulls the pilot back along the grapple (the hack is lost, he lives).
          ghostTicks_ = std::max(1, swat_.ticksToImpact);
          ghostShoulder_ = shoulder_;
          swat_.active = false;
          swatCooldown_ = tune::kSwatCooldownTicks;
          if (phase_ == BoardPhase::Hacking) Emit(d, EventType::HackResultEvt, static_cast<int>(HackState::Fail), 0, 0.f);
          AbortToReturn(d, HackState::Fail);
        }
        return;
      }
      if (canSwing && swat_.adjusted < tune::kMaxSwatAdjust) {
        DoSwing(d, true);
        return;
      }
    }
  }

  if (--swat_.ticksToImpact > 0) return;
  const bool airborne = phase_ == BoardPhase::HookSwing;
  const bool onIt = !airborne && swat_.shoulder == shoulder_ && (phase_ == BoardPhase::HookFlight || phase_ == BoardPhase::Landing || phase_ == BoardPhase::Hacking);
  Emit(d, EventType::BoardingSwatImpact, onIt ? 1 : 0, ShoulderIdx(swat_.shoulder));
  swat_.active = false;
  swatCooldown_ = tune::kSwatCooldownTicks;
  if (onIt) {
    if (cfg_.lethalSwat) Smash(d);
    else Slap(d);
  }
}

// ------------------------------------------------------------------------------------------------ hacking

void Boarding::BeginHack(Duel& d) {
  const Fighter& foe = d.fighter(Other(cfg_.owner));
  HackConfig hc;
  hc.difficulty = HackGame::DifficultyFor(cfg_.enemyArchetype, cfg_.enemyDifficulty, foe.body.state(ShoulderZone(shoulder_)));
  hc.seed = (static_cast<uint64_t>(rng_.Next()) << 32) | rng_.Next();
  hack_.Start(hc);
  lastProgressSent_ = 0.f;
  Enter(d, BoardPhase::Hacking, 0);
  Emit(d, EventType::HackStarted, hc.difficulty, hack_.timeLimit());
}

void Boarding::StepHack(Duel& d, const BoardingInput& in) {
  hack_.Step(in.hack);
  if (hack_.progress() - lastProgressSent_ >= 0.05f || hack_.progress() < lastProgressSent_) {
    lastProgressSent_ = hack_.progress();
    Emit(d, EventType::HackProgress, 0, 0, lastProgressSent_);
  }
  if (hack_.running()) return;
  quality_ = hack_.quality();
  Emit(d, EventType::HackResultEvt, static_cast<int>(hack_.state()), 0, quality_);
  swat_ = Swat();
  ghostTicks_ = -1;
  if (hack_.state() == HackState::Success) {
    outcome_ = BoardingOutcome::Success;
    Enter(d, BoardPhase::GrenadeThrow, tune::kBoardGrenadeThrowTicks);
    Emit(d, EventType::GrenadeThrown, ShoulderIdx(shoulder_));
  } else {
    AbortToReturn(d, hack_.state());
  }
}

void Boarding::AbortToReturn(Duel& d, HackState why) {
  Fighter& me = d.fighter(cfg_.owner);
  me.res.energy = std::max(0.f, me.res.energy - tune::kBoardPenaltyEnergy);
  outcome_ = why == HackState::Timeout ? BoardingOutcome::HackTimeout : BoardingOutcome::HackFailed;
  swat_ = Swat();
  ghostTicks_ = -1;
  Enter(d, BoardPhase::ReturnHook, tune::kBoardReturnHookTicks);
}

void Boarding::CheckShoulder(Duel& d) {
  if (UsableShoulder(d, shoulder_)) return;
  const bool otherOk = UsableShoulder(d, Other(shoulder_));
  switch (phase_) {
    case BoardPhase::ClimbOut:
    case BoardPhase::OnShoulder:
    case BoardPhase::HookLaunch:
      if (otherOk) shoulder_ = Other(shoulder_);
      else AbortToReturn(d, HackState::Fail);
      break;
    case BoardPhase::HookFlight:
    case BoardPhase::Landing:
    case BoardPhase::Hacking:
      if (otherOk) {
        ForcedSwing(d);
      } else {
        if (phase_ == BoardPhase::Hacking) Emit(d, EventType::HackResultEvt, static_cast<int>(HackState::Fail), 0, 0.f);
        AbortToReturn(d, HackState::Fail);
      }
      break;
    default: break;   // swinging, stunned, or the hatch is already open and the grenade is on its way: nothing to retarget
  }
}

// ------------------------------------------------------------------------------------------------ the tick

void Boarding::Step(Duel& d, const BoardingInput& in) {
  if (d.cinematic().active) return;   // the fight is frozen by an external cut: so is the boarding
  if (cooldown_ > 0) --cooldown_;

  if (!Active()) {
    if (in.start) {
      Arm chosen = Arm::R;
      const BoardingDenied why = CanStart(d, in, &chosen);
      lastDenied_ = why;
      if (why == BoardingDenied::None) Begin(d, chosen);
      else Emit(d, EventType::BoardingDenied, static_cast<int>(why));
    }
    return;
  }

  if (d.result().over) {   // the match ended while the pilot was outside
    Finish(d, BoardingOutcome::Aborted);
    return;
  }

  Fighter& me = d.fighter(cfg_.owner);
  me.set_autopilot(true);
  if (me.lastHitTick != lastHit_) {   // the empty mech was hit: the pilot is shaken
    lastHit_ = me.lastHitTick;
    if (shocks_ < tune::kBoardMaxShocks && phase_ != BoardPhase::Stunned) {
      ++shocks_;
      const int lost = static_cast<int>(tune::kBoardShockSeconds * static_cast<float>(kTickHz));
      if (phase_ == BoardPhase::Hacking) hack_.AddPenalty(lost);
      else if (phaseLen_ > 0) phaseLen_ += lost;
      Emit(d, EventType::BoardingShock, shocks_, 0, static_cast<float>(lost));
    }
  }

  CheckShoulder(d);
  if (!Active()) return;
  StepSwat(d, in);
  if (!Active()) return;

  ++phaseTick_;
  const bool done = phaseLen_ > 0 && phaseTick_ >= phaseLen_;
  switch (phase_) {
    case BoardPhase::ClimbOut:
      if (done) Enter(d, BoardPhase::OnShoulder, tune::kBoardOnShoulderTicks);
      break;
    case BoardPhase::OnShoulder:
      if (done) {
        Enter(d, BoardPhase::HookLaunch, tune::kBoardHookLaunchTicks);
        Emit(d, EventType::HookFired, ShoulderIdx(shoulder_));
      }
      break;
    case BoardPhase::HookLaunch:
      if (done) Enter(d, BoardPhase::HookFlight, tune::kBoardHookFlightTicks);
      break;
    case BoardPhase::HookFlight:
      if (done) {
        sinceLanding_ = 0;
        Emit(d, EventType::HookLanded, ShoulderIdx(shoulder_));
        Enter(d, BoardPhase::Landing, tune::kBoardLandingTicks);
      }
      break;
    case BoardPhase::Landing:
      ++sinceLanding_;
      if (done) BeginHack(d);
      break;
    case BoardPhase::HookSwing:
      if (phase_ == BoardPhase::HookSwing && done) {
        if (resume_ == BoardPhase::Hacking) Enter(d, BoardPhase::Hacking, 0);
        else {
          sinceLanding_ = 0;
          Emit(d, EventType::HookLanded, ShoulderIdx(shoulder_));
          Enter(d, BoardPhase::Landing, tune::kBoardLandingTicks);
        }
      }
      break;
    case BoardPhase::Hacking:
      ++sinceLanding_;
      StepHack(d, in);
      break;
    case BoardPhase::GrenadeThrow:
      if (done) Enter(d, BoardPhase::Escape, tune::kBoardEscapeTicks);
      break;
    case BoardPhase::Escape:
      if (done) {
        Enter(d, BoardPhase::WatchBlast, tune::kBoardWatchBlastTicks);
        blastDone_ = false;
      }
      break;
    case BoardPhase::WatchBlast:
      if (!blastDone_ && phaseTick_ >= tune::kBoardBlastDelayTicks) {
        blastDone_ = true;
        const Side enemy = Other(cfg_.owner);
        const Zone z = BlastZone(d, enemy, shoulder_);
        const HitReport hr = d.ExternalHit(enemy, z, GrenadeDamage(quality_), tune::kGrenadeStability, tune::kGrenadeSource, StatusKind::Burn, tune::kGrenadeBurnTicks);
        Emit(d, EventType::BoardingBlast, 0, 0, hr.dealt, z);
      }
      if (done) Enter(d, BoardPhase::ClimbIn, tune::kBoardClimbInTicks);
      break;
    case BoardPhase::Stunned:
      if (done) Enter(d, BoardPhase::ReturnHook, tune::kBoardReturnHookTicks);
      break;
    case BoardPhase::ReturnHook:
      if (done) Enter(d, BoardPhase::ClimbIn, tune::kBoardClimbInTicks);
      break;
    case BoardPhase::ClimbIn:
      if (done) Finish(d, outcome_);
      break;
    default: break;
  }
}

uint64_t Boarding::Hash() const {
  uint64_t h = 1469598103934665603ULL;
  auto mix = [&h](uint64_t v) {
    for (int i = 0; i < 8; ++i) {
      h ^= (v >> (i * 8)) & 0xffu;
      h *= 1099511628211ULL;
    }
  };
  mix(static_cast<uint64_t>(phase_));
  mix(static_cast<uint64_t>(phaseTick_));
  mix(static_cast<uint64_t>(phaseLen_));
  mix(static_cast<uint64_t>(shoulder_));
  mix(static_cast<uint64_t>(static_cast<uint32_t>(cooldown_)));
  mix(static_cast<uint64_t>(outcome_));
  mix(swat_.active ? 1u : 0u);
  mix(static_cast<uint64_t>(static_cast<uint32_t>(swat_.ticksToImpact)));
  mix(static_cast<uint64_t>(static_cast<uint32_t>(swatsDone_)));
  mix(static_cast<uint64_t>(static_cast<uint32_t>(shocks_)));
  mix(static_cast<uint64_t>(std::llround(static_cast<double>(quality_) * 100000.0)));
  mix(hack_.Hash());
  mix(rng_.state());
  return h;
}

}  // namespace iv

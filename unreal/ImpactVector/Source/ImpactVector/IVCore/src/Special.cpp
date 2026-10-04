// v5: sword lock (a blocked lunge), berserk (grab + timing presses + parries) and breakdown repair.
// The jump / slide / lunge themselves live in Fighter.cpp; Duel.cpp only dispatches here.
#include <algorithm>
#include <cmath>

#include "iv/Duel.h"

namespace iv {

namespace {
float ClampF(float v, float lo, float hi) { return std::max(lo, std::min(hi, v)); }
}  // namespace

// ----------------------------------------------------------------------------------- sword lock

void Duel::StartLock(int ai, int kind) {
  lock_ = LockState();
  lock_.active = true;
  lock_.attacker = f_[ai].side();
  lock_.kind = kind;
  lock_.score[1 - ai] = kind == 1 ? tune::kLockBonusParry : (kind == 2 ? tune::kLockBonusHard : tune::kLockBonusBlock);
  for (int i = 0; i < 2; ++i) f_[i].EnterClinch();
  distance_ = tune::kMinDistance + 2.f;
  chain_.active = false;
  Emit(EventType::LockStarted, f_[ai].side(), Zone::Torso, kind);
}

void Duel::StepLock(const Input* const* in) {
  ++lock_.ticks;
  distance_ = tune::kMinDistance + 2.f;
  for (int i = 0; i < 2; ++i) {
    bool press = in[i]->mash;
    if (aiLevel_[i] >= 0) press = rng_.Chance(tune::kLockAiMashPerTick[std::min(aiLevel_[i], kDifficultyCount - 1)]);
    if (press) lock_.score[i] += 1.f;
  }
  const float lead = std::fabs(lock_.score[0] - lock_.score[1]);
  if ((lock_.ticks >= tune::kLockMinTicks && lead >= tune::kLockLead) || lock_.ticks >= tune::kLockTicks) ResolveLock();
}

void Duel::ResolveLock() {
  const float margin = std::fabs(lock_.score[0] - lock_.score[1]);
  int winner = lock_.score[0] >= lock_.score[1] ? 0 : 1;
  if (margin < 0.5f) winner = Index(lock_.attacker);   // a dead heat goes to the one who rushed
  const int loser = 1 - winner;
  World w;
  const float landslide = ClampF(margin / tune::kLockLead, 0.f, 1.f);
  const StepContext lctx = Ctx(loser, w);
  const bool big = landslide >= 0.99f;
  Emit(EventType::LockResolved, f_[winner].side(), Zone::Torso, big ? 1 : 0, 0, margin);
  lock_.active = false;
  for (int i = 0; i < 2; ++i) {
    f_[i].LeaveClinch();
    f_[i].contactResolved = false;
    f_[i].contactPending = false;
    f_[i].phase = Phase::Recovery;
    f_[i].phaseTicks = 0;
    f_[i].recoveryLen = tune::kQuickRecoveryTicks;
  }
  if (margin < 0.5f) {   // nobody won: the blades fly apart
    f_[0].LoseStability(tune::kClashStability, Ctx(0, w));
    f_[1].LoseStability(tune::kClashStability, Ctx(1, w));
    return;
  }
  const float dmg = tune::kLockWinDamage * (0.65f + 0.35f * landslide);
  const HitReport hr = f_[loser].TakeHit(Zone::Torso, dmg, StrikeKind::Heavy, tune::kLockWinStability * (0.6f + 0.4f * landslide), lctx);
  EmitHit(f_[loser], f_[winner].side(), Zone::Torso, hr, tune::kLockWinStability, SwingSide::Right, false, false);
  const HitReport ar = f_[loser].TakeHit(ArmZone(Arm::R), tune::kLockArmDamage * (0.6f + 0.4f * landslide), StrikeKind::Quick, 0.f, lctx);
  EmitHit(f_[loser], f_[winner].side(), ArmZone(Arm::R), ar, 0.f, SwingSide::Right, false, false);
  GainUltimate(winner, tune::kUltGainHit * 2.f, w);
  f_[winner].recoveryLen = 6;
  if (!cinematic_.active) CheckEnd();
}

// ------------------------------------------------------------------------------------ berserk

bool Duel::TryStartBerserk(int who) {
  Fighter& f = f_[who];
  Fighter& o = f_[1 - who];
  if (berserk_.active || lock_.active || clinch_.active || cinematic_.active || result_.over) return false;
  if (f.berserkCooldown > 0 || f.autopilot || o.autopilot || f.ultimatePending) return false;
  if (f.posture != Posture::Standing || (f.phase != Phase::Idle && f.phase != Phase::Recovery)) return false;
  if (o.posture == Posture::Overloaded || o.posture == Posture::ShutDown || o.posture == Posture::Airborne) return false;
  if (f.res.energy < tune::kBerserkMinEnergy || f.res.stability < tune::kBerserkMinStability || distance_ > tune::kBerserkRange) return false;
  if (!f.body.modifiers().arm[Index(Arm::R)].usable) return false;
  f.res.Spend(tune::kBerserkMinEnergy);
  f.EnterClinch();
  o.EnterClinch();
  f.protectedTicks = tune::kBerserkMaxTicks + 600;
  distance_ = tune::kMinDistance;
  chain_.active = false;
  berserk_ = BerserkState();
  berserk_.active = true;
  berserk_.who = f.side();
  Emit(EventType::BerserkStarted, f.side());
  BerserkPrompt();
  return true;
}

void Duel::BerserkPrompt() {
  berserk_.stage = BerserkStage::Prompt;
  berserk_.stageTicks = 0;
  Emit(EventType::BerserkPrompt, berserk_.who, Zone::Torso, berserk_.round, tune::kBerserkPerfectTick);
}

void Duel::StepBerserk(const Input* const* in) {
  BerserkState& b = berserk_;
  ++b.ticks;
  distance_ = tune::kMinDistance;
  const int wi = Index(b.who);
  const int di = 1 - wi;
  Fighter& atk = f_[wi];
  Fighter& def = f_[di];
  const int level = std::min(std::max(aiLevel_[di], 0), kDifficultyCount - 1);
  if (b.ticks > tune::kBerserkMaxTicks) {
    EndBerserk(true, 1);
    return;
  }
  ++b.stageTicks;
  if (b.stage == BerserkStage::Prompt) {
    bool press = in[wi]->qte;
    SwingSide side = in[wi]->side;
    if (aiLevel_[wi] >= 0) {   // a computer-driven berserker presses near the perfect moment
      press = b.stageTicks == tune::kBerserkPerfectTick + static_cast<int>(rng_.Below(9)) - 4;
      side = static_cast<SwingSide>(rng_.Below(4));
    }
    if (press) {
      const int delta = b.stageTicks - tune::kBerserkPerfectTick;
      if (std::abs(delta) <= tune::kBerserkPressWindowTicks) {
        b.quality = 1.f - static_cast<float>(std::abs(delta)) / static_cast<float>(tune::kBerserkPressWindowTicks);
        b.side = side;
        b.stage = BerserkStage::Swing;
        b.stageTicks = 0;
        b.swingStart = tick_;
        Emit(EventType::BerserkSwing, atk.side(), Zone::Torso, b.round, Index(b.side), b.quality);
        Emit(EventType::BerserkParryPrompt, def.side(), Zone::Torso, Index(b.side), tune::kBerserkSwingTicks);
        return;
      }
      // too early: ignored, the ring is still closing
    }
    if (b.stageTicks > tune::kBerserkPerfectTick + tune::kBerserkPressWindowTicks) EndBerserk(true, 0);
    return;
  }
  // swing in flight: the foe must parry on the right side, and not earlier than the blow could be read
  if (b.stageTicks < tune::kBerserkSwingTicks) return;
  bool parried;
  if (aiLevel_[di] >= 0) {
    parried = rng_.Chance(tune::kBerserkAiParry[level] * (1.f - 0.04f * static_cast<float>(b.round)));
  } else {
    parried = gpHeld_[di] && gpSide_[di] == b.side && gpTick_[di] >= b.swingStart - tune::kBerserkParryLeadTicks &&
              gpTick_[di] <= b.swingStart + tune::kBerserkParryWindowTicks;
  }
  World w;
  if (parried) {
    def.res.Spend(tune::kBerserkParryEnergy);
    Emit(EventType::BerserkParried, def.side(), Zone::Torso, b.round);
    GainUltimate(di, tune::kUltGainParry, w);
    ++b.round;
    if (b.round >= tune::kBerserkRounds) {
      EndBerserk(true, 2);
      return;
    }
    BerserkPrompt();
    return;
  }
  // a missed parry: the piercing blow
  const StepContext dctx = Ctx(di, w);
  def.protectedTicks = 0;
  def.LeaveClinch();   // standing again, so the blow staggers it
  const float dmg = tune::kPierceDamage * (0.8f + 0.4f * b.quality);
  const HitReport hr = def.TakeHit(Zone::Torso, dmg, StrikeKind::Heavy, tune::kPierceStability, dctx);
  def.LoseStability(tune::kPierceStability, dctx);   // stagger -> knockdown
  EmitHit(def, atk.side(), Zone::Torso, hr, tune::kPierceStability, b.side, false, false);
  Emit(EventType::BerserkPierce, atk.side(), Zone::Torso, 0, Index(b.side), hr.dealt);
  GainUltimate(wi, tune::kUltGainHit * 3.f, w);
  EndBerserk(false, 0);
}

void Duel::EndBerserk(bool overload, int reason) {
  BerserkState b = berserk_;
  berserk_.active = false;
  const int wi = Index(b.who);
  const int di = 1 - wi;
  Fighter& atk = f_[wi];
  Fighter& def = f_[di];
  World w;
  atk.protectedTicks = 0;
  atk.berserkCooldown = tune::kBerserkCooldownTicks;
  def.LeaveClinch();
  atk.LeaveClinch();
  for (int i = 0; i < 2; ++i) {
    f_[i].contactPending = false;
    f_[i].contactResolved = false;
    f_[i].phase = Phase::Recovery;
    f_[i].phaseTicks = 0;
    f_[i].recoveryLen = tune::kQuickRecoveryTicks;
  }
  if (!overload) {
    Emit(EventType::BerserkEnded, atk.side(), Zone::Torso, 0);
    if (!cinematic_.active) CheckEnd();
    return;
  }
  Emit(EventType::BerserkOverload, atk.side(), Zone::Torso, reason);
  // the foe answers with a mighty counter blow; the berserker is left without power
  const StepContext actx = Ctx(wi, w);
  const HitReport hr = atk.TakeHit(Zone::Torso, tune::kCounterPunchDamage, StrikeKind::Heavy, tune::kCounterPunchStability, actx);
  EmitHit(atk, def.side(), Zone::Torso, hr, tune::kCounterPunchStability, SwingSide::Right, false, false);
  Emit(EventType::CounterPunch, def.side(), Zone::Torso, reason, 0, hr.dealt);
  atk.EnterOverload(actx);
  Emit(EventType::BerserkEnded, atk.side(), Zone::Torso, 1);
  if (!cinematic_.active) CheckEnd();
}

void Duel::RepairBreakdown(Side s, int levels) {
  World w;
  f_[Index(s)].RepairBreakdown(levels, Ctx(Index(s), w));
}

}  // namespace iv

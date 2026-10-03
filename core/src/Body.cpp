#include "iv/Body.h"

#include <algorithm>

#include "iv/Tuning.h"

namespace iv {

namespace {
constexpr float kEps = 0.0001f;

float Mix(float a, float b, float t) { return a + (b - a) * t; }
}  // namespace

void Body::Reset() {
  for (int z = 0; z < kZoneCount; ++z) {
    zone_[z].layer[0] = tune::kArmorMax[z];
    zone_[z].layer[1] = tune::kMechanismMax[z];
    zone_[z].layer[2] = tune::kSystemMax[z];
    zone_[z].state = ZoneState::Intact;
  }
  Recompute();
}

ZoneState Body::Classify(Zone z, const float (&layer)[kLayerCount]) {
  const int i = Index(z);
  if (layer[2] <= kEps) return ZoneState::Destroyed;
  if (layer[1] < tune::kMechanismMax[i] * tune::kCriticalMechanismFraction) return ZoneState::Critical;
  if (layer[1] < tune::kMechanismMax[i] - kEps) return ZoneState::Damaged;
  if (layer[0] <= kEps) return ZoneState::Exposed;
  if (layer[0] < tune::kArmorMax[i] - kEps) return ZoneState::Dented;
  return ZoneState::Intact;
}

float Body::Efficiency(Zone z) const { return tune::kStateEfficiency[static_cast<int>(state(z))]; }

DamageResult Body::ApplyDamage(Zone zone, float amount, StrikeKind kind) {
  DamageResult r;
  ZoneHealth& h = zone_[Index(zone)];
  r.before = h.state;
  r.after = h.state;
  if (amount <= 0.f || h.state == ZoneState::Severed) {
    r.ignored = true;
    return r;
  }
  if (h.state == ZoneState::Destroyed) {
    // Pitch §12: only a destroyed joint can be torn off, and only by a heavy hit or a grab.
    if (IsLimbZone(zone) && kind != StrikeKind::Quick && amount >= tune::kSeverMinDamage) {
      h.state = ZoneState::Severed;
      r.after = ZoneState::Severed;
      r.severed = true;
      r.dealt = amount;
      Recompute();
    } else {
      r.ignored = true;
    }
    return r;
  }
  float remaining = amount;
  for (int l = 0; l < kLayerCount && remaining > 0.f; ++l) {
    const float take = std::min(h.layer[l], remaining);
    h.layer[l] -= take;
    remaining -= take;
    r.dealt += take;
  }
  h.state = Classify(zone, h.layer);
  r.after = h.state;
  if (r.after != r.before) Recompute();
  return r;
}

void Body::Recompute() {
  Modifiers m;
  const Zone arms[2] = {Zone::ArmL, Zone::ArmR};
  const Zone shoulders[2] = {Zone::ShoulderL, Zone::ShoulderR};
  for (int a = 0; a < 2; ++a) {
    ArmMods& am = m.arm[a];
    const ZoneState armState = state(arms[a]);
    const ZoneState shState = state(shoulders[a]);
    const float sh = Efficiency(shoulders[a]);
    const float el = Efficiency(arms[a]);
    am.usable = armState < ZoneState::Destroyed && shState < ZoneState::Destroyed;
    am.swingSpeed = am.usable ? 0.7f * sh + 0.3f * el : 0.f;
    am.power = am.usable ? 0.5f * sh + 0.5f * el : 0.f;
    am.reach = am.usable ? Mix(0.5f, 1.f, sh) : 0.f;
    am.blockStrength = armState == ZoneState::Severed ? 0.f : 0.6f * sh + 0.4f * el;
    am.canRetarget = am.usable && shState <= ZoneState::Damaged && armState <= ZoneState::Damaged;
    am.canGrab = am.usable;
    if (!am.usable) {
      am.allowedSides = 0;
    } else if (armState <= ZoneState::Exposed) {
      am.allowedSides = 0b1111;
    } else if (armState == ZoneState::Damaged) {
      am.allowedSides = 0b0111;  // pitch §9: a damaged elbow loses the low swing
    } else {
      am.allowedSides = a == 0 ? 0b0011 : 0b0101;  // Critical: Up and the arm's own side only
    }
  }

  const float legL = Efficiency(Zone::LegL);
  const float legR = Efficiency(Zone::LegR);
  const float legMean = 0.5f * (legL + legR);
  const float legMin = std::min(legL, legR);
  m.stepSpeed = legMean * (0.6f + 0.4f * legMin);
  m.turnRate = m.stepSpeed * (0.6f + 0.4f * Efficiency(Zone::Torso));
  m.stabilityRecovery = m.stepSpeed * (0.5f + 0.5f * Efficiency(Zone::Reactor));
  m.coolingEff = Mix(0.4f, 1.f, Efficiency(Zone::Reactor));
  m.dodgeLeft = state(Zone::LegR) <= ZoneState::Damaged && state(Zone::LegL) <= ZoneState::Critical;
  m.dodgeRight = state(Zone::LegL) <= ZoneState::Damaged && state(Zone::LegR) <= ZoneState::Critical;
  m.canRam = state(Zone::LegL) <= ZoneState::Damaged && state(Zone::LegR) <= ZoneState::Damaged;

  const ZoneState head = state(Zone::Head);
  m.targetLockDelayTicks = tune::kBaseLockDelayTicks + tune::kHeadLockDelay[static_cast<int>(head)];
  m.blindSectors = 0;
  if (head == ZoneState::Critical) m.blindSectors = 0b0010;       // Left sector
  if (head >= ZoneState::Destroyed) m.blindSectors = 0b0110;      // Left + Right sectors
  m.weaponAccuracy = tune::kWeaponBaseAccuracy * (0.5f * Efficiency(Zone::Head) + 0.5f * Efficiency(Zone::ShoulderR));
  mods_ = m;
}

int Body::DamagedLimbs() const {
  int n = 0;
  const Zone limbs[] = {Zone::ArmL, Zone::ArmR, Zone::LegL, Zone::LegR};
  for (Zone z : limbs)
    if (state(z) >= ZoneState::Damaged) ++n;
  return n;
}

EndReason Body::CheckEnd(bool powerLoss) const {
  if (state(Zone::Reactor) >= ZoneState::Destroyed) return EndReason::ReactorDestroyed;
  if (state(Zone::Torso) >= tune::kCockpitCriticalState) return EndReason::CockpitCritical;
  const bool legsLost = lost(Zone::LegL) && lost(Zone::LegR);
  if (legsLost) return EndReason::TotalImmobility;
  if (powerLoss) return EndReason::PowerLoss;
  const bool armsLost = lost(Zone::ArmL) && lost(Zone::ArmR);
  if (armsLost && (lost(Zone::LegL) || lost(Zone::LegR))) return EndReason::ArmsLostImmobilised;
  return EndReason::None;
}

}  // namespace iv

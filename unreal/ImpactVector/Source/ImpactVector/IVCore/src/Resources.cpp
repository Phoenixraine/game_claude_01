#include "iv/Resources.h"

#include <algorithm>

namespace iv {

bool Resources::LoseStability(float amount) {
  if (amount <= 0.f) return false;
  const bool wasPositive = stability > 0.f;
  stability = std::max(0.f, stability - amount);
  return wasPositive && stability <= 0.f;
}

void Resources::GainStability(float amount) { stability = std::min(tune::kStabilityMax, stability + amount); }

void Resources::AddHeat(float amount) { heat = std::max(0.f, std::min(tune::kHeatMax, heat + amount)); }

bool Resources::Spend(float amount) {
  if (amount > energy) return false;
  energy -= amount;
  return true;
}

bool Resources::RequestPriority(EnergyPriority p) {
  if (switchTicksLeft > 0) {
    if (p == pending) return false;
  } else if (p == priority) {
    return false;
  }
  pending = p;
  switchTicksLeft = tune::kEnergySwitchTicks;
  return true;
}

float Resources::HeatPerformance() const {
  // Linear from 1 at the warning threshold down to kHeatMinPerformance at maximum heat.
  if (heat <= tune::kHeatWarnAt) return 1.f;
  const float t = (heat - tune::kHeatWarnAt) / (tune::kHeatMax - tune::kHeatWarnAt);
  return 1.f - (1.f - tune::kHeatMinPerformance) * std::min(1.f, t);
}

float Resources::ArmsMult() const {
  if (priority == EnergyPriority::Arms) return tune::kPrioArmsPower;
  if (priority == EnergyPriority::Legs) return tune::kPrioLegsArmsPenalty;
  return 1.f;
}

float Resources::LegsMult() const {
  if (priority == EnergyPriority::Legs) return tune::kPrioLegsSpeed;
  if (priority == EnergyPriority::Arms) return tune::kPrioArmsLegsPenalty;
  if (priority == EnergyPriority::Guard) return tune::kPrioGuardSpeedPenalty;
  return 1.f;
}

float Resources::DamageTakenMult() const {
  if (priority == EnergyPriority::Guard) return tune::kPrioGuardDamageTaken;
  if (priority == EnergyPriority::Weapon) return tune::kPrioWeaponGuardPenalty;
  return 1.f;
}

float Resources::WeaponChargeMult() const { return priority == EnergyPriority::Weapon ? tune::kPrioWeaponCharge : 1.f; }

ResourceTickResult Resources::Tick(const Modifiers& m, int damagedLimbs, float coolingMult, bool regenStability) {
  ResourceTickResult r;

  // Energy switch in progress (visible to the opponent as an event raised by the Fighter).
  if (switchTicksLeft > 0) {
    --switchTicksLeft;
    if (switchTicksLeft == 0) {
      priority = pending;
      r.prioritySwitched = true;
    }
  }

  energy = std::min(tune::kEnergyMax, energy + tune::kEnergyRegenPerTick);
  if (regenStability) GainStability(tune::kStabilityRegenPerTick * m.stabilityRecovery);

  // Heat: passive cooling (reduced by leaks, rear coolers, scaled by water/rain) plus drive losses.
  const float cooling = tune::kHeatCoolPerTick * coolingMult * m.coolingEff * (coolantLeak ? tune::kHeatLeakCoolingMult : 1.f);
  AddHeat(static_cast<float>(damagedLimbs) * tune::kDamagedDriveHeatPerTick - cooling);

  if (heat >= tune::kHeatWarnAt && !heatWarning) {
    heatWarning = true;
    r.heatWarningStarted = true;
  } else if (heat < tune::kHeatWarnAt - 10.f) {
    heatWarning = false;
  }
  if (heat >= tune::kHeatLeakAt && !coolantLeak) {
    coolantLeak = true;
    r.coolantLeakStarted = true;
  } else if (heat < tune::kHeatLeakAt - 25.f) {
    coolantLeak = false;
  }

  if (heat >= tune::kHeatOverheatAt) {
    ++overheatTicks;
    if (overheatTicks >= tune::kShutdownTicks && !shutdown) {
      shutdown = true;
      r.shutdown = true;
    }
  } else {
    overheatTicks = 0;
  }
  return r;
}

}  // namespace iv

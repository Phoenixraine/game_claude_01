// Module 2: Stability, Heat and Energy (pitch §10).
#pragma once

#include "iv/Body.h"
#include "iv/Tuning.h"
#include "iv/Types.h"

namespace iv {

// What changed during one resource tick; the Fighter turns these into events.
struct ResourceTickResult {
  bool heatWarningStarted = false;
  bool coolantLeakStarted = false;
  bool shutdown = false;           // heat stayed at maximum for kShutdownTicks
  bool prioritySwitched = false;   // the delayed energy switch completed this tick
};

struct Resources {
  float stability = tune::kStabilityMax;
  float heat = 0.f;
  float energy = tune::kEnergyMax;

  EnergyPriority priority = tune::kDefaultPriority;  // active distribution
  EnergyPriority pending = tune::kDefaultPriority;   // target of a switch in progress
  int switchTicksLeft = 0;                           // > 0 while the visible energy flow runs

  bool heatWarning = false;
  bool coolantLeak = false;
  int overheatTicks = 0;
  bool shutdown = false;

  // Subtracts stability (never below 0). Returns true when it just reached zero.
  bool LoseStability(float amount);
  void GainStability(float amount);
  void AddHeat(float amount);
  // Spends energy; refuses (returns false, nothing deducted) when not enough is left.
  bool Spend(float amount);
  // Starts a delayed switch (pitch §10: "Переключение происходит не мгновенно"). No-op if already
  // active or already switching to the same priority. Returns true when a new switch started.
  bool RequestPriority(EnergyPriority p);

  // Heat-based performance multiplier in [kHeatMinPerformance, 1] (pitch §10 "замедление, снижение силы").
  float HeatPerformance() const;

  // Multipliers of the active priority (pitch §10, §8).
  float ArmsMult() const;       // strike power and block strength
  float LegsMult() const;       // movement speed and recovery
  float DamageTakenMult() const;
  float WeaponChargeMult() const;

  // One simulation tick of passive effects. `regenStability` is false while the mech is blocking
  // or otherwise under load. `coolingMult` carries water/rain (pitch §10) times the cooler condition.
  ResourceTickResult Tick(const Modifiers& m, int damagedLimbs, float coolingMult, bool regenStability);
};

}  // namespace iv

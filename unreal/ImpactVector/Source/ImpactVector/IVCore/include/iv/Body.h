// Module 1: the nine-zone, three-layer body and the functional modifiers it produces (pitch §9, §14).
#pragma once

#include <cstdint>

#include "iv/Types.h"

namespace iv {

// What one arm can still do. Everything here is a monotone non-increasing function of the
// states of the shoulder and the arm (elbow + hand) zones (pitch §9 "Плечи и руки").
struct ArmMods {
  bool usable = true;          // false once the arm or its shoulder is Destroyed / Severed
  float swingSpeed = 1.f;      // pitch §9: shoulder damage slows the swing
  float power = 1.f;           // strike power
  float reach = 1.f;           // pitch §9: shoulder damage shortens the reach
  float blockStrength = 1.f;   // pitch §9: shoulder damage weakens blocks
  bool canRetarget = true;     // pitch §9: changing trajectory / feinting
  bool canGrab = true;         // pitch §9: a destroyed hand cannot grab
  uint8_t allowedSides = 0b1111;  // pitch §9: a damaged elbow limits the attack set (bit per SwingSide)
};

// Recomputed on every damage event (pitch §9 "Функциональные эффекты").
struct Modifiers {
  ArmMods arm[2];
  float stepSpeed = 1.f;          // legs: movement speed
  float turnRate = 1.f;           // legs + torso: how fast the mech re-faces
  float stabilityRecovery = 1.f;  // legs + rear stabilisers: recovery after hits
  float coolingEff = 1.f;         // rear coolers (pitch §9 "Задняя часть корпуса")
  bool dodgeLeft = true;          // pitch §9 "Ноги": damage removes some dodges
  bool dodgeRight = true;
  bool canRam = true;             // pitch §11 Таран needs two working legs
  int targetLockDelayTicks = 12;  // pitch §9 "Голова": lock-on delay
  uint8_t blindSectors = 0;       // pitch §9 "Голова": swing sectors the pilot cannot see (bit per SwingSide)
  float weaponAccuracy = 1.f;     // pitch §9 "Голова", pitch §13
};

struct DamageResult {
  float dealt = 0.f;       // damage that actually landed on layers
  ZoneState before = ZoneState::Intact;
  ZoneState after = ZoneState::Intact;
  bool severed = false;    // the limb was torn off by this hit
  bool ignored = false;    // zone already Destroyed/Severed and the hit could not sever it
  Layer deepest = Layer::Armor;  // deepest layer this hit touched (v2 HitEvent)
  float armorBefore = 0.f;       // Armor layer before / after (v2 ArmorPlateLost)
  float armorAfter = 0.f;
};

class Body {
 public:
  Body() { Reset(); }
  void Reset();

  // Consumes Armor first, then Mechanism, then System. A Destroyed arm/leg is torn off only by a
  // Heavy or Grab hit of at least tune::kSeverMinDamage (pitch §9, §12).
  DamageResult ApplyDamage(Zone zone, float amount, StrikeKind kind);

  ZoneState state(Zone z) const { return zone_[Index(z)].state; }
  float layer(Zone z, Layer l) const { return zone_[Index(z)].layer[static_cast<int>(l)]; }
  bool severed(Zone z) const { return state(z) == ZoneState::Severed; }
  // Zone counts as lost: Destroyed or Severed.
  bool lost(Zone z) const { return state(z) >= ZoneState::Destroyed; }
  float Efficiency(Zone z) const;
  const Modifiers& modifiers() const { return mods_; }
  // v3: fraction (0..1) of all armour + mechanism + system points that are left; the ultimate picks its variant by it.
  float Integrity() const;

  // Number of limbs in Damaged or worse state (feeds heat from "damaged drives", pitch §10).
  int DamagedLimbs() const;
  // Pitch §14 victory conditions. `powerLoss` is raised by the heat shutdown.
  EndReason CheckEnd(bool powerLoss) const;

 private:
  struct ZoneHealth {
    float layer[kLayerCount];
    ZoneState state;
  };

  static ZoneState Classify(Zone z, const float (&layer)[kLayerCount]);
  void Recompute();

  ZoneHealth zone_[kZoneCount];
  Modifiers mods_;
};

}  // namespace iv

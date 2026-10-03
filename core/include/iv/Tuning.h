// ALL balance numbers of the combat core live here (CLAUDE.md rule). Every constant carries a
// `pitch §N` reference to docs/pitch/02_pitch/IMPACT_VECTOR_FULL_PITCH_RU.md.
// Timings are ticks at 60 Hz; the pitch's millisecond values are converted with MsToTicks().
#pragma once

#include "iv/Types.h"

namespace iv {
namespace tune {

// ---------------------------------------------------------------- zones (pitch §9, §14)
// Layer capacities per zone: Armor -> Mechanism -> System.
constexpr float kArmorMax[kZoneCount] = {
    50.f,   // Head       pitch §9 "Голова и сенсоры"
    180.f,  // Torso      pitch §9 "лучше всего бронирован"
    40.f,   // Reactor    pitch §9 "Задняя часть корпуса"
    70.f,   // ShoulderL  pitch §9 "Плечи и руки"
    70.f,   // ShoulderR  pitch §9
    55.f,   // ArmL       pitch §9
    55.f,   // ArmR       pitch §9
    90.f,   // LegL       pitch §9 "Ноги"
    90.f,   // LegR       pitch §9
};
constexpr float kMechanismMax[kZoneCount] = {40.f, 110.f, 30.f, 50.f, 50.f, 45.f, 45.f, 70.f, 70.f};  // pitch §14
constexpr float kSystemMax[kZoneCount] = {60.f, 140.f, 60.f, 60.f, 60.f, 50.f, 50.f, 70.f, 70.f};      // pitch §14

constexpr float kCriticalMechanismFraction = 0.30f;  // pitch §14: below this the mechanism is Critical

// pitch §9: how well a zone works in each state (1 = perfect). Monotone non-increasing by construction.
constexpr float kStateEfficiency[kZoneStateCount] = {1.00f, 0.97f, 0.92f, 0.72f, 0.40f, 0.10f, 0.00f};

// pitch §9 "Центр корпуса": centre hits do the most total damage; limbs are cheaper to disable.
constexpr float kZoneDamageMult[kZoneCount] = {1.0f, 1.3f, 1.2f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f};

// pitch §12: a Destroyed limb can only be torn off by a heavy hit or grab of at least this damage.
constexpr float kSeverMinDamage = 6.f;

// pitch §14 "Победа без обычной полоски здоровья"
constexpr ZoneState kCockpitCriticalState = ZoneState::Destroyed;  // Torso at this state ends the match
constexpr int kShutdownTicks = 180;  // pitch §10: heat at maximum this long -> power loss

// pitch §9 "Голова": extra lock-on delay (ticks) by Head state; blind sectors from Critical on.
constexpr int kBaseLockDelayTicks = 12;
constexpr int kHeadLockDelay[kZoneStateCount] = {0, 0, 4, 10, 20, 40, 40};

// pitch §9 "Задняя часть корпуса": the Reactor can only be hit if the victim is flanked this far.
constexpr float kRearAngleDeg = 45.f;

// ---------------------------------------------------------------- resources (pitch §10)
constexpr float kStabilityMax = 100.f;                 // pitch §10 Стабильность
constexpr float kStabilityRegenPerTick = 0.12f;        // pitch §10, scaled by leg condition
constexpr int kStaggerTicks = MsToTicks(700);          // pitch §10 "сильный stagger"
constexpr float kStaggerHoldStability = 20.f;          // stability while staggered; reaching 0 again -> knockdown
constexpr float kStaggerResetStability = 35.f;         // stability after a stagger ends
constexpr int kKnockdownTicks = MsToTicks(2200);       // pitch §10 "полностью опрокидывается"
constexpr float kKnockdownResetStability = 55.f;
constexpr float kStaggerDamageMult = 1.3f;             // pitch §10: a staggered mech is easier to hit
constexpr float kKnockdownDamageMult = 1.6f;

constexpr float kHeatMax = 100.f;                      // pitch §10 Тепло
constexpr float kHeatCoolPerTick = 0.05f;              // passive cooling
constexpr float kHeatWarnAt = 65.f;                    // pitch §10 "аварийные предупреждения"
constexpr float kHeatLeakAt = 85.f;                    // pitch §10 "течь охлаждения"
constexpr float kHeatOverheatAt = 97.f;                // pitch §10 "риск отключения системы": shutdown timer runs above this
constexpr float kHeatLeakCoolingMult = 0.25f;          // cooling left while the coolant leaks
constexpr float kHeatMinPerformance = 0.65f;           // pitch §10 "замедление, снижение силы" at max heat
constexpr float kDamagedDriveHeatPerTick = 0.006f;     // pitch §10 "работа повреждённых приводов", per Damaged+ limb
constexpr float kHeavyChargeHeatPerTick = 0.09f;       // pitch §10 "заряженные атаки"
constexpr float kHeavyReleaseHeat = 2.0f;
constexpr float kFeintHeat = 4.5f;                     // pitch §8 "Частые финты накапливают тепло"
constexpr float kEmergencyBrakeHeat = 9.f;             // pitch §5.2 (4) "аварийное торможение ... накопит тепло"
constexpr float kCheapCancelHeat = 1.0f;               // pitch §5.2 (4) cheap cancel before the commit point
constexpr float kDodgeHeat = 2.0f;
constexpr float kWeaponChargeHeatPerTick = 0.08f;      // pitch §10 "стрельба"
constexpr float kWeaponFireHeat = 12.f;

constexpr float kEnergyMax = 100.f;                    // pitch §10 Энергия
constexpr float kEnergyRegenPerTick = 0.09f;
constexpr int kEnergySwitchTicks = MsToTicks(800);     // pitch §10 "Переключение происходит не мгновенно"
constexpr EnergyPriority kDefaultPriority = EnergyPriority::Guard;
// pitch §10 / §8 "Энергетические признаки": priority multipliers.
constexpr float kPrioArmsPower = 1.15f;                // Arms: stronger strikes and blocks
constexpr float kPrioArmsLegsPenalty = 0.90f;          // ...but legs and sensors work worse
constexpr float kPrioLegsSpeed = 1.20f;                // Legs: faster movement and recovery
constexpr float kPrioLegsArmsPenalty = 0.90f;
constexpr float kPrioGuardDamageTaken = 0.80f;         // Guard: lower structural damage
constexpr float kPrioGuardSpeedPenalty = 0.95f;
constexpr float kPrioWeaponCharge = 1.40f;             // Weapon: faster charge, steadier aim
constexpr float kPrioWeaponGuardPenalty = 1.0f;       // damage taken while Weapon is prioritised

// ---------------------------------------------------------------- strikes (pitch §5)
constexpr int kWindupMinTicks = MsToTicks(450);        // pitch §5.2 (1): shortest legal heavy windup
constexpr int kWindupMaxChargeTicks = MsToTicks(1000); // pitch §5.2: extra hold that still adds power
constexpr int kChargeAudibleTicks = MsToTicks(250);    // pitch §8 "звук набирающего давление привода"
constexpr int kCommitDelayTicks = MsToTicks(140);      // pitch §5.2 (4): release -> irreversible Strike
constexpr int kHeavyStrikeTicks = MsToTicks(560);      // pitch §5.2: travel time of the arm
constexpr int kHeavyRecoveryTicks = MsToTicks(950);    // pitch §5.4
constexpr int kQuickWindupTicks = 3;                   // pitch §5.3 (short press)
constexpr int kQuickStrikeTicks = 7;
constexpr int kQuickRecoveryTicks = MsToTicks(230);
constexpr int kGrabWindupTicks = MsToTicks(400);       // pitch §12
constexpr int kGrabStrikeTicks = MsToTicks(150);
constexpr int kGrabRecoveryTicks = MsToTicks(650);
constexpr int kAbortRecoveryTicks = 6;                 // pitch §5.2: windup released too early
constexpr int kEmergencyBrakeRecoveryTicks = MsToTicks(500);
constexpr float kEmergencyBrakeStability = 14.f;       // pitch §5.2 (4) "потеряет стабильность"
constexpr int kInterruptedRecoveryTicks = MsToTicks(500);  // windup broken by a hit (pitch §5.3 "перебивают")

constexpr float kHeavyDamage = 17.5f;                     // pitch §5.2 base damage of a heavy strike
constexpr float kChargeDamageBonus = 1.0f;             // pitch §5.2: full charge doubles the damage
constexpr float kQuickDamage = 2.5f;                    // pitch §5.3 "наносят небольшой урон"
constexpr float kInnerLineDamageMult = 1.0f;           // pitch §7 counter strikes
constexpr float kHitStabilityFactor = 0.55f;           // stability lost per point of damage taken (pitch §10)
constexpr float kQuickStabilityHit = 5.f;
constexpr float kWhiffStability = 9.f;                 // pitch §10 "промахов"
constexpr float kHeavyReach = 30.f;                    // distance units a straight heavy can cover
constexpr float kQuickReach = 22.f;
constexpr float kGrabReach = 18.f;
constexpr float kStepInReachBonus = 8.f;               // pitch §11 "Шаг в удар"
constexpr float kStepInDistance = 10.f;                // distance closed by a StepIn strike
constexpr float kStepBackDistance = 8.f;               // pitch §5.2 (3) "короткий удар с последующим отходом"
constexpr float kPlantPower[5] = {1.00f, 1.15f, 0.85f, 0.95f, 0.65f};  // pitch §11 Planted/Stepped/Over/Turned/Retreated
constexpr float kPlantRecoveryMult[5] = {1.0f, 1.0f, 1.3f, 1.0f, 0.7f};
constexpr float kPlantStabilityCost[5] = {0.f, 3.f, 8.f, 2.f, 0.f};      // pitch §5.2 п.3
constexpr float kStepInMinStability = 40.f;            // below this a StepIn becomes Overextended
constexpr float kTurnAngleDeg = 25.f;                  // pitch §11 "Спина и ноги не всегда направлены туда же"
constexpr float kUnnaturalTargetMult = 0.8f;           // pitch §5.2: swing/target pair that does not follow the arm's path
// Natural targets per swing family, bitmask over Zone (bit = Index(Zone)). pitch §5.2 (2).
constexpr uint16_t kNaturalTargets[4] = {
    0b000011111,  // Up:    Head, Torso, Reactor, ShoulderL/R
    0b001111111,  // Left:  everything above the hips
    0b001111111,  // Right: everything above the hips
    0b111100010,  // Down:  Torso, ArmL/R, LegL/R
};

// pitch §5.4: post-strike pose and its economy.
constexpr int kPoseReturnTicks = MsToTicks(500);       // extra windup needed when the pose forbids the swing
constexpr int kPoseDecayTicks = MsToTicks(900);        // idle time after which the arm is back to Neutral
// Allowed swing families per pose, as bitmask over SwingSide (Up=1, Left=2, Right=4, Down=8).
constexpr uint8_t kPoseAllowed[kArmPoseCount] = {
    0b1111,  // Neutral
    0b0111,  // Raised (after Up): Up, Left, Right
    0b0100,  // CrossedLeft (after Left): backhand Right only
    0b0010,  // CrossedRight (after Right): backhand Left only
    0b1110,  // Low (after Down): Down, Left, Right; a new Up swing needs the arm returned first
};
constexpr float kPoseRecoveryMult[kArmPoseCount] = {1.0f, 1.0f, 0.9f, 0.9f, 1.1f};

// pitch §8 "Финты".
constexpr int kFeintSlowTicks = MsToTicks(700);        // slowdown after each feint
constexpr float kFeintSlowMult = 0.8f;
constexpr int kFeintDecayTicks = MsToTicks(2500);      // one counted feint is forgotten this often
constexpr int kMaxFeintsBeforePenalty = 2;             // beyond this each feint costs double heat

// ---------------------------------------------------------------- defence (pitch §6, §7)
constexpr int kBlockRaiseTicks = MsToTicks(400);       // pitch §6: "безопасный блок 350-450 мс"
constexpr int kParryWindowTicks = MsToTicks(170);      // pitch §6: "парирование 140-200 мс"
constexpr int kInterceptWindowTicks = MsToTicks(115);  // pitch §7 / §6: "перехват 90-140 мс"
constexpr int kReverseWindowTicks[2] = {MsToTicks(100), MsToTicks(80)};  // pitch §6: "ответ на контратаку 70-110 мс" (6 and 5 ticks)
constexpr int kMaxReverseReplies = 2;                  // pitch §7: "максимум 2 ответа", then clinch
constexpr float kBlockDamageMult = 0.25f;              // pitch §6: block "сильно снижает прямой урон"
constexpr float kBlockStabilityFactor = 0.7f;          // pitch §6: "всё равно уменьшает стабильность"
constexpr float kBlockArmLoad = 0.18f;                 // pitch §6: "нагружает блокирующую руку" (share of damage)
constexpr float kGuardEnergyPerTick = 0.03f;           // pitch §6: passive guard must not be free
constexpr float kParryEnergy = 4.f;
constexpr float kParryStabilityHit = 24.0f;             // pitch §6: attacker's tempo breaks
constexpr int kParryRecoveryBonusTicks = MsToTicks(500);
constexpr int kCounterWindowTicks = MsToTicks(400);    // pitch §6: "короткое окно контратаки"
constexpr float kInterceptEnergy = 8.f;                // pitch §7
constexpr float kInterceptArmDamage = 0.4375f;           // pitch §7: share of strike damage that hits the intercepted arm
constexpr float kInterceptStabilityHit = 14.f;
// Counter lines that can intercept each attack, bitmask over SwingSide (pitch §7 "Перехват").
constexpr uint8_t kInterceptLines[4] = {
    0b0111,  // against Up:    Up, Left, Right
    0b0011,  // against Left:  Up, Left
    0b0101,  // against Right: Up, Right
    0b1110,  // against Down:  Left, Right, Down
};
constexpr int kInterceptedRecoveryTicks = MsToTicks(700);
constexpr float kReverseEnergyBase = 6.f;              // pitch §7: cost grows with depth
constexpr float kReverseDamage = 8.f;
constexpr float kReverseDepthDamageGrowth = 0.5f;      // pitch §7: "более серьёзное наказание за ошибку"
constexpr float kReverseFailStability = 12.f;
constexpr int kStrikeTradeWindowTicks = MsToTicks(100);// a strike this close to its own contact survives being hit

constexpr float kHardStanceDamageMult = 0.18f;         // pitch §6 "Усиленная стойка"
constexpr float kHardStanceLegDamageMult = 1.4f;       // pitch §6: "открывает ноги"
constexpr float kHardStanceEnergyPerTick = 0.22f;      // pitch §6: "расходует много энергии"
constexpr float kHardStanceStabilityFactor = 0.25f;
constexpr float kHardStanceMinStability = 30.f;
constexpr int kHardStanceRaiseTicks = MsToTicks(500);

constexpr int kDodgeEvadeTicks = MsToTicks(260);       // pitch §6 "Уклонение": time the mech is out of the line
constexpr int kDodgeStabilizeTicks = MsToTicks(500);   // pitch §6: "должен стабилизироваться"
constexpr float kDodgeStability = 10.f;
constexpr float kDodgeEnergy = 5.f;
constexpr float kDodgeFlankDeg = 75.f;                 // pitch §6 "зайти к повреждённому боку"
constexpr float kFlankTurnDegPerTick = 0.45f;           // pitch §11: how fast a mech re-faces its opponent

// ---------------------------------------------------------------- clinch (pitch §7)
constexpr int kClinchTicks = MsToTicks(900);
constexpr float kClinchWStability = 1.0f;              // pitch §7: stability, body angle, foot plant, arm damage,
constexpr float kClinchWAngle = 0.6f;                  //           movement direction, proximity of a wall
constexpr float kClinchWLegs = 0.7f;
constexpr float kClinchWArms = 0.6f;
constexpr float kClinchWMove = 0.25f;
constexpr float kClinchWWall = 0.7f;
constexpr float kClinchLoserStability = 45.f;
constexpr float kClinchWinnerHeat = 3.f;
constexpr float kWallSlamMargin = 0.6f;                // pitch §12 "прижимать к зданию"
constexpr float kWallSlamProximity = 0.5f;
constexpr float kWallSlamDamage = 14.f;

// ---------------------------------------------------------------- grab (pitch §12)
constexpr float kGrabStability = 35.2f;
constexpr float kGrabHeat = 3.f;
constexpr float kGrabDamage = 10.f;

// ---------------------------------------------------------------- weapon (pitch §13)
constexpr int kWeaponChargeTicks = MsToTicks(1800);    // pitch §13: "Удерживать цель несколько секунд"
constexpr float kWeaponDamage = 40.0f;                  // pitch §13: "способно пробить броню или разрушить сустав"
constexpr float kWeaponMinDistance = 18.f;
constexpr float kWeaponBlockMult = 0.55f;
constexpr float kWeaponBaseAccuracy = 0.8f;
constexpr int kWeaponRecoveryTicks = MsToTicks(1200);  // pitch §13: the shoulder launcher is slow to close again


// ================================================================ v2 (TASK-001 update): weapons, ultimate, cinematics, presentation
// Heavy weapons (pitch §13 + v2): each has a long cooldown; firing one cuts to an external camera (Cinematic).
struct WeaponProfile {
  int chargeTicks;        // hold time before the shot can be released
  float damage;           // per projectile
  int salvo;              // projectiles per shot
  int recoveryTicks;      // locked after the shot
  int cooldownTicks;      // before the next charge may start (the "large reload")
  int ammo;               // shots in the magazine (-1 = unlimited)
  float heatPerShot;
  float accuracy;         // multiplier on the base accuracy of the head/shoulder (pitch §9, §13)
  float blockMult;        // damage multiplier when the target blocks in time
  float stabilityFactor;  // stability damage = damage * factor
  bool locksLegs;         // the pilot cannot step or dodge while charging (RailSpear)
  int cinematicTicks;     // length of the external cut
};
constexpr WeaponProfile kWeapons[kWeaponKindCount] = {
    // RailSpear: long charge, legs locked, one devastating shot (the pitch §13 shoulder launcher, kept as the default loadout)
    {kWeaponChargeTicks, kWeaponDamage, 1, kWeaponRecoveryTicks, MsToTicks(9000), -1, 18.f, 1.0f, 0.7f, 0.6f, true, MsToTicks(2500)},
    // SuppressionRockets: short lock-on, six small rockets, three salvos in the rack
    {MsToTicks(700), 6.5f, 6, MsToTicks(900), MsToTicks(7000), 3, 10.f, 0.75f, 0.5f, 0.8f, false, MsToTicks(2000)},
    // PlasmaCannon: medium charge, heavy heat: a second shot soon after risks a shutdown
    {MsToTicks(1300), 34.f, 1, MsToTicks(1100), MsToTicks(6000), -1, 38.f, 0.9f, 0.6f, 0.7f, false, MsToTicks(1750)},
};
constexpr float kWeaponEvadeHitMult = 0.35f;            // rockets: a dodging target still gets clipped sometimes
constexpr int kCinematicStunTicks = MsToTicks(1500);    // the target of a hit cut is staggered for this long afterwards
constexpr int kCinematicProtectTicks = MsToTicks(2000); // the shooter takes no damage for this long after the cut
constexpr int kUltimateCinematicTicks = MsToTicks(3500);

// Ultimate gauge (v2): fills from skill, much less from suffering.
constexpr float kUltimateMax = 100.f;
constexpr float kUltGainParry = 6.f;                   // successful parry (the parrying fighter)
constexpr float kUltGainIntercept = 8.f;               // successful intercept (the interceptor)
constexpr float kUltGainCriticalHit = 1.5f;              // landing a hit on a zone that is Critical or worse
constexpr float kUltGainHit = 0.45f;                     // any landed hit
constexpr float kUltGainTakenPerDamage = 0.02f;         // receiving damage (small, capped per hit)
constexpr float kUltGainTakenCap = 0.3f;
constexpr float kUltimateDamage = 42.f;                 // scripted unblockable strike on the chosen zone
constexpr float kUltimateStabilityHit = 70.f;

// Armour plates per zone (ArmorPlateLost events fire as the Armor layer drains in equal steps).
constexpr int kArmorPlates[kZoneCount] = {3, 8, 4, 5, 5, 6, 6, 6, 6};

// ---------------------------------------------------------------- v3: sword duel rules
// Blades that meet: two strikes on the same line whose contact ticks are this close stop each other (double block).
constexpr int kClashWindowTicks = MsToTicks(110);
constexpr int kClashRecoveryTicks = MsToTicks(800);
constexpr float kClashStability = 14.f;
constexpr float kClashHeat = 3.f;
constexpr float kUltGainClash = 3.f;
// No chained stun: after a stagger or a knockdown the mech shrugs off further stability loss for a while.
constexpr int kStunImmuneTicks = MsToTicks(1600);
constexpr int kStunImmuneAfterKnockdownTicks = MsToTicks(2600);
constexpr float kStunImmuneFloor = 6.f;
// Status conditions.
constexpr int kBlindTicks = MsToTicks(4200);           // rockets: the target cannot read the sectors
constexpr int kStrikeLockTicks = MsToTicks(2600);      // rail spear: arm actuators jammed, no strikes (guard and dodge still work)
constexpr int kBurnTicks = MsToTicks(5000);            // plasma: the hull burns
constexpr int kBurnPeriodTicks = 30;
constexpr float kBurnDamage = 1.6f;
constexpr float kBurnHeatPerTick = 0.12f;
constexpr int kDebrisBlindTicks = MsToTicks(3200);     // a building thrown in the face
constexpr float kDebrisDamage = 11.f;
constexpr float kDebrisStability = 24.f;
// Ultimate variants: a weakened target is cut in half, a healthy one loses its off-hand arm (and with it the ultimate).
constexpr float kUltimateKillFraction = 0.38f;
constexpr float kUltimateSeverDamage = 60.f;
// AI mimic: chance that an attack repeats the swing line the opponent used last.
constexpr float kMirrorChance[kDifficultyCount] = {0.25f, 0.45f, 0.65f};

// Training dummy (v2).
constexpr int kDummyReactionTicks = 14;
constexpr int kDummyScriptGapTicks = MsToTicks(2200);

// ---------------------------------------------------------------- boarding (STATUS §6B, TASK-017)
// Phase lengths (STATUS §6B: climb out of the cockpit, stand on the shoulder, fire the grapple, fly, land, hack, throw, leave, watch, return).
constexpr int kBoardClimbOutTicks = MsToTicks(2200);      // STATUS §6B 1
constexpr int kBoardOnShoulderTicks = MsToTicks(700);     // STATUS §6B 1
constexpr int kBoardHookLaunchTicks = MsToTicks(600);     // STATUS §6B 2
constexpr int kBoardHookFlightTicks = MsToTicks(1400);    // STATUS §6B 2
constexpr int kBoardLandingTicks = MsToTicks(800);        // STATUS §6B 3
constexpr int kBoardGrenadeThrowTicks = MsToTicks(1100);  // STATUS §6B 5
constexpr int kBoardEscapeTicks = MsToTicks(1500);        // STATUS §6B 5 (fly up and away)
constexpr int kBoardBlastDelayTicks = MsToTicks(900);     // STATUS §6B 5: the grenade explodes this long after the WatchBlast phase begins
constexpr int kBoardWatchBlastTicks = MsToTicks(2200);    // STATUS §6B 5: includes the delay above, then the look back
constexpr int kBoardReturnHookTicks = MsToTicks(1500);    // STATUS §6B 5: the failed hack: back along the grapple
constexpr int kBoardClimbInTicks = MsToTicks(1800);       // STATUS §6B 5: into the cockpit, control returns
constexpr int kBoardHookSwingTicks = MsToTicks(900);      // STATUS §6B 6: swing to the other shoulder
// Cost and limits (STATUS §6B 7).
constexpr float kBoardEnergyCost = 25.f;                  // spent when the boarding starts
constexpr float kBoardMinStability = 35.f;                // a shaky mech cannot be left
constexpr float kBoardPenaltyEnergy = 15.f;               // extra energy lost after a failed or timed-out hack
constexpr int kBoardCooldownTicks = MsToTicks(60000);     // STATUS §6B 7 (task: not below 45 s)
constexpr int kBoardCooldownFailTicks = MsToTicks(75000); // longer after a failure
constexpr float kBoardShockSeconds = 0.8f;                // an enemy hit on the empty mech shakes the pilot: this much hack time is lost per hit
constexpr int kBoardMaxShocks = 4;
// Grenade (STATUS §6B 5): 1.5 .. 2.2 heavy strikes (kHeavyDamage = 17.5), better hack quality -> bigger blast.
constexpr float kGrenadeDamageMin = 27.f;
constexpr float kGrenadeDamageMax = 38.f;                 // kGrenadeDamageMax: hard cap
constexpr float kGrenadeStability = 30.f;
constexpr int kGrenadeBurnTicks = MsToTicks(3500);
constexpr int kGrenadeSource = 3;                         // Duel::ExternalHit source: 3 = grenade (0 debris, 1 crash, 2 fall)
// The enemy hand (STATUS §6B 6): telegraph, the window in which the swing button works, and what is kept of the hack.
constexpr int kSwatWindupTicks[kDifficultyCount] = {MsToTicks(1200), MsToTicks(900), MsToTicks(650)};  // >= 900 ms easy, >= 600 ms hard
constexpr int kSwatReadyTicks = MsToTicks(200);           // presses in the first moments after the telegraph are ignored (it cannot be seen yet)
constexpr int kSwingWindowTicks = MsToTicks(700);         // the swing works from this long before the impact...
constexpr int kSwingMinTicks = MsToTicks(150);            // ...until this long before it (the leap needs time)
constexpr float kSwingKeepProgress = 0.5f;                // share of the hack progress that survives a swing to the other shoulder
constexpr int kSwatGraceTicks = MsToTicks(1500);          // no swat in the first moments after landing
constexpr int kSwatCheckTicks = MsToTicks(500);           // the enemy decides every half second
constexpr int kSwatCooldownTicks = MsToTicks(3000);       // between two swats
constexpr int kMaxSwatsPerBoarding = 2;
constexpr int kMaxSwatAdjust = 1;                         // an early press makes the enemy re-aim once per swat
constexpr float kSwatChance[kDifficultyCount] = {0.05f, 0.09f, 0.14f};   // per check, by enemy difficulty
constexpr float kSwatArchetypeMult[kArchetypeCount] = {1.2f, 1.0f, 1.0f, 0.9f, 0.5f, 1.4f};  // Counterpuncher, Breaker, LimbHunter, Trickster, Gunner, Grappler
constexpr float kAutopilotDamageMult = 1.4f;           // STATUS §6B 3: the mech without its pilot takes more damage
constexpr bool kAiBoardingEnabled = false;                // STATUS §6B: the enemy cannot board the player (yet); the API is symmetric by Side

// ---------------------------------------------------------------- hack mini-game (STATUS §6B 4, TASK-018)
// One row per hack difficulty 1..10 (data/hack/difficulty.json is the same table: a test keeps them equal).
// Stages: 2 = Path + Frequency; 3 = Path + Rhythm + Frequency; 5 = ... + the boss phase (Rhythm + Frequency under a permanent alarm).
struct HackLevel {
  int level;
  int stages;
  int gridW, gridH, blocks, ice, keys;                       // path layer: nodes, blockers, ice nodes on the route, keys to collect in order
  int lanes, impulses, gapMin, gapMax, hitWindow;            // rhythm layer: lanes, impulses, gap between impulses (ticks), +-window (ticks)
  int locks;                                                 // frequency layer: locks to land
  float lockHalfDeg, lockShrink, relSpeed;                   // first window half-width (deg), shrink per lock, hacker/ICE relative speed (deg per tick)
  int timeLimitSec, penaltyMs, heatPerMistake;               // global time limit, time lost per mistake, ICE heat per mistake (100 = ICE trips)
};
constexpr HackLevel kHackLevels[10] = {
    {1, 3, 5, 4, 4, 0, 1, 3, 10, 26, 44, 5, 3, 20.f, 0.88f, 5.0f, 25, 1500, 30},
    {2, 3, 5, 4, 5, 0, 1, 3, 10, 24, 42, 5, 3, 20.f, 0.88f, 5.0f, 26, 1600, 31},
    {3, 3, 6, 4, 6, 1, 1, 3, 12, 22, 40, 6, 4, 21.f, 0.88f, 5.1f, 28, 1700, 32},
    {4, 3, 6, 5, 8, 1, 2, 3, 12, 22, 40, 6, 4, 20.f, 0.88f, 5.3f, 30, 1400, 26},
    {5, 3, 7, 5, 9, 2, 2, 4, 14, 22, 40, 6, 4, 19.f, 0.87f, 5.6f, 34, 1450, 26},
    {6, 3, 7, 5, 10, 2, 2, 4, 16, 20, 36, 5, 5, 18.f, 0.87f, 5.9f, 42, 1500, 27},
    {7, 3, 8, 5, 12, 3, 3, 4, 18, 18, 32, 5, 5, 17.5f, 0.86f, 6.0f, 40, 1600, 28},
    {8, 5, 8, 6, 13, 3, 3, 4, 18, 18, 32, 6, 5, 22.f, 0.90f, 5.1f, 45, 1500, 25},
    {9, 5, 9, 6, 15, 4, 3, 5, 20, 17, 30, 6, 5, 21.5f, 0.90f, 5.1f, 44, 1600, 26},
    {10, 5, 9, 6, 16, 4, 4, 5, 22, 16, 28, 5, 6, 22.5f, 0.90f, 4.9f, 48, 1700, 27},
};
constexpr int kHackLeadTicks = 60;                 // rhythm: the first impulse arrives this late
constexpr int kHackTravelTicks = 90;               // rhythm: how long an impulse is visible before the hit line
constexpr int kHackAlarmHeat = 70;                 // heat at which the alarm starts: the rhythm window shrinks by 1 tick, the frequency speed rises 12 %
constexpr int kHackTripHeat = 100;                 // heat at which the ICE trips: the stage restarts
constexpr int kHackTripHeatAfter = 40;
constexpr float kHackHeatDecayPerTick = 0.10f;     // 6 heat per second
constexpr int kHackTripPenaltyMult = 3;            // a trip costs this many mistake penalties of time
constexpr int kHackUndoPenaltyTicks = 12;          // path: stepping back one node
constexpr float kHackLockSpeedGain = 0.05f;        // frequency: speed rises by 5 % per landed lock
constexpr float kHackAlarmSpeedMult = 1.12f;
constexpr float kHackLockHalfMinDeg = 6.f;         // never narrower than this (also kept >= 1.2 x the per-tick travel so a window cannot be skipped)

// ---------------------------------------------------------------- movement (pitch §11)
constexpr float kMoveSpeedPerTick = 0.09f;             // distance units per tick at full leg condition
constexpr float kRetreatSpeedMult = 0.6f;              // pitch §11: backing away is slower than closing in
constexpr float kWindupMoveMult = 0.2f;
constexpr float kRecoveryMoveMult = 0.4f;
constexpr float kMinDistance = 8.f;
constexpr float kMaxDistance = 140.f;
constexpr float kStartDistance = 60.f;

// ---------------------------------------------------------------- AI (pitch §20, §8)
constexpr int kMinReactionTicks = 12;                  // pitch §20: never faster than ~200 ms
constexpr int kReactionTicks[kDifficultyCount] = {20, 15, 12};   // Easy / Normal / Hard
constexpr float kAnalysisDepth[kDifficultyCount] = {0.0f, 0.45f, 0.9f};  // pitch §8 "Поведенческое чтение"
constexpr float kPositionQuality[kDifficultyCount] = {0.35f, 0.65f, 0.95f};  // pitch §20 "выбор позиции"
constexpr float kParryTimingJitter[kDifficultyCount] = {5.0f, 3.5f, 2.0f};   // ticks of error when timing a parry
constexpr float kCounterChance[kDifficultyCount] = {0.15f, 0.30f, 0.50f};   // pitch §20 "частота сложных контратак"

// ---------------------------------------------------------------- match
constexpr int kMatchTimeLimitTicks = 20 * 60 * kTickHz;  // headless sims only: a draw after 20 min

}  // namespace tune
}  // namespace iv

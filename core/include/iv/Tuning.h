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
    120.f,  // Torso      pitch §9 "лучше всего бронирован"
    60.f,   // Reactor    pitch §9 "Задняя часть корпуса"
    70.f,   // ShoulderL  pitch §9 "Плечи и руки"
    70.f,   // ShoulderR  pitch §9
    55.f,   // ArmL       pitch §9
    55.f,   // ArmR       pitch §9
    90.f,   // LegL       pitch §9 "Ноги"
    90.f,   // LegR       pitch §9
};
constexpr float kMechanismMax[kZoneCount] = {40.f, 80.f, 50.f, 50.f, 50.f, 45.f, 45.f, 70.f, 70.f};  // pitch §14
constexpr float kSystemMax[kZoneCount] = {60.f, 100.f, 90.f, 60.f, 60.f, 50.f, 50.f, 70.f, 70.f};      // pitch §14

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
constexpr float kRearAngleDeg = 55.f;

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
constexpr int kWindupMinTicks = MsToTicks(300);        // pitch §5.2 (1): shortest legal heavy windup
constexpr int kWindupMaxChargeTicks = MsToTicks(1000); // pitch §5.2: extra hold that still adds power
constexpr int kChargeAudibleTicks = MsToTicks(250);    // pitch §8 "звук набирающего давление привода"
constexpr int kCommitDelayTicks = MsToTicks(100);      // pitch §5.2 (4): release -> irreversible Strike
constexpr int kHeavyStrikeTicks = MsToTicks(330);      // pitch §5.2: travel time of the arm
constexpr int kHeavyRecoveryTicks = MsToTicks(600);    // pitch §5.4
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

constexpr float kHeavyDamage = 10.5f;                   // pitch §5.2 base damage of a heavy strike
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
constexpr int kReverseWindowTicks[2] = {MsToTicks(110), MsToTicks(80)};  // pitch §6: "ответ на контратаку 70-110 мс"
constexpr int kMaxReverseReplies = 2;                  // pitch §7: "максимум 2 ответа", then clinch
constexpr float kBlockDamageMult = 0.25f;              // pitch §6: block "сильно снижает прямой урон"
constexpr float kBlockStabilityFactor = 0.7f;          // pitch §6: "всё равно уменьшает стабильность"
constexpr float kBlockArmLoad = 0.18f;                 // pitch §6: "нагружает блокирующую руку" (share of damage)
constexpr float kGuardEnergyPerTick = 0.03f;           // pitch §6: passive guard must not be free
constexpr float kParryEnergy = 4.f;
constexpr float kParryStabilityHit = 24.f;             // pitch §6: attacker's tempo breaks
constexpr int kParryRecoveryBonusTicks = MsToTicks(500);
constexpr int kCounterWindowTicks = MsToTicks(400);    // pitch §6: "короткое окно контратаки"
constexpr float kInterceptEnergy = 8.f;                // pitch §7
constexpr float kInterceptArmDamage = 0.35f;           // pitch §7: share of strike damage that hits the intercepted arm
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
constexpr float kGrabStability = 32.f;
constexpr float kGrabHeat = 3.f;
constexpr float kGrabDamage = 10.f;

// ---------------------------------------------------------------- weapon (pitch §13)
constexpr int kWeaponChargeTicks = MsToTicks(1800);    // pitch §13: "Удерживать цель несколько секунд"
constexpr float kWeaponDamage = 40.f;                  // pitch §13: "способно пробить броню или разрушить сустав"
constexpr float kWeaponMinDistance = 18.f;
constexpr float kWeaponBlockMult = 0.55f;
constexpr float kWeaponBaseAccuracy = 0.8f;
constexpr int kWeaponRecoveryTicks = MsToTicks(1200);  // pitch §13: the shoulder launcher is slow to close again

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

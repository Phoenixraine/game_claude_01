// Destructible building: a voxel grid of cells with a simple structural-support solver.
// Cells that lose support fall as physics debris (macro blocks of up to 2x2x2 cells).
// Supports a yaw rotation and an arbitrary polygonal footprint (mask) so worldgen buildings map directly.
// For hero buildings, TASK-009 supplies authored pre-fractured chunks that replace the cube cells.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "IVBuilding.generated.h"

class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UStaticMesh;

/** Rigid debris chunk with a lifetime. */
UCLASS()
class IMPACTVECTOR_API AIVDebris : public AActor
{
	GENERATED_BODY()

public:
	AIVDebris();
	virtual void Tick(float Dt) override;
	void Init(UStaticMesh* Mesh, UMaterialInterface* Mat, const FVector& Size, const FVector& Impulse, const FVector& Spin);
	static int32 LiveCount;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Mesh;
	float Age = 0.f, Life = 22.f;
	FVector BaseScale = FVector::OneVector;
};

UCLASS()
class IMPACTVECTOR_API AIVBuilding : public AActor
{
	GENERATED_BODY()

public:
	AIVBuilding();

	/** Center/YawDeg are world values; Size is the local bounding box (X along yaw, Y across, Z height) in cm.
	 *  FootprintLocal (optional) is a polygon in local XY (cm, relative to Center); cells outside it are empty.
	 *  HollowScale in (0,1) removes the inner part of the polygon (rings such as a stadium). */
	void Init(const FVector& Center, float YawDeg, const FVector& Size, UMaterialInterface* Mat, float CellSize,
		const TArray<FVector2D>& FootprintLocal = TArray<FVector2D>(), float HollowScale = 0.f);

	/** Destroy cells inside the sphere, then resolve structural support. Returns number of cells destroyed in total. */
	int32 ApplyBlast(const FVector& WorldCenter, float Radius, float Impulse);

	int32 AliveCount() const { return Alive; }

private:
	FIntVector Dim = FIntVector(1, 1, 1);
	FVector Origin = FVector::ZeroVector;     // local min corner
	FVector Size = FVector::OneVector;
	FVector CellSz = FVector::OneVector;
	TArray<uint8> Cells;                      // 1 = alive
	int32 Alive = 0;

	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> ISM;
	UPROPERTY() TObjectPtr<UMaterialInterface> Material;
	UPROPERTY() TObjectPtr<UStaticMesh> CubeMesh;

	int32 Idx(int32 X, int32 Y, int32 Z) const { return (Z * Dim.Y + Y) * Dim.X + X; }
	FVector CellCenterLocal(int32 X, int32 Y, int32 Z) const { return Origin + FVector((X + 0.5f) * CellSz.X, (Y + 0.5f) * CellSz.Y, (Z + 0.5f) * CellSz.Z); }
	FVector CellCenterWorld(int32 X, int32 Y, int32 Z) const { return GetActorTransform().TransformPosition(CellCenterLocal(X, Y, Z)); }
	void RebuildInstances();
	int32 ResolveSupport(const FVector& BlastCenterWorld, float Impulse);
	void SpawnDebrisForCells(const TArray<FIntVector>& Falling, const FVector& BlastCenterWorld, float Impulse);
};

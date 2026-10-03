// Destructible building: a voxel grid of cells with a simple structural-support solver.
// Cells that lose support fall as physics debris (macro blocks of up to 2x2x2 cells).
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

	/** Size is the full footprint+height in cm, Center is the building centre. CellSize is the nominal voxel edge. */
	void Init(const FVector& Center, const FVector& Size, UMaterialInterface* Mat, float CellSize);

	/** Destroy cells inside the sphere, then resolve structural support. Returns number of cells destroyed in total. */
	int32 ApplyBlast(const FVector& WorldCenter, float Radius, float Impulse);

	int32 AliveCount() const { return Alive; }
	FBox GetBounds() const { return FBox(Origin, Origin + Size); }

private:
	FIntVector Dim = FIntVector(1, 1, 1);
	FVector Origin = FVector::ZeroVector;     // min corner
	FVector Size = FVector::OneVector;
	FVector CellSz = FVector::OneVector;
	TArray<uint8> Cells;                      // 1 = alive
	int32 Alive = 0;

	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> ISM;
	UPROPERTY() TObjectPtr<UMaterialInterface> Material;
	UPROPERTY() TObjectPtr<UStaticMesh> CubeMesh;

	int32 Idx(int32 X, int32 Y, int32 Z) const { return (Z * Dim.Y + Y) * Dim.X + X; }
	FVector CellCenter(int32 X, int32 Y, int32 Z) const { return Origin + FVector((X + 0.5f) * CellSz.X, (Y + 0.5f) * CellSz.Y, (Z + 0.5f) * CellSz.Z); }
	void RebuildInstances();
	int32 ResolveSupport(const FVector& BlastCenter, float Impulse);
	void SpawnDebrisForCells(const TArray<FIntVector>& Falling, const FVector& BlastCenter, float Impulse);
};

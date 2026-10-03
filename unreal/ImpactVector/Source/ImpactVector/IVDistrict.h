// Loads a worldgen `district.json` (+ heightmap.r16) and builds the playable arena at runtime:
// terrain mesh with collision, roads, sea, destructible buildings, hero structures, props and spawn points.
// Coordinate mapping (district metres -> Unreal cm):  X_ue = y_d * 100,  Y_ue = x_d * 100,  Z_ue = z * 100,  yaw_ue = 90 - yaw_d.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "IVDistrict.generated.h"

class UProceduralMeshComponent;
class UInstancedStaticMeshComponent;
class UStaticMeshComponent;
class AIVBuilding;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UStaticMesh;

struct FIVDistrictBuilding
{
	FString Id;
	FVector Center = FVector::ZeroVector;   // ue cm
	FVector Size = FVector::OneVector;      // local box cm
	float YawDeg = 0.f;
	bool bGlass = false;
	bool bActive = false;
	bool bHero = false;
	TWeakObjectPtr<AIVBuilding> Actor;
};

UCLASS()
class IMPACTVECTOR_API AIVDistrict : public AActor
{
	GENERATED_BODY()

public:
	AIVDistrict();

	/** Returns false if files are missing or malformed. */
	bool Load(const FString& JsonPath, const FString& HeightPath);
	bool IsLoaded() const { return bLoaded; }

	int32 BlastAt(const FVector& Center, float Radius, float Impulse);
	/** Nearest standing building in front of `From` (along Dir) between MinD and MaxD cm; returns its base centre and size. */
	bool FindBuildingNear(const FVector& From, const FVector& Dir, float MinD, float MaxD, FVector& OutBase, FVector& OutSize) const;
	bool GetPoi(const FString& Id, FVector& OutLocationUE, float& OutYawUE) const;
	float SampleHeightCm(float XUe, float YUe) const;

	static FVector ToUE(double Xd, double Yd, double Z) { return FVector(Yd * 100.0, Xd * 100.0, Z * 100.0); }
	static float YawToUE(float YawD) { return 90.f - YawD; }

private:
	bool bLoaded = false;
	int32 Res = 0;
	TArray<uint16> Heights;
	double XMin = -800, YMin = -400, CellM = 1.5873;

	TMap<FString, TPair<FVector, float>> Pois;
	TArray<FIVDistrictBuilding> Buildings;

	UPROPERTY() TObjectPtr<USceneComponent> Root;
	UPROPERTY() TObjectPtr<UProceduralMeshComponent> Terrain;
	UPROPERTY() TObjectPtr<UProceduralMeshComponent> Roads;
	UPROPERTY() TObjectPtr<UStaticMeshComponent> Sea;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Concrete;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Glass;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Hero;        // static hero parts (overpass, crane, chimneys)
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Cars;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> TreeTrunks;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> TreeCrowns;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Lamps;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Containers;
	UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> Chimneys;
	UPROPERTY() TObjectPtr<UStaticMesh> CubeMesh;
	UPROPERTY() TObjectPtr<UStaticMesh> CylMesh;
	UPROPERTY() TObjectPtr<UStaticMesh> SphereMesh;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> FacadeConcrete;
	UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> FacadeGlass;

	double HeightM(int32 Col, int32 Row) const;
	double SampleHeightM(double Xd, double Yd) const;
	void BuildTerrain();
	void BuildRoads(const TArray<TSharedPtr<FJsonValue>>& RoadsJson);
	void BuildBuildings(const TArray<TSharedPtr<FJsonValue>>& BuildingsJson);
	void BuildProps(const TArray<TSharedPtr<FJsonValue>>& PropsJson);
	void BuildPort(const TSharedPtr<FJsonObject>& Infra);
	void BuildHeroStatics(const TSharedPtr<FJsonObject>& B);
	void RebuildStaticInstances();
	UMaterialInstanceDynamic* MakeMID(const TCHAR* Path, UMaterialInterface* Fallback);

	TArray<FTransform> HeroStaticTransforms;
};

#include "IVBuilding.h"
#include "IVFXManager.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

int32 AIVDebris::LiveCount = 0;
static const int32 GMaxDebris = 380;

// ------------------------------------------------------------------------------------------------------------
AIVDebris::AIVDebris()
{
	PrimaryActorTick.bCanEverTick = true;
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	RootComponent = Mesh;
	Mesh->SetCollisionProfileName(TEXT("PhysicsActor"));
	Mesh->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
	Mesh->SetCastShadow(true);
	Mesh->SetLinearDamping(0.15f);
	Mesh->SetAngularDamping(0.25f);
}

void AIVDebris::Init(UStaticMesh* InMesh, UMaterialInterface* Mat, const FVector& SizeCm, const FVector& Impulse, const FVector& Spin)
{
	Mesh->SetStaticMesh(InMesh);
	if (Mat) Mesh->SetMaterial(0, Mat);
	BaseScale = SizeCm / 100.f;
	Mesh->SetWorldScale3D(BaseScale);
	Mesh->SetSimulatePhysics(true);
	Mesh->SetEnableGravity(true);
	Mesh->SetPhysicsLinearVelocity(Impulse);
	Mesh->SetPhysicsAngularVelocityInDegrees(Spin);
	Life = 16.f + (GetUniqueID() % 7);
	++LiveCount;
}

void AIVDebris::EndPlay(const EEndPlayReason::Type Reason)
{
	Super::EndPlay(Reason);
	--LiveCount;
}

void AIVDebris::Tick(float Dt)
{
	Super::Tick(Dt);
	Age += Dt;
	if (Age > Life - 3.f)
	{
		const float K = FMath::Clamp((Life - Age) / 3.f, 0.f, 1.f);
		Mesh->SetWorldScale3D(BaseScale * K);
	}
	if (Age >= Life) Destroy();
}

// ------------------------------------------------------------------------------------------------------------
AIVBuilding::AIVBuilding()
{
	PrimaryActorTick.bCanEverTick = false;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeF(TEXT("/Engine/BasicShapes/Cube.Cube"));
	CubeMesh = CubeF.Object;
	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
	ISM = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Cells"));
	ISM->SetupAttachment(Root);
	ISM->SetStaticMesh(CubeMesh);
	ISM->SetCollisionProfileName(TEXT("BlockAll"));
}

static bool PointInPoly(const FVector2D& P, const TArray<FVector2D>& Poly)
{
	bool In = false;
	for (int32 i = 0, j = Poly.Num() - 1; i < Poly.Num(); j = i++)
	{
		if (((Poly[i].Y > P.Y) != (Poly[j].Y > P.Y)) && (P.X < (Poly[j].X - Poly[i].X) * (P.Y - Poly[i].Y) / (Poly[j].Y - Poly[i].Y) + Poly[i].X))
			In = !In;
	}
	return In;
}

void AIVBuilding::Init(const FVector& Center, float YawDeg, const FVector& InSize, UMaterialInterface* Mat, float CellSize,
	const TArray<FVector2D>& FootprintLocal, float HollowScale)
{
	SetActorLocationAndRotation(Center, FRotator(0.f, YawDeg, 0.f));
	Size = InSize;
	Origin = -InSize * 0.5f;
	Dim = FIntVector(FMath::Max(1, FMath::RoundToInt(InSize.X / CellSize)), FMath::Max(1, FMath::RoundToInt(InSize.Y / CellSize)), FMath::Max(1, FMath::RoundToInt(InSize.Z / CellSize)));
	CellSz = FVector(InSize.X / Dim.X, InSize.Y / Dim.Y, InSize.Z / Dim.Z);
	Cells.Init(1, Dim.X * Dim.Y * Dim.Z);

	if (FootprintLocal.Num() >= 3)
	{
		TArray<FVector2D> Inner;
		if (HollowScale > 0.f) for (const FVector2D& P : FootprintLocal) Inner.Add(P * HollowScale);
		for (int32 z = 0; z < Dim.Z; ++z)
			for (int32 y = 0; y < Dim.Y; ++y)
				for (int32 x = 0; x < Dim.X; ++x)
				{
					const FVector L = CellCenterLocal(x, y, z);
					const FVector2D P(L.X, L.Y);
					bool In = PointInPoly(P, FootprintLocal);
					if (In && Inner.Num() >= 3 && PointInPoly(P, Inner)) In = false;
					// ground floor must stay connected: keep the ring continuous even when hollow
					if (!In) Cells[Idx(x, y, z)] = 0;
				}
	}
	Alive = 0;
	for (uint8 C : Cells) Alive += C;
	Material = Mat;
	if (Mat) ISM->SetMaterial(0, Mat);
	RebuildInstances();
}

void AIVBuilding::RebuildInstances()
{
	ISM->ClearInstances();
	TArray<FTransform> T;
	T.Reserve(Alive);
	const FVector Scale = CellSz / 100.f;
	for (int32 z = 0; z < Dim.Z; ++z)
		for (int32 y = 0; y < Dim.Y; ++y)
			for (int32 x = 0; x < Dim.X; ++x)
				if (Cells[Idx(x, y, z)]) T.Add(FTransform(FRotator::ZeroRotator, CellCenterLocal(x, y, z), Scale));
	ISM->AddInstances(T, false, false);
}

int32 AIVBuilding::ApplyBlast(const FVector& C, float Radius, float Impulse)
{
	int32 Killed = 0;
	TArray<FIntVector> Destroyed;
	for (int32 z = 0; z < Dim.Z; ++z)
		for (int32 y = 0; y < Dim.Y; ++y)
			for (int32 x = 0; x < Dim.X; ++x)
			{
				if (!Cells[Idx(x, y, z)]) continue;
				const FVector P = CellCenterWorld(x, y, z);
				// ragged crater edge
				const float Jit = 0.82f + 0.18f * FMath::Frac(FMath::Sin(x * 12.9898f + y * 78.233f + z * 37.719f) * 43758.5453f);
				if (FVector::Dist(P, C) <= Radius * Jit)
				{
					Cells[Idx(x, y, z)] = 0;
					Destroyed.Add(FIntVector(x, y, z));
					++Killed;
				}
			}
	Alive -= Killed;
	if (Killed == 0) return 0;

	SpawnDebrisForCells(Destroyed, C, Impulse * 1.4f);
	const int32 Extra = ResolveSupport(C, Impulse);
	RebuildInstances();

	if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
	{
		FX->SpawnDust(C, Radius * 1.2f, FMath::Clamp(Killed / 3, 6, 40));
		FX->SpawnSparks(C, FVector::UpVector, 20, 5000.f);
	}
	return Killed + Extra;
}

int32 AIVBuilding::ResolveSupport(const FVector& BlastCenter, float Impulse)
{
	// Stability relaxation: the ground row has 100; support passes straight up, loses 34 per lateral step.
	const int32 N = Cells.Num();
	TArray<int8> Stab;
	Stab.Init(0, N);
	TArray<int32> Queue;
	for (int32 y = 0; y < Dim.Y; ++y)
		for (int32 x = 0; x < Dim.X; ++x)
			if (Cells[Idx(x, y, 0)]) { Stab[Idx(x, y, 0)] = 100; Queue.Add(Idx(x, y, 0)); }

	auto Relax = [&](int32 From, int32 To, int32 Cost)
	{
		if (!Cells[To]) return;
		const int32 S = Stab[From] - Cost;
		if (S > Stab[To]) { Stab[To] = (int8)S; Queue.Add(To); }
	};
	for (int32 qi = 0; qi < Queue.Num(); ++qi)
	{
		const int32 Cur = Queue[qi];
		const int32 x = Cur % Dim.X, y = (Cur / Dim.X) % Dim.Y, z = Cur / (Dim.X * Dim.Y);
		if (z + 1 < Dim.Z) Relax(Cur, Idx(x, y, z + 1), 0);
		if (x > 0) Relax(Cur, Idx(x - 1, y, z), 34);
		if (x + 1 < Dim.X) Relax(Cur, Idx(x + 1, y, z), 34);
		if (y > 0) Relax(Cur, Idx(x, y - 1, z), 34);
		if (y + 1 < Dim.Y) Relax(Cur, Idx(x, y + 1, z), 34);
	}

	TArray<FIntVector> Falling;
	for (int32 z = 0; z < Dim.Z; ++z)
		for (int32 y = 0; y < Dim.Y; ++y)
			for (int32 x = 0; x < Dim.X; ++x)
			{
				const int32 I = Idx(x, y, z);
				if (Cells[I] && Stab[I] <= 0) { Falling.Add(FIntVector(x, y, z)); Cells[I] = 0; }
			}
	Alive -= Falling.Num();
	if (Falling.Num() > 0)
	{
		SpawnDebrisForCells(Falling, BlastCenter, Impulse);
		if (AIVFXManager* FX = AIVFXManager::Get(GetWorld()))
		{
			FVector Mean = FVector::ZeroVector;
			for (const FIntVector& F : Falling) Mean += CellCenterWorld(F.X, F.Y, F.Z);
			Mean /= Falling.Num();
			FX->SpawnDust(Mean, FMath::Min(Size.X, Size.Y) * 0.6f, FMath::Clamp(Falling.Num() / 4, 8, 60), 1.4f);
		}
	}
	return Falling.Num();
}

void AIVBuilding::SpawnDebrisForCells(const TArray<FIntVector>& Cs, const FVector& BlastCenter, float Impulse)
{
	// group into 2x2x2 macro blocks, one rigid body per block
	TMap<int64, TArray<FIntVector>> Groups;
	for (const FIntVector& C : Cs)
	{
		const int64 Key = (int64(C.Z / 2) * 4096 + (C.Y / 2)) * 4096 + (C.X / 2);
		Groups.FindOrAdd(Key).Add(C);
	}
	UWorld* W = GetWorld();
	FRandomStream R(Cs.Num() * 7 + 13);
	const FTransform Xf = GetActorTransform();
	for (auto& KV : Groups)
	{
		if (AIVDebris::LiveCount >= GMaxDebris) break;
		FBox B(ForceInit);
		for (const FIntVector& C : KV.Value)
		{
			const FVector P = CellCenterLocal(C.X, C.Y, C.Z);
			B += P - CellSz * 0.5f;
			B += P + CellSz * 0.5f;
		}
		FActorSpawnParameters Sp;
		Sp.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		const FVector WorldCenter = Xf.TransformPosition(B.GetCenter());
		AIVDebris* D = W->SpawnActor<AIVDebris>(WorldCenter, GetActorRotation(), Sp);
		if (!D) continue;
		const FVector Out = (WorldCenter - BlastCenter).GetSafeNormal();
		D->Init(CubeMesh, Material, B.GetSize() * 0.97f, Out * Impulse * R.FRandRange(0.4f, 1.1f) + FVector(0, 0, Impulse * 0.25f), R.VRand() * R.FRandRange(10.f, 60.f));
	}
}

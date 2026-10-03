#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "IVHUD.generated.h"

/** Minimal sensor-style overlay: crosshair and target bracket. Replaced by the cockpit UI later. */
UCLASS()
class IMPACTVECTOR_API AIVHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;
};

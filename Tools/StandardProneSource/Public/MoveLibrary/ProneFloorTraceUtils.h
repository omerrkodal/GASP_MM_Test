// Copyright Epic Games, Inc. All Rights Reserved.
#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "DefaultMovementSet/ProneFloorData.h"
#include "ProneFloorTraceUtils.generated.h"

class UMoverComponent;

/** Visual floor samples from fixed character offsets. Does not modify collision. */
UCLASS()
class MOVER_API UProneFloorTraceUtils : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Resolve a fixed offset using heading projected onto the Mover up plane. */
    UFUNCTION(BlueprintPure, Category="Mover|Prone")
    static FVector GetProbeAnchor(const FVector& Origin, const FVector& Heading, const FVector& UpDirection, const FVector& Offset);

    /** Sample once after movement. Simulated proxies use the serialized samples. */
    static FProneFloorData SampleProneFloorData(const UMoverComponent* MoverComp);
};

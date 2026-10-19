// Copyright Epic Games, Inc. All Rights Reserved.
#pragma once

#include "CoreMinimal.h"
#include "ProneFloorData.generated.h"

/** One world-space floor sample. Matches the Does Hit?, Normal, Location layout of S_FloorData. */
USTRUCT(BlueprintType, meta=(DisplayName="Mover Floor Data"))
struct MOVER_API FMoverFloorData
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Floor", meta=(DisplayName="Does Hit?"))
    bool bDoesHit = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Floor")
    FVector Normal = FVector::UpVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Floor")
    FVector Location = FVector::ZeroVector;
};

/** Independent cached world-space tip/back/center probes and selected capsule alignment result. */
USTRUCT(BlueprintType)
struct MOVER_API FProneFloorData
{
    GENERATED_BODY()

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Mover|Prone")
    bool bTipHasFloor = false;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Mover|Prone")
    bool bBackHasFloor = false;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Mover|Prone")
    FVector TipFloorNormal = FVector::ZeroVector;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Mover|Prone")
    FVector BackFloorNormal = FVector::ZeroVector;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Mover|Prone")
    FVector TipFloorLocation = FVector::ZeroVector;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Mover|Prone")
    FVector BackFloorLocation = FVector::ZeroVector;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Mover|Prone")
    FVector CombinedFloorNormal = FVector::ZeroVector;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Mover|Prone")
    FVector CombinedFloorLocation = FVector::ZeroVector;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Mover|Prone")
    bool bCenterHasFloor = false;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Mover|Prone")
    FVector CenterFloorNormal = FVector::ZeroVector;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Mover|Prone")
    FVector CenterFloorLocation = FVector::ZeroVector;

    bool HasFloor() const { return bTipHasFloor || bBackHasFloor || bCenterHasFloor; }

    void UpdateCombined()
    {
        if (bTipHasFloor && bBackHasFloor)
        {
            CombinedFloorNormal = (TipFloorNormal + BackFloorNormal).GetSafeNormal();
            CombinedFloorLocation = (TipFloorLocation + BackFloorLocation) * 0.5;
        }
        else if (bTipHasFloor)
        {
            CombinedFloorNormal = TipFloorNormal;
            CombinedFloorLocation = TipFloorLocation;
        }
        else if (bBackHasFloor)
        {
            CombinedFloorNormal = BackFloorNormal;
            CombinedFloorLocation = BackFloorLocation;
        }
        else if (bCenterHasFloor)
        {
            CombinedFloorNormal = CenterFloorNormal;
            CombinedFloorLocation = CenterFloorLocation;
        }
        else
        {
            CombinedFloorNormal = FVector::ZeroVector;
            CombinedFloorLocation = FVector::ZeroVector;
        }
    }
};

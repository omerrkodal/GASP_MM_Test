// Copyright Epic Games, Inc. All Rights Reserved.
#include "MoveLibrary/ProneFloorTraceUtils.h"
#include "Components/PrimitiveComponent.h"
#include "DefaultMovementSet/CharacterMoverComponent.h"
#include "DefaultMovementSet/Settings/StanceSettings.h"
#include "DefaultMovementSet/Settings/CommonLegacyMovementSettings.h"
#include "MoveLibrary/MovementUtils.h"
#include "MoveLibrary/FloorQueryUtils.h"
#include "MoverComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "DrawDebugHelpers.h"
#include "HAL/IConsoleManager.h"

namespace
{
TAutoConsoleVariable<int32> CVarDrawProneFloorTraces(TEXT("mover.debug.DrawProneFloorTraces"), 0,
    TEXT("Draw animated-root prone floor probes: Tip cyan, Back magenta, Center yellow; green hits, red misses, orange unwalkable."), ECVF_Cheat);
}

FVector UProneFloorTraceUtils::GetProbeAnchor(const FVector& Origin, const FVector& Heading,
    const FVector& UpDirection, const FVector& Offset)
{
    const FVector Up = UpDirection.GetSafeNormal();
    if (Up.IsNearlyZero()) { return Origin; }
    FVector Forward = FVector::VectorPlaneProject(Heading, Up).GetSafeNormal();
    if (Forward.IsNearlyZero())
    {
        Forward = FVector::VectorPlaneProject(FVector::ForwardVector, Up).GetSafeNormal();
        if (Forward.IsNearlyZero()) { Forward = FVector::VectorPlaneProject(FVector::RightVector, Up).GetSafeNormal(); }
    }
    const FVector Right = FVector::CrossProduct(Up, Forward).GetSafeNormal();
    return Origin + Forward * Offset.X + Right * Offset.Y + Up * Offset.Z;
}

FProneFloorData UProneFloorTraceUtils::SampleProneFloorData(const UMoverComponent* MoverComp)
{
    FProneFloorData Data;
    if (!MoverComp) { return Data; }
    const UCharacterMoverComponent* CharacterMover = Cast<UCharacterMoverComponent>(MoverComp);
    const UPrimitiveComponent* Primitive = Cast<UPrimitiveComponent>(MoverComp->GetUpdatedComponent());
    if (!CharacterMover || !CharacterMover->IsOnGround() || !Primitive || !Primitive->GetWorld()) { return Data; }
    const UStanceSettings* Settings = MoverComp->FindSharedSettings<UStanceSettings>();
    if (!Settings) { return Data; }
    const FVector Up = MoverComp->GetUpDirection().GetSafeNormal();
    if (Up.IsNearlyZero()) { return Data; }
    const FTransform UpdatedToWorld = Primitive->GetComponentTransform();
    FVector Origin = UpdatedToWorld.GetLocation();
    FVector Heading = UpdatedToWorld.GetUnitAxis(EAxis::X);
    // Use the animated character root, including Offset Root Bone translation/facing.
    // Only value data is read here; skeletal pose access stays on the game thread.
    // Before the first valid mesh snapshot, retain the original component fallback.
    CharacterMover->GetProneFloorProbeFrame(UpdatedToWorld, Origin, Heading);
    const UCommonLegacyMovementSettings* MovementSettings = MoverComp->FindSharedSettings<UCommonLegacyMovementSettings>();
    const float MaxSlopeCosine = MovementSettings ? MovementSettings->MaxWalkSlopeCosine : 0.71f;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(ProneFloorProbes), false, Primitive->GetOwner());
    FCollisionResponseParams Response;
    UMovementUtils::InitCollisionParams(Primitive, Params, Response);
    auto Sample = [&](const FVector& Offset, const TCHAR* Name, const FColor& Color,
        bool& HasFloor, FVector& Normal, FVector& ImpactPoint)
    {
        const FVector Anchor = GetProbeAnchor(Origin, Heading, Up, Offset);
        const FVector Start = Anchor + Up * FMath::Max(0.f, Settings->ProneFloorProbeStartOffset);
        const FVector End = Anchor - Up * FMath::Max(1.f, Settings->ProneFloorTraceDistance);
        FHitResult Hit;
        const bool bHit = Primitive->GetWorld()->LineTraceSingleByChannel(Hit, Start, End,
            Primitive->GetCollisionObjectType(), Params, Response);
        if (bHit && UFloorQueryUtils::IsHitSurfaceWalkable(Hit, Up, MaxSlopeCosine))
        {
            HasFloor = true;
            Normal = Hit.ImpactNormal.GetSafeNormal();
            ImpactPoint = Hit.ImpactPoint;
        }
#if ENABLE_DRAW_DEBUG
        if (CVarDrawProneFloorTraces.GetValueOnAnyThread() && IsInGameThread())
        {
            UWorld* World = Primitive->GetWorld();
            const FColor ResultColor = HasFloor ? FColor::Green : (bHit ? FColor::Orange : FColor::Red);
            DrawDebugLine(World, Start, End, HasFloor ? Color : ResultColor, false, 0.f, 0, 1.5f);
            DrawDebugPoint(World, Start, 7.f, Color, false, 0.f);
            DrawDebugString(World, Start + Up * 5.f, FString::Printf(TEXT("%s: %s"), Name,
                HasFloor ? TEXT("HIT") : (bHit ? TEXT("UNWALKABLE") : TEXT("MISS"))), nullptr, ResultColor, 0.f, true);
            if (bHit)
            {
                DrawDebugSphere(World, Hit.ImpactPoint, 3.f, 8, ResultColor, false, 0.f, 0, 1.f);
                DrawDebugDirectionalArrow(World, Hit.ImpactPoint, Hit.ImpactPoint + Hit.ImpactNormal * 25.f,
                    6.f, ResultColor, false, 0.f, 0, 1.5f);
            }
        }
#endif
    };
    Sample(Settings->ProneFloorTipOffset, TEXT("Tip"), FColor::Cyan, Data.bTipHasFloor, Data.TipFloorNormal, Data.TipFloorLocation);
    Sample(Settings->ProneFloorBackOffset, TEXT("Back"), FColor::Magenta, Data.bBackHasFloor, Data.BackFloorNormal, Data.BackFloorLocation);
    Sample(Settings->ProneFloorCenterOffset, TEXT("Center"), FColor::Yellow, Data.bCenterHasFloor, Data.CenterFloorNormal, Data.CenterFloorLocation);
    Data.UpdateCombined();
    return Data;
}

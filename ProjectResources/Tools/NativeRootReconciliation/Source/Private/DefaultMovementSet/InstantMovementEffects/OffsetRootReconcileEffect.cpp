// Project extension to UE 5.8 Mover.
#include "DefaultMovementSet/InstantMovementEffects/OffsetRootReconcileEffect.h"

#include "Components/SceneComponent.h"
#include "Engine/ScopedMovementUpdate.h"
#include "MoverComponent.h"
#include "MoverDataModelTypes.h"
#include "MoverSimulationTypes.h"
#include "MoveLibrary/MovementRecord.h"
#include "DefaultMovementSet/Settings/CommonLegacyMovementSettings.h"
#include "MoveLibrary/BasedMovementUtils.h"
#include "MoveLibrary/FloorQueryUtils.h"
#include "MoveLibrary/GroundMovementUtils.h"
#include "MoveLibrary/MovementUtils.h"
#include "MoveLibrary/MoverBlackboard.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(OffsetRootReconcileEffect)

bool FOffsetRootReconcileEffect::ApplyMovementEffect(FApplyMovementEffectParams& Params, FMoverSyncState& OutputState)
{
	USceneComponent* Component = Params.UpdatedComponent;
	const UMoverComponent* Mover = Params.MoverComp;
	FMoverDefaultSyncState* State = OutputState.SyncStateCollection.FindMutableDataByType<FMoverDefaultSyncState>();
	if (!Component || !Params.UpdatedPrimitive || !Mover || !State || !Params.StartState || !Params.TimeStep ||
		TargetRootWorldLocation.ContainsNaN() || !FMath::IsFinite(MaxStepDistance) ||
		!FMath::IsFinite(StopSpeed) || !FMath::IsFinite(Tolerance) || !FMath::IsFinite(MaxOffset) ||
		MaxStepDistance <= 0.f || StopSpeed < 0.f || Tolerance < 0.f || MaxOffset <= Tolerance ||
		!Mover->HasGameplayTagInState(OutputState, Mover_IsOnGround, false))
	{
		return false;
	}

	const FVector Up = Mover->GetUpDirection().GetSafeNormal();
	const FVector Velocity = State->GetVelocity_WorldSpace();
	const FVector AngularVelocity = State->GetAngularVelocityDegrees_WorldSpace();
	if (Up.IsNearlyZero() || FVector::VectorPlaneProject(Velocity, Up).SizeSquared() > FMath::Square(StopSpeed))
	{
		return false;
	}
	// A request captured last frame must never hold back newly requested movement/jumping.
	if (const FCharacterDefaultInputs* Inputs = Params.StartState->InputCmd.InputCollection.FindDataByType<FCharacterDefaultInputs>())
	{
		if (Inputs->bIsJumpJustPressed || !Inputs->GetMoveInput().IsNearlyZero())
		{
			return false;
		}
	}
	const FVector OriginalLocation = Component->GetComponentLocation();
	const FVector Offset = FVector::VectorPlaneProject(TargetRootWorldLocation - OriginalLocation, Up);
	if (Offset.SizeSquared() <= FMath::Square(Tolerance) || Offset.SizeSquared() > FMath::Square(MaxOffset))
	{
		return false;
	}
	const UCommonLegacyMovementSettings* Settings = Mover->FindSharedSettings<UCommonLegacyMovementSettings>();
	UMoverBlackboard* Blackboard = Mover->GetSimBlackboard_Mutable();
	if (!Settings || !Blackboard)
	{
		return false;
	}
	FMovingComponentSet MovingComps(const_cast<UMoverComponent*>(Mover));
	FFloorCheckSettings FloorSettings;
	FloorSettings.FloorSweepDistance = Settings->FloorSweepDistance;
	FloorSettings.MaxWalkSlopeCosine = Settings->MaxWalkSlopeCosine;
	FloorSettings.bUseFlatBaseForFloorChecks = Settings->bUseFlatBaseForFloorChecks;
	FloorSettings.PerchRadiusThreshold = Settings->PerchRadiusThreshold;
	FFloorCheckResult Floor;
	if (!Blackboard->TryGet(CommonBlackboard::LastFloorResult, Floor))
	{
		UFloorQueryUtils::FindFloor(MovingComps, FloorSettings, OriginalLocation, Floor);
	}
	if (!Floor.IsWalkableFloor() || Floor.HitResult.bStartPenetrating)
	{
		return false;
	}

	const FVector PlanarStep = Offset.GetClampedToMaxSize(MaxStepDistance);
	const FVector RampStep = UGroundMovementUtils::ComputeDeflectedMoveOntoRamp(
		PlanarStep, Up, Floor.HitResult, Settings->MaxWalkSlopeCosine, Floor.bLineTrace);
	const FQuat Rotation = Component->GetComponentQuat();
	FScopedMovementUpdate ScopedCorrection(Component, EScopedUpdate::DeferredUpdates);
	// Deliberately separate from walking's movement record: never generate locomotion velocity.
	FMovementRecord CorrectionRecord;
	CorrectionRecord.SetDeltaSeconds(FMath::Max(Params.TimeStep->StepMs * 0.001f, UE_SMALL_NUMBER));
	FHitResult Hit(1.f);
	UMovementUtils::TrySafeMoveUpdatedComponent(MovingComps, RampStep, Rotation, true,
		Hit, ETeleportType::None, CorrectionRecord);
	if (Hit.bStartPenetrating)
	{
		ScopedCorrection.RevertMove();
		return false;
	}
	if (Hit.IsValidBlockingHit() && Hit.Time > 0.f &&
		UFloorQueryUtils::IsHitSurfaceWalkable(Hit, Up, Settings->MaxWalkSlopeCosine))
	{
		// Continue only over a walkable ramp; walls stop the correction without sliding.
		const FVector Remainder = UGroundMovementUtils::ComputeDeflectedMoveOntoRamp(
			PlanarStep * (1.f - Hit.Time), Up, Hit, Settings->MaxWalkSlopeCosine, false);
		UMovementUtils::TrySafeMoveUpdatedComponent(MovingComps, Remainder, Rotation, true,
			Hit, ETeleportType::None, CorrectionRecord);
	}
	if (Hit.bStartPenetrating || FVector::DotProduct(Component->GetComponentLocation() - OriginalLocation, PlanarStep) <= UE_SMALL_NUMBER)
	{
		ScopedCorrection.RevertMove();
		return false;
	}
	UFloorQueryUtils::FindFloor(MovingComps, FloorSettings, Component->GetComponentLocation(), Floor);
	if (!Floor.IsWalkableFloor() || Floor.HitResult.bStartPenetrating)
	{
		// Reconciliation must not pull an idle pawn off a ledge or onto an unwalkable slope.
		ScopedCorrection.RevertMove();
		return false;
	}
	UGroundMovementUtils::TryMoveToAdjustHeightAboveFloor(MovingComps, Floor,
		Settings->MaxWalkSlopeCosine, CorrectionRecord);

	FRelativeBaseInfo BaseInfo;
	if (UBasedMovementUtils::IsADynamicBase(Floor.HitResult.GetComponent()))
	{
		BaseInfo.SetFromFloorResult(Floor, Component->GetComponentLocation(), Up);
		Blackboard->Set(CommonBlackboard::LastFoundDynamicMovementBase, BaseInfo);
	}
	else
	{
		Blackboard->Invalidate(CommonBlackboard::LastFoundDynamicMovementBase);
	}
	Blackboard->Set(CommonBlackboard::LastFloorResult, Floor);
	State->SetTransforms_WorldSpace(Component->GetComponentLocation(), Component->GetComponentRotation(),
		Velocity, AngularVelocity, BaseInfo.MovementBase.Get(), BaseInfo.BoneName);
	Component->ComponentVelocity = Velocity;
	return true;
}

FInstantMovementEffect* FOffsetRootReconcileEffect::Clone() const
{
	return new FOffsetRootReconcileEffect(*this);
}

void FOffsetRootReconcileEffect::NetSerialize(FArchive& Ar)
{
	Super::NetSerialize(Ar);
	Ar << TargetRootWorldLocation;
	Ar << MaxStepDistance;
	Ar << StopSpeed;
	Ar << Tolerance;
	Ar << MaxOffset;
}

UScriptStruct* FOffsetRootReconcileEffect::GetScriptStruct() const
{
	return StaticStruct();
}

FString FOffsetRootReconcileEffect::ToSimpleString() const
{
	return TEXT("Swept offset-root position reconciliation");
}

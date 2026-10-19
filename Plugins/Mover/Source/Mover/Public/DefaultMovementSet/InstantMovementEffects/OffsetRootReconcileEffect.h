// Project extension to UE 5.8 Mover.
#pragma once

#include "InstantMovementEffect.h"
#include "OffsetRootReconcileEffect.generated.h"

/** Position-only reconciliation of a stopped capsule toward its accumulated animated root.
 * Scheduled by CharacterMover on the game thread and replayed as part of Mover simulation.
 * The correction has no linear/angular velocity contribution and emits no teleport event.
 */
USTRUCT()
struct MOVER_API FOffsetRootReconcileEffect : public FInstantMovementEffect
{
	GENERATED_BODY()

	UPROPERTY()
	FVector TargetRootWorldLocation = FVector::ZeroVector;
	UPROPERTY()
	float MaxStepDistance = 0.f;
	UPROPERTY()
	float StopSpeed = 5.f;
	UPROPERTY()
	float Tolerance = 1.f;
	UPROPERTY()
	float MaxOffset = 200.f;

	virtual bool ApplyMovementEffect(FApplyMovementEffectParams& Params, FMoverSyncState& OutputState) override;
	virtual FInstantMovementEffect* Clone() const override;
	virtual void NetSerialize(FArchive& Ar) override;
	virtual UScriptStruct* GetScriptStruct() const override;
	virtual FString ToSimpleString() const override;
};

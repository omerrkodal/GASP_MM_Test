// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "MoverComponent.h"
#include "DefaultMovementSet/LayeredMoves/MontageStateProvider.h"
#include "MovementModifiers/StanceModifier.h"
#include "DefaultMovementSet/ProneFloorData.h"
#include "CharacterMoverComponent.generated.h"

#define UE_API MOVER_API

/**
 * Fires when a stance is changed, if stance handling is enabled (see @SetHandleStanceChanges)
 * Note: If a stance was just Activated it will fire with an invalid OldStance
 *		 If a stance was just Deactivated it will fire with an invalid NewStance
 */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FMover_OnStanceChanged, EStanceMode, OldStance, EStanceMode, NewStance);



/** 
* Character Mover Component: this is a specialization of the core Mover Component that is set up with a 
* classic character in mind. Defaults and extended functionality, such as jumping and simple montage replication, 
* are intended to support features similar to UE's ACharacter actor type.
*/
UCLASS(MinimalAPI, BlueprintType, Blueprintable, meta = (BlueprintSpawnableComponent))
class UCharacterMoverComponent : public UMoverComponent
{
	GENERATED_BODY()
	
public:
	UE_API UCharacterMoverComponent();
	
	UE_API virtual void BeginPlay() override;

	/** Game-thread bridge from the ABP's cached world-space offset root. Call once per frame.
	 * Queues a bounded swept position correction only while grounded and stopped.
	 * bRootIsAccumulating must describe the evaluated node's Accumulate translation mode.
	 * CurveValue is the curve-backed radius including its blend-out hold. It starts
	 * correction; an in-progress correction may finish after this value reaches zero.
	 * This does not apply root-motion velocity, change facing, or teleport the actor.
	 * Returns whether a correction was queued, not whether collision allowed it.
	 */
	UFUNCTION(BlueprintCallable, Category="Mover|Offset Root", meta=(AdvancedDisplay="CorrectionSpeed,StopSpeed,Tolerance,MaxOffset"))
	UE_API bool ReconcileOffsetRootOnStop(FVector AnimatedRootWorldLocation, float CurveValue,
		bool bRootIsAccumulating, float CorrectionSpeed = 150.f, float StopSpeed = 5.f,
		float Tolerance = 1.f, float MaxOffset = 200.f);

	/** Copy on game-thread PostEvaluateAnimation to an ABP float. Thread-safe radius
	 * evaluation reads that float and uses max(curve radius, copied hold).
	 */
	UFUNCTION(BlueprintPure, Category="Mover|Offset Root")
	float GetOffsetRootReconciliationRadiusHold() const { return OffsetRootReconciliationRadiusHold; }


	// Returns whether this component is tasked with handling jump input or not
	UFUNCTION(BlueprintGetter)
	UE_API bool GetHandleJump() const;

	// If true, this component will handle default character inputs for jumping
	UFUNCTION(BlueprintSetter)
	UE_API void SetHandleJump(bool bInHandleJump);

	// Returns whether this component is tasked with handling character stance changes, including crouching and prone
	UFUNCTION(BlueprintGetter)
	UE_API bool GetHandleStanceChanges() const;

	// If true, this component will process stancing changes and crouching/prone inputs
	UFUNCTION(BlueprintSetter)
	UE_API void SetHandleStanceChanges(bool bInHandleStanceChanges);

	/** Returns true if currently crouching */ 
	UFUNCTION(BlueprintCallable, Category = Mover)
	UE_API virtual bool IsCrouching() const;

	/** Returns true if currently prone */
	UFUNCTION(BlueprintCallable, Category = Mover)
	UE_API virtual bool IsProne() const;

	/** Returns true if currently flying (moving through a non-fluid volume without resting on the ground) */
	UFUNCTION(BlueprintPure, Category = Mover)
	UE_API virtual bool IsFlying() const;
	
	// Is this actor in a falling state? Note that this includes upwards motion induced by jumping.
	UFUNCTION(BlueprintPure, Category = Mover)
	UE_API virtual bool IsFalling() const;

	// Is this actor in a airborne state? (e.g. Flying, Falling)
	UFUNCTION(BlueprintPure, Category = Mover)
	UE_API virtual bool IsAirborne() const;

	// Is this actor in a grounded state? (e.g. Walking)
	UFUNCTION(BlueprintPure, Category = Mover)
	UE_API virtual bool IsOnGround() const;

	// Is this actor in a Swimming state? (e.g. Swimming)
	UFUNCTION(BlueprintPure, Category = Mover)
	UE_API virtual bool IsSwimming() const;
	
	// Is this actor sliding on an unwalkable slope
	UFUNCTION(BlueprintPure, Category = Mover)
	UE_API virtual bool IsSlopeSliding() const;

	// Can this Actor jump?
	UFUNCTION(BlueprintPure, Category = Mover)
	UE_API virtual bool CanActorJump() const;

	// Perform jump on actor
	UFUNCTION(BlueprintCallable, Category = Mover)
	UE_API virtual bool Jump();
	
	// Whether this actor can currently crouch or not 
	UFUNCTION(BlueprintCallable, Category = Mover)
	UE_API virtual bool CanCrouch();
	
	// Perform crouch on actor
	UFUNCTION(BlueprintCallable, Category = Mover)
	UE_API virtual void Crouch();

	// Perform uncrouch on actor
	UFUNCTION(BlueprintCallable, Category = Mover)
	UE_API virtual void UnCrouch();

	/** Whether this actor can currently go prone */
	UFUNCTION(BlueprintCallable, Category = Mover)
	UE_API virtual bool CanProne();

	/** Perform prone on actor */
	UFUNCTION(BlueprintCallable, Category = Mover)
	UE_API virtual void Prone();

	/** Leave prone and return to standing */
	UFUNCTION(BlueprintCallable, Category = Mover)
	UE_API virtual void UnProne();

	// Get Crouch Intent
	UFUNCTION(BlueprintCallable, Category = Mover)
	bool GetCrouchIntent() const { return bWantsToCrouch; };

    /** Simulation cache; restored from the finalized stance state. Reading it performs no traces. */
    UPROPERTY(Transient, BlueprintReadOnly, Category="Mover|Prone")
    FProneFloorData CachedProneFloorData;

    /** Read independent cached world-space tip, back, and center probes without tracing.
     * Each Does Hit? reports that probe's walkable hit while prone and grounded.
     * Missing samples return up/updated-component position with Does Hit? false.
     * Center is an actual floor probe beneath the pawn, not the midpoint of tip/back.
     */
    UFUNCTION(BlueprintPure, Category="Mover|Prone")
    UE_API void GetProneFloorData(FMoverFloorData& Tip, FMoverFloorData& Back, FMoverFloorData& Center) const;

	// Broadcast when this actor changes stances.
	UPROPERTY(BlueprintAssignable, Category = Mover)
	FMover_OnStanceChanged OnStanceChanged;
	
protected:
	// Multiple post-evaluation callbacks must not multiply timers or the frame budget.
	uint64 LastOffsetRootCorrectionFrame = MAX_uint64;
	FVector OffsetRootReconciliationTarget = FVector::ZeroVector;
	FVector OffsetRootReconciliationLastPosition = FVector::ZeroVector;
	float OffsetRootReconciliationRadiusHold = 0.f;
	float OffsetRootReconciliationStalledSeconds = 0.f;
	bool bOffsetRootReconciliationActive = false;
	bool bOffsetRootReconciliationBlocked = false;

	UFUNCTION()
	UE_API virtual void OnMoverPreSimulationTick(const FMoverTimeStep& TimeStep, const FMoverInputCmdContext& InputCmd);

	UFUNCTION()
	UE_API virtual void OnMoverPostFinalize(const FMoverSyncState& SyncState, const FMoverAuxStateContext& AuxState);

	UE_API virtual void OnHandlerSettingChanged();

	UE_API virtual void UpdateSyncedMontageState(const FMoverTimeStep& TimeStep, const FMoverSyncState& SyncState, const FMoverAuxStateContext& AuxState);

	// ID used to keep track of the modifier responsible for stance changes
	FMovementModifierHandle StanceModifierHandle;

	/** If true, try to crouch (or keep crouching) on next update. If false, try to stop crouching on next update. */
	UPROPERTY(BlueprintReadOnly, Transient, Category = "Mover|Crouch")
	uint8 bWantsToCrouch : 1 = 0;

	/** If true, try to enter or remain prone on the next update. */
	UPROPERTY(BlueprintReadOnly, Transient, Category = "Mover|Prone")
	uint8 bWantsToProne : 1 = 0;

	// Whether this component should directly handle jumping or not 
	UPROPERTY(EditAnywhere, BlueprintGetter = GetHandleJump, BlueprintSetter = SetHandleJump, Category = "Mover|Character")
	uint8 bHandleJump : 1 = 1;

	// Whether this component should directly handle stance changes, including crouching and prone input
	UPROPERTY(EditAnywhere, BlueprintGetter = GetHandleStanceChanges, BlueprintSetter = SetHandleStanceChanges, Category = "Mover|Character")
	uint8 bHandleStanceChanges : 1 = 1;

	/** Current state of replicated montage playback from an active movement mechanism (layered move, etc.) */
	UPROPERTY(Transient)
	FMoverAnimMontageState SyncedMontageState;
};

#undef UE_API

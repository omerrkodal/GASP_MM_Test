// Copyright Epic Games, Inc. All Rights Reserved.

#include "DefaultMovementSet/MovementModifiers/StanceModifier.h"

#include "MoverComponent.h"
#include "Components/CapsuleComponent.h"
#include "DefaultMovementSet/CharacterMoverComponent.h"
#include "DefaultMovementSet/Settings/CommonLegacyMovementSettings.h"
#include "DefaultMovementSet/InstantMovementEffects/BasicInstantMovementEffects.h"
#include "DefaultMovementSet/Settings/StanceSettings.h"
#include "Engine/Blueprint.h"
#include "GameFramework/Pawn.h"
#include "MoveLibrary/MovementUtils.h"
#include "MoveLibrary/ProneFloorTraceUtils.h"
#include "MoveLibrary/MoverBlackboard.h"
#include "MoverSimulationTypes.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(StanceModifier)

FStanceModifier::FStanceModifier()
	: ActiveStance(EStanceMode::Crouch)
{
	DurationMs = -1.0f;
}

bool FStanceModifier::HasGameplayTag(FGameplayTag TagToFind, bool bExactMatch) const
{
	const FGameplayTag ActiveStanceTag = ActiveStance == EStanceMode::Prone ? Mover_IsProne :
		(ActiveStance == EStanceMode::Crouch ? Mover_IsCrouching : FGameplayTag());
	return ActiveStanceTag.IsValid() && (bExactMatch ? TagToFind.MatchesTagExact(ActiveStanceTag) : TagToFind.MatchesTag(ActiveStanceTag));
}

void FStanceModifier::GetGameplayTags(FGameplayTagContainer& InOutTags) const
{
	if (ActiveStance == EStanceMode::Prone)
	{
		InOutTags.AddTag(Mover_IsProne);
	}
	else if (ActiveStance == EStanceMode::Crouch)
	{
		InOutTags.AddTag(Mover_IsCrouching);
	}
}

bool FStanceModifier::GetStanceDimensions(const UMoverComponent* MoverComp, EStanceMode Stance, float& OutHalfHeight, float& OutRadius, float& OutEyeHeight) const
{
	const AActor* Owner = MoverComp ? MoverComp->GetOwner() : nullptr;
	const UCapsuleComponent* OriginalCapsule = Owner ? UMovementUtils::GetOriginalComponentType<UCapsuleComponent>(Owner) : nullptr;
	if (!OriginalCapsule)
	{
		return false;
	}

	OutHalfHeight = OriginalCapsule->GetUnscaledCapsuleHalfHeight();
	OutRadius = OriginalCapsule->GetUnscaledCapsuleRadius();
	OutEyeHeight = 0.0f;
	const AActor* OwnerCDO = Owner->GetClass()->GetDefaultObject<AActor>();
	if (const APawn* OwnerPawnCDO = Cast<APawn>(OwnerCDO))
	{
		OutEyeHeight = OwnerPawnCDO->BaseEyeHeight;
	}

	const UStanceSettings* StanceSettings = MoverComp->FindSharedSettings<UStanceSettings>();
	if (Stance == EStanceMode::Crouch)
	{
		if (StanceSettings)
		{
			OutHalfHeight = StanceSettings->CrouchHalfHeight;
			OutEyeHeight = StanceSettings->CrouchedEyeHeight;
		}
	}
	else if (Stance == EStanceMode::Prone)
	{
		if (StanceSettings)
		{
			OutRadius = FMath::Max(1.0f, StanceSettings->ProneCapsuleRadius);
			OutHalfHeight = FMath::Max(OutRadius, StanceSettings->ProneCapsuleHalfHeight);
			OutEyeHeight = StanceSettings->ProneEyeHeight;
		}
	}

	return true;
}

void FStanceModifier::ApplyActiveStance(UMoverComponent* MoverComp)
{
	if (UCapsuleComponent* CapsuleComponent = Cast<UCapsuleComponent>(MoverComp->GetUpdatedComponent()))
	{
		float NewHalfHeight = 0.0f;
		float NewRadius = 0.0f;
		float NewEyeHeight = 0.0f;
		if (GetStanceDimensions(MoverComp, ActiveStance, NewHalfHeight, NewRadius, NewEyeHeight))
		{
            if (ActiveStance != EStanceMode::Prone)
            {
                ProneFloorData = FProneFloorData();
                if (UCharacterMoverComponent* CharacterMover = Cast<UCharacterMoverComponent>(MoverComp))
                {
                    CharacterMover->CachedProneFloorData = ProneFloorData;
                }
            }
			AdjustCapsule(MoverComp, CapsuleComponent->GetUnscaledCapsuleHalfHeight(), CapsuleComponent->GetUnscaledCapsuleRadius(), NewHalfHeight, NewRadius, NewEyeHeight);
			ApplyMovementSettings(MoverComp);
			AppliedStance = ActiveStance;
		}
	}
}

void FStanceModifier::OnStart(UMoverComponent* MoverComp, const FMoverTimeStep& TimeStep, const FMoverSyncState& SyncState, const FMoverAuxStateContext& AuxState)
{
    ApplyActiveStance(MoverComp);
}

void FStanceModifier::OnEnd(UMoverComponent* MoverComp, const FMoverTimeStep& TimeStep, const FMoverSyncState& SyncState, const FMoverAuxStateContext& AuxState)
{
	if (UCapsuleComponent* CapsuleComponent = Cast<UCapsuleComponent>(MoverComp->GetUpdatedComponent()))
	{
		float StandingHalfHeight = 0.0f;
		float StandingRadius = 0.0f;
		float StandingEyeHeight = 0.0f;
		if (GetStanceDimensions(MoverComp, EStanceMode::Invalid, StandingHalfHeight, StandingRadius, StandingEyeHeight))
		{
			AdjustCapsule(MoverComp, CapsuleComponent->GetUnscaledCapsuleHalfHeight(), CapsuleComponent->GetUnscaledCapsuleRadius(), StandingHalfHeight, StandingRadius, StandingEyeHeight);
            if (UCharacterMoverComponent* CharacterMover = Cast<UCharacterMoverComponent>(MoverComp))
            {
                CharacterMover->CachedProneFloorData = FProneFloorData();
            }
			RevertMovementSettings(MoverComp);
		}
	}
}

void FStanceModifier::OnPreMovement(UMoverComponent* MoverComp, const FMoverTimeStep& TimeStep)
{
	if (ActiveStance != AppliedStance)
	{
		if (const UCharacterMoverComponent* CharacterMover = Cast<UCharacterMoverComponent>(MoverComp))
		{
			if (CanExpand(CharacterMover, ActiveStance))
			{
				ApplyActiveStance(MoverComp);
			}
		}
	}
}

void FStanceModifier::OnPostMovement(UMoverComponent* MoverComp, const FMoverTimeStep& TimeStep, const FMoverSyncState& SyncState, const FMoverAuxStateContext& AuxState)
{
	FMovementModifierBase::OnPostMovement(MoverComp, TimeStep, SyncState, AuxState);
    if (UCharacterMoverComponent* CharacterMover = Cast<UCharacterMoverComponent>(MoverComp))
    {
        if (ActiveStance == EStanceMode::Prone && MoverComp->GetOwner() &&
            MoverComp->GetOwner()->GetLocalRole() != ROLE_SimulatedProxy)
        {
            // Sample only once per simulation substep, at its final location.
            ProneFloorData = UProneFloorTraceUtils::SampleProneFloorData(MoverComp);
        }
        CharacterMover->CachedProneFloorData = ActiveStance == EStanceMode::Prone ?
            ProneFloorData : FProneFloorData();
    }
}

FMovementModifierBase* FStanceModifier::Clone() const
{
	FStanceModifier* CopyPtr = new FStanceModifier(*this);
	return CopyPtr;
}

void FStanceModifier::NetSerialize(FArchive& Ar)
{
	Super::NetSerialize(Ar);

	uint8 SerializedStance = static_cast<uint8>(ActiveStance);
	Ar.SerializeBits(&SerializedStance, 2);
    uint8 FloorFlags = (ProneFloorData.bTipHasFloor ? 1 : 0) | (ProneFloorData.bBackHasFloor ? 2 : 0) |
        (ProneFloorData.bCenterHasFloor ? 4 : 0);
    Ar.SerializeBits(&FloorFlags, 3);
    if (Ar.IsLoading())
    {
        ProneFloorData = FProneFloorData();
        ProneFloorData.bTipHasFloor = (FloorFlags & 1) != 0;
        ProneFloorData.bBackHasFloor = (FloorFlags & 2) != 0;
        ProneFloorData.bCenterHasFloor = (FloorFlags & 4) != 0;
    }
    if (ProneFloorData.bTipHasFloor) { Ar << ProneFloorData.TipFloorNormal << ProneFloorData.TipFloorLocation; }
    if (ProneFloorData.bBackHasFloor) { Ar << ProneFloorData.BackFloorNormal << ProneFloorData.BackFloorLocation; }
    if (ProneFloorData.bCenterHasFloor) { Ar << ProneFloorData.CenterFloorNormal << ProneFloorData.CenterFloorLocation; }
    ProneFloorData.UpdateCombined();
	if (Ar.IsLoading())
	{
		ActiveStance = static_cast<EStanceMode>(SerializedStance);
	}
}

UScriptStruct* FStanceModifier::GetScriptStruct() const
{
	return FStanceModifier::StaticStruct();
}

FString FStanceModifier::ToSimpleString() const
{
	return FString::Printf(TEXT("Stance Modifier"));
}

void FStanceModifier::AddReferencedObjects(FReferenceCollector& Collector)
{
	Super::AddReferencedObjects(Collector);
}

bool FStanceModifier::CanExpand(const UCharacterMoverComponent* MoverComp, EStanceMode TargetStance) const
{
	USceneComponent* UpdatedComponent = MoverComp->GetUpdatedComponent();
	UPrimitiveComponent* UpdatedCompAsPrimitive = Cast<UPrimitiveComponent>(UpdatedComponent);
	const UCapsuleComponent* CapsuleComponent = Cast<UCapsuleComponent>(UpdatedComponent);
	if (!UpdatedCompAsPrimitive || !CapsuleComponent)
	{
		return false;
	}

	float TargetHalfHeight = 0.0f;
	float TargetRadius = 0.0f;
	float TargetEyeHeight = 0.0f;
	if (!GetStanceDimensions(MoverComp, TargetStance, TargetHalfHeight, TargetRadius, TargetEyeHeight))
	{
		return false;
	}

	const float CurrentHalfHeight = CapsuleComponent->GetScaledCapsuleHalfHeight();
	const float CurrentRadius = CapsuleComponent->GetScaledCapsuleRadius();
	const float RadiusScale = CurrentRadius / FMath::Max(CapsuleComponent->GetUnscaledCapsuleRadius(), UE_SMALL_NUMBER);
	const float TargetHalfHeightScaled = FMath::Max(TargetHalfHeight, TargetRadius) * RadiusScale;
	const float TargetRadiusScaled = TargetRadius * RadiusScale;
	if (TargetHalfHeightScaled <= CurrentHalfHeight && TargetRadiusScaled <= CurrentRadius)
	{
		return true;
	}

	FCollisionQueryParams CapsuleParams(SCENE_QUERY_STAT(CrouchTrace), false, MoverComp->GetOwner());
	FCollisionResponseParams ResponseParam;
	UMovementUtils::InitCollisionParams(UpdatedCompAsPrimitive, CapsuleParams, ResponseParam);

	const FMoverDefaultSyncState* SyncState = MoverComp->GetSyncState().SyncStateCollection.FindDataByType<FMoverDefaultSyncState>();
	
	FVector PawnLocation = SyncState ? SyncState->GetLocation_WorldSpace() : UpdatedComponent->GetComponentLocation();
	FQuat PawnRot = SyncState ? SyncState->GetOrientation_WorldSpace().Quaternion() : UpdatedComponent->GetComponentQuat();
	const FCollisionShape TargetCapsuleShape = FCollisionShape::MakeCapsule(TargetRadiusScaled, TargetHalfHeightScaled);
	const ECollisionChannel CollisionChannel = UpdatedCompAsPrimitive->GetCollisionObjectType();
	bool bEncroached = true;

	if (!ShouldExpandingMaintainBase(MoverComp))
	{
		// Expand in place
		bEncroached = UMovementUtils::OverlapTest(UpdatedComponent, UpdatedCompAsPrimitive, PawnLocation, PawnRot, CollisionChannel, TargetCapsuleShape, MoverComp->GetOwner());
	}
	else
	{
		// Expand while keeping base location the same.
		const float HalfHeightDifference = TargetHalfHeightScaled - CurrentHalfHeight;
		const FVector TargetLocation = PawnLocation + (HalfHeightDifference + .01f) * MoverComp->GetUpDirection();
		bEncroached = UMovementUtils::OverlapTest(UpdatedComponent, UpdatedCompAsPrimitive, TargetLocation, PawnRot, CollisionChannel, TargetCapsuleShape, MoverComp->GetOwner());
	}

	return !bEncroached;
}

bool FStanceModifier::ShouldExpandingMaintainBase(const UCharacterMoverComponent* MoverComp) const
{
	if (MoverComp->IsOnGround())
	{
		return true;
	}

	return false;
}

void FStanceModifier::AdjustCapsule(UMoverComponent* MoverComp, float OldHalfHeight, float OldRadius,
    float NewHalfHeight, float NewRadius, float NewEyeHeight)
{
    UCapsuleComponent* Capsule = Cast<UCapsuleComponent>(MoverComp->GetUpdatedComponent());
    if (!Capsule) { return; }
    const float OldScaledHalfHeight = Capsule->GetScaledCapsuleHalfHeight();
    Capsule->SetCapsuleSize(NewRadius, FMath::Max(NewHalfHeight, NewRadius), true);
    const float HeightDifference = Capsule->GetScaledCapsuleHalfHeight() - OldScaledHalfHeight;
    if (APawn* Pawn = Cast<APawn>(MoverComp->GetOwner())) { Pawn->BaseEyeHeight = NewEyeHeight; }
    if (UMoverBlackboard* Blackboard = MoverComp->GetSimBlackboard_Mutable())
    {
        Blackboard->Invalidate(CommonBlackboard::LastFloorResult);
    }
    if (!FMath::IsNearlyZero(HeightDifference))
    {
        // Only grounded stance changes move the capsule to preserve its base.
        if (ShouldExpandingMaintainBase(Cast<UCharacterMoverComponent>(MoverComp)))
        {
            TSharedPtr<FStanceHeightAdjustmentEffect> Effect = MakeShared<FStanceHeightAdjustmentEffect>();
            Effect->Offset = MoverComp->GetUpDirection() * HeightDifference;
            MoverComp->QueueInstantMovementEffect(Effect);
        }

        // The visual attachment must follow every size change, including in air.
        // Otherwise entering/exiting a stance on different movement modes leaves
        // a permanent mesh offset after landing or returning to standing.
        FTransform VisualTransform = MoverComp->GetBaseVisualComponentTransform();
        VisualTransform.AddToTranslation(FVector::UpVector * -HeightDifference);
        MoverComp->SetBaseVisualComponentTransform(VisualTransform);
        if (USceneComponent* Visual = MoverComp->GetPrimaryVisualComponent())
        {
            Visual->SetRelativeLocation(VisualTransform.GetLocation(), false, nullptr, ETeleportType::TeleportPhysics);
        }
    }
}

void FStanceModifier::ApplyMovementSettings(UMoverComponent* MoverComp)
{
	switch (ActiveStance)
	{
	default:
	case EStanceMode::Crouch:
		if (UStanceSettings* StanceSettings = MoverComp->FindSharedSettings_Mutable<UStanceSettings>())
		{
			// Update relevant movement settings
			if (UCommonLegacyMovementSettings* MovementSettings = MoverComp->FindSharedSettings_Mutable<UCommonLegacyMovementSettings>())
			{
				MovementSettings->Acceleration = StanceSettings->CrouchingMaxAcceleration;
				MovementSettings->MaxSpeed = StanceSettings->CrouchingMaxSpeed;
			}
		}
		
		break;

	// Prone movement settings
	case EStanceMode::Prone:
		if (UStanceSettings* StanceSettings = MoverComp->FindSharedSettings_Mutable<UStanceSettings>())
		{
			if (UCommonLegacyMovementSettings* MovementSettings = MoverComp->FindSharedSettings_Mutable<UCommonLegacyMovementSettings>())
			{
				MovementSettings->Acceleration = StanceSettings->ProningMaxAcceleration;
				MovementSettings->MaxSpeed = StanceSettings->ProningMaxSpeed;
			}
		}
		break;
	}
}

void FStanceModifier::RevertMovementSettings(UMoverComponent* MoverComp)
{
	if (const UMoverComponent* CDOMoverComp = UMovementUtils::GetOriginalComponentType<UMoverComponent>(MoverComp->GetOwner()))
	{
		const UCommonLegacyMovementSettings* OriginalMovementSettings = CDOMoverComp->FindSharedSettings<UCommonLegacyMovementSettings>();
		UCommonLegacyMovementSettings* MovementSettings = MoverComp->FindSharedSettings_Mutable<UCommonLegacyMovementSettings>();
		
		// Revert movement settings back to original settings
		if (MovementSettings && OriginalMovementSettings)
		{
			MovementSettings->Acceleration = OriginalMovementSettings->Acceleration;
			MovementSettings->MaxSpeed = OriginalMovementSettings->MaxSpeed;
		}
	}
}

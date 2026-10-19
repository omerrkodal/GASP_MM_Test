// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "MovementMode.h"
#include "StanceSettings.generated.h"

/**
 * StanceSettings: collection of settings that are shared through the mover component and contain stance related settings.
 */ 
UCLASS(MinimalAPI, BlueprintType)
class UStanceSettings : public UObject, public IMovementSettingsInterface
{
	GENERATED_BODY()

	virtual FString GetDisplayName() const override { return GetName(); }

public:
	// New max acceleration while in crouching
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Crouch", meta = (ClampMin = "0", UIMin = "0", ForceUnits = "cm/s^2"))
	float CrouchingMaxAcceleration = 2000;

	// New max speed while in crouching
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Crouch", meta = (ClampMin = "0", UIMin = "0", ForceUnits = "cm/s"))
	float CrouchingMaxSpeed = 200;
	
	// New capsule half height while crouching
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Crouch", meta = (ClampMin = "0", UIMin = "0", ForceUnits = "cm"))
	float CrouchHalfHeight = 55;

	// New eye height while crouching
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Crouch")
	float CrouchedEyeHeight = 50;

	// Upright capsule half height while prone, including the end caps. Clamped to radius.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone", meta = (ClampMin = "1", UIMin = "1", ForceUnits = "cm"))
	float ProneCapsuleHalfHeight = 42;

	// Upright capsule radius while prone. Equal radius and half height form a sphere.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone", meta = (ClampMin = "1", UIMin = "1", ForceUnits = "cm"))
	float ProneCapsuleRadius = 30;

	// Probe offsets in centimeters: X forward, Y right, Z along Mover up.
	// They follow character heading, independently of capsule size and the animated mesh.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone|Floor Traces", meta = (ForceUnits = "cm"))
	FVector ProneFloorTipOffset = FVector(70, 0, 0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone|Floor Traces", meta = (ForceUnits = "cm"))
	FVector ProneFloorBackOffset = FVector(-70, 0, 0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone|Floor Traces", meta = (ForceUnits = "cm"))
	FVector ProneFloorCenterOffset = FVector::ZeroVector;

	// Extra upward start height relative to each fixed anchor; use only as much as terrain needs.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone|Floor Traces", meta = (ClampMin = "0", UIMin = "0", ForceUnits = "cm"))
	float ProneFloorProbeStartOffset = 0;

	// Distance downward from the anchor. Independent of capsule dimensions.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone|Floor Traces", meta = (ClampMin = "1", UIMin = "1", ForceUnits = "cm"))
	float ProneFloorTraceDistance = 120;

	// New eye height while prone
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone")
	float ProneEyeHeight = 35;

	// New max acceleration while prone
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone", meta = (ClampMin = "0", UIMin = "0", ForceUnits = "cm/s^2"))
	float ProningMaxAcceleration = 1200;

	// New max speed while prone
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone", meta = (ClampMin = "0", UIMin = "0", ForceUnits = "cm/s"))
	float ProningMaxSpeed = 150;
};

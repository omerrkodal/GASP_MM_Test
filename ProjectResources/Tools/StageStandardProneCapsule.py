"""Stage standard prone collision and independent fixed-offset floor traces.

Default: back up current source and write a reviewable patch, without installing.
--install: install exactly that staged manifest; requires Program Files write access.
"""
from pathlib import Path
import argparse
import difflib
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/Mover/Source/Mover')
BASELINE = ROOT / 'Saved/VibeUE/HorizontalProne-20261011/Before'
OUT = ROOT / 'Saved/VibeUE/StandardProneCapsule-20261015'


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def function_replace(text, signature, replacement):
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[:start] + replacement.rstrip() + text[end:]


def replace(text, old, new, count=1):
    assert text.count(old) == count, (old, text.count(old), count)
    return text.replace(old, new)


def stage():
    changes = {}

    def load(name):
        value = (SOURCE / name).read_text(encoding='utf-8-sig')
        changes[name] = value
        return value

    # These files differ from the preserved pre-horizontal snapshot only in the
    # collision hooks being removed. Preserve every other installed source file.
    for name in ['Private/MoveLibrary/FloorQueryUtils.cpp',
                 'Private/MoveLibrary/GroundMovementUtils.cpp',
                 'Private/MoveLibrary/MovementUtils.cpp']:
        changes[name] = (BASELINE / name).read_text(encoding='utf-8-sig')
    for name in ['Private/MoveLibrary/AsyncMovementUtils.cpp',
                 'Private/MoveLibrary/MovementUtilsTypes.cpp']:
        text = load(name).replace('#include "MoveLibrary/ProneCapsuleUtils.h"\n', '')
        text = re.sub(r'UProneCapsuleUtils::GetCollisionShape\((\w+)(?:, ([^)]*))?\)',
                      lambda m: m[1] + '->GetCollisionShape(' + (m[2] or '') + ')', text)
        changes[name] = text

    name = 'Public/DefaultMovementSet/Settings/StanceSettings.h'
    text = load(name)
    start = text.index('\t// Half length along the forward axis while prone')
    end = text.index('\t// New eye height while prone', start)
    changes[name] = text[:start] + '''\t// Upright capsule half height while prone, including the end caps. Clamped to radius.
\tUPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone", meta = (ClampMin = "1", UIMin = "1", ForceUnits = "cm"))
\tfloat ProneCapsuleHalfHeight = 42;

\t// Upright capsule radius while prone. Equal radius and half height form a sphere.
\tUPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone", meta = (ClampMin = "1", UIMin = "1", ForceUnits = "cm"))
\tfloat ProneCapsuleRadius = 30;

\t// Probe offsets in centimeters: X forward, Y right, Z along Mover up.
\t// They follow character heading, independently of capsule size and the animated mesh.
\tUPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone|Floor Traces", meta = (ForceUnits = "cm"))
\tFVector ProneFloorTipOffset = FVector(70, 0, 0);

\tUPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone|Floor Traces", meta = (ForceUnits = "cm"))
\tFVector ProneFloorBackOffset = FVector(-70, 0, 0);

\tUPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone|Floor Traces", meta = (ForceUnits = "cm"))
\tFVector ProneFloorCenterOffset = FVector::ZeroVector;

\t// Extra upward start height relative to each fixed anchor; use only as much as terrain needs.
\tUPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone|Floor Traces", meta = (ClampMin = "0", UIMin = "0", ForceUnits = "cm"))
\tfloat ProneFloorProbeStartOffset = 0;

\t// Distance downward from the anchor. Independent of capsule dimensions.
\tUPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone|Floor Traces", meta = (ClampMin = "1", UIMin = "1", ForceUnits = "cm"))
\tfloat ProneFloorTraceDistance = 120;

''' + text[end:]

    name = 'Public/DefaultMovementSet/MovementModifiers/StanceModifier.h'
    text = load(name)
    a = text.index('    // Accepted collision surface normal;')
    b = text.index('    // Probe results belong', a)
    text = text[:a] + text[b:]
    text = replace(text, ', bool bHorizontal);', ');')
    text = replace(text, '    float OriginalCapsuleBoundsScale = 1.f;\n', '')
    changes[name] = text

    name = 'Private/DefaultMovementSet/MovementModifiers/StanceModifier.cpp'
    text = load(name).replace('#include "MoveLibrary/ProneCapsuleUtils.h"', '#include "MoveLibrary/ProneFloorTraceUtils.h"')
    a = text.index('namespace\n{\nconstexpr float ProneSurfaceNormalHoldMs')
    b = text.index('FStanceModifier::FStanceModifier()', a)
    text = text[:a] + text[b:]
    text = replace(text, 'StanceSettings->ProneHalfHeight', 'StanceSettings->ProneCapsuleHalfHeight')
    a = text.index('            if (UCharacterMoverComponent* CharacterMover', text.index('void FStanceModifier::ApplyActiveStance'))
    b = text.index('\t\t\tAdjustCapsule(', a)
    text = text[:a] + '''            if (ActiveStance != EStanceMode::Prone)
            {
                ProneFloorData = FProneFloorData();
                if (UCharacterMoverComponent* CharacterMover = Cast<UCharacterMoverComponent>(MoverComp))
                {
                    CharacterMover->CachedProneFloorData = ProneFloorData;
                }
            }
''' + text[b:]
    text = replace(text, ', NewEyeHeight, ActiveStance == EStanceMode::Prone);', ', NewEyeHeight);')
    text = replace(text, ', StandingEyeHeight, false);', ', StandingEyeHeight);')
    text = function_replace(text, 'void FStanceModifier::OnStart(', '''void FStanceModifier::OnStart(UMoverComponent* MoverComp, const FMoverTimeStep& TimeStep, const FMoverSyncState& SyncState, const FMoverAuxStateContext& AuxState)
{
    ApplyActiveStance(MoverComp);
}''')
    a = text.index('    if (UCapsuleComponent* Capsule', text.index('void FStanceModifier::OnPreMovement'))
    b = text.index('\tif (ActiveStance != AppliedStance)', a)
    text = text[:a] + text[b:]
    text = replace(text, 'UProneCapsuleUtils::SampleProneFloorData(MoverComp,\n                Cast<UCapsuleComponent>(MoverComp->GetUpdatedComponent()))', 'UProneFloorTraceUtils::SampleProneFloorData(MoverComp)')
    text = replace(text, '    Ar << ProneSurfaceNormal;\n    Ar << PendingProneSurfaceNormal;\n    Ar << PendingProneSurfaceNormalMs;\n', '')
    original = (BASELINE / name).read_text(encoding='utf-8-sig')
    a = original.index('bool FStanceModifier::CanExpand(')
    b = original.index('bool FStanceModifier::ShouldExpandingMaintainBase(', a)
    can_expand = original[a:b].rstrip()
    # Avoid dereferencing an absent sync state during initial stance requests.
    can_expand = can_expand.replace('SyncState->GetLocation_WorldSpace()', 'SyncState ? SyncState->GetLocation_WorldSpace() : UpdatedComponent->GetComponentLocation()')
    can_expand = can_expand.replace('SyncState->GetOrientation_WorldSpace().Quaternion()', 'SyncState ? SyncState->GetOrientation_WorldSpace().Quaternion() : UpdatedComponent->GetComponentQuat()')
    text = function_replace(text, 'bool FStanceModifier::CanExpand(', can_expand)
    text = function_replace(text, 'void FStanceModifier::AdjustCapsule(', '''void FStanceModifier::AdjustCapsule(UMoverComponent* MoverComp, float OldHalfHeight, float OldRadius,
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
}''')
    changes[name] = text

    name = 'Public/DefaultMovementSet/CharacterMoverComponent.h'
    text = load(name)
    a = text.index('    /** Accepted walkable surface normal for prone collision.')
    b = text.index('    /** Simulation cache;', a)
    changes[name] = text[:a] + text[b:]
    name = 'Private/DefaultMovementSet/CharacterMoverComponent.cpp'
    text = load(name).replace('#include "MoveLibrary/ProneCapsuleUtils.h"\n', '')
    text = replace(text, '            ProneCollisionSurfaceNormal = StanceModifier->ProneSurfaceNormal;\n            UProneCapsuleUtils::EnsurePhysicsGeometry(Cast<UCapsuleComponent>(GetUpdatedComponent()));\n', '')
    text = replace(text, '    UProneCapsuleUtils::DrawDebug(Cast<UCapsuleComponent>(GetUpdatedComponent()));\n', '')
    changes[name] = text

    # The old public utility and all Chaos geometry mutation are removed.
    changes['Public/MoveLibrary/ProneCapsuleUtils.h'] = None
    changes['Private/MoveLibrary/ProneCapsuleUtils.cpp'] = None
    for name in ['Public/MoveLibrary/ProneFloorTraceUtils.h', 'Private/MoveLibrary/ProneFloorTraceUtils.cpp']:
        changes[name] = (ROOT / 'ProjectResources/Tools/StandardProneSource' / name).read_text(encoding='utf-8')

    patch = []
    manifest = []
    for name, after in changes.items():
        path = SOURCE / name
        before = path.read_bytes() if path.exists() else None
        new_bytes = after.encode('utf-8') if after is not None else None
        backup = OUT / 'before' / name
        if before is not None:
            backup.parent.mkdir(parents=True, exist_ok=True)
            if backup.exists():
                assert backup.read_bytes() == before, 'Existing rollback snapshot differs: ' + name
            else:
                backup.write_bytes(before)
        if after is not None:
            staged = OUT / 'staged' / name
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(new_bytes)
        patch.extend(difflib.unified_diff((before.decode('utf-8-sig').replace('\r\n', '\n') if before else '').splitlines(True),
                                         (after or '').splitlines(True), fromfile='a/Source/Mover/'+name,
                                         tofile='b/Source/Mover/'+name))
        manifest.append(dict(path=name, before_sha256=digest(before), after_sha256=digest(new_bytes)))
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (ROOT / 'ProjectResources/Tools/Patches/MoverStandardProneCapsule-UE5.8.patch').write_text(''.join(patch), encoding='utf-8', newline='\n')
    print('STAGED:', len(manifest), 'source files;', OUT)


def install():
    manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
    for item in manifest:
        destination = (SOURCE / item['path']).resolve()
        assert destination.is_relative_to(SOURCE.resolve()), destination
        current = destination.read_bytes() if destination.exists() else None
        assert digest(current) in [item['before_sha256'], item['after_sha256']], destination
        if item['after_sha256'] is not None:
            assert digest((OUT / 'staged' / item['path']).read_bytes()) == item['after_sha256']
    for item in manifest:
        destination = SOURCE / item['path']
        if item['after_sha256'] is None:
            if destination.exists():
                destination.unlink()
                print('DELETED:', destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((OUT / 'staged' / item['path']).read_bytes())
            print('MODIFIED:', destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    install() if args.install else stage()

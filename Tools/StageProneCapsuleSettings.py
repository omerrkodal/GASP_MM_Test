"""Stage the incremental global Mover change; --install requires filesystem approval."""
from pathlib import Path
import argparse
import difflib
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/Mover/Source/Mover')
OUT = ROOT / 'Saved/VibeUE/ProneCapsuleSettings-20261015'


def stage():
    changes = {}

    def load(name):
        text = (SOURCE / name).read_text(encoding='utf-8')
        changes[name] = [text, text]

    def replace(name, before, after, count=1):
        text = changes[name][1]
        assert text.count(before) == count, (name, before, text.count(before))
        changes[name][1] = text.replace(before, after)

    settings = 'Public/DefaultMovementSet/Settings/StanceSettings.h'
    utility_h = 'Public/MoveLibrary/ProneCapsuleUtils.h'
    utility = 'Private/MoveLibrary/ProneCapsuleUtils.cpp'
    stance = 'Private/DefaultMovementSet/MovementModifiers/StanceModifier.cpp'
    floor = 'Private/MoveLibrary/FloorQueryUtils.cpp'
    movement = 'Private/MoveLibrary/MovementUtils.cpp'
    async_movement = 'Private/MoveLibrary/AsyncMovementUtils.cpp'
    types = 'Private/MoveLibrary/MovementUtilsTypes.cpp'
    for name in [settings, utility_h, utility, stance, floor, movement, async_movement, types]:
        load(name)

    replace(settings,
        'meta = (ClampMin = "1", UIMin = "1", ForceUnits = "cm"))\n\tfloat ProneHalfHeight = 42;',
        'meta = (DisplayName = "Prone Physics Half Height", ClampMin = "1", UIMin = "1", ForceUnits = "cm"))\n\tfloat ProneHalfHeight = 42;\n\n'
        '\t// Upright capsule component half height while prone. Does not change the horizontal physics length.\n'
        '\t// UCapsuleComponent clamps this to at least ProneCapsuleRadius.\n'
        '\tUPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prone", meta = (ClampMin = "1", UIMin = "1", ForceUnits = "cm"))\n'
        '\tfloat ProneCapsuleHalfHeight = 42;')

    replace(utility_h, 'class UCapsuleComponent;', 'struct FCollisionShape;\nclass UCapsuleComponent;')
    replace(utility_h, '    static FQuat GetQueryRotation(',
        '    /** Scaled collision half length, independent of the upright component half height while prone. */\n'
        '    UFUNCTION(BlueprintPure, Category="Mover|Collision")\n'
        '    static float GetCollisionHalfHeight(const UCapsuleComponent* Capsule);\n\n'
        '    /** Read the actual live Chaos capsule half length including its end caps. Zero if unavailable. */\n'
        '    UFUNCTION(BlueprintPure, Category="Mover|Collision")\n'
        '    static float GetPhysicsCapsuleHalfHeight(const UCapsuleComponent* Capsule);\n\n'
        '    static FCollisionShape GetCollisionShape(const UPrimitiveComponent* Primitive, float Inflation = 0.f);\n'
        '    static FQuat GetQueryRotation(')
    replace(utility, '#include "DefaultMovementSet/CharacterMoverComponent.h"',
        '#include "DefaultMovementSet/CharacterMoverComponent.h"\n#include "DefaultMovementSet/Settings/StanceSettings.h"')
    replace(utility, 'FQuat UProneCapsuleUtils::GetQueryRotation(',
        'float UProneCapsuleUtils::GetCollisionHalfHeight(const UCapsuleComponent* Capsule)\n'
        '{\n'
        '    if (!Capsule) { return 0.f; }\n'
        '    if (IsCapsuleHorizontal(Capsule))\n'
        '    {\n'
        '        if (const UCharacterMoverComponent* Mover = FindCharacterMover(Capsule))\n'
        '        {\n'
        '            if (const UStanceSettings* Settings = Mover->FindSharedSettings<UStanceSettings>())\n'
        '            {\n'
        '                return FMath::Max(Capsule->GetUnscaledCapsuleRadius(), Settings->ProneHalfHeight) * Capsule->GetShapeScale();\n'
        '            }\n'
        '        }\n'
        '    }\n'
        '    return Capsule->GetScaledCapsuleHalfHeight();\n'
        '}\n\n'
        'FCollisionShape UProneCapsuleUtils::GetCollisionShape(const UPrimitiveComponent* Primitive, float Inflation)\n'
        '{\n'
        '    const UCapsuleComponent* Capsule = Cast<UCapsuleComponent>(Primitive);\n'
        '    if (!IsCapsuleHorizontal(Capsule)) { return Primitive->GetCollisionShape(Inflation); }\n'
        '    const float Radius = FMath::Max(0.f, Capsule->GetScaledCapsuleRadius() + Inflation);\n'
        '    return FCollisionShape::MakeCapsule(Radius, FMath::Max(Radius, GetCollisionHalfHeight(Capsule) + Inflation));\n'
        '}\n\n'
        'float UProneCapsuleUtils::GetPhysicsCapsuleHalfHeight(const UCapsuleComponent* Capsule)\n'
        '{\n'
        '    float HalfHeight = 0.f;\n'
        '    const FBodyInstance* Body = Capsule ? Capsule->GetBodyInstance() : nullptr;\n'
        '    if (Body && Body->IsValidBodyInstance())\n'
        '    {\n'
        '        FPhysicsCommand::ExecuteRead(Body->GetPhysicsActorHandle(), [&](const FPhysicsActorHandle& Actor)\n'
        '        {\n'
        '            TArray<FPhysicsShapeHandle> Shapes;\n'
        '            Body->GetAllShapes_AssumesLocked(Shapes);\n'
        '            if (Shapes.Num() == 1 && Shapes[0].GetGeometry().GetType() == Chaos::ImplicitObjectType::Capsule)\n'
        '            {\n'
        '                const Chaos::FCapsule* Geometry = Shapes[0].GetGeometry().GetObject<Chaos::FCapsule>();\n'
        '                HalfHeight = Geometry->GetRadiusf() + 0.5f * FVector(Geometry->GetX2f() - Geometry->GetX1f()).Size();\n'
        '            }\n'
        '        });\n'
        '    }\n'
        '    return HalfHeight;\n'
        '}\n\n'
        'FQuat UProneCapsuleUtils::GetQueryRotation(')
    # Keep the fallback in GetCollisionHalfHeight itself reading the component.
    marker = 'FQuat UProneCapsuleUtils::GetQueryRotation('
    prefix, tail = changes[utility][1].split(marker, 1)
    tail = tail.replace('Capsule->GetScaledCapsuleHalfHeight()', 'GetCollisionHalfHeight(Capsule)')
    tail = tail.replace('Capsule->GetCollisionShape(-0.1f)', 'GetCollisionShape(Capsule, -0.1f)')
    changes[utility][1] = prefix + marker + tail
    replace(stance, 'TargetHalfHeightScaled <= CapsuleComponent->GetScaledCapsuleHalfHeight()',
        'TargetHalfHeightScaled <= UProneCapsuleUtils::GetCollisionHalfHeight(CapsuleComponent)')
    replace(stance, '    Capsule->SetCapsuleSize(NewRadius, FMath::Max(NewHalfHeight, NewRadius), false);',
        '    float ComponentHalfHeight = NewHalfHeight;\n'
        '    if (bHorizontal)\n'
        '    {\n'
        '        if (const UStanceSettings* Settings = MoverComp->FindSharedSettings<UStanceSettings>())\n'
        '        {\n'
        '            ComponentHalfHeight = Settings->ProneCapsuleHalfHeight;\n'
        '        }\n'
        '    }\n'
        '    Capsule->SetCapsuleSize(NewRadius, FMath::Max(ComponentHalfHeight, NewRadius), false);')
    replace(stance, 'Capsule->GetScaledCapsuleHalfHeight() / FMath::Max(Capsule->GetScaledCapsuleRadius(), 1.f)',
        'UProneCapsuleUtils::GetCollisionHalfHeight(Capsule) / FMath::Max(Capsule->GetScaledCapsuleRadius(), 1.f)')
    replace(floor, '        // A horizontal capsule has a stadium footprint; upright shrink/perch formulas do not apply.',
        '        PawnHalfHeight = UProneCapsuleUtils::GetCollisionHalfHeight(ProneCapsule);\n'
        '        // A horizontal capsule has a stadium footprint; upright shrink/perch formulas do not apply.')
    for name in [movement, async_movement, types]:
        if '#include "MoveLibrary/ProneCapsuleUtils.h"' not in changes[name][1]:
            replace(name, '#include "MoverComponent.h"', '#include "MoverComponent.h"\n#include "MoveLibrary/ProneCapsuleUtils.h"')
        import re
        changes[name][1], count = re.subn(r'\b(UpdatedPrimitive|Capsule|PrimComp|PrimitiveComp)->GetCollisionShape\(([^)]*)\)',
            lambda m: 'UProneCapsuleUtils::GetCollisionShape(' + m[1] + (', ' + m[2] if m[2] else '') + ')', changes[name][1])
        assert count > 0, name

    patch = []
    manifest = []
    for name, (before, after) in changes.items():
        assert before != after, name
        old = OUT / 'before' / name
        new = OUT / 'staged' / name
        old.parent.mkdir(parents=True, exist_ok=True)
        new.parent.mkdir(parents=True, exist_ok=True)
        if old.exists():
            assert old.read_text(encoding='utf-8') == before, 'Prior backup differs'
        old.write_text(before, encoding='utf-8', newline='\n')
        new.write_text(after, encoding='utf-8', newline='\n')
        patch.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
            fromfile='a/Source/Mover/' + name, tofile='b/Source/Mover/' + name))
        manifest.append({'path':name, 'before_sha256':hashlib.sha256(before.encode()).hexdigest(),
                         'after_sha256':hashlib.sha256(after.encode()).hexdigest()})
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (ROOT / 'Tools/Patches/MoverProneCapsuleSettings-UE5.8.patch').write_text(''.join(patch), encoding='utf-8', newline='\n')
    print('STAGED', len(changes), 'files in', OUT)


def install():
    for item in json.loads((OUT / 'manifest.json').read_text(encoding='utf-8')):
        destination = SOURCE / item['path']
        current = destination.read_text(encoding='utf-8')
        assert hashlib.sha256(current.encode()).hexdigest() in [item['before_sha256'], item['after_sha256']], destination
    for item in json.loads((OUT / 'manifest.json').read_text(encoding='utf-8')):
        destination = SOURCE / item['path']
        text = (OUT / 'staged' / item['path']).read_text(encoding='utf-8')
        destination.write_text(text, encoding='utf-8', newline='\n')
        print('MODIFIED:', destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    install() if args.install else stage()

"""Stage mesh-root prone probe anchors. Does not install, build, or close UE."""
from pathlib import Path
import difflib
import hashlib
import json

PROJECT = Path(__file__).resolve().parents[3]
ENGINE_SOURCE = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/Mover/Source/Mover')
OUT = Path(__file__).resolve().parent
EVIDENCE = PROJECT / 'Saved/VibeUE/ProneMeshProbeAnchors'
EVIDENCE.mkdir(parents=True, exist_ok=True)
FILES = ['Public/DefaultMovementSet/CharacterMoverComponent.h',
         'Private/DefaultMovementSet/CharacterMoverComponent.cpp',
         'Private/MoveLibrary/ProneFloorTraceUtils.cpp']

def replace_once(text, old, new):
    assert text.count(old) == 1, old[:100]
    return text.replace(old, new, 1)

original = {name: (ENGINE_SOURCE / name).read_text(encoding='utf-8') for name in FILES}
assert 'CacheProneFloorProbeRoot' not in original[FILES[0]], 'Already installed; do not restage'
changed = dict(original)
h = changed[FILES[0]]
h = replace_once(h, '#include "MoverComponent.h"', '#include "MoverComponent.h"\n#include "HAL/CriticalSection.h"')
h = replace_once(h, '\t// Broadcast when this actor changes stances.', '''    /** Read the last game-thread animated root snapshot in the current movement frame.
     * The sampler never reads skeletal bones. Returns false until a mesh pose is available.
     */
    UE_API bool GetProneFloorProbeFrame(const FTransform& UpdatedToWorld,
        FVector& OutOrigin, FVector& OutHeading) const;

\t// Broadcast when this actor changes stances.''')
h = replace_once(h, 'protected:\n', '''protected:
    // Cosmetic floor-probe anchor only. Stance state still serializes the resulting hits.
    // Root pose is sampled on the game thread once per frame, never during worker simulation.
    void CacheProneFloorProbeRoot();
    mutable FRWLock ProneProbeRootLock;
    FVector ProneProbeRootRelativeLocation = FVector::ZeroVector;
    FVector ProneProbeRootRelativeForward = FVector::ForwardVector;
    uint64 LastProneProbeRootCacheFrame = MAX_uint64;
    bool bHasProneProbeRoot = false;

''')
changed[FILES[0]] = h

cpp = changed[FILES[1]]
cpp = replace_once(cpp, '#include "CoreGlobals.h"', '#include "CoreGlobals.h"\n#include "Engine/SkeletalMesh.h"\n#include "Misc/ScopeRWLock.h"')
marker = 'void UCharacterMoverComponent::OnMoverPreSimulationTick(const FMoverTimeStep& TimeStep, const FMoverInputCmdContext& InputCmd)\n{'
implementation = '''bool UCharacterMoverComponent::GetProneFloorProbeFrame(const FTransform& UpdatedToWorld,
    FVector& OutOrigin, FVector& OutHeading) const
{
    FReadScopeLock Lock(ProneProbeRootLock);
    if (!bHasProneProbeRoot) { return false; }
    OutOrigin = UpdatedToWorld.TransformPosition(ProneProbeRootRelativeLocation);
    OutHeading = UpdatedToWorld.TransformVectorNoScale(ProneProbeRootRelativeForward).GetSafeNormal();
    return !OutOrigin.ContainsNaN() && !OutHeading.IsNearlyZero();
}

void UCharacterMoverComponent::CacheProneFloorProbeRoot()
{
    // Bone buffers belong to animation. Only capture the last completed pose on the GT.
    if (!IsInGameThread() || LastProneProbeRootCacheFrame == GFrameCounter) { return; }
    LastProneProbeRootCacheFrame = GFrameCounter;
    const USkeletalMeshComponent* Mesh = GetPrimaryVisualComponent<USkeletalMeshComponent>();
    const USceneComponent* Updated = GetUpdatedComponent();
    const USkeletalMesh* MeshAsset = Mesh ? Mesh->GetSkeletalMeshAsset() : nullptr;
    if (!Mesh || !Updated || !MeshAsset || Mesh->GetNumBones() == 0 ||
        MeshAsset->GetRefSkeleton().GetNum() == 0)
    {
        FWriteScopeLock Lock(ProneProbeRootLock);
        bHasProneProbeRoot = false;
        return;
    }

    const FTransform UpdatedToWorld = Updated->GetComponentTransform();
    const FTransform MeshToWorld = Mesh->GetComponentTransform();
    const FTransform RootToMesh = Mesh->GetSocketTransform(Mesh->GetBoneName(0), RTS_Component);
    const FTransform RootToWorld = RootToMesh * MeshToWorld;
    const FVector RelativeLocation = UpdatedToWorld.InverseTransformPosition(RootToWorld.GetLocation());

    // Apply the animated root rotation relative to the imported root reference.
    // Express the character's forward axis in mesh space first: no hard-coded +/-90 yaw.
    const FQuat ReferenceRootRotation = MeshAsset->GetRefSkeleton().GetRefBonePose()[0].GetRotation();
    const FVector ForwardInMesh = MeshToWorld.InverseTransformVectorNoScale(
        UpdatedToWorld.GetUnitAxis(EAxis::X));
    const FVector AnimatedForwardInMesh = (RootToMesh.GetRotation() * ReferenceRootRotation.Inverse())
        .RotateVector(ForwardInMesh);
    const FVector RelativeForward = UpdatedToWorld.InverseTransformVectorNoScale(
        MeshToWorld.TransformVectorNoScale(AnimatedForwardInMesh)).GetSafeNormal();

    FWriteScopeLock Lock(ProneProbeRootLock);
    bHasProneProbeRoot = !RelativeLocation.ContainsNaN() && !RelativeForward.ContainsNaN() &&
        !RelativeForward.IsNearlyZero();
    if (bHasProneProbeRoot)
    {
        ProneProbeRootRelativeLocation = RelativeLocation;
        ProneProbeRootRelativeForward = RelativeForward;
    }
}

'''
cpp = replace_once(cpp, marker, implementation + marker + '\n    CacheProneFloorProbeRoot();')
old_handler = '''\tconst bool bIsHandlingAnySettings = bHandleJump || bHandleStanceChanges;

\tif (bIsHandlingAnySettings)
\t{
\t\tOnPreSimulationTick.AddUniqueDynamic(this, &UCharacterMoverComponent::OnMoverPreSimulationTick);
\t}
\telse
\t{
\t\tOnPreSimulationTick.RemoveDynamic(this, &UCharacterMoverComponent::OnMoverPreSimulationTick);
\t}'''
new_handler = '''    // Probe snapshots are also needed when another system handles stance/jump input.
    // The input handlers themselves remain gated by their existing flags in the callback.
    OnPreSimulationTick.AddUniqueDynamic(this, &UCharacterMoverComponent::OnMoverPreSimulationTick);'''
cpp = replace_once(cpp, old_handler, new_handler)
changed[FILES[1]] = cpp

probe = changed[FILES[2]]
probe = replace_once(probe, 'TEXT("Draw fixed-offset prone floor probes:', 'TEXT("Draw animated-root prone floor probes:')
probe = replace_once(probe, '''    const FVector Origin = Primitive->GetComponentLocation();
    const FVector Heading = Primitive->GetForwardVector();''', '''    const FTransform UpdatedToWorld = Primitive->GetComponentTransform();
    FVector Origin = UpdatedToWorld.GetLocation();
    FVector Heading = UpdatedToWorld.GetUnitAxis(EAxis::X);
    // Use the animated character root, including Offset Root Bone translation/facing.
    // Only value data is read here; skeletal pose access stays on the game thread.
    // Before the first valid mesh snapshot, retain the original component fallback.
    CharacterMover->GetProneFloorProbeFrame(UpdatedToWorld, Origin, Heading);''')
changed[FILES[2]] = probe

manifest = {'engineSource': str(ENGINE_SOURCE), 'status': 'staged-awaiting-install-and-user-build', 'files': []}
patch = []
for name in FILES:
    before_bytes = (ENGINE_SOURCE / name).read_bytes()
    backup = EVIDENCE / 'before' / name
    staged = OUT / 'Source' / name
    backup.parent.mkdir(parents=True, exist_ok=True)
    staged.parent.mkdir(parents=True, exist_ok=True)
    assert not backup.exists(), f'Rollback file already exists: {backup}'
    backup.write_bytes(before_bytes)
    staged.write_text(changed[name], encoding='utf-8', newline='\n')
    manifest['files'].append({'relativePath': name,
        'beforeSha256': hashlib.sha256(before_bytes).hexdigest(),
        'afterSha256': hashlib.sha256(staged.read_bytes()).hexdigest()})
    patch.extend(difflib.unified_diff(original[name].splitlines(True), changed[name].splitlines(True),
        fromfile='a/' + name, tofile='b/' + name))
    # Keep the project-owned source mirrors consistent for future installation helpers.
    mirror = (PROJECT / 'ProjectResources/Tools/NativeRootReconciliation/Source' / name
              if name != FILES[2] else PROJECT / 'ProjectResources/Tools/StandardProneSource' / name)
    mirror.write_text(changed[name], encoding='utf-8', newline='\n')
    print('MODIFIED:', mirror.relative_to(PROJECT))
(EVIDENCE / 'manifest.json').write_text(json.dumps(manifest, indent=2))
patch_file = PROJECT / 'ProjectResources/Tools/Patches/MoverProneMeshProbeAnchors-UE5.8.patch'
patch_file.write_text(''.join(patch), encoding='utf-8')
print('STAGED:', json.dumps(manifest))

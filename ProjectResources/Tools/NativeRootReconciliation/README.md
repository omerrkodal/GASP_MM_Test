# Native offset-root capsule reconciliation

Checkpoint before this work: `475b72f`.

`CharacterMover.ReconcileOffsetRootOnStop` accepts the ABP's cached world-space
`RootTransform` location, the held `RootRadiusCurveOutput` curve-backed radius, and a
boolean that is true only when Offset Root Bone is enabled and its translation
mode is `Accumulate`. The ABP calls it on the game thread from its existing
`BlueprintPostEvaluateAnimation` event, after animation worker evaluation completes.
The original foot-placement reset and debug execution paths remain connected.

The function queues a native, bounded **position-only** effect. It preserves
simulation linear/angular velocity and capsule rotation. It contributes no root
motion, velocity override, or teleport event. The accumulated animation root
counters the capsule's component translation through its existing native logic.

Defaults: 150 cm/s correction, stopped at <=5 cm/s planar speed, 1 cm tolerance,
200 cm maximum offset. At most one request is queued per engine frame, with a
maximum 50 ms frame budget. New movement/jump input cancels a pending correction.
While eligible, call each frame until the offset is closed or collision blocks it.
The held radius starts correction. After it reaches zero, an already active
correction keeps its most recent target and radius until completion. Lack of planar
progress for 0.25 seconds cancels correction and smoothly releases the radius.

Sweeps use Mover's actual updated collision component. The effect follows walkable
ramps, stops at walls, restores floor spacing, and rolls back a correction without
walkable support. Position, floor cache, and dynamic movement base are updated
together; correction displacement is excluded from locomotion velocity.

This implementation targets the project's standard CharacterMover backend.
It does not implement the separate ChaosMover async effect API. The suspected
AnimationWarping root-motion attribute forwarding issue is deliberately unchanged.

`StageAndInstall.py` stages a hash-checked patch and preserves the installed source
under `Saved/VibeUE/NativeRootReconciliation/Before`. `--install` requires write
permission to the global engine plugin. `InstallAndBuild.ps1` installs the staged
files and invokes the project's existing real native build script with UE closed.

Gameplay verification belongs to the user; compile success is not a gameplay pass.

## Slope hold revision (built and integrated 2026-10-16)

The original one-second curve hold could expire while slope-following correction
was still incomplete. The old bridge also stopped requests when the raw curve
became zero. The revised native code owns correction lifetime, exposes a safe
radius hold, and releases it at a bounded rate after completion/cancellation.

`InstallSlopeHoldSource.ps1` installs only the hash-checked `slope-hold-v2` source
revision. It never shuts down UE or builds. Recompile using the user's external
`ProjectResources/Tools/RebuildGlobalMover.py` workflow and reopen the editor. Then execute
`WireSlopeHold.py` through Unreal Python. It checks the new native getter exists
before editing the ABP, copies its hold on game-thread PostEvaluateAnimation, and
uses `max(RootRadiusCurveOutput, RootReconcileRadiusHold)` in the thread-safe getter.
It contains no timer or component access in that thread-safe getter.

The user's external rebuild succeeded, the new native getter is loaded, and
WorkflowService reports a current successful build (EditorBuild-20261016-190949.log).
The ABP bridge is integrated, compiled, saved, and its connections audited. A
pre-existing duplicate execution edge from ForceFootPlacementReset directly to
reconciliation was removed, retaining the valid-Mover guard. Gameplay slope
verification remains with the user. Integration evidence is under
Saved/VibeUE/NativeRootReconciliation/slope-hold-v2.

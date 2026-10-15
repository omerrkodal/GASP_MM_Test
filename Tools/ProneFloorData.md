# Native prone floor data

## Build and Blueprint access

The source is installed in the **global Mover plugin** at `C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/Mover`.

Close Unreal and run `Tools/RebuildGlobalMover.cmd` as administrator from File Explorer. Reopen the project after **BUILD SUCCEEDED**. The terminal embedded in Unreal closes with the editor, so the native build must run externally.

`Get Prone Floor Data` is a **pure C++ Blueprint node on CharacterMoverComponent**, under `Mover | Prone`. It reads cached simulation results and performs no traces. The user will wire it into `Update_FloorValues` and the Control Rig.

The node exposes **Tip**, **Back**, and **Center** as separate native floor structs, each with **Normal**, **Location**, and **Does Hit?**. There is no separate boolean Return Value.

| Output | Meaning |
|---|---|
| Tip | Walkable floor beneath the probe just inside the physical capsule's front end. |
| Back | Walkable floor beneath the probe just inside the physical capsule's rear end. |
| Center | Walkable floor beneath the capsule center; sampled even when either end hits. |

Each output uses native `FMoverFloorData` (Blueprint display name **Mover Floor Data**). This matches the fields of the project's `/Game/Blueprints/Data/S_FloorData`, but Unreal treats native and Blueprint-defined structs as different types. Split each native pin to get Normal/Location/Does Hit?, or use **Break Mover Floor Data**. If retaining `S_FloorData` variables, connect those fields to **Make S_FloorData**. The global plugin does not load or depend on the project struct asset.

Each **Does Hit?** is true only for that sample's valid walkable hit while prone and grounded. Missing samples return Does Hit? false, Mover's up direction, and the updated component's position. Outside prone/grounded state, all three samples are invalid. A missing sample's position is a fallback value, not a ground impact point. Center is an actual independent trace hit, not the midpoint of Tip and Back. The Blueprint getter never initiates a floor query.

After rebuilding, **Refresh Node** on existing Get Prone Floor Data nodes. The former single return or Tip/Back/Combined pins have been replaced by Tip/Back/Center, so old pin connections need manual rewiring. The user owns Blueprint implementation; the `S_FloorData` asset and function graphs were not modified for this output change.

Before the user narrowed the task to C++, six variables were added and saved in `SandboxCharacter_Mover`: `TipFloorNormal`, `BackFloorNormal`, `TipHasFloor`, `BackHasFloor`, `TipFloorLocation`, `BackFloorLocation`. The Blueprint compiled to `BS_UP_TO_DATE`. No function graph wiring or Control Rig edits were applied.

## Sampling and capsule alignment

- Local grounded prone simulation runs three downward line traces after movement, once per simulation substep: tip, back, and center. All use the same downward reach and collision settings.
- Probe anchors now follow the **live Chaos capsule geometry and body pose**, read under a physics read lock. Tip/Back are placed along its actual tilted axis, inset 2 cm from the outer ends (or half the radius for very small capsules). Center is the geometry's actual world center. Capsule scale is already included in the geometry and is not applied twice. Nonstandard welded/compound bodies and unavailable physics return empty samples.
- Each trace starts at its physical anchor plus Mover's up direction times `StanceSettings.ProneFloorProbeStartOffset` (**default 0 cm**). Unlike the prior flat-plane version, the end anchors rise/fall with the physics capsule's slope. Traces remain vertical relative to Mover's up direction, rather than following the capsule's normal. Each ends one physics half length plus `CommonLegacyMovementSettings.FloorSweepDistance` below its anchor.
- **Prone Floor Probe Start Offset** is editable under Mover's Stance Settings / Prone and clamped nonnegative. The effective offset is additionally bounded to a sphere inside the capsule at each anchor, leaving up to 1 cm of interior clearance. This keeps starts inside the body rather than above a low ceiling when the capsule itself has clearance. Samples above a trace's start height cannot be detected by that downward trace. Collision responses and the walkable slope threshold come from existing Mover settings. The owning actor is ignored.
- All three samples are copied/serialized with `FStanceModifier`, and finalized samples are published on `CharacterMoverComponent`. Simulated proxies use received samples without running local probes.
- Capsule alignment still selects tip only, both normalized together, back only, then center if both ends miss. The selected result is used on the next simulation substep. Center does not influence alignment while either end is valid. The existing 80 ms stability window, angular deadband, and sampled clearance checks remain in effect.
- If all probes miss while grounded, the capsule retains its accepted tilt. Airborne alignment targets Mover's up direction.
- The full capsule floor sweep still handles physical ground support and floor distance. Its winning contact does not choose prone alignment after probe data is available.
- This revision intentionally replaces the former fixed horizontal probe anchors. End probe positions now move with accepted capsule tilt; the existing stability window remains, but slope seam oscillation must be checked in gameplay after rebuilding. No runtime evidence of this revision is recorded yet.
- Standing and crouching keep the existing floor-query path.

All multiplayer peers need the same plugin revision because the stance serialization now includes the probe results. Async/ChaosMover and multiplayer behavior remain unverified.

## Visualize the floor probes

After rebuilding the global plugin, open the gameplay console in PIE:

```text
mover.debug.DrawProneFloorTraces 1
```

Use `mover.debug.DrawProneFloorTraces 0` to turn it off. The command draws the existing simulation queries without adding collision traces:

- **Tip:** cyan start point and walkable-hit trace line.
- **Back:** magenta start point and walkable-hit trace line.
- **Center:** yellow start point and walkable-hit trace line.
- **Green sphere and arrow:** a walkable impact point and its world-space normal.
- **Red line / MISS:** that probe found no blocking hit.
- **Orange line / UNWALKABLE:** it hit a surface rejected by the walkability check; the contact/normal are still drawn for diagnosis.

Each trace has a Tip/Back/Center label and result. Drawings last one frame and update while simulation runs; no persistent trails are accumulated. When the horizontal prone capsule is not grounded, a **SKIPPED (Mover is not grounded)** label is drawn instead: no probe queries run in that state. This distinguishes an actual Center miss from the shared grounded gate suppressing sampling. Simulated proxies do not run local probes, so use the locally simulated pawn to see its queries. Drawing requires a development build with debug drawing enabled.

The independent capsule visualization remains `mover.debug.DrawProneCapsule 1`.

The incremental source patch is `Tools/Patches/MoverProneFloorTraceDebug-UE5.8.patch`, applied after the 2026-10-15 prone component/physics dimension settings change. Backups, staged source, installed-file hashes, and prior successful build evidence are in `Saved/VibeUE/ProneFloorTraceDebug-20261015`. The debug revision built successfully at 13:07:43 UTC on 2026-10-15 (`EditorBuild-20261015-155643.log`), confirmed by WorkflowService as succeeded and not stale before the start-height change. Gameplay visual confirmation remains separate.

### Center-height trace starts (2026-10-15)

The center-height version started all three probes on a flat capsule-center plane plus the configurable upward offset. It built successfully at 13:19:53 UTC on 2026-10-15, confirmed by WorkflowService as succeeded and not stale before the physics-anchor revision. The user then reported problems on angled surfaces. That flat-plane version is superseded below.

The incremental patch is `Tools/Patches/MoverProneProbeStartHeight-UE5.8.patch`, applied after the debug patch. Backups of `StanceSettings.h` and `ProneCapsuleUtils.cpp`, staged source, installed hashes, and previous successful build evidence are in `Saved/VibeUE/ProneProbeStartHeight-20261015`. No Blueprint settings or graphs were edited.

### Live physics capsule probe anchors (2026-10-15)

The newest source uses the actual physics capsule center, axis, end-cap positions, and radius as described in Sampling above. It retains independent Tip/Back/Center outputs, downward queries, existing alignment selection, and serialized fields. The debug command draws the exact new query endpoints. This revision requires an **external native rebuild** and has not been compiled or gameplay verified yet.

The incremental patch is `Tools/Patches/MoverPronePhysicsProbeAnchors-UE5.8.patch`, applied after the center-height patch. Backups of `ProneCapsuleUtils.cpp`, its header, and `StanceSettings.h`, staged source, installed hashes, and previous successful build evidence are in `Saved/VibeUE/PronePhysicsProbeAnchors-20261015`. No Blueprint settings or graphs were edited.

## Native files and rollback artifacts

Under `Source/Mover`:

- `Public/DefaultMovementSet/ProneFloorData.h`: new reflected sample structure.
- `Public/DefaultMovementSet/CharacterMoverComponent.h` and matching private `.cpp`: cache and Blueprint getter.
- `Public/MoveLibrary/ProneCapsuleUtils.h` and matching private `.cpp`: independent probes and desired normal selection.
- `Public/DefaultMovementSet/MovementModifiers/StanceModifier.h` and matching private `.cpp`: sampling, copied state, and serialization.

The incremental patch is `Tools/Patches/MoverProneFloorProbes-UE5.8.patch`; apply it after the horizontal implementation, slope alignment patch, and normal stability patch. Backups, staged source, installed-file hashes, and previous build evidence are in `Saved/VibeUE/ProneFloorProbes-20261011`. Preserve that folder before resetting or deleting Saved. The new header did not exist in the prior version; its Before backup is an empty marker.

## Verification status

The native probe build succeeded at 18:44:55 UTC on 2026-10-11 (`EditorBuild-20261011-214424.log`), confirmed by WorkflowService with `isStale == false` before changing the output API. That DLL SHA-256 was `48aea6186adbcbb71ef67faee53af94fb0a01352360c1ed2a0ae8c5b66d3e4da`. This proves compilation of the probe version; no gameplay pass is recorded here.

The three-struct output API subsequently built successfully at 19:06:40 UTC (`EditorBuild-20261011-220606.log`), confirmed by WorkflowService with `isStale == false` before this single-result change. Its DLL SHA-256 was `b32cf389a90023b41b7edb80d3bd6c215216b0ffa2e809c9286cc523b98d6125`.

The incremental output-API patch is `Tools/Patches/MoverProneFloorStructOutputs-UE5.8.patch`, applied after the probe patch. Backups of the three modified files, staged source, installed hashes, and successful prior build evidence are in `Saved/VibeUE/ProneFloorStructOutputs-20261011`. Sampling and stance serialization were not changed by this patch.

The **single-result** version subsequently built successfully at 19:20:52 UTC (`EditorBuild-20261011-222025.log`), confirmed by WorkflowService with `isStale == false` before restoring separate outputs. Its DLL SHA-256 was `3589bec8235a794f90f3f71736696c20eda1aa49686392055d6e12982881128e`. Its patch is `Tools/Patches/MoverProneSingleFloorResult-UE5.8.patch`, applied after the three-struct output patch, with backups in `Saved/VibeUE/ProneSingleFloorResult-20261011`. That historical version added the conditional center query and its serialized data.

The newest **Tip/Back/Center** source subsequently built successfully at **19:27:19 UTC on 2026-10-11** (`Saved/VibeUE/Builds/GlobalMover/EditorBuild-20261011-222652.log`). WorkflowService confirmed `lastBuild.status == "succeeded"` and `isStale == false` on 2026-10-12. Its DLL SHA-256 is `234060069ee4dd0c9a6892a2cee5b0ee7b5e6f3003cf33410fbdb2c2de600616`. Its incremental patch is `Tools/Patches/MoverProneTipBackCenter-UE5.8.patch`, applied after the single-result patch. Backups, staged source, installed hashes, and previous successful build evidence are in `Saved/VibeUE/ProneThreeFloorResults-20261011`. It samples center every grounded prone substep and restores separate outputs; the serialized field layout is unchanged from the single-result version. This confirms compilation, not gameplay or multiplayer behavior.

For the recommended low-cost Control Rig rotation, ground snapping, smoothing, and optional IK architecture, see [Prone Control Rig: surface alignment and ground contact](ProneControlRigGroundAlignment.md).

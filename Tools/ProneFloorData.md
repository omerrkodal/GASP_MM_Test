# Native prone floor data

## Build and Blueprint access

The source is installed in the **global Mover plugin** at `C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/Mover`.

Close Unreal and run `Tools/RebuildGlobalMover.cmd` as administrator from File Explorer. Reopen the project after **BUILD SUCCEEDED**. The terminal embedded in Unreal closes with the editor, so the native build must run externally.

`Get Prone Floor Data` is a **pure C++ Blueprint node on CharacterMoverComponent**, under `Mover | Prone`. It reads cached simulation results and performs no traces. The user will wire it into `Update_FloorValues` and the Control Rig.

The node exposes **Tip**, **Back**, and **Center** as separate native floor structs, each with **Normal**, **Location**, and **Does Hit?**. There is no separate boolean Return Value.

| Output | Meaning |
|---|---|
| Tip | Walkable floor beneath the fixed front probe. |
| Back | Walkable floor beneath the fixed rear probe. |
| Center | Walkable floor beneath the capsule center; sampled even when either end hits. |

Each output uses native `FMoverFloorData` (Blueprint display name **Mover Floor Data**). This matches the fields of the project's `/Game/Blueprints/Data/S_FloorData`, but Unreal treats native and Blueprint-defined structs as different types. Split each native pin to get Normal/Location/Does Hit?, or use **Break Mover Floor Data**. If retaining `S_FloorData` variables, connect those fields to **Make S_FloorData**. The global plugin does not load or depend on the project struct asset.

Each **Does Hit?** is true only for that sample's valid walkable hit while prone and grounded. Missing samples return Does Hit? false, Mover's up direction, and the updated component's position. Outside prone/grounded state, all three samples are invalid. A missing sample's position is a fallback value, not a ground impact point. Center is an actual independent trace hit, not the midpoint of Tip and Back. The Blueprint getter never initiates a floor query.

After rebuilding, **Refresh Node** on existing Get Prone Floor Data nodes. The former single return or Tip/Back/Combined pins have been replaced by Tip/Back/Center, so old pin connections need manual rewiring. The user owns Blueprint implementation; the `S_FloorData` asset and function graphs were not modified for this output change.

Before the user narrowed the task to C++, six variables were added and saved in `SandboxCharacter_Mover`: `TipFloorNormal`, `BackFloorNormal`, `TipHasFloor`, `BackHasFloor`, `TipFloorLocation`, `BackFloorLocation`. The Blueprint compiled to `BS_UP_TO_DATE`. No function graph wiring or Control Rig edits were applied.

## Sampling and capsule alignment

- Local grounded prone simulation runs three downward line traces after movement, once per simulation substep: tip, back, and center. All use the same vertical bounds and collision settings.
- Probe anchors are the capsule centre plus/minus its scaled half length along the pawn's forward direction projected onto the plane perpendicular to Mover's up direction. Capsule collision tilt does not determine the anchors.
- Each trace starts one half length above its anchor and ends one half length plus `CommonLegacyMovementSettings.FloorSweepDistance` below it. Collision responses and the walkable slope threshold come from the existing Mover settings. The owning actor is ignored.
- All three samples are copied/serialized with `FStanceModifier`, and finalized samples are published on `CharacterMoverComponent`. Simulated proxies use received samples without running local probes.
- Capsule alignment still selects tip only, both normalized together, back only, then center if both ends miss. The selected result is used on the next simulation substep. Center does not influence alignment while either end is valid. The existing 80 ms stability window, angular deadband, and sampled clearance checks remain in effect.
- If all probes miss while grounded, the capsule retains its accepted tilt. Airborne alignment targets Mover's up direction.
- The full capsule floor sweep still handles physical ground support and floor distance. Its winning contact does not choose prone alignment after probe data is available.
- Standing and crouching keep the existing floor-query path.

All multiplayer peers need the same plugin revision because the stance serialization now includes the probe results. Async/ChaosMover and multiplayer behavior remain unverified.

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

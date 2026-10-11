# Native prone floor data

## Build and Blueprint access

The source is installed in the **global Mover plugin** at `C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/Mover`.

Close Unreal and run `Tools/RebuildGlobalMover.cmd` as administrator from File Explorer. Reopen the project after **BUILD SUCCEEDED**. The terminal embedded in Unreal closes with the editor, so the native build must run externally.

`Get Prone Floor Data` is a **pure C++ Blueprint node on CharacterMoverComponent**, under `Mover | Prone`. It reads cached simulation results and performs no traces. The user will wire it into `Update_FloorValues` and the Control Rig.

| Output | Meaning |
|---|---|
| `Tip` | `Mover Floor Data` struct for the front probe. |
| `Back` | `Mover Floor Data` struct for the rear probe. |
| `Combined` | `Mover Floor Data` derived from the valid tip/back samples. |
| `Return Value` | At least one valid probe while prone and grounded. |

Each output uses native `FMoverFloorData` (Blueprint display name **Mover Floor Data**) with **Does Hit?**, **Normal**, and **Location**. This matches the fields of the project's `/Game/Blueprints/Data/S_FloorData`, but Unreal treats native and Blueprint-defined structs as different types. Split the native pins or use **Break Mover Floor Data**. If retaining `S_FloorData` variables, connect those fields to **Make S_FloorData**. The global plugin does not load or depend on the project struct asset.

`Combined.Does Hit?` is true if either probe is valid. With both valid, `Combined.Normal` is the normalized sum of their normals and `Combined.Location` is the midpoint between their impact points. With one valid, Combined copies that sample. The midpoint is calculated data rather than a third collision hit.

Missing sample normals return Mover's up direction and missing locations return the updated component's position; check **Does Hit?** before using each sample. Outside prone/grounded state, all Does Hit? flags and Return Value are false. The Blueprint getter never initiates a floor query.

After rebuilding, **Refresh Node** on existing Get Prone Floor Data nodes. Their old separate vector/bool pins have been replaced by the three struct outputs, so old pin connections need manual rewiring. The user owns Blueprint implementation; the `S_FloorData` asset and function graphs were not modified for this output change.

Before the user narrowed the task to C++, six variables were added and saved in `SandboxCharacter_Mover`: `TipFloorNormal`, `BackFloorNormal`, `TipHasFloor`, `BackHasFloor`, `TipFloorLocation`, `BackFloorLocation`. The Blueprint compiled to `BS_UP_TO_DATE`. No function graph wiring or Control Rig edits were applied.

## Sampling and capsule alignment

- Local grounded prone simulation runs two downward line traces after movement, once per simulation substep.
- Probe anchors are the capsule centre plus/minus its scaled half length along the pawn's forward direction projected onto the plane perpendicular to Mover's up direction. Capsule collision tilt does not determine the anchors.
- Each trace starts one half length above its anchor and ends one half length plus `CommonLegacyMovementSettings.FloorSweepDistance` below it. Collision responses and the walkable slope threshold come from the existing Mover settings. The owning actor is ignored.
- Both samples are copied/serialized with `FStanceModifier`, and the finalized samples are published on `CharacterMoverComponent`. Simulated proxies use received samples without running local probes.
- The capsule derives its desired normal from the combined cached probes on the next simulation substep. The existing 80 ms stability window, angular deadband, and sampled clearance checks remain in effect.
- If neither probe is valid while grounded, the capsule retains its accepted tilt. Airborne alignment targets Mover's up direction.
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

The newer struct-output API supersedes that DLL, and `last-build.json` is marked `stale`. UBT exported `EditorBuild-20261011-220202-actions.json`; no native compilation/link ran. A new rebuild is required before the editor exposes Tip, Back, and Combined struct pins.

The incremental output-API patch is `Tools/Patches/MoverProneFloorStructOutputs-UE5.8.patch`, applied after the probe patch. Backups of the three modified files, staged source, installed hashes, and successful prior build evidence are in `Saved/VibeUE/ProneFloorStructOutputs-20261011`. Sampling and stance serialization were not changed by this patch.

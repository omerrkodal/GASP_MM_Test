# Native prone floor data

## Build and Blueprint access

The source is installed in the **global Mover plugin** at `C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/Mover`.

Close Unreal and run `Tools/RebuildGlobalMover.cmd` as administrator from File Explorer. Reopen the project after **BUILD SUCCEEDED**. The terminal embedded in Unreal closes with the editor, so the native build must run externally.

`Get Prone Floor Data` is a **pure C++ Blueprint node on CharacterMoverComponent**, under `Mover | Prone`. It reads cached simulation results and performs no traces. The user will wire it into `Update_FloorValues` and the Control Rig.

| Output | Meaning |
|---|---|
| `TipFloorNormal` / `BackFloorNormal` | Separate world-space walkable surface normals. |
| `TipHasFloor` / `BackHasFloor` | Whether that probe has a valid walkable hit. |
| `TipFloorLocation` / `BackFloorLocation` | Separate world-space impact points. |
| `FloorNormal` | Normalized sum when both probes are valid; otherwise the valid probe's normal. |
| `FloorLocation` | Midpoint of both valid impact points, or the single valid impact point. It is derived data, not a third collision hit. |
| `Return Value` | At least one valid probe while prone and grounded. |

Missing probe normals return Mover's up direction and missing locations return the updated component's position; check the validity outputs. Outside prone/grounded state, validity and return value are false. The Blueprint getter never initiates a floor query.

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

The previous stability build succeeded at 18:12:58 UTC on 2026-10-11 (`EditorBuild-20261011-211232.log`). The probe source supersedes that DLL, and `last-build.json` is marked `stale`.

UBT exported `EditorBuild-20261011-213546-actions.json` with six compile and eight link actions, including the global Mover DLL. UHT generated reflection for `GetProneFloorData` and `FProneFloorData`. This is not a successful C++ compilation/link or a runtime pass. The running editor does not yet expose the getter. Native rebuild and gameplay confirmation remain pending.

# Rebuilding the global Mover plugin

## Run from outside Unreal

The terminal embedded in Unreal exits with the editor. Use File Explorer or an external terminal for this build.

1. Save your work and close Unreal.
2. In this project's `Tools` folder, right-click **RebuildGlobalMover.cmd** and choose **Run as administrator**. The engine plugin is installed under Program Files.
3. Wait for **BUILD SUCCEEDED**, then reopen `GASP_MM_Test.uproject`.

The launcher uses Unreal's bundled Python; no Python packages are needed. You can also start the launcher from File Explorer while Unreal is open: it waits up to ten minutes for the editor to close normally. It never closes Unreal itself.

With an external administrator terminal and Python 3:

```powershell
python "F:\Unreal Projects\GASP_MM_Test\Tools\RebuildGlobalMover.py"
```

## What gets built

- Global plugin: `C:\Program Files\Epic Games\UE_5.8\Engine\Plugins\Experimental\Mover`.
- Target: **GASP_MM_TestEditor / Win64 / Development**, with this project's `.uproject`. The generic `UnrealEditor` target excluded Mover in this installation and only wrote metadata.
- The build passes **`-Plugin=<global Mover.uplugin>`** explicitly. In an installed engine, UBT can reuse Epic's precompiled/read-only module rules even after editing `Mover.Build.cs`. The explicit plugin argument disables precompiled reuse for Mover's modules and includes their compile/link actions.
- UBT regenerates this Blueprint project's temporary `Intermediate/Source` targets when needed; deleting Intermediate does not require changing the build to the generic engine target.
- Logs: `Saved/VibeUE/Builds/GlobalMover/EditorBuild-<timestamp>.log`.
- Actual build status: `Saved/VibeUE/last-build.json`, also read by `WorkflowService.get_environment()`.
- Success requires UBT exit code 0 and a global Mover DLL at least as recent as its source. It does not claim runtime verification.

Deleting the project's **Intermediate** folder removes generated build files, but the global plugin also has engine-level build artifacts. Deleting **DerivedDataCache** clears asset cache data; it does not rebuild a C++ DLL. Neither deletion alone verifies the modified global plugin compiled.

The script performs an incremental native build. Changed headers and C++ files trigger their required compile/link actions. It does not delete engine binaries or caches, install source, or open the editor.

For build diagnosis, `--plan-only` exports pending compile/link actions without executing them. It leaves `last-build.json` unchanged and never records a plan as a successful build.

## Native build history; normal stability rebuild pending

The first native compilation reported a namespace error in `ProneCapsuleUtils.cpp`. The construction call now uses `::MakeImplicitObjectPtr<Chaos::FCapsule>`, matching UE 5.8's global template declaration. This correction is installed globally and included in the saved patch.

The horizontal-only native rebuild succeeded on 2026-10-11 at 15:07:22 UTC (`EditorBuild-20261011-180635.log`). A live prone sample measured the Chaos capsule axis as `(1, 0, 0)` while the root component rotation stayed upright. This verifies orientation for that sample; movement, blocked transitions, and collision coverage are still incomplete.

The implementation keeps the pawn/root transform upright and rotates its live Chaos collision capsule along the pawn's forward axis. Its native floor, clearance, and movement queries account for that collision orientation.

### Slope alignment (2026-10-11): native build succeeded

The slope change uses Mover's existing `CommonBlackboard::LastFloorResult.HitResult.ImpactNormal` for walkable ground. It projects the pawn's facing direction onto that plane and uses the resulting long axis for both Chaos geometry and query capsules. The accepted normal is copied/serialized with the stance modifier and restored on finalization. Turns refresh the local tilt before translation. Sampled clearance checks reject blocked tilt arcs; accepted shape changes invalidate the old floor distance for Walking Mode to refresh. During a cache refresh, the previous accepted ground normal is retained. Airborne alignment targets Mover's up direction.

The external slope build succeeded at 15:42:36 UTC (`EditorBuild-20261011-184209.log`), and `WorkflowService.get_environment()` confirmed `lastBuild.status == "succeeded"` with `isStale == false` before the next source change. Its Mover DLL SHA-256 was `28c48ac2c9248fd42b96c74eb75d7564ca6baf413771b792eb26499498f182be`. The user subsequently reported capsule angles alternating when crossing between ground normals. This is a gameplay defect despite compilation succeeding. Async/ChaosMover and multiplayer behavior remain unverified.

Backups, staged source, the installed-file hash report, and the additional `slope-prone.patch` are in `Saved/VibeUE/SlopeProne-20261011`. Preserve both this folder and the earlier `HorizontalProne-20261011` folder before resetting or deleting Saved. The slope patch applies on top of the horizontal implementation; the older horizontal staging script alone does not contain this update.

A copy of the additional patch is tracked in Git at `Tools/Patches/MoverSlopeAlignment-UE5.8.patch`.

### Ground-normal transition stability (2026-10-11): native build pending

Source inspection found that every floor contact normal was immediately applied to the collision shape. A cached floor result that was temporarily unwalkable also returned the up direction even while the character was grounded. These paths can feed alternating surface contacts back into capsule tilt at a seam; no runtime normal trace was captured to prove that they are the only cause of the reported glitch.

The new global source keeps the accepted pose until a different normal stays within a 2-degree candidate band for 80 ms of simulation time. Differences within 0.5 degrees of the accepted normal are ignored. The candidate and elapsed time are copied/serialized with the stance modifier, so restoring movement state also restores the pending transition. Grounded missing or unwalkable floor results retain the accepted normal. Confirmed airborne state still targets the up direction. Simulated proxies restore the received pose without resampling their local floor cache. Existing collision clearance checks still decide whether the new pose can be accepted; this change debounces contact switches rather than interpolating the angle.

The changed source is installed globally, but the editor still uses the previously built DLL. `last-build.json` is marked `stale`. `--plan-only` exported `EditorBuild-20261011-203102-actions.json`; no compilation or linking ran. Close Unreal, run `Tools/RebuildGlobalMover.cmd` as administrator from File Explorer, and reopen the project after **BUILD SUCCEEDED**. Compilation and a new gameplay reproduction are still required before calling this fix verified. All multiplayer peers must use the same plugin revision because stance serialization includes the pending candidate state.

Backups of the successfully built slope version, staged source, prior build evidence, and installed-file hashes are in `Saved/VibeUE/ProneSlopeStability-20261011`. The incremental patch is tracked at `Tools/Patches/MoverSlopeStability-UE5.8.patch`; apply it after the horizontal implementation and `MoverSlopeAlignment-UE5.8.patch` when restoring the changes. The older staging folders are historical snapshots and do not include this stability update.

- **Prone Half Height** is now the capsule's forward **half length**, including the rounded end caps. Its existing value is preserved.
- **Prone Capsule Radius** controls vertical half thickness and sideways width. Half length must be at least the radius.
- The character Blueprint's working prone values are half length `55` and radius `32` cm. Random values of half length `32` and radius `55` produced a sphere because half length is clamped to radius. Equal dimensions have no meaningful capsule axis.
- **Prone Eye Height** remains a separate stance setting.
- `mover.debug.DrawProneCapsule 1` draws the intended collision shape in cyan; use `0` to disable it. The standard capsule component wireframe uses its upright root transform and does not show the live physics orientation.
- The implementation targets a standard, unwelded capsule moved by CharacterMover. Compound/welded collision and async/ChaosMover simulation require separate review.

After the native build succeeds, check standing/crouch/prone transitions, collision at the capsule's front and rear, turning beside walls, and blocked stance changes. A build success is not a gameplay pass.

During the follow-up diagnosis, the native `StartPIE` tool reported `No such camera parameter: EnableCollision`, and the PIE session ended before the debug screenshot could be captured. No complete visual/gameplay pass is recorded. The Blueprint settings edit compiled to `BS_UP_TO_DATE` and saved successfully.

Source backup, staged files, and the patch are under `Saved/VibeUE/HorizontalProne-20261011`. Keep a copy of that folder before deleting Saved or resetting project changes.

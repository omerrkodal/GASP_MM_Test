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

## Horizontal prone source change: pending native build

The horizontal prone source has been installed in the global plugin but has not yet compiled or been checked in gameplay. The loaded editor DLL still contains the previous upright prone implementation. If compilation fails, preserve the build log for diagnosis; do not assume the feature is ready.

The implementation keeps the pawn/root transform upright and rotates its live Chaos collision capsule along the pawn's forward axis. Its native floor, clearance, and movement queries account for that collision orientation.

- **Prone Half Height** is now the capsule's forward **half length**, including the rounded end caps. Its existing value is preserved.
- **Prone Capsule Radius** controls vertical half thickness and sideways width. Half length must be at least the radius.
- **Prone Eye Height** remains a separate stance setting.
- `mover.debug.DrawProneCapsule 1` draws the intended collision shape in cyan; use `0` to disable it. The standard capsule component wireframe uses its upright root transform and does not show the live physics orientation.
- The implementation targets a standard, unwelded capsule moved by CharacterMover. Compound/welded collision and async/ChaosMover simulation require separate review.

After the native build succeeds, check standing/crouch/prone transitions, collision at the capsule's front and rear, turning beside walls, and blocked stance changes. A build success is not a gameplay pass.

Source backup, staged files, and the patch are under `Saved/VibeUE/HorizontalProne-20261011`. Keep a copy of that folder before deleting Saved or resetting project changes.

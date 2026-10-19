# Project-local Mover plugins

The project contains the modified Mover source and the two enabled plugins that
depend on it:

| Plugin | Local directory | Editor modules |
| --- | --- | --- |
| Mover | `Plugins/Mover` | Mover, MoverCVDData, MoverEditor, MoverCVDEditor |
| ChaosMover | `Plugins/ChaosMover` | ChaosMover |
| MoverExamples | `Plugins/MoverExamples` | MoverExamples |

These copies came from UE **5.8.3, changelist 58210709**. Install the same engine
version, its C++ source, Visual Studio C++ build tools and a supported Windows SDK
after reinstalling Windows. The successful dependency plan used VS 2022 MSVC
14.44 and Windows SDK 10.0.26100.0.

Unreal selects project plugins ahead of engine plugins with the same names. The
project already enables all three; no engine plugin files need to be edited.
Their module and mount names are unchanged. MoverExamples includes its complete
Content folder, preserving `/MoverExamples/` references. Git ignore exceptions
retain its character assets.

## Rebuild before opening the migrated project

1. Save and close Unreal.
2. Run `Tools/RebuildGlobalMover.cmd` from File Explorer or an external terminal.
   Its legacy filename is retained, but it builds the **local** plugin group.
3. Wait for `BUILD SUCCEEDED`, then reopen `GASP_MM_Test.uproject`.

The helper does not stop or launch the editor. It checks all six local module
DLLs before recording a successful build in `Saved/VibeUE/last-build.json`.
With an engine installed elsewhere, run the Python helper with
`--engine "D:/Epic Games/UE_5.8"` using Python 3.10 or later.

Use the project's editor target and **omit `-Plugin`**. Passing `-Plugin` assigns
Mover a separate UBT scope and causes the project-side dependent modules to fail
dependency validation. The plugin group must be discovered together through the
project's `Plugins` directory. Engine-side ChaosMover and MoverExamples also
cannot depend on project-side Mover; this is why all three were copied locally.

## Validation recorded on 2026-10-19

- Plugin source copies were checked against the engine installation with SHA-256.
- MoverExamples content inventory was checked by relative path and byte size.
- UBT passed plugin/module dependency validation and exported 178 build actions.
- All six plugin module DLL link outputs target these project-local directories.
- The plan's compile/link response data contains no paths into the engine's
  Mover, ChaosMover or MoverExamples directories.
- **The full C++ build, editor reload and gameplay verification remain pending
  and are owned by the user.** A dependency plan is not a compiled build.

The source/content audit and plan summary are in `LocalMoverMigration.json`.
Detailed plan evidence is under `Saved/VibeUE/Builds/LocalMover`.

Other installed plugins that depend on this group are currently disabled:
MoverTests, MoverIntegrations, MoverAnimNext, ChaosModularVehicleExamples,
MetaHumanCrowd, and AnimGenExample. If any are enabled later, their dependency
chains must be reviewed for the same engine-to-project restriction.

Commit and push the migration with Git LFS before formatting any drive that
contains the only copy of the project.

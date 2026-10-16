# Airborne crouch/prone mesh offset

The reviewed fix is installed in the global UE 5.8 Mover source. **Native rebuild
and post-build gameplay verification are pending.** The existing successful build
predates this change and does not verify it. Do not use Live Coding for this change.

After saving and closing Unreal yourself, run `Tools/RebuildGlobalMover.cmd` as
administrator from File Explorer or an external terminal. The project instruction
reserves editor shutdown and native recompilation for the user. This change does
not launch a build or terminate the editor.

## Diagnosis

The original `FStanceModifier::AdjustCapsule` puts both the capsule position effect
and the primary visual/base-visual adjustment behind `IsOnGround`. Resizing while
airborne therefore changes the capsule without updating its mesh attachment.
If the matching resize occurs on the ground, only one half of the adjustment is
applied and the attachment error persists after landing or standing.

Read-only live inspection of the user's running PIE session found a standing
capsule half height of 86 cm with mesh-relative Z and Mover base-visual Z both at
-144 cm. A fresh session initialized both visual offsets at -88 cm with the same
86 cm standing half height. The existing broken attachment was thus 56 cm too low.
These observations establish a component/base-visual error independent of bone IK.

Fresh automated PIE inspection stayed at its initial actor position, so it was
stopped and is **not** a successful drop/jump reproduction or runtime validation.

## Change

Every nonzero capsule half-height delta now updates the base visual transform and
primary visual relative location. Only the capsule position effect remains gated
on maintaining a grounded base. Radius, collision tests, movement settings, probe
logic, animation assets, and Control Rig graphs are not modified by this patch.

The old standard-capsule source generator is updated to emit the same correction.
`StageSource.py --install` only installs the reviewed, hash-guarded source file;
it never closes Unreal or compiles anything. Original source and install hashes
are recorded in `Saved/VibeUE/StanceVisualOffset/manifest.json` and `before/`.

## Post-build checks

Start a fresh PIE session to discard any offset already accumulated by the old DLL.
Check ordinary standing/crouch/crawl transitions on flat ground, then:

1. Crawl off a high ledge, land while crawling, and stand up.
2. Jump while standing, request crawl in the air, land, and stand up.
3. Enter a low stance on the ground and exit it in the air, then land.
4. Repeat the sequences to detect accumulated error. Include a sloped landing.

With each return to standing, the capsule must restore its original dimensions and
both mesh-relative Z and Mover base-visual Z must return to their fresh standing
baseline (observed -88 cm for this character). Visually check floating and surface
clipping. Verify a new, non-stale `lastBuild.status == "succeeded"` before treating
the source change as built. Multiplayer stance prediction needs separate testing.

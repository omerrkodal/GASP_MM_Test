# Independent prone capsule dimensions

Character Mover → Shared Settings → Stance Settings → Prone exposes:

- **Prone Physics Half Height**: forward half length of the horizontal physics capsule, including end caps. The native property remains `ProneHalfHeight`, preserving existing overrides and Blueprint references.
- **Prone Capsule Half Height**: half height of the vertical `UCapsuleComponent` while prone. Default 42 cm; clamped to at least the capsule radius. The user's current character value is 36 cm.
- **Prone Capsule Radius**: shared radius. The current character value is 36 cm; its physics half height remains 72 cm.

Component rotation stays upright. Movement overlaps, floor sweeps, stance clearance, turn/slope clearance, probes, support extent, footprint checks and debug drawing use the horizontal physics length. Conservative bounds cover that length. Standing restores the original character capsule; crouching retains Crouch Half Height.

`Get Collision Half Height` reports the scaled query half length. `Get Physics Capsule Half Height` measures the live Chaos shape including end caps.

The incremental patch is [MoverProneCapsuleSettings-UE5.8.patch](Patches/MoverProneCapsuleSettings-UE5.8.patch), applied on top of the prior Tip/Back/Center implementation. Exact before/staged files are under `Saved/VibeUE/ProneCapsuleSettings-20261015`; preserve them for rollback.

The external native build succeeded on 2026-10-15 at 12:39:59 UTC and the reopened editor loaded the new setting. `WorkflowService.get_environment()` confirmed `lastBuild.status == succeeded` and `isStale == false`. Build evidence is in `Saved/VibeUE/last-build.json`.

The user reported gameplay appears correct. Automated scenario `20261015T124227Z-928E00BF` stayed standing after the native prone request and failed before testing prone dimensions. It is not an automated runtime pass. Its report and measurements remain under `Saved/VibeUE/Scenarios` and `Saved/VibeUE/ProneCapsuleSettings-20261015`.

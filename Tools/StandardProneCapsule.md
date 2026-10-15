# Standard prone capsule and fixed floor probes

Installed and built on 2026-10-15. This supersedes the horizontal capsule and slope-alignment experiments documented in the older prone notes.

- `StanceSettings.ProneCapsuleHalfHeight` and `ProneCapsuleRadius` control the ordinary upright capsule. Half height clamps to radius. The character's settings at final verification were 30/30 cm; existing user values were preserved.
- Removed the separate physics half length, horizontal Chaos geometry mutation, collision tilt/debounce state, custom turn arc handling, and horizontal floor/penetration query overrides.
- The existing Tip/Back/Center floor structs and getter remain compatible with the character Blueprint, ABP smoothing, and CR_Crawl1.
- Fixed probe offsets live in **Stance Settings → Prone → Floor Traces**. X is character forward, Y right, Z Mover up. Defaults: Tip `(70,0,0)`, Back `(-70,0,0)`, Center `(0,0,0)` cm. Heading is projected onto the up plane; mesh bones, capsule dimensions, and collision tilt do not determine the offsets.
- Probe start offset defaults to 0 cm; downward reach defaults to 120 cm. Samples are taken once per grounded prone movement substep, copied/serialized with stance state, and restored for simulated proxies. Probe contacts do not alter collision geometry.
- `mover.debug.DrawProneFloorTraces 1` displays the queries. The old `ProneCapsuleUtils` API and `mover.debug.DrawProneCapsule` were removed.

Verification: current native `lastBuild.status=succeeded`, `isStale=false`; both character and animation Blueprints compiled to `BS_UP_TO_DATE`; 84 native probe-anchor cases verified pitch invariance at seven pitches and four headings for all three offsets. Live slope traversal and multiplayer gameplay were not tested.

Build log: `Saved/VibeUE/Builds/GlobalMover/EditorBuild-20261015-175042.log`. Mover DLL SHA-256: `a57073998700485811f3cad5426d2707aefa042ad17fe7a2543f75977ef65da4`.

The install wrapper recorded an earlier failure, but the underlying native build completed successfully; authoritative build evidence is `Saved/VibeUE/last-build.json` and `Saved/VibeUE/StandardProneCapsule-20261015/verification.json`.

Rollback source and manifest: `Saved/VibeUE/StandardProneCapsule-20261015/before` and `manifest.json`. The reviewed incremental patch is tracked at `Tools/Patches/MoverStandardProneCapsule-UE5.8.patch`; staging/install helpers are `Tools/StageStandardProneCapsule.py` and `Tools/InstallAndBuildStandardProne.ps1`. Save and close Unreal before using `Tools/RebuildGlobalMover.py` for later native builds.

Removing tilt state changes the stance network serialization layout; use the same native plugin revision for all peers.

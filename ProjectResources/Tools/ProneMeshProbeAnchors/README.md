# Animated-root prone probes

Tip, Center and Back previously used the capsule origin and heading, so an Offset Root Bone pose could move away from all three probes.

`UCharacterMoverComponent` now captures the last completed skeletal root pose on the game thread once per render frame, storing its position and heading relative to the updated component. The floor sampler reconstructs that snapshot in the current movement frame. It reads a lock-protected value cache, never skeletal bones. The animated rotation is applied relative to the imported root reference and the mesh's forward basis, avoiding a mannequin-specific yaw constant.

All three existing offsets are applied from this shared animated-root frame. Tip remains the character's configured 40 cm forward offset; Back/Center settings and query filters are unchanged. Up/down traces still use Mover up. If a mesh pose is unavailable, the sampler retains the capsule fallback. Simulated proxies continue using the existing serialized stance contacts.

This uses the last completed pose; it cannot predict animation that has not evaluated yet. Floor samples remain visual data; the capsule collision shape and reconciliation algorithm are unchanged. No Blueprint rewiring is needed.

Source installation does not verify compilation. The user owns editor shutdown, external native recompilation and gameplay checks. After rebuilding, enable `mover.debug.DrawProneFloorTraces 1` and verify probes remain with the mesh during a translated/rotated reface while the capsule stays behind.

Stage with `StageSource.py`, then install with `InstallSource.ps1`. The three original files and before/after hashes are recorded under `Saved/VibeUE/ProneMeshProbeAnchors`. The incremental patch is `ProjectResources/Tools/Patches/MoverProneMeshProbeAnchors-UE5.8.patch`.

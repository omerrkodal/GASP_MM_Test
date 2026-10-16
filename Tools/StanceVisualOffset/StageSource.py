"""Stage the airborne stance visual-offset fix; --install writes the reviewed source.

Run installation with permission to write the global Mover plugin. This script
never stops Unreal, launches it, or compiles native code.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
EVIDENCE = PROJECT / "Saved/VibeUE/StanceVisualOffset"
ENGINE_SOURCE = Path("C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/Mover/Source/Mover")
RELATIVE = Path("Private/DefaultMovementSet/MovementModifiers/StanceModifier.cpp")

OLD = """    if (!FMath::IsNearlyZero(HeightDifference) && ShouldExpandingMaintainBase(Cast<UCharacterMoverComponent>(MoverComp)))
    {
        TSharedPtr<FStanceHeightAdjustmentEffect> Effect = MakeShared<FStanceHeightAdjustmentEffect>();
        Effect->Offset = MoverComp->GetUpDirection() * HeightDifference;
        MoverComp->QueueInstantMovementEffect(Effect);
        FTransform VisualTransform = MoverComp->GetBaseVisualComponentTransform();"""
NEW = """    if (!FMath::IsNearlyZero(HeightDifference))
    {
        // Only grounded stance changes move the capsule to preserve its base.
        if (ShouldExpandingMaintainBase(Cast<UCharacterMoverComponent>(MoverComp)))
        {
            TSharedPtr<FStanceHeightAdjustmentEffect> Effect = MakeShared<FStanceHeightAdjustmentEffect>();
            Effect->Offset = MoverComp->GetUpDirection() * HeightDifference;
            MoverComp->QueueInstantMovementEffect(Effect);
        }

        // The visual attachment must follow every size change, including in air.
        // Otherwise entering/exiting a stance on different movement modes leaves
        // a permanent mesh offset after landing or returning to standing.
        FTransform VisualTransform = MoverComp->GetBaseVisualComponentTransform();"""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stage() -> dict:
    target = ENGINE_SOURCE / RELATIVE
    original = target.read_bytes()
    text = original.decode("utf-8").replace("\r\n", "\n")
    if NEW in text:
        raise RuntimeError("Fix is already installed; use the existing manifest for verification.")
    assert text.count(OLD) == 1, "Expected exactly one original stance gate"
    replacement = text.replace(OLD, NEW)
    backup = EVIDENCE / "before" / RELATIVE
    assert not backup.exists(), "Rollback already exists; refusing to overwrite it"
    staged = TASK / "Source" / RELATIVE
    backup.parent.mkdir(parents=True, exist_ok=True)
    staged.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(original)
    staged.write_text(replacement, encoding="utf-8", newline="\n")
    patch = PROJECT / "Tools/Patches/MoverStanceVisualOffset-UE5.8.patch"
    patch.write_text("".join(difflib.unified_diff(text.splitlines(True), replacement.splitlines(True),
                     fromfile="a/" + RELATIVE.as_posix(), tofile="b/" + RELATIVE.as_posix())), encoding="utf-8")
    # Keep the original standard-capsule generator from reintroducing this gate.
    generator = PROJECT / "Tools/StageStandardProneCapsule.py"
    generator_text = generator.read_text(encoding="utf-8")
    assert generator_text.count(OLD) == 1, "Unexpected standard-capsule generator"
    (EVIDENCE / "StageStandardProneCapsule.before.py").write_bytes(generator.read_bytes())
    generator.write_text(generator_text.replace(OLD, NEW), encoding="utf-8", newline="\n")
    print("MODIFIED:", generator)
    manifest = {"status": "staged-awaiting-install-and-user-build", "relativePath": RELATIVE.as_posix(),
                "engineSource": str(ENGINE_SOURCE), "beforeSha256": digest(original),
                "afterSha256": digest(staged.read_bytes()), "rollback": str(backup),
                "staged": str(staged), "patch": str(patch)}
    (EVIDENCE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("CREATED:", staged)
    print("CREATED:", patch)
    return manifest


def install() -> dict:
    manifest_path = EVIDENCE / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = ENGINE_SOURCE / RELATIVE
    staged_bytes = (TASK / "Source" / RELATIVE).read_bytes()
    assert digest(staged_bytes) == manifest["afterSha256"], "Staged source changed after review"
    current_digest = digest(target.read_bytes())
    assert current_digest in (manifest["beforeSha256"], manifest["afterSha256"]), "Engine source changed; restage against current source"
    if current_digest != manifest["afterSha256"]:
        target.write_bytes(staged_bytes)
        print("MODIFIED:", target)
    assert digest(target.read_bytes()) == manifest["afterSha256"]
    manifest["status"] = "installed-awaiting-user-native-build"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    print(json.dumps(install() if args.install else stage(), indent=2))

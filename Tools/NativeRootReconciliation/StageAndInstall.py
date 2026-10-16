"""Stage a reviewable Mover patch. --install installs only its hash-checked files."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
STAGED = Path(__file__).resolve().parent / 'Source'
ENGINE_SOURCE = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Plugins/Experimental/Mover/Source/Mover')
EVIDENCE = PROJECT / 'Saved/VibeUE/NativeRootReconciliation'
BACKUP = EVIDENCE / 'Before'
MANIFEST = EVIDENCE / 'manifest.json'
PATCH = PROJECT / 'Tools/Patches/MoverOffsetRootReconcile-UE5.8.patch'


def digest(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def stage() -> None:
    entries = []
    patch = []
    for source in sorted(STAGED.rglob('*')):
        if not source.is_file() or source.suffix not in {'.h', '.cpp'}:
            continue
        rel = source.relative_to(STAGED)
        original = ENGINE_SOURCE / rel
        before = original.read_bytes() if original.exists() else None
        backup = BACKUP / rel
        if before is not None:
            backup.parent.mkdir(parents=True, exist_ok=True)
            if backup.exists() and backup.read_bytes() != before:
                raise RuntimeError(f'Original source changed since backup: {rel}')
            backup.write_bytes(before)
        after = source.read_bytes()
        entries.append({'path': rel.as_posix(), 'before': digest(before), 'after': digest(after)})
        patch.extend(difflib.unified_diff(
            [line + '\n' for line in before.decode('utf-8-sig').splitlines()] if before is not None else [],
            [line + '\n' for line in after.decode('utf-8-sig').splitlines()],
            fromfile='a/' + rel.as_posix() if before is not None else '/dev/null',
            tofile='b/' + rel.as_posix()))
    assert len(entries) == 4, entries
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({'engineSource': str(ENGINE_SOURCE), 'files': entries}, indent=2) + '\n')
    PATCH.parent.mkdir(parents=True, exist_ok=True)
    PATCH.write_text(''.join(patch), encoding='utf-8', newline='\n')
    print(f'STAGED: {len(entries)} files; patch: {PATCH}')
    print(f'Original source backups: {BACKUP}')


def install() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if Path(manifest['engineSource']).resolve() != ENGINE_SOURCE.resolve():
        raise RuntimeError('Manifest points to a different engine source directory')
    checked = []
    for entry in manifest['files']:
        rel = Path(entry['path'])
        target = (ENGINE_SOURCE / rel).resolve()
        if rel.is_absolute() or not target.is_relative_to(ENGINE_SOURCE.resolve()):
            raise RuntimeError(f'Invalid target: {target}')
        data = (STAGED / rel).read_bytes()
        if digest(data) != entry['after']:
            raise RuntimeError(f'Staged source changed after review: {rel}')
        current = target.read_bytes() if target.exists() else None
        if digest(current) not in {entry['before'], entry['after']}:
            raise RuntimeError(f'Installed source changed after staging: {rel}')
        checked.append((target, data))
    # Validate the entire patch before installing any file.
    for target, data in checked:
        if target.exists() and target.read_bytes() == data:
            print(f'UNCHANGED: {target}')
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f'MODIFIED: {target}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--revision', default='', help='Separate manifest/backup for an incremental revision')
    options = parser.parse_args()
    if options.revision:
        if not all(c.isalnum() or c in '-_' for c in options.revision):
            raise ValueError('Revision must contain only letters, numbers, hyphens or underscores')
        EVIDENCE = EVIDENCE / options.revision
        BACKUP = EVIDENCE / 'Before'
        MANIFEST = EVIDENCE / 'manifest.json'
        PATCH = PATCH.with_name(PATCH.stem + '-' + options.revision + PATCH.suffix)
    install() if options.install else stage()

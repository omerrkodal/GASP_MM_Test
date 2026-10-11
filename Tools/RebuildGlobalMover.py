"""Build the modified engine-level Mover with Unreal closed. Uses only Python's standard library."""

from __future__ import annotations

import argparse
import base64
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


DEFAULT_ENGINE = Path(r"C:\Program Files\Epic Games\UE_5.8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def powershell_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def powershell_command(code: str) -> list[str]:
    encoded = base64.b64encode(code.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded]


def running_editors() -> list[str]:
    # Check all editor sessions: any of them can hold the shared engine plugin DLLs open.
    code = (
        "$ErrorActionPreference='Stop'; "
        "Get-Process UnrealEditor -ErrorAction SilentlyContinue | "
        "ForEach-Object { Write-Output ('PID {0}: {1}' -f $_.Id,$_.Path) }; exit 0"
    )
    result = subprocess.run(powershell_command(code), capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError("Could not check editor processes. " + result.stderr.strip())
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def wait_until_closed(max_seconds: int) -> None:
    deadline = time.monotonic() + max_seconds
    announced = False
    while True:
        editors = running_editors()
        if not editors:
            return
        if not announced:
            print("Unreal must be closed before this build:", flush=True)
            for editor in editors:
                print("  " + editor, flush=True)
            if max_seconds:
                print(f"Waiting up to {max_seconds} seconds. Close UE normally; this script never stops it.", flush=True)
            announced = True
        if not max_seconds or time.monotonic() >= deadline:
            raise RuntimeError("Editor still running. Close Unreal, then run this script from an external terminal or File Explorer.")
        time.sleep(min(3, max(0, deadline - time.monotonic())))


def find_project(value: str | None) -> Path:
    if value:
        project = Path(value).expanduser().resolve()
        if project.suffix.lower() != ".uproject" or not project.is_file():
            raise RuntimeError(f"Project does not exist: {project}")
        return project
    projects = list(Path(__file__).resolve().parent.parent.glob("*.uproject"))
    if len(projects) != 1:
        raise RuntimeError("Pass --project with the complete .uproject path.")
    return projects[0]


def mover_binary(plugin: Path) -> Path:
    manifest = plugin / "Binaries" / "Win64" / "UnrealEditor.modules"
    if manifest.is_file():
        module_name = json.loads(manifest.read_text(encoding="utf-8-sig")).get("Modules", {}).get("Mover")
        if module_name:
            # Module filenames must stay inside this plugin's Binaries/Win64 directory.
            if Path(module_name).name != module_name:
                raise RuntimeError(f"Unexpected Mover module path: {module_name}")
            return manifest.parent / module_name
    return plugin / "Binaries" / "Win64" / "UnrealEditor-Mover.dll"


def file_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rebuild(args: argparse.Namespace) -> int:
    if os.name != "nt":
        raise RuntimeError("This launcher targets the project's Windows UE 5.8 installation.")
    project = find_project(args.project)
    engine = Path(args.engine).expanduser().resolve()
    if engine.name.lower() != "engine":
        engine /= "Engine"
    build_bat = engine / "Build" / "BatchFiles" / "Build.bat"
    plugin = engine / "Plugins" / "Experimental" / "Mover"
    rules = plugin / "Source" / "Mover" / "Mover.Build.cs"
    required = [build_bat, engine / "Source" / "UnrealEditor.Target.cs", rules,
                plugin / "Source" / "Mover" / "Private" / "MoveLibrary" / "ProneCapsuleUtils.cpp"]
    for path in required:
        if not path.is_file():
            raise RuntimeError(f"Required build input is missing: {path}")
    if not args.plan_only and not ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError("The global plugin is in Program Files. Right-click RebuildGlobalMover.cmd and choose 'Run as administrator'.")

    if not args.plan_only:
        wait_until_closed(args.wait_for_close)
    evidence_dir = project.parent / "Saved" / "VibeUE" / "Builds" / "GlobalMover"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    log = evidence_dir / ("EditorBuild-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".log")
    status_path = project.parent / "Saved" / "VibeUE" / "last-build.json"
    binary = mover_binary(plugin)
    target = args.target or project.stem + "Editor"
    source_files = [p for p in (plugin / "Source" / "Mover").rglob("*")
                    if p.is_file() and p.suffix.lower() in {".cpp", ".h", ".cs"}]
    newest_source = max(p.stat().st_mtime for p in source_files)
    build_args = [target, "Win64", "Development", f"-Project={project}",
                  f"-Plugin={plugin / 'Mover.uplugin'}",
                  "-WaitMutex", "-NoHotReloadFromIDE", "-NoUBTMakefiles", "-NoLiveCoding"]
    # Build the project's editor target so its enabled plugins are included. UBT's
    # NativeProjects support regenerates temporary targets for this Blueprint project.
    # The generic UnrealEditor target can exclude Mover and return metadata-only success.
    # An installed engine normally reuses read-only/precompiled engine module rules.
    # The explicit -Plugin argument clears bUsePrecompiled for this plugin's modules
    # in UEBuildTarget.CreateModuleByName, even when its cached rules are read-only.
    actions_path = evidence_dir / (log.stem + "-actions.json")
    if args.plan_only:
        build_args.append(f"-WriteOutdatedActions={actions_path}")
    code = "& " + powershell_literal(str(build_bat)) + " " + " ".join(powershell_literal(a) for a in build_args)
    code += "; exit $LASTEXITCODE"
    record = {
        "status": "planning" if args.plan_only else "running", "startedAtUtc": utc_now(),
        "target": target, "platform": "Win64", "configuration": "Development",
        "projectPath": str(project), "enginePath": str(engine), "pluginPath": str(plugin),
        "runner": "Tools/RebuildGlobalMover.py (standalone UBT; installed VibeUE has no build launcher)",
        "logPath": str(log), "arguments": build_args,
        "moverBinaryBefore": str(binary), "moverSha256Before": file_digest(binary),
        "newestMoverSourceTimestamp": newest_source,
    }
    # Exporting actions is not a native build and must not overwrite lastBuild evidence.
    record_path = actions_path.with_name(actions_path.stem + "-result.json") if args.plan_only else status_path
    atomic_json(record_path, record)
    print(f"Project: {project}\nGlobal plugin: {plugin}\nBuild target: {target} Win64 Development\nLog: {log}", flush=True)
    print("Exporting build actions only; compilation/linking will not run." if args.plan_only else
          "Keep Unreal closed until BUILD SUCCEEDED. This script does not launch the editor.", flush=True)
    exit_code = 1
    process = None
    try:
        with log.open("w", encoding="utf-8") as output:
            process = subprocess.Popen(powershell_command(code), cwd=engine.parent, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                output.write(line)
                output.flush()
            exit_code = process.wait()
        record["exitCode"] = exit_code
        if exit_code != 0:
            raise RuntimeError(f"UBT failed with exit code {exit_code}; see {log}")
        if args.plan_only:
            if not actions_path.is_file():
                raise RuntimeError("UBT did not export an action plan; see the log.")
            actions = json.loads(actions_path.read_text(encoding="utf-8-sig"))
            pending = actions.get("Actions", [])
            expected_binary = os.path.normcase(str(binary))
            dll_link_planned = any(
                action.get("Type") == "Link" and
                any(os.path.normcase(str(Path(output))) == expected_binary for output in action.get("ProducedItems", []))
                for action in pending
            )
            if (not binary.is_file() or binary.stat().st_mtime + 2 < newest_source) and not dll_link_planned:
                raise RuntimeError("The global Mover DLL is stale, but this action plan does not include its rebuild. No verified plan is recorded.")
            record.update({"status": "planned", "actionsPath": str(actions_path),
                           "actionCount": len(pending), "moverDllLinkPlanned": dll_link_planned})
            print(f"\nBUILD PLAN EXPORTED: {actions_path}\nThis is not a completed native build.", flush=True)
            return 0
        binary = mover_binary(plugin)
        if not binary.is_file() or binary.stat().st_mtime + 2 < newest_source:
            raise RuntimeError("UBT returned success, but the global Mover DLL is missing or older than its source. No successful build is recorded.")
        record.update({"status": "succeeded", "moverBinary": str(binary), "moverSha256": file_digest(binary),
                       "moverBinaryTimestamp": binary.stat().st_mtime, "moverBinarySize": binary.stat().st_size})
        print(f"\nBUILD SUCCEEDED\nMover DLL: {binary}\nYou can reopen {project.name} now.", flush=True)
        return 0
    except BaseException as error:
        if process is not None and process.poll() is None:
            # Never leave a compiler running while telling the user that it is safe to reopen UE.
            subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=30)
            process.wait(timeout=30)
        record.update({"status": "failed", "diagnostic": str(error), "exitCode": exit_code})
        raise
    finally:
        record["finishedAtUtc"] = utc_now()
        atomic_json(record_path, record)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default=str(DEFAULT_ENGINE), help="UE installation root, or its Engine directory")
    parser.add_argument("--project", help="Optional .uproject path; defaults to this script's project")
    parser.add_argument("--target", help="Optional editor target name; defaults to <ProjectName>Editor")
    parser.add_argument("--wait-for-close", type=int, default=0, metavar="SECONDS", help="Wait for UE to close before building")
    parser.add_argument("--plan-only", action="store_true", help="Export pending UBT actions without compiling or linking; does not record build success")
    args = parser.parse_args()
    if args.wait_for_close < 0:
        parser.error("--wait-for-close must be zero or positive")
    try:
        return rebuild(args)
    except (Exception, KeyboardInterrupt) as error:
        print(f"\nBUILD NOT COMPLETED: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

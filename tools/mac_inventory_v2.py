#!/usr/bin/env python3
"""G2 macOS read-only application/CLI inventory (v2).

Finds Codex in the new ChatGPT.app by its *bundle identifier*, not just the
legacy Codex.app filename. Reads Info.plist; does not launch apps or models,
read credentials, modify app/project settings, or issue security grants.

Discovery is NOT an OS-enforced approval/write-boundary certification.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import time

VERSION = "2.0.0"
BUNDLE_IDS = {
    "codex_desktop": "com.openai.codex",
    "claude_desktop": "com.anthropic.claudefordesktop",
}
APP_CANDIDATES = ("ChatGPT.app", "Codex.app", "Claude.app", "ChatGPT Classic.app")
CLI_NAMES = {"codex_cli": "codex", "claude_cli": "claude"}
SECURITY_FIELDS = (
    "approval_provenance", "mandatory_write_boundary", "native_negative_tests",
    "same_worktree_multiwriter",
)


def display_path(path: Path, home: Path | None = None) -> str:
    """Keep inventory useful without unnecessarily exposing local username."""
    home = home or Path.home()
    try:
        return "~" + str(path)[len(str(home)):] if path == home or home in path.parents else str(path)
    except (OSError, ValueError):
        return str(path)


def bundle_info(path: Path) -> dict | None:
    """Only inspect known .app bundles; a plist is not proof of authenticity."""
    if path.suffix != ".app" or not path.is_dir():
        return None
    try:
        with (path / "Contents" / "Info.plist").open("rb") as stream:
            data = plistlib.load(stream)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    bundle_id = data.get("CFBundleIdentifier")
    if bundle_id not in BUNDLE_IDS.values():
        return None
    return {
        "bundle_path": display_path(path),
        "bundle_identifier": bundle_id,
        "app_name": data.get("CFBundleDisplayName") or data.get("CFBundleName") or path.stem,
        "short_version": data.get("CFBundleShortVersionString"),
        "build_version": data.get("CFBundleVersion"),
        "metadata": "OBSERVED_NOT_CERTIFIED",
    }


def spotlight_paths() -> tuple[list[Path], str]:
    """Query macOS Spotlight metadata without launching application bundles."""
    if platform.system() != "Darwin" or shutil.which("mdfind") is None:
        return [], "UNAVAILABLE"
    paths: list[Path] = []
    try:
        for bundle_id in BUNDLE_IDS.values():
            result = subprocess.run(
                ["/usr/bin/mdfind", f'kMDItemCFBundleIdentifier == "{bundle_id}"'],
                capture_output=True, text=True, timeout=8, check=False,
            )
            if result.returncode != 0:
                return paths, "QUERY_FAILED"
            for line in result.stdout.splitlines()[:100]:
                candidate = Path(line.strip())
                if candidate.suffix == ".app":
                    paths.append(candidate)
        return paths, "QUERIED_SPOTLIGHT_NOT_AUTHORITATIVE"
    except (OSError, subprocess.TimeoutExpired):
        return paths, "QUERY_FAILED"


def discover_apps(roots: list[Path] | None = None, *, use_spotlight: bool = True) -> tuple[dict, str]:
    roots = roots if roots is not None else [Path("/Applications"), Path.home() / "Applications"]
    candidates = [root / filename for root in roots for filename in APP_CANDIDATES]
    spotlight_status = "SKIPPED"
    if use_spotlight:
        extra, spotlight_status = spotlight_paths()
        candidates.extend(extra)
    found: dict[str, list[dict]] = {p: [] for p in BUNDLE_IDS}
    seen: set[str] = set()
    for path in candidates:
        try:
            key = str(path.resolve())
        except (OSError, RuntimeError):
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        info = bundle_info(path)
        if not info:
            continue
        for provider, bundle_id in BUNDLE_IDS.items():
            if info["bundle_identifier"] == bundle_id:
                found[provider].append(info)
                break
    return found, spotlight_status


def discover_cli(name: str, home: Path | None = None) -> dict:
    home = home or Path.home()
    on_path = shutil.which(name)
    known = [
        home / ".local" / "bin" / name,
        home / ".npm-global" / "bin" / name,
        Path("/opt/homebrew/bin") / name,
        Path("/usr/local/bin") / name,
    ]
    other = [p for p in known if p.is_file() and os.access(p, os.X_OK)]
    location = Path(on_path) if on_path else (other[0] if other else None)
    return {
        "discovery": "ON_PATH" if on_path else ("KNOWN_LOCATION_ONLY" if other else "NOT_DISCOVERED"),
        "executable_present_on_path": bool(on_path),
        "binary_location": display_path(location, home) if location else None,
        "version": "NOT_READ_NO_PROCESS_LAUNCHED",
    }


def report(*, roots: list[Path] | None = None, use_spotlight: bool = True) -> dict:
    apps, spotlight_status = discover_apps(roots, use_spotlight=use_spotlight)
    providers = {}
    for provider in ("codex_cli", "codex_desktop", "claude_cli", "claude_desktop"):
        security = {field: "NOT_TESTED" for field in SECURITY_FIELDS}
        if provider in CLI_NAMES:
            cli = discover_cli(CLI_NAMES[provider])
            providers[provider] = {
                "provider": provider, "mode": "NOT_CERTIFIED", **security,
                "executable_present": cli["executable_present_on_path"], "cli": cli,
            }
        else:
            found = apps[provider]
            providers[provider] = {
                "provider": provider, "mode": "NOT_CERTIFIED", **security,
                "executable_present": None,
                "app_bundle_detected": bool(found),
                "bundles": found,
            }
    return {
        "probe_version": VERSION,
        "probe_kind": "READ_ONLY_DISCOVERY",
        "host_os": platform.system(), "host_release": platform.release(),
        "host_arch": platform.machine(), "generated_epoch": int(time.time()),
        "spotlight_status": spotlight_status,
        "providers": providers,
        "enforced_available": False,
        "status": "NOT_CERTIFIED",
        "G2": "BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED",
        "warnings": [
            "Codex Desktop may be the new ChatGPT.app (bundle ID com.openai.codex).",
            "CLI not found on PATH does not prove it is not installed elsewhere.",
            "App bundle metadata is not a signature verification or security proof.",
            "Native approval provenance and mandatory OS write blocking remain NOT_TESTED.",
            "No credentials, repo files, settings, or agent/model sessions were accessed.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Explicit new JSON path; never overwrite")
    parser.add_argument("--no-spotlight", action="store_true", help="Skip Spotlight query")
    args = parser.parse_args(argv)
    result = json.dumps(report(use_spotlight=not args.no_spotlight), indent=2, ensure_ascii=False) + "\n"
    if args.output is None:
        sys.stdout.write(result)
        return 0
    path = args.output.expanduser()
    if not path.parent.is_dir():
        parser.error("Output parent must already exist")
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(result)
    except FileExistsError:
        parser.error("Refusing to overwrite an existing report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

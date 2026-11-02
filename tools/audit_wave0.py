#!/usr/bin/env python3
"""Read-only static baseline audit. No adapter certification or OS enforcement claim."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / 'source-preview' / 'Agent_Workflow_System_V3'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 128), b''):
            h.update(chunk)
    return h.hexdigest()


def inspect():
    codex = PREVIEW / 'kit' / '.codex' / 'hooks.json'
    claude = PREVIEW / 'kit' / '.claude' / 'settings.json'
    engine = PREVIEW / 'kit' / '.agentflow' / 'bin' / 'agentflow.py'
    files = [codex, claude, engine, PREVIEW / 'install.py', PREVIEW / 'tests' / 'test_fast_core.py']
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    c, a = (json.loads(p.read_text(encoding='utf-8')) if p.is_file() else {} for p in (codex, claude))
    source = engine.read_text(encoding='utf-8') if engine.is_file() else ''
    core = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(PREVIEW / 'tests'), '-v'],
                          cwd=PREVIEW, capture_output=True, text=True)
    extra = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'), '-p', 'test_wave0_installer.py', '-v'],
                           cwd=ROOT, capture_output=True, text=True)
    return {
        'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'designation': 'DEVELOPMENT_BASELINE_NOT_INSTALLABLE',
        'wave': 'D0',
        'source_hashes': {str(p.relative_to(ROOT)): sha256(p) for p in files if p.is_file()},
        'missing_reference_files': missing,
        'preview_hook_events': {
            'codex_configured': sorted(c.get('hooks', {}).keys()),
            'claude_configured': sorted(a.get('hooks', {}).keys()),
            'NOTE': 'Configured events do not prove actual hook coverage or write enforcement',
        },
        'source_observations': {
            'preapproval_drafts_inside_working_tree': "TASK_ROOT = ROOT / 'docs' / 'agentflow' / 'tasks'" in source,
            'sqlite_state_available': 'sqlite3.connect(' in source,
            'time_limited_leases_present': 'SESSION_LEASE_SECONDS = 120' in source,
            'chat_approval_handler_present': 'def approve_from_user(' in source,
            'signed_human_approval_verified': False,
            'os_level_enforcement_verified': False,
            'macos_four_surface_certification': False,
        },
        'test_results': {
            'preview_core': {'pass': core.returncode == 0, 'summary': core.stderr.strip().splitlines()[-2:]},
            'wave0_installer': {'pass': extra.returncode == 0, 'summary': extra.stderr.strip().splitlines()[-2:]},
        },
        'g0_status': 'PASS' if not missing and core.returncode == 0 and extra.returncode == 0 else 'FAIL',
        'g1_to_g7_status': 'NOT_RUN',
        'platform_certification_status': {
            name: 'NOT_CERTIFIED' for name in ('Codex Desktop', 'Codex CLI', 'Claude Desktop Code', 'Claude Code CLI')
        },
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, help='Optional JSON output. Static scan otherwise writes nothing.')
    args = p.parse_args()
    report = inspect()
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding='utf-8')
    else:
        print(serialized)
    return 0 if report['g0_status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())

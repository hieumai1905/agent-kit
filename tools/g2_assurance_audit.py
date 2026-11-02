#!/usr/bin/env python3
"""One-shot LOCAL assurance test runner. Never approves/installs/edits product repos.

This script always reports G2 blocked until an INDEPENDENT native Mac
certification is performed. It only tests the Python prototype + scratch lab.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys
import time

NONCERTIFIED='BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED'
ROOT = Path(__file__).resolve().parents[1]


def run_suite(label: str, command: list[str], timeout: int = 150) -> dict:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
    output = result.stdout + result.stderr
    count = re.search(r'Ran (\d+) tests?', output)
    return {
        'label': label,
        'exit_code': result.returncode,
        'test_count': int(count.group(1)) if count else None,
        'success': result.returncode == 0 and ('OK' in output) and bool(count),
        'log_excerpt': output[-2500:],
    }


def audit() -> dict:
    coverage=json.loads((ROOT/'docs/G2_ADVERSARIAL_COVERAGE.json').read_text(encoding='utf-8'))
    suites=[
        run_suite('D0-D2.1 local unit + adversarial (single tree)',
                  [sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-q']),
        run_suite('Legacy Preview regression',
                  [sys.executable,'-m','unittest','discover','-s','source-preview/Agent_Workflow_System_V3/tests',
                   '-p','test_fast_core.py','-q']),
    ]
    return {
        'timestamp_epoch': int(time.time()),
        'artifact': 'Agent Workflow System V3 G2.1 local assurance research',
        'G2': NONCERTIFIED,
        'enforced_execution': False,
        'native_mac_security_certified': False,
        'trusted_human_approval_installed': False,
        'direct_write_paths_mandatorily_blocked': False,
        'ready_for_user_native_certification_batch': False,
        'all_local_tests_pass': all(s['success'] for s in suites),
        'local_test_count': sum(s['test_count'] or 0 for s in suites),
        'suites': suites,
        'threats_reviewed': len(coverage['items']),
        'coverage_status_breakdown': dict(Counter(r['evidence_status'] for r in coverage['items'])),
        'provenance_note': ('Local synthetic tests do not establish native macOS enforcement. '
                            'All Codex/Claude surface certification remains withheld.'),
        'observed_previous_mac_result': 'Preexisting hardlink alias changed protected canary in synthetic Seatbelt lab v0.1',
        'safe_next_step': ('Implement protected macOS human approval and writer service with '
                           'separate OS enforcement; then conduct one complete, predefined native acceptance batch.'),
    }


def main() -> int:
    try:
        report = audit()
    except Exception as exc:
        report = {'G2': NONCERTIFIED, 'all_local_tests_pass': False,
                  'error': f'{type(exc).__name__}: {exc}'}
    dest = ROOT/'.release'/'G2_1_LOCAL_ASSURANCE.json'
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('G2','all_local_tests_pass') if k in report},ensure_ascii=False))
    if report.get('all_local_tests_pass'):
        print(f"LOCAL TESTS PASS: {report['local_test_count']} | G2 STILL NOT_CERTIFIED")
        return 0
    return 2


if __name__ == '__main__':
    raise SystemExit(main())

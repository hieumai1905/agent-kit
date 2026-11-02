#!/usr/bin/env python3
"""D2 development audit: runs 4 local suites, does NOT certify macOS GUI security."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import os
import platform
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
SUITES={
    'preview_core': ('source-preview/Agent_Workflow_System_V3/tests','test_fast_core.py',5),
    'wave0_installer': ('tests','test_wave0_installer.py',2),
    'wave1_state': ('tests','test_wave1_state.py',38),
    'wave2_security_lab': ('tests','test_wave2_security.py',69),
}

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for piece in iter(lambda:f.read(1048576),b''):
            h.update(piece)
    return h.hexdigest()

def run_audit():
    try:
        import cryptography
        crypto_version=cryptography.__version__
    except ImportError:
        crypto_version=None
    report={
        'generated_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'release':'D2_DEVELOPMENT_PROTOTYPE_NOT_INSTALLABLE',
        'host_os':platform.system(), 'host_platform':platform.platform(),
        'python_version':platform.python_version(),
        'optional_crypto_available':bool(crypto_version),
        'cryptography_version':crypto_version,
        'suites':{},'source_sha256':{},'total_tests':0,
        'gate_status':{'G0':'NOT_RUN','G1':'NOT_RUN',
                       'G2':'BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED',
                       **{f'G{i}':'NOT_RUN' for i in range(3,8)}},
        'all_adapters':{name:'NOT_CERTIFIED' for name in
                        ('Codex Desktop','Codex CLI','Claude Desktop Code','Claude Code CLI')},
        'native_os_enforcement_tests':'NOT_RUN',
        'trusted_human_approval':'NOT_IMPLEMENTED',
        'mandatory_write_boundary':'NOT_IMPLEMENTED',
        'g2_prototype_checks':'NOT_RUN',
        'hard_limitations':[
            'Ed25519 verifies signer possession, not human presence or protected signer identity',
            'Same-UID agent can tamper with same-UID SQLite/config; no trusted host separation',
            'All product writes denied; only scratch mutation lab tests ran',
            'No actual Codex/Claude GUI/CLI write bypass tests on macOS',
            'G2 may not be marked PASS by this development test runner',
        ],
    }
    all_pass=True
    for name,(folder,pattern,expected_min) in SUITES.items():
        cmd=[sys.executable,'-m','unittest','discover','-s',folder,'-p',pattern,'-v']
        proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=120,
                            env=dict(os.environ,PYTHONPATH=str(ROOT)))
        match=re.search(r'Ran (\d+) tests?',proc.stderr)
        count=int(match.group(1)) if match else 0
        passed=proc.returncode==0 and count>=expected_min
        report['suites'][name]={'tests_executed':count,'passed':passed,
                                 'exit_code':proc.returncode,
                                 'command':' '.join(cmd),
                                 'tail':(proc.stdout+'\n'+proc.stderr).splitlines()[-7:]}
        report['total_tests']+=count
        all_pass &= passed
    for sub in ('agentflow_core','agentflow_security','tests','tools'):
        for path in sorted((ROOT/sub).glob('*.py')):
            report['source_sha256'][path.relative_to(ROOT).as_posix()] = sha256_file(path)
    report['gate_status']['G0']='PASS' if all(report['suites'][i]['passed'] for i in ('preview_core','wave0_installer')) else 'FAIL'
    report['gate_status']['G1']='PASS' if (report['gate_status']['G0']=='PASS' and
                           report['suites']['wave1_state']['passed']) else 'FAIL'
    report['g2_prototype_checks']='PASS' if (all_pass and crypto_version and
                              report['gate_status']['G1']=='PASS') else 'FAIL'
    return report

def main(argv=None):
    p=argparse.ArgumentParser(description='D2 local tests; G2 always BLOCKED until native macOS certification')
    p.add_argument('--output',type=Path)
    args=p.parse_args(argv)
    report=run_audit()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    else:
        print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['g2_prototype_checks']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())

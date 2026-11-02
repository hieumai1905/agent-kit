#!/usr/bin/env python3
"""Reproducible D1 gate audit: stdlib-only, runs exclusively on temporary repos.

It does NOT certify macOS GUI permissions or a trusted write boundary.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

SUITES={
    'preview_core': [sys.executable,'-m','unittest','discover','-s',
                     'source-preview/Agent_Workflow_System_V3/tests','-p','test_fast_core.py','-v'],
    'wave0_installer': [sys.executable,'-m','unittest','discover','-s','tests',
                       '-p','test_wave0_installer.py','-v'],
    'wave1_state': [sys.executable,'-m','unittest','discover','-s','tests',
                    '-p','test_wave1_state.py','-v'],
}
SOURCE_PATHS=[
  'agentflow_core/__init__.py','agentflow_core/errors.py',
  'agentflow_core/schema.py','agentflow_core/states.py',
  'agentflow_core/db.py','agentflow_core/coordinator.py',
  'agentflow_core/cli.py', 'tests/test_wave1_state.py',
  'tools/audit_wave1.py',
]


def checksum(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=None)
    args=parser.parse_args()
    report={'generated_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'release':'D1_DEVELOPMENT_NOT_CERTIFIED',
            'python_version':platform.python_version(),
            'execution_platform':platform.platform(),
            'suites':{},'source_sha256':{},
            'gate_status':{'G0':'NOT_RUN','G1':'NOT_RUN',
                           **{f'G{n}':'NOT_RUN' for n in range(2,8)}},
            'certification':{name:'NOT_CERTIFIED' for name in
              ('Codex Desktop','Codex CLI','Claude Desktop Code','Claude Code CLI')},
            'explicit_limitations':['No signed/trusted approval',
              'No enforced product write boundary',
              'No macOS GUI/CLI capability tests',
              'Legacy Preview installer is not D1 integration kit']}
    total=0
    for name,cmd in SUITES.items():
        env=dict(os.environ,PYTHONPATH=str(ROOT))
        run=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=90)
        tail=(run.stdout+'\n'+run.stderr).splitlines()[-10:]
        match=re.search(r'Ran (\d+) tests?',run.stderr)
        count=int(match.group(1)) if match else 0
        total+=count
        report['suites'][name]={
            'command':' '.join(cmd),'passed':run.returncode==0 and count>0,
            'tests_executed':count,'exit_code':run.returncode,'tail':tail}
    for source in SOURCE_PATHS:
        file=ROOT/source
        if file.exists(): report['source_sha256'][source]=checksum(file)
    report['tests_executed']=total
    report['gate_status']['G0']='PASS' if all(report['suites'][key]['passed']
                   for key in ('preview_core','wave0_installer')) else 'FAIL'
    report['gate_status']['G1']='PASS' if (report['gate_status']['G0']=='PASS' and
          report['suites']['wave1_state']['passed'] and
          len(report['source_sha256'])==len(SOURCE_PATHS) and
          report['suites']['wave1_state']['tests_executed']>=30) else 'FAIL'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    else:
        print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['gate_status']['G1']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())

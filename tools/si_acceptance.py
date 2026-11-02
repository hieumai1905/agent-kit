#!/usr/bin/env python3
"""Repeatable local SI01–14 evidence report. Never grants macOS certification.

Runs only synthetic fixture tests and fixed CLI preflights. No provider jobs,
no privileged helper, no activation of hooks or real repository writes.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]

STATUS={
 'SI-01':('BLOCKED_NATIVE_TRUST','Fail-closed authority report only; no independent human/protected store'),
 'SI-02':('LOCAL_OBSERVATION_ONLY','Per-provider metadata fingerprints; native certificates missing'),
 'SI-03':('LOCAL_IMPLEMENTED_RESTRICTED','External state location; export is preview-only'),
 'SI-04':('PRECHECK_ONLY','Canonical path/baseline checks; no trusted atomic mutation broker'),
 'SI-05':('DRY_RUN_ONLY','Git status scope and foreign-index detection; no staging/commit'),
 'SI-06':('COOPERATIVE_DIAGNOSTICS','Persistent sessions/generation/heartbeat checks; no enforced fence'),
 'SI-07':('CONSERVATIVE_DIAGNOSTICS','Side-effect classifier; dynamic commands remain unknown'),
 'SI-08':('LOCAL_DRAFT_ONLY','Versioned dependency graph draft and targeted invalidation; no trusted evidence'),
 'SI-09':('LOCAL_PREVIEW_ONLY','Natural language route, duplicate/disambiguation; no GUI provenance'),
 'SI-10':('LOCAL_DRAFT_ONLY','Policy exception draft with owner/scope/reason/expiry, never activated'),
 'SI-11':('LOCAL_RECOVERY_DIAGNOSTICS','SQLite doctor/backup verification, external file reconciliation pending'),
 'SI-12':('LOCAL_RULES_ONLY','Action-specific authority matrix, no grants issued'),
 'SI-13':('LOCAL_PLANNING_ONLY','Verification footprint collision/reuse hints, no tests executed'),
 'SI-14':('GUIDANCE_ONLY','Release doctor; native install/upgrade/cross-provider E2E not certified'),
}

def run():
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
    proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests',
                         '-p','test_si_integration.py','-q'],
                        cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                        capture_output=True,text=True,timeout=120)
    out=proc.stdout+'\n'+proc.stderr
    found=re.search(r'Ran (\d+) tests?',out)
    n=int(found.group(1)) if found else None
    with tempfile.TemporaryDirectory(prefix='si-acceptance-') as tmp:
        folder=Path(tmp);repo=folder/'repo';repo.mkdir()
        sentinel=repo/'sentinel.txt';sentinel.write_text('UNCHANGED\n')
        base=[sys.executable,str(ROOT/'tools/agentflow.py'),'--repo',str(repo),
              '--state-home',str(folder/'state')]
        cmds=[('trust',['si-trust']),('metadata',['si-metadata']),
              ('release_doctor',['si-release-doctor']),
              ('action',['si-action','GIT_PUSH']),
              ('intent',['si-intent','Duyệt'])]
        command_results=[]
        for label,args in cmds:
            p=subprocess.run(base+args,cwd=folder,env=env,capture_output=True,text=True,timeout=15)
            value=json.loads(p.stdout) if p.returncode==0 else {}
            command_results.append({'name':label,'exit_code':p.returncode,
                                    'si_response':value.get('si'),
                                    'write_authorized':value.get('code_write_enabled',value.get('authorized',False))})
        unchanged=sentinel.read_text()=='UNCHANGED\n' and {x.name for x in repo.iterdir()}=={'sentinel.txt'}
    covered=sorted(set(re.findall(r'def test_(si\d{2})_',
                     (ROOT/'tests'/'test_si_integration.py').read_text())))
    complete=proc.returncode==0 and n is not None and len(covered)==14 and unchanged and all(
             r['exit_code']==0 and not r['write_authorized'] for r in command_results)
    return {'product':'Agent Workflow System V3.0 SI01–SI14 Candidate',
        'timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'host':{'os':platform.system(),'arch':platform.machine(),
                'release':platform.release(),'python':platform.python_version()},
        'focus':'SI01-SI14_ONLY','excluded_from_this_wave':'EA01-EA16_NO_NEW_WORK',
        'local_tests':{'executed':n,'passed':proc.returncode==0 and n is not None,
                       'log_tail':out[-600:]},
        'si_test_modules_covered':covered,
        'cli_smoke':command_results,'scratch_repo_unchanged':unchanged,
        'local_acceptance_pass':complete,
        'status':{name:{'implementation_level':value[0],'limitation':value[1]}
                  for name,value in STATUS.items()},
        'four_provider_native_certification':'NOT_CERTIFIED',
        'G2':'BLOCKED_NATIVE_TRUST_AND_OS_WRITE_BOUNDARY',
        'G5':'BLOCKED_NO_ENFORCED_WRITER_OR_TRUSTED_VERIFICATION',
        'G7':'PARTIAL_NATIVE_INSTALL_AND_E2E_NOT_TESTED',
        'trusted_approval_available':False,'code_write_authorized':False,
        'note':'LOCAL PASS does not imply SI01-14 production completion or any macOS/coding-agent certification.'}

if __name__=='__main__':
    report=run()
    out=ROOT/'release'/'SI14_LOCAL_ACCEPTANCE.json'
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'pass':report['local_acceptance_pass'],
                      'tests':report['local_tests']['executed'],
                      'covered_si_ids':len(report['si_test_modules_covered']),
                      'G2':report['G2'],'report':str(out)},indent=2))
    raise SystemExit(0 if report['local_acceptance_pass'] else 2)

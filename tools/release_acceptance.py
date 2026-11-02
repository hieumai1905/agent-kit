#!/usr/bin/env python3
"""One-shot LOCAL integration regression. Not native macOS security certification.

Only test-created temp repositories and the extracted kit's release report are
changed. Never calls Codex/Claude, sudo, launchctl, model APIs or a product repo.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]

def _test(cmd,name):
    try:
        p=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         text=True,timeout=180,check=False,
                         env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        output=p.stdout+'\n'+p.stderr
        match=re.search(r'Ran (\d+) tests?',output)
        count=int(match.group(1)) if match else None
        def reported(label):
            found=re.search(label+r'=(\d+)',output)
            return int(found.group(1)) if found else 0
        skipped=reported('skipped');failures=reported('failures');errors=reported('errors')
        return {'name':name,'exit_code':p.returncode,
                'test_count':count,'skipped_count':skipped,
                'failure_count':failures,'error_count':errors,
                'passed_count':max(0,count-skipped-failures-errors) if count is not None else None,
                'pass':p.returncode==0 and bool(match) and re.search(r'(?m)^OK(?: \(skipped=\d+\))?$',output) is not None,
                'log_excerpt':output[-1500:]}
    except Exception as e:
        return {'name':name,'pass':False,'error':f'{type(e).__name__}: {e}'}


def _scratch_smoke():
    try:
        with tempfile.TemporaryDirectory(prefix='agentflow-rc-acceptance-') as d:
            root=Path(d);repo=root/'repo';repo.mkdir()
            marker=repo/'keep.txt';marker.write_text('do not modify\n')
            source=ROOT/'tools'/'agentflow.py'
            base=[sys.executable,str(source),'--repo',str(repo),'--state-home',str(root/'state')]
            cases=[]
            for label,command in [
                ('read_only_scan',['scan']),
                ('guidance_dry_run',['install-guidance']),
                ('natural_intake',['interact','Thêm bộ lọc sản phẩm']),
                ('resume_navigation',['interact','tiếp tục bộ lọc sản phẩm']),
                ('capability_matrix',['capabilities']),
                ('si_boundary',['si-trust']),
                ('si_native_doctor',['si-release-doctor']),
                ('si_action_scope',['si-action','GIT_COMMIT']),
                ('handoff_task_list',['tasks']),
            ]:
                p=subprocess.run(base+command,cwd=root,text=True,capture_output=True,timeout=10)
                cases.append({'step':label,'exit_code':p.returncode,
                              'pass':p.returncode==0,
                              'log_excerpt':p.stderr[-200:]})
            return {'pass':all(x['pass'] for x in cases) and marker.read_text()=='do not modify\n' and
                           set(x.name for x in repo.iterdir())=={'keep.txt'},
                    'steps':cases,'repo_product_files_unchanged':marker.read_text()=='do not modify\n'}
    except Exception as e:
        return {'pass':False,'error':f'{type(e).__name__}: {e}'}


def audit():
    suites=[_test([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-q'],
                  'D0–D2.1 + D3–D7 local regression'),
            _test([sys.executable,'-m','unittest','discover',
                   '-s','source-preview/Agent_Workflow_System_V3/tests',
                   '-p','test_fast_core.py','-q'],'Legacy Preview smoke')]
    scratch=_scratch_smoke()
    practical_process=subprocess.run([sys.executable,str(ROOT/'tools/practical_smoke.py')],
        cwd=ROOT,stdin=subprocess.DEVNULL,text=True,capture_output=True,
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},timeout=80,check=False)
    try: practical=json.loads((ROOT/'release/PRACTICAL_SMOKE.json').read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError): practical={'pass':False,'error':'No valid practical report'}
    practical['runner_exit_code']=practical_process.returncode
    practical['pass']=bool(practical.get('pass')) and practical_process.returncode==0
    all_pass=all(x['pass'] for x in suites) and scratch['pass'] and practical['pass']
    guide_names=['guides/00_BAT_DAU_V1_0.md','release/V1_0_SCOPE.md',
                 'guides/01_HUONG_DAN_TICH_HOP.md','guides/02_HUONG_DAN_SU_DUNG.md',
                 'guides/03_BAO_CAO_GIOI_HAN_VA_NGHIEM_THU.md']
    guides_present=all((ROOT/n).is_file() for n in guide_names)
    try:
        inventory_process=subprocess.run([sys.executable,str(ROOT/'tools/mac_inventory_v2.py'),
                                           '--no-spotlight'],cwd=ROOT,stdin=subprocess.DEVNULL,
                                           text=True,capture_output=True,timeout=12,check=False)
        inventory=json.loads(inventory_process.stdout) if inventory_process.returncode==0 else                   {'status':'DISCOVERY_FAILED','error':inventory_process.stderr[-300:]}
    except Exception as e:
        inventory={'status':'DISCOVERY_FAILED','error':str(e)}
    return {'product':'Agent Workflow V3 Minimal Repo Integration Kit',
            'version':'1.0.1',
            'working_revision':'V1.0.1-BUGFIX-2026-11-02',
            'release_class':'PRACTICAL_ADVISORY_RELEASE_NOT_SECURITY_CERTIFIED',
            'release_scope':'Frozen practical v1.0.1 bugfix; Codex local, one sequential writer, voluntary ADVISORY process',
            'epoch':int(time.time()),
            'host':{'os':platform.system(),'release':platform.release(),
                    'machine':platform.machine(),'python':platform.python_version()},
            'local_tests':suites,'local_test_count':sum(x.get('test_count') or 0 for x in suites),
            'local_test_passed_count':sum(x.get('passed_count') or 0 for x in suites),
            'local_test_skipped_count':sum(x.get('skipped_count') or 0 for x in suites),
            'native_app_discovery':inventory,
            'local_tests_pass':all_pass,'scratch_repo_smoke':scratch,
            'practical_e2e_smoke':{'pass':practical['pass'],'steps':practical.get('step_count'),
                 'product_fixture_unchanged':practical.get('product_fixture_unchanged'),
                 'providers_executed':False},'guides_present':guides_present,
            'G0':'HISTORICAL_LOCAL_PASS','G1':'LOCAL_PASS' if suites[0]['pass'] else 'LOCAL_REGRESSION_FAILED',
            'G2':'BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED',
            'G3':'PARTIAL_LOCAL_RIG_AND_NATURAL_RESUME_NOT_GUI_CERTIFIED',
            'G4':'PARTIAL_CONTRACT_LINKED_DRAFT_PLANNING',
            'G5':'BLOCKED_NO_ENFORCED_PRODUCT_CODE_WRITER',
            'G6':'PARTIAL_LOCAL_HANDOFF_MODEL_ADVISOR_NO_TRUSTED_COMPLETION',
            'G7':('PARTIAL_REPO_GUIDANCE_INSTALL_E2E_PASS_NATIVE_NOT_CERTIFIED' if scratch['pass'] and practical['pass']
                  else 'LOCAL_INSTALL_SMOKE_FAILED_NATIVE_NOT_CERTIFIED'),
            'si_wave_scope':'SI01-SI14_PRESERVED',
            'delivery_scope':'D3_D7_PRACTICAL_REPO_INTEGRATION',
            'ea_wave_scope':'NO_NEW_EA01_EA16_IMPLEMENTATION',
            'trusted_approval_available':False,
            'mandatory_write_boundary_available':False,
            'same_worktree_multiwriter_certified':False,
            'user_native_acceptance_required_to_claim_final_release':True,
            'final_release_definition':'Legacy FINAL/ENFORCED security certification; not the approved practical v1.0 distribution',
            'user_action_now':'Read guides/00_BAT_DAU_V1_0.md; inspect existing guidance before any installation or relocation',
            'notes':['PASS of local Python tests does not certify macOS GUI/CLI controls.',
                     'This local runner launches no provider app/model and changes only disposable scratch repos; separate historical A4 live results are in release/A4_RETRY_ACCEPTANCE.json.',
                     'ADVISORY is optional, opt-in, not OS-enforced; STRICT is default.',
                     'This report is generated by an unprivileged process and is not a protected attestation.']}


def main():
    report=audit()
    out=ROOT/'release'/'ONE_SHOT_ACCEPTANCE.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'local_tests_pass':report['local_tests_pass'],
                      'local_test_count':report['local_test_count'],
                      'G2':report['G2'],
                      'G3':report['G3'],'G4':report['G4'],'G5':report['G5'],
                      'G6':report['G6'],'G7':report['G7'],
                      'report':str(out)},indent=2,ensure_ascii=False))
    return 0 if report['local_tests_pass'] and report['guides_present'] else 2

if __name__=='__main__':raise SystemExit(main())

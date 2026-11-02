#!/usr/bin/env python3
"""One-shot scratch-repository demonstration. Never touches user's repo.

This demonstrates repository instruction installation, natural task intake,
versioned contract/plan, session handoff, review and uninstall/rollback. It does
NOT run a Codex/Claude provider or certify native approval/enforcement.
"""
from __future__ import annotations
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/'tools'/'agentflow.py'

def demo():
    steps=[]
    with tempfile.TemporaryDirectory(prefix='agentflow-practical-smoke-') as td:
        base=Path(td);repo=base/'repo';repo.mkdir()
        state=base/'state';fixture=repo/'app.py';fixture.write_text('print("original")\n')
        expected=sha256(fixture.read_bytes()).hexdigest()
        subprocess.run(['git','init','-q'],cwd=repo,check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8)
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
        def run(name,parts,expect=0):
            command=[sys.executable,str(CLI),'--repo',str(repo),'--state-home',str(state),*parts]
            proc=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,text=True,
                                capture_output=True,env=env,timeout=15,check=False)
            ok=proc.returncode==expect
            try: data=json.loads(proc.stdout) if ok and proc.stdout.strip() else None
            except json.JSONDecodeError:ok=False;data=None
            steps.append({'name':name,'pass':ok,'exit_code':proc.returncode,
                          'error_excerpt':proc.stderr[-280:] if not ok else ''})
            if not ok:raise RuntimeError(f'{name}: exit={proc.returncode} {proc.stderr[-300:]}')
            return data
        run('version',['version'])
        run('initial_doctor',['doctor'])
        dry=run('install_dry_run',['install-guidance'])
        assert all(i['would_change'] for i in dry['changes'])
        assert [p.name for p in repo.iterdir() if p.name not in ('.git',)]==['app.py']
        advisory=run('explicit_advisory_install',['install-guidance','--mode','advisory','--apply'])
        assert advisory['applied'] and not advisory['write_enforced']
        run('post_install_doctor',['doctor'])
        task=run('natural_intake',['interact','Sửa nhãn nút trong màn hình đăng nhập'])
        task_id=task['task']['task_id']
        run('task_search',['tasks'])
        result=run('resume_by_natural_name',['resume','Sửa nhãn nút trong màn hình đăng nhập'])
        assert result['action']=='RESUME_READ_ONLY' and not result['write_authorized']
        content={'analysis_level':'QUICK',
                 'objective':'Đổi đúng nhãn nút đăng nhập để người dùng nhận biết',
                 'accepted_behavior':['Nhãn tiếng Việt hiển thị đúng'],
                 'preserve':['Giữ nguyên hành vi đăng nhập'],
                 'scope':{'functional':['Nhãn giao diện đăng nhập'],'excluded':['logic auth']},
                 'acceptance':['Nhãn hiển thị tiếng Việt trên màn hình đăng nhập'],
                 'verification_strategy':['Inspect relevant UI rendering'],
                 'scenarios':[{'name':'normal','disposition':'VERIFY'}],
                 'impact':{'affected_components':['login label']},
                 'gaps':[],'open_questions':[]}
        spec=base/'contract.json';spec.write_text(json.dumps(content,ensure_ascii=False))
        checked=run('check_contract',['check-contract',str(spec)])
        assert checked['status']=='READY_FOR_HUMAN_REVIEW'
        proposed=run('versioned_contract_draft',['propose-contract',task_id,str(spec)])
        assert not proposed['trusted_approval'] and not proposed['write_authorized']
        plan={'selected_approach':'Change only the UI label',
              'verification_strategy':['Inspect rendered login UI']}
        pf=base/'plan.json';pf.write_text(json.dumps(plan))
        run('technical_plan_draft',['draft-plan',task_id,str(pf),'--save'])
        work={'items':[{'key':'W1','title':'Change label','verification':['UI check']}]}
        wf=base/'work.json';wf.write_text(json.dumps(work))
        run('work_dag_draft',['draft-work',task_id,str(wf),'--save'])
        progress=base/'progress.json';progress.write_text(json.dumps({'next_action':'Review exact patch in provider chat'}))
        run('checkpoint_draft',['checkpoint',task_id,str(progress)])
        reported=run('unverified_test_report',['report-check',task_id,'--kind','UI','--reported-status','PASS'])
        assert reported['attestation']=='UNVERIFIED'
        review=run('final_review',['final-review',task_id])
        assert not review['auto_complete'] and review['definition_of_done']=='NOT_VERIFIED'
        run('handoff',['handoff',task_id])
        run('repo_status',['repo-status'])
        run('remove_guidance',['remove-guidance','--apply'])
        assert not (repo/'AGENTS.md').exists() and not (repo/'CLAUDE.md').exists()
        strict=run('strict_install',['install-guidance','--apply'])
        run('rollback_install',['rollback-guidance',strict['transaction_id'],'--apply'])
        assert not (repo/'AGENTS.md').exists() and not (repo/'CLAUDE.md').exists()
        return {'pass':all(s['pass'] for s in steps) and sha256(fixture.read_bytes()).hexdigest()==expected,
                'steps':steps,'step_count':len(steps),'product_fixture_unchanged':sha256(fixture.read_bytes()).hexdigest()==expected,
                'final_repo_files':sorted(p.name for p in repo.iterdir() if p.name!='.git'),
                'state_outside_repo':True,
                'providers_executed':False,'trusted_approval':False,'native_enforcement_certified':False,
                'note':'Smoke runs on disposable scratch repo only; no provider or product code writes.'}

def main():
    try:r=demo()
    except Exception as e:r={'pass':False,'error':f'{type(e).__name__}: {e}'}
    out=ROOT/'release'/'PRACTICAL_SMOKE.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({'created_at_epoch':int(time.time()),
            'host':{'os':platform.system(),'arch':platform.machine(),
                    'python':platform.python_version()},**r},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'pass':r['pass'],'steps':r.get('step_count'),'report':str(out),
                      'error':r.get('error')},ensure_ascii=False))
    return 0 if r['pass'] else 2
if __name__=='__main__':raise SystemExit(main())

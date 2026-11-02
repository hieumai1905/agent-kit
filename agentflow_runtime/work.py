"""Three everyday operations composed over existing contracts and CAS checkpoints."""
from contextlib import closing
import hashlib
import json
from pathlib import Path

from agentflow_core import StoreError, ConflictError
from .records import WorkflowRecords
from .navigator import TaskNavigator, normalize
from .continuity import checkpoint_template, save_checkpoint
from .status import observe_source_hashes
from .rig import analyze_readiness
from .verification import assess


def resolve(records, topic):
    # IDs are internal; normal use resolves a title across all history.
    with closing(records.store.connect(read_only=True)) as cn:
        row = cn.execute('SELECT id FROM tasks WHERE id=? AND repo_id=?', (topic, records.store.repo_id)).fetchone()
    if row:
        return row['id']
    found = TaskNavigator(records).search(topic)
    if found['status'] != 'UNAMBIGUOUS':
        raise StoreError('Choose a specific existing task title; candidates: ' + ', '.join(x['title'] for x in found['choices']))
    return found['selected_task_id']


def hashes_for(repo, paths):
    if not isinstance(paths, list) or len(paths) > 32:
        raise StoreError('source_paths must contain at most 32 task-owned relative paths')
    result = {}
    root = Path(repo).resolve()
    for name in paths:
        if not isinstance(name, str): raise StoreError('Invalid source path')
        p = root / name
        if p.is_symlink() or not p.resolve().is_relative_to(root) or '.git' in p.parts:
            raise StoreError('Source paths must stay inside product tree without symlinks')
        if not p.is_file() or p.stat().st_size > 8 * 1024 * 1024:
            raise StoreError('Source file missing/too large: ' + name)
        result[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    if result and observe_source_hashes(root, result)['status'] != 'CURRENT':
        raise ConflictError('Source observation incomplete; inspect paths before saving')
    return result


def start(repo, home, title, data, kind='change'):
    if kind in ('question', 'investigate'):
        return {'action': 'ANSWER_OR_INVESTIGATE_READ_ONLY', 'stored': False, 'write_authorized': False}
    contract = data.get('contract', data)
    if not isinstance(contract,dict):raise StoreError('contract must be an object')
    from agentflow_core.db import canonical_json
    if len(canonical_json(contract).encode('utf-8'))>256*1024:raise StoreError('Contract exceeds 256 KiB; reduce to relevant facts before saving')
    ready = analyze_readiness(contract)
    if ready['status'] != 'READY_FOR_HUMAN_REVIEW':
        raise StoreError('Contract not ready: ' + '; '.join(ready['blockers']))
    for key in ('preserve', 'verification_strategy'):
        if not isinstance(contract.get(key), list) or not contract[key] or any(not isinstance(x,str) or not x.strip() for x in contract[key]):
            raise StoreError(key + ' must explicitly describe constraints/checks (use an explicit no-extra-constraints entry if appropriate)')
    if contract.get('work_type') not in ('BUG','FEATURE','MAINTENANCE'):
        raise StoreError('work_type must be BUG, FEATURE or MAINTENANCE; BUG requires original reproduction evidence')
    facts = contract.get('knowledge', {})
    if facts and (not isinstance(facts, dict) or any(k not in ('confirmed', 'observed', 'proposed') or not isinstance(v,list) for k,v in facts.items())):
        raise StoreError('knowledge separates confirmed, observed and proposed lists')
    from .artifacts import Artifacts
    manager=Artifacts(repo,home)
    artifact_check=manager.check() if manager.inventory() is not None else {'status':'NOT_CONFIGURED','next_action':'Complete setup before effects'}
    if artifact_check['status']=='BLOCKED':raise StoreError('Contract handoff blocked by artifacts: '+'; '.join(artifact_check['reasons']))
    rec = WorkflowRecords(repo, home)
    matches = TaskNavigator(rec).search(title)
    if matches['choices'] and matches['choices'][0]['match_score'] >= .65:
        return {'action': 'RECONCILE_EXISTING_TASK', 'matches': matches, 'new_task_created': False,
                'next_action': 'Resume the matching task; use propose-contract for an explicit scope revision.', 'write_authorized': False}
    created = rec.create_preflight(title, title, {'route': contract.get('analysis_level', 'STANDARD'),
                                   'semantic_correctness_verified': False}, normalize(title), contract=contract)
    tid = created['task_id']
    body = checkpoint_template(rec, tid, 'HANDOFF')['checkpoint']
    body.update(summary='Contract prepared; awaiting the user decision', completed=['Read relevant context; drafted contract'],
                remaining=['Obtain explicit decision on this contract'], next_action='Present contract and wait for the user decision')
    checkpoint = save_checkpoint(rec, tid, body)
    return {'action': 'PRESENT_CONTRACT', 'task_id': tid, 'contract': contract,
            'binding': {'contract_revision': created['contract_revision'], 'contract_sha256': created['contract_hash']},
            'checkpoint': checkpoint, 'artifact_check':artifact_check,
            'artifact_directory':str(rec.store.state_dir/'artifacts'),
            'decision_input_example':{'contract_sha256':created['contract_hash'],'expected_revision':checkpoint['revision'],
                'decision':{'choice':'APPROVED_OR_REJECTED_AFTER_ACTUAL_USER_DECISION','source':'actual current-chat USER message reference'},
                'source_paths':['existing/task-owned/file']},
            'next_action': 'Wait for this contract decision; then work checkpoint.',
            'trusted': False, 'write_authorized': False}


def checkpoint(repo, home, topic, data):
    rec = WorkflowRecords(repo, home, initialize=False)
    tid = resolve(rec, topic)
    data=dict(data)
    simple=data.get('decision')
    if simple is not None:
        if not isinstance(simple,dict):raise StoreError('decision must contain choice APPROVED/REJECTED and actual USER source')
        data['advisory_decision']={'kind':'DIRECT_HUMAN','decision':simple.get('choice'),'source':simple.get('source')}
        data.setdefault('milestone','CONTRACT_DECISION')
    milestone = data.get('milestone', 'HANDOFF')
    template = checkpoint_template(rec, tid, milestone)
    body = template['checkpoint']
    if milestone=='CONTRACT_DECISION':
        body.update(phase='PREFLIGHT',summary='Current-chat contract decision reported; no patch by this helper',
                    completed=['Recorded reported contract decision'],remaining=['Implementation/verification still require current authorized scope'],
                    next_action='Recheck current decision, contract and sources immediately before patch')
    expected = data.get('expected_revision')
    if type(expected) is not int:
        raise StoreError('expected_revision is required from the previous helper response/resume; reread instead of guessing')
    # Binding is captured by the caller when it read the contract, not silently refreshed here.
    if data.get('contract_sha256') != body['contract_sha256']:
        raise ConflictError('Contract binding changed/missing; resume and reconcile before recording')
    allowed = ('phase', 'summary', 'completed', 'remaining', 'blockers', 'changed_paths', 'next_action',
               'advisory_decision', 'human_contract_decision_observed', 'advisory_delegation','verification_report','new_paths')
    for key in allowed:
        if key in data: body[key] = data[key]
    if milestone == 'CONTRACT_DECISION':
        # A template may carry old provenance. It must never be silently rebound
        # to a new contract in lieu of an explicitly supplied current decision.
        decision = data.get('advisory_decision')
        if not isinstance(decision,dict) or decision.get('kind') != 'DIRECT_HUMAN' or decision.get('decision') not in ('APPROVED','REJECTED') or not decision.get('source'):
            raise StoreError('Direct decision requires kind DIRECT_HUMAN, decision APPROVED/REJECTED and an actual current-chat source reference')
        decision = {**decision, 'contract_sha256': body['contract_sha256'], 'contract_revision': body['contract_revision']}
        body['advisory_decision'] = decision
        body['source_hashes'] = hashes_for(repo, data.get('source_paths', []))
        new_paths=data.get('new_paths',[])
        from .continuity import _paths
        if not _paths(new_paths) or any((Path(repo)/p).exists() or (Path(repo)/p).is_symlink() for p in new_paths):
            raise StoreError('new_paths must be safe relative paths that are still absent')
        body['new_paths']=new_paths
        if not body['source_hashes'] and not new_paths:
            raise StoreError('Decision checkpoint needs source_paths to observe or explicit absent new_paths')
        if not body['source_hashes']:
            del body['source_hashes']
        from .practical import git_snapshot
        body['prewrite_git'] = git_snapshot(repo)
    if milestone == 'IMPLEMENTATION_VERIFICATION':
        body['source_hashes'] = hashes_for(repo, data.get('source_paths', body['changed_paths']))
    if milestone!='CONTRACT_DECISION' and 'source_paths' in data:
        # The caller must first reconcile its intentional in-scope changes.
        # Refresh observations, not the carried decision or contract binding.
        body['source_hashes']=hashes_for(repo,data['source_paths'])
        from .practical import git_snapshot
        body['prewrite_git']=git_snapshot(repo)
    if 'verification_report' in body:
        report=body['verification_report']
        if (not isinstance(report,dict) or report.get('contract_sha256')!=body['contract_sha256']
                or report.get('contract_revision')!=body['contract_revision']
                or not report.get('tested_source_hashes')
                or report['tested_source_hashes']!=body.get('source_hashes')):
            raise ConflictError('Verification must retain its own tested-source/current-contract binding; rerun affected checks, do not rebind old results')
    saved = save_checkpoint(rec, tid, body, expected_revision=expected)
    readback = rec.latest('PROGRESS', task_id=tid)
    if readback['revision'] != saved['revision'] or readback['content'] != body:
        raise ConflictError('Checkpoint readback diverged; do not patch, reread and reconcile')
    result={**saved, 'task_id': tid, 'contract_sha256':body['contract_sha256'], 'readback_matches': True,
            'artifact_directory':str(rec.store.state_dir/'artifacts'),
            'next_action': 'Recheck current decision, contract and sources before effects; saved report is not authorization.'}
    if milestone=='CONTRACT_DECISION' or data.get('prepare_next_batch') is True:
        # Persist -> read back -> re-observe in this invocation. No provider patch
        # is executed here, and a failed recheck must produce a nonzero CLI exit.
        checked=recheck(repo,home,tid,expected_revision=saved['revision'])
        result.update(status=checked['status'],prepatch_check=checked,
                      decision_readback=readback['content'].get('advisory_decision'),
                      observed_source_hashes=readback['content'].get('source_hashes',{}),
                      next_action='Inspect decision_readback and prepatch_check, revalidate actual current USER scope, then use provider tools. Repeat --check only after a gap/relevant change.')
        if checked['status']=='BLOCKED':
            result['next_action']='Stop: reconcile prepatch_check reasons and the actual current USER decision before any patch.'
            return result
        result['finish_input_example']={'contract_sha256':body['contract_sha256'],'expected_revision':saved['revision'],
            'source_paths':list(body.get('source_hashes',{})), 'tested_source_hashes':{'TASK_FILE':'HASH_CAPTURED_AT_TEST_TIME'},
            'summary':'ACTUAL_RESULT','completed':[],'remaining':[],'blockers':[], 'changed_paths':[],
            'checks':[{'kind':'REPRODUCTION_OR_REGRESSION','command':'ACTUAL_COMMAND','executed':False,
                       'exit_code':None,'output_excerpt':'','status':'NOT_RUN','covers':['A1','P1']}],
            'next_action':'Present actual evidence and remaining work'}
    return result


def finish(repo, home, topic, data):
    rec = WorkflowRecords(repo, home, initialize=False)
    tid = resolve(rec, topic)
    contract = rec.core.contract_revision(tid)
    if data.get('contract_sha256') != contract['sha256']:
        raise ConflictError('Finish must be bound to the contract read before verification')
    previous=rec.latest('PROGRESS',task_id=tid)
    decision=previous['content'].get('advisory_decision',{}) if previous else {}
    if decision.get('decision')!='APPROVED' or decision.get('kind')!='DIRECT_HUMAN' or decision.get('contract_sha256')!=contract['sha256']:
        raise StoreError('Finish requires the explicitly reported decision checkpoint for this contract; do not infer approval from code/tests')
    result = assess(contract['content'], data)
    paths = data.get('source_paths', data.get('changed_paths', []))
    actual = hashes_for(repo, paths)
    if not actual or data.get('tested_source_hashes') != actual:
        raise ConflictError('Provide tested_source_hashes captured at check time; current files must match them')
    result.update(contract_sha256=contract['sha256'],contract_revision=contract['revision'],
                  tested_source_hashes=dict(actual))
    from .artifacts import Artifacts
    artifact_check=Artifacts(repo,home).check()
    if artifact_check['status']!='CLEAR':raise StoreError('Handoff blocked by artifact check: '+'; '.join(artifact_check['reasons']))
    body = {**data, 'milestone': 'IMPLEMENTATION_VERIFICATION', 'phase': 'IMPLEMENTED',
            'source_paths': paths, 'summary': data.get('summary', result['reported_verdict']),
            'completed': data.get('completed', []), 'remaining': data.get('remaining', []),
            'blockers': data.get('blockers', []), 'changed_paths': data.get('changed_paths', []),
            'next_action': data.get('next_action', 'Review reported verification and decide acceptance')}
    body['verification_report']=result
    saved = checkpoint(repo, home, tid, body)
    return {**saved, 'verification': result, 'artifact_check':artifact_check, 'auto_complete': False,
            'handoff_saved':True,'handoff_revision':saved['revision'],
            'next_action': 'Handoff saved. Present acceptance evidence and remaining work; no duplicate handoff/checkpoint is needed. Publication is separate.'}


def recheck(repo,home,topic,expected_revision=None):
    rec=WorkflowRecords(repo,home,initialize=False);tid=resolve(rec,topic)
    contract=rec.core.contract_revision(tid);progress=rec.latest('PROGRESS',task_id=tid)
    body=progress['content'] if progress else {};decision=body.get('advisory_decision',{})
    problems=[]
    if expected_revision is not None and (not progress or progress['revision']!=expected_revision):problems.append('Checkpoint changed during recheck; reread and reconcile before patch')
    if decision.get('decision')!='APPROVED' or decision.get('kind')!='DIRECT_HUMAN':problems.append('No reported direct approval')
    if decision.get('contract_sha256')!=contract['sha256'] or body.get('contract_sha256')!=contract['sha256']:problems.append('Decision/checkpoint belongs to another contract')
    from .continuity import _paths
    absent=body.get('new_paths',[])
    if not _paths(absent):raise StoreError('Invalid new_paths in saved checkpoint; reconcile the report')
    source_ok=(body.get('source_hashes') and observe_source_hashes(repo,body['source_hashes'])['status']=='CURRENT') or (not body.get('source_hashes') and absent)
    if not source_ok:problems.append('Source baseline missing or stale; reconcile before patch')
    if any((Path(repo)/p).exists() or (Path(repo)/p).is_symlink() for p in body.get('new_paths',[])):problems.append('A planned new path now exists; reconcile concurrent work')
    from .practical import git_snapshot
    current_git=git_snapshot(repo)
    if not current_git.get('git_available') or current_git.get('changes_truncated'):problems.append('Git observation unavailable/truncated; inspect full scope before patch')
    if body.get('prewrite_git') and body['prewrite_git']!=current_git:problems.append('Git baseline changed after decision; inspect/reconcile before patch')
    from .installer import GuidanceInstaller
    installed=GuidanceInstaller(repo,home,mode='advisory').installed_status()
    if set(installed['installed_files'].values())!={'ADVISORY'}:problems.append('Current guidance is not consistently ADVISORY')
    from .artifacts import Artifacts
    artifacts=Artifacts(repo,home).check()
    if artifacts['status']!='CLEAR':problems.append('Artifact/index check blocked: '+'; '.join(artifacts['reasons']))
    return {'status':'BLOCKED' if problems else 'REPORTED_PRECONDITIONS_CURRENT','reasons':problems,
            'current_chat_decision_must_be_revalidated':True,'trusted':False,'write_authorized':False,
            'next_action':'Stop and reconcile' if problems else 'Agent revalidates actual current-chat decision and scope immediately before its provider patch'}


def compact_resume(out,artifact_check=None,artifact_directory=None):
    if out.get('action')!='RESUME_READ_ONLY':return out
    packet=out['handoff'];contract=packet['contract'];brief=packet['resume_brief']
    def bounded(xs):return [str(x)[:300] for x in xs[:5]] if isinstance(xs,list) else []
    scope=contract.get('scope') if isinstance(contract.get('scope'),dict) else {}
    groups=[brief.get(k,[]) for k in ('reported_completed','reported_remaining','reported_blockers','reported_changed_paths')]
    groups += [contract.get('acceptance',[]),contract.get('preserve',[]),scope.get('functional',[]),scope.get('excluded',[])]
    truncated=any(not isinstance(x,list) or len(x)>5 or any(len(str(v))>300 for v in x) for x in groups)
    truncated=truncated or len(str(contract.get('objective','')))>1000 or len(brief.get('reported_summary') or '')>1000 or len(brief.get('reported_next_action') or '')>500
    source=packet.get('relevant_artifacts',{}).get('PROGRESS',{}).get('source_hashes',{})
    source=source if isinstance(source,dict) else {}
    observed=packet['status_view']['reported_work']['source_freshness']
    git={**out['git']}
    if 'worktree_changes' in git:
        entries=git['worktree_changes']
        git['worktree_changes']=[{**x,'path':str(x.get('path',''))[:300],'previous':str(x['previous'])[:300] if x.get('previous') else None} for x in entries[:10]]
        git['changes_truncated']=git.get('changes_truncated',False) or len(entries)>10
    return {'action':out['action'],'task':packet['task'],
            'contract':{'revision':contract.get('revision'),'sha256':contract.get('sha256'),'objective':str(contract.get('objective',''))[:1000]},
            'acceptance':bounded(contract.get('acceptance',[])), 'preserve':bounded(contract.get('preserve',[])),
            'work_type':contract.get('work_type'),
            'scope':{k:bounded(scope.get(k,[])) for k in ('functional','excluded')},
            'checkpoint_revision':brief.get('record_revision'),
            'recorded_source_hashes':{str(k)[:300]:str(v)[:64] for k,v in list(source.items())[:5]},
            'source_observations':{'status':observed['status'],'files':[{**x,'path':str(x.get('path',''))[:300]} for x in observed.get('files',[])[:5]],'truncated':observed.get('truncated',False) or len(observed.get('files',[]))>5},
            'artifact_check':artifact_check,'artifact_directory':artifact_directory,
            'resume_brief':{**brief,'reported_summary':(brief['reported_summary'] or '')[:1000],
                'reported_completed':bounded(brief['reported_completed']), 'reported_remaining':bounded(brief['reported_remaining']),
                'reported_blockers':bounded(brief['reported_blockers']), 'reported_changed_paths':bounded(brief['reported_changed_paths']),
                'reported_next_action':(brief['reported_next_action'] or '')[:500]},
            'lists_truncated':truncated or len(source)>5,'content_truncated':truncated or len(source)>5,
            'git':git,'history_available':True,'write_authorized':False,
            'next_action':packet['next_action']}


def history(repo, home, topic, limit=5, before=None):
    if not 1 <= limit <= 20: raise StoreError('History limit must be 1..20')
    rec = WorkflowRecords(repo, home, initialize=False); tid = resolve(rec, topic)
    with closing(rec.store.connect(read_only=True)) as cn:
        rows = list(cn.execute('SELECT revision,content_json FROM workflow_documents WHERE repo_id=? AND scope_key=? AND kind=? AND revision<? ORDER BY revision DESC LIMIT ?',
                              (rec.store.repo_id, tid, 'PROGRESS', before if before is not None else 2**63-1, limit+1)))
    return {'task_id': tid, 'items': [{'revision': r['revision'], 'milestone': json.loads(r['content_json']).get('milestone'),
                                     'summary': str(json.loads(r['content_json']).get('summary',''))[:500]} for r in rows[:limit]],
            'more': len(rows)>limit, 'next_before': rows[limit-1]['revision'] if len(rows)>limit else None,
            'read_only': True, 'write_authorized': False}

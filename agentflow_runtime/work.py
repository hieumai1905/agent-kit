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
from .rig import analyze_readiness, normalize_contract
from .verification import assess
from . import sources
from . import implementation


def _artifact_checks(repo, home, contract):
    from .artifacts import Artifacts
    primary = Artifacts(repo, home); inv = primary.inventory()
    checks = {'anchor': primary.check()}
    if contract.get('repositories'):
        for entry in sources.registry(contract, repo):
            if Path(entry['root']) == Path(repo).resolve(): continue
            manager = Artifacts(entry['root'], home)
            own = manager.inventory()
            # Relative product-origin reports belong only to their own repo.
            shared = {**(inv or {}), 'product_reports': {}}
            if own:
                shared['items'] = (inv or {}).get('items', []) + own.get('items', [])
                shared['fingerprints'] = list(set((inv or {}).get('fingerprints', [])) | set(own.get('fingerprints', [])))
                shared['product_reports'] = own.get('product_reports', {})
            checks[entry['key']] = manager.check(inventory=shared) if inv else {'status':'BLOCKED','reasons':['No primary inventory']}
    if len(checks) == 1: return checks['anchor']
    return {'status':'CLEAR' if all(c['status']=='CLEAR' for c in checks.values()) else 'BLOCKED',
            'repositories':checks,'reasons':[key+': '+reason for key,c in checks.items() for reason in c.get('reasons',[])],
            'read_only':True,'write_authorized':False,'enforced_commit_gate':False}


def _repo_git(repo, contract):
    from .practical import git_snapshot
    cache = {}
    def observe(root):
        root = str(Path(root).resolve())
        if root not in cache: cache[root] = git_snapshot(root)
        return cache[root]
    return {'anchor':observe(repo), 'sources':{entry['key']:observe(entry['root']) for entry in sources.registry(contract, repo)}}


def source_snapshot(repo, home, topic, output=None):
    """Capture a test-time footprint without executing tests or changing DB."""
    rec=WorkflowRecords(repo,home,initialize=False);tid=resolve(rec,topic)
    contract=rec.core.contract_revision(tid)
    previous=rec.latest('PROGRESS',task_id=tid)
    execution=implementation.effective(contract,repo,previous['content'] if previous else {})
    manifest=sources.capture(execution,repo)
    if output:
        path=Path(output).expanduser()
        if not path.is_absolute() or path.is_symlink(): raise StoreError('sources --output must be an absolute external file')
        path=path.resolve()
        roots=[Path(repo).resolve()]+[Path(r['root']) for r in sources.registry(execution,repo)]
        if any(path.is_relative_to(root) for root in roots): raise StoreError('Source snapshots must stay outside every product root')
        # The normal destination is already registered by setup. Avoid arbitrary
        # external writes or mutable reuse of a previous test-time snapshot.
        artifact_dir=rec.store.state_dir/'artifacts'
        if not path.is_relative_to(artifact_dir): raise StoreError('Use the returned artifact_directory for --output')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x') as handle: json.dump(manifest,handle,ensure_ascii=False,sort_keys=True)
        return {'source_snapshot_file':str(path),'scope_sha256':manifest['scope_sha256'],
                'repositories':len(manifest['repositories']),'files':sum(len(r['files']) for r in manifest['repositories']),
                'contract_sha256':contract['sha256'],'read_only_product_and_db':True,'write_authorized':False}
    return {'source_manifest':manifest,'contract_sha256':contract['sha256'],'read_only':True,'write_authorized':False}


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
        if p.is_dir():
            raise StoreError('source_paths: directory '+name+' is not a file; list the explicit task files (or declare repositories.write_paths)')
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
    if contract.get('repositories'):
        sources.registry(contract, repo)
    elif sources.external_scope(contract, repo):
        raise StoreError('repositories: multi-repo scope needs explicit Git roots and write_paths; a primary-repo anchor cannot cover sibling source')
    implementation.policy(contract,repo)
    from agentflow_core.db import canonical_json
    if len(canonical_json(contract).encode('utf-8'))>256*1024:raise StoreError('Contract exceeds 256 KiB; reduce to relevant facts before saving')
    ready = analyze_readiness(contract)
    if ready['status'] != 'READY_FOR_HUMAN_REVIEW':
        raise StoreError('Contract not ready: ' + '; '.join(ready['blockers']))
    contract,_=normalize_contract(contract)
    contract={**contract,'analysis_level':ready['effective_level']}
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
    artifact_check=_artifact_checks(repo,home,contract) if manager.inventory() is not None else {'status':'NOT_CONFIGURED','next_action':'Complete setup before effects'}
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
    observed_contract=rec.core.contract_revision(tid)
    observed_progress=rec.latest('PROGRESS',task_id=tid)
    if (observed_contract['sha256']!=created['contract_hash'] or observed_contract['content']!=contract
            or observed_contract['revision']!=created['contract_revision']
            or not observed_progress or observed_progress['revision']!=checkpoint['revision']
            or observed_progress['content']!=body):
        raise ConflictError('Start readback changed; inspect the existing task and reconcile, never recreate/blind retry')
    return {'action': 'PRESENT_CONTRACT', 'task_id': tid, 'contract': contract, 'routing':ready,
            'readback_matches':True,'existing_task_lookup_performed':True,
            'input_derivations':ready.get('input_derivations',[]),
            'binding': {'contract_revision': created['contract_revision'], 'contract_sha256': created['contract_hash']},
            'checkpoint': checkpoint, 'artifact_check':artifact_check,
            'artifact_directory':str(rec.store.state_dir/'artifacts'),
            'decision_input_example':{'contract_sha256':created['contract_hash'],'expected_revision':checkpoint['revision'],
                'decision':{'choice':'APPROVED_OR_REJECTED_AFTER_ACTUAL_USER_DECISION','source':'actual current-chat USER message reference'},
                **({'source_paths':['existing/task-owned/file']} if not contract.get('repositories') else {})},
            'next_action': 'Contract/checkpoint read back; reuse this binding/revision, no immediate lookup/resume needed. Record only the actual current USER decision on this same scope before patch; if still pending, wait.',
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
    bound_contract=rec.core.contract_revision(tid)
    contract = bound_contract['content']
    multi = bool(contract.get('repositories'))
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
    if 'implementation_plan' in data:
        decision=body.get('advisory_decision',{})
        if (milestone=='CONTRACT_DECISION' or decision.get('decision')!='APPROVED'
                or decision.get('kind')!='DIRECT_HUMAN' or decision.get('contract_sha256')!=bound_contract['sha256']
                or decision.get('contract_revision')!=bound_contract['revision']):
            raise StoreError('Implementation refinement needs the existing reported decision on this exact contract; record it first')
        body['implementation_plan']=implementation.prepare(bound_contract,repo,body,data['implementation_plan'])
        previous=rec.latest('PROGRESS',task_id=tid)
        for key in ('phase','completed','remaining','blockers','next_action'):
            if key not in data and previous and key in previous['content']:body[key]=previous['content'][key]
        if 'summary' not in data:body['summary']='Implementation file plan refined: '+body['implementation_plan']['reason']
        if 'next_action' not in data:body['next_action']='Revalidate current USER scope and inspect the combined prepatch check before effects'
    contract=implementation.effective(bound_contract,repo,body)
    if milestone == 'CONTRACT_DECISION':
        # A template may carry old provenance. It must never be silently rebound
        # to a new contract in lieu of an explicitly supplied current decision.
        decision = data.get('advisory_decision')
        if not isinstance(decision,dict) or decision.get('kind') != 'DIRECT_HUMAN' or decision.get('decision') not in ('APPROVED','REJECTED') or not decision.get('source'):
            raise StoreError('Direct decision requires kind DIRECT_HUMAN, decision APPROVED/REJECTED and an actual current-chat source reference')
        decision = {**decision, 'contract_sha256': body['contract_sha256'], 'contract_revision': body['contract_revision']}
        body['advisory_decision'] = decision
        body['source_hashes'] = hashes_for(repo, data.get('source_paths', [])) if not multi else {}
        new_paths=data.get('new_paths',[])
        from .continuity import _paths
        if not _paths(new_paths) or any((Path(repo)/p).exists() or (Path(repo)/p).is_symlink() for p in new_paths):
            raise StoreError('new_paths must be safe relative paths that are still absent')
        body['new_paths']=new_paths
        if not multi and not body['source_hashes'] and not new_paths:
            raise StoreError('Decision checkpoint needs source_paths to observe or explicit absent new_paths')
        if not body['source_hashes']:
            del body['source_hashes']
        from .practical import git_snapshot
        body['prewrite_git'] = git_snapshot(repo)
    if milestone == 'IMPLEMENTATION_VERIFICATION' and not multi:
        body['source_hashes'] = hashes_for(repo, data.get('source_paths', body['changed_paths']))
    if milestone!='CONTRACT_DECISION' and 'source_paths' in data and not multi:
        # The caller must first reconcile its intentional in-scope changes.
        # Refresh observations, not the carried decision or contract binding.
        body['source_hashes']=hashes_for(repo,data['source_paths'])
        from .practical import git_snapshot
        body['prewrite_git']=git_snapshot(repo)
    if multi:
        if data.get('source_paths') or data.get('tested_source_hashes'):
            raise StoreError('Use the complete per-repo source manifest, not flat primary-repo source_paths/hashes')
        body.pop('source_hashes',None)
        body.pop('new_paths',None)
        body['source_manifest']=sources.capture(contract,repo)
        body['prewrite_repositories']=_repo_git(repo,contract)
        body['changed_sources']=sources.changed_files(contract,repo,data)
        body['changed_paths']=[]
    if 'verification_report' in body:
        report=body['verification_report']
        if (not isinstance(report,dict) or report.get('contract_sha256')!=body['contract_sha256']
                or report.get('contract_revision')!=body['contract_revision']
                or (report.get('tested_sources')!=body.get('source_manifest') if multi else
                    not report.get('tested_source_hashes') or report['tested_source_hashes']!=body.get('source_hashes'))):
            raise ConflictError('Verification must retain its own tested-source/current-contract binding; rerun affected checks, do not rebind old results')
    saved = save_checkpoint(rec, tid, body, expected_revision=expected)
    readback = rec.latest('PROGRESS', task_id=tid)
    if readback['revision'] != saved['revision'] or readback['content'] != body:
        raise ConflictError('Checkpoint readback diverged; do not patch, reread and reconcile')
    result={**saved, 'task_id': tid, 'contract_sha256':body['contract_sha256'], 'readback_matches': True,
            'artifact_directory':str(rec.store.state_dir/'artifacts'),
            'next_action': 'Recheck current decision, contract and sources before effects; saved report is not authorization.'}
    if body.get('implementation_plan'):result['implementation_plan']=implementation.summary(body['implementation_plan'])
    if milestone=='CONTRACT_DECISION' or data.get('prepare_next_batch') is True or 'implementation_plan' in data:
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
            **({'tested_sources_file':str(rec.store.state_dir/'artifacts/TEST_TIME_SNAPSHOT.json'),'changed_sources':{}} if multi else
               {'source_paths':list(body.get('source_hashes',{})), 'tested_source_hashes':{'TASK_FILE':'HASH_CAPTURED_AT_TEST_TIME'},'changed_paths':[]}),
            'summary':'ACTUAL_RESULT','completed':[],'remaining':[],'blockers':[],
            'checks':[{'kind':'REPRODUCTION_OR_REGRESSION','command':'ACTUAL_COMMAND','executed':False,
                       'exit_code':None,'output_excerpt':'','status':'NOT_RUN','covers':['A1','P1']}],
            'next_action':'Present actual evidence and remaining work'}
    return result


def finish(repo, home, topic, data):
    if 'implementation_plan' in data:raise StoreError('Refine implementation_plan in checkpoint before patch/tests, not in finish')
    rec = WorkflowRecords(repo, home, initialize=False)
    tid = resolve(rec, topic)
    contract = rec.core.contract_revision(tid)
    if data.get('contract_sha256') != contract['sha256']:
        raise ConflictError('Finish must be bound to the contract read before verification')
    previous=rec.latest('PROGRESS',task_id=tid)
    execution=implementation.effective(contract,repo,previous['content'] if previous else {})
    decision=previous['content'].get('advisory_decision',{}) if previous else {}
    if (decision.get('decision')!='APPROVED' or decision.get('kind')!='DIRECT_HUMAN'
            or decision.get('contract_sha256')!=contract['sha256'] or decision.get('contract_revision')!=contract['revision']):
        raise StoreError('Finish requires the explicitly reported decision checkpoint for this contract; do not infer approval from code/tests')
    result = assess(contract['content'], data)
    multi=bool(execution.get('repositories'))
    paths = data.get('source_paths', data.get('changed_paths', []))
    if multi:
        if data.get('source_paths') or data.get('tested_source_hashes'):
            raise StoreError('Manifest mode uses tested_sources_file/tested_sources; omit flat source_paths/tested_source_hashes')
        data={**data,'changed_sources':sources.changed_files(execution,repo,data),'changed_paths':[]}
        actual=sources.capture(execution,repo)
        if data.get('tested_sources')!=actual:
            raise ConflictError('tested_sources must cover every declared repo/file at test time and still match; capture with work sources before checks')
        result['tested_sources']=actual
        result['source_coverage']='DECLARED_SCOPE_COMPLETE'
    else:
        actual = hashes_for(repo, paths)
        coverage=sources.legacy_coverage(contract['content'],repo,actual,data.get('changed_paths'))
        if coverage['status']=='INCOMPLETE':raise StoreError('Source coverage incomplete: include every changed file or declare repositories/write_paths for sibling repos')
        if not actual or data.get('tested_source_hashes') != actual:
            raise ConflictError('Provide tested_source_hashes captured at check time; current files must match them')
        result['tested_source_hashes']=dict(actual)
        result['source_coverage']=coverage['status']
    result.update(contract_sha256=contract['sha256'],contract_revision=contract['revision'])
    artifact_check=_artifact_checks(repo,home,execution)
    if artifact_check['status']!='CLEAR':raise StoreError('Handoff blocked by artifact check: '+'; '.join(artifact_check['reasons']))
    body = {**data, 'milestone': 'IMPLEMENTATION_VERIFICATION', 'phase': 'IMPLEMENTED',
            'summary': data.get('summary', result['reported_verdict']),
            'completed': data.get('completed', []), 'remaining': data.get('remaining', []),
            'blockers': data.get('blockers', []), 'changed_paths': data.get('changed_paths', []),
            'next_action': data.get('next_action', 'Review reported verification and decide acceptance')}
    body['verification_report']=result
    if not multi:body['source_paths']=paths
    saved = checkpoint(repo, home, tid, body)
    return {**saved, 'verification': result, 'artifact_check':artifact_check, 'auto_complete': False,
            'handoff_saved':True,'handoff_revision':saved['revision'],
            'next_action': 'Handoff saved. Present acceptance evidence and remaining work; no duplicate handoff/checkpoint is needed. Publication is separate.'}


def recheck(repo,home,topic,expected_revision=None):
    rec=WorkflowRecords(repo,home,initialize=False);tid=resolve(rec,topic)
    contract=rec.core.contract_revision(tid);progress=rec.latest('PROGRESS',task_id=tid)
    body=progress['content'] if progress else {};decision=body.get('advisory_decision',{})
    problems=[]
    try:execution=implementation.effective(contract,repo,body)
    except (StoreError,ValueError,OSError,RuntimeError) as exc:
        return {'status':'BLOCKED','reasons':['Invalid implementation footprint: '+str(exc)],
                'trusted':False,'write_authorized':False,'next_action':'Reread/reconcile, never discard a plan to bypass it'}
    if expected_revision is not None and (not progress or progress['revision']!=expected_revision):problems.append('Checkpoint changed during recheck; reread and reconcile before patch')
    if decision.get('decision')!='APPROVED' or decision.get('kind')!='DIRECT_HUMAN':problems.append('No reported direct approval')
    if (decision.get('contract_sha256')!=contract['sha256'] or body.get('contract_sha256')!=contract['sha256']
            or decision.get('contract_revision')!=contract['revision'] or body.get('contract_revision')!=contract['revision']):
        problems.append('Decision/checkpoint belongs to another contract revision')
    from .continuity import _paths
    absent=body.get('new_paths',[])
    if not _paths(absent):raise StoreError('Invalid new_paths in saved checkpoint; reconcile the report')
    manifest_check=sources.observe(execution,repo,body.get('source_manifest')) if execution.get('repositories') else None
    source_ok=(manifest_check['status']=='CURRENT' if manifest_check else
        (body.get('source_hashes') and observe_source_hashes(repo,body['source_hashes'])['status']=='CURRENT') or (not body.get('source_hashes') and absent))
    if not manifest_check and sources.legacy_coverage(contract['content'],repo,body.get('source_hashes'))['status']=='INCOMPLETE':source_ok=False
    if not source_ok:problems.append('Source baseline missing or stale; reconcile before patch')
    if any((Path(repo)/p).exists() or (Path(repo)/p).is_symlink() for p in body.get('new_paths',[])):problems.append('A planned new path now exists; reconcile concurrent work')
    from .practical import git_snapshot
    current_git=git_snapshot(repo)
    if not current_git.get('git_available') or current_git.get('changes_truncated'):problems.append('Git observation unavailable/truncated; inspect full scope before patch')
    if body.get('prewrite_git') and body['prewrite_git']!=current_git:problems.append('Git baseline changed after decision; inspect/reconcile before patch')
    if manifest_check:
        multi_git=_repo_git(repo,execution)
        views=[multi_git['anchor'],*multi_git['sources'].values()]
        if any(not v.get('git_available') or v.get('changes_truncated') for v in views):problems.append('Per-repo Git observation unavailable/truncated')
        if body.get('prewrite_repositories')!=multi_git:problems.append('A repository Git baseline changed; reconcile before patch')
    from .installer import GuidanceInstaller
    installed=GuidanceInstaller(repo,home,mode='advisory').installed_status()
    if set(installed['installed_files'].values())!={'ADVISORY'}:problems.append('Current guidance is not consistently ADVISORY')
    artifacts=_artifact_checks(repo,home,execution)
    if artifacts['status']!='CLEAR':problems.append('Artifact/index check blocked: '+'; '.join(artifacts['reasons']))
    return {'status':'BLOCKED' if problems else 'REPORTED_PRECONDITIONS_CURRENT','reasons':problems,
            'source_coverage':manifest_check,
            'implementation_plan':implementation.summary(body.get('implementation_plan')),
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
            'source_hashes_summarized':len(source)>5,'recorded_source_file_count':len(source),
            'source_coverage':observed.get('coverage'),
            'repository_sources':observed.get('repositories',[]),
            'implementation_plan':implementation.summary(packet.get('relevant_artifacts',{}).get('PROGRESS',{}).get('implementation_plan')),
            'lists_truncated':truncated,'content_truncated':truncated,
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

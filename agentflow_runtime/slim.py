"""Three local milestones composing the existing advisory records, not authority.

Receipts detect stale/replayed reports; they are not capabilities or signatures.
Commands execute using the caller's existing permissions, without a shell.
"""
from pathlib import Path
import hashlib
import json
import os
import shlex
import signal
import subprocess
import re
import uuid

from agentflow_core import ConflictError, StoreError
from . import sources, work, brief, coordination
from .evidence_target import target, expected
from .records import WorkflowRecords

KEY = 'slim'


def _hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _git(repo, *args):
    proc = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if proc.returncode:
        raise StoreError('Git observation failed: ' + ' '.join(args))
    return proc.stdout


def _tree(repo):
    """Git-visible working files, including preexisting dirty/untracked files."""
    root = Path(repo).resolve(); files = {}
    for raw in sorted(set(_git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')) - {b''}):
        name = os.fsdecode(raw); path = root / name
        if path.is_symlink():
            files[name] = {'link': os.readlink(path)}
        elif path.is_file():
            files[name] = {'sha256': _hash(path), 'executable': bool(path.stat().st_mode & 0o111)}
        elif path.exists():
            raise StoreError('Normal path does not support submodules/special paths: ' + name)
        else:
            files[name] = None
    return {'files': files,
            'index': hashlib.sha256(_git(root, 'ls-files', '--stage', '-z')).hexdigest(),
            'head': _git(root, 'rev-parse', '--verify', 'HEAD').decode().strip()
                    if subprocess.run(['git', '-C', str(root), 'rev-parse', '--verify', 'HEAD'], capture_output=True).returncode == 0
                    else 'UNBORN:' + _git(root, 'symbolic-ref', 'HEAD').decode().strip()}


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def _external(records, raw):
    path = Path(raw).expanduser()
    root = records.store.state_dir / 'artifacts'
    if not path.is_absolute() and re.fullmatch(r'slim-[0-9a-f]{32}\.json',str(path)):
        path=root/path
    if not path.is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise StoreError('Receipt/evidence must be a regular file in this repository artifact_directory')
    if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise StoreError('Receipt/evidence missing or too large')
    return path


def _next(action, receipt, summary=False):
    """Arguments to append to the already-known helper prefix, no shell code."""
    result=['work',action,Path(receipt).name]
    if summary:result+=['--summary','ACTUAL_REPAIR_REASON' if action=='retry' else 'ACTUAL_OUTCOME']
    return result


def _save(records, task, content, expected=0):
    saved = records.put('CHANGE_REPORT', content, task_id=task, key=KEY, expected_revision=expected)
    actual = records.latest('CHANGE_REPORT', task_id=task, key=KEY)
    if actual['revision'] != saved['revision'] or actual['content'] != content:
        raise ConflictError('Milestone readback diverged; stop and reconcile')
    receipt = records.store.state_dir / 'artifacts' / ('slim-' + uuid.uuid4().hex + '.json')
    _write(receipt, {'schema': 'agentflow.slim.receipt.v1', 'task_id': task,
                     'revision': saved['revision'], 'sha256': saved['sha256']})
    coordination.remember(records, task, content, str(receipt))
    return str(receipt)


def _load(repo, home, receipt, *, read_only=False):
    records = WorkflowRecords(repo, home, initialize=False)
    payload = json.loads(_external(records, receipt).read_text())
    if not isinstance(payload, dict) or payload.get('schema') != 'agentflow.slim.receipt.v1' or not isinstance(payload.get('task_id'), str):
        raise StoreError('Not a slim receipt')
    task = payload.get('task_id')
    row = records.latest('CHANGE_REPORT', task_id=task, key=KEY)
    if not row or row['revision'] != payload.get('revision') or row['sha256'] != payload.get('sha256'):
        raise ConflictError('Receipt is stale or changed; resume and reconcile, never silently retry')
    content = row['content']; contract = records.core.contract_revision(task)
    actor = coordination.identity()
    if actor and content.get('session_ref') and actor != content['session_ref']:
        raise ConflictError('Receipt belongs to another chat; resume that chat at a safe point')
    if not read_only:coordination.check(records, content)
    brief.check(records, content)
    progress = records.latest('PROGRESS', task_id=task)
    if (contract['sha256'] != content['contract_sha256'] or contract['revision'] != content['contract_revision']
            or not progress or progress['revision'] != content['progress_revision']):
        raise ConflictError('Contract/checkpoint changed since receipt; use the advanced resume path to reconcile')
    from .installer import GuidanceInstaller
    if set(GuidanceInstaller(repo, home, mode='advisory').installed_status()['installed_files'].values()) != {'ADVISORY'}:
        raise StoreError('Current guidance is not consistently ADVISORY; stop and reconcile')
    return records, task, row, content, contract


def _check_scope(repo, records, content, contract):
    baseline_path = _external(records, content['baseline_file'])
    if _hash(baseline_path) != content['baseline_sha256']:
        raise ConflictError('Working baseline evidence changed')
    before = json.loads(baseline_path.read_text()); now = _tree(repo)
    if before['index'] != now['index'] or before['head'] != now['head']:
        raise ConflictError('Git index/HEAD changed; preserve preexisting staging and reconcile')
    changed = sorted(k for k in before['files'].keys() | now['files'].keys()
                     if before['files'].get(k) != now['files'].get(k))
    allowed = set(sources.registry(contract['content'], repo)[0]['write_paths'])
    outside = set(changed) - allowed
    if outside:
        raise StoreError('Out-of-scope working changes since begin: ' + ', '.join(sorted(outside)))
    return changed


def _plans(value, contract, repo):
    if not isinstance(value, list) or not 1 <= len(value) <= 12:
        raise StoreError('Declare 1..12 existing project checks before begin')
    refs = {f'A{i+1}' for i in range(len(contract.get('acceptance', [])))} | {f'P{i+1}' for i in range(len(contract.get('preserve', [])))}
    result = []
    for item in value:
        if not isinstance(item, dict): raise StoreError('Each check needs argv, kind and covers')
        argv = item.get('argv'); covers = item.get('covers', [])
        if not isinstance(argv, list) or not argv or len(argv) > 80 or any(not isinstance(x, str) or not x or '\x00' in x for x in argv):
            raise StoreError('Check argv must be explicit nonempty string arguments, without a shell')
        if not isinstance(covers, list) or any(x not in refs for x in covers):
            raise StoreError('Check covers must reference this contract A1.. and P1..')
        if item.get('execution_context') == 'ACTUAL_WORKFLOW':
            raise StoreError('Slim command tests do not attest actual UI workflow; report that separately through the advanced path')
        context=item.get('execution_context','COMMAND_EXECUTION')
        if context not in ('COMMAND_EXECUTION','ACTUAL_CLI'):raise StoreError('Use COMMAND_EXECUTION or actual CLI evidence; UI remains separate')
        if context=='ACTUAL_CLI':
            if target(contract)!='CLI':raise StoreError('Actual CLI evidence needs verification_target CLI before approval')
            entry=contract['cli_entrypoint'];scope=sources.registry(contract,repo)[0]
            if entry not in scope['write_paths']+scope.get('read_paths',[]):raise StoreError('CLI entrypoint must be declared in the source footprint')
            expanded=[os.path.expandvars(x) for x in argv]
            root=Path(repo).resolve();idx=0
            if re.fullmatch(r'(?:python(?:\d+(?:\.\d+)*)?|node)(?:\.exe)?',Path(expanded[0]).name):
                idx=1
                while idx<len(expanded) and expanded[idx] in ('-B','-u','--'):idx+=1
            if idx>=len(expanded) or (root/expanded[idx]).resolve()!=(root/entry).resolve():
                raise StoreError('Actual CLI check must invoke the declared entrypoint directly, not unittest/pytest or inline code')
        code=expected(item,contract)
        result.append({'argv': argv, 'kind': item.get('kind', 'REGRESSION'), 'covers': covers,
                       'execution_context': context,'expected_exit_code':code})
    return result


def begin(repo, home, title, data):
    records = WorkflowRecords(repo, home, initialize=False)
    owner = coordination.session(data.get('session_ref'))
    try:token = coordination.claim(records, owner, title)
    except ConflictError as exc:
        return {'status':'BLOCKED','reason_code':'WRITER_BUSY','reasons':[str(exc)],'write_authorized':False,
                'next_action':'Owning chat must save handoff/pause at a safe point; do not take over or contact other chats without USER authorization'}
    try:
        result = _begin(repo, home, title, data, owner, token)
    except BaseException:
        coordination.release(records, token)
        raise
    if 'receipt' not in result or result.get('status') == 'BLOCKED':
        coordination.release(records, token)
    return result


def _begin(repo, home, title, data, owner, token):
    approval = data.get('approval_source')
    if not isinstance(approval, str) or len(approval.strip()) < 6 or approval.strip().casefold() in ('approved', 'todo', 'unknown'):
        raise StoreError('Begin needs the actual current USER approval source reference, not an inferred approval')
    contract = data.get('contract')
    if not isinstance(contract, dict): raise StoreError('Begin requires the approved contract')
    entries = sources.registry(contract, repo)
    if len(entries) != 1 or Path(entries[0]['root']) != Path(repo).resolve():
        raise StoreError('Multiple repositories need the existing advanced work path')
    checks = _plans(data.get('checks'), contract, repo)
    records = WorkflowRecords(repo, home, initialize=False)
    goal = brief.bind(records, data)
    started = work.start(repo, home, title, {'contract': contract})
    if started.get('action') != 'PRESENT_CONTRACT':
        return {**started, 'status': 'BLOCKED', 'next_action': 'Existing task found. Resume and reconcile; begin never silently reapproves it.'}
    task = started['task_id']
    decision = work.checkpoint(repo, home, task, {
        'contract_sha256': started['binding']['contract_sha256'],
        'expected_revision': started['checkpoint']['revision'],
        'decision': {'choice': 'APPROVED', 'source': approval},
        'phase': 'IMPLEMENTING', 'summary': 'Reported current USER approval of the presented contract'})
    if decision.get('status') == 'BLOCKED': return decision
    records = WorkflowRecords(repo, home, initialize=False)
    baseline = records.store.state_dir / 'artifacts' / ('baseline-' + uuid.uuid4().hex + '.json')
    _write(baseline, {'schema': 'agentflow.slim.baseline.v1', **_tree(repo)})
    receipt = _save(records, task, {'stage': 'BEGUN', 'contract_sha256': started['binding']['contract_sha256'],
        'contract_revision': started['binding']['contract_revision'], 'progress_revision': decision['revision'],
        'baseline_file': str(baseline), 'baseline_sha256': _hash(baseline), 'checks': checks, **goal,
        'session_ref':owner,'lease_token':token,'title':title,'prepared_sources':sources.capture(contract, repo)})
    # Recheck after receipt persistence too: no successful response on a stale baseline.
    checked = work.recheck(repo, home, task, expected_revision=decision['revision'])
    return {'status': checked['status'], 'receipt': receipt, 'readback_matches': True,
            'decision_readback': decision['decision_readback'], 'prepatch_check': checked,
            'project_context': brief.view(records, goal),'session_ref':owner,
            'artifact_directory': str(records.store.state_dir / 'artifacts'),
            'next_command':_next('verify',receipt),
            'trusted': False, 'write_authorized': False,
            'next_action': 'Inspect this result and actual USER scope, then patch only declared files. Use the receipt with work verify.'}


def verify(repo, home, receipt, timeout=300):
    if type(timeout) is not int or not 1 <= timeout <= 600: raise StoreError('Check timeout must be 1..600 seconds')
    records, task, row, content, contract = _load(repo, home, receipt)
    if content['stage'] == 'VERIFIED':
        _check_scope(repo, records, content, contract)
        _logs_current(records, content)
        if sources.capture(contract['content'], repo) != content['tested_sources']:
            raise ConflictError('Sources changed since checks; use work retry RECEIPT --summary REASON before the next repair batch')
        return _verification_result(receipt, content['results'], reused=True)
    if content['stage'] != 'BEGUN': raise ConflictError('Verify requires a begin/retry receipt; completed handoffs cannot be replayed')
    changed = _check_scope(repo, records, content, contract)
    artifacts = work._artifact_checks(repo, home, contract['content'])
    if artifacts['status'] != 'CLEAR': return {'status': 'BLOCKED', 'artifact_check': artifacts}
    before = sources.capture(contract['content'], repo); results = []
    folder = records.store.state_dir / 'artifacts' / ('checks-' + uuid.uuid4().hex); folder.mkdir()
    for n, plan in enumerate(content['checks']):
        log = folder / (str(n + 1) + '.log'); timed_out = False
        argv = [os.path.expandvars(x) for x in plan['argv']]
        with log.open('xb') as stream:
            stream.write(b'AGENTFLOW_V3_GUIDANCE_ONLY: external kit check log\n')
            stream.flush()
            try:
                process = subprocess.Popen(argv, cwd=repo, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                try: code = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    os.killpg(process.pid, signal.SIGTERM)
                    try: process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL); process.wait()
                    code = 124
            except OSError as exc:
                stream.write((type(exc).__name__ + ': ' + str(exc)).encode()); code = 127
        with log.open('rb') as stream:
            stream.seek(max(0, log.stat().st_size - 3000)); excerpt = stream.read().decode('utf-8', errors='replace').strip()
        results.append({**{k: plan[k] for k in ('kind', 'covers', 'execution_context')},
                        'expected_exit_code':plan.get('expected_exit_code',0),
                        'command': shlex.join(argv), 'executed': code != 127, 'exit_code': code,
                        'output_excerpt': excerpt or 'Command completed with no output; see exit code.',
                        'status': 'PASS' if not timed_out and code == plan.get('expected_exit_code',0) else 'FAIL', 'timed_out': timed_out,
                        'log_file': str(log), 'log_sha256': _hash(log)})
    if sources.capture(contract['content'], repo) != before:
        raise ConflictError('Sources changed during checks; evidence is stale. Reconcile and rerun, never bind old checks to new hashes')
    _load(repo, home, receipt)  # No checkpoint/contract change may be silently rebound during a test run.
    _check_scope(repo, records, content, contract)
    proof = {**content, 'stage': 'VERIFIED', 'tested_sources': before, 'results': results, 'changed_paths': changed}
    next_receipt = _save(records, task, proof, row['revision'])
    return _verification_result(next_receipt, results)


def _verification_result(receipt, results, reused=False):
    failed = any(x['status'] != 'PASS' for x in results)
    return {'status': 'BLOCKED' if failed else 'CHECKS_EXECUTED', 'receipt': receipt,
            'reason_code': 'TESTS_FAILED' if failed else 'CHECKS_PASSED', 'checks_reused': reused,
            'checks': [{'command': x['command'], 'status': x['status'], 'exit_code': x['exit_code'], 'expected_exit_code':x.get('expected_exit_code',0), 'timed_out': x['timed_out']} for x in results],
            'reasons': ['One or more declared checks failed/timed out; do not claim success'] if failed else [],
            'trusted': False, 'write_authorized': False,
            'next_action': ('Inspect failed check logs, then work retry RECEIPT --summary REASON before an in-scope repair; or work handoff RECEIPT --summary OUTCOME to save failure.' if failed else
                            'work handoff RECEIPT --summary OUTCOME saves this evidence; work retry RECEIPT --summary REASON prepares an intentional in-scope repair.'),
            'log_files': [x['log_file'] for x in results],
            'next_command':_next('retry' if failed else 'handoff',receipt,True)}


def _logs_current(records, content):
    for check in content.get('results', []):
        if _hash(_external(records, check['log_file'])) != check['log_sha256']:
            raise ConflictError('Check output changed; do not reuse altered evidence')


def retry(repo, home, receipt, summary):
    """Prepare another batch under the same approval; never change scope or tests."""
    if not isinstance(summary, str) or not summary.strip():
        raise StoreError('Retry needs the observed reason for the same-scope repair')
    records, task, row, content, contract = _load(repo, home, receipt, read_only=True)
    if content['stage'] not in ('BEGUN', 'VERIFIED','PAUSED'):
        raise ConflictError('A saved handoff needs a new approved milestone, not retry')
    if content['stage'] != 'PAUSED':coordination.check(records, content)
    changed = _check_scope(repo, records, content, contract)
    _logs_current(records, content)
    if content['stage']=='PAUSED' and sources.capture(contract['content'],repo)!=content['pause_sources']:
        raise ConflictError('Declared sources changed while paused; inspect concurrent work and reconcile, never absorb it as your repair')
    new_token = coordination.claim(records, content['session_ref'], content['title']) if content['stage']=='PAUSED' else None
    try:
        return _retry(records, task, row, content, contract, repo, home, summary, changed, new_token)
    except BaseException:
        if new_token:coordination.release(records,new_token)
        raise


def _retry(records, task, row, content, contract, repo, home, summary, changed, new_token):
    checked = work.checkpoint(repo, home, task, {
        'contract_sha256': content['contract_sha256'], 'expected_revision': content['progress_revision'],
        'milestone': 'HANDOFF', 'phase': 'IMPLEMENTING', 'prepare_next_batch': True,
        'summary': summary, 'changed_sources': {sources.registry(contract['content'], repo)[0]['key']: changed},
        'completed': ['Reconciled changes against the unchanged approved scope'],
        'remaining': ['Repair in scope and rerun checks; previous results stay historical'],
        'blockers': [], 'next_action': 'Repair only after the persisted prepatch check is current'})
    next_content = {k: v for k, v in content.items() if k not in ('results', 'tested_sources', 'changed_paths')}
    next_content.update(stage='BEGUN', progress_revision=checked['revision'])
    next_content['prepared_sources']=sources.capture(contract['content'],repo)
    if new_token:next_content['lease_token']=new_token
    next_receipt = _save(records, task, next_content, row['revision'])
    return {**checked, 'receipt': next_receipt, 'reason_code': 'REPAIR_PREPARED' if checked['status'] != 'BLOCKED' else 'PRECONDITIONS_BLOCKED',
            'next_command':_next('verify',next_receipt) if checked['status']!='BLOCKED' else None,
            'next_action': 'Inspect prepatch_check and actual USER scope; repair declared files, then work verify RECEIPT. Do not reuse old PASS for changed sources.'}


def handoff(repo, home, receipt, summary, remaining=None):
    if not isinstance(summary, str) or not summary.strip(): raise StoreError('Provide the actual outcome summary')
    records, task, row, content, contract = _load(repo, home, receipt)
    if content['stage'] != 'VERIFIED': raise ConflictError('Handoff requires the verification receipt')
    changed = _check_scope(repo, records, content, contract)
    if sources.capture(contract['content'], repo) != content['tested_sources']:
        raise ConflictError('Sources changed since checks; rerun affected checks before handoff')
    _logs_current(records, content)
    entry = sources.registry(contract['content'], repo)[0]
    result = work.finish(repo, home, task, {'contract_sha256': content['contract_sha256'],
        'expected_revision': content['progress_revision'], 'tested_sources': content['tested_sources'],
        'changed_sources': {entry['key']: changed}, 'summary': summary, 'completed': [summary],
        'remaining': remaining or [], 'blockers': [], 'checks': content['results'],
        'next_action': 'Review actual evidence, acceptance, preservation and untested user workflow; publication is separate'})
    done = {**content, 'stage': 'HANDED_OFF', 'progress_revision': result['revision']}
    _save(records, task, done, row['revision'])
    if content.get('lease_token'):coordination.release(records,content['lease_token'])
    return {**result, 'status': 'HANDOFF_SAVED', 'project_context':brief.view(records, content),
            'trusted': False, 'write_authorized': False}


def pause(repo, home, receipt, summary):
    if not isinstance(summary,str) or not summary.strip():raise StoreError('Pause needs an actual progress/reason summary')
    if receipt is None:
        return coordination.pause_preparation(WorkflowRecords(repo,home,initialize=False),summary)
    records, task, row, content, contract = _load(repo,home,receipt)
    if content['stage'] not in ('BEGUN','VERIFIED'):raise ConflictError('Only active work can pause')
    conflicts=[]
    try:changed=_check_scope(repo,records,content,contract)
    except StoreError as exc:
        changed=[];conflicts=[str(exc)]
    saved=work.checkpoint(repo,home,task,{'contract_sha256':content['contract_sha256'],
        'expected_revision':content['progress_revision'],'milestone':'HANDOFF','phase':'IMPLEMENTING',
        'summary':summary,'remaining':['Paused; revalidate source/scope and retry before effects'],'blockers':conflicts,
        'changed_sources':{sources.registry(contract['content'],repo)[0]['key']:changed},
        'next_action':'Resume this session with work context; no old PASS applies to changed sources'})
    next_content={**content,'stage':'PAUSED','progress_revision':saved['revision'],
                  'pause_sources':sources.capture(contract['content'],repo),'pause_conflicts':conflicts}
    next_receipt=_save(records,task,next_content,row['revision'])
    coordination.release(records,content['lease_token'])
    return {'status':'PAUSED','receipt':next_receipt,'handoff_saved':True,'reasons':conflicts,'write_authorized':False,
            'next_action':'Use work context in this chat, then work retry RECEIPT --summary REASON after scope/source reconciliation'}


def context(repo, home, owner=None, receipt=None):
    records=WorkflowRecords(repo,home,initialize=False)
    pointer=coordination.pointer(records,owner)
    if not receipt and not pointer:
        return {'status':'NO_CHAT_POINTER','read_only':True,'writer':coordination.display(records),
                'next_action':'Use the receipt/session_ref returned by begin; never guess another chat task','write_authorized':False}
    receipt=receipt or pointer['receipt']
    records,task,row,content,contract=_load(repo,home,receipt,read_only=True)
    before=content.get('tested_sources') or content.get('prepared_sources')
    now=sources.capture(contract['content'],repo)
    next_step={'BEGUN':'Implement only approved scope, then work verify RECEIPT',
               'VERIFIED':'Inspect checks; handoff or retry before repair','PAUSED':'Reconcile current scope/sources, then work retry RECEIPT --summary REASON',
               'HANDED_OFF':'Review pending acceptance; begin a distinct milestone only under its actual USER approval'}[content['stage']]
    return {'status':'CONTEXT_READ','session_ref':content.get('session_ref'),'title':content.get('title'),
        'stage':content['stage'],'receipt':receipt,'source_state':'CURRENT' if now==before else 'CHANGED_SINCE_SNAPSHOT',
        'project_context':brief.view(records,content),'writer':coordination.display(records),
        'checks':[{'command':x['command'],'status':x['status'],'exit_code':x['exit_code']} for x in content.get('results',[])],
        'read_only':True,'write_authorized':False,'next_action':next_step,
        'next_command':(_next('verify',receipt) if content['stage']=='BEGUN' else
                        _next('retry' if any(x['status']!='PASS' for x in content.get('results',[])) else 'handoff',receipt,True) if content['stage']=='VERIFIED' else
                        _next('retry',receipt,True) if content['stage']=='PAUSED' else None)}

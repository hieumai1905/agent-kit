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
import uuid

from agentflow_core import ConflictError, StoreError
from . import sources, work
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
    if not path.is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise StoreError('Receipt/evidence must be a regular file in this repository artifact_directory')
    if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise StoreError('Receipt/evidence missing or too large')
    return path


def _save(records, task, content, expected=0):
    saved = records.put('CHANGE_REPORT', content, task_id=task, key=KEY, expected_revision=expected)
    actual = records.latest('CHANGE_REPORT', task_id=task, key=KEY)
    if actual['revision'] != saved['revision'] or actual['content'] != content:
        raise ConflictError('Milestone readback diverged; stop and reconcile')
    receipt = records.store.state_dir / 'artifacts' / ('slim-' + uuid.uuid4().hex + '.json')
    _write(receipt, {'schema': 'agentflow.slim.receipt.v1', 'task_id': task,
                     'revision': saved['revision'], 'sha256': saved['sha256']})
    return str(receipt)


def _load(repo, home, receipt):
    records = WorkflowRecords(repo, home, initialize=False)
    payload = json.loads(_external(records, receipt).read_text())
    if not isinstance(payload, dict) or payload.get('schema') != 'agentflow.slim.receipt.v1' or not isinstance(payload.get('task_id'), str):
        raise StoreError('Not a slim receipt')
    task = payload.get('task_id')
    row = records.latest('CHANGE_REPORT', task_id=task, key=KEY)
    if not row or row['revision'] != payload.get('revision') or row['sha256'] != payload.get('sha256'):
        raise ConflictError('Receipt is stale or changed; resume and reconcile, never silently retry')
    content = row['content']; contract = records.core.contract_revision(task)
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


def _plans(value, contract):
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
        result.append({'argv': argv, 'kind': item.get('kind', 'REGRESSION'), 'covers': covers,
                       'execution_context': 'COMMAND_EXECUTION'})
    return result


def begin(repo, home, title, data):
    approval = data.get('approval_source')
    if not isinstance(approval, str) or len(approval.strip()) < 6 or approval.strip().casefold() in ('approved', 'todo', 'unknown'):
        raise StoreError('Begin needs the actual current USER approval source reference, not an inferred approval')
    contract = data.get('contract')
    if not isinstance(contract, dict): raise StoreError('Begin requires the approved contract')
    entries = sources.registry(contract, repo)
    if len(entries) != 1 or Path(entries[0]['root']) != Path(repo).resolve():
        raise StoreError('Multiple repositories need the existing advanced work path')
    checks = _plans(data.get('checks'), contract)
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
        'baseline_file': str(baseline), 'baseline_sha256': _hash(baseline), 'checks': checks})
    # Recheck after receipt persistence too: no successful response on a stale baseline.
    checked = work.recheck(repo, home, task, expected_revision=decision['revision'])
    return {'status': checked['status'], 'receipt': receipt, 'readback_matches': True,
            'decision_readback': decision['decision_readback'], 'prepatch_check': checked,
            'artifact_directory': str(records.store.state_dir / 'artifacts'),
            'trusted': False, 'write_authorized': False,
            'next_action': 'Inspect this result and actual USER scope, then patch only declared files. Use the receipt with work verify.'}


def verify(repo, home, receipt, timeout=300):
    if type(timeout) is not int or not 1 <= timeout <= 600: raise StoreError('Check timeout must be 1..600 seconds')
    records, task, row, content, contract = _load(repo, home, receipt)
    if content['stage'] != 'BEGUN': raise ConflictError('Verify requires the begin receipt; do not replay completed milestones')
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
                        'command': shlex.join(argv), 'executed': code != 127, 'exit_code': code,
                        'output_excerpt': excerpt or 'Command completed with no output; see exit code.',
                        'status': 'PASS' if code == 0 else 'FAIL', 'timed_out': timed_out,
                        'log_file': str(log), 'log_sha256': _hash(log)})
    if sources.capture(contract['content'], repo) != before:
        raise ConflictError('Sources changed during checks; evidence is stale. Reconcile and rerun, never bind old checks to new hashes')
    _load(repo, home, receipt)  # No checkpoint/contract change may be silently rebound during a test run.
    _check_scope(repo, records, content, contract)
    proof = {**content, 'stage': 'VERIFIED', 'tested_sources': before, 'results': results, 'changed_paths': changed}
    next_receipt = _save(records, task, proof, row['revision'])
    failed = any(x['status'] != 'PASS' for x in results)
    return {'status': 'BLOCKED' if failed else 'CHECKS_EXECUTED', 'receipt': next_receipt,
            'checks': [{'command': x['command'], 'status': x['status'], 'exit_code': x['exit_code'], 'timed_out': x['timed_out']} for x in results],
            'reasons': ['One or more declared checks failed/timed out; do not claim success'] if failed else [],
            'trusted': False, 'write_authorized': False,
            'next_action': 'Use this latest receipt with work handoff to save the actual outcome; after changes reconcile and rerun affected checks through the advanced path.'}


def handoff(repo, home, receipt, summary, remaining=None):
    if not isinstance(summary, str) or not summary.strip(): raise StoreError('Provide the actual outcome summary')
    records, task, row, content, contract = _load(repo, home, receipt)
    if content['stage'] != 'VERIFIED': raise ConflictError('Handoff requires the verification receipt')
    changed = _check_scope(repo, records, content, contract)
    if sources.capture(contract['content'], repo) != content['tested_sources']:
        raise ConflictError('Sources changed since checks; rerun affected checks before handoff')
    for check in content['results']:
        if _hash(_external(records, check['log_file'])) != check['log_sha256']:
            raise ConflictError('Check output changed; do not reuse altered evidence')
    entry = sources.registry(contract['content'], repo)[0]
    result = work.finish(repo, home, task, {'contract_sha256': content['contract_sha256'],
        'expected_revision': content['progress_revision'], 'tested_sources': content['tested_sources'],
        'changed_sources': {entry['key']: changed}, 'summary': summary, 'completed': [summary],
        'remaining': remaining or [], 'blockers': [], 'checks': content['results'],
        'next_action': 'Review actual evidence, acceptance, preservation and untested user workflow; publication is separate'})
    done = {**content, 'stage': 'HANDED_OFF', 'progress_revision': result['revision']}
    _save(records, task, done, row['revision'])
    return {**result, 'status': 'HANDOFF_SAVED', 'trusted': False, 'write_authorized': False}

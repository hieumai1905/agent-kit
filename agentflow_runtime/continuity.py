"""A3 milestone checkpoints: external unverified reports, never permissions."""
from __future__ import annotations

from copy import deepcopy
from contextlib import closing
import json
from pathlib import PurePosixPath
from agentflow_core import ConflictError, StoreError
from .status import PHASES, observe_source_hashes, _binding, _aggregate

SCHEMA = 'agentflow.checkpoint.v1'
MILESTONES = ('CONTRACT_DECISION', 'SCOPE_CHANGE', 'IMPLEMENTATION_VERIFICATION', 'HANDOFF')
CONTINUITY_GUIDANCE = '''### Continuity — milestone checkpoints (UNVERIFIED, not authority)
For a NEW coding task, including a read-only investigation that ends with a Task Contract awaiting approval, use the helper prefix below with `tasks` to find existing work. If none matches, use `interact 'natural request'` to create an UNTRUSTED draft; no human approval is needed merely to save that external draft. Do not use a grep of SQLite/backups as the only task lookup. STRICT permits these external drafts/checkpoints, while still forbidding product-code edits and side-effecting tests. On RESUME use `resume 'natural topic'` (or `interact 'tiếp tục topic'`); read handoff/resume_brief, current Git and status_view. Never ask the user for an ID/snapshot path when the helper can find the task. If vague or multiple tasks match, offer short titles; do not choose merely the newest or create another task.
Record a checkpoint at material milestones: a contract decision, a scope change, completed implementation/verification, or before stopping/waiting/handoff. Before a final answer that presents a coding Task Contract and waits for approval, save HANDOFF/WAITING_DECISION; that is task work, not standalone Q&A. Do not checkpoint every message or standalone Q&A. Do not wait for the user to remind you. Use `checkpoint-template TASK_ID --milestone HANDOFF` and `checkpoint-milestone TASK_ID /OUTSIDE/progress.json --expected-revision N` with the same helper prefix. The agent handles IDs/JSON; keep JSON and state outside the product repo. The template supplies the observed contract binding and PROGRESS revision: inspect them, populate actual facts, and recheck before saving. On revision conflict, reread and reconcile; never silently retry over another writer.
Include phase, a concise summary, completed/remaining work, changed paths, decisions/source refs as reports, blockers, next action, and source hashes for an implementation/verification checkpoint. Distinguish proposed/in-memory work from applied changes and reported tests from tests actually run. Do not bind old reports to a new contract without revalidation. Preserve prior decision/provenance unless superseded; identify a superseding human decision explicitly. If saving fails, report the failure and a brief handoff; do not claim it was saved.
On a new session, retrieve the checkpoint yourself and state what is done, pending, blocked and stale before further effects. A handoff/SQLite record cannot restore approval, delegation, OS rights or trusted completion: revalidate current contract, Git and current-provider decisions (H/D if applicable). STRICT remains read-only for product code. No daemon, hook, automatic model switch or extra UI is installed.
'''


def checkpoint_template(records, task_id, milestone='HANDOFF'):
    if milestone not in MILESTONES: raise StoreError('Unknown checkpoint milestone. Allowed: '+', '.join(MILESTONES)+'; progress within a batch uses HANDOFF with phase IMPLEMENTING')
    contract = records.core.contract_revision(task_id)
    previous = records.latest('PROGRESS', task_id=task_id)
    # Copy only known continuity fields, not arbitrary transcript data. Facts
    # must be reconciled by the caller; stale source/contract reports cannot save.
    carried = {}
    if previous:
        for key in ('advisory_decision', 'human_contract_decision_observed', 'advisory_delegation'):
            if key in previous['content']: carried[key] = deepcopy(previous['content'][key])
        if (previous['content'].get('contract_sha256')==contract['sha256']
                and previous['content'].get('contract_revision')==contract['revision'] and previous['content'].get('implementation_plan')):
            carried['implementation_plan']=deepcopy(previous['content']['implementation_plan'])
    return {'checkpoint': {
                'checkpoint_schema': SCHEMA, 'milestone': milestone,
                'contract_sha256': contract['sha256'], 'contract_revision': contract['revision'],
                'phase': 'WAITING_DECISION', 'summary': '', 'completed': [], 'remaining': [],
                'changed_paths': [], 'blockers': [], 'next_action': '', **carried},
            'expected_revision': previous['revision'] if previous else 0,
            'previous_report_contract_binding': {
                'contract_sha256': previous['content'].get('contract_sha256'),
                'contract_revision': previous['content'].get('contract_revision')} if previous else None,
            'instructions': 'Template only. Reconcile current contract, prior facts/decisions and Git; fill actual milestone facts before saving.',
            'write_authorized': False, 'trusted': False}


def _paths(paths):
    if not isinstance(paths, list) or len(paths) > 40: return False
    for name in paths:
        if not isinstance(name, str) or not name or len(name) > 400 or '\\' in name or '\x00' in name:
            return False
        path = PurePosixPath(name)
        if (path.is_absolute() or not path.parts or '..' in path.parts or '.git' in path.parts
                or path.as_posix() != name or any(c in name for c in '*?[]')): return False
    return len(set(paths)) == len(paths)


def save_checkpoint(records, task_id, content, *, expected_revision=0):
    """Validate a milestone report then CAS through existing PROGRESS records."""
    if not isinstance(content, dict) or content.get('checkpoint_schema') != SCHEMA:
        raise StoreError('Expected agentflow.checkpoint.v1 object, not a template wrapper')
    if content.get('milestone') not in MILESTONES: raise StoreError('Unknown checkpoint milestone. Allowed: '+', '.join(MILESTONES))
    if not isinstance(content.get('phase'), str) or content['phase'] not in PHASES:
        raise StoreError('Unsupported reported phase. Allowed: '+', '.join(sorted(PHASES))+'; verification in progress uses VERIFYING or TESTING. Reread/reconcile before saving.')
    for name, limit in (('summary', 4000), ('next_action', 2000)):
        value = content.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise StoreError(f'Checkpoint requires a concise nonempty {name}')
    for name in ('completed', 'remaining', 'blockers'):
        value = content.get(name)
        if (not isinstance(value, list) or len(value) > 40
                or any(not isinstance(x, str) or not x.strip() or len(x) > 2000 for x in value)):
            raise StoreError(f'Checkpoint requires a bounded {name} list')
    if not _paths(content.get('changed_paths')): raise StoreError('Invalid changed_paths')
    if type(expected_revision) is not int or expected_revision < 0:
        raise StoreError('Invalid expected revision')
    current = records.latest('PROGRESS', task_id=task_id)
    revision = current['revision'] if current else 0
    if revision != expected_revision: raise ConflictError('PROGRESS changed; reread and reconcile before saving')
    contract = records.core.contract_revision(task_id)
    if (type(content.get('contract_revision')) is not int or content['contract_revision'] != contract['revision']
            or content.get('contract_sha256') != contract['sha256']):
        raise ConflictError('Contract changed or checkpoint is unbound; revalidate before saving')
    from .implementation import transition
    execution=transition(contract,records.store.repo,current['content'] if current else {},content)
    if content['milestone'] == 'CONTRACT_DECISION' and not any(
        content.get(key) for key in ('advisory_decision', 'human_contract_decision_observed', 'advisory_delegation')):
        raise StoreError('Contract-decision milestone requires reported decision provenance')
    hashes = content.get('source_hashes')
    manifest=content.get('source_manifest')
    if content['milestone'] == 'IMPLEMENTATION_VERIFICATION' and not hashes and manifest is None:
        raise StoreError('Implementation/verification checkpoint requires reported source_hashes')
    if manifest is not None:
        from .sources import observe
        state=observe(execution,records.core.store.repo,manifest)
        if state['status']!='CURRENT':raise ConflictError('Per-repo source coverage missing/stale; reconcile: '+str(state.get('reason',state['status'])))
    if hashes is not None:
        observed = observe_source_hashes(records.core.store.repo, hashes)
        if observed['status'] != 'CURRENT':
            raise ConflictError('Source hashes do not match bounded current observations; revalidate before saving')
    if current and current['content'] == content:
        return {'saved': False, 'no_changes': True, 'record_id': current['record_id'],
                'revision': current['revision'], 'trusted': False, 'write_authorized': False}
    result = records.put('PROGRESS', content, task_id=task_id, expected_revision=expected_revision,
                         status='UNVERIFIED_REPORT')
    return {**result, 'saved': True, 'write_authorized': False,
            'note': 'Checkpoint is an unverified report; no approval/lifecycle/completion transition.'}


def last_reported_verification(records, task_id, contract, progress_record):
    """Read the last verification fact, independent of later progress reports.

    Finish already saves report + binding atomically in one immutable PROGRESS
    row. Reuse that history: no new DB schema, duplicate save or PASS carry-over.
    The current progress revision bounds this snapshot during concurrent reads.
    """
    if not progress_record:
        return None
    with closing(records.store.connect(read_only=True)) as cn:
        rows = cn.execute('''SELECT id, revision, content_json FROM workflow_documents
            WHERE repo_id=? AND scope_key=? AND kind='PROGRESS' AND doc_key='primary'
            AND revision<=? AND instr(content_json, '"verification_report"')>0
            ORDER BY revision DESC''',
            (records.store.repo_id, task_id, progress_record['revision']))
        for row in rows:
            content = json.loads(row['content_json'])
            report = content.get('verification_report')
            if not isinstance(report, dict):
                continue
            # rc2 reports bind the actual tested snapshot inside the report.
            # rc1 history retains its original immutable checkpoint binding.
            own_binding=any(key in report for key in
                            ('contract_sha256','contract_revision','tested_source_hashes','tested_sources'))
            bound=report if own_binding else content
            hashes=report.get('tested_source_hashes') if own_binding else content.get('source_hashes')
            from .sources import observe,legacy_coverage
            tested_manifest=report.get('tested_sources')
            if tested_manifest is not None:
                from .implementation import effective
                try:source=observe(effective(contract,records.store.repo,progress_record['content']),records.store.repo,tested_manifest)
                except (StoreError,ValueError,OSError,RuntimeError) as exc:source={'status':'UNKNOWN','coverage':'INCOMPLETE','reason':str(exc)}
                coverage={'status':source['coverage']}
            else:
                source=observe_source_hashes(records.store.repo,hashes)
                coverage=legacy_coverage(contract['content'],records.store.repo,hashes,content.get('changed_paths'))
                if coverage['status']=='INCOMPLETE':source['status']='UNKNOWN'
            binding = _binding(bound, contract)
            return {'record_id': row['id'], 'progress_revision': row['revision'],
                    'contract_sha256': bound.get('contract_sha256'),
                    'contract_revision': bound.get('contract_revision'),
                    'binding_origin':'TESTED_REPORT' if own_binding else 'LEGACY_IMMUTABLE_PROGRESS',
                    'contract_freshness': binding, 'source_freshness': source,
                    'source_coverage':coverage,
                    'freshness': _aggregate([binding, source['status']]),
                    'assessment': report, 'trust': 'UNVERIFIED_REPORT',
                    'trusted': False, 'write_authorized': False}
    return None


def resume_brief(progress_record, status, verification=None):
    """Summarize stored facts; do not synthesize a completion or a new approval."""
    content = progress_record['content'] if progress_record else {}
    structured = content.get('checkpoint_schema') == SCHEMA
    def texts(name):
        value = content.get(name)
        return [x[:2000] for x in value[:40] if isinstance(x, str)] if isinstance(value, list) else []
    def text(name):
        value = content.get(name)
        return value[:4000] if isinstance(value, str) else None
    report = verification['assessment'] if verification else content.get('verification_report')
    summary = None
    if isinstance(report, dict):
        summary = {
            'verdict': str(report.get('reported_verdict', ''))[:80],
            'coverage': str(report.get('coverage', ''))[:30],
            'missing_criteria': [str(x)[:100] for x in report.get('missing_criteria', [])[:5]]
                if isinstance(report.get('missing_criteria'), list) else [],
            'trust': 'UNVERIFIED_REPORT',
            'freshness': verification['freshness'] if verification else status['reported_work']['freshness']}
        if report.get('user_workflow'):summary['user_workflow']=report['user_workflow']
        if verification:
            summary.update({key: verification[key] for key in
                ('record_id', 'progress_revision', 'contract_sha256', 'contract_revision', 'contract_freshness')})
            summary['source_freshness'] = verification['source_freshness']['status']
            summary['source_coverage'] = verification['source_coverage']
    return {
        'checkpoint_format': 'MISSING' if not progress_record else 'STRUCTURED' if structured else 'LEGACY',
        'record_id': progress_record['record_id'] if progress_record else None,
        'record_revision': progress_record['revision'] if progress_record else None,
        'reported_phase': text('phase'), 'reported_summary': text('summary'),
        'reported_completed': texts('completed'), 'reported_remaining': texts('remaining'),
        'reported_blockers': texts('blockers'), 'reported_changed_paths': texts('changed_paths'),
        'reported_next_action': text('next_action') or text('next'),
        'progress_freshness': status['reported_work']['freshness'],
        'status_recommendation': status['next_action'],
        'reported_verification': summary,
        'required_before_effects': ['RECONCILE_CURRENT_CONTRACT_AND_GIT',
                                    'REVALIDATE_CURRENT_PROVIDER_DECISIONS',
                                    'DO_NOT_TREAT_SAVED_REPORT_AS_AUTHORITY'],
        'trusted': False, 'write_authorized': False,
    }

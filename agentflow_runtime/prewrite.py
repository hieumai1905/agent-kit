"""A4 repair: checked decision checkpoint preparation/read-back.

No product writer, provider call, authenticated grant or native attestation.
Only agent-reported native observations are checked. The provider-side checked
flow must inspect successful results before calling its existing patch tool.
"""
from __future__ import annotations

from .continuity import save_checkpoint
from .delegation import contract_binding, review_record
from .status import observe_source_hashes
from agentflow_core import ConflictError, StoreError


def _validate(records, task_id, content):
    if not isinstance(content, dict): raise StoreError('Expected decision checkpoint object')
    if (content.get('milestone') != 'CONTRACT_DECISION' or content.get('phase') != 'IMPLEMENTING'
            or content.get('blockers') != []):
        raise StoreError('Prewrite requires an unblocked CONTRACT_DECISION/IMPLEMENTING checkpoint')
    current = records.core.contract_revision(task_id)
    if (content.get('contract_sha256') != current['sha256']
            or type(content.get('contract_revision')) is not int
            or content['contract_revision'] != current['revision']):
        raise ConflictError('Current contract no longer matches the decision checkpoint')
    report = content.get('advisory_delegation')
    if not isinstance(report, dict) or report.get('reported_process_status') != 'DELEGATED_ADVISORY_ELIGIBLE':
        raise StoreError('Current agent-native source review must be reported; saved state alone is not approval')
    if report.get('contract') != current['content']:
        raise ConflictError('Reported delegated contract differs from the actual core contract document')
    binding = report.get('canonical_contract_binding')
    if binding != {'contract_sha256': current['sha256'], 'contract_revision': current['revision']}:
        raise ConflictError('Missing or mismatched canonical binding')
    decision = report.get('decision', {})
    if decision.get('task_id') != task_id:
        raise ConflictError('Decision is bound to another task')
    if decision.get('contract_sha256') != contract_binding(current['content'])['sha256']:
        raise ConflictError('Decision envelope digest mismatch')
    diagnostic = review_record(records.core.store.repo, report)
    if diagnostic['blockers']:
        raise StoreError('Prewrite blocked: ' + ', '.join(diagnostic['blockers']))
    hashes = content.get('source_hashes')
    targets = current['content'].get('files', [])
    if not isinstance(hashes, dict) or not targets or not all(p in hashes for p in targets):
        raise StoreError('Current hashes are required for every proposed patch target')
    observation = observe_source_hashes(records.core.store.repo, hashes)
    if observation['status'] != 'CURRENT':
        raise ConflictError('Patch baseline changed or cannot be observed within limits')
    return current, report


def _reference(task_id, record, contract):
    return {'task_id': task_id, 'record_id': record['record_id'], 'revision': record['revision'],
            'sha256': record['sha256'], 'contract_sha256': contract['sha256'],
            'contract_revision': contract['revision']}


def prepare_decision(records, task_id, content, *, expected_revision=0):
    """Guard -> save milestone -> read-back -> guard. No patch is performed."""
    contract, _ = _validate(records, task_id, content)
    saved = save_checkpoint(records, task_id, content, expected_revision=expected_revision)
    latest = records.latest('PROGRESS', task_id=task_id)
    if (not latest or latest['record_id'] != saved['record_id']
            or latest['revision'] != saved['revision'] or latest['content'] != content
            or latest['status'] != 'UNVERIFIED_REPORT'):
        raise ConflictError('Decision checkpoint read-back mismatch; no patch may follow')
    reference = _reference(task_id, latest, contract)
    # If it aged while saving, this raises. The historical checkpoint can remain,
    # but the caller gets a failure, not a successful preparation result.
    check_decision(records, task_id, reference)
    return {'process_result': 'DECISION_CHECKPOINT_SAVED_UNVERIFIED', 'checkpoint_ref': reference,
            'trusted': False, 'write_authorized': False, 'native_certified': False}


def check_decision(records, task_id, reference):
    """Recheck exact latest decision and source ages immediately before patch."""
    if not isinstance(reference, dict) or reference.get('task_id') != task_id:
        raise StoreError('Missing task-bound decision checkpoint reference')
    if any(type(reference.get(key)) is not int or reference[key] < 1
           for key in ('revision', 'contract_revision')):
        raise StoreError('Checkpoint revisions must be positive integers')
    latest = records.latest('PROGRESS', task_id=task_id)
    contract = records.core.contract_revision(task_id)
    if (not latest or reference != _reference(task_id, latest, contract)
            or latest['status'] != 'UNVERIFIED_REPORT'):
        raise ConflictError('Decision checkpoint is missing, superseded or belongs to another contract')
    _validate(records, task_id, latest['content'])
    return {'process_result': 'DECISION_CHECKPOINT_RECHECKED_UNVERIFIED',
            'checkpoint_ref': reference, 'trusted': False, 'write_authorized': False,
            'native_certified': False,
            'note': 'Process consistency only. Independently reviewed native sources and provider permissions are still required; not an execution grant.'}

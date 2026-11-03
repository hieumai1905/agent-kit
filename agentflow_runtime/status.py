"""A2 read-only presentation of reported work, provenance and freshness.

No task transitions, approval parsing, test execution or native attestation.
File digests are bounded observations against UNTRUSTED reported hashes; they
do not establish who approved anything, test coverage or a filesystem lock.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from .delegation import contract_binding

PHASES = {
    'PREFLIGHT': 'PREFLIGHT', 'IMPLEMENTING': 'IMPLEMENTING',
    'IMPLEMENTED': 'IMPLEMENTED', 'IMPLEMENTATION_COMPLETE': 'IMPLEMENTED',
    'IMPLEMENTED_AND_FOCUSED_CHECKS_PASSED': 'IMPLEMENTED',
    'VERIFYING': 'VERIFYING', 'TESTING': 'VERIFYING',
    'COMPLETED': 'DONE_REPORTED', 'DONE': 'DONE_REPORTED', 'REPORTED_DONE': 'DONE_REPORTED',
    'BLOCKED': 'BLOCKED', 'PAUSED': 'PAUSED',
    'WAITING_APPROVAL': 'WAITING_DECISION', 'WAITING_DECISION': 'WAITING_DECISION',
}
FILE_KINDS = frozenset({'source', 'file', 'source_file', 'test_file'})
MAX_EVIDENCE = 12
MAX_FILES = 32
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
HEX64 = re.compile(r'^[0-9a-f]{64}$')


def _binding(body, contract):
    sha, revision = body.get('contract_sha256'), body.get('contract_revision')
    if sha is None and revision is None:
        return 'UNBOUND'
    if (not isinstance(sha, str) or not HEX64.fullmatch(sha)
            or type(revision) is not int or revision < 1):
        return 'UNKNOWN'
    return 'CURRENT' if sha == contract['sha256'] and revision == contract['revision'] else 'STALE'


def _aggregate(states, *, truncated=False):
    if 'STALE' in states: return 'STALE'
    if truncated or 'UNKNOWN' in states: return 'UNKNOWN'
    if not states or 'UNBOUND' in states: return 'UNBOUND'
    return 'CURRENT'


class _Files:
    def __init__(self, repo, *, max_files=None, max_total_bytes=None):
        self.root = Path(repo).resolve(strict=True)
        self.cache = {}
        self.bytes_read = 0
        self.max_files = max_files
        self.max_total_bytes = max_total_bytes

    def check(self, name, expected):
        if not isinstance(expected, str) or not HEX64.fullmatch(expected):
            return {'path': name, 'status': 'UNKNOWN', 'reason': 'INVALID_REPORTED_HASH'}
        if name not in self.cache:
            self.cache[name] = self._observe(name)
        observed = self.cache[name]
        if observed.get('sha256'):
            return {'path': name, 'status': 'CURRENT' if observed['sha256'] == expected else 'STALE',
                    'reason': 'MATCHES_REPORTED_HASH' if observed['sha256'] == expected else 'FILE_CONTENT_CHANGED'}
        return {'path': name, **observed}

    def _observe(self, name):
        if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
            return {'status': 'UNKNOWN', 'reason': 'UNSAFE_PATH'}
        relative = PurePosixPath(name)
        if (relative.is_absolute() or not relative.parts or '..' in relative.parts
                or '.git' in relative.parts or relative.as_posix() != name
                or any(c in name for c in '*?[]')):
            return {'status': 'UNKNOWN', 'reason': 'UNSAFE_PATH'}
        if len(self.cache) >= (MAX_FILES if self.max_files is None else self.max_files):
            return {'status': 'UNKNOWN', 'reason': 'FILE_COUNT_LIMIT'}
        target = self.root
        try:
            for part in relative.parts:
                target = target / part
                if target.is_symlink():
                    return {'status': 'UNKNOWN', 'reason': 'SYMLINK_NOT_READ'}
            if not target.resolve().is_relative_to(self.root):
                return {'status': 'UNKNOWN', 'reason': 'UNSAFE_PATH'}
            before = target.stat()
            if not stat.S_ISREG(before.st_mode):
                return {'status': 'UNKNOWN', 'reason': 'NOT_REGULAR_FILE'}
            total_limit = MAX_TOTAL_BYTES if self.max_total_bytes is None else self.max_total_bytes
            if before.st_size > MAX_FILE_BYTES or self.bytes_read + before.st_size > total_limit:
                return {'status': 'UNKNOWN', 'reason': 'FILE_SIZE_OR_TOTAL_BUDGET'}
            fd = os.open(target, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
            with os.fdopen(fd, 'rb') as source:
                opened = os.fstat(source.fileno())
                if (not stat.S_ISREG(opened.st_mode) or opened.st_ino != before.st_ino
                        or opened.st_dev != before.st_dev):
                    return {'status': 'UNKNOWN', 'reason': 'FILE_CHANGED_DURING_READ'}
                read_limit = min(MAX_FILE_BYTES, total_limit - self.bytes_read)
                payload = source.read(read_limit)
                self.bytes_read += len(payload)
                after = os.fstat(source.fileno())
            if len(payload) != before.st_size:
                return {'status': 'UNKNOWN', 'reason': 'FILE_CHANGED_DURING_READ'}
            final = target.stat()
            signature = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
            if signature(before) != signature(after) or signature(before) != signature(final):
                return {'status': 'UNKNOWN', 'reason': 'FILE_CHANGED_DURING_READ'}
            return {'sha256': hashlib.sha256(payload).hexdigest()}
        except FileNotFoundError:
            return {'status': 'STALE', 'reason': 'FILE_MISSING'}
        except (OSError, RuntimeError, ValueError):
            return {'status': 'UNKNOWN', 'reason': 'FILE_UNREADABLE'}

    def hashes(self, hashes):
        if hashes is None:
            return {'status': 'UNBOUND', 'files': [], 'reason': 'NO_REPORTED_SOURCE_HASHES'}
        if not isinstance(hashes, dict) or not hashes:
            return {'status': 'UNKNOWN', 'files': [], 'reason': 'INVALID_SOURCE_HASHES'}
        pairs = list(hashes.items())[:MAX_FILES]
        checks = [self.check(name, expected) for name, expected in pairs]
        truncated = len(hashes) > MAX_FILES
        return {'status': _aggregate([x['status'] for x in checks], truncated=truncated),
                'files': checks, 'truncated': truncated}


def _reference(value):
    if not isinstance(value, dict): return {}
    return {k: value[k][:180] for k in ('host', 'thread_id', 'message_id', 'item_type')
            if isinstance(value.get(k), str)}


def observe_source_hashes(repo, hashes):
    """Bounded read-only observations shared by status and milestone validation."""
    return _Files(repo).hashes(hashes)


def _decisions(progress, contract):
    claims = []
    direct = progress.get('advisory_decision')
    if isinstance(direct, dict):
        claims.append({'kind': 'DIRECT_HUMAN_REPORTED' if direct.get('kind') == 'DIRECT_HUMAN' else 'UNRECOGNIZED_REPORTED_SOURCE',
                       'reported_decision': str(direct.get('decision', 'UNKNOWN'))[:120],
                       'source_reference': _reference(direct.get('source')),
                       'contract_binding': _binding(direct, contract)})
    legacy = progress.get('human_contract_decision_observed')
    if isinstance(legacy, str) and legacy.strip():
        claims.append({'kind': 'DIRECT_HUMAN_REPORTED_LEGACY', 'reported_text': legacy[:300],
                       'reported_decision': 'TEXT_ONLY_NOT_AUTHENTICATED',
                       'source_reference': {}, 'contract_binding': 'UNBOUND'})
    delegation = progress.get('advisory_delegation')
    if isinstance(delegation, dict):
        decision = delegation.get('decision') if isinstance(delegation.get('decision'), dict) else {}
        sources = delegation.get('sources') if isinstance(delegation.get('sources'), dict) else {}
        # A1 hashes a versioned envelope, while core hashes its stored contract.
        # Never compare these different digest domains and invent STALE.
        canonical = delegation.get('canonical_contract_binding')
        canonical = canonical if isinstance(canonical, dict) else {}
        observation = delegation.get('observation') if isinstance(delegation.get('observation'), dict) else {}
        document_status = 'UNKNOWN'
        if isinstance(delegation.get('contract'), dict) and delegation['contract']:
            try:
                document_status = ('CONSISTENT' if contract_binding(delegation['contract'])['sha256'] == decision.get('contract_sha256')
                                   else 'MISMATCH')
            except (ValueError, TypeError):
                document_status = 'UNKNOWN'
        claims.append({'kind': 'DELEGATED_REPORTED',
                       'reported_decision': str(decision.get('kind', 'UNKNOWN'))[:120],
                       'source_references': {k: _reference(sources.get(k)) for k in ('human_grant', 'coordinator_decision')},
                       'contract_binding': _binding(canonical, contract),
                       'decision_digest_scheme': 'agentflow.delegated-contract.v1',
                       'reported_document_consistency': document_status,
                       'reported_process_status': (delegation.get('reported_process_status')
                           if delegation.get('reported_process_status') in
                           ('NOT_REVIEWED','DELEGATED_ADVISORY_BLOCKED','DELEGATED_ADVISORY_ELIGIBLE') else 'UNRECOGNIZED'),
                       'reported_stop_flags': [key for key in ('revoked','paused','superseded','task_complete')
                                               if observation.get(key) is True],
                       'delegation_revalidation': 'REQUIRED_IN_CURRENT_PROVIDER'})
    return {'status': 'NOT_REPORTED' if not claims else 'REPORTED_UNVERIFIED',
            'claims': claims, 'source_verification': 'NOT_RECHECKED_IN_THIS_VIEW',
            'approval_authenticated': False}


def task_status(records, task_id, *, task=None, contract=None, progress_record=None):
    """Additive presentation view; existing canonical fields keep their meaning."""
    core = records.core
    task = task or core.get_task(task_id)
    contract = contract or core.contract_revision(task_id)
    progress_record = progress_record or records.latest('PROGRESS', task_id=task_id)
    progress = progress_record['content'] if progress_record else {}
    files = _Files(core.store.repo)
    raw_phase = progress.get('phase')
    phase = PHASES.get(raw_phase, 'UNRECOGNIZED') if isinstance(raw_phase, str) else 'NOT_REPORTED'
    progress_binding = _binding(progress, contract)
    if progress.get('source_manifest') is not None:
        from .sources import observe
        source_freshness = observe(contract['content'], core.store.repo, progress['source_manifest'])
    else:
        from .sources import legacy_coverage
        source_freshness = files.hashes(progress.get('source_hashes'))
        coverage = legacy_coverage(contract['content'], core.store.repo, progress.get('source_hashes'), progress.get('changed_paths'))
        source_freshness['coverage'] = coverage
        if coverage['status'] == 'INCOMPLETE': source_freshness['status'] = 'UNKNOWN'
    work = {
        'phase': phase, 'reported_phase': raw_phase[:180] if isinstance(raw_phase, str) else None,
        'record_id': progress_record['record_id'] if progress_record else None,
        'record_revision': progress_record['revision'] if progress_record else None,
        'trust': 'UNVERIFIED_REPORT', 'contract_binding': progress_binding,
        'source_freshness': source_freshness,
        'freshness': _aggregate([progress_binding, source_freshness['status']]),
    }
    evidence = []
    with closing(core.store.connect(read_only=True)) as cn:
        rows = list(cn.execute('''SELECT id,kind,reported_status,attestation,metadata_json,recorded_at
            FROM evidence WHERE task_id=? ORDER BY recorded_at DESC,id DESC LIMIT ?''', (task_id, MAX_EVIDENCE + 1)))
        for row in rows[:MAX_EVIDENCE]:
            item = dict(row)
            metadata = json.loads(item.pop('metadata_json'))
            metadata = metadata if isinstance(metadata, dict) else {}
            binding = _binding(metadata, contract)
            deps = list(cn.execute('''SELECT d.kind,d.artifact_key,d.content_sha256,d.revision,
                a.content_sha256 AS current_hash,a.revision AS current_revision
                FROM evidence_dependencies d LEFT JOIN artifacts a ON a.repo_id=d.repo_id
                AND a.kind=d.kind AND a.artifact_key=d.artifact_key
                WHERE d.evidence_id=? ORDER BY d.kind,d.artifact_key LIMIT ?''', (item['id'], MAX_FILES + 1)))
            registry_stale = any(d['current_hash'] != d['content_sha256'] or d['current_revision'] != d['revision'] for d in deps)
            checks = []
            for dep in deps[:MAX_FILES]:
                if dep['kind'].lower() in FILE_KINDS:
                    checks.append(files.check(dep['artifact_key'], dep['content_sha256']))
                else:
                    checks.append({'path': dep['artifact_key'], 'status': 'UNKNOWN',
                                   'reason': 'NON_FILE_DEPENDENCY_NOT_OBSERVED'})
            content_state = _aggregate([c['status'] for c in checks], truncated=len(deps) > MAX_FILES)
            freshness = _aggregate([binding, content_state, 'STALE' if registry_stale else 'CURRENT'])
            evidence.append({**item, 'contract_binding': binding, 'content_freshness': content_state,
                             'freshness': freshness, 'registry_freshness': 'STALE' if registry_stale else 'CURRENT' if deps else 'UNBOUND',
                             'file_observations': checks, 'dependencies_truncated': len(deps) > MAX_FILES,
                             'verification': 'UNVERIFIED', 'tests_rerun': False})
    truncated = len(rows) > MAX_EVIDENCE
    statuses = {x['reported_status'] for x in evidence}
    verification_summary = ('NO_EVIDENCE' if not evidence else 'INCOMPLETE_REPORTS' if truncated
                            else 'REPORTED_FAILURE_OR_BLOCKER' if statuses & {'FAIL', 'BLOCKED'}
                            else 'REPORTED_PASS' if statuses == {'PASS'} else 'MIXED_OR_INCOMPLETE_REPORTS')
    verification = {
        'summary': verification_summary, 'reported_evidence': evidence,
        'evidence_truncated': truncated,
        'freshness': _aggregate([x['freshness'] for x in evidence], truncated=truncated),
        'trust': 'UNVERIFIED', 'tests_rerun': False,
    }
    provenance = _decisions(progress, contract)
    warnings = []
    if phase in ('IMPLEMENTED', 'DONE_REPORTED') and task['lifecycle'] == 'WAITING_APPROVAL':
        warnings.append('REPORTED_WORK_AND_CANONICAL_LIFECYCLE_DIFFER')
    if work['freshness'] != 'CURRENT': warnings.append('PROGRESS_REQUIRES_REVALIDATION')
    if verification['freshness'] != 'CURRENT': warnings.append('EVIDENCE_REQUIRES_REVALIDATION')
    if any(x['contract_binding'] == 'STALE' for x in provenance['claims']):
        warnings.append('REPORTED_DECISION_FOR_OLD_CONTRACT')
    if any(x.get('reported_document_consistency') == 'MISMATCH' for x in provenance['claims']):
        warnings.append('DELEGATED_DOCUMENT_DIGEST_MISMATCH')
    if any(x['reported_decision'] in ('REJECTED','DECLINED','REVOKED','PAUSED','STOP')
           or x.get('reported_stop_flags') or x.get('reported_process_status') == 'DELEGATED_ADVISORY_BLOCKED'
           for x in provenance['claims']):
        warnings.append('REPORTED_DECISION_OR_DELEGATION_NOT_CLEAR_TO_PROCEED')
    if phase in ('BLOCKED', 'PAUSED'):
        action = 'RESOLVE_REPORTED_BLOCKER_OR_PAUSE'
    elif 'REPORTED_DECISION_OR_DELEGATION_NOT_CLEAR_TO_PROCEED' in warnings:
        action = 'REVIEW_REPORTED_DECISION_OR_STOP_IN_PROVIDER'
    elif progress_binding == 'STALE' or any(x['contract_binding'] == 'STALE' for x in evidence):
        action = 'REVALIDATE_CONTRACT'
    elif 'REPORTED_DECISION_FOR_OLD_CONTRACT' in warnings:
        action = 'REVIEW_DECISION_FOR_CURRENT_CONTRACT'
    elif 'DELEGATED_DOCUMENT_DIGEST_MISMATCH' in warnings:
        action = 'RECONCILE_REPORTED_DELEGATION_DOCUMENT'
    elif 'STALE' in (work['freshness'], verification['freshness']):
        action = 'REVIEW_CURRENT_DIFF_AND_RERUN_AFFECTED_CHECKS'
    elif verification_summary == 'REPORTED_FAILURE_OR_BLOCKER':
        action = 'REVIEW_REPORTED_FAILURES'
    elif progress and work['freshness'] != 'CURRENT':
        action = 'BIND_OR_REVALIDATE_REPORTED_PROGRESS'
    elif evidence and verification['freshness'] != 'CURRENT':
        action = 'BIND_OR_REVALIDATE_REPORTED_EVIDENCE'
    elif phase in ('IMPLEMENTED', 'DONE_REPORTED'):
        action = 'REVIEW_REPORTED_RESULTS_AND_CURRENT_DIFF'
    else:
        action = 'REVIEW_CURRENT_CONTRACT_AND_DECISION_IN_PROVIDER'
    explanation = (
        'Tiến độ và kết quả kiểm tra dưới đây là lời báo của agent. Lifecycle canonical là trạng thái trong kit; '
        'WAITING_APPROVAL không tự kết luận code chưa được làm hoặc người dùng chưa từng duyệt trong chat. '
        'Nguồn quyết định chưa được xác minh lại; view này không chạy lại test và không cấp quyền.')
    return {
        'schema': 'agentflow.task-status.v1', 'task_id': task_id,
        'reported_work': work, 'decision_provenance': provenance, 'verification': verification,
        'canonical_state': {'lifecycle': task['lifecycle'], 'contract_revision': contract['revision'],
                            'claimed_approved_contract_revision': task['approved_contract_revision'],
                            'approval_verification': 'NOT_VERIFIED_IN_THIS_RUNTIME',
                            'definition_of_done': 'NOT_VERIFIED'},
        'warnings': warnings, 'next_action': action, 'explanation_vi': explanation,
        'freshness_scope': 'REPORTED_CONTRACT_AND_DEPENDENCIES_ONLY_NOT_FULL_TEST_COVERAGE',
        'snapshot_note': 'Bounded observations of untrusted records and current files, not an atomic snapshot, test run or native attestation.',
        'write_authorized': False, 'auto_complete': False, 'auto_approval': False,
    }

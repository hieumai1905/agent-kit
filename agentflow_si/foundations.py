"""SI-01/02/03/06/11/14 diagnostics, with fail-closed security semantics."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re

from agentflow_core import LocalCoordinator, StoreError
from agentflow_core.db import canonical_json
from agentflow_core.db import StateStore

PROVIDERS = ('codex_desktop', 'codex_cli', 'claude_desktop', 'claude_cli')
SHA256 = re.compile(r'^[a-f0-9]{64}$')


def trust_boundary(repo, state_home=None) -> dict:
    """SI-01: report an authority *gap*, not a spoofable certification.

    A local Python process sharing agent credentials has no trustworthy way to
    attest human origin, protected key material, or OS mandatory confinement.
    """
    store = StateStore(repo, state_home)
    return {
        'si': 'SI-01', 'decision': 'DENY_EXECUTION', 'trusted_approval': False,
        'trusted_control_plane': False, 'mandatory_os_write_boundary': False,
        'approval_claim_from_chat': 'UNVERIFIED',
        'agent_writable_sqlite': 'NOT_A_TRUST_ROOT',
        'runtime_state_dir': str(store.state_dir),
        'native_human_provenance': 'NOT_TESTED',
        'code_write_enabled': False, 'status': 'BLOCKED_NATIVE_AUTHORITY',
        'new_user_interface_installed': False,
        'note': 'Existing Codex/Claude chat or terminal remains the interface. No additional UI is installed.',
    }


def capability_observations(repo, state_home=None, observations=None) -> dict:
    """SI-02: exact-version discovery data, never a certification authority.

    Caller-supplied observations can be inaccurate; bound source = UNTRUSTED.
    """
    store = StateStore(repo, state_home)
    observations = observations or {}
    if not isinstance(observations, dict) or set(observations)-set(PROVIDERS):
        raise ValueError('Unsupported provider observation')
    result = {}
    for name in PROVIDERS:
        record = observations.get(name, {})
        if not isinstance(record, dict):
            raise ValueError('Provider observation must be a mapping')
        # Never embed arbitrary secrets, paths or configuration text in the report.
        for key in record:
            if key not in ('version','build','permission_mode','tool_paths','config_sha256','os_version','test_ids'):
                raise ValueError('Unsupported or sensitive observation field')
        if len(canonical_json(record).encode()) > 16000:
            raise ValueError('Observation too large')
        if 'config_sha256' in record and not SHA256.fullmatch(str(record['config_sha256'])):
            raise ValueError('config_sha256 must be sha256')
        if 'tool_paths' in record and (not isinstance(record['tool_paths'], list) or
            len(record['tool_paths']) > 80 or not all(isinstance(x,str) and len(x)<250 for x in record['tool_paths'])):
            raise ValueError('Invalid tool_paths')
        result[name] = {
            'observation': record, 'observation_sha256': sha256(canonical_json(record).encode()).hexdigest(),
            'observation_provenance': 'UNTRUSTED_INPUT',
            'native_enforcement_test': 'NOT_VERIFIED', 'mode': 'NOT_CERTIFIED',
            'code_write_enabled': False,
        }
    return {'si':'SI-02', 'host': {'os':platform.system(), 'release':platform.release(),
                                 'arch':platform.machine()}, 'repo_id':store.repo_id,
            'providers':result, 'enforced_available':False,
            'note':'Detection/metadata are not independent native OS security evidence.'}


def metadata_location(repo, state_home=None, *, export_destination=None) -> dict:
    """SI-03: validate local storage and preview export. NEVER copy data."""
    store=StateStore(repo,state_home)
    output = {'si':'SI-03','state_dir':str(store.state_dir), 'repo':str(store.repo),
              'state_outside_repo':not store.state_dir.is_relative_to(store.repo),
              'export_performed':False, 'export_needs_separate_authorization':True}
    if export_destination:
        dest=Path(export_destination).expanduser().resolve()
        if dest.is_relative_to(store.repo) or dest == store.repo:
            raise ValueError('Export into working tree is forbidden without an explicit approved workflow')
        if dest.is_relative_to(store.state_dir):
            raise ValueError('Export destination must be outside live state directory')
        output['export_plan']={'destination':str(dest),'action':'NOT_RUN', 'data_class':'SENSITIVE_REVIEW_REQUIRED'}
    return output


def session_fencing(repo, state_home=None, *, session_id=None, now_epoch=None, heartbeat_max_age=300) -> dict:
    """SI-06: observe durable session/intent generation and stale state, no grants."""
    app=LocalCoordinator(repo,state_home,initialize=False)
    if not app.store.db_file.exists():
        return {'si':'SI-06', 'state':'NOT_INITIALIZED', 'resumed':False,'grants_issued':False}
    now=int(now_epoch if now_epoch is not None else datetime.now(timezone.utc).timestamp())
    if not isinstance(heartbeat_max_age,int) or isinstance(heartbeat_max_age,bool) or heartbeat_max_age<1:
        raise ValueError('Invalid heartbeat age limit')
    with closing(app.store.connect(read_only=True)) as cn:
        if session_id:
            s=cn.execute('SELECT * FROM sessions WHERE id=? AND repo_id=?',
                         (session_id,app.store.repo_id)).fetchone()
            if not s: raise StoreError('Unknown session for repo')
            sessions=[s]
        else:
            sessions=cn.execute('SELECT * FROM sessions WHERE repo_id=?', (app.store.repo_id,)).fetchall()
        entries=[]
        for s in sessions:
            try:
                last_heartbeat=int(datetime.fromisoformat(s['heartbeat_at']).timestamp())
                heartbeat_age=max(0,now-last_heartbeat)
            except (ValueError,TypeError,OverflowError):
                heartbeat_age=None
            stale_heartbeat=heartbeat_age is None or heartbeat_age>heartbeat_max_age
            leases=[dict(row) for row in cn.execute('''SELECT resource_key,generation,state,expires_at
                FROM resource_intents WHERE repo_id=? AND holder_session=?''',
                (app.store.repo_id,s['id']))]
            expired=[x['resource_key'] for x in leases if x['state']=='ACTIVE' and
                     (x['expires_at'] is None or x['expires_at']<=now)]
            live=[x['resource_key'] for x in leases if x['state']=='ACTIVE' and
                  x['expires_at'] is not None and x['expires_at']>now]
            entries.append({'session_id':s['id'], 'provider':s['provider'],
                'lifecycle':s['lifecycle'], 'revision':s['revision'],
                'heartbeat_at':s['heartbeat_at'], 'heartbeat_age_seconds':heartbeat_age,
                'stale_heartbeat':stale_heartbeat, 'resource_intents':leases,
                'stale_intents':expired, 'active_claims':live,
                'reconciliation_required':bool(expired or (live and (s['lifecycle']!='ACTIVE' or stale_heartbeat))),
                'execution_authorized':False})
    return {'si':'SI-06', 'sessions':entries, 'leases_are_cooperative_only':True,
            'grants_issued':False, 'session_namespace':'provider + runtime-generated session id'}


def recovery_status(repo, state_home=None, *, backup=None, expected_sha256=None) -> dict:
    """SI-11: inspect existing WAL/audit/backup contract. No automatic restore."""
    app=LocalCoordinator(repo,state_home,initialize=False)
    if app.store.db_file.exists():
        doctor=app.doctor()
    else:
        doctor={'initialized':False,'healthy':False,'reasons':['No state database'],'enforced':False}
    checked=None
    if backup:
        checked=app.store.verify_backup(backup,expected_sha256)
    return {'si':'SI-11','doctor':doctor,'verified_backup':checked,
            'cross_db_filesystem_atomicity':False,
            'post_crash_external_mutations':'RECONCILIATION_REQUIRED',
            'automatic_restore':False, 'trusted_audit_attestation':False,
            'note':'Audit hash chain detects accidental DB edits, not same-UID malicious rewriting.'}


def release_readiness(repo, state_home=None, *, observations=None) -> dict:
    """SI-14: fail-closed dry-run matrix. Never install or certify an adapter."""
    base=capability_observations(repo,state_home,observations)
    store=StateStore(repo,state_home)
    checks={
        'runtime_outside_worktree': not store.state_dir.is_relative_to(store.repo),
        'trusted_human_approval': False,
        'mandatory_write_isolation':False,
        'native_negative_tests_pass':False,
        'four_provider_certificates':False,
        'task_scoped_git_enforced':False,
        'installer_upgrade_rollback_native_pass':False,
    }
    from agentflow_runtime.installer import GuidanceInstaller, InstallerError
    try:
        install_preview=GuidanceInstaller(repo,state_home).inspect()
    except (InstallerError,OSError,UnicodeError) as exc:
        install_preview={'mode':'BLOCKED_ON_EXISTING_CONFIG',
                         'reason':type(exc).__name__,'write_enforced':False}
    return {'si':'SI-14','release_class':'NON_CERTIFIED_GUIDANCE_ONLY',
        'installer_inspection':install_preview,
        'install_mode':'PREVIEW_DRY_RUN_ONLY','installation_performed':False,
        'checks':checks,'providers':base['providers'],'G2':'BLOCKED',
        'G5':'BLOCKED','G7':'PARTIAL',
        'ready_for_native_certification_batch':False,
        'can_opt_out_of_security_requirements':False,
        'note':'No third-party desktop UI, hooks, native helper, or OS settings are modified.'}

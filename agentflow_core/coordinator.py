"""D1 deterministic task/session/work state API; no product-code mutation.

All state changes use sqlite BEGIN IMMEDIATE + idempotency keys. Method names
reflect exactly the trust level: no APPROVE, AUTHORIZE_WRITE, COMMIT or DEPLOY
operation is exposed by this wave.
"""
from __future__ import annotations

from contextlib import closing
import datetime as dt
import json
from pathlib import Path
import re
import uuid

from .db import StateStore, canonical_json, digest, require_key, utc_now
from .errors import ConflictError, GateNotImplemented, InvalidTransition, StoreError
from .states import check_transition

HEX64 = re.compile(r'^[0-9a-f]{64}$')
PROVIDERS = {'codex_cli', 'codex_desktop', 'claude_cli', 'claude_desktop', 'unknown'}


def _new_id(prefix: str) -> str:
    return prefix + '-' + uuid.uuid4().hex[:20]


def _expect(row, kind: str, identifier: str):
    if not row:
        raise StoreError(f'{kind} not found: {identifier}')
    return row


def _version(row, expected: int, kind: str):
    if not isinstance(expected, int) or row['revision'] != expected:
        raise ConflictError(f'{kind} changed; expected revision {expected}, found {row["revision"]}')


def _validate_document(doc: dict) -> str:
    if not isinstance(doc, dict) or not doc:
        raise StoreError('Document must be a nonempty JSON object')
    encoded = canonical_json(doc)
    if len(encoded.encode('utf-8')) > 256 * 1024:
        raise StoreError('Document exceeds 256 KiB; store large evidence separately')
    return encoded


class LocalCoordinator:
    def __init__(self, repo: str | Path, state_home: str | Path | None = None,
                 *, initialize: bool = True, clock=None):
        self.store = StateStore(repo, state_home, clock=clock)
        if initialize:
            self.store.initialize()

    def create_task(self, title: str, request: str, *, kind: str = 'IMPLEMENTATION',
                    request_key: str | None = None) -> dict:
        title, request = require_key(title.strip(), 'title', 180), require_key(request.strip(), 'request', 20000)
        if kind not in ('IMPLEMENTATION', 'INVESTIGATION'):
            raise StoreError('Unknown task kind')
        payload = dict(title=title, request=request, kind=kind, repo_id=self.store.repo_id)

        def run(cn):
            task_id, ts = _new_id('T'), utc_now(self.store.clock)
            document = {'source_request': request, 'purpose': kind}
            cn.execute('''INSERT INTO tasks
                (id,repo_id,title,kind,lifecycle,revision,current_contract_revision,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)''',
                (task_id,self.store.repo_id,title,kind,'DRAFT',1,1,ts,ts))
            cn.execute('''INSERT INTO contract_revisions
                (task_id,revision,content_json,content_sha256,created_at)
                VALUES(?,?,?,?,?)''',
                (task_id,1,canonical_json(document),digest(document),ts))
            return dict(task_id=task_id, lifecycle='DRAFT', revision=1, contract_revision=1,
                        contract_hash=digest(document), approved=False)
        return self.store.mutate('task.create', payload, run, request_key=request_key)

    def get_task(self, task_id: str) -> dict:
        with closing(self.store.connect(read_only=True)) as cn:
            row = _expect(cn.execute('SELECT * FROM tasks WHERE id=? AND repo_id=?',
                                      (task_id,self.store.repo_id)).fetchone(),'Task',task_id)
            return dict(row)

    def list_tasks(self, limit: int = 30) -> list[dict]:
        if not isinstance(limit, int) or not 1 <= limit <= 200:
            raise StoreError('Invalid task limit')
        with closing(self.store.connect(read_only=True)) as cn:
            return [dict(row) for row in cn.execute('SELECT * FROM tasks WHERE repo_id=? ORDER BY updated_at DESC LIMIT ?',
                                                    (self.store.repo_id,limit))]

    def contract_revision(self, task_id: str, revision: int | None = None) -> dict:
        with closing(self.store.connect(read_only=True)) as cn:
            task = _expect(cn.execute('SELECT * FROM tasks WHERE id=? AND repo_id=?',
                                      (task_id,self.store.repo_id)).fetchone(),'Task',task_id)
            requested = revision or task['current_contract_revision']
            row = _expect(cn.execute('SELECT * FROM contract_revisions WHERE task_id=? AND revision=?',
                                      (task_id,requested)).fetchone(),'Contract',str(requested))
            return dict(revision=row['revision'],content=json.loads(row['content_json']),
                        sha256=row['content_sha256'], author_class=row['author_class'])

    def transition_task(self, task_id: str, expected_revision: int, to_state: str,
                        *, request_key: str | None = None) -> dict:
        payload = dict(task_id=task_id, expected_revision=expected_revision, to_state=to_state)
        def run(cn):
            task = _expect(cn.execute('SELECT * FROM tasks WHERE id=? AND repo_id=?',
                                      (task_id,self.store.repo_id)).fetchone(),'Task',task_id)
            _version(task,expected_revision,'Task')
            check_transition('task',task['lifecycle'],to_state)
            if to_state == 'WAITING_APPROVAL':
                contract = cn.execute('SELECT content_json FROM contract_revisions WHERE task_id=? AND revision=?',
                                      (task_id,task['current_contract_revision'])).fetchone()
                if not contract or not json.loads(contract['content_json']).get('objective'):
                    raise StoreError('Cannot propose a request-only draft; submit a contract revision')
            cn.execute('UPDATE tasks SET lifecycle=?, revision=revision+1, updated_at=? WHERE id=?',
                       (to_state,utc_now(self.store.clock),task_id))
            return dict(task_id=task_id,lifecycle=to_state,revision=expected_revision+1)
        return self.store.mutate('task.transition',payload,run,request_key=request_key,entity_id=task_id)

    def revise_contract(self, task_id: str, expected_task_revision: int, content: dict,
                        *, request_key: str | None = None) -> dict:
        encoded = _validate_document(content)
        payload = dict(task_id=task_id,expected_task_revision=expected_task_revision,content=content)
        def run(cn):
            task = _expect(cn.execute('SELECT * FROM tasks WHERE id=? AND repo_id=?',
                                      (task_id,self.store.repo_id)).fetchone(),'Task',task_id)
            _version(task,expected_task_revision,'Task')
            if task['lifecycle'] not in ('DRAFT','PREFLIGHT','WAITING_APPROVAL'):
                raise InvalidTransition('D1 can only revise non-approved task drafts')
            next_rev = task['current_contract_revision'] + 1
            cn.execute('''INSERT INTO contract_revisions
                (task_id,revision,content_json,content_sha256,created_at) VALUES(?,?,?,?,?)''',
                (task_id,next_rev,encoded,digest(content),utc_now(self.store.clock)))
            new_state = 'PREFLIGHT' if task['lifecycle'] != 'DRAFT' else 'DRAFT'
            cn.execute('''UPDATE tasks SET current_contract_revision=?,lifecycle=?,revision=revision+1,
                updated_at=? WHERE id=?''',
                (next_rev,new_state,utc_now(self.store.clock),task_id))
            return dict(task_id=task_id,contract_revision=next_rev,contract_hash=digest(content),
                        lifecycle=new_state,revision=expected_task_revision+1,approved=False)
        return self.store.mutate('contract.revise',payload,run,request_key=request_key,entity_id=task_id)

    def reference_unverified_approval(self, task_id: str, source: str, *, request_key: str | None = None) -> dict:
        """Persist an untrusted CLAIM only; it can NEVER activate product-code writes."""
        source = require_key(source, 'claimed_source', 100)
        payload = dict(task_id=task_id,claimed_source=source)
        def run(cn):
            task = _expect(cn.execute('SELECT * FROM tasks WHERE id=? AND repo_id=?',
                                      (task_id,self.store.repo_id)).fetchone(),'Task',task_id)
            if task['lifecycle'] != 'WAITING_APPROVAL':
                raise InvalidTransition('Task is not waiting for approval')
            ref_id = _new_id('APR')
            cn.execute('''INSERT INTO approval_references
                (id,task_id,contract_revision,claimed_source,provenance_status,created_at)
                VALUES(?,?,?,?,?,?)''',
                (ref_id,task_id,task['current_contract_revision'],source,'UNVERIFIED',utc_now(self.store.clock)))
            return dict(reference_id=ref_id,provenance_status='UNVERIFIED',approved=False)
        return self.store.mutate('approval.reference_unverified',payload,run,
                                 request_key=request_key,entity_id=task_id)

    def open_session(self, provider: str, *, task_id: str | None = None,
                     external_ref: str | None = None, request_key: str | None = None) -> dict:
        if provider not in PROVIDERS:
            raise StoreError('Unsupported session provider')
        if external_ref is not None:
            require_key(external_ref, 'external_ref', 300)
        payload = dict(provider=provider,task_id=task_id,external_ref=external_ref)
        def run(cn):
            if task_id:
                _expect(cn.execute('SELECT id FROM tasks WHERE id=? AND repo_id=?',
                                   (task_id,self.store.repo_id)).fetchone(),'Task',task_id)
            sid, ts = _new_id('S'), utc_now(self.store.clock)
            cn.execute('''INSERT INTO sessions
                (id,repo_id,task_id,provider,external_ref,lifecycle,heartbeat_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?)''',
                (sid,self.store.repo_id,task_id,provider,external_ref,'ACTIVE',ts,ts))
            return dict(session_id=sid,task_id=task_id,lifecycle='ACTIVE',revision=1,
                        write_authorized=False)
        return self.store.mutate('session.open',payload,run,request_key=request_key,entity_id=task_id)

    def transition_session(self, session_id: str, expected_revision: int,
                           to_state: str, *, request_key: str | None = None) -> dict:
        payload = dict(session_id=session_id,expected_revision=expected_revision,to_state=to_state)
        def run(cn):
            session = _expect(cn.execute('SELECT * FROM sessions WHERE id=? AND repo_id=?',
                                        (session_id,self.store.repo_id)).fetchone(),'Session',session_id)
            _version(session,expected_revision,'Session')
            check_transition('session',session['lifecycle'],to_state)
            cn.execute('UPDATE sessions SET lifecycle=?,revision=revision+1,updated_at=? WHERE id=?',
                       (to_state,utc_now(self.store.clock),session_id))
            return dict(session_id=session_id,lifecycle=to_state,revision=expected_revision+1)
        return self.store.mutate('session.transition',payload,run,request_key=request_key,entity_id=session_id)

    def create_work_item(self, task_id: str, title: str, dependencies: list[str] | None = None,
                         *, plan_revision: int = 0,request_key: str | None = None) -> dict:
        title = require_key(title.strip(),'work title',180)
        dependencies = dependencies or []
        if len(set(dependencies)) != len(dependencies):
            raise StoreError('Duplicate work dependency')
        payload = dict(task_id=task_id,title=title,dependencies=dependencies,plan_revision=plan_revision)
        def run(cn):
            _expect(cn.execute('SELECT * FROM tasks WHERE id=? AND repo_id=?',
                               (task_id,self.store.repo_id)).fetchone(),'Task',task_id)
            for dep in dependencies:
                _expect(cn.execute('SELECT id FROM work_items WHERE id=? AND task_id=?',
                                   (dep,task_id)).fetchone(),'Dependency',dep)
            wid, ts = _new_id('W'), utc_now(self.store.clock)
            cn.execute('''INSERT INTO work_items
                (id,task_id,title,lifecycle,plan_revision,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)''', (wid,task_id,title,'PLANNED',plan_revision,ts,ts))
            for dep in dependencies:
                cn.execute('INSERT INTO work_dependencies(work_id,depends_on_id) VALUES(?,?)',(wid,dep))
            return dict(work_item_id=wid,lifecycle='PLANNED',revision=1,dependencies=dependencies)
        return self.store.mutate('work.create',payload,run,request_key=request_key,entity_id=task_id)

    def add_work_dependency(self, work_item_id: str, depends_on_id: str,
                            *, request_key: str | None = None) -> dict:
        payload = dict(work_item_id=work_item_id,depends_on_id=depends_on_id)
        def run(cn):
            a = _expect(cn.execute('SELECT * FROM work_items WHERE id=?',(work_item_id,)).fetchone(),
                        'Work item',work_item_id)
            b = _expect(cn.execute('SELECT * FROM work_items WHERE id=?',(depends_on_id,)).fetchone(),
                        'Dependency',depends_on_id)
            if a['task_id'] != b['task_id'] or work_item_id == depends_on_id:
                raise StoreError('Work dependencies must connect different items of same task')
            if a['lifecycle'] not in ('PLANNED','READY'):
                raise InvalidTransition('Work item is no longer safe to re-plan')
            # If B already depends on A, A -> B creates a cycle.
            descendants = cn.execute('''WITH RECURSIVE graph(id) AS (
               SELECT depends_on_id FROM work_dependencies WHERE work_id=?
               UNION SELECT d.depends_on_id FROM work_dependencies d JOIN graph g ON d.work_id=g.id
               ) SELECT 1 FROM graph WHERE id=? LIMIT 1''',(depends_on_id,work_item_id)).fetchone()
            if descendants:
                raise StoreError('Dependency cycle would be created')
            cn.execute('INSERT OR IGNORE INTO work_dependencies(work_id,depends_on_id) VALUES(?,?)',
                       (work_item_id,depends_on_id))
            if a['lifecycle'] == 'READY':
                cn.execute("UPDATE work_items SET lifecycle='PLANNED', revision=revision+1, updated_at=? WHERE id=?",
                           (utc_now(self.store.clock),work_item_id))
            return dict(work_item_id=work_item_id,depends_on_id=depends_on_id,added=True)
        return self.store.mutate('work.add_dependency',payload,run,request_key=request_key,entity_id=work_item_id)

    def transition_work(self, work_item_id: str, expected_revision: int,
                        to_state: str, *, request_key: str | None = None) -> dict:
        payload = dict(work_item_id=work_item_id,expected_revision=expected_revision,to_state=to_state)
        def run(cn):
            work = _expect(cn.execute('''SELECT w.* FROM work_items w JOIN tasks t ON t.id=w.task_id
                                      WHERE w.id=? AND t.repo_id=?''',
                                      (work_item_id,self.store.repo_id)).fetchone(),'Work item',work_item_id)
            _version(work,expected_revision,'Work item')
            check_transition('work',work['lifecycle'],to_state)
            if to_state == 'READY':
                unready = cn.execute('''SELECT d.depends_on_id FROM work_dependencies d
                    JOIN work_items prereq ON prereq.id=d.depends_on_id
                    WHERE d.work_id=? AND prereq.lifecycle!='COMPLETED' LIMIT 1''',
                    (work_item_id,)).fetchone()
                if unready:
                    raise InvalidTransition('Prerequisite is not completed: '+unready['depends_on_id'])
            cn.execute('UPDATE work_items SET lifecycle=?,revision=revision+1,updated_at=? WHERE id=?',
                       (to_state,utc_now(self.store.clock),work_item_id))
            return dict(work_item_id=work_item_id,lifecycle=to_state,revision=expected_revision+1)
        return self.store.mutate('work.transition',payload,run,request_key=request_key,entity_id=work_item_id)

    def propose_policy(self, policy_key: str, content: dict, expected_revision: int = 0,
                       *, request_key: str | None = None) -> dict:
        policy_key = require_key(policy_key,'policy key',100)
        encoded = _validate_document(content)
        payload = dict(policy_key=policy_key, content=content,expected_revision=expected_revision)
        def run(cn):
            latest = cn.execute('''SELECT MAX(revision) AS revision FROM policy_versions
                WHERE repo_id=? AND policy_key=?''',(self.store.repo_id,policy_key)).fetchone()['revision'] or 0
            if latest != expected_revision:
                raise ConflictError(f'Policy revision changed: expected {expected_revision}, found {latest}')
            revision = latest + 1
            policy_id = _new_id('POL')
            cn.execute('''INSERT INTO policy_versions
                (id,repo_id,policy_key,revision,content_json,content_sha256,status,created_at)
                VALUES(?,?,?,?,?,?,?,?)''',
                (policy_id,self.store.repo_id,policy_key,revision,encoded,digest(content),'PROPOSED',
                 utc_now(self.store.clock)))
            return dict(policy_id=policy_id,policy_key=policy_key,revision=revision,
                        sha256=digest(content),status='PROPOSED',active=False)
        return self.store.mutate('policy.propose',payload,run,request_key=request_key,entity_id=policy_key)

    def register_artifact(self, kind: str, artifact_key: str, sha256: str,
                          expected_revision: int = 0, *, request_key: str | None = None) -> dict:
        kind=require_key(kind,'artifact kind',60)
        artifact_key=require_key(artifact_key,'artifact key',256)
        if not HEX64.fullmatch(sha256):
            raise StoreError('Artifact hash must be lowercase SHA-256 hex')
        payload=dict(kind=kind,key=artifact_key,sha256=sha256,expected_revision=expected_revision)
        def run(cn):
            current = cn.execute('''SELECT revision,content_sha256 FROM artifacts
                WHERE repo_id=? AND kind=? AND artifact_key=?''',
                (self.store.repo_id,kind,artifact_key)).fetchone()
            revision=current['revision'] if current else 0
            if expected_revision!=revision:
                raise ConflictError('Artifact version changed')
            if current and current['content_sha256']==sha256:
                return dict(kind=kind, key=artifact_key, revision=revision, changed=False)
            new_revision=revision+1
            cn.execute('''INSERT INTO artifacts
                (repo_id,kind,artifact_key,revision,content_sha256,updated_at) VALUES(?,?,?,?,?,?)
                ON CONFLICT(repo_id,kind,artifact_key) DO UPDATE SET
                  revision=excluded.revision,content_sha256=excluded.content_sha256,
                  updated_at=excluded.updated_at''',
                (self.store.repo_id,kind,artifact_key,new_revision,sha256,utc_now(self.store.clock)))
            return dict(kind=kind,key=artifact_key,revision=new_revision,changed=True)
        return self.store.mutate('artifact.register',payload,run,request_key=request_key,
                                 entity_id=artifact_key)

    def record_unverified_evidence(self, task_id: str, kind: str, reported_status: str,
                                   dependencies: list[tuple[str,str]], *, work_item_id: str | None = None,
                                   metadata: dict | None = None, request_key: str | None = None) -> dict:
        """Append evidence metadata; PASS is only a reported, untrusted status in D1."""
        kind=require_key(kind,'evidence kind',60)
        if reported_status not in {'PASS','FAIL','NOT_RUN','BLOCKED','UNKNOWN'}:
            raise StoreError('Invalid evidence status')
        metadata=metadata or {}
        _validate_document(metadata or {'empty':True})
        payload=dict(task_id=task_id,kind=kind,status=reported_status,dependencies=dependencies,
                     work_item_id=work_item_id,metadata=metadata)
        def run(cn):
            _expect(cn.execute('SELECT 1 FROM tasks WHERE id=? AND repo_id=?',
                               (task_id,self.store.repo_id)).fetchone(),'Task',task_id)
            if work_item_id:
                _expect(cn.execute('SELECT 1 FROM work_items WHERE id=? AND task_id=?',
                                   (work_item_id,task_id)).fetchone(),'Work item',work_item_id)
            rows=[]
            for dependency_kind,dependency_key in dependencies:
                row=_expect(cn.execute('''SELECT revision,content_sha256 FROM artifacts
                  WHERE repo_id=? AND kind=? AND artifact_key=?''',
                  (self.store.repo_id,dependency_kind,dependency_key)).fetchone(),
                  'Artifact',dependency_key)
                rows.append((dependency_kind,dependency_key,row['revision'],row['content_sha256']))
            evid=_new_id('EV')
            cn.execute('''INSERT INTO evidence
              (id,task_id,work_item_id,kind,reported_status,attestation,metadata_json,recorded_at)
              VALUES(?,?,?,?,?,?,?,?)''',
              (evid,task_id,work_item_id,kind,reported_status,'UNVERIFIED',canonical_json(metadata),
               utc_now(self.store.clock)))
            for dkind,dkey,rev,sha in rows:
                cn.execute('''INSERT INTO evidence_dependencies
                   (evidence_id,repo_id,kind,artifact_key,revision,content_sha256)
                   VALUES(?,?,?,?,?,?)''',(evid,self.store.repo_id,dkind,dkey,rev,sha))
            return dict(evidence_id=evid,reported_status=reported_status,
                        attestation='UNVERIFIED',sufficient_for_DoD=False,
                        dependencies=len(rows))
        return self.store.mutate('evidence.record_unverified',payload,run,
                                 request_key=request_key,entity_id=task_id)

    def evidence_freshness(self, evidence_id: str) -> dict:
        with closing(self.store.connect(read_only=True)) as cn:
            ev=_expect(cn.execute('''SELECT e.* FROM evidence e JOIN tasks t ON t.id=e.task_id
                  WHERE e.id=? AND t.repo_id=?''',
                  (evidence_id,self.store.repo_id)).fetchone(),'Evidence',evidence_id)
            deps=list(cn.execute('''SELECT d.*, a.revision AS current_rev,
                       a.content_sha256 AS current_hash FROM evidence_dependencies d
                       LEFT JOIN artifacts a ON a.repo_id=d.repo_id AND a.kind=d.kind
                            AND a.artifact_key=d.artifact_key WHERE d.evidence_id=?''',(evidence_id,)))
            stale=[f'{r["kind"]}:{r["artifact_key"]}' for r in deps if
                   r['current_rev']!=r['revision'] or r['current_hash']!=r['content_sha256']]
            return dict(evidence_id=evidence_id,fresh=not stale,stale_dependencies=stale,
                        reported_status=ev['reported_status'],attestation=ev['attestation'],
                        sufficient_for_DoD=False)

    def reserve_intent(self, session_id: str, resource_key: str, *, ttl_seconds: int = 120,
                       request_key: str | None = None) -> dict:
        """Coordination metadata ONLY: NEVER a write authorization or lease grant."""
        resource_key = require_key(resource_key,'resource key',300)
        if not resource_key.startswith(('file:','contract:','git:','test:')):
            raise StoreError('Resource key must specify its type')
        if not isinstance(ttl_seconds,int) or not 1 <= ttl_seconds <= 3600:
            raise StoreError('Invalid intent TTL')
        payload=dict(session_id=session_id,resource_key=resource_key,ttl_seconds=ttl_seconds)
        def run(cn):
            session=_expect(cn.execute('SELECT * FROM sessions WHERE id=? AND repo_id=?',
                                       (session_id,self.store.repo_id)).fetchone(),'Session',session_id)
            if session['lifecycle'] != 'ACTIVE' or not session['task_id']:
                raise InvalidTransition('Session must be ACTIVE and bound to task')
            existing=cn.execute('SELECT * FROM resource_intents WHERE repo_id=? AND resource_key=?',
                                (self.store.repo_id,resource_key)).fetchone()
            if existing and existing['state'] != 'RELEASED':
                if existing['holder_session'] != session_id:
                    raise ConflictError('Resource is reserved; expired intents require explicit recovery')
                raise ConflictError('Intent already held; release/reacquire requires coordination')
            generation=1+(existing['generation'] if existing else 0)
            expiry=int(dt.datetime.now(dt.timezone.utc).timestamp())+ttl_seconds
            cn.execute('''INSERT INTO resource_intents
                (repo_id,resource_key,holder_session,task_id,generation,state,expires_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(repo_id,resource_key) DO UPDATE SET
                  holder_session=excluded.holder_session,task_id=excluded.task_id,
                  generation=excluded.generation,state=excluded.state,
                  expires_at=excluded.expires_at,updated_at=excluded.updated_at''',
                (self.store.repo_id,resource_key,session_id,session['task_id'],generation,
                 'ACTIVE',expiry,utc_now(self.store.clock)))
            return dict(resource_key=resource_key,generation=generation,state='ACTIVE',
                        write_authorized=False)
        return self.store.mutate('intent.reserve',payload,run,request_key=request_key,
                                 entity_id=resource_key)

    def release_intent(self, session_id: str, resource_key: str, generation: int,
                       *, request_key: str | None = None) -> dict:
        payload=dict(session_id=session_id,resource_key=resource_key,generation=generation)
        def run(cn):
            existing=_expect(cn.execute('SELECT * FROM resource_intents WHERE repo_id=? AND resource_key=?',
                                        (self.store.repo_id,resource_key)).fetchone(),
                             'Resource intent',resource_key)
            if existing['holder_session']!=session_id or existing['generation']!=generation:
                raise ConflictError('Stale session/generation cannot release current resource')
            if existing['state']!='ACTIVE':
                raise InvalidTransition('Resource intent not active')
            cn.execute('''UPDATE resource_intents SET state='RELEASED',expires_at=NULL,updated_at=?
                WHERE repo_id=? AND resource_key=?''',
                (utc_now(self.store.clock),self.store.repo_id,resource_key))
            return dict(resource_key=resource_key,generation=generation,state='RELEASED')
        return self.store.mutate('intent.release',payload,run,request_key=request_key,
                                 entity_id=resource_key)

    def approval_or_write_capability(self) -> None:
        raise GateNotImplemented('D1 cannot issue trusted approvals or authorize product-code writes; D2 required')

    def doctor(self) -> dict:
        return self.store.doctor()

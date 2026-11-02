"""Immutable, versioned UNTRUSTED engineering artifacts stored in canonical SQLite.

This layer is not a trust root. Everything writable by this CLI may be tampered
with by a same-UID agent. It never transitions tasks to APPROVED or VERIFIED.
"""
from __future__ import annotations
from contextlib import closing
import json
import uuid
from typing import Any

from agentflow_core import LocalCoordinator, ConflictError, StoreError
from agentflow_core.db import canonical_json, digest, require_key, utc_now

ALLOWED_KINDS = frozenset({
    'RIG_BRIEF','RIG_GAPS','RIG_SCENARIOS','RIG_DECISIONS','RIG_IMPACT',
    'TECHNICAL_PLAN','WORK_GRAPH','ENGINEERING_PROFILE','DOMAIN_PROFILE',
    'PROGRESS','CHANGE_REPORT','CHECK_REPORT','REVIEW_REPORT','HANDOFF',
    'MODEL_CATALOG','MODEL_ADVICE','ACCEPTANCE_REPORT','UPGRADE_PLAN',
    'SI_POLICY_EXCEPTION','SI_EVIDENCE_GRAPH','SI_ACTION_PROPOSAL',
})

class WorkflowRecords:
    def __init__(self, repo, state_home=None, *, initialize=True):
        self.core = LocalCoordinator(repo,state_home,initialize=initialize)
        self.store = self.core.store

    def _scope(self, task_id: str|None) -> str:
        return task_id or 'REPOSITORY'

    def put(self, kind: str, content: dict, *, task_id: str|None=None,
            key: str='primary', expected_revision: int=0,
            status: str='UNTRUSTED_DRAFT', request_key: str|None=None) -> dict:
        if kind not in ALLOWED_KINDS:
            raise StoreError('Unrecognized workflow document kind')
        key=require_key(key,'document key',120)
        if not isinstance(content,dict) or not content:
            raise StoreError('Document must be a nonempty JSON object')
        payload_str=canonical_json(content)
        if len(payload_str.encode('utf-8'))>256*1024:
            raise StoreError('Document exceeds 256 KiB')
        if status not in ('UNTRUSTED_DRAFT','OBSERVED','UNVERIFIED_REPORT'):
            raise StoreError('Untrusted workflow records cannot assert privileged status')
        if isinstance(expected_revision,bool) or not isinstance(expected_revision,int) or expected_revision<0:
            raise StoreError('Invalid expected revision')
        payload={'kind':kind,'content':content,'task_id':task_id,'key':key,
                 'status':status,'expected_revision':expected_revision}
        scope=self._scope(task_id)
        def run(cn):
            if task_id and not cn.execute('SELECT id FROM tasks WHERE id=? AND repo_id=?',
                          (task_id,self.store.repo_id)).fetchone():
                raise StoreError('Unknown task in repository')
            row=cn.execute('''SELECT MAX(revision) AS rev FROM workflow_documents
                         WHERE repo_id=? AND scope_key=? AND kind=? AND doc_key=?''',
                         (self.store.repo_id,scope,kind,key)).fetchone()
            current=row['rev'] or 0
            if current!=expected_revision:
                raise ConflictError(f'Document revision conflict: expected {expected_revision}, found {current}')
            rev=current+1; record_id='DOC-'+uuid.uuid4().hex[:20]
            cn.execute('''INSERT INTO workflow_documents
                (id,repo_id,scope_key,kind,doc_key,revision,content_json,content_sha256,trust_status,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (record_id,self.store.repo_id,scope,kind,key,rev,payload_str,
                 digest(content),status,utc_now(self.store.clock)))
            return {'record_id':record_id,'kind':kind,'key':key,'revision':rev,
                    'sha256':digest(content),'status':status,'trusted':False}
        return self.store.mutate('workflow.document.put',payload,run,request_key=request_key,
                                 entity_id=task_id or kind)

    def latest(self, kind: str, *, task_id: str|None=None, key: str='primary') -> dict|None:
        if kind not in ALLOWED_KINDS:
            raise StoreError('Unrecognized workflow document kind')
        with closing(self.store.connect(read_only=True)) as cn:
            row=cn.execute('''SELECT * FROM workflow_documents WHERE repo_id=? AND
                  scope_key=? AND kind=? AND doc_key=? ORDER BY revision DESC LIMIT 1''',
                  (self.store.repo_id,self._scope(task_id),kind,key)).fetchone()
            if not row: return None
            return {'record_id':row['id'],'kind':row['kind'],'key':row['doc_key'],
                    'revision':row['revision'],'content':json.loads(row['content_json']),
                    'sha256':row['content_sha256'],'status':row['trust_status'],'trusted':False}

    def list_latest(self, *, task_id: str|None=None) -> list[dict]:
        scope=self._scope(task_id)
        with closing(self.store.connect(read_only=True)) as cn:
            rows=cn.execute('''SELECT kind,doc_key,MAX(revision) AS revision FROM workflow_documents
                        WHERE repo_id=? AND scope_key=? GROUP BY kind,doc_key
                        ORDER BY kind,doc_key''',(self.store.repo_id,scope))
            return [dict(row) for row in rows]

    def alias(self, task_id: str, alias_norm: str, request_key: str|None=None) -> dict:
        alias_norm=require_key(alias_norm,'alias_norm',180)
        payload={'task_id':task_id,'alias_norm':alias_norm}
        def run(cn):
            if not cn.execute('SELECT 1 FROM tasks WHERE id=? AND repo_id=?',
                      (task_id,self.store.repo_id)).fetchone():
                raise StoreError('Unknown task')
            row=cn.execute('SELECT task_id FROM task_aliases WHERE repo_id=? AND alias_norm=?',
                           (self.store.repo_id,alias_norm)).fetchone()
            if row and row['task_id'] != task_id:
                raise ConflictError('Alias belongs to another task')
            cn.execute('''INSERT OR IGNORE INTO task_aliases(repo_id,alias_norm,task_id,created_at)
                        VALUES(?,?,?,?)''',(self.store.repo_id,alias_norm,task_id,utc_now(self.store.clock)))
            return {'alias':alias_norm,'task_id':task_id,'created':not bool(row)}
        return self.store.mutate('workflow.alias.add',payload,run,request_key=request_key,entity_id=task_id)

    def aliases_for(self, task_id: str)->list[str]:
        with closing(self.store.connect(read_only=True)) as cn:
            return [row['alias_norm'] for row in cn.execute(
                'SELECT alias_norm FROM task_aliases WHERE repo_id=? AND task_id=?',
                (self.store.repo_id,task_id))]

    def create_preflight(self, title: str, request: str, brief: dict, alias_norm: str) -> dict:
        """One draft intake transaction: task, request, brief and alias or nothing."""
        title=require_key(title.strip(),'title',180)
        request=require_key(request.strip(),'request',20000)
        alias_norm=require_key(alias_norm,'alias_norm',180)
        if not isinstance(brief,dict) or not brief or len(canonical_json(brief).encode('utf-8'))>256*1024:
            raise StoreError('Invalid preflight brief')
        payload={'title':title,'request':request,'brief':brief,'alias_norm':alias_norm}
        def run(cn):
            if cn.execute('SELECT 1 FROM task_aliases WHERE repo_id=? AND alias_norm=?',
                          (self.store.repo_id,alias_norm)).fetchone():
                raise ConflictError('Alias belongs to another task; refresh task lookup')
            task_id='T-'+uuid.uuid4().hex[:20];ts=utc_now(self.store.clock)
            document={'source_request':request,'purpose':'IMPLEMENTATION'}
            cn.execute('''INSERT INTO tasks
                (id,repo_id,title,kind,lifecycle,revision,current_contract_revision,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)''',
                (task_id,self.store.repo_id,title,'IMPLEMENTATION','PREFLIGHT',2,1,ts,ts))
            cn.execute('''INSERT INTO contract_revisions
                (task_id,revision,content_json,content_sha256,created_at) VALUES(?,?,?,?,?)''',
                (task_id,1,canonical_json(document),digest(document),ts))
            cn.execute('''INSERT INTO workflow_documents
                (id,repo_id,scope_key,kind,doc_key,revision,content_json,content_sha256,trust_status,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)''',
                ('DOC-'+uuid.uuid4().hex[:20],self.store.repo_id,task_id,'RIG_BRIEF','primary',1,
                 canonical_json(brief),digest(brief),'OBSERVED',ts))
            cn.execute('INSERT INTO task_aliases(repo_id,alias_norm,task_id,created_at) VALUES(?,?,?,?)',
                       (self.store.repo_id,alias_norm,task_id,ts))
            return {'task_id':task_id,'lifecycle':'PREFLIGHT','revision':2,'contract_revision':1,
                    'contract_hash':digest(document),'approved':False}
        return self.store.mutate('workflow.intake.create',payload,run)

    def note_capability(self, provider: str, version: str, observation: dict, *,
                        request_key: str|None=None)->dict:
        # OBSERVED != certified; cannot update any permission decision.
        if provider not in {'codex_cli','codex_desktop','claude_cli','claude_desktop'}:
            raise StoreError('Unknown provider')
        version=require_key(version,'version',100)
        if not isinstance(observation,dict) or len(canonical_json(observation))>30000:
            raise StoreError('Invalid observation')
        payload={'provider':provider,'version':version,'observation':observation}
        def run(cn):
            row_id='CAP-'+uuid.uuid4().hex[:20]
            cn.execute('''INSERT INTO adapter_observations
               (id,repo_id,provider,app_version,observed_json,capability_status,created_at)
               VALUES(?,?,?,?,?,?,?)''',
               (row_id,self.store.repo_id,provider,version,canonical_json(observation),
                'NOT_CERTIFIED',utc_now(self.store.clock)))
            return {'observation_id':row_id,'provider':provider,
                    'capability_status':'NOT_CERTIFIED','enforced':False}
        return self.store.mutate('workflow.capability.observe',payload,run,request_key=request_key)

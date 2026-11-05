"""Pending scope drafts never replace active scope or authenticate approval."""
import json
import uuid
from contextlib import closing

from agentflow_core import ConflictError, StoreError
from agentflow_core.db import canonical_json, digest, utc_now
from .records import WorkflowRecords
from . import coordination, implementation, sources, work
from .rig import analyze_readiness, normalize_contract

KIND='CONTRACT_PROPOSAL'
KEY='pending'


def _draft(row):
    value=row.get('content') if isinstance(row,dict) else None
    if (not isinstance(value,dict) or value.get('state') not in ('PENDING','DECISION_REPORTED','REJECTED')
            or not isinstance(value.get('contract'),dict) or not value['contract']
            or type(value.get('base_revision')) is not int or value['base_revision']<1
            or not isinstance(value.get('base_sha256'),str) or len(value['base_sha256'])!=64
            or any(c not in '0123456789abcdef' for c in value['base_sha256'])
            or value.get('owner') is not None and not isinstance(value['owner'],str)):
        raise StoreError('Malformed pending proposal record; reconcile without replacing active scope')
    return value


def view(records, task):
    row=records.latest(KIND,task_id=task,key=KEY)
    if not row:return None
    draft=_draft(row);active=records.core.contract_revision(task)
    return {'proposal_revision':row['revision'],'state':draft.get('state'),
            'objective':str(draft.get('contract',{}).get('objective',''))[:300],
            'active_base_current':draft.get('base_revision')==active['revision'] and draft.get('base_sha256')==active['sha256'],
            'trusted':False,'write_authorized':False}


def read(repo,home,topic):
    records=WorkflowRecords(repo,home,initialize=False);task=work.resolve(records,topic)
    row=records.latest(KIND,task_id=task,key=KEY)
    if not row:raise StoreError('No saved proposal for this specific task')
    draft=_draft(row)
    return {'status':'PROPOSAL_READ',**view(records,task),'proposal':draft['contract'],
            'read_only':True,
            'next_command':['work','accept-proposal',topic,'--proposal-revision',str(row['revision']),
                            '--source-ref','ACTUAL_USER_DECISION_SOURCE'] if draft['state']=='PENDING' else None,
            'next_action':('Compare this exact proposal, paths and checks to the actual USER decision. If it was approved, use next_command with that real decision source; do not recreate its scope under a new title or ask again. If not approved, keep it pending and stay within active authority.' if draft['state']=='PENDING' else
                           'This proposal was already decided; do not replay it or infer new permission. Read current USER scope and active decision for further work.')}


def reject(repo,home,topic,proposal_revision,source):
    if not isinstance(source,str) or len(source.strip())<6 or source.strip().casefold() in ('rejected','unknown','todo'):
        raise StoreError('Reject needs the actual current USER rejection source')
    records=WorkflowRecords(repo,home,initialize=False);task=work.resolve(records,topic)
    row=records.latest(KIND,task_id=task,key=KEY)
    if type(proposal_revision) is not int or not row or row['revision']!=proposal_revision or _draft(row)['state']!='PENDING':
        raise ConflictError('Pending proposal changed/consumed; do not reject a different draft')
    draft=_draft(row)
    if draft.get('owner') and draft['owner']!=coordination.identity():
        raise ConflictError('Proposal belongs to another chat; do not carry its decision')
    saved=records.put(KIND,{**draft,'state':'REJECTED','source':source},task_id=task,key=KEY,
                      expected_revision=proposal_revision,status='UNVERIFIED_REPORT')
    return {'status':'PROPOSAL_REJECTED','proposal_revision':saved['revision'],'active_contract_unchanged':True,
            'read_only_product':True,'write_authorized':False,
            'next_action':'Rejection recorded; active contract/decision/receipt were not changed. Continue only independently authorized work. No new permission was created.'}


def pending_overlap(records, contract):
    """A path overlap is a reconciliation hint, never semantic approval."""
    new={(r['root'],p) for r in sources.registry(contract,records.store.repo) for p in r['write_paths']}
    with closing(records.store.connect(read_only=True)) as cn:
        rows=cn.execute('''SELECT d.scope_key,d.content_json,t.title FROM workflow_documents d
            JOIN tasks t ON t.id=d.scope_key AND t.repo_id=d.repo_id
            WHERE d.repo_id=? AND d.kind=? AND d.doc_key=? AND NOT EXISTS
            (SELECT 1 FROM workflow_documents n WHERE n.repo_id=d.repo_id AND n.scope_key=d.scope_key
             AND n.kind=d.kind AND n.doc_key=d.doc_key AND n.revision>d.revision)
            ORDER BY d.created_at DESC LIMIT 201''',(records.store.repo_id,KIND,KEY)).fetchall()
    if len(rows)>200:raise StoreError('Too many pending-scope records; reconcile before creating another task')
    for row in rows:
        draft=_draft({'content':json.loads(row['content_json'])})
        if draft.get('state')!='PENDING':continue
        active=records.core.contract_revision(row['scope_key'])['content']
        observed=set()
        for spec in (active,draft['contract']):
            if spec.get('repositories'):
                observed|={(r['root'],p) for r in sources.registry(spec,records.store.repo) for p in r['write_paths']}
        if new&observed:
            return {'status':'BLOCKED','reason_code':'PENDING_SCOPE_OVERLAP',
                    'reasons':['New task overlaps existing work with a pending proposal; reconcile the actual USER decision before creating another scope'],
                    'next_command':['work','proposal',row['title']],
                    'next_action':'Read the referenced saved proposal. Existing approval may suffice for that exact proposal; do not reconstruct paths from memory or request approval again. No scope was activated.',
                    'write_authorized':False}
    return None


def stage(repo, home, topic, contract, expected_revision=0):
    records=WorkflowRecords(repo,home,initialize=False);task=work.resolve(records,topic)
    readiness=analyze_readiness(contract)
    if readiness['status']!='READY_FOR_HUMAN_REVIEW':
        raise StoreError('Task Contract is not structurally ready: '+', '.join(readiness['blockers']))
    contract,_=normalize_contract(contract)
    implementation.policy(contract,repo)
    if contract.get('repositories'):sources.registry(contract,repo)
    active=records.core.contract_revision(task)
    draft={'state':'PENDING','base_sha256':active['sha256'],'base_revision':active['revision'],
           'contract':contract,'owner':coordination.identity()}
    saved=records.put(KIND,draft,task_id=task,key=KEY,expected_revision=expected_revision)
    readback=records.latest(KIND,task_id=task,key=KEY)
    if readback['sha256']!=saved['sha256'] or records.core.contract_revision(task)!=active:
        raise ConflictError('Proposal/base changed during save; reread and reconcile')
    return {'status':'PROPOSAL_PENDING','proposal_revision':saved['revision'],
            'active_contract_unchanged':True,'readiness':readiness,
            'trusted_approval':False,'write_authorized':False,
            'next_action':'Explain the actual extra decision. Continue only independent approved work after recheck; pause dependent work. No new scope is approved. After an actual USER decision use work accept-proposal with this proposal_revision.'}


def accept(repo, home, topic, proposal_revision, source):
    if not isinstance(source,str) or len(source.strip())<6 or source.strip().casefold() in ('approved','unknown','todo'):
        raise StoreError('Accept needs the actual current USER decision source, not an inferred approval')
    if type(proposal_revision) is not int or proposal_revision<1:
        raise StoreError('Use the observed pending proposal_revision')
    records=WorkflowRecords(repo,home,initialize=False);task=work.resolve(records,topic)
    pending=records.latest(KIND,task_id=task,key=KEY)
    if not pending or pending['revision']!=proposal_revision or _draft(pending)['state']!='PENDING':
        raise ConflictError('Pending proposal changed/consumed; reread before recording a decision')
    draft=_draft(pending);owner=coordination.identity()
    if draft.get('owner') and draft['owner']!=owner:
        raise ConflictError('Proposal belongs to another chat; do not carry its approval')
    held=coordination.writer(records)
    if held.get('held'):
        raise ConflictError('Pause/handoff the active receipt writer before changing scope; do not take over')
    contract=draft['contract']
    readiness=analyze_readiness(contract)
    if readiness['status']!='READY_FOR_HUMAN_REVIEW':
        raise StoreError('Stored proposal is no longer structurally ready: '+', '.join(readiness['blockers']))
    # A new boundary needs complete explicit observations, not guessed legacy files.
    sources.capture(contract,repo);implementation.policy(contract,repo)
    if contract.get('work_type') not in ('BUG','FEATURE','MAINTENANCE'):
        raise StoreError('Accepted implementation needs an explicit work_type')
    for field in ('preserve','verification_strategy'):
        if not isinstance(contract.get(field),list) or not contract[field] or any(not isinstance(x,str) or not x.strip() for x in contract[field]):
            raise StoreError('Accepted implementation needs '+field)
    artifacts=work._artifact_checks(repo,home,contract)
    if artifacts['status']!='CLEAR':raise StoreError('Resolve artifacts before accepting new scope')
    previous=records.latest('PROGRESS',task_id=task)
    expected_progress=previous['revision'] if previous else 0
    def activate(cn):
        current=cn.execute('SELECT * FROM tasks WHERE id=? AND repo_id=?',(task,records.store.repo_id)).fetchone()
        row=cn.execute('SELECT * FROM workflow_documents WHERE repo_id=? AND scope_key=? AND kind=? AND doc_key=? ORDER BY revision DESC LIMIT 1',
            (records.store.repo_id,task,KIND,KEY)).fetchone()
        if not current:raise ConflictError('Active task disappeared during proposal activation')
        active=cn.execute('SELECT content_sha256 FROM contract_revisions WHERE task_id=? AND revision=?',
            (task,current['current_contract_revision'])).fetchone()
        if (not row or not active or row['id']!=pending['record_id'] or row['content_sha256']!=pending['sha256']
                or current['current_contract_revision']!=draft['base_revision'] or active['content_sha256']!=draft['base_sha256']):
            raise ConflictError('Pending proposal or active contract changed; no decision was transferred')
        if current['lifecycle'] not in ('DRAFT','PREFLIGHT','WAITING_APPROVAL'):
            raise ConflictError('Active lifecycle requires reconciliation before contract change')
        rev=current['current_contract_revision']+1;stamp=utc_now(records.store.clock)
        cn.execute('INSERT INTO contract_revisions (task_id,revision,content_json,content_sha256,created_at) VALUES(?,?,?,?,?)',
            (task,rev,canonical_json(contract),digest(contract),stamp))
        cn.execute("UPDATE tasks SET current_contract_revision=?,lifecycle='WAITING_APPROVAL',revision=revision+1,updated_at=? WHERE id=?",
            (rev,stamp,task))
        consumed={**draft,'state':'DECISION_REPORTED','source':source,'activated_revision':rev}
        cn.execute('INSERT INTO workflow_documents (id,repo_id,scope_key,kind,doc_key,revision,content_json,content_sha256,trust_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
            ('DOC-'+uuid.uuid4().hex[:20],records.store.repo_id,task,KIND,KEY,proposal_revision+1,
             canonical_json(consumed),digest(consumed),'UNVERIFIED_REPORT',stamp))
        return {'revision':rev,'sha256':digest(contract)}
    activated=records.store.mutate('workflow.proposal.activate',{'task':task,'proposal_revision':proposal_revision,'source':source},activate,entity_id=task)
    # Fail closed if source/checkpoint changed after activation. The previous
    # decision cannot match the new contract; no automatic recovery/reapproval.
    checked=work.checkpoint(repo,home,task,{'contract_sha256':activated['sha256'],
        'expected_revision':expected_progress,'decision':{'choice':'APPROVED','source':source},
        'phase':'IMPLEMENTING','summary':'Actual USER decision reported on the pending scope'})
    result={**checked,'proposal_revision':proposal_revision,'active_contract_unchanged':False,
            'next_action':'Decision is already saved/readback/rechecked: do not start or record it again. Inspect prepatch and actual USER scope, then patch. Immediately before actual tests run next_command to capture sources; fill finish_input_example with actual checks/results and send it to work finish TOPIC --data -. Old evidence/receipts stay historical.'}
    if checked['status']!='BLOCKED':
        snapshot=records.store.state_dir/'artifacts'/('test-sources-'+uuid.uuid4().hex+'.json')
        result['next_command']=['work','sources',topic,'--output',str(snapshot)]
        result['finish_input_example']['tested_sources_file']=str(snapshot)
        if contract['work_type']=='BUG':
            result['before_patch']='Exercise the actual original symptom before editing when feasible; preserve the observed failure. After repair recheck that symptom and record its real command/output as kind REPRODUCTION, separately from unrelated regressions. If unavailable, report the limitation; never invent baseline evidence.'
            result['finish_input_example']['checks'][0]['kind']='REPRODUCTION'
    return result

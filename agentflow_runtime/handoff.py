"""Bounded context packet assembled from canonical records, not chat transcripts."""
from __future__ import annotations
from contextlib import closing
from .records import WorkflowRecords
from .status import task_status
from .continuity import resume_brief, last_reported_verification

class HandoffBuilder:
    def __init__(self,repo,state_home=None,*,initialize=True):
        self.records=WorkflowRecords(repo,state_home,initialize=initialize)

    def packet(self,task_id:str)->dict:
        core=self.records.core
        task=core.get_task(task_id)
        contract=core.contract_revision(task_id)
        with closing(core.store.connect(read_only=True)) as cn:
            work=[dict(row) for row in cn.execute('''SELECT id,title,lifecycle,revision,plan_revision
                  FROM work_items WHERE task_id=? ORDER BY created_at LIMIT 80''',(task_id,))]
            sessions=[dict(row) for row in cn.execute('''SELECT id,provider,lifecycle,heartbeat_at
                   FROM sessions WHERE task_id=? ORDER BY updated_at DESC LIMIT 5''',(task_id,))]
            evid=[dict(row) for row in cn.execute('''SELECT id,kind,reported_status,attestation
                   FROM evidence WHERE task_id=? ORDER BY recorded_at DESC LIMIT 12''',(task_id,))]
        pieces={k:self.records.latest(k,task_id=task_id) for k in
                ('RIG_GAPS','RIG_DECISIONS','TECHNICAL_PLAN','WORK_GRAPH','PROGRESS','CHANGE_REPORT','REVIEW_REPORT')}
        compact={k:v['content'] for k,v in pieces.items() if v}
        freshness={}
        for kind in ('TECHNICAL_PLAN','WORK_GRAPH'):
            if kind not in compact:continue
            body=compact[kind]
            bound_hash=body.get('contract_sha256')
            bound_revision=body.get('contract_revision')
            freshness[kind]=('UNBOUND' if bound_hash is None else
                'CURRENT' if bound_hash==contract['sha256'] and
                bound_revision in (None,contract['revision']) else 'STALE')
        contract_content=contract['content']
        display=task_status(self.records,task_id,task=task,contract=contract,progress_record=pieces.get('PROGRESS'))
        verification=last_reported_verification(self.records,task_id,contract,pieces.get('PROGRESS'))
        return {'task':{'id':task_id,'title':task['title'],'state':task['lifecycle'],
                        'revision':task['revision'],'approved':False if not task['approved_contract_revision'] else
                          'CLAIMED_IN_DATABASE_NOT_TRUSTED_IN_THIS_RUNTIME'},
                'contract':{**contract_content,'revision':contract['revision'],'sha256':contract['sha256'],
                            'objective':contract['content'].get('objective',task['title']),
                            'acceptance':contract['content'].get('acceptance',[])},
                'sessions':sessions,'work_items':work,'recent_reported_evidence':evid,
                'relevant_artifacts':compact,
                'artifact_freshness':freshness,
                'status_view':display,
                'resume_brief':resume_brief(pieces.get('PROGRESS'),display,verification),
                'last_reported_verification':verification,
                'stale_artifacts':[k for k,v in freshness.items() if v=='STALE'],
                'next_action':('Revalidate stale or unbound plans against the current contract; review Git and pending gates before tool effects'
                               if any(v!='CURRENT' for v in freshness.values()) else
                               'Review current Git state and pending gates before any tool effects'),
                'permissions':{'code_write':False,'auto_approval':False,'provider_switch':False},
                'trust':'STATE_SNAPSHOT_UNVERIFIED_NOT_EXECUTION_AUTHORIZATION'}

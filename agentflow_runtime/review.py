"""Evidence-aware review and DoD candidates. NEVER self-attests actual quality."""
from __future__ import annotations
from contextlib import closing
import json
from .records import WorkflowRecords
from .status import task_status

class EvidenceReviewer:
    def __init__(self,repo,state_home=None):self.records=WorkflowRecords(repo,state_home)

    def evaluation(self,task_id:str)->dict:
        core=self.records.core
        task=core.get_task(task_id)
        contract=core.contract_revision(task_id)
        with closing(core.store.connect(read_only=True)) as cn:
            evidence=[dict(r) for r in cn.execute(
                'SELECT id,kind,reported_status,attestation,recorded_at FROM evidence WHERE task_id=? ORDER BY recorded_at DESC',
                (task_id,))]
            works=[dict(r) for r in cn.execute(
                'SELECT id,title,lifecycle FROM work_items WHERE task_id=?',(task_id,))]
        display=task_status(self.records,task_id,task=task,contract=contract)
        observations={r['id']:r for r in display['verification']['reported_evidence']}
        details=[{**r,'freshness':core.evidence_freshness(r['id']),
                  'freshness_scope':'REGISTERED_METADATA_ONLY_NOT_CURRENT_FILE_CONTENT',
                  'content_freshness':observations.get(r['id'],{}).get('content_freshness','UNKNOWN'),
                  'contract_binding':observations.get(r['id'],{}).get('contract_binding','UNKNOWN')}
                 for r in evidence[:120]]
        # D1/D2 evidence is unverified; no path from this runtime to PASS.
        return {'task_id':task_id,'contract_sha256':contract['sha256'],
                'task_state':task['lifecycle'],'work_items':works,
                'status_view':display,
                'reported_evidence':details,'requirements':contract['content'].get('acceptance',[]),
                'review_status':'NEEDS_TRUSTED_REVIEW',
                'convergence':'NOT_VERIFIED','definition_of_done':'NOT_VERIFIED',
                'can_auto_complete':False,'can_release':False,
                'pending_gates':['TRUSTED_APPROVAL_G2','MANDATORY_WRITE_G2',
                                 'TRUSTED_VERIFICATION_G5','REVIEW_CONVERGENCE_G5'],
                'note':'Reports and tool outputs are untrusted; passing strings do not establish verification.'}

    def record_report(self,task_id: str, findings: list[dict], *, expected_revision=0):
        if not isinstance(findings,list):raise ValueError('Findings must be a list')
        allowed={'BLOCKER','MAJOR','ADVISORY'}
        for finding in findings:
            if not isinstance(finding,dict) or finding.get('severity') not in allowed or not finding.get('issue'):
                raise ValueError('Finding requires issue and severity')
        return self.records.put('REVIEW_REPORT',
                                {'findings':findings,'convergence':'NOT_VERIFIED','attestation':'UNVERIFIED'},
                                task_id=task_id,expected_revision=expected_revision,status='UNVERIFIED_REPORT')

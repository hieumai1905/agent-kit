"""Structural Definition-of-Ready validation for a proposed Task Contract.

Does not semantically judge user intent, verify evidence or approve anything.
Only a model + human review may supply the missing meaning; the trusted native
approval channel (not implemented) must validate any final authorization.
"""
from __future__ import annotations
from typing import Any

LEVELS=('QUICK','STANDARD','DEEP')
PLACEHOLDERS={'tbd','todo','unknown','?', '...', 'later','chua ro','chưa rõ'}
CRITICAL_TERMS=('authentication','oauth','payment','thanh toán','database migration',
                'migration','production','phân quyền','authorization','xóa dữ liệu')

def meaningful(value, *, min_length=6):
    if not isinstance(value,str): return False
    normalized=value.casefold().strip()
    return (len(normalized)>=min_length and normalized not in PLACEHOLDERS
            and not (normalized.startswith('<') and normalized.endswith('>')))


def analyze_readiness(contract:dict)->dict:
    if not isinstance(contract,dict):
        return {'status':'NOT_READY','blockers':['Contract must be a JSON object'],
                'trusted_approval':False}
    declared=contract.get('analysis_level','STANDARD')
    if declared not in LEVELS:declared='STANDARD'
    combined=(str(contract.get('objective',''))+' '+str(contract.get('risk_summary',''))).casefold()
    risk_alert=any(term in combined for term in CRITICAL_TERMS)
    effective='DEEP' if risk_alert else declared
    blockers=[]; warnings=[]
    if not meaningful(contract.get('objective')):
        blockers.append('Missing meaningful objective')
    acceptance=contract.get('acceptance')
    if not isinstance(acceptance,list) or not acceptance:
        blockers.append('Missing acceptance criteria')
    else:
        for i,item in enumerate(acceptance):
            statement=item if isinstance(item,str) else item.get('criterion') if isinstance(item,dict) else None
            if not meaningful(statement):blockers.append(f'Acceptance criterion {i+1} missing/placeholder')
    scope=contract.get('scope')
    if not isinstance(scope,dict) or not isinstance(scope.get('functional'),list) or not scope['functional']:
        blockers.append('Missing functional scope')
    elif any(not meaningful(item,min_length=1) for item in scope['functional']):
        blockers.append('Functional scope entries must be non-placeholder strings')
    if effective in ('STANDARD','DEEP'):
        scenario=contract.get('scenarios')
        if not isinstance(scenario,list) or not scenario:
            blockers.append('Scenario coverage not recorded')
        impact=contract.get('impact')
        if not isinstance(impact,dict) or not impact:
            blockers.append('Impact/dependency assessment missing')
        if not isinstance(contract.get('verification_strategy'),list) or not contract['verification_strategy']:
            blockers.append('Verification strategy missing')
    gaps=contract.get('gaps',[] if effective=='QUICK' else None)
    if not isinstance(gaps,list):
        blockers.append('Gap register must explicitly declare unresolved issues (or [])')
    else:
        for gap in gaps:
            if not isinstance(gap,dict):
                blockers.append('Invalid gap record')
            elif (gap.get('severity')=='BLOCKING' and
                  gap.get('status') not in ('RESOLVED','ACCEPTED_WITH_TRUSTED_DECISION')):
                blockers.append('Unresolved blocking gap: '+str(gap.get('summary','unspecified')))
    questions=contract.get('open_questions',[])
    if not isinstance(questions,list):
        blockers.append('open_questions must be a list')
    else:
        for question in questions:
            if (not isinstance(question,dict) or
                (question.get('status')!='RESOLVED' and question.get('blocking',True))):
                blockers.append('Unresolved approval-relevant question')
    if effective=='DEEP':
        if not meaningful(contract.get('risk_summary')):
            blockers.append('Critical domain needs risk_summary')
        if not isinstance(contract.get('evidence_sources'),list) or not contract['evidence_sources']:
            blockers.append('Critical domain needs evidence provenance')
        if not isinstance(contract.get('solution_challenge'),dict):
            blockers.append('Critical domain needs solution challenge record')
    if 'preserve' not in contract:
        warnings.append('Preservation constraints not explicitly recorded')
    if 'open_questions' not in contract:
        warnings.append('User-owned pending questions not explicitly recorded')
    if risk_alert and declared!='DEEP':
        warnings.append('Risk trigger escalated level to DEEP')
    return {'status':'READY_FOR_HUMAN_REVIEW' if not blockers else 'NOT_READY',
            'declared_level':declared,'effective_level':effective,
            'blockers':blockers,'warnings':warnings,
            'semantic_correctness_verified':False,
            'trusted_approval':False,'write_authorized':False,
            'note':'Structural DoR checks alone cannot approve requirements or prove their semantic completeness.'}


def contract_template(level='STANDARD'):
    if level not in LEVELS:raise ValueError('Unknown analysis level')
    return {'analysis_level':level,
            'objective':'<State the verifiable intended outcome>',
            'accepted_behavior':['<State desired behavior and success criteria>'],
            'preserve':['<State behaviors/constraints to preserve>'],
            'scope':{'functional':['<In scope>'], 'excluded':[]},
            'acceptance':['<Verifiable, non-placeholder condition>'],
            'scenarios':[{'name':'normal','disposition':'VERIFY'}],
            'impact':{'affected_components':[], 'coordination_scope':[]},
            'verification_strategy':['<Concrete method>'],
            'risk_summary':'<Risks and failure modes, or explicitly low risk>',
            'gaps':[],'open_questions':[],
            'evidence_sources':[],
            'solution_challenge':{'status':'PENDING'},
            'draft_only':True}

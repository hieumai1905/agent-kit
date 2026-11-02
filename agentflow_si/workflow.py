"""SI-08/09/10/13: focused task/evidence/policy/test proposals.

All results are untrusted workflow data. No completion, approval, execution
permission or trusted test attestation is issued here.
"""
from __future__ import annotations

from hashlib import sha256
import re
from datetime import datetime, timezone
from typing import Any

from agentflow_core import StoreError
from agentflow_core.db import canonical_json
from agentflow_runtime.navigator import TaskNavigator, route_intent, normalize
from agentflow_runtime.records import WorkflowRecords

_HEX=re.compile(r'^[a-f0-9]{64}$')


def evidence_impact(graph: dict, *, changed: list[str]|None=None) -> dict:
    """SI-08: deterministic versioned dependency graph + targeted invalidation.

    graph nodes are snapshots supplied by an untrusted caller. A report that a
    node is unaffected does NOT mean that original tests were trusted.
    """
    if not isinstance(graph,dict) or not isinstance(graph.get('nodes'),list) or len(graph['nodes'])>512:
        raise ValueError('Invalid/big evidence graph')
    nodes={}
    for n in graph['nodes']:
        if not isinstance(n,dict) or set(n)!={'id','kind','revision','sha256','depends_on'}:
            raise ValueError('Malformed node')
        identifier=n['id']
        if not isinstance(identifier,str) or not re.fullmatch('[A-Za-z0-9_.:-]{1,100}',identifier) or identifier in nodes:
            raise ValueError('Duplicate/invalid graph node')
        if not isinstance(n['revision'],int) or isinstance(n['revision'],bool) or n['revision']<1:
            raise ValueError('Invalid revision')
        if not isinstance(n['sha256'],str) or not _HEX.fullmatch(n['sha256']):
            raise ValueError('Invalid hash')
        if not isinstance(n['depends_on'],list) or len(n['depends_on'])>150 or len(set(n['depends_on']))!=len(n['depends_on']):
            raise ValueError('Invalid deps')
        nodes[identifier]=n
    for id,n in nodes.items():
        if id in n['depends_on'] or any(dep not in nodes for dep in n['depends_on']):
            raise ValueError('Missing/self dependency')
    visiting=set();visited=set()
    def visit(identifier):
        if identifier in visiting:raise ValueError('Dependency cycle')
        if identifier in visited:return
        visiting.add(identifier)
        for parent in nodes[identifier]['depends_on']:visit(parent)
        visiting.remove(identifier);visited.add(identifier)
    for id in nodes:visit(id)
    changed=set(changed or [])
    if not changed.issubset(nodes):raise ValueError('Unknown changed node')
    affected=set(changed)
    while True:
        extra={id for id,n in nodes.items() if id not in affected and
               any(dep in affected for dep in n['depends_on'])}
        if not extra:break
        affected.update(extra)
    snapshot=sha256(canonical_json({'nodes':graph['nodes']}).encode()).hexdigest()
    return {'si':'SI-08','graph_sha256':snapshot,
            'affected_nodes':sorted(affected),'unaffected_nodes':sorted(nodes.keys()-affected),
            'requires_reverification':bool(affected),
            'attestation':'UNVERIFIED','promotes_tests_to_pass':False,
            'scope':'CALLER_SUPPLIED_GRAPH_NOT_AUTHORITATIVE_RUNTIME_PROOF'}


def intent_preview(repo, text: str, state_home=None) -> dict:
    """SI-09: reuse canonical navigator, no task creation or new user interface."""
    if not isinstance(text,str) or not text.strip() or len(text)>20000:
        raise ValueError('Invalid user prompt')
    route=route_intent(text)
    if route['intent']=='APPROVAL_CLAIM':
        return {'si':'SI-09','intent':'APPROVAL_CLAIM',
                'message':'Approval expressed in chat; human provenance still unverified.',
                'requires_trusted_channel':True,'approved':False,'task_created':False}
    if route['intent'] in ('QUESTION','EXPLORE'):
        return {'si':'SI-09','intent':route['intent'],'action':'READ_ONLY_ANSWER',
                'task_created':False,'approved':False}
    rec=WorkflowRecords(repo,state_home)
    nav=TaskNavigator(rec)
    query=text
    if route['intent']=='RESUME':
        query=re.sub(r'^(tiếp tục|tiep tuc|resume|làm tiếp|lam tiep|trở lại task|tro lai task|mở lại|mo lai)\s+',
                     '',text,flags=re.I).strip()
    if route['intent']=='NAVIGATE':query=''
    matches=nav.search(query)
    return {'si':'SI-09','intent':route['intent'],'candidate_tasks':matches['choices'],
            'needs_disambiguation':matches.get('requires_confirmation',False),
            'resolved_task_id':matches.get('selected_task_id') if matches.get('auto_selected') else None,
            'task_created':False,'needs_manual_task_id':False,
            'action':'DISPLAY_CHOICES' if matches.get('requires_confirmation') else
                     'RESUME_CANDIDATE' if matches.get('auto_selected') else 'DRAFT_ONLY'}


def profile_exception_proposal(repo, payload: dict, state_home=None, *, save=False,
                               expected_revision=0, request_key=None) -> dict:
    """SI-10: one-repo policy exceptions are drafts; agents cannot activate them."""
    if not isinstance(payload,dict) or set(payload)!={'policy_key','owner','reason','scope','expires_at'}:
        raise ValueError('Expected exact policy exception fields')
    for name in ('policy_key','owner','reason','scope'):
        if not isinstance(payload[name],str) or not payload[name].strip() or len(payload[name])>320:
            raise ValueError('Invalid policy exception '+name)
    try:
        expiry=datetime.fromisoformat(payload['expires_at'].replace('Z','+00:00'))
    except (AttributeError,ValueError):raise ValueError('expires_at must be ISO8601')
    if expiry.tzinfo is None or expiry.astimezone(timezone.utc)<=datetime.now(timezone.utc):
        raise ValueError('Exception must have future UTC expiry')
    body={'status':'PROPOSED_NOT_APPROVED',
          'policy_key':payload['policy_key'],'owner':payload['owner'],
          'reason':payload['reason'],'scope':payload['scope'],
          'expires_at':expiry.astimezone(timezone.utc).isoformat(),
          'approved':False,'active':False,'legacy_is_not_policy':True}
    stored=None
    if save:
        rec=WorkflowRecords(repo,state_home)
        stored=rec.put('SI_POLICY_EXCEPTION',body,key=payload['policy_key'],
                       expected_revision=expected_revision,request_key=request_key)
    return {'si':'SI-10','proposal':body,'persisted_draft':stored,'policy_activated':False}


def verification_plan(payload: dict) -> dict:
    """SI-13: bounded resource declaration and content-based reuse hint only."""
    if not isinstance(payload,dict):raise ValueError('Plan must be a dictionary')
    if set(payload)!={'test_id','code_sha256','env_sha256','resources','prior_result'}:
        raise ValueError('Unexpected test-plan fields')
    for key in ('code_sha256','env_sha256'):
        if not isinstance(payload[key],str) or not _HEX.fullmatch(payload[key]):
            raise ValueError('Invalid '+key)
    test_id=payload['test_id']
    if not isinstance(test_id,str) or not re.fullmatch('[A-Za-z0-9_.:-]{1,100}',test_id):
        raise ValueError('Invalid test id')
    res=payload['resources']
    if not isinstance(res,list) or len(res)>64 or any(not isinstance(x,str) or not re.fullmatch('[A-Za-z0-9_./:@-]{1,128}',x) for x in res):
        raise ValueError('Invalid resource footprint')
    if len(res)!=len(set(res)):raise ValueError('Duplicate resources')
    prior=payload['prior_result']
    if prior is not None and (not isinstance(prior,dict) or
        set(prior)!={'code_sha256','env_sha256','reported_status','attestation'}):
        raise ValueError('Malformed prior_result')
    exact=(bool(prior) and prior['code_sha256']==payload['code_sha256'] and
           prior['env_sha256']==payload['env_sha256'] and prior['reported_status']=='PASS')
    return {'si':'SI-13','test_id':test_id,'resource_footprint':sorted(res),
            'content_fingerprint':sha256(canonical_json({k:payload[k] for k in
                        ('test_id','code_sha256','env_sha256','resources')}).encode()).hexdigest(),
            'candidate_reuse':bool(exact),'trusted_reuse':False,
            'rerun_recommended':True,  # No trusted runner in this candidate, even if claimed.
            'tool_effects':'RUN_TEST_REQUIRES_FOOTPRINT_AUTHORIZATION',
            'tests_executed':False,'test_pass_attested':False,
            'note':'Even a matching claimed attestation cannot be verified inside this agent-writable layer.'}


def evidence_graph_draft(repo, graph: dict, *, state_home=None, changed=None,
                         task_id=None, save=False, expected_revision=0) -> dict:
    """SI-08 persistent untrusted graph snapshot in existing versioned state.

    No new SQLite truth source and no trusted attestation. Saving is opt-in and
    only adds a draft document to the existing outside-repository state.
    """
    impact=evidence_impact(graph,changed=changed)
    record=None
    if save:
        rec=WorkflowRecords(repo,state_home)
        record=rec.put('SI_EVIDENCE_GRAPH',{'nodes':graph['nodes'],
               'graph_sha256':impact['graph_sha256']},task_id=task_id,
               expected_revision=expected_revision,status='UNTRUSTED_DRAFT')
    return {'impact':impact,'saved_draft':record,'trusted_evidence':False}


def verification_resource_conflicts(plans: list[dict]) -> dict:
    """SI-13 only simulate shared resource collision; never run tests."""
    if not isinstance(plans,list) or len(plans)>60:
        raise ValueError('Invalid number of test plans')
    inspected=[verification_plan(p) for p in plans]
    conflicts=[]
    for i,left in enumerate(inspected):
        for right in inspected[i+1:]:
            overlap=set(left['resource_footprint']) & set(right['resource_footprint'])
            if overlap:
                conflicts.append({'test_a':left['test_id'],'test_b':right['test_id'],
                                  'shared_resources':sorted(overlap)})
    return {'si':'SI-13','test_plans':inspected,'conflicts':conflicts,
            'recommendation':'SERIALIZE_OR_ISOLATE' if conflicts else 'NO_DECLARED_OVERLAP',
            'tests_executed':False,'resource_isolation_enforced':False}

"""Agent Workflow Kit v1.0.1 local process CLI (V3 engine).

Safe by default: read-only exploration and external-state drafts; no product-code
mutation, native approvals, execution grants, model calls or CI/CD actions.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sqlite3
import sys

from agentflow_core import LocalCoordinator, StoreError
from agentflow_core.errors import state_database_error
from .capabilities import capability_matrix
from .discovery import RepoDiscovery
from .handoff import HandoffBuilder
from .installer import GuidanceInstaller, InstallerError
from .delegation import contract_binding, record_template, review_record
from .status import task_status
from .continuity import MILESTONES, checkpoint_template, save_checkpoint
from .prewrite import prepare_decision, check_decision
from .model_advisor import ModelAdvisor
from .navigator import TaskNavigator, normalize, route_intent
from .planner import DraftPlanner
from .profiles import EngineeringProfiler
from .records import WorkflowRecords
from .review import EvidenceReviewer
from .practical import git_snapshot, resume_view, final_review_view
from .rig import analyze_readiness,contract_template
from agentflow_security.gates import classify_tool_effect
from agentflow_si.foundations import (trust_boundary, capability_observations, metadata_location,
    session_fencing, recovery_status, release_readiness)
from agentflow_si.operations import mutation_preflight, git_scope_preview, classify_effect, action_approval_scope
from agentflow_si.workflow import (evidence_impact, evidence_graph_draft, intent_preview,
    profile_exception_proposal, verification_plan, verification_resource_conflicts)

VERSION='1.0.1'


def make_parser():
    p=argparse.ArgumentParser(description='Agent Workflow Kit v1.0.1 - local process tools, not OS enforcement')
    p.add_argument('--repo',required=True,help='Existing project folder')
    p.add_argument('--state-home',help='External local state root')
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('version'); sub.add_parser('doctor');sub.add_parser('capabilities')
    sub.add_parser('scan');sub.add_parser('tasks');sub.add_parser('profile');sub.add_parser('setup-preview')
    sub.add_parser('repo-status')
    resume=sub.add_parser('resume');resume.add_argument('query',nargs='?',default='')
    final=sub.add_parser('final-review');final.add_argument('task_id')
    status=sub.add_parser('task-status');status.add_argument('task_id')
    template=sub.add_parser('contract-template');template.add_argument('--level',choices=['QUICK','STANDARD','DEEP'],default='STANDARD')
    check_contract=sub.add_parser('check-contract');check_contract.add_argument('json_file')
    sub.add_parser('delegation-template')
    binding=sub.add_parser('delegation-contract');binding.add_argument('json_file')
    diagnostic=sub.add_parser('delegation-check');diagnostic.add_argument('json_file')
    tool=sub.add_parser('classify-tool');tool.add_argument('command')
    session=sub.add_parser('open-session');session.add_argument('provider',choices=['codex_cli','codex_desktop','claude_cli','claude_desktop']);session.add_argument('--task-id');session.add_argument('--external-ref')
    contract=sub.add_parser('propose-contract');contract.add_argument('task_id');contract.add_argument('json_file')
    checkpoint=sub.add_parser('checkpoint');checkpoint.add_argument('task_id');checkpoint.add_argument('json_file');checkpoint.add_argument('--expected-revision',type=int,default=0)
    template=sub.add_parser('checkpoint-template');template.add_argument('task_id');template.add_argument('--milestone',choices=MILESTONES,default='HANDOFF')
    milestone=sub.add_parser('checkpoint-milestone');milestone.add_argument('task_id');milestone.add_argument('json_file');milestone.add_argument('--expected-revision',type=int,default=0)
    prepare=sub.add_parser('prepare-write');prepare.add_argument('task_id');prepare.add_argument('json_file');prepare.add_argument('--expected-revision',type=int,default=0)
    check=sub.add_parser('check-write');check.add_argument('task_id');check.add_argument('json_file')
    evidence=sub.add_parser('report-check');evidence.add_argument('task_id');evidence.add_argument('--kind',required=True);evidence.add_argument('--reported-status',choices=['PASS','FAIL','NOT_RUN','BLOCKED','UNKNOWN'],required=True);evidence.add_argument('--metadata-json')
    nav=sub.add_parser('navigate');nav.add_argument('query')
    intent=sub.add_parser('route');intent.add_argument('text')
    interact=sub.add_parser('interact');interact.add_argument('text')
    rig=sub.add_parser('preflight');rig.add_argument('text');rig.add_argument('--task-id');rig.add_argument('--save',action='store_true')
    domains=sub.add_parser('domains');domains.add_argument('text')
    task=sub.add_parser('task');task.add_argument('task_id')
    prof=sub.add_parser('propose-profile');prof.add_argument('--save',action='store_true');prof.add_argument('--expected-revision',type=int,default=0)
    plan=sub.add_parser('draft-plan');plan.add_argument('task_id');plan.add_argument('json_file');plan.add_argument('--save',action='store_true');plan.add_argument('--expected-revision',type=int,default=0)
    work=sub.add_parser('draft-work');work.add_argument('task_id');work.add_argument('json_file');work.add_argument('--save',action='store_true');work.add_argument('--expected-revision',type=int,default=0)
    review=sub.add_parser('review');review.add_argument('task_id')
    handoff=sub.add_parser('handoff');handoff.add_argument('task_id')
    adv=sub.add_parser('model-advice');adv.add_argument('level',choices=['QUICK','STANDARD','DEEP']);adv.add_argument('--catalog-json');adv.add_argument('--provider')
    for name in ('install-guidance','remove-guidance'):
        ins=sub.add_parser(name);ins.add_argument('--apply',action='store_true')
        ins.add_argument('--mode',choices=['strict','advisory'],default='strict')
        if name=='install-guidance':
            ins.add_argument('--upgrade',action='store_true')
            ins.add_argument('--delegated-advisory',action='store_true',
                             help='Opt-in Codex local delegation protocol; not a grant (requires --mode advisory)')
    rollback=sub.add_parser('rollback-guidance');rollback.add_argument('transaction_id');rollback.add_argument('--apply',action='store_true')
    # SI-01..14 operator/developer diagnostics. No new UI, no provider execution.
    for name in ('si-trust','si-session','si-recovery','si-release-doctor'):
        sub.add_parser(name)
    obs=sub.add_parser('si-capabilities'); obs.add_argument('--observations-json')
    loc=sub.add_parser('si-metadata');loc.add_argument('--export-destination')
    patch=sub.add_parser('si-mutation-plan');patch.add_argument('json_file')
    git=sub.add_parser('si-git-scope');git.add_argument('json_file',help='JSON list of task-owned relative paths')
    effect=sub.add_parser('si-effect');effect.add_argument('command');effect.add_argument('--declared-effect')
    evidence=sub.add_parser('si-evidence-impact');evidence.add_argument('json_file');evidence.add_argument('--changed',nargs='*',default=[])
    evidence.add_argument('--save',action='store_true');evidence.add_argument('--expected-revision',type=int,default=0);evidence.add_argument('--task-id')
    intent=sub.add_parser('si-intent');intent.add_argument('text')
    policy=sub.add_parser('si-exception');policy.add_argument('json_file');policy.add_argument('--save',action='store_true');policy.add_argument('--expected-revision',type=int,default=0)
    action=sub.add_parser('si-action');action.add_argument('action_name')
    test=sub.add_parser('si-verification-plan');test.add_argument('json_file')
    batch=sub.add_parser('si-test-footprints');batch.add_argument('json_file')
    ses=sub.choices['si-session'];ses.add_argument('--session-id')
    recover=sub.choices['si-recovery'];recover.add_argument('--backup');recover.add_argument('--expected-sha256')
    release=sub.choices['si-release-doctor'];release.add_argument('--observations-json')
    return p


def _read_json(path:str):
    p=Path(path)
    if not p.is_file() or p.stat().st_size>400000:raise StoreError('JSON file missing or too large')
    return json.loads(p.read_text(encoding='utf-8'))


def _strip_resume(text:str):
    return re.sub(r'^(tiếp tục|tiep tuc|resume|làm tiếp|lam tiep|trở lại task|tro lai task|mở lại|mo lai)\s+',
                  '',text,flags=re.I).strip()


def process(args):
    repo=args.repo; home=args.state_home
    # Pure templates/diagnostics: no implicit state initialization or approval.
    if args.action=='delegation-template':return record_template()
    if args.action=='delegation-contract':return contract_binding(_read_json(args.json_file))
    if args.action=='delegation-check':return review_record(repo,_read_json(args.json_file))
    # SI commands are intentionally dispatched before any implicit coordinator
    # creation. Most are pure read-only analyses; --save writes drafts outside repo.
    if args.action=='si-trust':return trust_boundary(repo,home)
    if args.action=='si-capabilities':
        return capability_observations(repo,home,_read_json(args.observations_json) if args.observations_json else None)
    if args.action=='si-metadata':return metadata_location(repo,home,export_destination=args.export_destination)
    if args.action=='si-mutation-plan':return mutation_preflight(repo,_read_json(args.json_file))
    if args.action=='si-git-scope':return git_scope_preview(repo,_read_json(args.json_file))
    if args.action=='si-session':return session_fencing(repo,home,session_id=args.session_id)
    if args.action=='si-effect':return classify_effect(args.command,declared_effect=args.declared_effect)
    if args.action=='si-evidence-impact':
        return evidence_graph_draft(repo,_read_json(args.json_file),state_home=home,
            changed=args.changed,task_id=args.task_id,save=args.save,expected_revision=args.expected_revision)
    if args.action=='si-intent':return intent_preview(repo,args.text,home)
    if args.action=='si-exception':
        return profile_exception_proposal(repo,_read_json(args.json_file),home,
                  save=args.save,expected_revision=args.expected_revision)
    if args.action=='si-recovery':return recovery_status(repo,home,backup=args.backup,expected_sha256=args.expected_sha256)
    if args.action=='si-action':return action_approval_scope(args.action_name)
    if args.action=='si-verification-plan':return verification_plan(_read_json(args.json_file))
    if args.action=='si-test-footprints':return verification_resource_conflicts(_read_json(args.json_file))
    if args.action=='si-release-doctor':
        return release_readiness(repo,home,observations=_read_json(args.observations_json) if args.observations_json else None)
    if args.action=='version':return {'version':VERSION,'working_revision':'V1.0.1-BUGFIX-2026-11-02',
                                     'release_class':'PRACTICAL_ADVISORY_RELEASE_NOT_SECURITY_CERTIFIED'}
    if args.action=='repo-status':return git_snapshot(repo)
    if args.action=='resume':return resume_view(repo,home,args.query)
    if args.action=='interact' and route_intent(args.text)['intent']=='RESUME':
        resumed=resume_view(repo,home,args.text)
        return {'intent':'RESUME','action':'MATCH_EXISTING_TASK','result':resumed['match'],
                'resume':resumed,'requires_disambiguation':resumed['action']=='CHOOSE_TASK',
                'new_task_created':False,'write_authorized':False}
    if args.action=='final-review':return final_review_view(repo,home,args.task_id)
    if args.action=='task-status':return task_status(WorkflowRecords(repo,home),args.task_id)
    if args.action=='check-write':
        return check_decision(WorkflowRecords(repo,home,initialize=False),args.task_id,_read_json(args.json_file))
    if args.action=='capabilities':return capability_matrix()
    if args.action=='doctor':
        core=LocalCoordinator(repo,home,initialize=False)
        doc=core.doctor()
        return {'state':doc,'capabilities':capability_matrix(),
                'guidance_installer':GuidanceInstaller(repo,home).installed_status(),
                'runtime_mode':'READ_ONLY_AND_UNTRUSTED_DRAFTS'}
    if args.action=='setup-preview':return GuidanceInstaller(repo,home).inspect()
    if args.action=='install-guidance':
        ins=GuidanceInstaller(repo,home,mode=args.mode,delegated_advisory=args.delegated_advisory)
        return ins.apply(explicit=True,upgrade=args.upgrade) if args.apply else ins.inspect(upgrade=args.upgrade)
    if args.action=='remove-guidance':
        ins=GuidanceInstaller(repo,home,mode=args.mode)
        return ins.remove(explicit=True) if args.apply else {'would_remove':'two managed guidance blocks only','applied':False}
    if args.action=='rollback-guidance':
        ins=GuidanceInstaller(repo,home)
        return ins.rollback(args.transaction_id,explicit=True) if args.apply else {'transaction_id':args.transaction_id,'would_restore_from_backup':True,'applied':False}
    if args.action=='route':return route_intent(args.text)
    if args.action=='contract-template':return contract_template(args.level)
    if args.action=='check-contract':return analyze_readiness(_read_json(args.json_file))
    if args.action=='classify-tool':return classify_tool_effect(args.command)
    if args.action=='scan':return RepoDiscovery(repo).scan()
    if args.action=='profile':return EngineeringProfiler(repo,home).propose()
    if args.action=='domains':return EngineeringProfiler(repo,home).applicable_domains(args.text)
    if args.action=='model-advice':
        catalog=_read_json(args.catalog_json) if args.catalog_json else None
        return ModelAdvisor().recommend(args.level,catalog,current_provider=args.provider)
    app=LocalCoordinator(repo,home)
    rec=WorkflowRecords(repo,home)
    nav=TaskNavigator(rec)
    if args.action=='tasks':return nav.search('')
    if args.action=='checkpoint-template':return checkpoint_template(rec,args.task_id,args.milestone)
    if args.action=='prepare-write':
        return prepare_decision(rec,args.task_id,_read_json(args.json_file),expected_revision=args.expected_revision)
    if args.action=='checkpoint-milestone':
        return save_checkpoint(rec,args.task_id,_read_json(args.json_file),expected_revision=args.expected_revision)
    if args.action=='open-session':
        return app.open_session(args.provider,task_id=args.task_id,external_ref=args.external_ref)
    if args.action=='checkpoint':
        return rec.put('PROGRESS',_read_json(args.json_file),task_id=args.task_id,
                       expected_revision=args.expected_revision,status='UNVERIFIED_REPORT')
    if args.action=='report-check':
        metadata=_read_json(args.metadata_json) if args.metadata_json else {'reported_by':'agent_or_operator'}
        return app.record_unverified_evidence(args.task_id,args.kind,args.reported_status,[],metadata=metadata)
    if args.action=='propose-contract':
        doc=_read_json(args.json_file)
        readiness=analyze_readiness(doc)
        if readiness['status']!='READY_FOR_HUMAN_REVIEW':
            raise StoreError('Task Contract is not structurally ready: '+', '.join(readiness['blockers']))
        t=app.get_task(args.task_id)
        if t['lifecycle']=='DRAFT':t=app.transition_task(args.task_id,t['revision'],'PREFLIGHT')
        result=app.revise_contract(args.task_id,t['revision'],doc)
        return {'contract':result,'readiness':readiness,
                'approval':app.transition_task(args.task_id,result['revision'],'WAITING_APPROVAL'),
                'trusted_approval':False,'write_authorized':False}
    if args.action=='navigate':return nav.search(args.query)
    if args.action=='task':return {'task':app.get_task(args.task_id),'contract':app.contract_revision(args.task_id)}
    if args.action=='interact':
        r=route_intent(args.text)
        intent=r['intent']
        if intent=='APPROVAL_CLAIM':
            return {'intent':intent,'action':'TRUSTED_APPROVAL_REQUIRED',
                    'approved':False,'write_authorized':False,
                    'message':'Chat text cannot authenticate approval. G2 native control plane not certified.'}
        if intent in ('QUESTION','EXPLORE'):
            return {'intent':intent,'action':'ANSWER_OR_EXPLORE_IN_READ_ONLY_AGENT',
                    'stored':False,'requires_semantic_reasoning':True}
        if intent in ('NAVIGATE','CHANGE_REQUEST'):
            q=_strip_resume(args.text) if intent=='RESUME' else args.text
            matches=nav.search(q)
            return {'intent':intent,'action':'MATCH_EXISTING_TASK','result':matches,
                    'requires_disambiguation':matches.get('requires_confirmation',False)}
        # Avoid accidentally duplicating matching existing tasks; ask for resolution.
        matches=nav.search(args.text)
        if matches['choices'] and matches['choices'][0]['match_score']>=.65:
            return {'intent':intent,'action':'POTENTIAL_EXISTING_TASK',
                    'result':matches,'task_created':False}
        brief=RepoDiscovery(repo).preflight(args.text)
        created=rec.create_preflight(args.text[:180],args.text,brief,normalize(args.text[:180]))
        return {'intent':intent,'action':'CREATED_PREFLIGHT_DRAFT',
                'task':created,'brief_readiness':brief['readiness'],
                'approval_valid':False,'write_authorized':False}
    if args.action=='preflight':
        brief=RepoDiscovery(repo).preflight(args.text)
        if args.save:
            if not args.task_id:raise StoreError('--save requires --task-id from existing draft')
            existing=rec.latest('RIG_BRIEF',task_id=args.task_id)
            record=rec.put('RIG_BRIEF',brief,task_id=args.task_id,
                           expected_revision=existing['revision'] if existing else 0,status='OBSERVED')
            return {'brief':brief,'record':record}
        return brief
    if args.action=='propose-profile':
        profile=EngineeringProfiler(repo,home).propose()
        latest=rec.latest('ENGINEERING_PROFILE')
        expected=args.expected_revision
        record=rec.put('ENGINEERING_PROFILE',profile,expected_revision=expected) if args.save else None
        return {'profile':profile,'record':record,'previous_revision':latest['revision'] if latest else 0}
    if args.action=='draft-plan':
        return DraftPlanner(repo,home).plan(args.task_id,_read_json(args.json_file),
                 save=args.save,expected_revision=args.expected_revision)
    if args.action=='draft-work':
        data=_read_json(args.json_file)
        items=data.get('items') if isinstance(data,dict) else data
        return DraftPlanner(repo,home).work_graph(args.task_id,items,
                     save=args.save,expected_revision=args.expected_revision)
    if args.action=='review':return EvidenceReviewer(repo,home).evaluation(args.task_id)
    if args.action=='handoff':return HandoffBuilder(repo,home).packet(args.task_id)
    raise StoreError('Unsupported command')


def main(argv=None):
    parser=make_parser();args=parser.parse_args(argv)
    try:
        response=process(args)
        print(json.dumps(response,indent=2,ensure_ascii=False,sort_keys=False))
        return 0
    except sqlite3.DatabaseError as exc:
        response=state_database_error(exc)
        if response is None:raise
        print(json.dumps(response,ensure_ascii=False),file=sys.stderr)
        return 2
    except (ValueError,StoreError,OSError,json.JSONDecodeError,InstallerError) as exc:
        print(json.dumps({'error':type(exc).__name__,'message':str(exc),
                          'write_authorized':False},ensure_ascii=False),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())

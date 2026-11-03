"""Agent Workflow Kit slim candidate local process CLI (V3 engine).

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

VERSION='1.1.0-slim-candidate.2'


def make_parser():
    p=argparse.ArgumentParser(description='Agent Workflow Kit slim candidate - begin/verify/handoff; advanced APIs retained; not OS enforcement')
    p.add_argument('--repo',required=True,help='Existing project folder')
    p.add_argument('--state-home',help='External local state root')
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('version'); sub.add_parser('doctor');sub.add_parser('capabilities')
    sub.add_parser('scan');sub.add_parser('tasks');sub.add_parser('profile');sub.add_parser('setup-preview')
    sub.add_parser('repo-status')
    resume=sub.add_parser('resume');resume.add_argument('query',nargs='?',default='');resume.add_argument('--compact',action='store_true')
    work=sub.add_parser('work',help='Everyday start/checkpoint/finish; legacy commands remain available')
    worksub=work.add_subparsers(dest='work_action',required=True)
    begin=worksub.add_parser('begin',help='After actual USER approval: save/read back decision and return a receipt; no patch')
    begin.add_argument('topic');begin.add_argument('--data',help='Approved contract, approval_source and checks JSON, or - for stdin')
    begin.add_argument('--source-ref',help='Actual USER approval reference in this chat')
    begin.add_argument('--objective');begin.add_argument('--path',action='append',default=[])
    begin.add_argument('--accept',action='append',default=[]);begin.add_argument('--preserve',action='append',default=[])
    begin.add_argument('--test',help='One existing project command, parsed without a shell; environment variables in arguments are expanded')
    begin.add_argument('--covers',help='Explicit reported check mapping, e.g. A1,P1; not inferred semantic coverage')
    begin.add_argument('--type',choices=['BUG','FEATURE','MAINTENANCE'],default='BUG')
    begin.add_argument('--scenario',help='Concrete interaction path, if relevant; command-only checks leave actual UI unverified')
    verify=worksub.add_parser('verify',help='Run predeclared checks and bind logs to tested sources')
    verify.add_argument('topic',help='Latest receipt path');verify.add_argument('--timeout',type=int,default=300)
    handoff=worksub.add_parser('handoff',help='Save actual checks and handoff without manual metadata')
    handoff.add_argument('topic',help='Verification receipt path');handoff.add_argument('--summary',required=True)
    handoff.add_argument('--remaining',action='append',default=[])
    for cmd in (begin,verify,handoff):cmd.add_argument('--verbose',action='store_true')
    for name in ('start','checkpoint','finish','history','sources'):
        examples={
          'start':'JSON: analysis_level QUICK|STANDARD|DEEP, work_type BUG|FEATURE|MAINTENANCE, objective, scope.functional, preserve, acceptance, verification_strategy. STANDARD needs scenario/impact facts and gaps(list); usage_scenario can supply the missing scenarios/declared-scope inventory without duplicate input. Explicit invalid fields are not overwritten. DEEP also needs risk_summary(string), evidence_sources(list), solution_challenge(object). Use contract-template --level DEEP for field shapes. Sibling repos: repositories=[{key,root:absolute Git root,write_paths:[explicit relative files],read_paths:[]}]. Direct CLI or stdin; do not read implementation source to discover payloads.',
          'checkpoint':'Use --decision APPROVED --source-ref "actual USER message" --expected-revision N --contract-sha256 SHA [--source relative/file]. Alternatively JSON: {"contract_sha256":"FROM_START_OR_RESUME","expected_revision":1,"decision":{"choice":"APPROVED","source":"actual current-chat USER message"},"source_paths":["app.py"]}. Use the observed revision, never guess. Saves, reads back and rechecks automatically; inspect decision_readback/prepatch_check, stop on BLOCKED/nonzero. No immediate duplicate check; --check revalidates after a gap/change. Multi-repo contracts capture repositories automatically. For new legacy files use new_paths. Next intentional batch JSON: milestone HANDOFF, phase IMPLEMENTING, contract_sha256, expected_revision, source_paths (legacy), prepare_next_batch true, actual summary/completed/remaining/blockers/changed_paths/next_action. Reconcile changes first; approval is not refreshed. In-scope technical refinement: implementation_plan={repositories:[full footprint],reason:string}; requires initial implementation_policy, preserves the original contract/decision and automatically readbacks/rechecks. EXACT remains default.',
          'finish':'JSON: contract_sha256, expected_revision, source_paths, tested_source_hashes captured at test time, summary/completed/remaining/blockers/changed_paths/next_action, checks. Each check: kind (REPRODUCTION for bug), command, executed, exit_code, output_excerpt, status, covers [A1..,P1..]. Manifest mode uses tested_sources_file and changed_sources; no flat source_paths/hashes. A usage_scenario requires USER_WORKFLOW with execution_context ACTUAL_WORKFLOW for complete reported verification. Runs artifact check and saves verification plus handoff; no extra handoff/artifacts call required after success.',
          'history':'Read-only paged checkpoint summaries. Use next_before as --before to continue.',
          'sources':'Capture every declared repository/file immediately before tests. --output /OUTSIDE/artifacts/test-batch.json saves an immutable snapshot; finish accepts tested_sources_file. No tests are executed and no DB/product writes occur.'}
        cmd=worksub.add_parser(name,description=examples[name]);cmd.add_argument('topic');cmd.add_argument('--data',help='JSON file OUTSIDE product tree, or - for stdin; see description above')
        cmd.add_argument('--verbose',action='store_true',help='Full output, selected before a mutation; normal output is concise')
        if name=='start':cmd.add_argument('--kind',choices=['change','question','investigate'],default='change')
        if name=='checkpoint':
            cmd.add_argument('--check',action='store_true',help='Read-only recheck of the saved decision and sources before patch')
            cmd.add_argument('--decision',choices=['APPROVED','REJECTED'])
            cmd.add_argument('--source-ref',help='Actual current-chat USER decision reference; not an inferred approval')
            cmd.add_argument('--expected-revision',type=int)
            cmd.add_argument('--contract-sha256')
            cmd.add_argument('--source',action='append',default=[],help='Explicit existing relative file; repeat for legacy single-repo tasks')
            cmd.add_argument('--new-path',action='append',default=[],help='Explicit absent path for a legacy single-repo task')
        if name=='history':cmd.add_argument('--limit',type=int,default=5);cmd.add_argument('--before',type=int)
        if name=='sources':cmd.add_argument('--output')
    setup=sub.add_parser('setup',help='Guidance plus external inventory and local Git exclude')
    setup.add_argument('--mode',choices=['strict','advisory'],default='strict');setup.add_argument('--apply',action='store_true');setup.add_argument('--upgrade',action='store_true');setup.add_argument('--data')
    setup.add_argument('--delegated-advisory',action='store_true',help='Preserve explicitly selected legacy H/D protocol; never a grant')
    artifacts=sub.add_parser('artifacts',help='External kit-only inventory / INDEX checker')
    artifacts.add_argument('artifact_action',choices=['check','register','inventory','classify-product']);artifacts.add_argument('--data',help='External JSON or stdin. classify-product: items with relative path, exact sha256, source and reason; reports do not override known kit paths/markers/state.')
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


def _work_data(path,repo):
    if not path:return {}
    if path=='-':
        raw=sys.stdin.read(400001)
        if len(raw.encode('utf-8'))>400000:raise StoreError('JSON input too large')
        value=json.loads(raw)
    else:
        p=Path(path).expanduser().resolve()
        if p.is_relative_to(Path(repo).resolve()):raise StoreError('Kit JSON must stay outside product tree; use --data -')
        value=_read_json(str(p))
    if not isinstance(value,dict):raise StoreError('Expected a JSON object')
    return value


def _strip_resume(text:str):
    return re.sub(r'^(tiếp tục|tiep tuc|resume|làm tiếp|lam tiep|trở lại task|tro lai task|mở lại|mo lai)\s+',
                  '',text,flags=re.I).strip()


def process(args):
    repo=args.repo; home=args.state_home
    if args.action=='setup':
        from .artifacts import setup
        return setup(repo,home,args.mode,args.apply,args.upgrade,_work_data(args.data,repo).get('guidance_classification'),delegated=args.delegated_advisory)
    if args.action=='artifacts':
        from .artifacts import Artifacts
        manager=Artifacts(repo,home);data=_work_data(args.data,repo)
        if args.artifact_action=='register':return manager.register(data.get('items'))
        if args.artifact_action=='classify-product':return manager.classify_product(data.get('items'))
        if args.artifact_action=='inventory':return {'inventory':manager.inventory(),'read_only':True}
        return manager.check(data.get('product_paths'))
    if args.action=='work':
        if args.work_action in ('begin','verify','handoff'):
            from . import slim
            if args.work_action=='verify':return slim.verify(repo,home,args.topic,args.timeout)
            if args.work_action=='handoff':return slim.handoff(repo,home,args.topic,args.summary,args.remaining)
            if args.data:
                if any((args.source_ref,args.objective,args.path,args.accept,args.preserve,args.test,args.covers,args.scenario)):
                    raise StoreError('Choose --data or short contract flags, not both')
                data=_work_data(args.data,repo)
            else:
                import shlex
                if not args.test:raise StoreError('Begin needs an existing project --test command')
                contract={'analysis_level':'STANDARD' if args.scenario else 'QUICK','work_type':args.type,
                    'objective':args.objective,'scope':{'functional':args.path},'acceptance':args.accept,
                    'preserve':args.preserve,'verification_strategy':[args.test],
                    'repositories':[{'key':'project','root':str(Path(repo).resolve()),'write_paths':args.path,'read_paths':[]}],
                    'gaps':[]}
                if args.scenario:contract['usage_scenario']=args.scenario
                data={'contract':contract,'approval_source':args.source_ref,
                      'checks':[{'argv':shlex.split(args.test),'kind':'REPRODUCTION' if args.type=='BUG' else 'REGRESSION',
                                 'covers':args.covers.split(',') if args.covers else []}]}
            return slim.begin(repo,home,args.topic,data)
        from .work import start,checkpoint,finish,history,recheck,source_snapshot
        if args.work_action=='history':return history(repo,home,args.topic,args.limit,args.before)
        if args.work_action=='sources':
            if args.data:raise StoreError('work sources takes --output, not --data')
            return source_snapshot(repo,home,args.topic,args.output)
        if args.work_action=='checkpoint' and args.check:
            if args.data or args.decision or args.source_ref or args.expected_revision is not None or args.contract_sha256 or args.source or args.new_path:
                raise StoreError('--check is read-only; do not combine with decision/data/source mutation flags')
            return recheck(repo,home,args.topic)
        data=_work_data(args.data,repo)
        if args.work_action=='checkpoint' and args.decision:
            if args.data:raise StoreError('Choose --data or direct decision flags, not both')
            data={'decision':{'choice':args.decision,'source':args.source_ref},
                  'contract_sha256':args.contract_sha256,'expected_revision':args.expected_revision,
                  'source_paths':args.source,'new_paths':args.new_path}
        if args.work_action=='start':spec=data.get('contract',data)
        else:
            from .work import resolve
            records=WorkflowRecords(repo,home,initialize=False)
            spec=records.core.contract_revision(resolve(records,args.topic))['content']
        if not isinstance(spec,dict):raise StoreError('contract: expected a JSON object')
        from .sources import registry
        roots=[Path(repo).resolve()]+[Path(r['root']) for r in registry(spec,repo)] if spec.get('repositories') else [Path(repo).resolve()]
        if args.data and args.data!='-' and any(Path(args.data).expanduser().resolve().is_relative_to(root) for root in roots):
            raise StoreError('Kit JSON must stay outside every product root; use --data -')
        if args.work_action=='finish' and 'tested_sources_file' in data:
            if 'tested_sources' in data:raise StoreError('Choose tested_sources or tested_sources_file, not both')
            path=Path(data['tested_sources_file']).expanduser().resolve()
            if not path.is_relative_to(records.store.state_dir/'artifacts'):raise StoreError('tested_sources_file must be in the returned artifact_directory')
            data['tested_sources']=_read_json(str(path))
        if args.work_action=='start':return start(repo,home,args.topic,data,args.kind)
        if args.work_action=='checkpoint':return checkpoint(repo,home,args.topic,data)
        return finish(repo,home,args.topic,data)
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
    if args.action=='version':return {'version':VERSION,'working_revision':'SLIM-ISOLATED-CANDIDATE-1',
                                     'release_class':'PRACTICAL_ADVISORY_RELEASE_NOT_SECURITY_CERTIFIED'}
    if args.action=='repo-status':return git_snapshot(repo)
    if args.action=='resume':
        out=resume_view(repo,home,args.query)
        if args.compact:
            from .work import compact_resume
            if out.get('action')=='RESUME_READ_ONLY':
                from .artifacts import Artifacts
                from agentflow_core.db import StateStore
                return compact_resume(out,Artifacts(repo,home).check(),str(StateStore(repo,home).state_dir/'artifacts'))
            return out
        return out
    if args.action=='interact' and route_intent(args.text)['intent']=='RESUME':
        resumed=resume_view(repo,home,args.text)
        return {'intent':'RESUME','action':'MATCH_EXISTING_TASK','result':resumed['match'],
                'resume':resumed,'requires_disambiguation':resumed['action']=='CHOOSE_TASK',
                'new_task_created':False,'write_authorized':False}
    if args.action=='final-review':return final_review_view(repo,home,args.task_id)
    if args.action=='task-status':return task_status(WorkflowRecords(repo,home,initialize=False),args.task_id)
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
        shown=response
        if args.action=='work' and args.work_action!='history' and not args.verbose and not (args.work_action=='sources' and not args.output):
            from .presentation import work_result
            shown=work_result(response)
        print(json.dumps(shown,indent=2,ensure_ascii=False,sort_keys=False))
        if args.action in ('setup','artifacts') and response.get('status')=='BLOCKED':return 2
        if args.action=='work' and response.get('status')=='BLOCKED':return 2
        return 0
    except sqlite3.DatabaseError as exc:
        response=state_database_error(exc)
        if response is None:raise
        print(json.dumps(response,ensure_ascii=False),file=sys.stderr)
        return 2
    except (ValueError,StoreError,OSError,json.JSONDecodeError,InstallerError) as exc:
        from .presentation import error_hint
        error={'error':type(exc).__name__,'message':str(exc),'write_authorized':False}
        hint=error_hint(str(exc))
        if hint:error['input_help']=hint
        print(json.dumps(error,ensure_ascii=False),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())

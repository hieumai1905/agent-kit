"""D3-D7 integration-candidate acceptance: disposable fixtures only."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from contextlib import closing
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from agentflow_core import ConflictError, GateNotImplemented, LocalCoordinator, StoreError
from agentflow_core.schema import SCHEMA_VERSION
from agentflow_runtime import (WorkflowRecords, TaskNavigator, RepoDiscovery, EngineeringProfiler,
                               DraftPlanner, EvidenceReviewer, HandoffBuilder, ModelAdvisor)
from agentflow_runtime.capabilities import capability_matrix
from agentflow_runtime.installer import GuidanceInstaller, InstallerError, BEGIN, END
from agentflow_runtime.navigator import normalize,route_intent
from agentflow_runtime.planner import validate_work_graph
from agentflow_runtime.cli import main as cli_main, process, make_parser
from agentflow_runtime.rig import analyze_readiness,contract_template

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='agentflow-int-')
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.repo=self.base/'repo';self.repo.mkdir()
        self.home=self.base/'state'
        self.file=self.repo/'code.py';self.file.write_text('print("original")\n')
        self.core=LocalCoordinator(self.repo,self.home)
        self.records=WorkflowRecords(self.repo,self.home)

    def _task(self,title='Google login bug'):
        t=self.core.create_task(title,'Investigate and fix problem safely')
        return t['task_id']

    def test_schema_v4_and_outside_repository(self):
        self.assertEqual(SCHEMA_VERSION,4)
        self.assertTrue(self.core.doctor()['healthy'])
        self.assertFalse((self.repo/'.agentflow').exists())

    def test_untrusted_versioned_docs(self):
        t=self._task()
        a=self.records.put('RIG_BRIEF',{'objective':'fix login'},task_id=t)
        self.assertEqual(a['revision'],1)
        with self.assertRaises(ConflictError):
            self.records.put('RIG_BRIEF',{'objective':'outdated'},task_id=t,expected_revision=0)
        b=self.records.put('RIG_BRIEF',{'objective':'changed'},task_id=t,expected_revision=1)
        self.assertEqual(b['revision'],2)
        self.assertFalse(self.records.latest('RIG_BRIEF',task_id=t)['trusted'])

    def test_doc_rows_immutable_at_sqlite_level(self):
        t=self._task();out=self.records.put('PROGRESS',{'foo':1},task_id=t)
        with closing(self.core.store.connect()) as cn:
            with self.assertRaises(Exception):
                cn.execute('UPDATE workflow_documents SET trust_status="VERIFIED" WHERE id=?',(out['record_id'],))
            with self.assertRaises(Exception):
                cn.execute('DELETE FROM workflow_documents WHERE id=?',(out['record_id'],))

    def test_doc_only_expected_trust_status(self):
        with self.assertRaises(StoreError):
            self.records.put('PROGRESS',{'done':True},status='TRUSTED')

    def test_task_scoping_prevents_cross_repo(self):
        t=self._task();other=self.base/'other';other.mkdir()
        with self.assertRaises(StoreError):
            WorkflowRecords(other,self.home).put('PROGRESS',{'x':1},task_id=t)

    def test_alias_unicode_and_collision(self):
        a=self._task('Đăng nhập Google');b=self._task('Quản lý người dùng')
        norm=normalize('Đăng nhập Google')
        self.records.alias(a,norm)
        self.assertEqual(TaskNavigator(self.records).search('Đăng nhập Google')['status'],'UNAMBIGUOUS')
        with self.assertRaises(ConflictError):self.records.alias(b,norm)

    def test_ambiguous_navigation_does_not_guess(self):
        self._task('Sửa API Login');self._task('Sửa UI Login')
        result=TaskNavigator(self.records).search('Login')
        self.assertNotEqual(result['status'],'UNAMBIGUOUS')
        self.assertTrue(result['requires_confirmation'])

    def test_recent_tasks_empty_query(self):
        self._task('A');self._task('B')
        result=TaskNavigator(self.records).search('')
        self.assertEqual(result['status'],'RECENT')
        self.assertEqual(len(result['choices']),2)

    def test_intent_approve_never_trusted(self):
        result=route_intent('duyệt')
        self.assertFalse(result['approval_valid'])
        self.assertTrue(result['requires_trusted_channel'])

    def test_intent_question(self):
        self.assertEqual(route_intent('How does this work?')['intent'],'QUESTION')
        self.assertEqual(route_intent('tiếp tục đăng nhập')['intent'],'RESUME')

    def test_git_scan_no_source_mutation(self):
        subprocess.run(['git','init','-q'],cwd=self.repo,check=True)
        subprocess.run(['git','add','code.py'],cwd=self.repo,check=True)
        original=self.file.read_bytes()
        scan=RepoDiscovery(self.repo).scan()
        self.assertTrue(scan['git_available'])
        self.assertEqual(self.file.read_bytes(),original)
        self.assertTrue(scan['read_only_intent'])

    def test_symlink_config_not_read(self):
        secret=self.base/'secret';secret.write_text('{"secret":1}')
        (self.repo/'package.json').symlink_to(secret)
        snapshot=RepoDiscovery(self.repo).scan()
        self.assertEqual(snapshot['package_summary'],{})
        self.assertEqual(secret.read_text(),'{"secret":1}')

    def test_preflight_is_candidate_not_spec(self):
        r=RepoDiscovery(self.repo).preflight('Sửa OAuth login')
        self.assertEqual(r['readiness'],'NOT_READY_FOR_APPROVAL')
        self.assertFalse(r['constraints']['implementation_write_allowed'])
        self.assertIn('AUTH',r['risk_triggers'])

    def test_profiler_detects_next_without_rewrite(self):
        (self.repo/'package.json').write_text(json.dumps({
            'dependencies':{'next':'16','react':'19'},'scripts':{'test':'vitest'}}))
        prof=EngineeringProfiler(self.repo,self.home).propose()
        self.assertIn('next',prof['framework_evidence'])
        self.assertEqual(prof['status'],'PROPOSED_NOT_APPROVED')
        self.assertTrue(self.file.exists())

    def test_domain_activation_is_proposal(self):
        result=EngineeringProfiler(self.repo,self.home).applicable_domains('Add React dashboard')
        self.assertIn('ui_frontend',result['domains'])
        self.assertIn('security_privacy',result['domains'])
        self.assertFalse(result['policy_activated'])

    def test_plan_draft_with_contract(self):
        t=self._task()
        c=self.core.contract_revision(t)
        plan={'selected_approach':'reuse utility','verification_strategy':['unit test'],
              'contract_sha256':c['sha256']}
        result=DraftPlanner(self.repo,self.home).plan(t,plan,save=True)
        self.assertFalse(result['can_execute'])
        self.assertEqual(result['record']['revision'],1)

    def test_plan_wrong_hash_fails(self):
        t=self._task()
        with self.assertRaises(StoreError):
            DraftPlanner(self.repo,self.home).plan(t,{
                'selected_approach':'A','verification_strategy':['test'],'contract_sha256':'mismatch'})

    def test_plan_missing_verification_fails(self):
        with self.assertRaises(StoreError):
            DraftPlanner(self.repo,self.home).plan(self._task(),{'selected_approach':'A'})

    def test_work_graph_parallel_not_authorized(self):
        items=[{'key':'a','title':'contract','verification':['review']},
               {'key':'b','title':'front','depends_on':['a'],'verification':['test']},
               {'key':'c','title':'back','depends_on':['a'],'verification':['test']}]
        v=validate_work_graph(items)
        self.assertEqual(v['layers'],[['a'],['b','c']])
        self.assertFalse(v['safe_to_parallelize'])
        result=DraftPlanner(self.repo,self.home).work_graph(self._task(),items,save=True)
        self.assertFalse(result['execution_ready'])

    def test_work_graph_cycle(self):
        items=[{'key':'a','title':'a','depends_on':['b'],'verification':['x']},
               {'key':'b','title':'b','depends_on':['a'],'verification':['y']}]
        with self.assertRaises(StoreError):validate_work_graph(items)

    def test_work_graph_missing_dependency(self):
        with self.assertRaises(StoreError):validate_work_graph([
            {'key':'a','title':'a','depends_on':['none'],'verification':['unit']}])

    def test_work_graph_duplicate(self):
        with self.assertRaises(StoreError):validate_work_graph([
            {'key':'a','title':'a','verification':['unit']},
            {'key':'a','title':'a2','verification':['unit']}])

    def test_ready_candidates_no_write(self):
        planner=DraftPlanner(self.repo,self.home)
        items=[{'key':'a','title':'A','verification':['unit']}]
        result=planner.ready_candidates(items)
        self.assertEqual(result['logical_ready'],['a'])
        self.assertFalse(result['write_authorized'])

    def test_unverified_test_pass_is_not_dod(self):
        t=self._task()
        h='a'*64
        self.core.register_artifact('source','code.py',h)
        self.core.record_unverified_evidence(t,'unit','PASS',[('source','code.py')])
        review=EvidenceReviewer(self.repo,self.home).evaluation(t)
        self.assertEqual(review['definition_of_done'],'NOT_VERIFIED')
        self.assertFalse(review['can_auto_complete'])

    def test_bad_review_severity_refused(self):
        with self.assertRaises(ValueError):EvidenceReviewer(self.repo,self.home).record_report(
            self._task(),[{'severity':'PERFECT','issue':'imagined'}])

    def test_handoff_does_not_require_transcript(self):
        t=self._task();self.records.put('PROGRESS',{'next':'run unit tests'},task_id=t)
        packet=HandoffBuilder(self.repo,self.home).packet(t)
        self.assertEqual(packet['task']['id'],t)
        self.assertFalse(packet['permissions']['code_write'])
        self.assertNotIn('transcript',packet)
        self.assertIn('PROGRESS',packet['relevant_artifacts'])

    def test_advisor_unknown_usage(self):
        out=ModelAdvisor().recommend('DEEP')
        self.assertEqual(out['usage_status'],'UNKNOWN')
        self.assertIsNone(out['suggested_model'])
        self.assertFalse(out['automatic_switch'])

    def test_advisor_only_allowlisted_available_provider(self):
        catalog=[{'name':'fast-a','tier':'FAST','provider':'claude_cli','allowed':True,'available':True},
                 {'name':'deep-b','tier':'DEEP','provider':'codex_cli','allowed':True,'available':True},
                 {'name':'deep-c','tier':'DEEP','provider':'claude_cli','allowed':False,'available':True}]
        out=ModelAdvisor().recommend('DEEP',catalog,current_provider='claude_cli')
        self.assertIsNone(out['suggested_model'])
        self.assertTrue(out['human_escalation_recommended'])
        self.assertFalse(out['automatic_switch'])

    def test_capability_never_certified(self):
        caps=capability_matrix()
        self.assertEqual(caps['G2'],'BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED')
        self.assertTrue(all(not p['code_write_enabled'] for p in caps['providers'].values()))

    def test_observed_capability_not_grant(self):
        report=self.records.note_capability('claude_cli','1.0',{'binary_found':True})
        self.assertEqual(report['capability_status'],'NOT_CERTIFIED')
        self.assertFalse(report['enforced'])

    def test_installer_dry_run_leaves_repo_unchanged(self):
        before=list(self.repo.iterdir())
        ins=GuidanceInstaller(self.repo,self.home)
        plan=ins.inspect()
        self.assertFalse(plan['hooks_installed'])
        self.assertEqual(before,list(self.repo.iterdir()))

    def test_installer_apply_preserves_existing_content_and_is_idempotent(self):
        (self.repo/'AGENTS.md').write_text('# Existing custom rules\n')
        ins=GuidanceInstaller(self.repo,self.home)
        out=ins.apply(explicit=True)
        self.assertTrue(out['applied'])
        text=(self.repo/'AGENTS.md').read_text()
        self.assertIn('Existing custom rules',text)
        self.assertIn(BEGIN,text)
        self.assertTrue(ins.apply(explicit=True)['no_changes'])
        self.assertFalse(ins.inspect()['hooks_installed'])
        self.assertEqual(self.file.read_text(),'print("original")\n')
        self.assertTrue(Path(out['backup_dir']).is_relative_to(self.home.resolve()))

    def test_uninstaller_preserves_original_text(self):
        (self.repo/'CLAUDE.md').write_text('My instructions\n')
        ins=GuidanceInstaller(self.repo,self.home)
        ins.apply(explicit=True)
        out=ins.remove(explicit=True)
        self.assertEqual(out['removed_blocks'],2)
        self.assertEqual((self.repo/'CLAUDE.md').read_text().strip(),'My instructions')
        self.assertEqual(self.file.read_text(),'print("original")\n')

    def test_installer_modified_managed_block_refuses(self):
        ins=GuidanceInstaller(self.repo,self.home)
        ins.apply(explicit=True)
        p=self.repo/'AGENTS.md'
        p.write_text(p.read_text().replace('NOT ENFORCED','NOW ENFORCED'))
        with self.assertRaises(InstallerError):ins.apply(explicit=True)
        with self.assertRaises(InstallerError):ins.remove(explicit=True)

    def test_installer_hardlink_refused(self):
        (self.repo/'AGENTS.md').hardlink_to(self.file)
        with self.assertRaises(InstallerError):GuidanceInstaller(self.repo,self.home).inspect()

    def test_installer_symlink_refused(self):
        (self.repo/'AGENTS.md').symlink_to(self.file)
        with self.assertRaises(InstallerError):GuidanceInstaller(self.repo,self.home).inspect()

    def test_installer_no_apply_without_explicit(self):
        with self.assertRaises(InstallerError):GuidanceInstaller(self.repo,self.home).apply()

    def test_external_state_does_not_create_repo_metadata(self):
        t=self._task();self.records.put('RIG_DECISIONS',{'pending':True},task_id=t)
        self.assertEqual([x.name for x in self.repo.iterdir()],['code.py'])

    def test_cli_natural_intake_creates_preflight(self):
        args=make_parser().parse_args(['--repo',str(self.repo),'--state-home',str(self.home),
                                       'interact','Add product filters'])
        out=process(args)
        self.assertEqual(out['action'],'CREATED_PREFLIGHT_DRAFT')
        self.assertFalse(out['write_authorized'])
        self.assertEqual(self.core.list_tasks()[0]['lifecycle'],'PREFLIGHT')

    def test_cli_approval_is_rejected(self):
        args=make_parser().parse_args(['--repo',str(self.repo),'--state-home',str(self.home),
                                       'interact','duyệt'])
        out=process(args)
        self.assertFalse(out['approved'])
        self.assertEqual(len(self.core.list_tasks()),0)

    def test_cli_resume_no_auto_new(self):
        self._task('Google login')
        args=make_parser().parse_args(['--repo',str(self.repo),'--state-home',str(self.home),
                                       'interact','tiếp tục Google login'])
        out=process(args)
        self.assertEqual(out['action'],'MATCH_EXISTING_TASK')
        self.assertEqual(len(self.core.list_tasks()),1)

    def test_cli_question_no_task_created(self):
        args=make_parser().parse_args(['--repo',str(self.repo),'--state-home',str(self.home),
                                       'interact','Tại sao login lỗi?'])
        out=process(args)
        self.assertEqual(out['action'],'ANSWER_OR_EXPLORE_IN_READ_ONLY_AGENT')
        self.assertEqual(len(self.core.list_tasks()),0)

    def test_record_race_one_wins(self):
        t=self._task()
        def worker(i):
            try:return self.records.put('PROGRESS',{'i':i},task_id=t,expected_revision=0)
            except ConflictError:return None
        with ThreadPoolExecutor(max_workers=5) as pool:
            result=list(pool.map(worker,range(5)))
        self.assertEqual(sum(bool(x) for x in result),1)

    def test_never_enable_cli_trusted_transition(self):
        t=self._task()
        self.core.transition_task(t,1,'PREFLIGHT')
        self.core.revise_contract(t,2,{'objective':'Something','acceptance':['test']})
        self.core.transition_task(t,3,'WAITING_APPROVAL')
        with self.assertRaises(GateNotImplemented):
            self.core.transition_task(t,4,'APPROVED')

    def test_v3_to_v4_migration_preserves_existing_task(self):
        from agentflow_core.db import StateStore
        other=self.base/'v3-home'
        store=StateStore(self.repo,other)
        store.initialize(target_version=3)
        with closing(store.connect()) as cn:
            cn.execute('''INSERT INTO tasks
            (id,repo_id,title,kind,lifecycle,revision,current_contract_revision,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)''',
            ('T-old',store.repo_id,'Keep existing','IMPLEMENTATION','DRAFT',1,0,'2026','2026'))
        upgraded=WorkflowRecords(self.repo,other)
        self.assertEqual(upgraded.core.get_task('T-old')['title'],'Keep existing')
        self.assertEqual(upgraded.core.doctor()['schema_version'],4)

    def test_model_advisor_does_not_downgrade_deep_task(self):
        out=ModelAdvisor().recommend('DEEP',[{'name':'fast','tier':'FAST','provider':'claude_cli',
                                              'allowed':True,'available':True}])
        self.assertIsNone(out['suggested_model'])
        self.assertTrue(out['human_escalation_recommended'])








    def test_rig_missing_acceptance_blocked(self):
        r=analyze_readiness({'objective':'Build an improved dashboard','scope':{'functional':['dashboard']}})
        self.assertEqual(r['status'],'NOT_READY')
        self.assertFalse(r['trusted_approval'])

    def test_rig_quick_valid_readiness_not_approval(self):
        r=analyze_readiness({'analysis_level':'QUICK','objective':'Change label from Login to Đăng nhập',
                             'scope':{'functional':['Login label']},
                             'acceptance':['UI renders the intended translation']})
        self.assertEqual(r['status'],'READY_FOR_HUMAN_REVIEW')
        self.assertFalse(r['write_authorized'])

    def test_rig_security_escalates(self):
        r=analyze_readiness({'analysis_level':'QUICK','objective':'Fix OAuth login callback',
                             'scope':{'functional':['callback']},
                             'acceptance':['Callback behavior verified']})
        self.assertEqual(r['effective_level'],'DEEP')
        self.assertEqual(r['status'],'NOT_READY')

    def test_rig_blocking_gap_prevents_dor(self):
        r=analyze_readiness({'objective':'Add product filtering','analysis_level':'STANDARD',
            'scope':{'functional':['filter']},'acceptance':['Product list filters properly'],
            'scenarios':[{'name':'normal'}], 'impact':{'api':['products']},
            'verification_strategy':['API integration'],
            'gaps':[{'severity':'BLOCKING','status':'UNKNOWN','summary':'API contract unspecified'}]})
        self.assertEqual(r['status'],'NOT_READY')

    def test_rig_template_is_not_ready(self):
        for level in ('QUICK','STANDARD','DEEP'):
            self.assertEqual(analyze_readiness(contract_template(level))['status'],'NOT_READY')

    def test_propose_contract_cli_refuses_incomplete(self):
        t=self._task()
        doc=self.base/'bad.json';doc.write_text(json.dumps({'objective':'fix login'}))
        args=make_parser().parse_args(['--repo',str(self.repo),'--state-home',str(self.home),
            'propose-contract',t,str(doc)])
        with self.assertRaises(StoreError):process(args)
        self.assertEqual(self.core.get_task(t)['lifecycle'],'DRAFT')

    def test_propose_quick_contract_only_pending(self):
        t=self._task()
        doc=self.base/'quick.json'
        doc.write_text(json.dumps({'analysis_level':'QUICK','objective':'Change title to Users',
            'scope':{'functional':['heading']},'acceptance':['Title now shows Users']}))
        args=make_parser().parse_args(['--repo',str(self.repo),'--state-home',str(self.home),
            'propose-contract',t,str(doc)])
        out=process(args)
        self.assertFalse(out['trusted_approval'])
        self.assertEqual(self.core.get_task(t)['lifecycle'],'WAITING_APPROVAL')

    def test_cli_does_not_ship_auto_execute(self):
        actions=make_parser()._subparsers._group_actions[0].choices.keys()
        for forbidden in ('approve','execute','authorize-write','deploy','push','commit','mark-pass'):
            self.assertNotIn(forbidden,actions)

if __name__=='__main__':unittest.main()

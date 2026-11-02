"""Regression for independently observed pilot blockers; disposable repositories."""
from contextlib import closing
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch

from agentflow_core import LocalCoordinator
from agentflow_runtime import installer
from agentflow_runtime.installer import GuidanceInstaller,InstallerError
from agentflow_runtime.handoff import HandoffBuilder
from agentflow_runtime.planner import DraftPlanner
from agentflow_runtime.practical import resume_view
from agentflow_runtime.rig import analyze_readiness


class PilotRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='agentflow-pilot-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.repo=self.root/'repo';self.repo.mkdir()
        self.home=self.root/'custom state'

    def quick(self,**changes):
        return {'analysis_level':'QUICK','objective':'Translate the login label',
                'scope':{'functional':['Login label'],'excluded':['Auth logic']},
                'preserve':['Existing authentication behavior'],
                'acceptance':['Login label displays the agreed text'],**changes}

    def test_crlf_and_whitespace_survive_install_upgrade_rollback_remove(self):
        for original in (b'# Policy\r\nPreserve me.\r\n\r\n',b'# Policy\n\n\n\n',b'# Policy without newline',b' \r\n'):
            with self.subTest(original=original):
                target=self.repo/'AGENTS.md';target.write_bytes(original)
                ins=GuidanceInstaller(self.repo,self.home)
                first=ins.apply(explicit=True)
                self.assertTrue(target.read_bytes().startswith(original))
                advisory=GuidanceInstaller(self.repo,self.home,mode='advisory')
                second=advisory.apply(explicit=True,upgrade=True)
                advisory.rollback(second['transaction_id'],explicit=True)
                ins.rollback(first['transaction_id'],explicit=True)
                self.assertEqual(target.read_bytes(),original)
                ins.apply(explicit=True);ins.remove(explicit=True)
                self.assertEqual(target.read_bytes(),original)

    def test_partial_install_can_be_rolled_back_without_overwriting_unknown_edits(self):
        (self.repo/'AGENTS.md').write_bytes(b'# Original\r\n')
        ins=GuidanceInstaller(self.repo,self.home)
        real=installer._atomic_write
        def fail_second(path,data):
            if path.name=='CLAUDE.md':raise OSError('injected disk write failure')
            return real(path,data)
        with patch.object(installer,'_atomic_write',side_effect=fail_second):
            with self.assertRaisesRegex(InstallerError,'transaction_id='):
                ins.apply(explicit=True)
        tx=next(ins.backup_root.iterdir()).name
        self.assertFalse((self.repo/'CLAUDE.md').exists())
        ins.rollback(tx,explicit=True)
        ins.rollback(tx,explicit=True)  # Recovery is repeatable after interruption.
        self.assertEqual((self.repo/'AGENTS.md').read_bytes(),b'# Original\r\n')

    def test_partial_rollback_refuses_unrecognized_user_content(self):
        ins=GuidanceInstaller(self.repo,self.home);tx=ins.apply(explicit=True)['transaction_id']
        (self.repo/'CLAUDE.md').write_text('# Later user changes\n')
        with self.assertRaises(InstallerError):ins.rollback(tx,explicit=True)
        self.assertEqual((self.repo/'CLAUDE.md').read_text(),'# Later user changes\n')

    def test_relocated_helper_paths_are_known_but_custom_rules_are_not(self):
        ins=GuidanceInstaller(self.repo,self.home);ins.apply(explicit=True)
        path=self.repo/'AGENTS.md'
        path.write_text(path.read_text().replace(str(Path(installer.__file__).resolve().parents[1]),'/moved kit'))
        # Actual commands use quoted paths; simulate moving to a path without spaces.
        path.write_text(path.read_text().replace('/moved kit','/moved-kit'))
        ins.remove(explicit=True)
        self.assertFalse(path.exists())
        ins.apply(explicit=True)
        path.write_text(path.read_text().replace('NOT ENFORCED','ENFORCED'))
        with self.assertRaises(InstallerError):ins.remove(explicit=True)

    def test_explicit_state_home_survives_generated_helper_command(self):
        ins=GuidanceInstaller(self.repo,self.home)
        import shlex
        args=shlex.split(ins.command)
        self.assertEqual(args[args.index('--state-home')+1],str(self.home))

    def test_environment_state_home_matches_backups_and_helper(self):
        with patch.dict('os.environ',{'AGENTFLOW_STATE_HOME':str(self.home)}):
            ins=GuidanceInstaller(self.repo)
            self.assertTrue(ins.backup_root.is_relative_to(self.home))
            self.assertIn('--state-home',ins.command)

    def test_override_diagnostic_does_not_modify_override(self):
        override=self.repo/'AGENTS.override.md';override.write_text('# Custom override\n')
        ins=GuidanceInstaller(self.repo,self.home);ins.apply(explicit=True)
        self.assertEqual(ins.installed_status()['instruction_overrides'],[str(override)])
        self.assertEqual(override.read_text(),'# Custom override\n')

    def test_quick_blocking_gap_and_unanswered_question_are_not_ready(self):
        for addition in ({'gaps':[{'severity':'BLOCKING','status':'UNKNOWN'}]},
                         {'open_questions':['Which text should be displayed?']}):
            self.assertEqual(analyze_readiness(self.quick(**addition))['status'],'NOT_READY')

    def test_nonblocking_questions_do_not_expand_quick_workflow(self):
        doc=self.quick(open_questions=[{'summary':'Optional follow-up','blocking':False,'status':'OPEN'}])
        self.assertEqual(analyze_readiness(doc)['status'],'READY_FOR_HUMAN_REVIEW')
        self.assertFalse(analyze_readiness(doc)['write_authorized'])

    def test_handoff_preserves_contract_and_flags_stale_plan(self):
        c=LocalCoordinator(self.repo,self.home);tid=c.create_task('Login translation','Translate label')['task_id']
        c.revise_contract(tid,1,self.quick())
        planner=DraftPlanner(self.repo,self.home)
        planner.plan(tid,{'selected_approach':'Change label only','verification_strategy':['Unit test']},save=True)
        graph=planner.work_graph(tid,[{'key':'one','title':'Translate label','verification':['Unit test']}],save=True)
        self.assertEqual(graph['work_graph']['contract_sha256'],c.contract_revision(tid)['sha256'])
        c.revise_contract(tid,c.get_task(tid)['revision'],self.quick(objective='Change the dashboard heading'))
        packet=HandoffBuilder(self.repo,self.home).packet(tid)
        self.assertEqual(packet['contract']['preserve'],self.quick()['preserve'])
        self.assertEqual(packet['contract']['scope']['excluded'],['Auth logic'])
        self.assertEqual(packet['stale_artifacts'],['TECHNICAL_PLAN','WORK_GRAPH'])
        self.assertFalse(packet['permissions']['code_write'])

    def test_vague_resume_offers_recent_choices_without_guessing(self):
        c=LocalCoordinator(self.repo,self.home);c.create_task('Translate label','A small task')
        out=resume_view(self.repo,self.home,'work from yesterday')
        self.assertEqual(out['action'],'CHOOSE_TASK')
        self.assertFalse(out['match']['auto_selected'])
        self.assertFalse(out['match']['query_matched'])

    def test_acceptance_does_not_promote_failed_regression_to_gate_pass(self):
        path=Path(__file__).resolve().parents[1]/'tools/release_acceptance.py'
        spec=importlib.util.spec_from_file_location('pilot_release_runner',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        failed={'pass':False,'test_count':1};passed={'pass':True,'test_count':5}
        fake=type('Process',(),{'returncode':0,'stdout':'{}','stderr':''})()
        with patch.object(module,'_test',side_effect=[failed,passed]),\
             patch.object(module,'_scratch_smoke',return_value={'pass':True}),\
             patch.object(module.subprocess,'run',return_value=fake):
            result=module.audit()
        self.assertFalse(result['local_tests_pass'])
        self.assertEqual(result['G1'],'LOCAL_REGRESSION_FAILED')

    def test_acceptance_distinguishes_skipped_checks_from_passed_checks(self):
        path=Path(__file__).resolve().parents[1]/'tools/release_acceptance.py'
        spec=importlib.util.spec_from_file_location('pilot_skip_runner',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        fake=type('Process',(),{'returncode':0,'stdout':'',
             'stderr':'Ran 2 tests in 0.1s\n\nOK (skipped=1)\n'})()
        with patch.object(module.subprocess,'run',return_value=fake):
            result=module._test(['fixture-only'],'parse runner summary')
        self.assertTrue(result['pass'])
        self.assertEqual(result['passed_count'],1)
        self.assertEqual(result['skipped_count'],1)


if __name__=='__main__':unittest.main()

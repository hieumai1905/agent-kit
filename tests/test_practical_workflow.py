"""D3-D7 practical integration: temp repos and external temp state only."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agentflow_core import LocalCoordinator
from agentflow_runtime.installer import GuidanceInstaller, InstallerError, BEGIN
from agentflow_runtime.practical import git_snapshot,resume_view,final_review_view
from agentflow_runtime.records import WorkflowRecords
from agentflow_runtime.cli import make_parser,process

class PracticalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='practical-v3-')
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.repo=self.base/'repo';self.repo.mkdir()
        self.code=self.repo/'app.py';self.code.write_text('print("original")\n')
        self.home=self.base/'state'

    def call(self,*items):
        args=make_parser().parse_args(['--repo',str(self.repo),'--state-home',str(self.home),*items])
        return process(args)

    def test_default_strict_no_product_writes(self):
        ins=GuidanceInstaller(self.repo,self.home)
        self.assertEqual(ins.inspect()['guidance_mode'],'STRICT')
        result=ins.apply(explicit=True)
        self.assertTrue(result['applied'])
        self.assertIn('Do not write product code', (self.repo/'AGENTS.md').read_text())
        self.assertIn('NOT ENFORCED', (self.repo/'CLAUDE.md').read_text())
        self.assertEqual(self.code.read_text(),'print("original")\n')

    def test_advisory_is_explicit_and_not_enforced(self):
        ins=GuidanceInstaller(self.repo,self.home,mode='advisory')
        self.assertEqual(ins.inspect()['user_selected_advisory'],True)
        self.assertEqual([p.name for p in self.repo.iterdir()],['app.py'])
        ins.apply(explicit=True)
        text=(self.repo/'AGENTS.md').read_text()
        self.assertIn('ADVISORY',text)
        self.assertIn('explicit, current USER-role approval',text)
        self.assertIn('NOT an enforced security gate',text)
        self.assertNotIn('AgentFlowGuard.app',text)
        self.assertFalse(ins.installed_status()['write_enforced'])
        self.assertEqual(self.code.read_text(),'print("original")\n')

    def test_mode_upgrade_requires_explicit_flag(self):
        GuidanceInstaller(self.repo,self.home).apply(explicit=True)
        target=GuidanceInstaller(self.repo,self.home,mode='advisory')
        with self.assertRaises(InstallerError):target.inspect()
        with self.assertRaises(InstallerError):target.apply(explicit=True)
        self.assertTrue(target.inspect(upgrade=True)['changes'][0]['would_change'])
        target.apply(explicit=True,upgrade=True)
        self.assertEqual(target.installed_status()['installed_files']['AGENTS.md'],'ADVISORY')
        self.assertEqual(self.code.read_text(),'print("original")\n')

    def test_rollback_recovers_exact_original_and_created_files(self):
        (self.repo/'AGENTS.md').write_text('# Important custom policy\n')
        ins=GuidanceInstaller(self.repo,self.home,mode='advisory')
        result=ins.apply(explicit=True)
        self.assertTrue((self.repo/'CLAUDE.md').exists())
        roll=ins.rollback(result['transaction_id'],explicit=True)
        self.assertTrue(roll['rollback'])
        self.assertEqual((self.repo/'AGENTS.md').read_text(),'# Important custom policy\n')
        self.assertFalse((self.repo/'CLAUDE.md').exists())

    def test_rollback_refuses_user_edits_after_install(self):
        ins=GuidanceInstaller(self.repo,self.home)
        r=ins.apply(explicit=True)
        (self.repo/'CLAUDE.md').write_text((self.repo/'CLAUDE.md').read_text()+'CUSTOM\n')
        with self.assertRaises(InstallerError):ins.rollback(r['transaction_id'],explicit=True)

    def test_remove_does_not_keep_empty_instruction_files(self):
        ins=GuidanceInstaller(self.repo,self.home,mode='advisory')
        ins.apply(explicit=True);ins.remove(explicit=True)
        self.assertFalse((self.repo/'AGENTS.md').exists())
        self.assertFalse((self.repo/'CLAUDE.md').exists())
        self.assertEqual(self.code.read_text(),'print("original")\n')

    def test_customized_managed_block_never_overwritten_on_upgrade(self):
        ins=GuidanceInstaller(self.repo,self.home)
        ins.apply(explicit=True)
        file=self.repo/'AGENTS.md'
        file.write_text(file.read_text().replace('NOT ENFORCED','IS ENFORCED'))
        with self.assertRaises(InstallerError):GuidanceInstaller(self.repo,self.home,mode='advisory').apply(explicit=True,upgrade=True)

    def test_git_status_read_only(self):
        subprocess.run(['git','init','-q'],cwd=self.repo,check=True)
        before=self.code.read_bytes()
        snapshot=git_snapshot(self.repo)
        self.assertTrue(snapshot['git_available'])
        self.assertIn('app.py',[x['path'] for x in snapshot['worktree_changes']])
        self.assertFalse(snapshot['write_authorized'])
        self.assertEqual(before,self.code.read_bytes())

    def test_git_status_no_git_not_clean_claim(self):
        status=git_snapshot(self.repo)
        self.assertFalse(status['git_available'])
        self.assertNotIn('clean',status)

    def test_resume_by_name_reads_packet_not_grant(self):
        coordinator=LocalCoordinator(self.repo,self.home)
        coordinator.create_task('Repair product list','Fix products')
        view=resume_view(self.repo,self.home,'Repair product list')
        self.assertEqual(view['action'],'RESUME_READ_ONLY')
        self.assertEqual(view['handoff']['task']['title'],'Repair product list')
        self.assertFalse(view['write_authorized'])

    def test_resume_ambiguity_never_auto_picks(self):
        core=LocalCoordinator(self.repo,self.home)
        core.create_task('Fix login mobile','a');core.create_task('Fix login web','b')
        out=resume_view(self.repo,self.home,'login')
        self.assertEqual(out['action'],'CHOOSE_TASK')
        self.assertFalse(out['new_task_created'])

    def test_final_review_does_not_fabricate_pass(self):
        core=LocalCoordinator(self.repo,self.home)
        task=core.create_task('Repair checkout','bug')
        core.record_unverified_evidence(task['task_id'],'TEST','PASS',[],metadata={'reported_by':'assistant'})
        out=final_review_view(self.repo,self.home,task['task_id'])
        self.assertEqual(out['review_status'],'NEEDS_TRUSTED_REVIEW')
        self.assertEqual(out['definition_of_done'],'NOT_VERIFIED')
        self.assertFalse(out['auto_complete'])

    def test_doctor_advisory_does_not_report_enforcement(self):
        self.call('install-guidance','--mode','advisory','--apply')
        out=self.call('doctor')
        self.assertEqual(out['guidance_installer']['installed_files']['CLAUDE.md'],'ADVISORY')
        self.assertFalse(out['guidance_installer']['certified'])

    def test_cli_rollback_dry_run_safe(self):
        res=self.call('rollback-guidance','abcd'*5)
        self.assertFalse(res['applied'])
        self.assertEqual([x.name for x in self.repo.iterdir()],['app.py'])

    def test_cli_resume_and_repo_status(self):
        self.call('interact','Fix something small')
        r=self.call('resume','Fix something small')
        self.assertEqual(r['action'],'RESUME_READ_ONLY')
        self.assertIn('git_available',self.call('repo-status'))

if __name__=='__main__':unittest.main()

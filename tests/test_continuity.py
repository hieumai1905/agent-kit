"""A3 checkpoints and independent-process resume on disposable state."""
from contextlib import closing
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agentflow_core import ConflictError, LocalCoordinator, StoreError
from agentflow_runtime.cli import make_parser, process
from agentflow_runtime.continuity import checkpoint_template, save_checkpoint
from agentflow_runtime.handoff import HandoffBuilder
from agentflow_runtime.installer import GuidanceInstaller, InstallerError
from agentflow_runtime.practical import resume_view
from agentflow_runtime.records import WorkflowRecords

ROOT=Path(__file__).resolve().parents[1]


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='a3-continuity-');self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name).resolve();self.repo=self.base/'repo';self.repo.mkdir()
        self.file=self.repo/'app.py';self.file.write_text('print("keep")\n');self.home=self.base/'state'
        self.core=LocalCoordinator(self.repo,self.home);self.records=WorkflowRecords(self.repo,self.home)
        self.tid=self.core.create_task('Sửa lỗi locale','Focused locale fix')['task_id']
        self.core.transition_task(self.tid,1,'PREFLIGHT')
        rev=self.core.revise_contract(self.tid,2,{'objective':'Fix locale exit','preserve':['Translations'],
                                               'acceptance':['Missing key exits 1']})
        self.core.transition_task(self.tid,rev['revision'],'WAITING_APPROVAL')

    def payload(self,milestone='HANDOFF'):
        body=checkpoint_template(self.records,self.tid,milestone)['checkpoint']
        body.update(summary='Investigation complete; source not changed',
                    completed=['Read locale code'],remaining=['Obtain a current decision'],
                    next_action='Present the contract and wait')
        return body
    def call(self,*args):
        return process(make_parser().parse_args(['--repo',str(self.repo),'--state-home',str(self.home),*args]))

    def test_template_does_not_create_progress_or_infer_approval(self):
        out=checkpoint_template(self.records,self.tid)
        self.assertEqual(out['expected_revision'],0)
        self.assertEqual(out['checkpoint']['summary'],'')
        self.assertFalse(out['write_authorized'])
        self.assertIsNone(self.records.latest('PROGRESS',task_id=self.tid))

    def test_save_structured_handoff_and_read_brief(self):
        before=self.core.get_task(self.tid)
        saved=save_checkpoint(self.records,self.tid,self.payload())
        self.assertTrue(saved['saved']);self.assertFalse(saved['trusted'])
        packet=HandoffBuilder(self.repo,self.home).packet(self.tid)
        brief=packet['resume_brief']
        self.assertEqual(brief['checkpoint_format'],'STRUCTURED')
        self.assertEqual(brief['reported_remaining'],['Obtain a current decision'])
        self.assertEqual(brief['reported_next_action'],'Present the contract and wait')
        self.assertFalse(brief['write_authorized']);self.assertEqual(self.core.get_task(self.tid),before)
        self.assertEqual(self.file.read_text(),'print("keep")\n')

    def test_milestones_preserve_unverified_decision_and_source_hashes(self):
        first=self.payload('CONTRACT_DECISION')
        first['advisory_decision']={'kind':'DIRECT_HUMAN','decision':'APPROVED',
            'source':{'host':'local','thread_id':'reported','message_id':'unverified'}}
        save_checkpoint(self.records,self.tid,first)
        template=checkpoint_template(self.records,self.tid,'IMPLEMENTATION_VERIFICATION')
        self.assertEqual(template['expected_revision'],1)
        self.assertEqual(template['checkpoint']['advisory_decision'],first['advisory_decision'])
        second=self.payload('IMPLEMENTATION_VERIFICATION')
        second.update(phase='IMPLEMENTED',source_hashes={'app.py':hashlib.sha256(self.file.read_bytes()).hexdigest()})
        saved=save_checkpoint(self.records,self.tid,second,expected_revision=1)
        self.assertEqual(saved['revision'],2)
        self.assertIsNone(self.core.get_task(self.tid)['approved_contract_revision'])

    def test_empty_summary_or_missing_next_step_is_rejected(self):
        for key,value in (('summary',''),('next_action',' '),('completed','done'),('remaining',None),('blockers',[42]),('phase',[])):
            with self.subTest(key=key):
                body=self.payload();body[key]=value
                with self.assertRaises(StoreError):save_checkpoint(self.records,self.tid,body)
        self.assertIsNone(self.records.latest('PROGRESS',task_id=self.tid))

    def test_wrapped_template_cannot_be_saved_as_a_complete_checkpoint(self):
        with self.assertRaises(StoreError):
            save_checkpoint(self.records,self.tid,checkpoint_template(self.records,self.tid))

    def test_decision_milestone_requires_reported_provenance(self):
        with self.assertRaises(StoreError):save_checkpoint(self.records,self.tid,self.payload('CONTRACT_DECISION'))

    def test_verification_milestone_requires_current_observed_hashes(self):
        body=self.payload('IMPLEMENTATION_VERIFICATION')
        with self.assertRaises(StoreError):save_checkpoint(self.records,self.tid,body)
        body['source_hashes']={'app.py':'a'*64}
        with self.assertRaises(ConflictError):save_checkpoint(self.records,self.tid,body)
        body['source_hashes']={'../outside.py':'a'*64}
        with self.assertRaises(ConflictError):save_checkpoint(self.records,self.tid,body)

    def test_contract_change_prevents_rebinding_old_checkpoint(self):
        body=self.payload()
        self.core.revise_contract(self.tid,self.core.get_task(self.tid)['revision'],{'objective':'New requirement'})
        with self.assertRaises(ConflictError):save_checkpoint(self.records,self.tid,body)
        self.assertIsNone(self.records.latest('PROGRESS',task_id=self.tid))

    def test_wrong_expected_revision_never_overwrites_another_checkpoint(self):
        body=self.payload();save_checkpoint(self.records,self.tid,body)
        body['summary']='A stale writer'
        with self.assertRaises(ConflictError):save_checkpoint(self.records,self.tid,body,expected_revision=0)
        self.assertNotEqual(self.records.latest('PROGRESS',task_id=self.tid)['content']['summary'],'A stale writer')

    def test_same_report_is_idempotent_only_for_current_revision(self):
        body=self.payload();save_checkpoint(self.records,self.tid,body)
        with self.assertRaises(ConflictError):save_checkpoint(self.records,self.tid,body,expected_revision=0)
        out=save_checkpoint(self.records,self.tid,body,expected_revision=1)
        self.assertTrue(out['no_changes']);self.assertFalse(out['saved'])
        self.assertEqual(self.records.latest('PROGRESS',task_id=self.tid)['revision'],1)

    def test_changed_paths_reject_traversal_wildcards_and_git_metadata(self):
        for name in ('../x','/absolute','a/**','.git/config','./app.py','a\\b'):
            with self.subTest(name=name):
                body=self.payload();body['changed_paths']=[name]
                with self.assertRaises(StoreError):save_checkpoint(self.records,self.tid,body)

    def test_legacy_checkpoint_remains_readable_without_synthetic_upgrade(self):
        self.records.put('PROGRESS',{'phase':'IMPLEMENTED','next':'Review diff'},task_id=self.tid)
        packet=HandoffBuilder(self.repo,self.home).packet(self.tid)
        self.assertEqual(packet['resume_brief']['checkpoint_format'],'LEGACY')
        self.assertEqual(packet['resume_brief']['reported_next_action'],'Review diff')
        self.assertEqual(packet['status_view']['reported_work']['freshness'],'UNBOUND')
        self.assertEqual(self.records.latest('PROGRESS',task_id=self.tid)['revision'],1)

    def test_missing_checkpoint_is_not_invented_from_git(self):
        brief=HandoffBuilder(self.repo,self.home).packet(self.tid)['resume_brief']
        self.assertEqual(brief['checkpoint_format'],'MISSING')
        self.assertIsNone(brief['reported_next_action'])

    def test_named_natural_resume_returns_checkpoint_without_new_task(self):
        save_checkpoint(self.records,self.tid,self.payload())
        out=self.call('interact','Tiếp tục sửa lỗi locale')
        self.assertEqual(out['action'],'MATCH_EXISTING_TASK')
        self.assertEqual(out['resume']['action'],'RESUME_READ_ONLY')
        self.assertEqual(out['resume']['handoff']['task']['id'],self.tid)
        self.assertEqual(out['resume']['handoff']['resume_brief']['checkpoint_format'],'STRUCTURED')
        self.assertFalse(out['new_task_created']);self.assertEqual(len(self.core.list_tasks()),1)

    def test_generic_resume_requires_a_title_choice_even_with_one_task(self):
        for query in ('tiếp tục việc hôm trước','Tiếp tục công việc vừa làm','resume previous work',''):
            with self.subTest(query=query):
                out=resume_view(self.repo,self.home,query)
                self.assertEqual(out['action'],'CHOOSE_TASK')
                self.assertFalse(out['match']['auto_selected'])
                self.assertFalse(out['new_task_created'])

    def test_multiple_matching_tasks_do_not_auto_pick_newest(self):
        self.core.create_task('Sửa lỗi locale mobile','Mobile')
        self.core.create_task('Sửa lỗi locale web','Web')
        out=resume_view(self.repo,self.home,'locale')
        self.assertEqual(out['action'],'CHOOSE_TASK')
        self.assertIsNone(out['match'].get('selected_task_id'))

    def test_empty_state_resume_does_not_initialize_or_create_task(self):
        fresh=self.base/'fresh-state'
        out=resume_view(self.repo,fresh,'tiếp tục việc hôm trước')
        self.assertEqual(out['action'],'NO_MATCH');self.assertFalse(fresh.exists())
        args=make_parser().parse_args(['--repo',str(self.repo),'--state-home',str(fresh),'interact','tiếp tục lỗi locale'])
        self.assertEqual(process(args)['resume']['action'],'NO_MATCH');self.assertFalse(fresh.exists())

    def test_resume_does_not_initialize_or_migrate_existing_state(self):
        save_checkpoint(self.records,self.tid,self.payload())
        with patch('agentflow_core.db.StateStore.initialize',side_effect=AssertionError('unexpected initialization')):
            out=resume_view(self.repo,self.home,'sửa lỗi locale')
        self.assertEqual(out['action'],'RESUME_READ_ONLY')

    def test_saved_approval_does_not_restore_permissions_on_resume(self):
        body=self.payload();body.update(approved=True,write_authorized=True)
        body['advisory_delegation']={'reported_process_status':'DELEGATED_ADVISORY_ELIGIBLE'}
        save_checkpoint(self.records,self.tid,body)
        out=resume_view(self.repo,self.home,'sửa lỗi locale')
        self.assertFalse(out['write_authorized']);self.assertFalse(out['handoff']['permissions']['code_write'])
        self.assertFalse(out['handoff']['resume_brief']['write_authorized'])

    def test_changed_source_is_stale_on_resume_and_saved_report_is_not_rewritten(self):
        body=self.payload('IMPLEMENTATION_VERIFICATION')
        body.update(phase='IMPLEMENTED',source_hashes={'app.py':hashlib.sha256(self.file.read_bytes()).hexdigest()})
        save_checkpoint(self.records,self.tid,body)
        self.file.write_text('changed later')
        out=resume_view(self.repo,self.home,'sửa lỗi locale')
        self.assertEqual(out['handoff']['resume_brief']['progress_freshness'],'STALE')
        self.assertEqual(self.records.latest('PROGRESS',task_id=self.tid)['content'],body)

    def test_old_guidance_upgrade_rollback_preserves_original_bytes(self):
        installer=GuidanceInstaller(self.repo,self.home,mode='advisory',delegated_advisory=True)
        for name,body in installer._content('advisory',delegated_advisory=True,continuity=False).items():
            (self.repo/name).write_bytes(b'# custom outside\r\n'+body.encode())
        before={name:(self.repo/name).read_bytes() for name in installer.content}
        with self.assertRaises(InstallerError):installer.apply(explicit=True)
        tx=installer.apply(explicit=True,upgrade=True)['transaction_id']
        self.assertIn('Continuity — milestone checkpoints',(self.repo/'AGENTS.md').read_text())
        installer.rollback(tx,explicit=True)
        self.assertEqual(before,{name:(self.repo/name).read_bytes() for name in before})

    def test_raw_checkpoint_command_still_accepts_legacy_payload(self):
        path=self.base/'legacy.json';path.write_text(json.dumps({'next':'Review old report'}))
        out=self.call('checkpoint',self.tid,str(path))
        self.assertFalse(out['trusted'])
        self.assertEqual(self.records.latest('PROGRESS',task_id=self.tid)['content'],{'next':'Review old report'})

    def test_fresh_cli_reads_handoff_without_transcript_or_snapshot_path(self):
        save_checkpoint(self.records,self.tid,self.payload())
        before=self.core.get_task(self.tid)
        run=subprocess.run([sys.executable,'-B',str(ROOT/'tools/agentflow.py'),'--repo',str(self.repo),
            '--state-home',str(self.home),'interact','Tiếp tục sửa lỗi locale'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        data=json.loads(run.stdout)
        self.assertEqual(data['resume']['handoff']['resume_brief']['reported_remaining'],['Obtain a current decision'])
        self.assertEqual(self.core.get_task(self.tid),before)


if __name__=='__main__':unittest.main()

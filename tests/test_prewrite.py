"""A4 regression: failed guards cannot produce a ready checked-flow result."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from agentflow_core import LocalCoordinator, ConflictError, StoreError
from agentflow_runtime.continuity import checkpoint_template
from agentflow_runtime.delegation import contract_binding, record_template
from agentflow_runtime.prewrite import prepare_decision, check_decision
from agentflow_runtime.records import WorkflowRecords
from agentflow_runtime.installer import GuidanceInstaller, InstallerError
from agentflow_runtime.cli import make_parser, process

ROOT=Path(__file__).resolve().parents[1]


class PrewriteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='a4-guard-repair-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.repo=self.root/'repo';self.repo.mkdir()
        self.file=self.repo/'app.py';self.file.write_text('# unchanged fixture\n');self.home=self.root/'state'
        self.core=LocalCoordinator(self.repo,self.home);self.records=WorkflowRecords(self.repo,self.home)
        self.tid=self.core.create_task('Guarded fixture task','Small scope')['task_id']
        self.core.transition_task(self.tid,1,'PREFLIGHT')
        self.document={'revision':2,'objective':'Add one regression','preserve':['Old tests'],
            'acceptance':['Regression passes'],'files':['app.py'],
            'verification_commands':[['python3','-B','-m','unittest']]}
        revised=self.core.revise_contract(self.tid,2,self.document)
        self.core.transition_task(self.tid,revised['revision'],'WAITING_APPROVAL')
        self.contract=self.core.contract_revision(self.tid)

    def decision(self):
        now=time.time();report=record_template()
        report['contract']=deepcopy(self.document)
        report['canonical_contract_binding']={'contract_sha256':self.contract['sha256'],'contract_revision':2}
        report['grant'].update(coordinator_thread='coordinator',executor_thread='executor',repo=str(self.repo),
            task_id=self.tid,objective=self.document['objective'],preserve=self.document['preserve'],
            required_acceptance=self.document['acceptance'],files=['app.py'],
            verification_commands=self.document['verification_commands'],starts_at=now-60,expires_at=now+600)
        report['decision'].update(kind='APPROVE',task_id=self.tid,revision=2,
            contract_sha256=contract_binding(self.document)['sha256'],repo=str(self.repo),
            executor_thread='executor',files=['app.py'],actions=report['grant']['actions'])
        for src in report['sources'].values():
            src.update(thread_id='coordinator',message_id='reported-anchor',observed_at=now,
                complete_context=True,complete_since_anchor=True,explicit_decision=True)
        report['observation'].update(enabled_by_human=True,executor_thread='executor',task_id=self.tid,
            source_accessible=True,source_roles_available=True,executor_history_complete=True,
            executor_observed_at=now,executor_latest_message_id='reported-latest',revoked=False,
            paused=False,superseded=False,task_complete=False,baseline_reconciled=True,single_writer=True)
        report['reported_process_status']='DELEGATED_ADVISORY_ELIGIBLE'
        body=checkpoint_template(self.records,self.tid,'CONTRACT_DECISION')['checkpoint']
        body.update(phase='IMPLEMENTING',summary='Native source review reported; fixture only',
            completed=['Reported source review'],remaining=['Patch and test'],blockers=[],
            next_action='Use checked flow',source_hashes={'app.py':hashlib.sha256(self.file.read_bytes()).hexdigest()},
            advisory_delegation=report)
        return body

    def test_prepare_saves_and_reads_exact_decision_before_recheck(self):
        before=self.core.get_task(self.tid);content=self.decision()
        result=prepare_decision(self.records,self.tid,content)
        stored=self.records.latest('PROGRESS',task_id=self.tid)
        self.assertEqual(result['checkpoint_ref']['record_id'],stored['record_id'])
        self.assertEqual(stored['content'],content)
        self.assertEqual(stored['status'],'UNVERIFIED_REPORT')
        checked=check_decision(self.records,self.tid,result['checkpoint_ref'])
        self.assertEqual(checked['process_result'],'DECISION_CHECKPOINT_RECHECKED_UNVERIFIED')
        self.assertFalse(checked['write_authorized']);self.assertFalse(checked['native_certified'])
        self.assertEqual(self.core.get_task(self.tid),before)
        self.assertEqual(self.file.read_text(),'# unchanged fixture\n')

    def test_stale_source_fails_before_decision_is_saved(self):
        body=self.decision();body['advisory_delegation']['sources']['human_grant']['observed_at']-=31
        with self.assertRaises(StoreError):prepare_decision(self.records,self.tid,body)
        self.assertIsNone(self.records.latest('PROGRESS',task_id=self.tid))

    def test_expired_executor_observation_blocks(self):
        body=self.decision();body['advisory_delegation']['observation']['executor_observed_at']-=31
        with self.assertRaises(StoreError):prepare_decision(self.records,self.tid,body)

    def test_save_failure_propagates_without_ready_result(self):
        with patch('agentflow_runtime.prewrite.save_checkpoint',side_effect=OSError('injected storage failure')):
            with self.assertRaises(OSError):prepare_decision(self.records,self.tid,self.decision())
        self.assertIsNone(self.records.latest('PROGRESS',task_id=self.tid))

    def test_readback_mismatch_does_not_return_prepared_reference(self):
        real=self.records.latest;calls=0
        def latest(*args,**kwargs):
            nonlocal calls
            calls+=1;value=real(*args,**kwargs)
            if calls>=2 and value:value={**value,'record_id':'WRONG'}
            return value
        body=self.decision()
        with patch.object(self.records,'latest',side_effect=latest):
            with self.assertRaises(ConflictError):prepare_decision(self.records,self.tid,body)

    def test_source_expiring_while_saving_stops_after_saved_checkpoint(self):
        body=self.decision();observed=body['advisory_delegation']['sources']['human_grant']['observed_at']
        with patch('agentflow_runtime.delegation.time.time',side_effect=[observed,observed+31]):
            with self.assertRaises(StoreError):prepare_decision(self.records,self.tid,body)
        self.assertIsNotNone(self.records.latest('PROGRESS',task_id=self.tid))
        self.assertEqual(self.file.read_text(),'# unchanged fixture\n')

    def test_checkpoint_conflict_blocks_prepare(self):
        self.records.put('PROGRESS',{'phase':'PAUSED'},task_id=self.tid)
        with self.assertRaises(ConflictError):prepare_decision(self.records,self.tid,self.decision(),expected_revision=0)

    def test_non_decision_or_blocked_milestone_cannot_prepare(self):
        for key,value in (('milestone','HANDOFF'),('phase','PAUSED'),('blockers',['unresolved'])):
            with self.subTest(key=key):
                body=self.decision();body[key]=value
                with self.assertRaises(StoreError):prepare_decision(self.records,self.tid,body)

    def test_wrong_task_or_contract_or_digest_blocks(self):
        for path,value in [('decision.task_id','another-task'),('decision.contract_sha256','a'*64),
                           ('contract.objective','different'),('canonical_contract_binding.contract_revision',1)]:
            with self.subTest(path=path):
                body=self.decision();node=body['advisory_delegation'];parts=path.split('.')
                for p in parts[:-1]:node=node[p]
                node[parts[-1]]=value
                with self.assertRaises((StoreError,ConflictError)):prepare_decision(self.records,self.tid,body)

    def test_stop_revocation_completion_and_unreported_review_block(self):
        for key in ('revoked','paused','superseded','task_complete'):
            with self.subTest(key=key):
                body=self.decision();body['advisory_delegation']['observation'][key]=True
                with self.assertRaises(StoreError):prepare_decision(self.records,self.tid,body)
        body=self.decision();body['advisory_delegation']['reported_process_status']='NOT_REVIEWED'
        with self.assertRaises(StoreError):prepare_decision(self.records,self.tid,body)

    def test_changed_or_missing_patch_baseline_blocks(self):
        body=self.decision();self.file.write_text('# changed externally\n')
        with self.assertRaises(ConflictError):prepare_decision(self.records,self.tid,body)
        body=self.decision();body['source_hashes']={}
        with self.assertRaises(StoreError):prepare_decision(self.records,self.tid,body)

    def test_recheck_refuses_missing_forged_and_badly_typed_reference(self):
        out=prepare_decision(self.records,self.tid,self.decision());ref=out['checkpoint_ref']
        for key,value in [('record_id','forged'),('sha256','b'*64),('revision',True),('contract_revision',2.0),('task_id','other')]:
            with self.subTest(key=key):
                bad={**ref,key:value}
                with self.assertRaises((StoreError,ConflictError)):check_decision(self.records,self.tid,bad)

    def test_recheck_rejects_new_progress_or_contract_or_file(self):
        ref=prepare_decision(self.records,self.tid,self.decision())['checkpoint_ref']
        self.file.write_text('# changed before patch\n')
        with self.assertRaises(ConflictError):check_decision(self.records,self.tid,ref)
        self.file.write_text('# unchanged fixture\n')
        self.records.put('PROGRESS',{'phase':'PAUSED'},task_id=self.tid,expected_revision=1)
        with self.assertRaises(ConflictError):check_decision(self.records,self.tid,ref)
        self.core.revise_contract(self.tid,self.core.get_task(self.tid)['revision'],{**self.document,'objective':'New scope'})
        with self.assertRaises(ConflictError):check_decision(self.records,self.tid,ref)

    def test_recheck_never_renews_observation_time_or_updates_checkpoint(self):
        body=self.decision();ref=prepare_decision(self.records,self.tid,body)['checkpoint_ref']
        before=self.records.latest('PROGRESS',task_id=self.tid)
        check_decision(self.records,self.tid,ref)
        self.assertEqual(self.records.latest('PROGRESS',task_id=self.tid),before)
        old=body['advisory_delegation']['sources']['human_grant']['observed_at']
        with patch('agentflow_runtime.delegation.time.time',return_value=old+31):
            with self.assertRaises(StoreError):check_decision(self.records,self.tid,ref)

    def test_check_write_CLI_does_not_initialize_or_migrate_state(self):
        ref=prepare_decision(self.records,self.tid,self.decision())['checkpoint_ref']
        path=self.root/'reference.json';path.write_text(json.dumps(ref))
        args=make_parser().parse_args(['--repo',str(self.repo),'--state-home',str(self.home),
            'check-write',self.tid,str(path)])
        with patch('agentflow_core.db.StateStore.initialize',side_effect=AssertionError('must stay read-only')):
            out=process(args)
        self.assertEqual(out['process_result'],'DECISION_CHECKPOINT_RECHECKED_UNVERIFIED')

    def test_current_guidance_upgrade_and_rollback_old_A3_bytes(self):
        ins=GuidanceInstaller(self.repo,self.home,mode='advisory',delegated_advisory=True)
        for name,body in ins._content('advisory',delegated_advisory=True,guarded_flow=False).items():
            (self.repo/name).write_bytes(b'# User header\r\n'+body.encode())
        before={n:(self.repo/n).read_bytes() for n in ins.content}
        with self.assertRaises(InstallerError):ins.apply(explicit=True)
        result=ins.apply(explicit=True,upgrade=True)
        self.assertIn('checkedPatchFlow',(self.repo/'AGENTS.md').read_text())
        ins.rollback(result['transaction_id'],explicit=True)
        self.assertEqual(before,{n:(self.repo/n).read_bytes() for n in before})

    def test_fresh_CLI_nonzero_on_expired_guard_no_checkpoint(self):
        body=self.decision();body['advisory_delegation']['sources']['human_grant']['observed_at']-=31
        path=self.root/'expired.json';path.write_text(json.dumps(body))
        result=subprocess.run([sys.executable,'-B',str(ROOT/'tools/agentflow.py'),'--repo',str(self.repo),
            '--state-home',str(self.home),'prepare-write',self.tid,str(path)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(json.loads(result.stderr)['write_authorized'])
        self.assertIsNone(self.records.latest('PROGRESS',task_id=self.tid))

    def integrated_flow(self,mode):
        body=self.decision()
        if mode=='prepare-fails':body['advisory_delegation']['sources']['human_grant']['observed_at']-=31
        decision=self.root/'decision.json';decision.write_text(json.dumps(body))
        inputs={'mode':mode,'python':sys.executable,'cli':str(ROOT/'tools/agentflow.py'),
            'repo':str(self.repo),'state':str(self.home),'task':self.tid,'decision':str(decision),
            'reference':str(self.root/'reference.json'),'db':str(self.core.store.db_file),'target':str(self.file)}
        path=self.root/'integration.json';path.write_text(json.dumps(inputs))
        run=subprocess.run(['node',str(ROOT/'tests/prewrite_flow_integration.js'),str(path)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        return json.loads(run.stdout)

    @unittest.skipUnless(shutil.which('node'),'Node optional for actual CLI/JS integration test')
    def test_actual_helper_and_JS_chain_saves_before_patch(self):
        out=self.integrated_flow('valid')
        self.assertEqual(out['patch_calls'],1)
        self.assertEqual(out['result']['trace'],['decision_checkpoint_saved_and_read_back','decision_checkpoint_rechecked','provider_patch_called'])
        self.assertEqual(self.file.read_text(),'# patched after decision checkpoint\n')
        self.assertIsNone(self.core.get_task(self.tid)['approved_contract_revision'])

    @unittest.skipUnless(shutil.which('node'),'Node optional for actual CLI/JS integration test')
    def test_actual_failed_prepare_never_calls_patch(self):
        out=self.integrated_flow('prepare-fails')
        self.assertEqual(out['patch_calls'],0);self.assertEqual(out['result']['stage'],'prepare')
        self.assertEqual(self.file.read_text(),'# unchanged fixture\n')
        self.assertIsNone(self.records.latest('PROGRESS',task_id=self.tid))

    @unittest.skipUnless(shutil.which('node'),'Node optional for actual CLI/JS integration test')
    def test_actual_failed_recheck_after_save_never_calls_patch(self):
        out=self.integrated_flow('recheck-fails')
        self.assertEqual(out['patch_calls'],0);self.assertEqual(out['result']['stage'],'recheck')
        self.assertIsNotNone(self.records.latest('PROGRESS',task_id=self.tid))
        self.assertEqual(self.file.read_text(),'# unchanged fixture\n')

    @unittest.skipUnless(shutil.which('node'),'Node optional: provider JS sequencing tests need a local JS runtime')
    def test_provider_JS_control_flow_on_real_sentinel_files(self):
        run=subprocess.run(['node',str(ROOT/'tests/test_checked_patch_flow.js')],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        result=json.loads(run.stdout);self.assertTrue(result['pass'])
        self.assertGreaterEqual(result['cases'],15)


if __name__=='__main__':unittest.main()

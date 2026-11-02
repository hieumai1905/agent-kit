"""D1 acceptance tests. Every repository and state home here is disposable."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from agentflow_core import LocalCoordinator, ConflictError, GateNotImplemented, InvalidTransition, StoreError
from agentflow_core.db import StateStore
from agentflow_core.schema import SCHEMA_VERSION, migrate


def child_crash_during_transaction(repo, home):
    # Hard process exit: SQLite must roll back this uncommitted insert on reopen.
    store=StateStore(repo,home)
    with closing(store.connect()) as cn:
        cn.execute('BEGIN IMMEDIATE')
        cn.execute('INSERT INTO tasks (id,repo_id,title,kind,lifecycle,revision,current_contract_revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                   ('T-never-committed',store.repo_id,'Aborted','IMPLEMENTATION','DRAFT',1,0,'2026','2026'))
        os._exit(71)


def child_init(repo, home, queue):
    try:
        app=LocalCoordinator(repo,home)
        queue.put(('ok',app.doctor()['healthy']))
    except BaseException as exc:
        queue.put(('error',type(exc).__name__ + ':' + str(exc)))


def child_race(repo, home, task_id, expected_rev, queue):
    try:
        app=LocalCoordinator(repo,home)
        out=app.transition_task(task_id, expected_rev, 'PREFLIGHT',request_key=os.urandom(12).hex())
        queue.put(('ok',out['revision']))
    except BaseException as exc:
        queue.put(('error',type(exc).__name__))


class Wave1StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='awsv3-d1-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root/'repo'
        self.repo.mkdir()
        (self.repo/'PRODUCT_FILE.py').write_text('print("do not touch")\n',encoding='utf8')
        self.state_home = self.root/'state-home'
        self.app = LocalCoordinator(self.repo,self.state_home)

    def task(self):
        return self.app.create_task('Google login error',
                                    'Investigate intermittent Google login callback errors')

    def test_database_healthy_and_outside_working_tree(self):
        self.assertEqual(self.app.doctor()['schema_version'],SCHEMA_VERSION)
        self.assertTrue(self.app.doctor()['healthy'])
        self.assertFalse(self.app.doctor()['enforced'])
        self.assertFalse((self.repo/'.agentflow').exists())
        self.assertEqual(list(self.repo.iterdir()),[self.repo/'PRODUCT_FILE.py'])
        self.assertTrue(self.app.store.state_dir.is_relative_to(self.state_home.resolve()))

    def test_state_home_inside_repo_is_rejected(self):
        with self.assertRaises(StoreError):
            LocalCoordinator(self.repo,self.repo/'private-state')
        self.assertFalse((self.repo/'private-state').exists())

    def test_readonly_doctor_does_not_create_database(self):
        new_home=self.root/'not-created'
        res=LocalCoordinator(self.repo,new_home,initialize=False).doctor()
        self.assertFalse(res['initialized'])
        self.assertFalse(new_home.exists())

    def test_task_creation_and_immutable_initial_contract(self):
        t=self.task()
        self.assertEqual(t['lifecycle'],'DRAFT')
        self.assertFalse(t['approved'])
        obj=self.app.contract_revision(t['task_id'])
        self.assertEqual(obj['revision'],1)
        self.assertIn('intermittent',obj['content']['source_request'])
        self.assertEqual(obj['sha256'],hashlib.sha256(json.dumps(obj['content'],sort_keys=True,
                             separators=(',', ':'),ensure_ascii=False).encode()).hexdigest())

    def test_idempotent_create_returns_exactly_same_task(self):
        params=('Task title','Requested behavior and acceptance criteria')
        a=self.app.create_task(*params,request_key='same-create')
        b=LocalCoordinator(self.repo,self.state_home).create_task(*params,request_key='same-create')
        self.assertEqual(a,b)
        self.assertEqual(len(self.app.list_tasks()),1)

    def test_reused_idempotency_key_different_payload_rejected(self):
        self.app.create_task('Feature A','Build feature A',request_key='unique-key')
        with self.assertRaises(ConflictError):
            self.app.create_task('Feature B','Build feature B',request_key='unique-key')

    def test_contract_revisions_are_immutable_and_only_proposed(self):
        t=self.task()
        task_id=t['task_id']
        started=self.app.transition_task(task_id,1,'PREFLIGHT')
        doc={'objective':'Make Google login callback stable','acceptance':['Callback handles invalid state']}
        revised=self.app.revise_contract(task_id,started['revision'],doc)
        self.assertEqual(revised['contract_revision'],2)
        self.assertEqual(revised['lifecycle'],'PREFLIGHT')
        self.assertEqual(self.app.contract_revision(task_id,1)['content']['purpose'],'IMPLEMENTATION')
        self.assertEqual(self.app.contract_revision(task_id,2)['content'],doc)
        proposed=self.app.transition_task(task_id,revised['revision'],'WAITING_APPROVAL')
        self.assertEqual(proposed['lifecycle'],'WAITING_APPROVAL')
        self.assertIsNone(self.app.get_task(task_id)['approved_contract_revision'])

    def test_cannot_propose_request_only_contract(self):
        t=self.task()
        self.app.transition_task(t['task_id'],1,'PREFLIGHT')
        with self.assertRaises(StoreError):
            self.app.transition_task(t['task_id'],2,'WAITING_APPROVAL')

    def test_invalid_task_transition_rejected(self):
        t=self.task()
        with self.assertRaises(InvalidTransition):
            self.app.transition_task(t['task_id'],1,'COMPLETED')
        with self.assertRaises(InvalidTransition):
            self.app.transition_task(t['task_id'],1,'WAITING_APPROVAL')

    def test_approval_cannot_be_self_issued_in_d1(self):
        t=self.task()
        self.app.transition_task(t['task_id'],1,'PREFLIGHT')
        revised=self.app.revise_contract(t['task_id'],2,{'objective':'fix callback'})
        self.app.transition_task(t['task_id'],revised['revision'],'WAITING_APPROVAL')
        with self.assertRaises(GateNotImplemented):
            self.app.transition_task(t['task_id'],4,'APPROVED')
        claimed=self.app.reference_unverified_approval(t['task_id'],'chat-text:Duyệt')
        self.assertEqual(claimed['provenance_status'],'UNVERIFIED')
        self.assertFalse(claimed['approved'])
        self.assertEqual(self.app.get_task(t['task_id'])['lifecycle'],'WAITING_APPROVAL')
        with self.assertRaises(GateNotImplemented):
            self.app.approval_or_write_capability()

    def test_stale_task_revision_rejected(self):
        t=self.task()
        self.app.transition_task(t['task_id'],1,'PREFLIGHT')
        with self.assertRaises(ConflictError):
            self.app.revise_contract(t['task_id'],1,{'objective':'abc'})

    def test_session_lifecycle_and_revision(self):
        task=self.task()
        s=self.app.open_session('codex_cli',task_id=task['task_id'])
        self.assertFalse(s['write_authorized'])
        p=self.app.transition_session(s['session_id'],1,'PAUSED')
        self.assertEqual(p['revision'],2)
        with self.assertRaises(ConflictError):
            self.app.transition_session(s['session_id'],1,'ACTIVE')
        self.app.transition_session(s['session_id'],2,'CLOSED')
        with self.assertRaises(InvalidTransition):
            self.app.transition_session(s['session_id'],3,'ACTIVE')

    def test_session_provider_must_be_supported(self):
        with self.assertRaises(StoreError):
            self.app.open_session('unsafe_custom_shell')

    def test_work_items_and_dependency_readiness(self):
        t=self.task()['task_id']
        first=self.app.create_work_item(t,'Define API contract')
        second=self.app.create_work_item(t,'Implement UI',[first['work_item_id']])
        self.app.transition_work(first['work_item_id'],1,'READY')
        with self.assertRaises(InvalidTransition):
            self.app.transition_work(second['work_item_id'],1,'READY')
        with self.assertRaises(GateNotImplemented):
            self.app.transition_work(first['work_item_id'],2,'CLAIMED')

    def test_cyclic_dependencies_rejected(self):
        t=self.task()['task_id']
        a=self.app.create_work_item(t,'A')
        b=self.app.create_work_item(t,'B',[a['work_item_id']])
        with self.assertRaises(StoreError):
            self.app.add_work_dependency(a['work_item_id'],b['work_item_id'])

    def test_policy_proposal_versioning_and_no_activations(self):
        a=self.app.propose_policy('engineering.core',{'rule':'Concise and correct'},0)
        self.assertEqual(a['status'],'PROPOSED')
        b=self.app.propose_policy('engineering.core',{'rule':'Avoid unnecessary patterns'},1)
        self.assertEqual(b['revision'],2)
        with self.assertRaises(ConflictError):
            self.app.propose_policy('engineering.core',{'rule':'Anything'},1)
        with closing(self.app.store.connect(read_only=True)) as cn:
            self.assertEqual(cn.execute("SELECT COUNT(*) FROM policy_versions WHERE status='PROPOSED'").fetchone()[0],2)

    def test_artifact_dependency_invalidates_evidence(self):
        task=self.task()['task_id']
        h1=hashlib.sha256(b'version 1').hexdigest()
        h2=hashlib.sha256(b'version 2').hexdigest()
        self.app.register_artifact('source','src/auth.py',h1)
        evidence=self.app.record_unverified_evidence(task,'test','PASS',
                                                    [('source','src/auth.py')],metadata={'runner':'fake'})
        self.assertEqual(evidence['attestation'],'UNVERIFIED')
        self.assertFalse(evidence['sufficient_for_DoD'])
        self.assertTrue(self.app.evidence_freshness(evidence['evidence_id'])['fresh'])
        self.app.register_artifact('source','src/auth.py',h2,expected_revision=1)
        self.assertFalse(self.app.evidence_freshness(evidence['evidence_id'])['fresh'])
        self.assertFalse(self.app.evidence_freshness(evidence['evidence_id'])['sufficient_for_DoD'])

    def test_artifact_cas(self):
        hash1='a'*64
        self.app.register_artifact('config','settings',hash1)
        with self.assertRaises(ConflictError):
            self.app.register_artifact('config','settings','b'*64,0)
        unchanged=self.app.register_artifact('config','settings',hash1,1)
        self.assertFalse(unchanged['changed'])
        self.assertEqual(unchanged['revision'],1)

    def test_resource_intents_do_not_authorize_writes(self):
        task=self.task()['task_id']
        a=self.app.open_session('codex_cli',task_id=task)
        b=self.app.open_session('claude_cli',task_id=task)
        reservation=self.app.reserve_intent(a['session_id'],'file:src/auth.py')
        self.assertFalse(reservation['write_authorized'])
        with self.assertRaises(ConflictError):
            self.app.reserve_intent(b['session_id'],'file:src/auth.py')
        self.app.release_intent(a['session_id'],'file:src/auth.py',reservation['generation'])
        other=self.app.reserve_intent(b['session_id'],'file:src/auth.py')
        self.assertGreater(other['generation'],reservation['generation'])
        with self.assertRaises(ConflictError):
            self.app.release_intent(a['session_id'],'file:src/auth.py',reservation['generation'])

    def test_expired_intent_is_not_silently_stolen(self):
        task=self.task()['task_id']
        a=self.app.open_session('codex_cli',task_id=task)
        b=self.app.open_session('claude_cli',task_id=task)
        self.app.reserve_intent(a['session_id'],'git:index',ttl_seconds=1)
        with closing(self.app.store.connect()) as cn:
            cn.execute("UPDATE resource_intents SET expires_at=0 WHERE resource_key='git:index'")
        with self.assertRaises(ConflictError):
            self.app.reserve_intent(b['session_id'],'git:index')

    def test_contract_policy_and_evidence_records_are_immutable(self):
        t=self.task()['task_id']
        self.app.propose_policy('engineering.baseline',{'rule':'correct and concise'})
        e=self.app.record_unverified_evidence(t,'typecheck','NOT_RUN',[])
        with closing(self.app.store.connect()) as cn:
            for query in (
                "UPDATE contract_revisions SET content_json='{}' WHERE task_id=?",
                "DELETE FROM contract_revisions WHERE task_id=?",
                "UPDATE policy_versions SET content_json='{}' WHERE id=?",
                "DELETE FROM policy_versions WHERE id=?",
                "UPDATE evidence SET reported_status='PASS' WHERE id=?",
                "DELETE FROM evidence WHERE id=?",
            ):
                param=e['evidence_id'] if 'evidence' in query else (
                    cn.execute('SELECT id FROM policy_versions LIMIT 1').fetchone()[0]
                    if 'policy' in query else t)
                with self.assertRaises(sqlite3.DatabaseError):
                    cn.execute(query,(param,))
        self.assertTrue(self.app.doctor()['healthy'])

    def test_audit_is_append_only_and_valid(self):
        self.task()
        with closing(self.app.store.connect()) as cn:
            with self.assertRaises(sqlite3.DatabaseError):
                cn.execute("UPDATE audit_events SET event_kind='FAKE' WHERE seq=1")
            with self.assertRaises(sqlite3.DatabaseError):
                cn.execute('DELETE FROM audit_events WHERE seq=1')
        self.assertTrue(self.app.store.audit_valid())

    def test_audit_detects_tampering_even_if_sqlite_triggers_removed(self):
        self.task()
        with closing(self.app.store.connect()) as cn:
            cn.execute('DROP TRIGGER audit_events_no_update')
            cn.execute("UPDATE audit_events SET event_kind='FORGED' WHERE seq=1")
        self.assertFalse(self.app.store.audit_valid())
        self.assertFalse(self.app.doctor()['healthy'])

    def test_failed_transaction_rolls_back_everything(self):
        def broken_handler(cn):
            cn.execute('INSERT INTO tasks (id,repo_id,title,kind,lifecycle,revision,current_contract_revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                       ('T-incomplete',self.app.store.repo_id,'Broken task','IMPLEMENTATION','DRAFT',
                        1,0,'2026','2026'))
            raise RuntimeError('simulated crash before event commit')
        with self.assertRaises(RuntimeError):
            self.app.store.mutate('bad-operation',{'x':1},broken_handler)
        with closing(self.app.store.connect(read_only=True)) as cn:
            self.assertEqual(cn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],0)
            self.assertEqual(cn.execute('SELECT COUNT(*) FROM operations').fetchone()[0],0)
            self.assertEqual(cn.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0],0)

    def test_consistent_backup_and_fresh_restore(self):
        self.task()
        b=self.app.store.backup()
        verified=self.app.store.verify_backup(b['path'],b['sha256'])
        self.assertTrue(verified['valid'])
        restored=self.app.store.restore_to_fresh_state(b['path'],self.root/'fresh-recovery',b['sha256'])
        self.assertTrue(restored['doctor']['healthy'])
        fresh=LocalCoordinator(self.repo,self.root/'fresh-recovery')
        self.assertEqual(len(fresh.list_tasks()),1)
        with self.assertRaises(StoreError):
            self.app.store.restore_to_fresh_state(b['path'],self.root/'fresh-recovery')

    def test_backup_bad_checksum_rejected(self):
        b=self.app.store.backup()
        with self.assertRaises(StoreError):
            self.app.store.verify_backup(b['path'],'0'*64)

    def test_backup_of_different_repo_rejected(self):
        b=self.app.store.backup()
        repo2=self.root/'another'
        repo2.mkdir()
        with self.assertRaises(StoreError):
            StateStore(repo2,self.root/'elsewhere').verify_backup(b['path'])

    def test_migration_v1_to_v2_preserves_rows(self):
        home=self.root/'oldschema'
        old=StateStore(self.repo,home)
        old.initialize(target_version=1)
        with closing(old.connect()) as cn:
            cn.execute('''INSERT INTO tasks
              (id,repo_id,title,kind,lifecycle,revision,current_contract_revision,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?)''',
              ('T-legacy',old.repo_id,'Old task','IMPLEMENTATION','DRAFT',1,0,'2026','2026'))
        upgraded=LocalCoordinator(self.repo,home)
        self.assertTrue(upgraded.doctor()['healthy'])
        self.assertEqual(upgraded.get_task('T-legacy')['title'],'Old task')

    def test_migration_history_mismatch_fails_closed(self):
        home=self.root/'mismatch'
        store=StateStore(self.repo,home)
        store.initialize(target_version=1)
        with closing(store.connect()) as cn:
            with self.assertRaises(sqlite3.DatabaseError):
                cn.execute("UPDATE schema_migrations SET sha256='bad' WHERE version=1")
            # Same-user malicious process can still DROP triggers (D2 trust boundary).
            cn.execute('DROP TRIGGER migrations_immutable_update')
            cn.execute("UPDATE schema_migrations SET sha256='bad' WHERE version=1")
        with self.assertRaises(StoreError):
            store.initialize(target_version=2)
        with closing(store.connect(read_only=True)) as cn:
            self.assertEqual(cn.execute('PRAGMA user_version').fetchone()[0],1)

    def test_unknown_unversioned_preview_db_refused(self):
        home=self.root/'legacy'
        store=StateStore(self.repo,home)
        store._mkdir_state()
        with sqlite3.connect(str(store.db_file)) as cn:
            cn.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY)')
        with self.assertRaises(StoreError):
            store.initialize()
        with closing(store.connect(read_only=True)) as cn:
            self.assertEqual(cn.execute('PRAGMA user_version').fetchone()[0],0)

    def test_concurrent_idempotent_call_one_result(self):
        def worker(_):
            return LocalCoordinator(self.repo,self.state_home).create_task(
                'Same task','Same natural language request',request_key='the-same-request')
        with ThreadPoolExecutor(max_workers=7) as pool:
            results=list(pool.map(worker,range(15)))
        self.assertEqual(len({r['task_id'] for r in results}),1)
        self.assertEqual(len(self.app.list_tasks()),1)

    def test_parallel_process_initialization_is_atomic(self):
        home=self.root/'new-concurrent-state'
        context=mp.get_context('spawn')
        queue=context.Queue()
        procs=[context.Process(target=child_init,args=(str(self.repo),str(home),queue))
               for _ in range(4)]
        for p in procs: p.start()
        result=[queue.get(timeout=20) for _ in procs]
        for p in procs:
            p.join(20)
            self.assertEqual(p.exitcode,0)
        self.assertEqual(result,[('ok',True)]*4)

    def test_forced_process_crash_rolls_back_partial_write(self):
        ctx=mp.get_context('spawn')
        child=ctx.Process(target=child_crash_during_transaction,
                          args=(str(self.repo),str(self.state_home)))
        child.start()
        child.join(20)
        self.assertEqual(child.exitcode,71)
        self.assertTrue(self.app.doctor()['healthy'])
        with closing(self.app.store.connect(read_only=True)) as cn:
            self.assertEqual(cn.execute("SELECT COUNT(*) FROM tasks WHERE id='T-never-committed'").fetchone()[0],0)
        self.task()
        self.assertTrue(self.app.doctor()['healthy'])

    def test_failed_mutation_can_retry_same_idempotency_key(self):
        def fail(cn):
            raise RuntimeError('machine stopped before commit')
        with self.assertRaises(RuntimeError):
            self.app.store.mutate('scratch',{'attempt':1},fail,request_key='retryable')
        self.assertEqual(self.app.store.mutate('scratch',{'attempt':1},
                        lambda cn:{'committed':True},request_key='retryable'),{'committed':True})

    def test_session_intent_rejected_when_session_closed(self):
        t=self.task()['task_id']
        s=self.app.open_session('codex_cli',task_id=t)
        self.app.transition_session(s['session_id'],1,'CLOSED')
        with self.assertRaises(InvalidTransition):
            self.app.reserve_intent(s['session_id'],'file:component.ts')

    def test_no_automatic_approval_on_backup_restore(self):
        t=self.task()['task_id']
        self.app.transition_task(t,1,'PREFLIGHT')
        self.app.revise_contract(t,2,{'objective':'fix problem'})
        self.app.transition_task(t,3,'WAITING_APPROVAL')
        self.app.reference_unverified_approval(t,'chat-text:Duyệt')
        back=self.app.store.backup()
        target=self.root/'restore-unverified'
        self.app.store.restore_to_fresh_state(back['path'],target,back['sha256'])
        recovered=LocalCoordinator(self.repo,target)
        self.assertIsNone(recovered.get_task(t)['approved_contract_revision'])
        with self.assertRaises(GateNotImplemented):
            recovered.transition_task(t,4,'APPROVED')

    def test_parallel_process_optimistic_updates_no_lost_write(self):
        task=self.task()['task_id']
        context=mp.get_context('spawn')
        queue=context.Queue()
        procs=[context.Process(target=child_race,args=(str(self.repo),str(self.state_home),task,1,queue))
               for _ in range(3)]
        for p in procs:p.start()
        results=[queue.get(timeout=20) for _ in procs]
        for p in procs:
            p.join(20)
            self.assertEqual(p.exitcode,0)
        self.assertEqual(sum(kind=='ok' for kind,_ in results),1)
        self.assertEqual(self.app.get_task(task)['revision'],2)

    def test_cli_init_and_doctor_json(self):
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        run=subprocess.run([sys.executable,'-m','agentflow_core.cli','--repo',str(self.repo),
                            '--state-home',str(self.state_home),'doctor'],
                           env=env,text=True,capture_output=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertTrue(json.loads(run.stdout)['healthy'])


if __name__=='__main__':
    unittest.main()

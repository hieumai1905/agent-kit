"""v1.0.1 observed-defect regressions. All state/repos are disposable."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agentflow_core import LocalCoordinator, ConflictError
from agentflow_runtime.cli import make_parser, process
from agentflow_runtime.navigator import TaskNavigator, normalize
from agentflow_runtime.records import WorkflowRecords
from agentflow_runtime.planner import DraftPlanner
from agentflow_runtime.rig import analyze_readiness
from agentflow_core import StoreError
from agentflow_core.errors import state_database_error
from agentflow_runtime.discovery import RepoDiscovery, MAX_CONFIG_FILES, MAX_CONFIG_DEPTH

ROOT=Path(__file__).resolve().parents[1]


class F1IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.repo=self.base/'repo';self.repo.mkdir()
        self.home=self.base/'state';(self.repo/'keep.py').write_text('# unchanged\n')
        self.core=LocalCoordinator(self.repo,self.home);self.rec=WorkflowRecords(self.repo,self.home)

    def call(self,*args):
        return process(make_parser().parse_args(['--repo',str(self.repo),'--state-home',str(self.home),*args]))

    def counts(self):
        with closing(self.rec.store.connect(read_only=True)) as cn:
            return {table:cn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in
                    ('tasks','task_aliases','contract_revisions','workflow_documents','operations','audit_events')}

    def test_exact_old_title_and_alias_beyond_500_and_repeated_intake(self):
        title='Khôi phục codec ZYXW987654321'
        old=self.call('interact',title)['task']['task_id']
        self.rec.alias(old,normalize('Biệt danh codec cũ'))
        for i in range(501):self.core.create_task(f'Recent unrelated {i:04d}','Scratch fixture')
        for query in (title,'khoi phuc codec ZYXW987654321','Biệt danh codec cũ'):
            found=TaskNavigator(self.rec).search(query)
            self.assertEqual(found['selected_task_id'],old)
            self.assertEqual(found['search_scope'],'EXACT_ALL_HISTORY')
        before=self.counts();out=self.call('interact',title)
        self.assertEqual(out['action'],'POTENTIAL_EXISTING_TASK');self.assertEqual(self.counts(),before)
        self.assertEqual(self.call('resume',title)['match']['selected_task_id'],old)

    def test_duplicate_exact_titles_do_not_guess_even_with_limit_one(self):
        for i in range(2):self.core.create_task('Same exact title','Scratch fixture')
        out=TaskNavigator(self.rec).search('Same exact title',limit=1)
        self.assertEqual(out['status'],'AMBIGUOUS');self.assertFalse(out['auto_selected'])
        self.assertTrue(out['search_truncated'])

    def test_recent_fuzzy_window_reports_truncation(self):
        for i in range(201):self.core.create_task(f'Recent task {i:04d}','Scratch fixture')
        out=TaskNavigator(self.rec).search('Recent task')
        self.assertTrue(out['search_truncated']);self.assertFalse(out['auto_selected'])

    def test_alias_conflict_leaves_all_state_counts_unchanged(self):
        owner=self.core.create_task('Alias owner','Scratch fixture')['task_id'];self.rec.alias(owner,'collision')
        before=self.counts()
        with self.assertRaises(ConflictError):
            self.rec.create_preflight('Another task','Another request',{'readiness':'NOT_READY'},'collision')
        self.assertEqual(self.counts(),before)

    def test_failure_after_inserts_rolls_back_entire_intake(self):
        with closing(self.rec.store.connect()) as cn:
            cn.execute("CREATE TRIGGER reject_alias BEFORE INSERT ON task_aliases BEGIN SELECT RAISE(ABORT,'injected failure'); END")
        before=self.counts()
        with self.assertRaises(sqlite3.IntegrityError):
            self.rec.create_preflight('New task','New request',{'readiness':'NOT_READY'},'new task')
        self.assertEqual(self.counts(),before)

    def test_discovery_failure_precedes_any_task_creation(self):
        before=self.counts()
        with patch('agentflow_runtime.cli.RepoDiscovery.preflight',side_effect=OSError('injected read failure')):
            with self.assertRaises(OSError):self.call('interact','New task request')
        self.assertEqual(self.counts(),before)

    def test_successful_atomic_intake_is_an_unapproved_preflight(self):
        out=self.call('interact','Thêm nhãn thư viện mới');task=out['task'];stored=self.core.get_task(task['task_id'])
        self.assertEqual((task['revision'],task['lifecycle']),(stored['revision'],stored['lifecycle']))
        self.assertEqual(task['lifecycle'],'PREFLIGHT');self.assertFalse(out['write_authorized'])
        self.assertIsNone(stored['approved_contract_revision'])
        self.assertIsNotNone(self.rec.latest('RIG_BRIEF',task_id=task['task_id']))
        self.assertTrue(self.core.doctor()['healthy'])
        self.assertEqual((self.repo/'keep.py').read_text(),'# unchanged\n')


class F2F4ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.repo=self.base/'repo';self.repo.mkdir();self.home=self.base/'state'
        self.core=LocalCoordinator(self.repo,self.home);self.rec=WorkflowRecords(self.repo,self.home)
        self.tid=self.core.create_task('Plan validation','Scratch fixture')['task_id']

    def cli(self,action,body):
        payload=self.base/'payload.json';payload.write_text(json.dumps(body))
        return subprocess.run([sys.executable,'-B',str(ROOT/'tools/agentflow.py'),'--repo',str(self.repo),
            '--state-home',str(self.home),action,self.tid,str(payload),'--save'],capture_output=True,text=True,timeout=10)

    def test_wrong_plan_JSON_shapes_return_structured_errors_and_save_nothing(self):
        for body in (None,[],42,'wrong',True):
            with self.subTest(body=body):
                out=self.cli('draft-plan',body)
                self.assertEqual(out.returncode,2);self.assertNotIn('Traceback',out.stderr)
                self.assertFalse(json.loads(out.stderr)['write_authorized'])
        self.assertIsNone(self.rec.latest('TECHNICAL_PLAN',task_id=self.tid))

    def test_bad_dependency_and_verification_types_never_save_work_graph(self):
        for deps in ([{}],[[]],[None],[True],'wrong'):
            with self.subTest(deps=deps):
                body={'items':[{'key':'W1','title':'Test work','verification':['test'],'depends_on':deps}]}
                out=self.cli('draft-work',body)
                self.assertEqual(out.returncode,2);self.assertNotIn('Traceback',out.stderr)
                self.assertFalse(json.loads(out.stderr)['write_authorized'])
        for proof in ([None],[{}],[' ']):
            out=self.cli('draft-work',{'items':[{'key':'W1','title':'Test work','verification':proof}]})
            self.assertEqual(out.returncode,2)
        self.assertIsNone(self.rec.latest('WORK_GRAPH',task_id=self.tid))

    def test_empty_placeholder_or_wrong_type_approach_rejected(self):
        for approach in ('',' ','TODO','unknown','<Approach>',None,42,[],{}):
            with self.subTest(approach=approach):
                with self.assertRaises(StoreError):DraftPlanner(self.repo,self.home).plan(self.tid,
                    {'selected_approach':approach,'verification_strategy':['test']},save=True)
        self.assertIsNone(self.rec.latest('TECHNICAL_PLAN',task_id=self.tid))

    def test_bad_scope_items_block_contract_readiness(self):
        base={'analysis_level':'QUICK','objective':'Update library label','acceptance':['Label displays correctly'],
              'preserve':['Existing behavior'],'gaps':[],'open_questions':[]}
        for item in ('',' ',None,42,True,{},[],'<In scope>','TODO'):
            with self.subTest(item=item):
                out=analyze_readiness({**base,'scope':{'functional':[item]}})
                self.assertEqual(out['status'],'NOT_READY');self.assertFalse(out['write_authorized'])
        self.assertEqual(analyze_readiness({**base,'scope':{'functional':['UI']}})['status'],'READY_FOR_HUMAN_REVIEW')

    def test_old_blank_drafts_still_readable_but_new_valid_plan_remains_unapproved(self):
        self.rec.put('TECHNICAL_PLAN',{'selected_approach':'','legacy':True},task_id=self.tid)
        self.assertEqual(self.rec.latest('TECHNICAL_PLAN',task_id=self.tid)['content']['selected_approach'],'')
        valid=DraftPlanner(self.repo,self.home).plan(self.tid,
            {'selected_approach':'Rename','verification_strategy':['test']},save=True,expected_revision=1)
        self.assertEqual(valid['record']['revision'],2);self.assertFalse(valid['can_execute'])
        self.assertIsNone(self.core.get_task(self.tid)['approved_contract_revision'])

    def test_invalid_verification_strategy_cannot_persist_plan(self):
        for proof in (None,'test',[],[None],[{}],['TODO']):
            with self.subTest(proof=proof),self.assertRaises(StoreError):
                DraftPlanner(self.repo,self.home).plan(self.tid,
                    {'selected_approach':'Rename label','verification_strategy':proof},save=True)
        self.assertIsNone(self.rec.latest('TECHNICAL_PLAN',task_id=self.tid))


class F3StateRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.repo=self.base/'repo';self.repo.mkdir();self.home=self.base/'state'
        (self.repo/'keep.py').write_text('# unchanged\n');self.core=LocalCoordinator(self.repo,self.home)

    def cli(self,*args,low_level=False):
        command=([sys.executable,'-B','-m','agentflow_core.cli'] if low_level else
                 [sys.executable,'-B',str(ROOT/'tools/agentflow.py')])
        return subprocess.run(command+['--repo',str(self.repo),'--state-home',str(self.home),*args],
                              cwd=ROOT,capture_output=True,text=True,timeout=10)

    def test_corrupt_and_truncated_state_emit_structured_errors_without_modification(self):
        for content in (b'not a sqlite database\n',b'SQLite format 3\x00'+b'\x00'*48):
            self.core.store.db_file.write_bytes(content)
            for args in (('doctor',),('resume','old work'),('tasks',)):
                with self.subTest(size=len(content),args=args):
                    out=self.cli(*args);self.assertEqual(out.returncode,2);self.assertNotIn('Traceback',out.stderr)
                    body=json.loads(out.stderr);self.assertEqual(body['action'],'RECOVERY_REQUIRED')
                    self.assertFalse(body['healthy']);self.assertFalse(body['write_authorized'])
                    self.assertFalse(body['automatic_repair'])
                    self.assertEqual(self.core.store.db_file.read_bytes(),content)
            self.assertEqual((self.repo/'keep.py').read_text(),'# unchanged\n')

    def test_core_doctor_uses_the_same_controlled_recovery_error(self):
        self.core.store.db_file.write_bytes(b'not a database\n')
        out=self.cli('doctor',low_level=True);self.assertEqual(out.returncode,2)
        self.assertEqual(json.loads(out.stderr)['action'],'RECOVERY_REQUIRED')

    def test_unopenable_state_path_yields_a_structured_error(self):
        self.core.store.db_file.unlink();self.core.store.db_file.mkdir()
        out=self.cli('doctor');self.assertEqual(out.returncode,2)
        self.assertEqual(json.loads(out.stderr)['action'],'RECOVERY_REQUIRED')
        self.assertTrue(self.core.store.db_file.is_dir())

    def test_backup_restores_to_fresh_state_and_refuses_bad_checksum_or_existing_target(self):
        tid=self.core.create_task('Recovery fixture','Keep this task')['task_id']
        rec=WorkflowRecords(self.repo,self.home);rec.put('PROGRESS',{'summary':'Keep checkpoint'},task_id=tid)
        backup=self.core.store.backup();fresh=self.base/'fresh-state'
        with self.assertRaises(StoreError):self.core.store.verify_backup(backup['path'],'0'*64)
        result=self.core.store.restore_to_fresh_state(backup['path'],fresh,backup['sha256'])
        self.assertTrue(result['doctor']['healthy'])
        restored=WorkflowRecords(self.repo,fresh,initialize=False)
        self.assertEqual(restored.latest('PROGRESS',task_id=tid)['content']['summary'],'Keep checkpoint')
        with self.assertRaises(StoreError):self.core.store.restore_to_fresh_state(backup['path'],fresh,backup['sha256'])
        self.assertIsNone(restored.core.get_task(tid)['approved_contract_revision'])

    def test_known_busy_state_is_not_mislabeled_as_corruption_and_SQL_defects_are_not_hidden(self):
        busy=sqlite3.OperationalError('locked');busy.sqlite_errorcode=sqlite3.SQLITE_BUSY
        out=state_database_error(busy);self.assertEqual(out['action'],'RETRY_OR_RECONCILE')
        self.assertFalse(out['recovery_required'])
        syntax=sqlite3.OperationalError('near SELECT: syntax error');syntax.sqlite_errorcode=sqlite3.SQLITE_ERROR
        self.assertIsNone(state_database_error(syntax))

    def test_existing_empty_state_reports_recovery_without_initialization_in_readonly_doctor(self):
        self.core.store.db_file.write_bytes(b'')
        out=self.cli('doctor');self.assertEqual(out.returncode,2)
        self.assertEqual(json.loads(out.stderr)['action'],'RECOVERY_REQUIRED')
        self.assertEqual(self.core.store.db_file.read_bytes(),b'')


class F5DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.repo=self.base/'repo';self.repo.mkdir()

    def create(self,name,data='fixture'):
        p=self.repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data);return p

    def scan(self,names):
        def git(*args):return {'available':True,'output':('\0'.join(names)+'\0').encode() if args[0]=='ls-files' else b''}
        with patch.object(RepoDiscovery,'_git',side_effect=git):return RepoDiscovery(self.repo).scan()

    def test_nested_Cargo_and_CI_paths_are_listed_without_parsing_or_execution(self):
        names=['src/Cargo.toml','src/crates/app/Cargo.toml','.github/workflows/ci.yml','.github/workflows/release.yaml']
        for name in names:self.create(name,'INVALID CONTENT; must not be parsed or executed')
        out=self.scan(names)
        self.assertEqual(set(out['configuration_files']),set(names));self.assertFalse(out['configuration_files_truncated'])
        self.assertIn('Rust',out['languages_observed']);self.assertTrue(out['read_only_intent'])
        self.assertEqual(sorted(p.relative_to(self.repo).as_posix() for p in self.repo.rglob('*') if p.is_file()),sorted(names))

    def test_root_config_and_package_summary_still_work(self):
        self.create('package.json',json.dumps({'scripts':{'test':'must not run'},'dependencies':{'react':'fixture'}}))
        self.create('tsconfig.json')
        out=self.scan(['package.json','tsconfig.json'])
        self.assertEqual(out['configuration_files'],['package.json','tsconfig.json'])
        self.assertEqual(out['package_summary']['scripts'],['test'])

    def test_configuration_count_and_depth_limits_are_explicit(self):
        names=[f'workspace-{i:03d}/Cargo.toml' for i in range(MAX_CONFIG_FILES+2)]
        deep='/'.join(['nested']*(MAX_CONFIG_DEPTH+1)+['Cargo.toml']);names.append(deep)
        for name in names:self.create(name)
        out=self.scan(names)
        self.assertEqual(len(out['configuration_files']),MAX_CONFIG_FILES)
        self.assertNotIn(deep,out['configuration_files']);self.assertTrue(out['configuration_files_truncated'])
        self.assertEqual(out['configuration_limits']['max_depth'],MAX_CONFIG_DEPTH)

    def test_symlink_parent_and_outside_or_traversal_paths_are_excluded(self):
        outside=self.base/'outside';outside.mkdir();(outside/'Cargo.toml').write_text('outside')
        (self.repo/'linked').symlink_to(outside,target_is_directory=True)
        self.create('safe/Cargo.toml');(self.repo/'Cargo.toml').symlink_to(outside/'Cargo.toml')
        out=self.scan(['linked/Cargo.toml','Cargo.toml','safe/Cargo.toml','../outside/Cargo.toml',str(outside/'Cargo.toml')])
        self.assertEqual(out['configuration_files'],['safe/Cargo.toml'])

    def test_tracked_path_truncation_does_not_claim_complete_config_discovery(self):
        self.create('src/Cargo.toml')
        out=self.scan([f'file-{i}.txt' for i in range(2501)]+['src/Cargo.toml'])
        self.assertTrue(out['truncated']);self.assertTrue(out['configuration_files_truncated'])

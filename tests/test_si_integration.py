"""SI01–SI14 local regression: NO production repo, approval, Git mutations or native jobs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agentflow_core import LocalCoordinator
from agentflow_si.foundations import (trust_boundary,capability_observations,metadata_location,
    session_fencing,recovery_status,release_readiness)
from agentflow_si.operations import (mutation_preflight,git_scope_preview,classify_effect,
    action_approval_scope,validate_relative_path)
from agentflow_si.workflow import (evidence_impact,evidence_graph_draft,intent_preview,
    profile_exception_proposal,verification_plan,verification_resource_conflicts)

ROOT=Path(__file__).resolve().parents[1]
A='a'*64
B='b'*64
C='c'*64

class SITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='si-local-')
        self.root=Path(self.tmp.name)
        self.repo=self.root/'repo';self.repo.mkdir()
        self.home=self.root/'state'
        (self.repo/'source.txt').write_text('original\n',encoding='utf-8')
        self.before=self._contents()
    def tearDown(self):
        self.assertEqual(self.before,self._contents(), 'SI preflight unexpectedly changed product file')
        self.tmp.cleanup()
    def _contents(self):return (self.repo/'source.txt').read_text()
    def _hash(self,b):return sha256(b).hexdigest()
    def _proposal(self,**changes):
        base={'task_id':'T-example','spec_sha256':A,'session_id':'codex:S-example',
              'relative_path':'source.txt','before_sha256':self._hash(b'original\n'),
              'after_sha256':B,'resource_generation':1}
        base.update(changes)
        return base

    # SI-01
    def test_si01_trust_denies_by_default(self):
        r=trust_boundary(self.repo,self.home)
        self.assertFalse(r['trusted_approval']);self.assertEqual(r['decision'],'DENY_EXECUTION')
        self.assertFalse(r['code_write_enabled'])
    def test_si01_no_new_ui(self):
        r=trust_boundary(self.repo,self.home)
        self.assertFalse(r['new_user_interface_installed'])
        self.assertFalse(self.home.exists())

    # SI-02
    def test_si02_all_surfaces_uncertified(self):
        r=capability_observations(self.repo,self.home)
        self.assertEqual(len(r['providers']),4)
        self.assertTrue(all(not v['code_write_enabled'] for v in r['providers'].values()))
    def test_si02_input_cannot_certify(self):
        r=capability_observations(self.repo,self.home,{
            'codex_cli':{'version':'99','build':'certified','test_ids':['W2-01']}})
        self.assertEqual(r['providers']['codex_cli']['mode'],'NOT_CERTIFIED')
    def test_si02_rejects_unknown_provider(self):
        with self.assertRaises(ValueError):capability_observations(self.repo,self.home,{'other':{}})
    def test_si02_rejects_bad_hash(self):
        with self.assertRaises(ValueError):capability_observations(self.repo,self.home,{'codex_cli':{'config_sha256':'f'}})

    # SI-03
    def test_si03_stays_outside_repo(self):
        r=metadata_location(self.repo,self.home)
        self.assertTrue(r['state_outside_repo']);self.assertFalse(self.home.exists())
    def test_si03_denies_export_to_worktree(self):
        with self.assertRaises(ValueError):
            metadata_location(self.repo,self.home,export_destination=self.repo/'x.json')
    def test_si03_allows_only_export_plan_outside_repo(self):
        d=self.root/'export.json'
        r=metadata_location(self.repo,self.home,export_destination=d)
        self.assertFalse(r['export_performed']);self.assertFalse(d.exists())
    def test_si03_rejects_state_home_in_repo(self):
        from agentflow_core import StoreError
        with self.assertRaises(StoreError):metadata_location(self.repo,self.repo/'state')

    # SI-04
    def test_si04_preflight_exact_baseline_no_apply(self):
        r=mutation_preflight(self.repo,self._proposal())
        self.assertEqual(r['status'],'PROPOSAL_PRECHECK_ONLY');self.assertFalse(r['applied'])
        self.assertFalse(r['apply_allowed'])
    def test_si04_rejects_stale_baseline(self):
        with self.assertRaises(ValueError):mutation_preflight(self.repo,self._proposal(before_sha256=C))
    def test_si04_rejects_traversal(self):
        for path in ('../outside','src/../source.txt','/tmp/file','x//y','.git/config','abc\\xyz','source.txt/..'):
            with self.subTest(path=path),self.assertRaises(ValueError):validate_relative_path(path)
    def test_si04_rejects_symlink(self):
        (self.repo/'link.txt').symlink_to('source.txt')
        with self.assertRaises(ValueError):mutation_preflight(self.repo,self._proposal(relative_path='link.txt'))
    def test_si04_rejects_hardlink(self):
        os.link(self.repo/'source.txt',self.repo/'alias.txt')
        with self.assertRaises(ValueError):mutation_preflight(self.repo,self._proposal())
    def test_si04_rejects_generation_zero(self):
        with self.assertRaises(ValueError):mutation_preflight(self.repo,self._proposal(resource_generation=0))
    def test_si04_accepts_missing_file_only_as_proposal(self):
        r=mutation_preflight(self.repo,self._proposal(relative_path='new.py',before_sha256='MISSING'))
        self.assertFalse(r['applied']);self.assertFalse((self.repo/'new.py').exists())
    def test_si04_rejects_case_ambiguous_alias(self):
        with self.assertRaises(ValueError):mutation_preflight(self.repo,self._proposal(relative_path='SOURCE.TXT'))

    # SI-05
    def _git(self,*args):
        p=subprocess.run(['git',*args],cwd=self.repo,capture_output=True,text=True,
                         env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
        self.assertEqual(p.returncode,0,p.stderr)
    def test_si05_no_repo_detects_error(self):
        with self.assertRaises(ValueError):git_scope_preview(self.repo,['source.txt'])
    def test_si05_with_untracked_file(self):
        self._git('init','-q')
        r=git_scope_preview(self.repo,['source.txt'])
        self.assertFalse(r['stage_performed']);self.assertTrue(r['all_changes_scoped'])
    def test_si05_other_task_changes_block(self):
        self._git('init','-q')
        (self.repo/'other.txt').write_text('unrelated')
        r=git_scope_preview(self.repo,['source.txt'])
        self.assertIn('other.txt',r['foreign_changes'])
    def test_si05_index_staging_is_visible_but_never_done_by_si(self):
        self._git('init','-q')
        self._git('add','source.txt') # scratch-only test arrangement
        r=git_scope_preview(self.repo,['source.txt'])
        self.assertIn('source.txt',r['preexisting_staged_paths'])
        self.assertFalse(r['commit_performed'])

    # SI-06
    def test_si06_uninitialized_never_grants(self):
        r=session_fencing(self.repo,self.home)
        self.assertEqual(r['state'],'NOT_INITIALIZED');self.assertFalse(r['grants_issued'])
    def test_si06_existing_session_read_only(self):
        c=LocalCoordinator(self.repo,self.home)
        s=c.open_session('claude_cli')
        r=session_fencing(self.repo,self.home,session_id=s['session_id'])
        self.assertEqual(r['sessions'][0]['provider'],'claude_cli')
        self.assertFalse(r['sessions'][0]['execution_authorized'])
    def test_si06_stale_heartbeat_requires_reconciliation(self):
        c=LocalCoordinator(self.repo,self.home)
        s=c.open_session('codex_cli')
        r=session_fencing(self.repo,self.home,session_id=s['session_id'],now_epoch=2**31)
        self.assertTrue(r['sessions'][0]['stale_heartbeat'])
        self.assertFalse(r['sessions'][0]['execution_authorized'])
    def test_si06_foreign_session_rejected(self):
        LocalCoordinator(self.repo,self.home)
        with self.assertRaises(Exception):session_fencing(self.repo,self.home,session_id='other')

    # SI-07
    def test_si07_looks_like_read_not_authorization(self):
        r=classify_effect('cat README.md',declared_effect='READ_ONLY')
        self.assertFalse(r['permission_granted'])
    def test_si07_dynamic_shell_never_readonly(self):
        for cmd in ('python -c print(1)','sh -c echo','cat a | sh','rg TODO && rm x','env cat file'):
            with self.subTest(cmd=cmd):
                r=classify_effect(cmd,declared_effect='READ_ONLY')
                self.assertEqual(r['observed_effect'],'UNKNOWN_OR_DYNAMIC_CHILD_EFFECT')
    def test_si07_invalid_declaration(self):
        with self.assertRaises(ValueError):classify_effect('echo x',declared_effect='SAFE_TO_WRITE')
    def test_si07_git_commit_is_not_read(self):
        self.assertEqual(classify_effect('git commit -m X')['observed_effect'],'T3_SHARED_OR_DESTRUCTIVE')

    # SI-08
    def _graph(self):
        return {'nodes':[{'id':'SPEC','kind':'SPEC','revision':1,'sha256':A,'depends_on':[]},
                        {'id':'PLAN','kind':'PLAN','revision':1,'sha256':B,'depends_on':['SPEC']},
                        {'id':'TEST','kind':'TEST','revision':1,'sha256':C,'depends_on':['PLAN']},
                        {'id':'OTHER','kind':'README','revision':1,'sha256':A,'depends_on':[]}]}
    def test_si08_selective_invalidation(self):
        r=evidence_impact(self._graph(),changed=['SPEC'])
        self.assertEqual(r['affected_nodes'],['PLAN','SPEC','TEST']);self.assertEqual(r['unaffected_nodes'],['OTHER'])
        self.assertFalse(r['promotes_tests_to_pass'])
    def test_si08_no_change_no_invalidation(self):
        self.assertFalse(evidence_impact(self._graph())['requires_reverification'])
    def test_si08_cycle_fails(self):
        g=self._graph();g['nodes'][0]['depends_on']=['TEST']
        with self.assertRaises(ValueError):evidence_impact(g)
    def test_si08_invalid_reference_fails(self):
        g=self._graph();g['nodes'][0]['depends_on']=['MISSING_NODE']
        with self.assertRaises(ValueError):evidence_impact(g)
    def test_si08_duplicate_nodes_fail(self):
        g=self._graph();g['nodes'].append(g['nodes'][0])
        with self.assertRaises(ValueError):evidence_impact(g)

    def test_si08_graph_persisted_as_untrusted_revision(self):
        result=evidence_graph_draft(self.repo,self._graph(),state_home=self.home,save=True)
        self.assertEqual(result['saved_draft']['revision'],1)
        self.assertEqual(result['saved_draft']['status'],'UNTRUSTED_DRAFT')
        self.assertFalse(result['trusted_evidence'])
    def test_si08_graph_rejects_stale_revision(self):
        evidence_graph_draft(self.repo,self._graph(),state_home=self.home,save=True)
        with self.assertRaises(Exception):
            evidence_graph_draft(self.repo,self._graph(),state_home=self.home,save=True)

    # SI-09
    def test_si09_chat_approval_stays_unverified(self):
        r=intent_preview(self.repo,'Duyệt',self.home)
        self.assertFalse(r['approved']);self.assertTrue(r['requires_trusted_channel'])
    def test_si09_question_does_not_create_task(self):
        r=intent_preview(self.repo,'Tại sao ứng dụng chậm?',self.home)
        self.assertFalse(r['task_created'])
    def test_si09_no_user_task_id(self):
        r=intent_preview(self.repo,'Tiếp tục việc sửa đăng nhập',self.home)
        self.assertFalse(r['needs_manual_task_id'])

    # SI-10
    def _exception(self):
        expiry=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        return dict(policy_key='lint.exception',owner='reviewer',reason='Legacy section',
                    scope='src/legacy',expires_at=expiry)
    def test_si10_propose_no_activation(self):
        r=profile_exception_proposal(self.repo,self._exception(),self.home)
        self.assertFalse(r['policy_activated']);self.assertFalse(self.home.exists())
    def test_si10_expired_rejected(self):
        e=self._exception();e['expires_at']='2000-01-01T00:00:00Z'
        with self.assertRaises(ValueError):profile_exception_proposal(self.repo,e,self.home)
    def test_si10_unexpected_status_rejected(self):
        e=self._exception();e['approved']=True
        with self.assertRaises(ValueError):profile_exception_proposal(self.repo,e,self.home)
    def test_si10_save_is_untrusted_external_draft(self):
        r=profile_exception_proposal(self.repo,self._exception(),self.home,save=True)
        self.assertEqual(r['persisted_draft']['status'],'UNTRUSTED_DRAFT');self.assertFalse(r['policy_activated'])
        self.assertEqual({x.name for x in self.repo.iterdir()},{'source.txt'})
    def test_si10_save_same_revision_conflicts(self):
        e=self._exception()
        profile_exception_proposal(self.repo,e,self.home,save=True)
        with self.assertRaises(Exception):profile_exception_proposal(self.repo,e,self.home,save=True)

    # SI-11
    def test_si11_not_initialized_reports_block(self):
        r=recovery_status(self.repo,self.home)
        self.assertFalse(r['doctor']['healthy'])
    def test_si11_existing_state_no_native_audit_attestation(self):
        LocalCoordinator(self.repo,self.home)
        r=recovery_status(self.repo,self.home)
        self.assertTrue(r['doctor']['healthy']);self.assertFalse(r['trusted_audit_attestation'])
    def test_si11_valid_backup_verification_no_restore(self):
        c=LocalCoordinator(self.repo,self.home)
        b=c.store.backup()
        r=recovery_status(self.repo,self.home,backup=b['path'],expected_sha256=b['sha256'])
        self.assertIsNotNone(r['verified_backup']);self.assertFalse(r['automatic_restore'])
    def test_si11_wrong_backup_sha_fails(self):
        c=LocalCoordinator(self.repo,self.home);b=c.store.backup()
        with self.assertRaises(Exception):
            recovery_status(self.repo,self.home,backup=b['path'],expected_sha256=C)

    # SI-12
    def test_si12_action_specific_scopes(self):
        grants={action_approval_scope(x)['required_grant'] for x in ('APPLY_CODE_PATCH','GIT_COMMIT','GIT_PUSH','DEPLOY','MIGRATION','POLICY_CHANGE')}
        self.assertEqual(len(grants),6)
    def test_si12_task_approval_claim_not_code_grant(self):
        r=action_approval_scope('APPLY_CODE_PATCH',claimed_task_approved=True,claimed_grant={'approved':True})
        self.assertFalse(r['authorized']);self.assertTrue(r['claimed_grant_ignored'])
    def test_si12_unknown_action_rejected(self):
        with self.assertRaises(ValueError):action_approval_scope('EXECUTE_ARBITRARY_SHELL')
    def test_si12_read_does_not_grant_runtime_write(self):
        self.assertFalse(action_approval_scope('READ_REPO')['authorized'])

    # SI-13
    def _test_plan(self,prior=None):
        return dict(test_id='test_auth',code_sha256=A,env_sha256=B,
                    resources=['port:12345','db:fixture'],prior_result=prior)
    def test_si13_new_plan_no_execution(self):
        r=verification_plan(self._test_plan())
        self.assertTrue(r['rerun_recommended']);self.assertFalse(r['tests_executed'])
    def test_si13_same_claimed_pass_does_not_trust_reuse(self):
        prior={'code_sha256':A,'env_sha256':B,'reported_status':'PASS',
               'attestation':'VERIFIED_BY_TRUSTED_RUNNER'}
        r=verification_plan(self._test_plan(prior))
        self.assertTrue(r['candidate_reuse']);self.assertFalse(r['trusted_reuse'])
        self.assertTrue(r['rerun_recommended'])
    def test_si13_changed_env_retest(self):
        r=verification_plan(self._test_plan({'code_sha256':A,'env_sha256':C,
                      'reported_status':'PASS','attestation':'CLAIMED'}))
        self.assertFalse(r['candidate_reuse']);self.assertTrue(r['rerun_recommended'])
    def test_si13_invalid_footprint(self):
        t=self._test_plan();t['resources']=['db:x','db:x']
        with self.assertRaises(ValueError):verification_plan(t)

    def test_si13_shared_resource_conflict(self):
        a=self._test_plan();b=self._test_plan();b['test_id']='test_other';b['resources']=['db:fixture']
        r=verification_resource_conflicts([a,b])
        self.assertEqual(len(r['conflicts']),1)
        self.assertFalse(r['resource_isolation_enforced'])
    def test_si13_disjoint_test_resources(self):
        a=self._test_plan();b=self._test_plan();b['test_id']='test_other';b['resources']=['db:other']
        r=verification_resource_conflicts([a,b])
        self.assertEqual(r['recommendation'],'NO_DECLARED_OVERLAP')

    # SI-14
    def test_si14_release_gate_stays_blocked(self):
        r=release_readiness(self.repo,self.home)
        self.assertEqual(r['G2'],'BLOCKED');self.assertFalse(r['ready_for_native_certification_batch'])
        self.assertEqual(r['installer_inspection']['mode'],'GUIDANCE_ONLY')
    def test_si14_cannot_override_certification(self):
        r=release_readiness(self.repo,self.home,observations={
            'codex_desktop':{'version':'certified','build':'pass','test_ids':['all']}})
        self.assertEqual(r['providers']['codex_desktop']['mode'],'NOT_CERTIFIED')
    def test_cli_all_si_actions_present(self):
        from agentflow_runtime.cli import make_parser
        p=make_parser()
        sub=next(a for a in p._actions if getattr(a,'choices',None) and 'si-trust' in a.choices)
        names=[f'si-{x}' for x in ('trust','capabilities','metadata','mutation-plan','git-scope',
               'session','effect','evidence-impact','intent','exception','recovery','action',
               'verification-plan','release-doctor')]
        self.assertEqual(len(names),14)
        self.assertTrue(set(names).issubset(sub.choices))
    def test_cli_si_trust_readonly_smoke(self):
        proc=subprocess.run([sys.executable,str(ROOT/'tools/agentflow.py'),
                             '--repo',str(self.repo),'--state-home',str(self.home),'si-trust'],
                             cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertFalse(json.loads(proc.stdout)['code_write_enabled'])
        self.assertFalse(self.home.exists())

if __name__=='__main__':unittest.main()

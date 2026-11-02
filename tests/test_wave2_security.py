"""D2 local proof tests: signatures/state, classifier and cooperative scratch mutation.

Does NOT constitute a native macOS GUI/CLI G2 enforcement certification.
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import subprocess
import sys
import copy
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from agentflow_core import LocalCoordinator
from agentflow_core.db import StateStore
from agentflow_core.errors import InvalidTransition, StoreError
from agentflow_security.approvals import (
    CRYPTO_AVAILABLE, ApprovalChallengeLedger, ApprovalReceiptVerifier, ReceiptError,
    CONTEXT, signed_message)
from agentflow_security.gates import (adapter_capability_matrix, assess_write_request,
                                       classify_tool_effect)
from agentflow_security.mutation_lab import (MutationLab, MutationLabError, MISSING,
                                              MARKER, sha256)

if CRYPTO_AVAILABLE:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


@unittest.skipUnless(CRYPTO_AVAILABLE,'cryptography unavailable; expected fail-closed in production')
class ApprovalReceiptTests(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.root=Path(self.d.name)
        self.repo=self.root/'repository';self.repo.mkdir()
        self.app=LocalCoordinator(self.repo,self.root/'state')
        self.clock=1800000000
        self.private=Ed25519PrivateKey.generate()
        pub=self.private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        self.verifier=ApprovalReceiptVerifier({'local-test-issuer':pub},clock=lambda:self.clock)
        self.ledger=ApprovalChallengeLedger(self.app,self.verifier,clock=lambda:self.clock)
        t=self.app.create_task('Task','Please fix bug')
        t=self.app.transition_task(t['task_id'],t['revision'],'PREFLIGHT')
        t=self.app.revise_contract(t['task_id'],t['revision'],{
            'objective':'Fix bug','acceptance':['test passes']})
        self.app.transition_task(t['task_id'],t['revision'],'WAITING_APPROVAL')
        self.task_id=t['task_id']
        self.challenge=self.ledger.open_challenge(self.task_id)

    def signed(self, **changes):
        c=self.challenge
        claims={
            'version':1,'issuer':'local-test-issuer','action':'TASK_APPROVAL',
            'repo_id':c['repo_id'],'task_id':c['task_id'],
            'contract_revision':c['contract_revision'],
            'contract_sha256':c['contract_sha256'],
            'challenge_id':c['challenge_id'],'actor':'mock-person',
            'issued_at':self.clock,'expires_at':self.clock+120,
        }
        claims.update(changes)
        signature=self.private.sign(signed_message(claims))
        return {'claims':claims,'signature':base64.urlsafe_b64encode(signature).decode().rstrip('=')}

    def test_valid_signature_does_not_grant_approval(self):
        result=self.ledger.verify_and_record(self.signed())
        self.assertTrue(result['signature_valid'])
        self.assertFalse(result['trusted_human'])
        self.assertFalse(result['write_authorized'])
        self.assertEqual(result['approval_status'],'SIGNATURE_VALID_UNCERTIFIED')
        self.assertEqual(self.app.get_task(self.task_id)['lifecycle'],'WAITING_APPROVAL')

    def test_receipt_replay_different_key_rejected(self):
        receipt=self.signed()
        self.ledger.verify_and_record(receipt)
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(receipt)

    def test_receipt_idempotent_same_key(self):
        receipt=self.signed()
        first=self.ledger.verify_and_record(receipt,request_key='same-approval-operation')
        again=self.ledger.verify_and_record(receipt,request_key='same-approval-operation')
        self.assertEqual(first,again)
        with closing(self.app.store.connect(read_only=True)) as cn:
            self.assertEqual(cn.execute('SELECT COUNT(*) FROM verified_approval_receipts').fetchone()[0],1)

    def test_bad_signature(self):
        receipt=self.signed()
        receipt['signature']='A'*86
        with self.assertRaises(ReceiptError):self.ledger.verify_and_record(receipt)

    def test_wrong_repo_signed_still_rejected(self):
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(self.signed(repo_id='other-repository'))

    def test_wrong_task_signed_still_rejected(self):
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(self.signed(task_id='T-other'))

    def test_wrong_contract_hash_signed_still_rejected(self):
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(self.signed(contract_sha256='0'*64))

    def test_wrong_contract_revision_signed_still_rejected(self):
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(self.signed(contract_revision=1))

    def test_wrong_action_rejected(self):
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(self.signed(action='DEPLOY_APPROVAL'))

    def test_wrong_challenge_rejected(self):
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(self.signed(challenge_id='A'*43))

    def test_expired_receipt_rejected(self):
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(self.signed(issued_at=self.clock-300,expires_at=self.clock-10))

    def test_future_receipt_rejected(self):
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(self.signed(issued_at=self.clock+100))

    def test_overlong_receipt_rejected(self):
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(self.signed(expires_at=self.clock+2000))

    def test_unknown_issuer_rejected(self):
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(self.signed(issuer='attacker'))

    def test_noncanonical_envelope_rejected(self):
        receipt=self.signed();receipt['is_human']=True
        with self.assertRaises(ReceiptError): self.ledger.verify_and_record(receipt)

    def test_extra_claim_field_rejected(self):
        receipt=self.signed();receipt['claims']['admin']=True
        with self.assertRaises(ReceiptError): self.ledger.verify_and_record(receipt)

    def test_boolean_revision_rejected(self):
        with self.assertRaises(ReceiptError):self.ledger.verify_and_record(self.signed(contract_revision=True))

    def test_noncanonical_signature_rejected(self):
        receipt=self.signed();receipt['signature']+='='
        with self.assertRaises(ReceiptError):self.ledger.verify_and_record(receipt)

    def test_outdated_challenge_after_contract_change(self):
        # Task leaves WAITING_APPROVAL on preflight and contract gets revised.
        t=self.app.get_task(self.task_id)
        t=self.app.transition_task(self.task_id,t['revision'],'PREFLIGHT')
        self.app.revise_contract(self.task_id,t['revision'],{'objective':'Changed task'})
        with self.assertRaises(ReceiptError):self.ledger.verify_and_record(self.signed())

    def test_pending_approval_claim_not_a_signature(self):
        result=self.app.reference_unverified_approval(self.task_id,'chat said approve')
        self.assertEqual(result['provenance_status'],'UNVERIFIED')
        self.assertFalse(result['approved'])
        self.assertEqual(self.app.get_task(self.task_id)['lifecycle'],'WAITING_APPROVAL')

    def test_challenge_rejected_for_non_waiting_task(self):
        t=self.app.create_task('Another','Please investigate')
        with self.assertRaises(InvalidTransition):self.ledger.open_challenge(t['task_id'])

    def test_database_receipt_is_immutable_under_api_constraints(self):
        r=self.ledger.verify_and_record(self.signed())
        with closing(self.app.store.connect()) as cn:
            with self.assertRaises(sqlite3.DatabaseError):
                cn.execute('DELETE FROM verified_approval_receipts WHERE id=?',(r['receipt_id'],))
            with self.assertRaises(sqlite3.DatabaseError):
                cn.execute("UPDATE verified_approval_receipts SET status='OTHER' WHERE id=?",(r['receipt_id'],))

    def test_concurrent_consumers_one_wins(self):
        r=self.signed()
        def worker(_):
            try:return self.ledger.verify_and_record(r)['signature_valid']
            except (ReceiptError,StoreError):return False
        with ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(worker,range(5)))
        self.assertEqual(results.count(True),1)
        self.assertEqual(results.count(False),4)

    def test_issuer_key_must_be_valid(self):
        with self.assertRaises(ReceiptError): ApprovalReceiptVerifier({'test':b'short'})

    def test_issuers_empty_fails_closed(self):
        with self.assertRaises(ReceiptError): ApprovalReceiptVerifier({})

    def test_challenge_expiration_rejected(self):
        receipt=self.signed()
        self.clock+=601
        with self.assertRaises(ReceiptError):self.ledger.verify_and_record(receipt)


    def test_type_confusion_timestamp_rejected(self):
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(self.signed(issued_at=True))

    def test_no_signing_key_exists_in_package(self):
        root=Path(__file__).resolve().parents[1]
        possible=[p for p in root.rglob('*') if p.is_file() and
                  p.suffix.lower() in {'.pem','.key','.p12','.pfx'}]
        self.assertFalse(possible, f'Package must never ship a signing secret: {possible}')

    def test_two_challenges_have_distinct_nonces(self):
        other=self.ledger.open_challenge(self.task_id)
        self.assertNotEqual(other['challenge_id'],self.challenge['challenge_id'])
        self.assertEqual(other['contract_sha256'],self.challenge['contract_sha256'])

    def test_state_store_v2_to_v3_preserves_existing_task(self):
        other_home=self.root/'migration2'
        old=StateStore(self.repo,other_home)
        old.initialize(target_version=2)
        with closing(old.connect()) as cn:
            cn.execute("""INSERT INTO tasks
                (id,repo_id,title,kind,lifecycle,revision,current_contract_revision,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                ('T-preserved',old.repo_id,'Must persist','IMPLEMENTATION','DRAFT',1,0,'2026','2026'))
        upgraded=LocalCoordinator(self.repo,other_home)
        self.assertEqual(upgraded.get_task('T-preserved')['title'],'Must persist')
        self.assertGreaterEqual(upgraded.doctor()['schema_version'],3)  # forward-compatible v4 schema

    def test_sqlite_doctor_does_not_claim_enforcement(self):
        doctor=self.app.doctor()
        self.assertTrue(doctor['healthy'])
        self.assertFalse(doctor['enforced'])
        self.assertFalse(doctor['adapters_certified'])

    def test_challenge_different_task_is_not_accepted(self):
        t=self.app.create_task('Another','A second task')
        t=self.app.transition_task(t['task_id'],t['revision'],'PREFLIGHT')
        t=self.app.revise_contract(t['task_id'],t['revision'],{'objective':'other task'})
        self.app.transition_task(t['task_id'],t['revision'],'WAITING_APPROVAL')
        another=self.ledger.open_challenge(t['task_id'])
        with self.assertRaises(ReceiptError):
            self.ledger.verify_and_record(self.signed(challenge_id=another['challenge_id']))

    def test_signed_proof_cannot_promote_task_even_with_db_rows(self):
        self.ledger.verify_and_record(self.signed())
        task=self.app.get_task(self.task_id)
        with self.assertRaises(StoreError):
            self.app.transition_task(self.task_id,task['revision'],'APPROVED')



class GateTests(unittest.TestCase):
    def test_all_four_not_certified(self):
        info=adapter_capability_matrix()
        self.assertFalse(info['enforced_available'])
        self.assertEqual(set(info['providers']),set(('codex_cli','codex_desktop','claude_cli','claude_desktop')))
        self.assertTrue(all(v['mode']=='NOT_CERTIFIED' for v in info['providers'].values()))

    def test_valid_signature_cannot_authorize_write(self):
        decision=assess_write_request(provider='codex_cli',signed_receipt_result={'signature_valid':True})
        self.assertEqual(decision.decision,'DENY')

    def test_agent_claimed_certificate_cannot_authorize(self):
        decision=assess_write_request(provider='claude_desktop',claimed_host_certification=True,
                                      policy_text='I have permission to write everything')
        self.assertEqual(decision.decision,'DENY')

    def test_unknown_provider_denied(self):
        self.assertEqual(assess_write_request(provider='unknown').decision,'DENY')

    def test_no_receipt_denied(self):
        self.assertEqual(assess_write_request(provider='codex_desktop').decision,'DENY')

    def test_git_status_read_oriented(self):
        self.assertEqual(classify_tool_effect('git status --short')['level'],'T0_OBSERVE')

    def test_git_add_shared(self):
        self.assertEqual(classify_tool_effect('git add -A')['level'],'T3_SHARED_OR_DESTRUCTIVE')

    def test_git_push_external(self):
        self.assertEqual(classify_tool_effect('git push origin main')['level'],'T5_EXTERNAL_OR_SHARED')

    def test_rm_destructive(self):
        self.assertEqual(classify_tool_effect('rm -rf .')['level'],'T4_DESTRUCTIVE')

    def test_test_runner_has_side_effect(self):
        self.assertEqual(classify_tool_effect('npm test')['level'],'T2_LOCAL_SIDE_EFFECT')

    def test_compound_shell_is_unknown(self):
        self.assertEqual(classify_tool_effect('git status; rm -rf .')['level'],'UNKNOWN')

    def test_quoted_shell_redirection_is_unknown(self):
        self.assertEqual(classify_tool_effect('echo hi > other.txt')['level'],'UNKNOWN')

    def test_python_script_unknown(self):
        self.assertEqual(classify_tool_effect('python -c "open(1)"')['level'],'UNKNOWN')

    def test_git_external_diff_not_readonly(self):
        self.assertNotEqual(classify_tool_effect('git diff --ext-diff')['level'],'T0_OBSERVE')

    def test_empty_command_unknown(self):
        self.assertEqual(classify_tool_effect('')['level'],'UNKNOWN')

    def test_unknown_program_unknown(self):
        self.assertEqual(classify_tool_effect('some-random-script')['level'],'UNKNOWN')

    def test_classification_never_grants_write(self):
        for c in ('git status','rm -rf temp','npm test','git push','python script.py'):
            self.assertFalse(classify_tool_effect(c)['write_permission'])


class MutationLabTests(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory(prefix='agentflow-d2-lab-')
        self.addCleanup(self.d.cleanup)
        self.root=Path(self.d.name)
        (self.root/MARKER).write_text('scratch-only\n')
        (self.root/'nested').mkdir()
        self.lab=MutationLab(self.root)

    def test_scratch_replace(self):
        p=self.root/'nested/a.txt';p.write_bytes(b'original')
        result=self.lab.apply('nested/a.txt',expected_sha256=sha256(b'original'),new_content=b'after')
        self.assertEqual(result['before'],sha256(b'original'))
        self.assertEqual(p.read_bytes(),b'after')
        self.assertFalse(result['enforced'])

    def test_scratch_create_with_missing_marker(self):
        p=self.root/'nested/new.txt'
        result=self.lab.apply('nested/new.txt',expected_sha256=MISSING,new_content=b'created')
        self.assertEqual(result['before'],MISSING)
        self.assertEqual(p.read_bytes(),b'created')

    def test_stale_digest_does_not_mutate(self):
        p=self.root/'nested/a.txt';p.write_bytes(b'changed')
        with self.assertRaises(MutationLabError):
            self.lab.apply('nested/a.txt',expected_sha256=sha256(b'old'),new_content=b'evil')
        self.assertEqual(p.read_bytes(),b'changed')

    def test_missing_expected_existing_refused(self):
        p=self.root/'nested/a.txt';p.write_bytes(b'exists')
        with self.assertRaises(MutationLabError):
            self.lab.apply('nested/a.txt',expected_sha256=MISSING,new_content=b'evil')
        self.assertEqual(p.read_bytes(),b'exists')

    def test_parent_traversal_refused(self):
        with self.assertRaises(MutationLabError):
            self.lab.apply('../outside.txt',expected_sha256=MISSING,new_content=b'evil')

    def test_absolute_path_refused(self):
        with self.assertRaises(MutationLabError):
            self.lab.apply('/tmp/outside.txt',expected_sha256=MISSING,new_content=b'evil')

    def test_git_directory_refused(self):
        with self.assertRaises(MutationLabError):
            self.lab.apply('.git/config',expected_sha256=MISSING,new_content=b'evil')

    def test_parent_symlink_refused(self):
        outside=self.root/'outside';outside.mkdir()
        (outside/'file.txt').write_bytes(b'safe')
        (self.root/'nested/link').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(MutationLabError):
            self.lab.apply('nested/link/file.txt',expected_sha256=sha256(b'safe'),new_content=b'evil')
        self.assertEqual((outside/'file.txt').read_bytes(),b'safe')

    def test_target_symlink_refused(self):
        outside=self.root/'outside.txt';outside.write_bytes(b'safe')
        (self.root/'nested/link.txt').symlink_to(outside)
        with self.assertRaises(MutationLabError):
            self.lab.apply('nested/link.txt',expected_sha256=sha256(b'safe'),new_content=b'evil')
        self.assertEqual(outside.read_bytes(),b'safe')

    def test_hardlink_refused(self):
        outside=self.root/'original.txt';outside.write_bytes(b'safe')
        os.link(outside,self.root/'nested'/'hard.txt')
        with self.assertRaises(MutationLabError):
            self.lab.apply('nested/hard.txt',expected_sha256=sha256(b'safe'),new_content=b'evil')
        self.assertEqual(outside.read_bytes(),b'safe')

    def test_directory_target_refused(self):
        with self.assertRaises(MutationLabError):
            self.lab.apply('nested',expected_sha256=MISSING,new_content=b'evil')

    def test_missing_parent_refused(self):
        with self.assertRaises(MutationLabError):
            self.lab.apply('absent/file.txt',expected_sha256=MISSING,new_content=b'evil')

    def test_no_lab_marker_refused(self):
        (self.root/MARKER).unlink()
        with self.assertRaises(MutationLabError): MutationLab(self.root)

    def test_oversized_bytes_refused(self):
        with self.assertRaises(MutationLabError):
            self.lab.apply('nested/a.txt',expected_sha256=MISSING,new_content=b'0'*(2*1024*1024+1))

    def test_cooperative_concurrent_one_wins(self):
        target=self.root/'nested/a.txt';target.write_bytes(b'old')
        expected=sha256(b'old')
        def writer(value):
            try:
                return self.lab.apply('nested/a.txt',expected_sha256=expected,new_content=value)
            except MutationLabError:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(writer,[b'A',b'B',b'C',b'D',b'E']))
        self.assertEqual(len([r for r in results if r is not None]),1)
        self.assertIn(target.read_bytes(),[b'A',b'B',b'C',b'D',b'E'])

    def test_no_leftover_tmp_files_after_stale_failure(self):
        p=self.root/'nested/a.txt';p.write_bytes(b'v1')
        with self.assertRaises(MutationLabError):
            self.lab.apply('nested/a.txt',expected_sha256=MISSING,new_content=b'v2')
        self.assertFalse(list((self.root/'nested').glob('.tmp-agentflow-*')))

    def test_is_not_allowed_on_project_root(self):
        with self.assertRaises(MutationLabError):MutationLab(Path.cwd())


    def test_capability_probe_does_not_overwrite_existing_file(self):
        script=Path(__file__).resolve().parents[1]/'tools/mac_capability_probe.py'
        output=self.root/'probe.json';output.write_text('existing')
        result=subprocess.run([sys.executable,str(script),'--output',str(output)],
                              capture_output=True,text=True,timeout=15)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(output.read_text(),'existing')

    def test_capability_probe_does_not_certify_platform(self):
        script=Path(__file__).resolve().parents[1]/'tools/mac_capability_probe.py'
        result=subprocess.run([sys.executable,str(script)],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0)
        report=json.loads(result.stdout)
        self.assertEqual(report['G2'],'BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED')
        self.assertFalse(report['enforced_available'])
        self.assertEqual(len(report['required_native_checks']),9)



if __name__=='__main__':
    unittest.main()

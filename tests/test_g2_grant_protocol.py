"""Negative signed-intent cases. No production keys are created or bundled."""
from __future__ import annotations

import base64
import copy
import secrets
import unittest

from agentflow_security.grant_protocol import (
    CRYPTO_PRESENT, SignedWriteIntentVerifier, GrantProtocolDenied, canonical_claims)
from agentflow_security.hardened_lab import digest

if CRYPTO_PRESENT:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


@unittest.skipUnless(CRYPTO_PRESENT, 'requires optional cryptography module')
class SignedWriteIntentTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()  # ephemeral mock; never written to file
        public = self.private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.verifier = SignedWriteIntentVerifier({'test-authority': public}, clock=lambda: 1800000000)
        self.claims = {
            'version': 1, 'issuer': 'test-authority', 'action': 'FILE_REPLACE',
            'repo_id': 'repo-abc', 'task_id': 'task-1', 'contract_revision': 5,
            'contract_sha256': 'a'*64, 'session_id': 'session-abc',
            'provider': 'claude_cli', 'relative_path': 'src/example.py',
            'before_sha256': digest(b'old'), 'after_sha256': digest(b'new'),
            'resource_id': 'resource:src/example.py', 'fencing_epoch': 12,
            'nonce': secrets.token_urlsafe(20), 'issued_at': 1800000000,
            'expires_at': 1800000060,
        }

    def signed(self, claims=None):
        c = copy.deepcopy(self.claims if claims is None else claims)
        raw = self.private.sign(canonical_claims(c))
        return {'claims': c, 'signature': base64.urlsafe_b64encode(raw).decode().rstrip('=')}

    def expected(self):
        return {k: self.claims[k] for k in (
            'repo_id','task_id','contract_revision','contract_sha256',
            'session_id','provider','relative_path','before_sha256',
            'after_sha256','resource_id','fencing_epoch','nonce')}

    def test_valid_signature_never_authorizes_write(self):
        out = self.verifier.inspect(self.signed(), expected=self.expected())
        self.assertTrue(out['signature_valid'])
        self.assertFalse(out['execution_authorized'])
        self.assertFalse(out['human_approval_verified'])
        self.assertFalse(out['os_write_isolation_verified'])

    def test_mutated_signature(self):
        env = self.signed(); env['signature'] = 'A'*86
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(env, expected=self.expected())

    def test_no_binding_info(self):
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(), expected={})

    def test_agent_provided_key_not_accepted(self):
        env = self.signed(); env['public_key']='fake'
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(env, expected=self.expected())

    def test_reject_extra_claim(self):
        env=self.signed(); env['claims']['admin']=True
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(env, expected=self.expected())

    def test_wrong_spec_hash(self):
        exp=self.expected(); exp['contract_sha256']='b'*64
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(),expected=exp)

    def test_wrong_session(self):
        exp=self.expected(); exp['session_id']='another'
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(),expected=exp)

    def test_stale_fencing_epoch(self):
        exp=self.expected(); exp['fencing_epoch']=13
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(),expected=exp)

    def test_wrong_file(self):
        exp=self.expected(); exp['relative_path']='src/other.py'
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(),expected=exp)

    def test_wrong_patch(self):
        exp=self.expected(); exp['after_sha256']='f'*64
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(),expected=exp)

    def test_wrong_baseline(self):
        exp=self.expected(); exp['before_sha256']='f'*64
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(),expected=exp)

    def test_expected_boolean_revision_cannot_compare_as_integer(self):
        exp=self.expected(); exp['contract_revision']=True
        with self.assertRaises(GrantProtocolDenied):
            self.verifier.inspect(self.signed(), expected=exp)

    def test_expected_boolean_epoch_cannot_compare_as_integer(self):
        exp=self.expected(); exp['fencing_epoch']=True
        with self.assertRaises(GrantProtocolDenied):
            self.verifier.inspect(self.signed(), expected=exp)

    def test_wrong_resource(self):
        exp=self.expected(); exp['resource_id']='resource:other'
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(),expected=exp)

    def test_wrong_nonce(self):
        exp=self.expected(); exp['nonce']='F'*30
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(),expected=exp)

    def test_wrong_action(self):
        c=copy.deepcopy(self.claims); c['action']='DEPLOY'
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(c),expected=self.expected())

    def test_malicious_path(self):
        c=copy.deepcopy(self.claims); c['relative_path']='src/../secrets'
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(c),expected=self.expected())

    def test_expired(self):
        c=copy.deepcopy(self.claims); c['expires_at']=1799999999
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(c),expected=self.expected())

    def test_unknown_issuer(self):
        c=copy.deepcopy(self.claims); c['issuer']='agent'
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(c),expected=self.expected())

    def test_wrong_provider(self):
        c=copy.deepcopy(self.claims); c['provider']='agent'
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(c),expected=self.expected())

    def test_boolean_fencing_epoch_rejected(self):
        c=copy.deepcopy(self.claims); c['fencing_epoch']=True
        with self.assertRaises(GrantProtocolDenied): self.verifier.inspect(self.signed(c),expected=self.expected())

    def test_empty_keyring_denied(self):
        with self.assertRaises(GrantProtocolDenied): SignedWriteIntentVerifier({})


if __name__ == '__main__':
    unittest.main()

class GrantFuzzTests(unittest.TestCase):
    @unittest.skipUnless(CRYPTO_PRESENT, 'requires cryptography')
    def test_all_malformed_python_claims_fail_cleanly(self):
        """A malformed object cannot crash the verifier or grant authority."""
        import math
        key = Ed25519PrivateKey.generate()
        pub = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        verifier = SignedWriteIntentVerifier({'issuer': pub}, clock=lambda: 1800000000)
        base = {
            'version':1,'issuer':'issuer','action':'FILE_REPLACE','repo_id':'r',
            'task_id':'t','contract_revision':1,'contract_sha256':'a'*64,
            'session_id':'s','provider':'codex_cli','relative_path':'src/a',
            'before_sha256':'b'*64,'after_sha256':'c'*64,'resource_id':'r1',
            'fencing_epoch':1,'nonce':'A'*24,'issued_at':1800000000,
            'expires_at':1800000010,
        }
        expected = {k: base[k] for k in (
            'repo_id','task_id','contract_revision','contract_sha256',
            'session_id','provider','relative_path','before_sha256',
            'after_sha256','resource_id','fencing_epoch','nonce')}
        cases = [None,[],{},set(),1,False,0,'',float('nan')]
        checked = 0
        for field in base:
            for val in cases:
                if type(val) is type(base[field]) and val == base[field]:
                    continue
                c=copy.deepcopy(base)
                c[field]=val
                try:
                    sig=base64.urlsafe_b64encode(key.sign(canonical_claims(c))).decode().rstrip('=')
                    envelope={'claims':c,'signature':sig}
                    with self.assertRaises(GrantProtocolDenied):
                        verifier.inspect(envelope, expected=expected)
                except GrantProtocolDenied:
                    pass  # Canonical encoding rejects the value earlier
                checked += 1
        self.assertGreaterEqual(checked, 140)

"""Wave Đ2: signed approval RECEIPT VERIFICATION, not trusted human approval.

An Ed25519 receipt proves possession of a signer key. It does *not* prove that a
human clicked Approve, that a signer key is isolated from agents, or that a DB is
protected from a same-UID agent. Hence results are SIGNATURE_VALID_UNCERTIFIED
and never unlock the D1 protected task states or product writes.

Production needs a separately protected signer + human-presence/provenance UI,
trusted key distribution, independent OS/process identity, and a mandatory
write boundary, all verified on the user's Mac at G2.
"""
from __future__ import annotations

import base64
from contextlib import closing
import json
import re
import secrets
import time
from typing import Callable, Mapping

from agentflow_core.db import canonical_json, digest, utc_now
from agentflow_core.errors import ConflictError, InvalidTransition, StoreError

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    CRYPTO_AVAILABLE = True
except ImportError:
    InvalidSignature = Exception
    Ed25519PublicKey = None
    CRYPTO_AVAILABLE = False

CONTEXT = b'AgentWorkflowV3:approval-receipt:v1\n'
HEX64 = re.compile(r'^[0-9a-f]{64}$')
CLAIMS_KEYS = frozenset({
    'version','issuer','action','repo_id','task_id','contract_revision',
    'contract_sha256','challenge_id','actor','issued_at','expires_at',
})
MAX_LIFETIME_SECONDS = 600


class ReceiptError(StoreError):
    """Untrusted, malformed, stale or misbound approval receipt."""


def decode_b64url(value: str, *, expected_length: int) -> bytes:
    if not isinstance(value, str) or not value or len(value) > 160:
        raise ReceiptError('Invalid encoded signature')
    if re.fullmatch(r'[A-Za-z0-9_-]+', value) is None:
        raise ReceiptError('Non-canonical base64url signature')
    try:
        data = base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
    except (ValueError, base64.binascii.Error) as e:
        raise ReceiptError('Malformed base64url') from e
    if len(data) != expected_length or base64.urlsafe_b64encode(data).decode().rstrip('=') != value:
        raise ReceiptError('Invalid signature length or canonical form')
    return data


def signed_message(claims: dict) -> bytes:
    """Only canonical JSON claims are signed (never a model-generated summary)."""
    if not isinstance(claims, dict) or set(claims) != CLAIMS_KEYS:
        raise ReceiptError('Receipt claims must use the exact schema')
    return CONTEXT + canonical_json(claims).encode('utf-8')


class ApprovalReceiptVerifier:
    """Verifier with externally provisioned issuer keys; never signs receipts.

    Keys passed to this verifier MUST originate from a host-control trust store
    inaccessible to the agent. Using an agent-provided key is NOT authentication.
    """
    def __init__(self, public_keys: Mapping[str, bytes], *, clock: Callable[[], int] | None = None):
        if not CRYPTO_AVAILABLE:
            raise ReceiptError('Ed25519 verifier dependency not installed; failing closed')
        if not public_keys:
            raise ReceiptError('No trusted issuers configured')
        self.keys = {}
        for issuer, raw in public_keys.items():
            if (not isinstance(issuer,str) or not 1 <= len(issuer) <= 80 or
                not isinstance(raw,bytes) or len(raw) != 32):
                raise ReceiptError('Invalid externally provisioned trusted issuer')
            self.keys[issuer] = Ed25519PublicKey.from_public_bytes(raw)
        self.clock = clock or (lambda: int(time.time()))

    def verify(self, receipt: dict, challenge: dict) -> dict:
        if not isinstance(receipt,dict) or set(receipt) != {'claims','signature'}:
            raise ReceiptError('Invalid receipt envelope')
        claims = receipt['claims']
        payload = signed_message(claims)
        if len(payload) > 8192:
            raise ReceiptError('Receipt too large')
        issuer = claims['issuer']
        if not isinstance(issuer,str) or issuer not in self.keys:
            raise ReceiptError('Unknown issuer')
        if (type(claims['version']) is not int or claims['version'] != 1 or
            claims['action'] != 'TASK_APPROVAL'):
            raise ReceiptError('Unsupported receipt version/action')
        if type(claims['contract_revision']) is not int or claims['contract_revision'] < 1:
            raise ReceiptError('Invalid contract revision')
        if not isinstance(claims['contract_sha256'],str) or not HEX64.fullmatch(claims['contract_sha256']):
            raise ReceiptError('Invalid contract hash')
        if (not isinstance(claims['actor'],str) or
            not 1 <= len(claims['actor']) <= 120 or
            any(ord(ch) < 32 for ch in claims['actor'])):
            raise ReceiptError('Invalid actor label')
        if type(claims['issued_at']) is not int or type(claims['expires_at']) is not int:
            raise ReceiptError('Receipt timestamps must be integer seconds')
        now = int(self.clock())
        if (claims['issued_at'] > now + 30 or claims['expires_at'] <= now or
            claims['expires_at'] <= claims['issued_at'] or
            claims['expires_at']-claims['issued_at'] > MAX_LIFETIME_SECONDS):
            raise ReceiptError('Expired, future or overlong receipt')
        binding = {
            'repo_id':challenge['repo_id'], 'task_id':challenge['task_id'],
            'contract_revision':challenge['contract_revision'],
            'contract_sha256':challenge['contract_sha256'],
            'challenge_id':challenge['id'],
            'action':challenge['action'],
        }
        if any(claims.get(k) != v for k,v in binding.items()):
            raise ReceiptError('Receipt does not bind to requested task/spec/challenge')
        if challenge['state'] != 'PENDING' or challenge['expires_at'] <= now:
            raise ReceiptError('Challenge is used/revoked/expired')
        raw_sig = decode_b64url(receipt['signature'],expected_length=64)
        try:
            self.keys[issuer].verify(raw_sig,payload)
        except InvalidSignature as e:
            raise ReceiptError('Invalid Ed25519 signature') from e
        return {'signature_valid':True, 'trusted_human':False,
                'approval_status':'SIGNATURE_VALID_UNCERTIFIED',
                'issuer':issuer,'claims_sha256':digest(claims),
                'write_authorized':False}


class ApprovalChallengeLedger:
    """Challenge/replay prototype in D1 SQLite. Same-UID DB is NOT a trust root."""
    def __init__(self, coordinator, verifier: ApprovalReceiptVerifier, *, clock=None):
        self.coordinator = coordinator
        self.verifier = verifier
        self.clock = clock or (lambda: int(time.time()))

    def open_challenge(self, task_id: str, *, request_key: str | None = None) -> dict:
        store=self.coordinator.store
        payload={'task_id':task_id}
        def handler(cn):
            task=cn.execute('SELECT * FROM tasks WHERE id=? AND repo_id=?',
                            (task_id,store.repo_id)).fetchone()
            if not task or task['lifecycle']!='WAITING_APPROVAL':
                raise InvalidTransition('Task is not waiting for approval')
            contract=cn.execute('SELECT content_sha256 FROM contract_revisions WHERE task_id=? AND revision=?',
                                (task_id,task['current_contract_revision'])).fetchone()
            if not contract:
                raise StoreError('No referenced contract')
            challenge_id=secrets.token_urlsafe(32)
            expires_at=int(self.clock()) + MAX_LIFETIME_SECONDS
            cn.execute('''INSERT INTO approval_challenges
                (id,repo_id,task_id,contract_revision,contract_sha256,action,state,expires_at,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)''',
                (challenge_id,store.repo_id,task_id,task['current_contract_revision'],
                 contract['content_sha256'],'TASK_APPROVAL','PENDING',expires_at,utc_now(store.clock)))
            return {'challenge_id':challenge_id,'task_id':task_id,
                    'contract_revision':task['current_contract_revision'],
                    'contract_sha256':contract['content_sha256'],'repo_id':store.repo_id,
                    'expires_at':expires_at, 'action':'TASK_APPROVAL'}
        return store.mutate('approval.challenge_open',payload,handler,
                            request_key=request_key,entity_id=task_id)

    def verify_and_record(self, receipt: dict, *, request_key: str | None = None) -> dict:
        if not isinstance(receipt,dict) or not isinstance(receipt.get('claims'),dict):
            raise ReceiptError('Invalid receipt')
        challenge_id=receipt['claims'].get('challenge_id')
        if not isinstance(challenge_id,str) or not 20 <= len(challenge_id) <= 80:
            raise ReceiptError('Invalid challenge identifier')
        store=self.coordinator.store
        payload={'receipt':receipt}
        def handler(cn):
            row=cn.execute('SELECT * FROM approval_challenges WHERE id=? AND repo_id=?',
                           (challenge_id,store.repo_id)).fetchone()
            if not row:
                raise ReceiptError('Unknown challenge')
            challenge=dict(row)
            task=cn.execute('SELECT * FROM tasks WHERE id=? AND repo_id=?',
                            (challenge['task_id'],store.repo_id)).fetchone()
            if (not task or task['lifecycle']!='WAITING_APPROVAL' or
                task['current_contract_revision']!=challenge['contract_revision']):
                raise ReceiptError('Task/spec has changed since challenge was issued')
            result=self.verifier.verify(receipt,challenge)
            cn.execute("UPDATE approval_challenges SET state='CONSUMED' WHERE id=? AND state='PENDING'",
                       (challenge_id,))
            if cn.execute('SELECT changes()').fetchone()[0] != 1:
                raise ConflictError('Approval challenge consumed concurrently')
            receipt_id='REC-'+secrets.token_hex(12)
            cn.execute('''INSERT INTO verified_approval_receipts
                (id,challenge_id,issuer,claims_json,signature,claims_sha256,status,recorded_at)
                VALUES(?,?,?,?,?,?,?,?)''',
                (receipt_id,challenge_id,result['issuer'],canonical_json(receipt['claims']),
                 receipt['signature'],result['claims_sha256'],result['approval_status'],utc_now(store.clock)))
            return dict(receipt_id=receipt_id,**result)
        return store.mutate('approval.signature_verify',payload,handler,
                            request_key=request_key,entity_id=challenge_id)

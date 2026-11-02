"""Security-restricted signed write-intent verification protocol, G2 research.

IMPORTANT: This module ONLY proves a signature on an exact proposed write intent.
It NEVER issues a grant or authorizes a mutation, even with a valid signature.
Trust depends on a future protected approval and service key installation, peer
identity checking, one-time use/revocation, session fencing, and mandatory OS
write isolation. The signer private key MUST NOT be included in agent package.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from typing import Mapping, Callable

from .hardened_lab import checked_parts, MISSING, SHA, LabDenied

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    CRYPTO_PRESENT = True
except ImportError:
    Ed25519PublicKey = None
    InvalidSignature = Exception
    CRYPTO_PRESENT = False

PREFIX = b'AgentWorkflowV3:untrusted-write-intent:v1\n'
FIELDS = frozenset({
    'version', 'issuer', 'action', 'repo_id', 'task_id', 'contract_revision',
    'contract_sha256', 'session_id', 'provider', 'relative_path',
    'before_sha256', 'after_sha256', 'resource_id', 'fencing_epoch',
    'nonce', 'issued_at', 'expires_at',
})
PROVIDERS = frozenset({'codex_cli', 'codex_desktop', 'claude_cli', 'claude_desktop'})
MAX_TTL = 60


class GrantProtocolDenied(Exception):
    pass


def canonical_claims(claims: dict) -> bytes:
    if not isinstance(claims, dict) or set(claims) != FIELDS:
        raise GrantProtocolDenied('Exact grant claim schema is required')
    try:
        raw = json.dumps(claims, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                         allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, OverflowError, UnicodeError) as e:
        raise GrantProtocolDenied('Claims cannot be canonically encoded') from e
    if len(raw) > 4096:
        raise GrantProtocolDenied('Claims too large')
    return PREFIX + raw


def strict_b64url(raw: str) -> bytes:
    if not isinstance(raw, str) or len(raw) != 86 or not re.fullmatch('[A-Za-z0-9_-]{86}', raw):
        raise GrantProtocolDenied('Signature encoding invalid')
    try:
        decoded = base64.urlsafe_b64decode(raw + '==')
    except (ValueError, base64.binascii.Error) as e:
        raise GrantProtocolDenied('Signature encoding malformed') from e
    if len(decoded) != 64 or base64.urlsafe_b64encode(decoded).rstrip(b'=').decode('ascii') != raw:
        raise GrantProtocolDenied('Signature encoding noncanonical')
    return decoded


def _str(label: str, value: object, maxlen: int = 128) -> None:
    if (not isinstance(value, str) or not value or len(value) > maxlen or
        any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise GrantProtocolDenied(f'Invalid {label}')


class SignedWriteIntentVerifier:
    """Verification only. Never accept a key supplied with the claimed grant."""
    def __init__(self, trusted_pubkeys: Mapping[str, bytes], *, clock: Callable[[], int] | None = None):
        if not CRYPTO_PRESENT:
            raise GrantProtocolDenied('Ed25519 verification unavailable; deny')
        if not trusted_pubkeys:
            raise GrantProtocolDenied('Trusted signer set unavailable; deny')
        self.keys = {}
        for name, raw in trusted_pubkeys.items():
            _str('issuer', name, 80)
            if not isinstance(raw, bytes) or len(raw) != 32:
                raise GrantProtocolDenied('Invalid public key')
            self.keys[name] = Ed25519PublicKey.from_public_bytes(raw)
        self.clock = clock or (lambda: int(time.time()))

    def inspect(self, envelope: dict, *, expected: dict) -> dict:
        """Verify signature + explicit binding but NEVER promote to authorization."""
        if not isinstance(envelope, dict) or set(envelope) != {'claims', 'signature'}:
            raise GrantProtocolDenied('Bad envelope')
        claims = envelope['claims']
        message = canonical_claims(claims)
        issuer = claims['issuer']
        _str('issuer', issuer, 80)
        if issuer not in self.keys:
            raise GrantProtocolDenied('Issuer not in protected trust store')
        if type(claims['version']) is not int or claims['version'] != 1 or claims['action'] != 'FILE_REPLACE':
            raise GrantProtocolDenied('Wrong protocol/action')
        for name in ('issuer','repo_id','task_id','session_id','resource_id'):
            _str(name, claims[name])
        if not isinstance(claims['provider'], str) or claims['provider'] not in PROVIDERS:
            raise GrantProtocolDenied('Unsupported provider')
        try:
            checked_parts(claims['relative_path'])
        except LabDenied as e:
            raise GrantProtocolDenied('Path is unsafe') from e
        for k in ('contract_sha256','after_sha256'):
            if not isinstance(claims[k], str) or not SHA.fullmatch(claims[k]):
                raise GrantProtocolDenied(f'Invalid {k}')
        if claims['before_sha256'] != MISSING and (
            not isinstance(claims['before_sha256'], str) or not SHA.fullmatch(claims['before_sha256'])
        ):
            raise GrantProtocolDenied('Invalid baseline hash')
        for k in ('contract_revision','fencing_epoch'):
            if type(claims[k]) is not int or claims[k] < 1:
                raise GrantProtocolDenied(f'Invalid {k}')
        if not isinstance(claims['nonce'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{22,90}', claims['nonce']):
            raise GrantProtocolDenied('Invalid nonce')
        issued, expiry = claims['issued_at'], claims['expires_at']
        now = int(self.clock())
        if (type(issued) is not int or type(expiry) is not int or issued > now + 15 or
            expiry <= now or expiry <= issued or expiry-issued > MAX_TTL):
            raise GrantProtocolDenied('Stale/future grant intent')
        if not isinstance(expected, dict) or not expected:
            raise GrantProtocolDenied('Protected binding input required')
        # ALL relevant identifiers must be supplied from the independent trusted
        # session/resource registry. The caller cannot choose only the easy fields.
        required = ('repo_id','task_id','contract_revision','contract_sha256','session_id',
                    'provider','relative_path','before_sha256','after_sha256','resource_id','fencing_epoch','nonce')
        if any(k not in expected or type(claims[k]) is not type(expected[k]) or
               claims[k] != expected[k] for k in required):
            raise GrantProtocolDenied('Mismatch against independent binding')
        try:
            self.keys[issuer].verify(strict_b64url(envelope['signature']), message)
        except InvalidSignature as e:
            raise GrantProtocolDenied('Signature mismatch') from e
        return {
            'signature_valid': True,
            'intent_digest': hashlib.sha256(message).hexdigest(),
            'human_approval_verified': False,
            'one_time_use_verified': False,
            'os_write_isolation_verified': False,
            'execution_authorized': False,
            'status': 'SIGNATURE_VALID_NOT_AN_AUTHORIZATION',
        }

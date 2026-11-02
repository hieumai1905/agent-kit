"""Local transactional SQLite state store; deliberately NOT a security boundary.

Transactions, migration and optimistic versions protect against accidental
concurrent application updates. The same macOS user/process can still tamper
with these files: trusted approval and mandatory write isolation are D2 work.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import uuid
from urllib.parse import quote
from typing import Callable, Any
from contextlib import closing

from .errors import ConflictError, StoreError
from .schema import SCHEMA_VERSION, migrate, migration_digest

GENESIS = '0' * 64


def utc_now(clock=None) -> str:
    moment = clock() if clock else dt.datetime.now(dt.timezone.utc)
    return moment.astimezone(dt.timezone.utc).isoformat(timespec='microseconds')


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode('utf-8')).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def require_key(value: str, name: str, limit: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise StoreError(f'Invalid {name}')
    return value


class StateStore:
    def __init__(self, repo: str | Path, state_home: str | Path | None = None, clock=None):
        self.repo = Path(repo).expanduser().resolve(strict=True)
        if not self.repo.is_dir():
            raise StoreError('Repository path must be a directory')
        self.repo_id = hashlib.sha256(os.fsencode(str(self.repo))).hexdigest()[:32]
        root = (Path(state_home).expanduser() if state_home is not None else
                Path(os.environ.get('AGENTFLOW_STATE_HOME',
                    str(Path.home() / 'Library' / 'Application Support' / 'AgentWorkflowV3'))))
        # A user-chosen path is not allowed to touch the repository working tree.
        self.state_home = root.resolve()
        self.state_dir = self.state_home / 'repositories' / self.repo_id
        if self.state_dir == self.repo or self.repo in self.state_dir.parents:
            raise StoreError('Runtime state must be outside repository working tree')
        self.db_file = self.state_dir / 'state.sqlite3'
        self.clock = clock

    def _mkdir_state(self):
        self.state_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.state_dir.chmod(0o700)

    def connect(self, read_only: bool = False):
        if read_only:
            if not self.db_file.exists():
                raise StoreError('State database is not initialized')
            uri = 'file:' + quote(str(self.db_file), safe='/') + '?mode=ro'
            cn = sqlite3.connect(uri, uri=True, timeout=12, isolation_level=None)
        else:
            self._mkdir_state()
            cn = sqlite3.connect(str(self.db_file), timeout=12, isolation_level=None)
        cn.row_factory = sqlite3.Row
        cn.execute('PRAGMA busy_timeout=12000')
        cn.execute('PRAGMA foreign_keys=ON')
        if not read_only:
            try:
                # Concurrent first opens can get SQLITE_BUSY on journal-mode
                # negotiation before migration obtains its transaction lock.
                deadline=time.monotonic()+12
                while True:
                    try:
                        cn.execute('PRAGMA journal_mode=WAL')
                        break
                    except sqlite3.OperationalError as exc:
                        if getattr(exc,'sqlite_errorcode',None) not in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED) or time.monotonic()>=deadline:
                            raise
                        time.sleep(.02)
                cn.execute('PRAGMA synchronous=FULL')
                self.db_file.chmod(0o600)
            except BaseException:
                cn.close()
                raise
        return cn

    def initialize(self, target_version: int = SCHEMA_VERSION):
        with closing(self.connect()) as cn:
            migrate(cn, target_version=target_version, clock=self.clock)
            cn.execute('BEGIN IMMEDIATE')
            try:
                existing = cn.execute('SELECT canonical_path FROM repositories WHERE id=?',
                                      (self.repo_id,)).fetchone()
                if existing and existing['canonical_path'] != str(self.repo):
                    raise StoreError('Repository identity collision')
                if not existing:
                    cn.execute('INSERT INTO repositories(id,canonical_path,created_at) VALUES(?,?,?)',
                               (self.repo_id, str(self.repo), utc_now(self.clock)))
                cn.execute('COMMIT')
            except BaseException:
                if cn.in_transaction:
                    cn.execute('ROLLBACK')
                raise
        return self

    def _append_audit(self, cn, op_id: str, operation: str, entity_id: str | None, metadata: dict):
        prev = cn.execute('SELECT chain_hash FROM audit_events ORDER BY seq DESC LIMIT 1').fetchone()
        prev_hash = prev['chain_hash'] if prev else GENESIS
        event = dict(op_id=op_id, kind=operation, entity_id=entity_id,
                     payload=metadata, occurred_at=utc_now(self.clock))
        chain_hash = hashlib.sha256((prev_hash + '\n' + canonical_json(event)).encode()).hexdigest()
        cn.execute('''INSERT INTO audit_events
          (op_id,event_kind,entity_id,payload_json,occurred_at,prev_hash,chain_hash)
          VALUES(?,?,?,?,?,?,?)''',
          (op_id, operation, entity_id, canonical_json(metadata), event['occurred_at'], prev_hash, chain_hash))

    def mutate(self, operation: str, payload: dict, handler: Callable,
               *, request_key: str | None = None, entity_id: str | None = None) -> dict:
        require_key(operation, 'operation')
        request_key = require_key(request_key or uuid.uuid4().hex, 'request_key', 160)
        signature = digest(payload)
        with closing(self.connect()) as cn:
            try:
                cn.execute('BEGIN IMMEDIATE')
                previous = cn.execute('SELECT * FROM operations WHERE idempotency_key=?',
                                      (request_key,)).fetchone()
                if previous:
                    if previous['operation'] != operation or previous['payload_hash'] != signature:
                        raise ConflictError('Idempotency key already used for a different operation/payload')
                    result = json.loads(previous['result_json'])
                    cn.execute('COMMIT')
                    return result
                result = handler(cn)
                # The metadata is intentionally minimal; no prompt, policy or secret text in audit.
                self._append_audit(cn, request_key, operation, entity_id,
                                   {'payload_sha256': signature, 'result_sha256': digest(result)})
                cn.execute('''INSERT INTO operations
                    (idempotency_key,operation,payload_hash,result_json,performed_at)
                    VALUES(?,?,?,?,?)''',
                    (request_key, operation, signature, canonical_json(result), utc_now(self.clock)))
                cn.execute('COMMIT')
                return result
            except BaseException:
                if cn.in_transaction:
                    cn.execute('ROLLBACK')
                raise

    def audit_valid(self, cn=None) -> bool:
        own = cn is None
        cn = cn or self.connect(read_only=True)
        try:
            prev = GENESIS
            for row in cn.execute('SELECT * FROM audit_events ORDER BY seq'):
                event = dict(op_id=row['op_id'], kind=row['event_kind'],
                             entity_id=row['entity_id'], payload=json.loads(row['payload_json']),
                             occurred_at=row['occurred_at'])
                expected = hashlib.sha256((prev + '\n' + canonical_json(event)).encode()).hexdigest()
                if row['prev_hash'] != prev or row['chain_hash'] != expected:
                    return False
                prev = row['chain_hash']
            return True
        finally:
            if own:
                cn.close()

    def doctor(self) -> dict:
        if not self.db_file.exists():
            return dict(initialized=False, schema_version=None, healthy=False,
                        reasons=['State store not initialized'],
                        state_dir=str(self.state_dir), repository=str(self.repo),
                        enforced=False)
        with closing(self.connect(read_only=True)) as cn:
            version = cn.execute('PRAGMA user_version').fetchone()[0]
            quick = [r[0] for r in cn.execute('PRAGMA quick_check')]
            foreign = list(cn.execute('PRAGMA foreign_key_check'))
            migration_rows = []
            try:
                migration_rows = list(cn.execute('SELECT version,sha256 FROM schema_migrations'))
            except sqlite3.Error:
                pass
            expected_migrations = (version <= SCHEMA_VERSION and
                len(migration_rows) == version and all(
                r['sha256'] == migration_digest(r['version']) for r in migration_rows
                if 1 <= r['version'] <= SCHEMA_VERSION))
            try:
                audit_ok = self.audit_valid(cn)
            except (sqlite3.Error, json.JSONDecodeError):
                audit_ok = False
            repo_ok = bool(cn.execute('SELECT 1 FROM repositories WHERE id=? AND canonical_path=?',
                                      (self.repo_id, str(self.repo))).fetchone())
            reasons = []
            if version != SCHEMA_VERSION: reasons.append(f'Schema version {version}, expected {SCHEMA_VERSION}')
            if quick != ['ok']: reasons.append('SQLite quick_check failed')
            if foreign: reasons.append('Broken foreign keys')
            if not expected_migrations: reasons.append('Migration checksums mismatch')
            if not audit_ok: reasons.append('Audit integrity check failed')
            if not repo_ok: reasons.append('Repository identity mismatch')
            return dict(initialized=True, schema_version=version, healthy=not reasons,
                        reasons=reasons, state_dir=str(self.state_dir),repository=str(self.repo),
                        tasks=cn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],
                        sessions=cn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],
                        enforced=False, adapters_certified=False,
                        note='D2 verification prototype only; no trusted human approval or mandatory write enforcement.')

    def backup(self) -> dict:
        """Consistent live backup of the state DB, never the product repository."""
        if not self.db_file.exists():
            raise StoreError('State database has not been initialized')
        backups = self.state_dir / 'backups'
        backups.mkdir(mode=0o700, exist_ok=True)
        backups.chmod(0o700)
        path = backups / f"state-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}.sqlite3"
        tmp = path.with_suffix('.tmp')
        try:
            with self.connect(read_only=True) as source:
                with closing(sqlite3.connect(str(tmp))) as target:
                    source.backup(target)
            tmp.chmod(0o600)
            with tmp.open('rb') as durable:
                os.fsync(durable.fileno())
            with closing(sqlite3.connect(str(tmp))) as verify:
                if verify.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise StoreError('Backup integrity check failed')
            os.replace(tmp, path)
            # fsync directory protects renames on commonly used local filesystems.
            dir_fd = os.open(str(backups), os.O_RDONLY)
            try: os.fsync(dir_fd)
            finally: os.close(dir_fd)
            return dict(path=str(path), sha256=file_sha256(path), schema_version=SCHEMA_VERSION)
        finally:
            tmp.unlink(missing_ok=True)

    def verify_backup(self, file: str | Path, expected_sha256: str | None = None) -> dict:
        file = Path(file).expanduser().resolve(strict=True)
        if not file.is_file():
            raise StoreError('Backup must be a regular file')
        calculated = file_sha256(file)
        if expected_sha256 and calculated != expected_sha256:
            raise StoreError('Backup checksum mismatch')
        uri = 'file:' + quote(str(file), safe='/') + '?mode=ro'
        with closing(sqlite3.connect(uri, uri=True)) as cn:
            cn.row_factory = sqlite3.Row
            version = cn.execute('PRAGMA user_version').fetchone()[0]
            if cn.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise StoreError('Backup quick_check failed')
            if list(cn.execute('PRAGMA foreign_key_check')):
                raise StoreError('Backup has invalid foreign key references')
            if not self.audit_valid(cn):
                raise StoreError('Backup audit chain mismatch')
            repo = cn.execute('SELECT canonical_path FROM repositories WHERE id=?',
                              (self.repo_id,)).fetchone()
            if not repo or repo[0] != str(self.repo):
                raise StoreError('Backup repository identity mismatch')
            if version > SCHEMA_VERSION:
                raise StoreError('Backup schema too new for this release')
        return dict(valid=True, sha256=calculated, schema_version=version, path=str(file))

    def restore_to_fresh_state(self, backup_file: str | Path, fresh_state_home: str | Path,
                               expected_sha256: str | None = None) -> dict:
        """Recover into a FRESH directory; never overwrite live state or source code."""
        verified = self.verify_backup(backup_file, expected_sha256)
        recovered = StateStore(self.repo, fresh_state_home, clock=self.clock)
        if recovered.state_dir.exists():
            raise StoreError('Recovery destination already exists; will not overwrite')
        recovered._mkdir_state()
        target = recovered.db_file
        try:
            with open(verified['path'], 'rb') as src, target.open('xb') as dst:
                for chunk in iter(lambda: src.read(1024 * 1024), b''):
                    dst.write(chunk)
                dst.flush()
                os.fsync(dst.fileno())
            target.chmod(0o600)
            with closing(recovered.connect()) as cn:
                migrate(cn, clock=self.clock)
            result = recovered.doctor()
            if not result['healthy']:
                raise StoreError('Restored state failed doctor check')
            return dict(restored_to=str(target), doctor=result)
        except BaseException:
            target.unlink(missing_ok=True)
            raise

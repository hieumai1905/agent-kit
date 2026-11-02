"""Atomic, forward-only SQLite migrations for the D1 local state model.

No migration imports or modifies the old V3 Preview database. Preview and D1
are deliberately separate until a reviewed migration is designed.
"""
from __future__ import annotations

import hashlib

from .errors import StoreError

SCHEMA_VERSION = 4

MIGRATIONS = {
    1: (
        """CREATE TABLE repositories (
            id TEXT PRIMARY KEY, canonical_path TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE tasks (
            id TEXT PRIMARY KEY, repo_id TEXT NOT NULL REFERENCES repositories(id),
            title TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('IMPLEMENTATION','INVESTIGATION')),
            lifecycle TEXT NOT NULL CHECK(lifecycle IN
                ('DRAFT','PREFLIGHT','WAITING_APPROVAL','APPROVED','EXECUTING',
                 'BLOCKED','VERIFYING','COMPLETED','CANCELLED','PAUSED')),
            revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
            current_contract_revision INTEGER NOT NULL DEFAULT 0,
            approved_contract_revision INTEGER,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE contract_revisions (
            task_id TEXT NOT NULL REFERENCES tasks(id), revision INTEGER NOT NULL,
            content_json TEXT NOT NULL, content_sha256 TEXT NOT NULL,
            author_class TEXT NOT NULL DEFAULT 'UNTRUSTED_DRAFT',
            created_at TEXT NOT NULL,
            PRIMARY KEY(task_id, revision)
        )""",
        """CREATE TABLE approval_references (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
            contract_revision INTEGER NOT NULL, claimed_source TEXT NOT NULL,
            provenance_status TEXT NOT NULL CHECK(provenance_status='UNVERIFIED'),
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE sessions (
            id TEXT PRIMARY KEY, repo_id TEXT NOT NULL REFERENCES repositories(id),
            task_id TEXT REFERENCES tasks(id), provider TEXT NOT NULL,
            external_ref TEXT, lifecycle TEXT NOT NULL
              CHECK(lifecycle IN ('ACTIVE','IDLE','PAUSED','DISCONNECTED','CLOSED')),
            revision INTEGER NOT NULL DEFAULT 1,
            heartbeat_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE audit_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, op_id TEXT NOT NULL,
            event_kind TEXT NOT NULL, entity_id TEXT,
            payload_json TEXT NOT NULL, occurred_at TEXT NOT NULL,
            prev_hash TEXT NOT NULL, chain_hash TEXT NOT NULL
        )""",
        """CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events
            BEGIN SELECT RAISE(ABORT,'audit events are append-only'); END""",
        """CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events
            BEGIN SELECT RAISE(ABORT,'audit events are append-only'); END""",
        """CREATE TABLE operations (
            idempotency_key TEXT PRIMARY KEY, operation TEXT NOT NULL,
            payload_hash TEXT NOT NULL, result_json TEXT NOT NULL,
            performed_at TEXT NOT NULL
        )""",
        """CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY, sha256 TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )""",
        """CREATE TRIGGER contracts_immutable_update BEFORE UPDATE ON contract_revisions
            BEGIN SELECT RAISE(ABORT,'contract revisions are immutable'); END""",
        """CREATE TRIGGER contracts_immutable_delete BEFORE DELETE ON contract_revisions
            BEGIN SELECT RAISE(ABORT,'contract revisions are immutable'); END""",
        """CREATE TRIGGER approval_refs_immutable_update BEFORE UPDATE ON approval_references
            BEGIN SELECT RAISE(ABORT,'approval references are immutable'); END""",
        """CREATE TRIGGER approval_refs_immutable_delete BEFORE DELETE ON approval_references
            BEGIN SELECT RAISE(ABORT,'approval references are immutable'); END""",
        """CREATE TRIGGER operations_immutable_update BEFORE UPDATE ON operations
            BEGIN SELECT RAISE(ABORT,'operation records are immutable'); END""",
        """CREATE TRIGGER operations_immutable_delete BEFORE DELETE ON operations
            BEGIN SELECT RAISE(ABORT,'operation records are immutable'); END""",
        """CREATE TRIGGER migrations_immutable_update BEFORE UPDATE ON schema_migrations
            BEGIN SELECT RAISE(ABORT,'migration records are immutable'); END""",
        """CREATE TRIGGER migrations_immutable_delete BEFORE DELETE ON schema_migrations
            BEGIN SELECT RAISE(ABORT,'migration records are immutable'); END""",
        "CREATE INDEX tasks_repo ON tasks(repo_id, updated_at)",
        "CREATE INDEX sessions_task ON sessions(task_id, lifecycle)",
        "CREATE INDEX audit_entity ON audit_events(entity_id, seq)",
    ),
    2: (
        """CREATE TABLE work_items (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
            title TEXT NOT NULL, lifecycle TEXT NOT NULL CHECK(lifecycle IN
               ('PLANNED','READY','CLAIMED','IN_PROGRESS','VERIFYING','COMPLETED',
                'BLOCKED','PAUSED','INVALIDATED','CANCELLED')),
            revision INTEGER NOT NULL DEFAULT 1, plan_revision INTEGER NOT NULL DEFAULT 0,
            owner_session TEXT REFERENCES sessions(id),
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE work_dependencies (
            work_id TEXT NOT NULL REFERENCES work_items(id),
            depends_on_id TEXT NOT NULL REFERENCES work_items(id),
            PRIMARY KEY(work_id, depends_on_id), CHECK(work_id <> depends_on_id)
        )""",
        """CREATE TABLE policy_versions (
            id TEXT PRIMARY KEY, repo_id TEXT NOT NULL REFERENCES repositories(id),
            policy_key TEXT NOT NULL, revision INTEGER NOT NULL,
            content_json TEXT NOT NULL, content_sha256 TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status='PROPOSED'),
            created_at TEXT NOT NULL, UNIQUE(repo_id,policy_key,revision)
        )""",
        """CREATE TABLE artifacts (
            repo_id TEXT NOT NULL REFERENCES repositories(id),
            kind TEXT NOT NULL, artifact_key TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK(revision >= 1),
            content_sha256 TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(repo_id,kind,artifact_key)
        )""",
        """CREATE TABLE evidence (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
            work_item_id TEXT REFERENCES work_items(id), kind TEXT NOT NULL,
            reported_status TEXT NOT NULL CHECK(reported_status IN
               ('PASS','FAIL','NOT_RUN','BLOCKED','UNKNOWN')),
            attestation TEXT NOT NULL CHECK(attestation='UNVERIFIED'),
            metadata_json TEXT NOT NULL, recorded_at TEXT NOT NULL
        )""",
        """CREATE TABLE evidence_dependencies (
            evidence_id TEXT NOT NULL REFERENCES evidence(id),
            repo_id TEXT NOT NULL, kind TEXT NOT NULL, artifact_key TEXT NOT NULL,
            revision INTEGER NOT NULL, content_sha256 TEXT NOT NULL,
            PRIMARY KEY(evidence_id,repo_id,kind,artifact_key)
        )""",
        """CREATE TABLE resource_intents (
            repo_id TEXT NOT NULL REFERENCES repositories(id),
            resource_key TEXT NOT NULL, holder_session TEXT REFERENCES sessions(id),
            task_id TEXT REFERENCES tasks(id), generation INTEGER NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('ACTIVE','RELEASED','SUSPECT')),
            expires_at INTEGER, updated_at TEXT NOT NULL,
            PRIMARY KEY(repo_id,resource_key)
        )""",
        """CREATE TRIGGER policy_versions_immutable_update BEFORE UPDATE ON policy_versions
            BEGIN SELECT RAISE(ABORT,'policy proposals are immutable'); END""",
        """CREATE TRIGGER policy_versions_immutable_delete BEFORE DELETE ON policy_versions
            BEGIN SELECT RAISE(ABORT,'policy proposals are immutable'); END""",
        """CREATE TRIGGER evidence_immutable_update BEFORE UPDATE ON evidence
            BEGIN SELECT RAISE(ABORT,'evidence records are immutable'); END""",
        """CREATE TRIGGER evidence_immutable_delete BEFORE DELETE ON evidence
            BEGIN SELECT RAISE(ABORT,'evidence records are immutable'); END""",
        """CREATE TRIGGER evidence_dependencies_immutable_update BEFORE UPDATE ON evidence_dependencies
            BEGIN SELECT RAISE(ABORT,'evidence references are immutable'); END""",
        """CREATE TRIGGER evidence_dependencies_immutable_delete BEFORE DELETE ON evidence_dependencies
            BEGIN SELECT RAISE(ABORT,'evidence references are immutable'); END""",
        "CREATE INDEX work_by_task ON work_items(task_id,lifecycle)",
        "CREATE INDEX evidence_by_task ON evidence(task_id,recorded_at)",
        "CREATE INDEX policies_by_repo ON policy_versions(repo_id,policy_key,revision)",
        "CREATE INDEX artifacts_by_repo ON artifacts(repo_id,kind)",
    ),
    3: (
        """CREATE TABLE approval_challenges (
            id TEXT PRIMARY KEY,
            repo_id TEXT NOT NULL REFERENCES repositories(id),
            task_id TEXT NOT NULL REFERENCES tasks(id),
            contract_revision INTEGER NOT NULL,
            contract_sha256 TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action='TASK_APPROVAL'),
            state TEXT NOT NULL CHECK(state IN ('PENDING','CONSUMED','REVOKED')),
            expires_at INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE verified_approval_receipts (
            id TEXT PRIMARY KEY,
            challenge_id TEXT NOT NULL UNIQUE REFERENCES approval_challenges(id),
            issuer TEXT NOT NULL,
            claims_json TEXT NOT NULL,
            signature TEXT NOT NULL,
            claims_sha256 TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status='SIGNATURE_VALID_UNCERTIFIED'),
            recorded_at TEXT NOT NULL
        )""",
        """CREATE TRIGGER verified_approval_receipts_no_update BEFORE UPDATE ON verified_approval_receipts
            BEGIN SELECT RAISE(ABORT,'verified receipts are immutable'); END""",
        """CREATE TRIGGER verified_approval_receipts_no_delete BEFORE DELETE ON verified_approval_receipts
            BEGIN SELECT RAISE(ABORT,'verified receipts are immutable'); END""",
        "CREATE INDEX approval_challenges_task ON approval_challenges(task_id,state)",
    ),

    4: (
        """CREATE TABLE workflow_documents (
            id TEXT PRIMARY KEY,
            repo_id TEXT NOT NULL REFERENCES repositories(id),
            scope_key TEXT NOT NULL,
            kind TEXT NOT NULL,
            doc_key TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK(revision>=1),
            content_json TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            trust_status TEXT NOT NULL CHECK(trust_status IN ('UNTRUSTED_DRAFT','OBSERVED','UNVERIFIED_REPORT')),
            created_at TEXT NOT NULL,
            UNIQUE(repo_id,scope_key,kind,doc_key,revision)
        )""",
        """CREATE TABLE task_aliases (
            repo_id TEXT NOT NULL REFERENCES repositories(id),
            alias_norm TEXT NOT NULL,
            task_id TEXT NOT NULL REFERENCES tasks(id),
            created_at TEXT NOT NULL,
            PRIMARY KEY(repo_id,alias_norm)
        )""",
        """CREATE TABLE adapter_observations (
            id TEXT PRIMARY KEY,
            repo_id TEXT NOT NULL REFERENCES repositories(id),
            provider TEXT NOT NULL,
            app_version TEXT NOT NULL,
            observed_json TEXT NOT NULL,
            capability_status TEXT NOT NULL CHECK(capability_status='NOT_CERTIFIED'),
            created_at TEXT NOT NULL
        )""",
        """CREATE TRIGGER workflow_docs_no_update BEFORE UPDATE ON workflow_documents
            BEGIN SELECT RAISE(ABORT,'workflow documents are immutable'); END""",
        """CREATE TRIGGER workflow_docs_no_delete BEFORE DELETE ON workflow_documents
            BEGIN SELECT RAISE(ABORT,'workflow documents are immutable'); END""",
        """CREATE TRIGGER adapter_observations_no_update BEFORE UPDATE ON adapter_observations
            BEGIN SELECT RAISE(ABORT,'adapter observations are immutable'); END""",
        """CREATE TRIGGER adapter_observations_no_delete BEFORE DELETE ON adapter_observations
            BEGIN SELECT RAISE(ABORT,'adapter observations are immutable'); END""",
        "CREATE INDEX workflow_docs_latest ON workflow_documents(repo_id,scope_key,kind,doc_key,revision DESC)",
        "CREATE INDEX task_alias_by_task ON task_aliases(task_id)",
    ),
}


def migration_digest(version: int) -> str:
    return hashlib.sha256("\n".join(MIGRATIONS[version]).encode()).hexdigest()


def migrate(conn, *, target_version: int = SCHEMA_VERSION, clock=None) -> int:
    """Apply migrations atomically; reread version UNDER the write lock.

    Rechecking after BEGIN IMMEDIATE is necessary when multiple processes
    initialize an empty database concurrently. executescript is avoided because
    it can implicitly commit a transaction.
    """
    from .db import utc_now

    if target_version < 1 or target_version > SCHEMA_VERSION:
        raise StoreError(f"Unsupported target schema version: {target_version}")
    try:
        conn.execute('BEGIN IMMEDIATE')
        current = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if current > SCHEMA_VERSION:
            raise StoreError(f"Database from newer version {current}; refusing downgrade")
        if current == 0:
            existing = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )}
            if existing:
                raise StoreError("Unversioned/Preview database detected; explicit import required")
        if current:
            try:
                prior = {r[0]: r[1] for r in conn.execute(
                    'SELECT version,sha256 FROM schema_migrations')}
            except Exception as exc:
                raise StoreError('Migration history unavailable; refusing upgrade') from exc
            if set(prior) != set(range(1, current + 1)) or any(
                    prior[v] != migration_digest(v) for v in prior):
                raise StoreError('Migration history mismatch; refusing upgrade')
        if current < target_version:
            for version in range(current + 1, target_version + 1):
                for statement in MIGRATIONS[version]:
                    conn.execute(statement)
                conn.execute('INSERT INTO schema_migrations(version,sha256,applied_at) VALUES(?,?,?)',
                             (version, migration_digest(version), utc_now(clock)))
                conn.execute(f'PRAGMA user_version = {version}')
        conn.execute('COMMIT')
        return max(current,target_version)
    except BaseException:
        if conn.in_transaction:
            conn.execute('ROLLBACK')
        raise

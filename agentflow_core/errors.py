"""Stable error classes for the state engine."""
import sqlite3


def state_database_error(error):
    """Known state/storage failures only; never hide arbitrary SQL defects."""
    code=getattr(error,'sqlite_errorcode',None)
    primary=code & 0xff if isinstance(code,int) else None
    storage={sqlite3.SQLITE_CORRUPT,sqlite3.SQLITE_NOTADB,sqlite3.SQLITE_CANTOPEN,
             sqlite3.SQLITE_IOERR,sqlite3.SQLITE_READONLY,sqlite3.SQLITE_PERM,
             sqlite3.SQLITE_FULL}
    busy=primary in {sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED}
    incomplete=(primary==sqlite3.SQLITE_ERROR and str(error).startswith('no such table:'))
    if primary not in storage and not busy and not incomplete:
        return None
    return {'error':'StateDatabaseError','message':str(error),
            'sqlite_error':getattr(error,'sqlite_errorname','UNKNOWN'),
            'healthy':False,'action':'RETRY_OR_RECONCILE' if busy else 'RECOVERY_REQUIRED',
            'recovery_required':not busy,'write_authorized':False,
            'next_action':('Wait for the current state operation and retry; do not reset the DB.' if busy else
                'Preserve the original state. Check storage/permissions; verify a known backup with '
                'agentflow_core.cli verify-backup, then restore-new into a fresh --fresh-state-home. '
                'Never delete or overwrite the current DB automatically.'),
            'automatic_repair':False}

class StoreError(Exception):
    """A validated operation could not be completed."""


class ConflictError(StoreError):
    """Optimistic concurrency or idempotency conflict."""


class InvalidTransition(StoreError):
    """State machine rejected a transition."""


class GateNotImplemented(StoreError):
    """A security-sensitive gate belongs to a later certified wave."""

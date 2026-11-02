"""Deterministic allowed transitions. No user-input path grants approval in D1."""
from __future__ import annotations

from .errors import GateNotImplemented, InvalidTransition

TASK_TRANSITIONS = {
    'DRAFT': {'PREFLIGHT', 'CANCELLED'},
    'PREFLIGHT': {'WAITING_APPROVAL', 'PAUSED', 'CANCELLED'},
    'WAITING_APPROVAL': {'APPROVED', 'PREFLIGHT', 'CANCELLED'},
    'APPROVED': {'EXECUTING', 'CANCELLED', 'PAUSED'},
    'EXECUTING': {'BLOCKED', 'VERIFYING', 'PAUSED', 'CANCELLED'},
    'BLOCKED': {'EXECUTING', 'PAUSED', 'CANCELLED'},
    'VERIFYING': {'EXECUTING', 'COMPLETED', 'BLOCKED'},
    'PAUSED': {'PREFLIGHT', 'EXECUTING', 'CANCELLED'},
    'COMPLETED': set(),
    'CANCELLED': set(),
}
SESSION_TRANSITIONS = {
    'ACTIVE': {'IDLE', 'PAUSED', 'DISCONNECTED', 'CLOSED'},
    'IDLE': {'ACTIVE', 'PAUSED', 'DISCONNECTED', 'CLOSED'},
    'PAUSED': {'ACTIVE', 'DISCONNECTED', 'CLOSED'},
    'DISCONNECTED': {'CLOSED'},  # external session identity reconnection in D2
    'CLOSED': set(),
}
WORK_TRANSITIONS = {
    'PLANNED': {'READY', 'BLOCKED', 'CANCELLED', 'INVALIDATED'},
    'READY': {'CLAIMED', 'BLOCKED', 'INVALIDATED', 'CANCELLED'},
    'CLAIMED': {'IN_PROGRESS', 'READY', 'PAUSED', 'INVALIDATED'},
    'IN_PROGRESS': {'VERIFYING', 'BLOCKED', 'PAUSED', 'INVALIDATED'},
    'VERIFYING': {'IN_PROGRESS', 'BLOCKED', 'INVALIDATED'},
    'BLOCKED': {'READY', 'PAUSED', 'INVALIDATED'},
    'PAUSED': {'READY', 'INVALIDATED'},
    'INVALIDATED': {'PLANNED', 'CANCELLED'},
    'COMPLETED': {'INVALIDATED'},
    'CANCELLED': set(),
}

# D1 cannot manufacture trusted approval, authorization, verification or DoD.
PROTECTED_TASK_STATES = {'APPROVED', 'EXECUTING', 'BLOCKED', 'VERIFYING', 'COMPLETED'}
PROTECTED_WORK_STATES = {'CLAIMED', 'IN_PROGRESS', 'VERIFYING', 'COMPLETED'}


def check_transition(kind: str, current: str, next_state: str) -> None:
    transitions = {'task': TASK_TRANSITIONS, 'session': SESSION_TRANSITIONS,
                   'work': WORK_TRANSITIONS}.get(kind)
    if not transitions or current not in transitions:
        raise InvalidTransition(f'Unknown state {kind}:{current}')
    if next_state not in transitions[current]:
        raise InvalidTransition(f'Invalid {kind} transition {current} -> {next_state}')
    if kind == 'task' and next_state in PROTECTED_TASK_STATES:
        raise GateNotImplemented('D2 trusted approval/execution required; D1 cannot advance task')
    if kind == 'work' and next_state in PROTECTED_WORK_STATES:
        raise GateNotImplemented('D5 verified work execution required; D1 cannot advance work item')

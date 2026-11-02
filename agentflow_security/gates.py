"""Conservative tool-effect classification and adapter certification diagnostics.

This module NEVER turns a report, hook event, chat approval, environment flag or
cryptographic signature alone into an executable write grant.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import re
import shlex
import shutil
from typing import Any

PROVIDERS = ('codex_cli','codex_desktop','claude_cli','claude_desktop')
CERTIFICATION = 'NOT_CERTIFIED'


@dataclass(frozen=True)
class CapabilityAssessment:
    provider: str
    host_os: str
    executable_present: bool | None
    mode: str = CERTIFICATION
    approval_provenance: str = 'NOT_TESTED'
    mandatory_write_boundary: str = 'NOT_TESTED'
    native_negative_tests: str = 'NOT_TESTED'
    same_worktree_multiwriter: str = 'NOT_TESTED'


@dataclass(frozen=True)
class GateDecision:
    decision: str
    reason: str
    security_level: str = 'NOT_CERTIFIED'


def adapter_capability_matrix() -> dict[str, Any]:
    # Read-only binary presence is not proof of app support or security.
    host = platform.system()
    seen={'codex_cli': bool(shutil.which('codex')),
          'claude_cli': bool(shutil.which('claude')),
          'codex_desktop': None,'claude_desktop':None}
    result={p:vars(CapabilityAssessment(p,host,seen[p])) for p in PROVIDERS}
    return {
        'host_os':host,
        'host_release':platform.release(),
        'host_arch':platform.machine(),
        'enforced_available':False,
        'status':CERTIFICATION,
        'providers':result,
        'warnings':[
            'CLI binary presence does not authenticate sessions or certify tools.',
            'Model-reported hooks, env vars, config and database flags are not OS enforcement.',
            'Every surface requires native macOS proof for all relevant write paths.',
            'Same-UID application processes can alter same-UID files and invoke local commands.',
            'No dedicated trusted macOS human approval UI/signing realm is installed.',
        ],
    }


def assess_write_request(*, provider: str, signed_receipt_result: dict | None = None,
                         claimed_host_certification: bool = False,
                         policy_text: str | None = None) -> GateDecision:
    """G2 safe default: no runtime has a certified mandatory write boundary yet.

    Deliberately IGNORE untrusted claimant-provided flag/text. A future secure
    broker must take certification from a separate OS-protected trust channel,
    not from this API, a project file or an agent-supplied dict.
    """
    if provider not in PROVIDERS:
        return GateDecision('DENY','Unknown provider / no adapter certification')
    if signed_receipt_result and signed_receipt_result.get('signature_valid'):
        return GateDecision('DENY', 'Signature verification is not trusted human approval or enforced writes')
    return GateDecision('DENY', 'Trusted host approval and mandatory write boundary not certified')


def classify_tool_effect(command: str) -> dict:
    """Conservative *hint*, never security authorization for arbitrary shells.

    Shell metacharacters and programs capable of arbitrary execution are UNKNOWN;
    the classifier is designed to avoid false READ_ONLY classifications, not to
    parse all possible shell, aliases, functions, substitutions or dynamic loading.
    """
    if not isinstance(command,str) or not command.strip() or len(command)>10000:
        return {'level':'UNKNOWN','reason':'Missing or overlong command','write_permission':False}
    # Metacharacters can hide writes even behind a benign prefix. Refuse
    # even quoted meta chars: false positives are safer than accidental allow.
    if any(ch in command for ch in [';', '|', '&', '>', '<', '`', '$', '\\', '\n', '\r']):
        return {'level':'UNKNOWN','reason':'Shell composition/redirection/expansion','write_permission':False}
    try:
        tokens=shlex.split(command,posix=True)
    except ValueError:
        return {'level':'UNKNOWN','reason':'Unparseable shell arguments','write_permission':False}
    if not tokens:
        return {'level':'UNKNOWN','reason':'Empty command','write_permission':False}
    cmd=os.path.basename(tokens[0])
    if cmd == 'git' and len(tokens)>=2:
        second=tokens[1]
        # Git config -c, -C may redirect repo or run custom helpers.
        if second in ('status','diff','log','rev-parse') and all(not t.startswith('--ext-diff')
                            and not t.startswith('--textconv') for t in tokens[2:]):
            return {'level':'T0_OBSERVE','reason':'Read-oriented Git command; config may still invoke helpers','write_permission':False}
        if second in ('add','commit','restore','switch','checkout','stash','reset','clean','rebase','merge','cherry-pick'):
            return {'level':'T3_SHARED_OR_DESTRUCTIVE','reason':'Git index/tree/shared state','write_permission':False}
        if second in ('push','pull','fetch'):
            return {'level':'T5_EXTERNAL_OR_SHARED','reason':'Network/remote state and local Git refs','write_permission':False}
    if cmd in ('rm','rmdir','chmod','chown','sudo','dd','mkfs','shred'):
        return {'level':'T4_DESTRUCTIVE','reason':'Potential destructive or privilege-changing operation','write_permission':False}
    if cmd in ('curl','wget','ssh','scp','rsync'):
        return {'level':'T5_EXTERNAL_OR_SHARED','reason':'External I/O or potentially mutating transfer','write_permission':False}
    if cmd in ('pytest','npm','pnpm','yarn','cargo','make','gradle','mvn','go'):
        return {'level':'T2_LOCAL_SIDE_EFFECT','reason':'Build/test tool can write outputs, caches, fixtures or services','write_permission':False}
    if cmd in ('cat','head','tail','grep','rg','wc','pwd') and not any(t.startswith('-exec') for t in tokens[1:]):
        return {'level':'T0_OBSERVE','reason':'Read-oriented command; still not a permission grant','write_permission':False}
    return {'level':'UNKNOWN','reason':'Tool behavior not safely classified','write_permission':False}

"""SI-04/05/07/12: read-only mutation, Git, tool and action preflight.

No function in this module performs a product filesystem mutation, staging,
commit, push or action authorization. Intentional: G2 is NOT_CERTIFIED.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import subprocess
import unicodedata

from agentflow_security.gates import classify_tool_effect

_HEX = re.compile(r'^[a-f0-9]{64}$')
_MISSING = 'MISSING'
_ACTIONS = {
    'READ_REPO': ('T0_OBSERVE','NO_CHANGE_APPROVAL'),
    'RUN_TEST': ('T2_LOCAL_SIDE_EFFECT','EXPLICIT_TEST_FOOTPRINT_GRANT'),
    'APPLY_CODE_PATCH': ('T2_LOCAL_SIDE_EFFECT','TRUSTED_SPEC_AND_SCOPED_MUTATION_GRANT'),
    'GIT_STAGE': ('T3_SHARED_OR_DESTRUCTIVE','TASK_SCOPED_GIT_GRANT'),
    'GIT_COMMIT': ('T3_SHARED_OR_DESTRUCTIVE','SEPARATE_COMMIT_GRANT'),
    'GIT_PUSH': ('T5_EXTERNAL_OR_SHARED','SEPARATE_PUSH_GRANT'),
    'DEPLOY': ('T5_EXTERNAL_OR_SHARED','SEPARATE_DEPLOY_GRANT'),
    'MIGRATION': ('T4_DESTRUCTIVE','SEPARATE_MIGRATION_GRANT'),
    'POLICY_CHANGE': ('T4_DESTRUCTIVE','SEPARATE_POLICY_ADMIN_GRANT'),
}


def validate_relative_path(relative: str) -> tuple[str, ...]:
    if not isinstance(relative, str) or not relative or len(relative)>1024 or '\\' in relative:
        raise ValueError('Invalid relative path')
    if unicodedata.normalize('NFC', relative)!=relative:
        raise ValueError('Noncanonical unicode path')
    if any(ord(x)<32 for x in relative):
        raise ValueError('Control character path')
    posix=PurePosixPath(relative)
    if posix.is_absolute() or not posix.parts or any(x in ('.','..','') for x in relative.split('/')):
        raise ValueError('Noncanonical or traversal path')
    if any(x.casefold() in ('.git','.agentflow') for x in posix.parts):
        raise ValueError('Git/internal metadata cannot be modified as product files')
    if any(x.endswith(' ') or x in ('~','') for x in posix.parts):
        raise ValueError('Unsafe path segment')
    return posix.parts


def mutation_preflight(repo, request: dict) -> dict:
    """SI-04: hash/check scope of a patch *proposal*; never apply it.

    Check-use race remains possible because no native mandatory write boundary
    exists here. Passing this check is NEVER sufficient to issue a grant.
    """
    if not isinstance(request,dict):raise ValueError('Expected mutation request object')
    if set(request) != {'task_id','spec_sha256','session_id','relative_path',
                        'before_sha256','after_sha256','resource_generation'}:
        raise ValueError('Missing/extra mutation proposal fields')
    for k in ('spec_sha256','after_sha256'):
        if not isinstance(request[k],str) or not _HEX.fullmatch(request[k]):
            raise ValueError('Invalid '+k)
    if request['before_sha256']!=_MISSING and (not isinstance(request['before_sha256'],str)
        or not _HEX.fullmatch(request['before_sha256'])):
        raise ValueError('Invalid before_sha256')
    for k in ('task_id','session_id'):
        if not isinstance(request[k],str) or not 1<=len(request[k])<=100 or any(ord(c)<32 for c in request[k]):
            raise ValueError('Invalid '+k)
    if isinstance(request['resource_generation'],bool) or not isinstance(request['resource_generation'],int) or request['resource_generation']<1:
        raise ValueError('Invalid fencing generation')
    parts=validate_relative_path(request['relative_path'])
    root=Path(repo).expanduser().resolve(strict=True)
    if not root.is_dir():raise ValueError('Repository must be a directory')
    parent=root
    for part in parts[:-1]:
        child=parent/part
        st=child.lstat()             # no symlink resolution
        if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
            raise ValueError('Not a safe parent directory')
        parent=child
    # Defend casefold aliases in preflight; native broker must do fd-relative
    # revalidation immediately before an actual apply.
    if any(p.casefold()==parts[-1].casefold() and p!=parts[-1] for p in os.listdir(parent)):
        raise ValueError('Casefold ambiguity')
    path=parent/parts[-1]
    try:
        st=path.lstat()
    except FileNotFoundError:
        actual=_MISSING
    else:
        if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size>8*1024*1024:
            raise ValueError('Not a safe regular, singly-linked, bounded target')
        fd=os.open(str(path),os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
        try:
            opened=os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or opened.st_nlink!=1 or (opened.st_dev,opened.st_ino)!=(st.st_dev,st.st_ino):
                raise ValueError('Target changed while inspected')
            hasher=hashlib.sha256()
            while True:
                chunk=os.read(fd,65536)
                if not chunk:break
                hasher.update(chunk)
        finally:os.close(fd)
        actual=hasher.hexdigest()
    if actual!=request['before_sha256']:
        raise ValueError('Stale baseline: compare-and-apply would refuse patch')
    return {'si':'SI-04','status':'PROPOSAL_PRECHECK_ONLY','path':str(PurePosixPath(*parts)),
            'observed_before_sha256':actual,'proposed_after_sha256':request['after_sha256'],
            'fencing_generation_claimed':request['resource_generation'],
            'os_boundary_verified':False,'grant_issued':False,'applied':False,
            'apply_allowed':False,'race_free':False,
            'required_next':'TRUSTED_BROKER_WITH_RECHECK_AND_FENCING'}


def git_scope_preview(repo, allowed_paths: list[str]) -> dict:
    """SI-05: analyze changed paths without staging or changing Git settings.

    Runs git status with optional locks disabled. This is best-effort inspection,
    not a security proof against hostile git binaries or repo configuration.
    """
    if not isinstance(allowed_paths,list) or len(allowed_paths)>500:
        raise ValueError('allowed_paths must be a bounded list')
    approved={'/'.join(validate_relative_path(x)) for x in allowed_paths}
    root=Path(repo).expanduser().resolve(strict=True)
    env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','GIT_TERMINAL_PROMPT':'0',
         'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull}
    cmd=['git','-c','core.fsmonitor=false','-c','core.untrackedCache=false',
         '-c','core.hooksPath=/dev/null','--no-optional-locks',
         'status','--porcelain=v1','-z','--untracked-files=all']
    try:
        p=subprocess.run(cmd,cwd=root,env=env,stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,timeout=8,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise ValueError('Unable to inspect Git status: '+type(exc).__name__) from exc
    if p.returncode or len(p.stdout)>4*1024*1024:
        raise ValueError('Git status failed / oversized response')
    pieces=p.stdout.split(b'\x00');entries=[];idx=0
    while idx<len(pieces):
        raw=pieces[idx];idx+=1
        if not raw:break
        if len(raw)<4 or raw[2:3]!=b' ':
            raise ValueError('Unexpected git porcelain record')
        xy=raw[:2].decode('ascii',errors='replace')
        file=raw[3:].decode('utf-8',errors='surrogateescape')
        extra=None
        if 'R' in xy or 'C' in xy:
            if idx>=len(pieces) or not pieces[idx]:raise ValueError('Malformed rename record')
            extra=pieces[idx].decode('utf-8',errors='surrogateescape');idx+=1
        entries.append({'path':file,'previous_path':extra,'index_status':xy[0],
                        'worktree_status':xy[1],
                        'within_task_scope':file in approved and (extra is None or extra in approved)})
    foreign=[x['path'] for x in entries if not x['within_task_scope']]
    staged=[x['path'] for x in entries if x['index_status'] not in (' ','?')]
    return {'si':'SI-05','entries':entries,'foreign_changes':foreign,
            'preexisting_staged_paths':staged,'all_changes_scoped':not foreign,
            'stage_performed':False,'commit_performed':False,'push_performed':False,
            'task_scoped_git_grant':False,'recommendation':
                'BLOCK_AND_RECONCILE' if foreign or staged else 'DRY_RUN_ONLY'}


def classify_effect(command: str, *, declared_effect=None) -> dict:
    """SI-07: child/shell and user-supplied manifest never authorize a write."""
    old=classify_tool_effect(command)
    try:parts=shlex.split(command)
    except (TypeError,ValueError):parts=[]
    wrapper={'sh','bash','zsh','fish','python','python3','node','ruby','perl','env','xargs','find','parallel','eval','osascript','open','sudo','npx','pip','pip3'}
    base=os.path.basename(parts[0]) if parts else ''
    if base in wrapper or any(x in command for x in ('&&','||','|',';','$(', '`','>','<','\n')):
        observed='UNKNOWN_OR_DYNAMIC_CHILD_EFFECT'
    else:
        observed=old['level']
    declared = (str(declared_effect) if declared_effect is not None else 'UNSPECIFIED')
    if declared not in ('UNSPECIFIED','READ_ONLY','LOCAL_SIDE_EFFECT','SHARED_STATE','NETWORK','DESTRUCTIVE'):
        raise ValueError('Unknown tool effect declaration')
    return {'si':'SI-07','observed_effect':observed,
            'declared_effect':declared,'command_name':base,
            'child_commands_verified':False,'shell_effects_exhaustively_analyzed':False,
            'permission_granted':False,
            'decision':'DENY_EXECUTION' if observed!='T0_OBSERVE' else 'OBSERVE_HINT_NOT_AUTHORIZATION',
            'note':'Command and declaration are not a complete side-effect proof.'}


def action_approval_scope(action: str, *, claimed_task_approved=False, claimed_grant=None) -> dict:
    """SI-12: distinct action-specific authorizations, no chat-based grant."""
    if action not in _ACTIONS:raise ValueError('Unknown action')
    effect,required=_ACTIONS[action]
    return {'si':'SI-12','action':action,'effect':effect,'required_grant':required,
            'task_approval_claim':bool(claimed_task_approved),
            'claimed_grant_ignored':claimed_grant is not None,
            'can_use_task_approval_for_action':False if action!='READ_REPO' else None,
            'decision':'READ_INTENT_ONLY' if action=='READ_REPO' else 'DENY_UNTIL_TRUSTED_ACTION_AUTHORITY',
            'authorized':False,
            'note':'No user-visible UI or approval dialogue is created by SI contract.'}

"""Small, read-only practical workflow views for existing agent chats/terminals.

No command here executes a provider, edits repository files, grants approvals,
records PASS, stages Git or launches processes other than read-only Git queries.
"""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
from .navigator import TaskNavigator, resume_query
from .records import WorkflowRecords
from .handoff import HandoffBuilder
from .review import EvidenceReviewer

MAX_OUTPUT=1024*1024

def _git(repo:Path, *args):
    env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','GIT_TERMINAL_PROMPT':'0',
         'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull,
         'GIT_LFS_SKIP_SMUDGE':'1'}
    cmd=['git','-c','core.fsmonitor=false','-c','core.untrackedCache=false',
         '-c','core.hooksPath=/dev/null','--no-optional-locks',*args]
    try:
        p=subprocess.run(cmd,cwd=repo,stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         env=env,timeout=6,check=False)
    except (OSError,subprocess.TimeoutExpired):return None
    if p.returncode or len(p.stdout)>MAX_OUTPUT:return None
    return p.stdout

def git_snapshot(repo)->dict:
    """Bounded Git metadata: no diff content, no secrets, no write claims."""
    root=Path(repo).expanduser().resolve(strict=True)
    if not root.is_dir():raise ValueError('Not a repository directory')
    status=_git(root,'status','--porcelain=v1','-z','--untracked-files=normal')
    if status is None:
        return {'git_available':False,'read_only':True,'write_authorized':False,
                'warning':'Git not available or status failed; no clean tree claim'}
    head=_git(root,'rev-parse','--verify','HEAD')
    branch=_git(root,'symbolic-ref','--short','HEAD')
    tokens=status.split(b'\0');idx=0;entries=[]
    while idx<len(tokens):
        row=tokens[idx];idx+=1
        if not row:break
        if len(row)<4 or row[2:3]!=b' ':
            return {'git_available':True,'status':'PARSE_ERROR','read_only':True,
                    'write_authorized':False,'warning':'Unexpected porcelain record'}
        xy=row[:2].decode('ascii',errors='replace')
        filename=row[3:].decode('utf-8',errors='replace')
        previous=None
        if 'R' in xy or 'C' in xy:
            if idx>=len(tokens) or not tokens[idx]:
                return {'git_available':True,'status':'PARSE_ERROR','read_only':True,'write_authorized':False}
            previous=tokens[idx].decode('utf-8',errors='replace');idx+=1
        entries.append({'xy':xy,'path':filename,'previous':previous})
        if len(entries)>=120:break
    return {'git_available':True,'head':head.decode().strip() if head else None,
            'branch':branch.decode().strip() if branch else '(detached/unborn)',
            'worktree_changes':entries,'changes_truncated':len(entries)>=120,
            'read_only':True,'write_authorized':False,
            'warning':'Status is a snapshot, not a lock. Recheck before any provider write.'}


def resume_view(repo,state_home,query):
    """Natural-language task lookup; don't invent links when there is ambiguity."""
    records=WorkflowRecords(repo,state_home,initialize=False)
    if not records.store.db_file.exists():
        return {'action':'NO_MATCH','match':{'status':'STATE_NOT_INITIALIZED','choices':[],
                    'auto_selected':False,'requires_confirmation':False},
                'new_task_created':False,'approval_preserved_as_authorization':False,
                'write_authorized':False,
                'instructions':'No existing state to resume. Do not create a task from a resume request; clarify the work or state location.'}
    lookup=resume_query(query)
    match=TaskNavigator(records).search(lookup)
    if not lookup and match['choices']:
        match={**match,'status':'RECENT_REQUIRES_CHOICE','requires_confirmation':True,'query_matched':False}
    if match['status']=='NO_MATCH':
        recent=TaskNavigator(records).search('')
        if recent['choices']:
            match={**recent,'status':'RECENT_REQUIRES_CHOICE','requires_confirmation':True,
                   'query_matched':False}
    if match['status']!='UNAMBIGUOUS':
        return {'action':'CHOOSE_TASK' if match.get('choices') else 'NO_MATCH',
                'match':match,'new_task_created':False,'approval_preserved_as_authorization':False,
                'instructions':'Choose an existing task using its title, not its ID; do not guess.'}
    task_id=match['selected_task_id']
    packet=HandoffBuilder(repo,state_home,initialize=False).packet(task_id)
    return {'action':'RESUME_READ_ONLY','match':match,
            'handoff':packet,'git':git_snapshot(repo),
            'write_authorized':False,
            'instructions':'Check current scope/diff and approvals in the CURRENT provider before editing; this untrusted snapshot is not a grant.'}


def final_review_view(repo,state_home,task_id):
    """A compact, honest acceptance view: no synthetic PASS or fake DoD."""
    evidence=EvidenceReviewer(repo,state_home).evaluation(task_id)
    packet=HandoffBuilder(repo,state_home).packet(task_id)
    criteria=evidence.get('requirements',[])
    return {'task_id':task_id,'objective':packet['contract']['objective'],
            'status_view':evidence['status_view'],
            'acceptance_criteria':[{'criterion':x,'verification':'UNVERIFIED_IN_THIS_KIT'} for x in criteria],
            'reported_evidence':evidence['reported_evidence'],
            'review_status':evidence['review_status'],
            'definition_of_done':evidence['definition_of_done'],
            'git':git_snapshot(repo),'known_limits':['NO_TRUSTED_NATIVE_APPROVAL',
               'NO_CERTIFIED_MUTATION_BROKER','NO_AUTOMATED_PRODUCTION_VERIFICATION'],
            'recommended_next':'Have the agent show the exact diff and real test output in Codex/Claude; user decides acceptance. Commit/push/deploy remain separate.',
            'auto_complete':False,'auto_release':False}

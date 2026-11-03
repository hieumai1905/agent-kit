"""Bounded file-plan refinements under an unchanged user contract.

These are unverified observations, not semantic approval or a protected writer.
The default remains exact files. Nothing infers a policy for an old contract.
"""
from pathlib import Path, PurePosixPath
from agentflow_core import StoreError, ConflictError
from agentflow_core.db import digest
from .sources import registry, paths

SCHEMA='agentflow.implementation.v1'
SENSITIVE_PARTS={'.git','.github','.gitlab','migrations','migration','auth','authentication',
                 'authorization','security','permissions','payment','payments','secrets','config'}
SENSITIVE_NAMES={'package.json','package-lock.json','pnpm-lock.yaml','yarn.lock','pyproject.toml',
                 'poetry.lock','uv.lock','cargo.toml','cargo.lock','go.mod','go.sum','dockerfile',
                 'docker-compose.yml','docker-compose.yaml','tsconfig.json'}
CODE_SUFFIXES={'.py','.ts','.tsx','.js','.jsx','.mjs','.cjs','.cs','.rs','.go','.java','.kt',
               '.swift','.vue','.svelte','.html','.css','.scss','.md','.txt','.json'}


def protected(name):
    p=PurePosixPath(name);parts={x.casefold() for x in p.parts};base=p.name.casefold()
    return (bool(parts&SENSITIVE_PARTS) or base in SENSITIVE_NAMES or base.startswith(('.env','requirements'))
            or base.endswith(('.sql','.sh','.ps1','.csproj','.props','.targets'))
            or any(x in base for x in ('migration','permission','auth','security','payment','config','settings','credential','secret'))
            or p.suffix.casefold() not in CODE_SUFFIXES)


def policy(contract, anchor):
    value=contract.get('implementation_policy')
    if value is None:return {'mode':'EXACT','repositories':{}}
    if not isinstance(value,dict) or set(value)-{'mode','repositories'}:
        raise StoreError('implementation_policy: expected mode and optional repositories only')
    mode=value.get('mode')
    if mode=='EXACT':
        if value.get('repositories'):raise StoreError('EXACT policy cannot include refinement allowances')
        return {'mode':'EXACT','repositories':{}}
    if mode!='SCOPED_REFINEMENTS':raise StoreError('implementation_policy.mode: EXACT or SCOPED_REFINEMENTS')
    base={r['key']:r for r in registry(contract,anchor)};rows=value.get('repositories')
    if not isinstance(rows,dict) or not rows or set(rows)-set(base):
        raise StoreError('implementation_policy.repositories: use existing contract repo keys')
    result={}
    for key,row in rows.items():
        if not isinstance(row,dict) or set(row)-{'allow_under','support_files'}:
            raise StoreError('Refinement allowance accepts allow_under and support_files only')
        prefixes=paths(row.get('allow_under',[]),'allow_under')
        support=paths(row.get('support_files',[]),'support_files')
        if len(prefixes)>16 or len(support)>32 or not prefixes and not support:
            raise StoreError('Keep refinement allowances bounded: 1..16 component directories or 1..32 support files')
        for name in prefixes:
            if name=='.' or protected(name+'/component.py'):
                raise StoreError('Refinement directory is broad/protected: '+name)
            p=Path(base[key]['root'])/name
            walk=Path(base[key]['root'])
            for part in PurePosixPath(name).parts:
                walk=walk/part
                if walk.is_symlink():raise StoreError('Refinement directory cannot traverse symlinks')
            if p.exists() and not p.is_dir():raise StoreError('allow_under must name component directories')
        if any(protected(name) for name in support):
            raise StoreError('Protected dependency/security/config/migration files require explicit contract write_paths')
        result[key]={'allow_under':prefixes,'support_files':support}
    return {'mode':mode,'repositories':result}


def _entries(contract, anchor, proposed, required=None):
    base=registry(contract,anchor);candidate=registry({**contract,'repositories':proposed},anchor)
    bykey={r['key']:r for r in base};rules=policy(contract,anchor)
    if {r['key'] for r in candidate}!=set(bykey):raise StoreError('Implementation refinement cannot add/remove repository roots')
    previous={r['key']:r for r in required or base}
    for row in candidate:
        key=row['key'];old=bykey[key];prior=previous[key]
        if row['root']!=old['root']:raise StoreError('Implementation refinement cannot change a Git root')
        for field in ('write_paths','read_paths'):
            if not set(prior[field])<=set(row[field]):raise StoreError('Implementation refinement cannot remove/downgrade observed files')
        allowance=rules['repositories'].get(key,{})
        for name in set(row['write_paths'])-set(old['write_paths']):
            if name in old['read_paths']:
                raise StoreError('Declared read-only input needs contract review before becoming writable: '+key+':'+name)
            allowed=(name in allowance.get('support_files',[]) or
                     any(name.startswith(prefix+'/') for prefix in allowance.get('allow_under',[])))
            if rules['mode']!='SCOPED_REFINEMENTS' or not allowed or protected(name):
                raise StoreError('File needs contract review, outside approved refinement allowance: '+key+':'+name)
        # Read-only dependency observations may grow within the same approved
        # roots. They grant no new write path and remain bounded by registry.
    return candidate


def validate(contract, anchor, plan):
    if not isinstance(plan,dict) or set(plan)!={'schema','contract_sha256','contract_revision','policy_sha256','revision','reason','repositories'}:
        raise StoreError('Invalid implementation_plan record')
    if (plan['schema']!=SCHEMA or plan['contract_sha256']!=contract['sha256']
            or type(plan['contract_revision']) is not int or plan['contract_revision']!=contract['revision']):
        raise ConflictError('Implementation plan belongs to another user contract; never rebind it')
    if plan['policy_sha256']!=digest(policy(contract['content'],anchor)):
        raise ConflictError('Implementation policy binding changed')
    if type(plan['revision']) is not int or plan['revision']<1:
        raise StoreError('Invalid implementation plan revision')
    if not isinstance(plan['reason'],str) or not 6<=len(plan['reason'].strip())<=2000:
        raise StoreError('implementation_plan.reason must explain the in-scope technical refinement')
    entries=_entries(contract['content'],anchor,plan['repositories'])
    if entries!=plan['repositories']:raise StoreError('Implementation plan must use normalized explicit repositories')
    return entries


def effective(contract, anchor, progress=None):
    plan=(progress or {}).get('implementation_plan')
    return {**contract['content'],'repositories':validate(contract,anchor,plan)} if plan is not None else contract['content']


def prepare(contract, anchor, previous, proposed):
    if not isinstance(proposed,dict) or set(proposed)!={'repositories','reason'}:
        raise StoreError('implementation_plan input: repositories and reason; contract fields are immutable here')
    current=(previous or {}).get('implementation_plan')
    required=validate(contract,anchor,current) if current else registry(contract['content'],anchor)
    entries=_entries(contract['content'],anchor,proposed['repositories'],required)
    result={'schema':SCHEMA,'contract_sha256':contract['sha256'],'contract_revision':contract['revision'],
            'policy_sha256':digest(policy(contract['content'],anchor)),
            'revision':current['revision']+1 if current else 1,'reason':proposed['reason'],'repositories':entries}
    validate(contract,anchor,result)
    if current and {k:v for k,v in result.items() if k!='revision'}=={k:v for k,v in current.items() if k!='revision'}:
        return current
    return result


def transition(contract, anchor, previous, content):
    plan=content.get('implementation_plan')
    old=(previous or {}).get('implementation_plan') if ((previous or {}).get('contract_sha256')==contract['sha256']
        and (previous or {}).get('contract_revision')==contract['revision']) else None
    if plan is None:
        if old:raise ConflictError('Do not silently discard the current implementation footprint')
        return contract['content']
    entries=validate(contract,anchor,plan)
    if old and old!=plan:
        required=validate(contract,anchor,old)
        _entries(contract['content'],anchor,entries,required)
    if plan!=old and plan['revision']!=(old['revision']+1 if old else 1):
        raise ConflictError('Implementation plan revision changed; reread and reconcile')
    return {**contract['content'],'repositories':entries}


def summary(plan):
    if plan is None:return None
    invalid={'status':'INVALID_REPORTED_PLAN','trust':'UNVERIFIED_REPORT','write_authorized':False}
    try:
        if (not isinstance(plan,dict) or plan.get('schema')!=SCHEMA
                or not isinstance(plan.get('repositories'),list) or not 1<=len(plan['repositories'])<=8
                or not isinstance(plan.get('reason'),str)):return invalid
        return {'revision':plan['revision'],'contract_sha256':plan['contract_sha256'],
                'contract_revision':plan['contract_revision'],
                'reason':plan['reason'][:300], 'repositories':len(plan['repositories']),
                'files':sum(len(set(r['write_paths']+r['read_paths'])) for r in plan['repositories']),
                'approval_changed':False,'trust':'UNVERIFIED_REPORT'}
    except (KeyError,TypeError,ValueError):return invalid

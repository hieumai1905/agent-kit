"""Cooperative repo writer and per-chat pointers. No OS lock or authority."""
import hashlib
import os
import uuid
from agentflow_core import ConflictError, StoreError

KEY = 'cooperative-writer'


def identity():
    return os.environ.get('AGENTFLOW_SESSION') or os.environ.get('CODEX_THREAD_ID') or os.environ.get('CLAUDE_SESSION_ID')


def session(explicit=None):
    current = identity()
    # A redundant model-supplied alias never overrides/selects another provider
    # chat. Legacy overrides are useful only when no provider identity exists.
    value = current or explicit or 'anonymous-' + uuid.uuid4().hex
    if not isinstance(value,str) or len(value)>180 or not value.strip():raise StoreError('Invalid session reference')
    return value


def writer(records):
    row = records.latest('CHANGE_REPORT', key=KEY)
    return row['content'] if row else {'held':False}


def display(records):
    current=writer(records)
    result={k:v for k,v in current.items() if k!='token'}
    result['ownership']=('IDLE' if not current.get('held') else
        'THIS_CHAT' if identity() and current.get('owner')==identity() else
        'OTHER_CHAT' if identity() else 'UNKNOWN')
    return result


def claim(records, owner, title):
    row = records.latest('CHANGE_REPORT', key=KEY)
    if row and row['content'].get('held'):
        old = row['content']
        raise ConflictError('Cooperative writer busy: '+old['owner']+' / '+old['title']+'. Owning session must save handoff/pause at a safe point; no automatic takeover.')
    token = uuid.uuid4().hex
    records.put('CHANGE_REPORT', {'held':True,'owner':owner,'title':title,'token':token,'phase':'PREPARING','pid':os.getpid()},
                key=KEY, expected_revision=row['revision'] if row else 0)
    return token


def check(records, content):
    if 'lease_token' not in content:return  # old receipts remain readable; never invent an owner
    current = writer(records)
    if not current.get('held') or current.get('token') != content['lease_token'] or current.get('owner') != content['session_ref']:
        raise ConflictError('Cooperative writer changed/released; resume the owning session, do not bypass its state')


def release(records, token):
    row = records.latest('CHANGE_REPORT', key=KEY)
    if not row or not row['content'].get('held') or row['content'].get('token') != token:
        raise ConflictError('Writer token changed; refusing release of another session')
    records.put('CHANGE_REPORT', {**row['content'],'held':False},key=KEY,expected_revision=row['revision'])


def remember(records, task, content, receipt):
    owner = content.get('session_ref')
    if not owner:return
    key = 'chat-' + hashlib.sha256(owner.encode()).hexdigest()[:40]
    row = records.latest('CHANGE_REPORT',key=key)
    records.put('CHANGE_REPORT', {'session_ref':owner,'task_id':task,'title':content.get('title',''),
                'stage':content['stage'],'receipt':receipt},key=key,expected_revision=row['revision'] if row else 0)
    held=records.latest('CHANGE_REPORT',key=KEY)
    if held and held['content'].get('held') and held['content'].get('token')==content.get('lease_token') and held['content'].get('phase')=='PREPARING':
        records.put('CHANGE_REPORT',{**held['content'],'phase':'ACTIVE','task_id':task},key=KEY,expected_revision=held['revision'])


def pause_preparation(records, summary):
    current=writer(records)
    if not identity() or current.get('owner')!=identity() or not current.get('held') or current.get('phase')!='PREPARING':
        raise ConflictError('Only the owning chat can pause an interrupted preparation; active work requires its receipt')
    try:os.kill(current['pid'],0)
    except ProcessLookupError:pass
    else:raise ConflictError('Preparing process is still present; wait for its result, never take over a live operation')
    from .practical import git_snapshot
    previous=records.latest('CHANGE_REPORT',key='interrupted-preparation')
    records.put('CHANGE_REPORT',{'summary':summary,'writer':display(records),'git':git_snapshot(records.store.repo),
                'approval_preserved_as_authorization':False},key='interrupted-preparation',expected_revision=previous['revision'] if previous else 0)
    release(records,current['token'])
    return {'status':'PAUSED','write_authorized':False,'next_action':'Interrupted preparation recorded. Read task/history and reconcile before a new begin; no completion or approval was inferred'}


def pointer(records, owner=None):
    owner = owner or identity()
    if not owner:return None
    key = 'chat-' + hashlib.sha256(owner.encode()).hexdigest()[:40]
    row = records.latest('CHANGE_REPORT',key=key)
    return row['content'] if row else None

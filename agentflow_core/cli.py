"""Developer-facing D1 diagnostics and state APIs. Not the end-user agent UX."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
import sys

from .coordinator import LocalCoordinator
from .db import StateStore
from .errors import StoreError, state_database_error


def parser():
    p=argparse.ArgumentParser(description='Agent Workflow V3 D1: unprivileged local state foundation')
    p.add_argument('--repo',required=True,help='Existing repository directory; source is never changed')
    p.add_argument('--state-home',help='Optional external root for state (outside repository)')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('init',help='Create/migrate local metadata; never install hooks or modify product source')
    sub.add_parser('doctor',help='Read-only schema/state/audit integrity checks')
    sub.add_parser('tasks',help='List state records')
    sub.add_parser('backup',help='Consistent SQLite state snapshot outside working tree')
    cmd=sub.add_parser('verify-backup')
    cmd.add_argument('file'); cmd.add_argument('--sha256')
    cmd=sub.add_parser('restore-new')
    cmd.add_argument('file'); cmd.add_argument('--fresh-state-home',required=True);cmd.add_argument('--sha256')
    cmd=sub.add_parser('new-task')
    cmd.add_argument('--title',required=True); cmd.add_argument('--request',required=True)
    cmd.add_argument('--kind',choices=['IMPLEMENTATION','INVESTIGATION'],default='IMPLEMENTATION')
    cmd.add_argument('--request-key')
    cmd=sub.add_parser('task')
    cmd.add_argument('task_id')
    cmd=sub.add_parser('start-preflight')
    cmd.add_argument('task_id');cmd.add_argument('--revision',type=int,required=True);cmd.add_argument('--request-key')
    cmd=sub.add_parser('revise-contract')
    cmd.add_argument('task_id');cmd.add_argument('--revision',type=int,required=True)
    cmd.add_argument('--json-file',required=True);cmd.add_argument('--request-key')
    cmd=sub.add_parser('propose-contract')
    cmd.add_argument('task_id');cmd.add_argument('--revision',type=int,required=True);cmd.add_argument('--request-key')
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command=='doctor':
            result=LocalCoordinator(args.repo,args.state_home,initialize=False).doctor()
        elif args.command=='verify-backup':
            result=StateStore(args.repo,args.state_home).verify_backup(args.file,args.sha256)
        elif args.command=='restore-new':
            result=StateStore(args.repo,args.state_home).restore_to_fresh_state(args.file,args.fresh_state_home,args.sha256)
        else:
            app=LocalCoordinator(args.repo,args.state_home)
            if args.command=='init': result=app.doctor()
            elif args.command=='tasks': result=app.list_tasks()
            elif args.command=='backup': result=app.store.backup()
            elif args.command=='new-task':
                result=app.create_task(args.title,args.request,kind=args.kind,request_key=args.request_key)
            elif args.command=='task':
                result=dict(task=app.get_task(args.task_id),contract=app.contract_revision(args.task_id))
            elif args.command=='start-preflight':
                result=app.transition_task(args.task_id,args.revision,'PREFLIGHT',request_key=args.request_key)
            elif args.command=='revise-contract':
                content=json.loads(Path(args.json_file).read_text(encoding='utf-8'))
                result=app.revise_contract(args.task_id,args.revision,content,request_key=args.request_key)
            elif args.command=='propose-contract':
                result=app.transition_task(args.task_id,args.revision,'WAITING_APPROVAL',request_key=args.request_key)
            else: raise StoreError('Unknown CLI command')
        print(json.dumps(result,indent=2,ensure_ascii=False))
        if args.command=='doctor' and not result.get('healthy'):
            return 2
        return 0
    except sqlite3.DatabaseError as exc:
        response=state_database_error(exc)
        if response is None:raise
        print(json.dumps(response,ensure_ascii=False),file=sys.stderr)
        return 2
    except (StoreError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({'error':type(exc).__name__,'message':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())

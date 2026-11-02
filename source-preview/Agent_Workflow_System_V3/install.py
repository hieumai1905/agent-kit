#!/usr/bin/env python3
"""Safe per-repository installer; dry-run by default; preserve existing agent settings."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'kit'
MARKER_BEGIN = '<!-- AWSYS MANAGED RULES BEGIN -->'
MARKER_END = '<!-- AWSYS MANAGED RULES END -->'


def hash_bytes(content):
    return hashlib.sha256(content).hexdigest()


def check_repo(repo):
    if not repo.is_dir(): raise ValueError('Thư mục repo không tồn tại')
    res=subprocess.run(['git','-C',str(repo),'rev-parse','--show-toplevel'],capture_output=True,text=True)
    if res.returncode: raise ValueError('Cần một Git repository thực sự')
    if Path(res.stdout.strip()).resolve()!=repo:
        raise ValueError('Chỉ cài tại Git repo root, không cài trong thư mục con/worktree khác')


def merge_hooks(current, proposed):
    try:
        old=json.loads(current.decode()) if current else {}
    except json.JSONDecodeError as exc:
        raise ValueError('File hook hiện có không phải JSON; không tự ghi đè') from exc
    if not isinstance(old,dict): raise ValueError('Hook config hiện tại cần là object')
    if not isinstance(old.get('hooks',{}),dict): raise ValueError('Trường hooks phải là object')
    merged=dict(old)
    hookmap=dict(old.get('hooks',{}))
    for event,entries in proposed['hooks'].items():
        existing=list(hookmap.get(event,[]))
        if not isinstance(hookmap.get(event,[]),list):
            raise ValueError(f'Hook event {event} không phải danh sách')
        for entry in entries:
            if entry not in existing:
                existing.append(entry)
        hookmap[event]=existing
    merged['hooks']=hookmap
    return (json.dumps(merged,ensure_ascii=False,indent=2)+'\n').encode()


def merged_content(rel, current, incoming):
    name=rel.as_posix()
    if name in ('.codex/hooks.json','.claude/settings.json'):
        return merge_hooks(current, json.loads(incoming.decode()))
    if name=='AGENTS.md' and current:
        if MARKER_BEGIN.encode() in current: return current
        return current.rstrip(b'\n') + (f'\n\n{MARKER_BEGIN}\n').encode() + incoming + (f'\n{MARKER_END}\n').encode()
    if name=='.gitignore' and current:
        if b'docs/agentflow/tasks/' in current: return current
        return current.rstrip(b'\n') + b'\n\n# AWSYS local task state\ndocs/agentflow/tasks/\n'
    if name=='CLAUDE.md' and current:
        if b'@AGENTS.md' in current: return current
        return current.rstrip(b'\n') + b'\n\n@AGENTS.md\n'
    if current:
        # Do not overwrite existing repo-specific project policies or files.
        return current
    return incoming


def plan(repo):
    changes=[]
    for source in sorted(SOURCE.rglob('*')):
        if not source.is_file() or '__pycache__' in source.parts or source.suffix in ('.pyc',):
            continue
        rel=source.relative_to(SOURCE)
        dest=repo/rel
        current=dest.read_bytes() if dest.exists() else b''
        incoming=source.read_bytes()
        after=merged_content(rel,current,incoming)
        if not dest.exists() or after!=current:
            changes.append((dest,current if dest.exists() else None,after))
    return changes


def install(repo,changes):
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    slug=hashlib.sha256(str(repo).encode()).hexdigest()[:16]
    backup=Path.home()/'Library'/'Application Support'/'AgentWorkflow'/'installation-backups'/slug/stamp
    backup.mkdir(parents=True,exist_ok=False)
    manifest=[]
    for i,(dest,before,after) in enumerate(changes):
        dest.parent.mkdir(parents=True,exist_ok=True)
        saved=None
        if before is not None:
            saved=f'originals/{i}.bin'
            (backup/'originals').mkdir(exist_ok=True)
            (backup/saved).write_bytes(before)
        tmp=dest.with_name(dest.name+'.agentflow-install-tmp')
        tmp.write_bytes(after)
        os.replace(tmp,dest)
        manifest.append(dict(path=str(dest), backup=saved, after_hash=hash_bytes(after)))
    (backup/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    return backup


def rollback(backup):
    manifest=json.loads((backup/'manifest.json').read_text(encoding='utf-8'))
    blocked=[]
    for entry in manifest:
        dest=Path(entry['path'])
        if not dest.exists() or hash_bytes(dest.read_bytes())!=entry['after_hash']:
            blocked.append(str(dest))
    if blocked:
        raise ValueError('Đã có thay đổi từ sau cài đặt. Không rollback tự động:\n'+'\n'.join(blocked))
    for entry in reversed(manifest):
        dest=Path(entry['path'])
        if entry['backup']:
            dest.write_bytes((backup/entry['backup']).read_bytes())
        else:
            dest.unlink()
    print('Đã khôi phục những file được quản lý trong manifest. Không xóa task hoặc dữ liệu runtime.')


def main():
    parser=argparse.ArgumentParser(description='Agent Workflow V3 installer for macOS')
    parser.add_argument('--repo',type=Path,help='Đường dẫn Git repository root')
    parser.add_argument('--apply',action='store_true',help='Thực sự cài đặt; mặc định chỉ dry-run')
    parser.add_argument('--rollback',type=Path,help='Thư mục backup chứa manifest.json')
    args=parser.parse_args()
    try:
        if args.rollback:
            rollback(args.rollback.expanduser()); return 0
        if not args.repo: parser.error('Cần --repo hoặc --rollback')
        repo=args.repo.expanduser().resolve()
        check_repo(repo)
        changes=plan(repo)
        print(('APPLY' if args.apply else 'DRY-RUN')+':',repo)
        for dest,before,_ in changes:
            print(('  UPDATE ' if before is not None else '  CREATE ')+str(dest.relative_to(repo)))
        if not changes: print('Không có thay đổi cần cài.')
        if args.apply and changes:
            backup=install(repo,changes)
            print('DONE. Backup ở:',backup)
            print('Kiểm tra: cd "'+str(repo)+'" && python3 .agentflow/bin/agentflow.py doctor')
            print('Cần xác nhận /hooks, project trust và kiểm thử hành vi trong từng app/CLI.')
        return 0
    except (OSError,ValueError) as exc:
        print('ERROR:',exc,file=sys.stderr)
        return 2

if __name__=='__main__':sys.exit(main())

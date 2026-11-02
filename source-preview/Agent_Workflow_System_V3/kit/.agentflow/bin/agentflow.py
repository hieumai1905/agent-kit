#!/usr/bin/env python3
"""Agent Workflow V3 preview. Local stdlib-only repo task coordinator.

IMPORTANT: hook/lease coordination is not a macOS security boundary. See SECURITY.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import sqlite3
import subprocess
import sys
import time
import unicodedata

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent.resolve()
TASK_ROOT = ROOT / 'docs' / 'agentflow' / 'tasks'
POLICY_ROOT = BASE.parent / 'policies'
TASK_RE = re.compile(r'^T-\d{8}-[a-f0-9]{6}$')
WRITE_TOOLS = {'Write', 'Edit', 'MultiEdit', 'apply_patch'}
READ_TOOLS = {'Read', 'Grep', 'Glob', 'WebSearch', 'WebFetch', 'LS', 'AskUserQuestion',
              'EnterPlanMode', 'ExitPlanMode', 'TodoWrite', 'update_plan'}
SHELL_TOOLS = {'Bash', 'exec_command', 'Shell'}
RISK_LEVELS = {'LOW', 'MEDIUM', 'HIGH'}
SESSION_LEASE_SECONDS = 120


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def data_dir() -> Path:
    custom = os.environ.get('AGENTFLOW_STATE_DIR')
    if custom:
        parent = Path(custom).expanduser().resolve()
    else:
        slug = hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
        parent = Path.home() / 'Library' / 'Application Support' / 'AgentWorkflow' / slug
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def db() -> sqlite3.Connection:
    cn = sqlite3.connect(str(data_dir() / 'state.sqlite3'), timeout=15, isolation_level=None)
    cn.row_factory = sqlite3.Row
    cn.execute('PRAGMA busy_timeout=15000')
    cn.execute('PRAGMA journal_mode=WAL')
    cn.executescript('''
    CREATE TABLE IF NOT EXISTS tasks (
      id TEXT PRIMARY KEY, title TEXT NOT NULL, lifecycle TEXT NOT NULL,
      proposed_hash TEXT, approved_hash TEXT, created TEXT NOT NULL, updated TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
      id TEXT PRIMARY KEY, task_id TEXT, mode TEXT NOT NULL,
      provider TEXT NOT NULL, updated TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS leases (
      resource TEXT PRIMARY KEY, session_id TEXT NOT NULL,
      task_id TEXT NOT NULL, expires_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS verification (
      task_id TEXT NOT NULL, check_name TEXT NOT NULL, status TEXT NOT NULL,
      detail TEXT NOT NULL, ts TEXT NOT NULL, PRIMARY KEY (task_id,check_name)
    );
    CREATE TABLE IF NOT EXISTS audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, session_id TEXT,
      action TEXT NOT NULL, detail TEXT NOT NULL, ts TEXT NOT NULL
    );
    ''')
    return cn


def add_audit(cn, task_id, session_id, action, detail=''):
    cn.execute('INSERT INTO audit(task_id,session_id,action,detail,ts) VALUES(?,?,?,?,?)',
               (task_id, session_id, action, str(detail)[:2000], now()))


def task_path(task_id: str) -> Path:
    if not TASK_RE.fullmatch(task_id):
        raise ValueError('Task ID không hợp lệ')
    return TASK_ROOT / task_id


def contract_path(task_id):
    return task_path(task_id) / 'contract.json'


def read_contract(task_id) -> dict:
    try:
        obj = json.loads(contract_path(task_id).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('Không đọc được contract.json: ' + str(exc)) from exc
    if not isinstance(obj, dict):
        raise ValueError('contract.json cần là JSON object')
    return obj


def contract_hash(task_id) -> str:
    return hashlib.sha256(contract_path(task_id).read_bytes()).hexdigest()


def clean_scope(pattern: str) -> str:
    if not isinstance(pattern, str) or not pattern.strip():
        raise ValueError('Scope rỗng')
    x = pattern.replace('\\', '/')
    if x.startswith('/') or x.startswith('~') or '..' in x.split('/') or x in ('*', '**', './**'):
        raise ValueError('Scope quá rộng hoặc đường dẫn không an toàn: ' + pattern)
    if x.startswith('./'):
        x = x[2:]
    if x.startswith('.git/') or x.startswith('.agentflow/') or x.startswith('.claude/') or x.startswith('.codex/'):
        raise ValueError('Không cho phép ghi cấu hình agent/Git từ task')
    return x


def validate(task_id: str) -> tuple[dict, list[str]]:
    obj = read_contract(task_id)
    errors = []
    for k in ('objective', 'scope', 'out_of_scope', 'acceptance', 'verification',
              'risk', 'complexity', 'assumptions', 'open_questions', 'impact'):
        if k not in obj:
            errors.append('Thiếu ' + k)
    if errors:
        return obj, errors
    if not isinstance(obj['objective'], str) or len(obj['objective'].strip()) < 12:
        errors.append('objective chưa đủ rõ')
    for k in ('scope', 'out_of_scope', 'acceptance', 'verification', 'assumptions', 'open_questions'):
        if not isinstance(obj[k], list) or any(not isinstance(i, str) for i in obj[k]):
            errors.append(k + ' phải là danh sách chuỗi')
    for k in ('scope', 'acceptance', 'verification'):
        if isinstance(obj[k], list) and not obj[k]:
            errors.append(k + ' không được rỗng')
    for k in ('risk', 'complexity'):
        if str(obj[k]).upper() not in RISK_LEVELS:
            errors.append(k + ' phải LOW/MEDIUM/HIGH')
    if not isinstance(obj['impact'], str) or not obj['impact'].strip():
        errors.append('impact chưa được mô tả')
    if isinstance(obj.get('open_questions'), list) and obj['open_questions']:
        errors.append('Còn câu hỏi chặn thực thi trong open_questions')
    if isinstance(obj.get('scope'), list):
        for x in obj['scope']:
            try:
                clean_scope(x)
            except ValueError as exc:
                errors.append(str(exc))
    if isinstance(obj.get('acceptance'), list):
        if any(x.strip().lower() in ('todo', 'tbd', 'test', '[todo]') for x in obj['acceptance']):
            errors.append('acceptance còn placeholder')
    return obj, errors


def markdown(obj, task_id, hash_value):
    def bullets(xs):
        return '\n'.join('- ' + v for v in xs) if xs else '- Không có'
    return (f'# Task Contract — {task_id}\n\n'
            f'**SHA-256:** `{hash_value}`\n\n'
            f'**Mục tiêu:** {obj["objective"]}\n\n'
            f'## Phạm vi chỉnh sửa dự kiến\n{bullets(obj["scope"])}\n\n'
            f'## Không thực hiện\n{bullets(obj["out_of_scope"])}\n\n'
            f'## Tiêu chí hoàn thành\n{bullets(obj["acceptance"])}\n\n'
            f'## Kiểm chứng\n{bullets(obj["verification"])}\n\n'
            f'## Đánh giá\n- Risk: **{obj["risk"]}**\n'
            f'- Complexity: **{obj["complexity"]}**\n'
            f'- Impact: {obj["impact"]}\n\n'
            f'## Giả định chưa được xác nhận\n{bullets(obj["assumptions"])}\n\n'
            f'## Câu hỏi cần làm rõ\n{bullets(obj["open_questions"])}\n\n'
            '**Chỉ được thực thi sau khi người dùng xem và phê duyệt bản này.**\n')


def create_task(cn, prompt, session_id):
    task_id = 'T-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d') + '-' + secrets.token_hex(3)
    folder = task_path(task_id)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'REQUEST.md').write_text('# Yêu cầu gốc\n\n' + prompt.strip() + '\n', encoding='utf-8')
    contract = dict(objective='', scope=[], out_of_scope=[], acceptance=[], verification=[],
                    risk='MEDIUM', complexity='MEDIUM', assumptions=[], open_questions=[], impact='Chưa khảo sát')
    contract_path(task_id).write_text(json.dumps(contract, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (folder / 'STATE.md').write_text(
        f'# {task_id} — Execution State\n\nStatus: PREFLIGHT\n\n'
        '## Completed\n- Chưa thực thi\n\n## Evidence\n- NOT RUN\n\n'
        '## Decisions\n- Chưa có\n\n## Next Action\n- Khảo sát và chuẩn hóa yêu cầu\n\n'
        '## Blockers\n- Chưa xác định\n', encoding='utf-8')
    cn.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?)',
               (task_id, prompt.strip()[:100], 'DRAFT', None, None, now(), now()))
    add_audit(cn, task_id, session_id, 'TASK_CREATED', prompt[:200])
    return task_id


def bind_session(cn, session_id, task_id, mode='PREFLIGHT', provider='unknown'):
    cn.execute('INSERT INTO sessions(id,task_id,mode,provider,updated) VALUES(?,?,?,?,?) '
               'ON CONFLICT(id) DO UPDATE SET task_id=excluded.task_id, mode=excluded.mode, '
               'provider=excluded.provider, updated=excluded.updated',
               (session_id, task_id, mode, provider, now()))


def get_session(cn, session_id):
    return cn.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()


def spec_matches_contract(task_id):
    try:
        obj = read_contract(task_id)
        digest = contract_hash(task_id)
        path = task_path(task_id) / 'SPEC.md'
        return path.read_text(encoding='utf-8') == markdown(obj, task_id, digest)
    except (OSError, ValueError):
        return False


def approved(cn, task_id):
    row = cn.execute('SELECT approved_hash FROM tasks WHERE id=?', (task_id,)).fetchone()
    if not row or not row['approved_hash']:
        return False
    try:
        return row['approved_hash'] == contract_hash(task_id) and spec_matches_contract(task_id)
    except OSError:
        return False


def propose(cn, task_id):
    obj, errors = validate(task_id)
    if errors:
        raise ValueError('Spec chưa hợp lệ: ' + '; '.join(errors))
    digest = contract_hash(task_id)
    (task_path(task_id) / 'SPEC.md').write_text(markdown(obj, task_id, digest), encoding='utf-8')
    cn.execute('UPDATE tasks SET proposed_hash=?, lifecycle=?, updated=? WHERE id=?',
               (digest, 'WAITING_APPROVAL', now(), task_id))
    add_audit(cn, task_id, None, 'PROPOSED', digest[:12])
    return digest


def approve_from_user(cn, task_id, session_id):
    row = cn.execute('SELECT proposed_hash FROM tasks WHERE id=?', (task_id,)).fetchone()
    if not row or not row['proposed_hash']:
        return False, 'Chưa có bản đặc tả đã chuẩn hóa để duyệt.'
    try:
        digest = contract_hash(task_id)
        _, errors = validate(task_id)
    except ValueError as exc:
        return False, str(exc)
    if errors:
        return False, 'Spec không hợp lệ: ' + '; '.join(errors)
    if digest != row['proposed_hash'] or not spec_matches_contract(task_id):
        return False, 'Spec đã thay đổi sau khi trình duyệt; cần propose lại.'
    cn.execute('UPDATE tasks SET approved_hash=?, lifecycle=?, updated=? WHERE id=?',
               (digest, 'APPROVED', now(), task_id))
    bind_session(cn, session_id, task_id, 'EXECUTE', get_session(cn,session_id)['provider'])
    add_audit(cn, task_id, session_id, 'HUMAN_APPROVAL_IN_CHAT', digest)
    return True, f'Đã ghi nhận duyệt {task_id}, SHA-256 {digest[:12]}.'


def normalize(s):
    s = ''.join(ch for ch in unicodedata.normalize('NFKD', s) if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', s.lower()).strip(' .!')


def user_hook(cn, event):
    session = str(event.get('session_id') or 'no-session')
    provider = str(event.get('model') or 'unknown')
    prompt = str(event.get('prompt') or '').strip()
    if not prompt:
        return 'Không có nội dung prompt; chỉ xử lý read-only.'
    normalized = normalize(prompt)
    row = get_session(cn, session)
    current = row['task_id'] if row else None
    match = re.fullmatch(r'(?:duyet|approve)(?:\s+(T-\d{8}-[a-f0-9]{6}))?', normalized, flags=re.I)
    if match:
        task_id = (('T' + match.group(1)[1:]) if match.group(1) else current)
        if not task_id:
            return 'Chưa có task đang chờ duyệt. Hãy xác định task cụ thể.'
        task_row = cn.execute('SELECT id FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not task_row:
            return 'Task không tồn tại; không phê duyệt.'
        bind_session(cn,session,task_id,'PREFLIGHT',provider)
        ok, message = approve_from_user(cn, task_id, session)
        return message + (' Có thể triển khai SPEC đã duyệt trong đúng phạm vi.' if ok
                          else ' DỪNG triển khai; yêu cầu sửa spec/trình lại.')
    resume = re.fullmatch(r'(?:tiep tuc|continue|resume)(?:\s+(T-\d{8}-[a-f0-9]{6}))?', normalized, flags=re.I)
    if resume:
        task_id = (('T' + resume.group(1)[1:]) if resume.group(1) else current)
        if not task_id:
            candidates=cn.execute("SELECT id FROM tasks WHERE lifecycle IN ('DRAFT','WAITING_APPROVAL','APPROVED') ORDER BY updated DESC LIMIT 2").fetchall()
            if len(candidates)==1:
                task_id=candidates[0]['id']
        if not task_id or not cn.execute('SELECT 1 FROM tasks WHERE id=?',(task_id,)).fetchone():
            return 'Chưa xác định được task duy nhất; hãy nêu Task ID hoặc tên công việc. CHƯA ĐƯỢC SỬA CODE.'
        if approved(cn, task_id):
            bind_session(cn,session,task_id,'EXECUTE',provider)
            return (f'TIẾP QUẢN {task_id}: SPEC đã duyệt còn hợp lệ. Đọc SPEC.md, STATE.md, '
                    'git status/diff trước khi thực thi; chỉ sửa trong scope, kiểm tra leases. '
                    'Không tự commit/push/deploy.')
        bind_session(cn,session,task_id,'PREFLIGHT',provider)
        return f'{task_id} chưa được duyệt hoặc spec đã đổi. Chỉ khảo sát và trình duyệt lại.'
    select = re.fullmatch(r'(?:task|chon task|select task)\s+(T-\d{8}-[a-f0-9]{6})', normalized)
    if select:
        task_id = 'T' + select.group(1)[1:]
        if cn.execute('SELECT 1 FROM tasks WHERE id=?', (task_id,)).fetchone():
            bind_session(cn,session,task_id,'PREFLIGHT',provider)
            return f'Đã chọn {task_id}. Kiểm tra trạng thái rồi nhận hướng dẫn hoặc yêu cầu TIẾP TỤC. Chưa sửa code.'
    if current:
        # Every new natural-language instruction is a preflight until explicitly approved.
        request_log = task_path(current) / 'REQUEST.md'
        if request_log.exists():
            with request_log.open('a', encoding='utf-8') as out:
                out.write('\n## Follow-up — ' + now() + '\n\n' + prompt + '\n')
        bind_session(cn,session,current,'PREFLIGHT',provider)
        add_audit(cn,current,session,'NEW_PROMPT_REQUIRES_PREFLIGHT',prompt[:150])
        return (f'TIN NHẮN MỚI cho {current}; chuyển lượt này về PREFLIGHT/READ-ONLY. '
                'Phân loại là câu hỏi, thay đổi yêu cầu hay task khác. Nếu yêu cầu thay đổi code mới, '
                'cập nhật hoặc tạo task/contract, trình lại và đợi “Duyệt”. '
                'Nếu chỉ hỏi giải thích, trả lời read-only. Không được sửa code trên lượt này.')
    new_id = create_task(cn,prompt,session)
    bind_session(cn,session,new_id,'PREFLIGHT',provider)
    return (f'TASK {new_id} tự tạo. PREFLIGHT ONLY. Đọc AGENTS.md và '
            f'docs/agentflow/tasks/{new_id}/REQUEST.md; khảo sát code (read-only). '
            f'Hoàn thành docs/agentflow/tasks/{new_id}/contract.json rồi chạy '
            f'`python3 .agentflow/bin/agentflow.py propose {new_id}`; '
            'in SPEC.md cho người dùng đọc, hỏi những câu còn thiếu, đợi người dùng nhắn “Duyệt”. '
            'Không sửa code, tests, dependencies hoặc config khi chưa được duyệt.')


def inside_repo(path_value):
    p = Path(path_value)
    if not p.is_absolute():
        p = ROOT / p
    p = p.resolve(strict=False)
    try:
        rel = p.relative_to(ROOT).as_posix()
    except ValueError:
        raise ValueError('Đường dẫn nằm ngoài repository')
    return rel


def tool_paths(event):
    tool = event.get('tool_name') or ''
    args = event.get('tool_input') or {}
    if not isinstance(args, dict):
        return []
    if tool == 'apply_patch':
        patch = args.get('command') or args.get('patch') or args.get('text') or ''
        if not isinstance(patch, str):
            return []
        paths = re.findall(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$', patch, re.M)
        paths += re.findall(r'^\*\*\* Move to: (.+)$', patch, re.M)
        return paths
    paths = []
    for k in ('file_path','path'):
        if isinstance(args.get(k), str):
            paths.append(args[k])
    return paths


def readonly_shell(cmd: str) -> bool:
    if any(x in cmd for x in (';', '&&', '||', '|', '>', '<', '`', '$(', '\n', '\r', '\x00', '\\')):
        return False
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return False
    if not tokens:
        return False
    if tokens[0] in ('pwd','ls','cat','rg','grep','head','tail','wc'):
        return not any(x.startswith(('--pre', '--post', '--exec', '--output', '--glob=')) for x in tokens) and not any('/.ssh/' in x or '/.env' in x or x.startswith('.env') for x in tokens)
    if tokens[0] == 'git' and len(tokens) > 1 and tokens[1] in ('status','diff','log','show','rev-parse','ls-files'):
        unsafe = ('--ext-diff','--textconv','--output','--exec','--config','-c','--paginate')
        return not any(x.startswith(unsafe) for x in tokens[2:])
    if tokens[0] == 'sed' and len(tokens)>2 and tokens[1]=='-n':
        return True
    return False


def managed_command(cmd:str, task_id:str, preflight:bool) -> bool:
    try:
        xs = shlex.split(cmd)
    except ValueError:
        return False
    if len(xs)<3 or Path(xs[0]).name not in ('python3','python3.10','python3.11','python3.12','python3.13','python3.14'):
        return False
    try:
        script = Path(xs[1]).resolve()
    except OSError:
        return False
    if script != BASE / 'agentflow.py':
        return False
    if xs[2] in ('tasks','status','model-advice','doctor'):
        return True
    if xs[2]=='propose' and len(xs)==4 and xs[3]==task_id and preflight:
        return True
    if xs[2]=='verify' and len(xs)==4 and xs[3]==task_id and not preflight:
        return True
    return False


def acquire(cn,resource,session,task_id):
    # Atomic arbitration, with a short lease to recover from dead sessions.
    cn.execute('BEGIN IMMEDIATE')
    try:
        cn.execute('DELETE FROM leases WHERE expires_at < ?', (int(time.time()),))
        if resource.startswith('file:'):
            busy = cn.execute("SELECT * FROM leases WHERE resource='global:verify' AND session_id != ?", (session,)).fetchone()
            if busy:
                cn.execute('ROLLBACK'); return False, 'Có phiên khác đang kiểm chứng toàn repository'
        lock = cn.execute('SELECT session_id,task_id FROM leases WHERE resource=?', (resource,)).fetchone()
        if lock and lock['session_id'] != session:
            cn.execute('ROLLBACK'); return False, 'Tài nguyên đã được session khác giữ: '+resource
        cn.execute('INSERT INTO leases VALUES(?,?,?,?) ON CONFLICT(resource) DO UPDATE SET '
                   'session_id=excluded.session_id, task_id=excluded.task_id, expires_at=excluded.expires_at',
                   (resource,session,task_id,int(time.time())+SESSION_LEASE_SECONDS))
        cn.execute('COMMIT')
    except BaseException:
        if cn.in_transaction:
            cn.execute('ROLLBACK')
        raise
    return True, ''


def release(cn,resource,session):
    cn.execute('DELETE FROM leases WHERE resource=? AND session_id=?', (resource,session))


def guard_tool(cn,event):
    session = str(event.get('session_id') or 'no-session')
    row = get_session(cn,session)
    tool = str(event.get('tool_name') or '')
    if tool in READ_TOOLS:
        return True, 'read tool'
    if not row or not row['task_id']:
        return False, 'Chưa có task gắn với session. Gửi yêu cầu để chạy preflight.'
    task_id, mode = row['task_id'], row['mode']
    preflight = mode != 'EXECUTE' or not approved(cn,task_id)
    if tool in SHELL_TOOLS:
        args = event.get('tool_input') or {}
        cmd = args.get('command') if isinstance(args,dict) else ''
        if isinstance(cmd,list):
            cmd = ' '.join(str(x) for x in cmd)
        if not isinstance(cmd,str):
            return False, 'Không nhận diện được shell command'
        if readonly_shell(cmd):
            return True,'read-only shell'
        if managed_command(cmd,task_id,preflight):
            return True,'managed command'
        return False, ('Shell command chưa được cấp quyền bởi policy. '
                       'Dùng file tools để sửa file đúng scope; kiểm chứng qua lệnh managed verify. '
                       'Không chạy lệnh có side effects trực tiếp.')
    if tool in WRITE_TOOLS:
        paths = tool_paths(event)
        if not paths:
            return False, 'Không phân tích được danh sách file mục tiêu (deny by default)'
        resources=[]
        for path in paths:
            try:
                rel = inside_repo(path)
            except ValueError as exc:
                return False,str(exc)
            is_contract = rel == f'docs/agentflow/tasks/{task_id}/contract.json'
            is_state = rel == f'docs/agentflow/tasks/{task_id}/STATE.md'
            protected = (rel in {'AGENTS.md','CLAUDE.md','.gitignore'} or
                         rel.startswith(('.git/','.codex/','.claude/','.agentflow/')) or
                         rel.startswith('docs/agentflow/'))
            if protected and not (is_contract and preflight) and not (is_state and not preflight):
                return False, 'File hệ thống / cấu hình / tài liệu được bảo vệ: '+rel
            if preflight:
                if not is_contract:
                    return False,'Chưa duyệt: chỉ cho phép cập nhật contract.json của task hiện tại'
            else:
                if not (is_state or is_contract):
                    obj,_ = validate(task_id)
                    if not any(fnmatch.fnmatchcase(rel,clean_scope(x)) or rel == clean_scope(x).rstrip('/')
                               for x in obj.get('scope',[])):
                        return False,'Ngoài write scope đã duyệt: '+rel
                if is_contract:
                    # Any change will invalidate content hash; require re-approval.
                    return False,'Không sửa contract đã duyệt trong EXECUTE; quay lại PREFLIGHT trước'
            resources.append('file:'+rel)
        acquired=[]
        for resource in resources:
            ok,reason = acquire(cn,resource,session,task_id)
            if not ok:
                for a in acquired: release(cn,a,session)
                return False,reason
            acquired.append(resource)
        return True,'write lease acquired'
    return False,'Tool không nằm trong danh sách cho phép; cần review policy: '+tool


def provider_respond(event_name,text,provider=''):
    # All supported hook clients accept text as context on UserPromptSubmit.
    print(text)


def hook_cli(args):
    event = json.load(sys.stdin)
    if not isinstance(event, dict):
        raise ValueError('Hook event không hợp lệ')
    with db() as cn:
        if args.event == 'prompt':
            provider_respond('UserPromptSubmit',user_hook(cn,event))
        elif args.event == 'pretool':
            ok,why = guard_tool(cn,event)
            if not ok:
                print('AGENT WORKFLOW BLOCKED: '+why,file=sys.stderr)
                raise SystemExit(2)
        elif args.event == 'posttool':
            tool = event.get('tool_name')
            if tool in WRITE_TOOLS:
                for path in tool_paths(event):
                    try: release(cn,'file:'+inside_repo(path),str(event.get('session_id') or 'no-session'))
                    except ValueError: pass
        elif args.event == 'end':
            cn.execute('DELETE FROM leases WHERE session_id=?', (str(event.get('session_id') or 'no-session'),))


def model_advice(cn,task_id,provider=''):
    obj = read_contract(task_id)
    complexity = str(obj.get('complexity','MEDIUM')).upper()
    risk = str(obj.get('risk','MEDIUM')).upper()
    policy_file = POLICY_ROOT / 'model-policy.json'
    policy = json.loads(policy_file.read_text(encoding='utf-8'))
    tier = 'DEEP' if risk == 'HIGH' or complexity == 'HIGH' else ('BALANCED' if risk == 'MEDIUM' or complexity == 'MEDIUM' else 'FAST')
    provider_settings = policy.get('providers',{}).get(provider, {})
    usage = provider_settings.get('usage_mode', policy.get('usage_mode','UNKNOWN')).upper()
    if usage in ('LOW','CRITICAL') and risk=='LOW' and complexity!='HIGH':
        tier = 'FAST'
    allowed = provider_settings.get('allowed_models',[])
    known = provider_settings.get('known_available_models',[])
    candidates = [m for m in allowed if m in known]
    return dict(capability_tier=tier,usage_mode=usage,provider=provider or 'unknown',
                model_candidates=candidates, recommendation_only=True,
                reason='HIGH risk/complexity => DEEP; usage thấp => tiết kiệm nếu an toàn.',
                note='UNKNOWN usage không được suy diễn thành còn nhiều. Model mới cần người dùng cho phép.')


def verify(cn,task_id):
    if not approved(cn,task_id):
        raise ValueError('Chưa có phê duyệt hợp lệ')
    policy = json.loads((POLICY_ROOT/'verification.json').read_text(encoding='utf-8'))
    checks = policy.get('checks',[])
    if not checks:
        print('NO_CHECKS_CONFIGURED: chưa có phép kiểm thử nào được chốt; không được tự báo PASS.')
        return 3
    task_session = f'verify-{os.getpid()}'
    cn.execute('BEGIN IMMEDIATE')
    try:
        cn.execute('DELETE FROM leases WHERE expires_at < ?', (int(time.time()),))
        if cn.execute("SELECT 1 FROM leases WHERE resource LIKE 'file:%' OR resource='global:verify'").fetchone():
            cn.execute('ROLLBACK'); raise ValueError('Có phiên ghi đang hoạt động; chưa thể verify toàn repo')
        cn.execute('INSERT INTO leases VALUES(?,?,?,?)',('global:verify',task_session,task_id,int(time.time())+1800))
        cn.execute('COMMIT')
    except BaseException:
        if cn.in_transaction: cn.execute('ROLLBACK')
        raise
    worst=0
    try:
        for check in checks:
            name=check['name']; command=check['argv']
            if not isinstance(command,list) or not command or not all(isinstance(x,str) for x in command):
                raise ValueError('verification argv phải là list of strings')
            if not (Path(command[0]).name in {'python3','pytest','npm','pnpm','yarn','cargo','go','make','npx','bun','ruff','node'}):
                raise ValueError('Command chưa nằm trong test allowlist: '+command[0])
            try:
                run = subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=min(int(check.get('timeout',300)),600),check=False)
                status = 'PASS' if run.returncode == 0 else 'FAIL'
                detail=(run.stdout+'\n'+run.stderr)[-6000:]
                worst=max(worst,0 if run.returncode==0 else 1)
            except (subprocess.TimeoutExpired,OSError) as exc:
                status='ERROR'; detail=str(exc); worst=1
            cn.execute('INSERT OR REPLACE INTO verification VALUES(?,?,?,?,?)', (task_id,name,status,detail,now()))
            print(f'{name}: {status}\n{detail[-800:]}')
    finally:
        release(cn,'global:verify',task_session)
    return worst


def doctor():
    print('Agent Workflow V3 preview')
    print('Repository:',ROOT)
    print('Python:',sys.version.split()[0])
    print('OS:',sys.platform)
    print('State DB:',data_dir()/'state.sqlite3')
    print('Hooks: on-disk configuration only; actual GUI/CLI loading must be tested.')
    print('Security: advisory guards; NOT an OS filesystem sandbox.')
    for cli in ('codex','claude','git'):
        from shutil import which
        print(f'{cli}:',which(cli) or 'NOT FOUND (GUI may still work)')
    with db() as cn:
        print('Tasks:',cn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0])


def run_cli():
    p=argparse.ArgumentParser(description='Agent Workflow V3 preview; docs/guide.md')
    sub=p.add_subparsers(dest='cmd',required=True)
    h=sub.add_parser('hook'); h.add_argument('event',choices=['prompt','pretool','posttool','end'])
    sub.add_parser('doctor')
    sub.add_parser('tasks')
    s=sub.add_parser('status'); s.add_argument('task')
    s=sub.add_parser('propose'); s.add_argument('task')
    s=sub.add_parser('model-advice'); s.add_argument('task'); s.add_argument('--provider',choices=['codex','claude'],default='')
    s=sub.add_parser('verify'); s.add_argument('task')
    args=p.parse_args()
    try:
        if args.cmd=='hook':
            hook_cli(args); return 0
        if args.cmd=='doctor': doctor(); return 0
        with db() as cn:
            if args.cmd=='tasks':
                for t in cn.execute('SELECT id,lifecycle,title FROM tasks ORDER BY created DESC'):
                    print(t['id'],t['lifecycle'],t['title']);
                return 0
            task_id=args.task
            if not cn.execute('SELECT 1 FROM tasks WHERE id=?',(task_id,)).fetchone():
                raise ValueError('Không tồn tại task '+task_id)
            if args.cmd=='propose':
                digest=propose(cn,task_id)
                print(f'PROPOSED {task_id}, sha256={digest[:12]}')
                print((task_path(task_id)/'SPEC.md').read_text(encoding='utf-8'))
                print('Hãy trình toàn bộ nội dung này cho người dùng; chỉ khi user gửi “Duyệt” trong chính session mới có approval.')
            elif args.cmd=='status':
                row=cn.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone()
                print(json.dumps(dict(id=task_id,lifecycle=row['lifecycle'],proposed_hash=row['proposed_hash'],
                                      approved_valid=approved(cn,task_id)),indent=2,ensure_ascii=False))
            elif args.cmd=='model-advice':
                print(json.dumps(model_advice(cn,task_id,args.provider),indent=2,ensure_ascii=False))
            elif args.cmd=='verify': return verify(cn,task_id)
        return 0
    except (ValueError,OSError,json.JSONDecodeError,sqlite3.Error) as exc:
        print('LỖI:',exc,file=sys.stderr); return 2


if __name__ == '__main__':
    sys.exit(run_cli())

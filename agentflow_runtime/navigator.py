"""Task discovery by natural language. Never equates natural-language approval with trust."""
from __future__ import annotations
from difflib import SequenceMatcher
import re
import unicodedata

from .records import WorkflowRecords


def normalize(text: str) -> str:
    text=unicodedata.normalize('NFD', text.casefold().replace('đ','d'))
    text=''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9\s]',' ',text)).strip()


def resume_query(text: str) -> str:
    """Strip the resume intent; relative/vague requests are never task identity."""
    text=re.sub(r'^(tiếp tục|tiep tuc|resume|làm tiếp|lam tiep|trở lại task|tro lai task|mở lại|mo lai)\b[\s,:-]*',
                '',(text or '').strip(),flags=re.I).strip()
    if normalize(text) in {'', 'viec hom truoc', 'cong viec hom truoc', 'viec vua lam',
                           'cong viec vua lam', 'hom truoc', 'viec hom qua', 'hom qua',
                           'previous work', 'last task', 'work from yesterday'}:
        return ''
    return text


def route_intent(message: str) -> dict:
    """Conservative deterministic hints; not a semantic authorization engine."""
    s=normalize(message)
    if not s: return {'intent':'UNCLEAR','confidence':'LOW','requires_interpretation':True}
    # Do not let a quoted 'duyet' in a larger command become approval.
    if s in {'duyet','approve','approved','chap thuan','xac nhan duyet'}:
        return {'intent':'APPROVAL_CLAIM','approval_valid':False,'requires_trusted_channel':True}
    if any(s.startswith(x) for x in ('tiep tuc','resume','lam tiep','tro lai task','mo lai')):
        intent='RESUME'
    elif any(s.startswith(x) for x in ('danh sach','liet ke','co viec nao','tim task')):
        intent='NAVIGATE'
    elif message.rstrip().endswith('?') or any(s.startswith(x) for x in ('tai sao','vi sao','la gi','cho hoi','giai thich','how','what','why')):
        intent='QUESTION'
    elif any(s.startswith(x) for x in ('kham pha','danh gia','nghien cuu','explore','phan tich')):
        intent='EXPLORE'
    elif any(s.startswith(x) for x in ('thay doi','sua yeu cau','bo sung yeu cau','change requirement')):
        intent='CHANGE_REQUEST'
    else:
        intent='NEW_OR_UPDATE_UNCERTAIN'
    return {'intent':intent,'confidence':'HEURISTIC','requires_interpretation':True,
            'approval_valid':False}


class TaskNavigator:
    def __init__(self, records: WorkflowRecords):
        self.records=records

    def search(self, query: str, limit: int=6) -> dict:
        if not 1<=limit<=20: raise ValueError('limit must be 1..20')
        norm=normalize(query)
        if norm:
            # Exact identity must not depend on the recent fuzzy-search window.
            with __import__('contextlib').closing(self.records.store.connect(read_only=True)) as cn:
                cn.create_function('task_normalize', 1, normalize, deterministic=True)
                exact=list(cn.execute('''SELECT t.* FROM tasks t WHERE t.repo_id=? AND
                    (task_normalize(t.title)=? OR EXISTS (
                        SELECT 1 FROM task_aliases a WHERE a.repo_id=t.repo_id
                        AND a.task_id=t.id AND a.alias_norm=?))
                    ORDER BY t.updated_at DESC,t.id LIMIT ?''',
                    (self.records.store.repo_id,norm,norm,limit+1)))
            if exact:
                unique=len(exact)==1
                return {'status':'UNAMBIGUOUS' if unique else 'AMBIGUOUS',
                    'choices':[{'task_id':t['id'],'title':t['title'],'lifecycle':t['lifecycle'],
                                'match_score':1.0} for t in exact[:limit]],
                    'auto_selected':unique,'selected_task_id':exact[0]['id'] if unique else None,
                    'requires_confirmation':not unique,'search_scope':'EXACT_ALL_HISTORY',
                    'search_truncated':len(exact)>limit}
        # Activity includes checkpoint/work/session updates, not just task creation.
        with __import__('contextlib').closing(self.records.store.connect(read_only=True)) as cn:
            tasks=[dict(row) for row in cn.execute('''
              SELECT t.*, MAX(t.updated_at,COALESCE(s.last_at,''),
                             COALESCE(w.last_at,''),COALESCE(d.last_at,'')) AS last_activity
              FROM tasks t
              LEFT JOIN (SELECT task_id, MAX(updated_at) last_at FROM sessions GROUP BY task_id) s
                ON s.task_id=t.id
              LEFT JOIN (SELECT task_id, MAX(updated_at) last_at FROM work_items GROUP BY task_id) w
                ON w.task_id=t.id
              LEFT JOIN (SELECT scope_key, MAX(created_at) last_at FROM workflow_documents
                         GROUP BY scope_key) d ON d.scope_key=t.id
              WHERE t.repo_id=? ORDER BY last_activity DESC,t.id LIMIT 201''',
              (self.records.store.repo_id,))]
        truncated=len(tasks)>200
        tasks=tasks[:200]
        if not norm:
            return {'status':'RECENT','choices':[
                {'task_id':t['id'],'title':t['title'],'lifecycle':t['lifecycle']}
                for t in tasks[:limit]],'auto_selected':False,
                'search_scope':'RECENT','search_truncated':truncated}
        scores=[]
        qwords=set(norm.split())
        for rank,t in enumerate(tasks):
            forms=[normalize(t['title'])]+self.records.aliases_for(t['id'])
            # Lookup original request only as a weak signal, never authorizes task transition.
            matching=max((SequenceMatcher(None,norm,f).ratio() for f in forms), default=0)
            if norm in forms: matching=1.0
            overlap=max((len(qwords & set(f.split()))/max(len(qwords),1) for f in forms),default=0)
            score=.62*matching+.35*overlap+.03*(1-rank/max(len(tasks),1))
            if any(norm in f for f in forms): score=max(score,.80)
            if score >= .33: scores.append((score,t))
        scores.sort(key=lambda x:x[0],reverse=True)
        choices=[{'task_id':t['id'],'title':t['title'],'lifecycle':t['lifecycle'],
                  'match_score':round(score,3)} for score,t in scores[:limit]]
        # High confidence requires distinctive lead, not merely highest of several vague matches.
        unique=bool(not truncated and choices and choices[0]['match_score']>=.84 and
                    (len(choices)==1 or choices[0]['match_score']-choices[1]['match_score']>=.16))
        return {'status':'UNAMBIGUOUS' if unique else 'AMBIGUOUS' if choices else 'NO_MATCH',
                'choices':choices,'auto_selected':unique,
                'selected_task_id':choices[0]['task_id'] if unique else None,
                'requires_confirmation':not unique and bool(choices),
                'search_scope':'RECENT_FUZZY','search_truncated':truncated}

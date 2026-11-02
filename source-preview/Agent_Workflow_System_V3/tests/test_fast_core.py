"""Fast deterministic integration checks, no actual Codex/Claude application required."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

TOP=Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t=tempfile.TemporaryDirectory(prefix='aw-fast-')
        cls.repo=Path(cls.t.name)/'repo'
        shutil.copytree(TOP/'kit',cls.repo)
        cls.old=os.environ.get('AGENTFLOW_STATE_DIR')
        os.environ['AGENTFLOW_STATE_DIR']=str(Path(cls.t.name)/'db')
        spec=importlib.util.spec_from_file_location('agentflow_fast',cls.repo/'.agentflow/bin/agentflow.py')
        cls.a=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.a)
        cls.conn=cls.a.db()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        if cls.old is None: os.environ.pop('AGENTFLOW_STATE_DIR',None)
        else: os.environ['AGENTFLOW_STATE_DIR']=cls.old
        cls.t.cleanup()

    def task(self,session,request='Please implement auth correctly'):
        task=self.a.create_task(self.conn,request,session)
        self.a.bind_session(self.conn,session,task,provider='test')
        return task

    def prepare(self,task):
        path=self.a.contract_path(task)
        obj=json.loads(path.read_text())
        obj.update(objective='Fix authentication error on expired token',
                   scope=['src/auth/**','tests/auth/**'],out_of_scope=['src/dashboard/**'],
                   acceptance=['Session expiration produces deterministic auth error'],
                   verification=['Unit test auth code'],risk='MEDIUM',complexity='MEDIUM',
                   assumptions=['No schema change needed'],open_questions=[],impact='Auth only')
        path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
        return self.a.propose(self.conn,task)

    def test_complete_lifecycle(self):
        a=self.a; db=self.conn
        t=self.task('Session-Alpha')
        # Pre-approval: allow contract, deny code.
        pre={'session_id':'Session-Alpha','tool_name':'Write','tool_input':{'file_path':str(a.contract_path(t))}}
        self.assertTrue(a.guard_tool(db,pre)[0])
        product={'session_id':'Session-Alpha','tool_name':'Write','tool_input':{'file_path':str(self.repo/'src/auth/login.py')}}
        self.assertFalse(a.guard_tool(db,product)[0])
        self.assertRaises(ValueError,a.propose,db,t)
        sig=self.prepare(t)
        self.assertEqual(len(sig),64)
        self.assertFalse(a.approved(db,t))
        res=a.user_hook(db,{'session_id':'Session-Alpha','prompt':'Duyệt'})
        self.assertIn('Đã ghi nhận',res)
        self.assertTrue(a.approved(db,t))
        self.assertTrue(a.guard_tool(db,product)[0])
        other={'session_id':'Session-Alpha','tool_name':'Write','tool_input':{'file_path':str(self.repo/'src/dashboard/ui.py')}}
        self.assertFalse(a.guard_tool(db,other)[0])
        self.assertFalse(a.guard_tool(db,{'session_id':'Session-Alpha','tool_name':'Bash','tool_input':{'command':'npm install bad'}})[0])
        self.assertTrue(a.guard_tool(db,{'session_id':'Session-Alpha','tool_name':'Bash','tool_input':{'command':'git status --short'}})[0])
        # Same scope but different files: parallel allowed; same path: denied.
        t2=self.task('Session-Beta'); self.prepare(t2)
        self.assertIn('Đã ghi nhận',a.user_hook(db,{'session_id':'Session-Beta','prompt':'Duyệt'}))
        collide=dict(product,session_id='Session-Beta')
        self.assertFalse(a.guard_tool(db,collide)[0])
        disjoint=dict(collide,tool_input={'file_path':str(self.repo/'src/auth/other.py')})
        self.assertTrue(a.guard_tool(db,disjoint)[0])
        a.release(db,'file:src/auth/login.py','Session-Alpha')
        self.assertTrue(a.guard_tool(db,collide)[0])
        # New message requires preflight, continuation restores execution.
        a.user_hook(db,{'session_id':'Session-Alpha','prompt':'Bổ sung điều chỉnh khác'})
        self.assertFalse(a.guard_tool(db,product)[0])
        self.assertIn('TIẾP QUẢN',a.user_hook(db,{'session_id':'Session-Alpha','prompt':'Tiếp tục '+t}))
        a.release(db,'file:src/auth/login.py','Session-Beta')
        self.assertTrue(a.guard_tool(db,product)[0])
        # Fingerprint mismatch revokes approval.
        cp=a.contract_path(t)
        cp.write_text(cp.read_text().replace('Auth only','Auth plus dashboard'))
        self.assertFalse(a.approved(db,t))
        self.assertFalse(a.guard_tool(db,product)[0])
        # Rendered SPEC mismatch also revokes approval.
        cp.write_text(cp.read_text().replace('Auth plus dashboard','Auth only'))
        self.assertTrue(a.approved(db,t))
        sp=a.task_path(t)/'SPEC.md'
        sp.write_text(sp.read_text()+'\nTAMPER')
        self.assertFalse(a.approved(db,t))
        # Model routing never invents named model/usage data.
        advice=a.model_advice(db,t,'codex')
        self.assertEqual(advice['usage_mode'],'UNKNOWN')
        self.assertEqual(advice['model_candidates'],[])
        self.assertTrue(advice['recommendation_only'])
        # Dangerous paths/invalid broad scope rejected.
        self.assertRaises(ValueError,a.clean_scope,'**')
        self.assertRaises(ValueError,a.inside_repo,str(Path(self.t.name)/'external.py'))
        # Shell policy denies chaining.
        self.assertFalse(a.readonly_shell('git status && rm -rf .'))


    def test_hook_configuration_files(self):
        for hook_file in (self.repo/'.codex/hooks.json',self.repo/'.claude/settings.json'):
            config=json.loads(hook_file.read_text())
            self.assertIn('UserPromptSubmit',config['hooks'])
            self.assertIn('PreToolUse',config['hooks'])
            self.assertIn('PostToolUse',config['hooks'])

    def test_strong_model_tier_from_high_risk(self):
        task=self.task('Risky-Turn')
        obj=json.loads(self.a.contract_path(task).read_text())
        obj.update(risk='HIGH',complexity='LOW')
        self.a.contract_path(task).write_text(json.dumps(obj))
        advice=self.a.model_advice(self.conn,task,'claude')
        self.assertEqual(advice['capability_tier'],'DEEP')
        self.assertEqual(advice['model_candidates'],[])

    def test_unknown_tool_fails_closed(self):
        task=self.task('Unknown-Turn')
        event=dict(session_id='Unknown-Turn',tool_name='mcp__unknown__unsafe_write',tool_input={'path':'src/a.py'})
        allowed,_=self.a.guard_tool(self.conn,event)
        self.assertFalse(allowed)

    def test_task_id_validation_and_relative_scope(self):
        with self.assertRaises(ValueError): self.a.task_path('../bad')
        with self.assertRaises(ValueError): self.a.clean_scope('../src/**')
        with self.assertRaises(ValueError): self.a.clean_scope('.git/**')
        self.assertEqual(self.a.clean_scope('src/feature/**'),'src/feature/**')


if __name__=='__main__': unittest.main()

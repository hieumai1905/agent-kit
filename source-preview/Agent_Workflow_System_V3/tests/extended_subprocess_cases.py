import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOP=Path(__file__).resolve().parent.parent
INSTALL=TOP/'install.py'


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='agentflow-v3-')
        self.addCleanup(self.temp.cleanup)
        self.repo=Path(self.temp.name)/'project'
        self.repo.mkdir()
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        cmd=[sys.executable,str(INSTALL),'--repo',str(self.repo),'--apply']
        r=subprocess.run(cmd,text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.script=self.repo/'.agentflow/bin/agentflow.py'
        self.env=dict(os.environ,AGENTFLOW_STATE_DIR=str(Path(self.temp.name)/'state'))
        spec=importlib.util.spec_from_file_location('agentflow',self.script)
        self.af=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.af)
        self.state_env=os.environ.get('AGENTFLOW_STATE_DIR')
        os.environ['AGENTFLOW_STATE_DIR']=self.env['AGENTFLOW_STATE_DIR']
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        if self.state_env is None: os.environ.pop('AGENTFLOW_STATE_DIR',None)
        else: os.environ['AGENTFLOW_STATE_DIR']=self.state_env

    def cmd(self,*args,stdin=None):
        return subprocess.run([sys.executable,str(self.script),*args],cwd=self.repo,
                              env=self.env,input=stdin,text=True,capture_output=True)

    def hook(self,event,payload):
        return self.cmd('hook',event,stdin=json.dumps(payload,ensure_ascii=False))

    def new(self,session='S1'):
        response=self.hook('prompt',dict(session_id=session,prompt='Sửa lỗi đăng nhập thật chi tiết ở module auth'))
        self.assertEqual(response.returncode,0,response.stderr)
        ids=list((self.repo/'docs/agentflow/tasks').glob('T-*'))
        self.assertTrue(ids)
        return sorted(ids)[-1].name

    def contract(self,task):
        path=self.repo/'docs/agentflow/tasks'/task/'contract.json'
        obj=json.loads(path.read_text())
        obj.update(objective='Khắc phục lỗi đăng nhập khi phiên hết hạn',
                   scope=['src/auth/**','tests/auth/**'],out_of_scope=['src/dashboard/**'],
                   acceptance=['Khi session hết hạn, người dùng nhận lỗi đúng cách'],
                   verification=['Chạy unit test auth'],risk='MEDIUM',complexity='MEDIUM',
                   assumptions=['Chưa xác minh cách xử lý refresh token'],open_questions=[],
                   impact='Auth module, không đổi migration')
        path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
        return path

    def approve(self,task,session='S1'):
        self.contract(task)
        p=self.cmd('propose',task)
        self.assertEqual(p.returncode,0,p.stderr)
        a=self.hook('prompt',dict(session_id=session,prompt='Duyệt'))
        self.assertEqual(a.returncode,0,a.stderr)
        self.assertIn('Đã ghi nhận',a.stdout)

    def test_auto_create_requires_approval(self):
        task=self.new()
        r=self.hook('pretool',dict(session_id='S1',tool_name='Write',tool_input={'file_path':str(self.repo/'src/auth/login.py')}))
        self.assertEqual(r.returncode,2)
        self.assertIn('Chưa duyệt',r.stderr)
        self.assertFalse((self.repo/'src/auth/login.py').exists())
        self.assertIn('PREFLIGHT', (self.repo/'docs/agentflow/tasks'/task/'STATE.md').read_text())

    def test_preflight_contract_only(self):
        task=self.new()
        path=self.repo/'docs/agentflow/tasks'/task/'contract.json'
        self.assertEqual(self.hook('pretool',dict(session_id='S1',tool_name='Write',tool_input={'file_path':str(path)})).returncode,0)
        self.assertEqual(self.hook('pretool',dict(session_id='S1',tool_name='Write',tool_input={'file_path':str(self.repo/'AGENTS.md')})).returncode,2)

    def test_propose_requires_full_contract(self):
        task=self.new()
        invalid=self.cmd('propose',task)
        self.assertEqual(invalid.returncode,2)
        self.contract(task)
        valid=self.cmd('propose',task)
        self.assertEqual(valid.returncode,0,valid.stderr)
        self.assertIn('Task Contract',valid.stdout)

    def test_chat_approve_allows_in_scope_and_blocks_outside(self):
        task=self.new(); self.approve(task)
        inside=self.hook('pretool',dict(session_id='S1',tool_name='Write',tool_input={'file_path':str(self.repo/'src/auth/login.py')}))
        outside=self.hook('pretool',dict(session_id='S1',tool_name='Write',tool_input={'file_path':str(self.repo/'src/dashboard/home.py')}))
        self.assertEqual(inside.returncode,0,inside.stderr)
        self.assertEqual(outside.returncode,2)
        self.assertIn('Ngoài write scope',outside.stderr)

    def test_new_prompt_forces_preflight_until_continue(self):
        task=self.new(); self.approve(task)
        r=self.hook('prompt',dict(session_id='S1',prompt='Tiện thể sửa dashboard luôn'))
        self.assertIn('PREFLIGHT',r.stdout)
        blocked=self.hook('pretool',dict(session_id='S1',tool_name='Write',tool_input={'file_path':str(self.repo/'src/auth/login.py')}))
        self.assertEqual(blocked.returncode,2)
        r=self.hook('prompt',dict(session_id='S1',prompt='Tiếp tục '+task))
        self.assertIn('TIẾP QUẢN',r.stdout)
        allowed=self.hook('pretool',dict(session_id='S1',tool_name='Write',tool_input={'file_path':str(self.repo/'src/auth/login.py')}))
        self.assertEqual(allowed.returncode,0,allowed.stderr)

    def test_spec_mutation_invalidates_approval(self):
        task=self.new(); self.approve(task)
        c=self.repo/'docs/agentflow/tasks'/task/'contract.json'
        c.write_text(c.read_text().replace('Auth module','Auth and payment'))
        r=self.hook('pretool',dict(session_id='S1',tool_name='Write',tool_input={'file_path':str(self.repo/'src/auth/login.py')}))
        self.assertEqual(r.returncode,2)
        self.assertFalse(self.af.approved(self.af.db(),task))

    def test_rendered_spec_mutation_invalidates_approval(self):
        task=self.new(); self.approve(task)
        spec=self.repo/'docs/agentflow/tasks'/task/'SPEC.md'
        spec.write_text(spec.read_text()+'\nExtra unchecked text')
        self.assertFalse(self.af.approved(self.af.db(),task))

    def test_same_file_lock_conflict_but_different_files_parallel(self):
        task=self.new(); self.approve(task)
        new=self.hook('prompt',dict(session_id='S2',prompt='Task tiếp theo cần chỉnh sửa auth'))
        task2=max(x.name for x in (self.repo/'docs/agentflow/tasks').glob('T-*') if x.name!=task)
        self.approve(task2,session='S2')
        f1=str(self.repo/'src/auth/a.py'); f2=str(self.repo/'src/auth/b.py')
        def write(session,file):
            return self.hook('pretool',dict(session_id=session,tool_name='Write',tool_input={'file_path':file}))
        self.assertEqual(write('S1',f1).returncode,0)
        self.assertEqual(write('S2',f1).returncode,2)
        self.assertEqual(write('S2',f2).returncode,0)
        self.hook('posttool',dict(session_id='S1',tool_name='Write',tool_input={'file_path':f1}))
        self.assertEqual(write('S2',f1).returncode,0)

    def test_shell_and_patch_blocked_when_unapproved(self):
        self.new()
        denied=self.hook('pretool',dict(session_id='S1',tool_name='Bash',tool_input={'command':'npm install bad'}))
        self.assertEqual(denied.returncode,2)
        allowed=self.hook('pretool',dict(session_id='S1',tool_name='Bash',tool_input={'command':'git status --short'}))
        self.assertEqual(allowed.returncode,0)
        patch='*** Begin Patch\n*** Add File: src/auth/a.py\n+hello\n*** End Patch'
        self.assertEqual(self.hook('pretool',dict(session_id='S1',tool_name='apply_patch',tool_input={'command':patch})).returncode,2)

    def test_cannot_write_outside_repo_even_approved(self):
        task=self.new(); self.approve(task)
        path=str(Path(self.temp.name)/'outside.py')
        r=self.hook('pretool',dict(session_id='S1',tool_name='Write',tool_input={'file_path':path}))
        self.assertEqual(r.returncode,2)

    def test_model_advisor_does_not_invent_model(self):
        task=self.new(); self.contract(task)
        result=self.cmd('model-advice',task,'--provider','claude')
        self.assertEqual(result.returncode,0)
        obj=json.loads(result.stdout)
        self.assertEqual(obj['model_candidates'],[])
        self.assertEqual(obj['usage_mode'],'UNKNOWN')
        self.assertTrue(obj['recommendation_only'])

    def test_no_fake_quality_pass(self):
        task=self.new(); self.approve(task)
        result=self.cmd('verify',task)
        self.assertEqual(result.returncode,3)
        self.assertIn('NO_CHECKS_CONFIGURED',result.stdout)

    def test_installer_is_idempotent_and_respects_existing_rules(self):
        rules=self.repo/'AGENTS.md'
        rules.write_text('CUSTOM RULES\n')
        res=subprocess.run([sys.executable,str(INSTALL),'--repo',str(self.repo),'--apply'],text=True,capture_output=True)
        self.assertEqual(res.returncode,0,res.stderr)
        self.assertIn('CUSTOM RULES',rules.read_text())
        self.assertIn('AWSYS MANAGED RULES',rules.read_text())
        res2=subprocess.run([sys.executable,str(INSTALL),'--repo',str(self.repo)],text=True,capture_output=True)
        self.assertEqual(res2.returncode,0)
        self.assertNotIn('UPDATE AGENTS.md',res2.stdout)


if __name__=='__main__':unittest.main()

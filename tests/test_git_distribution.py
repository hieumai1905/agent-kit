"""Distribution must work from a Git clone without packaging Git metadata."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

def tool(name,root):
    root=root.resolve()
    spec=importlib.util.spec_from_file_location('distribution_'+name,ROOT/'tools'/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.ROOT=root
    if hasattr(module,'MANIFEST'):module.MANIFEST=root/'release/MANIFEST_SHA256.json'
    return module


class GitDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        (self.root/'app.py').write_text('# fixture\n')
        (self.root/'release').mkdir()
        (self.root/'release/MANIFEST_SHA256.json').write_text(json.dumps({'sha256':{
            'app.py':hashlib.sha256((self.root/'app.py').read_bytes()).hexdigest()}}))

    def verify(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=tool('verify_release.py',self.root).main()
        return code,json.loads(output.getvalue())

    def test_verifier_accepts_actual_Git_metadata_but_rejects_unlisted_payload(self):
        subprocess.run(['git','init','-q'],cwd=self.root,check=True,capture_output=True)
        self.assertEqual(self.verify()[0],0)
        (self.root/'unexpected.py').write_text('# unexpected payload\n')
        code,result=self.verify();self.assertEqual(code,2)
        self.assertIn('unexpected.py',str(result['failures']))

    def test_builder_excludes_git_metadata_and_keeps_instruction_files(self):
        git=self.root/'.git';git.mkdir();(git/'config').write_text('fixture metadata')
        (self.root/'.gitignore').write_text('__pycache__/\n')
        (self.root/'INIT_PROMPT.md').write_text('Fixture bootstrap instructions')
        files={p.relative_to(self.root).as_posix() for p in tool('build_practical_release.py',self.root).source_files()}
        self.assertNotIn('.git/config',files);self.assertIn('.gitignore',files)
        self.assertIn('INIT_PROMPT.md',files)

    def test_git_worktree_pointer_is_not_a_payload_file(self):
        (self.root/'.git').write_text('gitdir: /fixture/worktree\n')
        self.assertEqual(self.verify()[0],0)
        files={p.relative_to(self.root).as_posix() for p in tool('build_practical_release.py',self.root).source_files()}
        self.assertNotIn('.git',files)

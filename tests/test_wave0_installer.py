"""Wave-0 installer regression tests; operate only on throwaway Git repos."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
INSTALLER = BASE / 'source-preview' / 'Agent_Workflow_System_V3' / 'install.py'


class InstallerPreviewSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agentflow-wave0-')
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True, capture_output=True)
        (self.repo / 'AGENTS.md').write_text('# Existing project instructions\n', encoding='utf-8')
        (self.repo / '.claude').mkdir()
        (self.repo / '.claude' / 'settings.json').write_text(
            json.dumps({'permissions': {'deny': ['Bash(rm:*)']}, 'hooks': {}}), encoding='utf-8'
        )
        self.env = dict(os.environ, HOME=str(self.root / 'test-home'))
        (self.root / 'test-home').mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def run_install(self, *extra):
        return subprocess.run(['python3', str(INSTALLER), '--repo', str(self.repo), *extra],
                              env=self.env, text=True, capture_output=True)

    def test_dry_run_does_not_mutate_repo(self):
        original_agents = (self.repo / 'AGENTS.md').read_bytes()
        original_claude = (self.repo / '.claude' / 'settings.json').read_bytes()
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('DRY-RUN:', result.stdout)
        self.assertEqual(original_agents, (self.repo / 'AGENTS.md').read_bytes())
        self.assertEqual(original_claude, (self.repo / '.claude' / 'settings.json').read_bytes())
        self.assertFalse((self.repo / '.agentflow').exists())
        self.assertFalse((self.root / 'test-home' / 'Library').exists())

    def test_apply_merge_and_rollback_in_temporary_repo(self):
        original_agents = (self.repo / 'AGENTS.md').read_bytes()
        original_claude = (self.repo / '.claude' / 'settings.json').read_bytes()
        result = self.run_install('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.repo / '.agentflow' / 'bin' / 'agentflow.py').exists())
        self.assertTrue((self.repo / 'AGENTS.md').read_bytes().startswith(original_agents))
        settings = json.loads((self.repo / '.claude' / 'settings.json').read_text())
        self.assertEqual(settings['permissions'], {'deny': ['Bash(rm:*)']})
        self.assertIn('PreToolUse', settings['hooks'])
        manifests = list((self.root / 'test-home').rglob('manifest.json'))
        self.assertEqual(len(manifests), 1)
        rollback = subprocess.run(['python3', str(INSTALLER), '--rollback', str(manifests[0].parent)],
                                  env=self.env, text=True, capture_output=True)
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(original_agents, (self.repo / 'AGENTS.md').read_bytes())
        self.assertEqual(original_claude, (self.repo / '.claude' / 'settings.json').read_bytes())
        self.assertFalse((self.repo / '.agentflow' / 'bin' / 'agentflow.py').exists())


if __name__ == '__main__':
    unittest.main()

"""Adversarial scratch-only regression suite for G2 hardlink and broker design.

Tests describe bounded implementation properties, NOT mandatory OS enforcement.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import hashlib
import multiprocessing
import os
from pathlib import Path
import random
import shutil
import stat
import string
import tempfile
import unittest

from agentflow_security.hardened_lab import (
    HardenedScratchWriter, LabDenied, TestOnlyProposal, MISSING, MARKER,
    checked_parts, digest, make_disposable_lab, MAX_BYTES,
)


def worker_compete(root: str, target: str, expected: str, payload: bytes) -> tuple[bool, str]:
    """Simulate two cooperative workers; this is NOT a hostile-process proof."""
    writer = HardenedScratchWriter(root)
    p = TestOnlyProposal(target, expected, digest(payload), 1)
    try:
        result = writer.apply(p, payload)
        return True, result['after']
    except LabDenied as exc:
        return False, str(exc)


class G2HardenedScratchTests(unittest.TestCase):
    def setUp(self):
        self.root = make_disposable_lab()
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        self.writer = HardenedScratchWriter(self.root)
        self.existing = self.root / 'src' / 'original.py'
        self.existing.write_bytes(b'print("original")\n')

    def do_apply(self, rel='src/original.py', before=None, body=b'print("new")\n'):
        if before is None:
            before = digest(b'print("original")\n')
        return self.writer.apply(TestOnlyProposal(rel, before, digest(body), 1), body)

    def test_normal_replacement(self):
        out = self.do_apply()
        self.assertEqual(out['before'], digest(b'print("original")\n'))
        self.assertEqual(out['after'], digest(b'print("new")\n'))
        self.assertFalse(out['enforced'])
        self.assertFalse(out['write_authorized'])
        self.assertEqual(self.existing.read_bytes(), b'print("new")\n')

    def test_new_file_creation(self):
        out = self.do_apply('src/new.py', MISSING, b'# new\n')
        self.assertEqual(out['before'], MISSING)
        self.assertEqual((self.root/'src/new.py').read_bytes(), b'# new\n')

    def test_empty_content(self):
        self.do_apply(body=b'')
        self.assertEqual(self.existing.read_bytes(), b'')

    def test_mode_preservation(self):
        self.existing.chmod(0o750)
        self.do_apply()
        self.assertEqual(stat.S_IMODE(self.existing.stat().st_mode), 0o750)

    def test_existing_file_is_replaced_not_truncated(self):
        handle = os.open(self.existing, os.O_RDONLY)
        try:
            inode_before = os.fstat(handle).st_ino
            self.do_apply()
            self.assertNotEqual(inode_before, self.existing.stat().st_ino)
            os.lseek(handle, 0, os.SEEK_SET)
            self.assertEqual(os.read(handle, 100), b'print("original")\n')
        finally:
            os.close(handle)

    def test_reject_stale_base(self):
        with self.assertRaisesRegex(LabDenied, 'Stale baseline'):
            self.do_apply(before='0'*64)
        self.assertEqual(self.existing.read_bytes(), b'print("original")\n')

    def test_reject_expected_missing_if_exists(self):
        with self.assertRaises(LabDenied):
            self.do_apply(before=MISSING)

    def test_reject_missing_if_expected_old(self):
        with self.assertRaises(LabDenied):
            self.do_apply('src/nonexistent.py', digest(b'old'))

    def test_reject_wrong_payload(self):
        p = TestOnlyProposal('src/original.py', digest(self.existing.read_bytes()), digest(b'allowed'), 1)
        with self.assertRaisesRegex(LabDenied, 'bound digest'):
            self.writer.apply(p, b'not allowed')
        self.assertEqual(self.existing.read_bytes(), b'print("original")\n')

    def test_reject_fake_issuer(self):
        p = TestOnlyProposal('src/original.py', digest(self.existing.read_bytes()), digest(b'x'), 1, 'AGENT')
        with self.assertRaises(LabDenied):
            self.writer.apply(p, b'x')

    def test_reject_replayed_epoch(self):
        p = TestOnlyProposal('src/original.py', digest(self.existing.read_bytes()), digest(b'x'), 0)
        with self.assertRaises(LabDenied):
            self.writer.apply(p, b'x')

    def test_reject_bool_epoch(self):
        p = TestOnlyProposal('src/original.py', digest(self.existing.read_bytes()), digest(b'x'), True)
        with self.assertRaises(LabDenied):
            self.writer.apply(p, b'x')

    def test_reject_oversize_payload(self):
        with self.assertRaises(LabDenied):
            self.do_apply(body=b'x'*(MAX_BYTES+1))
        self.assertEqual(self.existing.read_bytes(), b'print("original")\n')

    def test_reject_oversize_old(self):
        with self.existing.open('wb') as f:
            f.truncate(MAX_BYTES+1)
        with self.assertRaises(LabDenied):
            self.writer.apply(TestOnlyProposal('src/original.py','0'*64,digest(b'x'),1),b'x')

    def test_reject_direct_symlink_to_protected(self):
        canary = self.root/'canary-secret.txt'
        canary.write_bytes(b'secret')
        (self.root/'src/link.py').symlink_to(canary)
        with self.assertRaises(LabDenied):
            self.do_apply('src/link.py', digest(b'secret'))
        self.assertEqual(canary.read_bytes(), b'secret')

    def test_reject_intermediate_symlink(self):
        protected = self.root/'other'
        protected.mkdir()
        (self.root/'src/linkdir').symlink_to(protected, target_is_directory=True)
        with self.assertRaises(LabDenied):
            self.do_apply('src/linkdir/secret.txt', MISSING, b'bad')
        self.assertFalse((protected/'secret.txt').exists())

    def test_preexisting_hardlink_attack_is_denied(self):
        outside = self.root/'synthetic_protected.txt'
        outside.write_bytes(b'PROTECTED_ORIGINAL')
        os.link(outside, self.root/'src/external_alias.py')
        self.assertEqual(outside.stat().st_ino, (self.root/'src/external_alias.py').stat().st_ino)
        with self.assertRaisesRegex(LabDenied, 'single-link'):
            self.do_apply('src/external_alias.py', digest(outside.read_bytes()), b'ATTACK')
        self.assertEqual(outside.read_bytes(), b'PROTECTED_ORIGINAL')

    def test_preexisting_hardlink_is_real_bypass_for_direct_write(self):
        # Reproduces the class of behavior seen on user's Mac, WITHOUT running
        # any sandbox or touching non-synthetic data. Shows why broker alone
        # cannot protect if direct write is allowed.
        protected = self.root/'synthetic_protected.txt'
        protected.write_bytes(b'SECRET')
        alias = self.root/'src/alias.py'
        os.link(protected, alias)
        alias.write_bytes(b'OVERRIDDEN')
        self.assertEqual(protected.read_bytes(), b'OVERRIDDEN')

    def test_reject_hardlinked_lock_file(self):
        lock = self.root/'.AGENTFLOW_ASSURANCE_TEST_LOCK'
        outsider = self.root/'another.txt'
        outsider.write_bytes(b'x')
        os.link(outsider, lock)
        with self.assertRaises(LabDenied):
            self.do_apply()
        self.assertEqual(outsider.read_bytes(), b'x')

    def test_reject_symlink_lock_file(self):
        lock = self.root/'.AGENTFLOW_ASSURANCE_TEST_LOCK'
        protected = self.root/'another.txt'
        protected.write_bytes(b'x')
        lock.symlink_to(protected)
        with self.assertRaises(LabDenied):
            self.do_apply()
        self.assertEqual(protected.read_bytes(), b'x')

    def test_reject_existing_directory_as_target(self):
        (self.root/'src/subdir').mkdir()
        with self.assertRaises(LabDenied):
            self.do_apply('src/subdir', MISSING, b'new')

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'requires POSIX FIFO')
    def test_reject_fifo_without_blocking(self):
        os.mkfifo(self.root/'src/special')
        with self.assertRaises(LabDenied):
            self.do_apply('src/special', MISSING, b'x')

    def test_reject_world_writable_parent(self):
        (self.root/'src').chmod(0o777)
        with self.assertRaises(LabDenied):
            self.do_apply()
        self.existing.parent.chmod(0o700)

    def test_reject_modified_marker(self):
        (self.root/MARKER).write_text('not the marker')
        with self.assertRaises(LabDenied):
            HardenedScratchWriter(self.root)

    def test_reject_root_without_marker(self):
        outside = Path(tempfile.mkdtemp(prefix='agentflow_assurance_'))
        self.addCleanup(lambda: shutil.rmtree(outside, ignore_errors=True))
        with self.assertRaises(LabDenied):
            HardenedScratchWriter(outside)

    def test_reject_non_scratch_directory(self):
        with self.assertRaises(LabDenied):
            HardenedScratchWriter(Path('/tmp'))

    def test_reject_root_symlink(self):
        link = self.root.parent / (self.root.name + '_symlink')
        link.symlink_to(self.root, target_is_directory=True)
        self.addCleanup(lambda: link.unlink(missing_ok=True))
        with self.assertRaises(LabDenied):
            HardenedScratchWriter(link)

    def test_reject_non_normalized_reserved(self):
        bad = ['.GIT/config','src/.AgentFlow/state','src/.AGENTFLOW_ASSURANCE_TEST_LOCK']
        for rel in bad:
            with self.subTest(path=rel), self.assertRaises(LabDenied):
                self.do_apply(rel, MISSING, b'x')

    def test_reject_unicode_non_nfc(self):
        with self.assertRaises(LabDenied):
            checked_parts('src/ca\u0301fe.txt')

    def test_reject_test_grant_with_modified_path(self):
        p = TestOnlyProposal('src/original.py',digest(self.existing.read_bytes()), digest(b'x'),1)
        bad = replace(p, relative_path='../../unsafe')
        with self.assertRaises(LabDenied):
            self.writer.apply(bad,b'x')

    def test_reject_untrusted_proposal_function(self):
        with self.assertRaisesRegex(LabDenied, 'no implicit authorization'):
            self.writer.proposal('src/new.py', b'x')

    def test_no_temp_files_left_after_stale(self):
        with self.assertRaises(LabDenied):
            self.do_apply(before='a'*64)
        self.assertFalse(list((self.root/'src').glob('.agentflow-lab-tmp-*')))

    @unittest.skipUnless(hasattr(os, 'setxattr'), 'xattr not available')
    def test_reject_xattr_bearing_files(self):
        try:
            os.setxattr(self.existing, 'user.agentflow-test', b'x')
        except OSError:
            self.skipTest('filesystem cannot set test xattr')
        with self.assertRaises(LabDenied):
            self.do_apply()

    def test_two_workers_same_snapshot_one_wins(self):
        old = digest(self.existing.read_bytes())
        with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context('spawn')) as pool:
            futs = [pool.submit(worker_compete, str(self.root), 'src/original.py', old, f'body-{i}'.encode()) for i in range(2)]
            outputs = [f.result(timeout=15) for f in futs]
        self.assertEqual(sum(1 for ok,_ in outputs if ok), 1, outputs)
        self.assertIn(self.existing.read_bytes(), (b'body-0', b'body-1'))

    def test_two_workers_create_same_name_one_wins(self):
        with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context('spawn')) as pool:
            futs = [pool.submit(worker_compete, str(self.root), 'src/new.py', MISSING, f'new-{i}'.encode()) for i in range(2)]
            outputs = [f.result(timeout=15) for f in futs]
        self.assertEqual(sum(1 for ok,_ in outputs if ok), 1, outputs)
        self.assertIn((self.root/'src/new.py').read_bytes(), (b'new-0', b'new-1'))

    def test_randomized_path_rejections_do_not_touch_canary(self):
        """Seeded adversarial path exercise, not a full OS security proof."""
        rng = random.Random(7331)
        canary = self.root/'canary.txt'
        canary.write_bytes(b'CANARY')
        components = ['..', '.', '', '.git', '.GIT', '.agentflow', '\\', '\x00','\n','\r',
                      'src/..', '/tmp/elsewhere','src//file','src/../canary.txt','src/.AgentFlow/file']
        for _ in range(300):
            candidate = rng.choice(components)
            bad_path = candidate if '/' in candidate else 'src/' + candidate + '/result.py'
            with self.assertRaises(LabDenied, msg=bad_path):
                self.do_apply(bad_path, MISSING, b'bad')
        self.assertEqual(canary.read_bytes(), b'CANARY')

    def test_test_only_grant_is_not_real_proof(self):
        """No database task/approval or OS protected signer is created."""
        p = TestOnlyProposal('src/original.py',digest(self.existing.read_bytes()), digest(b'y'),1)
        out = self.writer.apply(p,b'y')
        self.assertEqual(out['method'], 'TEST_ONLY_ATOMIC_REPLACE')
        self.assertFalse(out['enforced'])
        self.assertFalse(out['write_authorized'])


class G2PathPolicyTests(unittest.TestCase):
    def test_reject_path_classes(self):
        bad_paths = [
            '', '/', '/private/tmp/x', 'a/../b', './a', 'a/./b', 'a//b', 'a/',
            'a\\b', 'a\x00b', '.git/config', '.GIT/config', 'x/.agentflow/z',
            MARKER, 'a/\r/x', 'a/\n/x', 'a/\x7f/x',
            'a/' + 'x'*256, 'a/'*30 + 'end',
        ]
        for p in bad_paths:
            with self.subTest(p=p), self.assertRaises(LabDenied):
                checked_parts(p)

    def test_accept_normal_programming_paths(self):
        for p in ('src/module.py','src/api/v1/controller.ts','assets/ảnh.png','a b.c'):
            self.assertEqual('/'.join(checked_parts(p)),p)

    def test_sha_length(self):
        self.assertEqual(len(digest(b'')),64)


if __name__ == '__main__':
    unittest.main()

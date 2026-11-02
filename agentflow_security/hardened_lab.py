"""Scratch-only G2 security assurance lab: content-bound, cooperative file replacements.

This is NOT a production write broker, a trusted control plane, an OS sandbox,
or an authorization provider. Same-UID processes may bypass it. It cannot stop
Codex/Claude GUI tools from writing directly. Never use to edit product code.

The lab is intentionally limited to disposable directories beneath system temp.
The grant is a TEST FIXTURE (not an authenticated approval).

Security-critical invariants demonstrated:
* exact, narrow path; no symlink, hardlink, special files, or VCS metadata
* fd-relative traversal, checks on opened inodes, no in-place writes
* content hash pinned at both ends, nonce/epoch check, cooperative root lock
* atomically replace one file within a stable parent, then fsync
* refuse unsupported metadata instead of silently stripping it

External hard prerequisites for enforcement:
* an OS protected identity/control plane and a trusted human approval issuer
* ALL agent direct write paths blocked outside a mandatory broker
* parent directory namespace not writable by untrusted processes
* resource fencing / shared index control / trusted audit in the protected plane
"""
from __future__ import annotations

from dataclasses import dataclass
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile
import unicodedata
from typing import Optional

MARKER = '.AGENTFLOW_ASSURANCE_TEST_ONLY'
LOCK = '.AGENTFLOW_ASSURANCE_TEST_LOCK'
MISSING = 'MISSING'
MAX_BYTES = 2 * 1024 * 1024
SHA = re.compile(r'^[0-9a-f]{64}$')
RESERVED = {'.git', '.agentflow', MARKER, LOCK}


class LabDenied(Exception):
    """A strictly-denied lab mutation; never retry by falling back to direct IO."""


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class TestOnlyProposal:
    """Test-only intent binding. This is NEVER an authenticated write grant."""
    relative_path: str
    before_sha256: str
    after_sha256: str
    epoch: int
    issuer: str = 'DISPOSABLE_TEST_HARNESS_ONLY'


def checked_parts(relative: str) -> tuple[str, ...]:
    if not isinstance(relative, str) or not relative or len(relative) > 1024:
        raise LabDenied('Invalid path')
    if relative.startswith('/') or '\\' in relative or '\x00' in relative or '\r' in relative or '\n' in relative:
        raise LabDenied('Unsafe path encoding')
    parts = relative.split('/')
    try:
        unsafe = (len(parts) > 24 or any(
            part in ('', '.', '..') or part.casefold() in {x.casefold() for x in RESERVED} or
            unicodedata.normalize('NFC', part) != part or
            any(ord(ch) < 32 or ord(ch) == 127 for ch in part) or
            len(part.encode('utf-8')) > 255 for part in parts))
    except (ValueError, UnicodeError):
        raise LabDenied('Invalid Unicode path')
    if unsafe:
        raise LabDenied('Unsafe path component')
    return tuple(parts)


def _dirflags() -> int:
    if not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
        raise LabDenied('Required no-follow/directory flags unavailable')
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0)


def _check_regular(fd: int, *, label: str) -> os.stat_result:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise LabDenied(f'{label} is not a single-link regular file')
    if info.st_size > MAX_BYTES:
        raise LabDenied(f'{label} exceeds size cap')
    # Replacing a named file discards metadata on the old inode. The scratch
    # prototype explicitly denies files with xattrs instead of losing them.
    if hasattr(os, 'listxattr'):
        try:
            attrs = os.listxattr(fd)
        except (OSError, ValueError, TypeError):
            # Unsupported inspection is NOT a reason to assume it is safe.
            raise LabDenied(f'{label} extended attributes cannot be inspected')
        if attrs:
            raise LabDenied(f'{label} has extended attributes')
    return info


def _read_limited(fd: int) -> bytes:
    chunks = []
    length = 0
    while True:
        b = os.read(fd, 65536)
        if not b:
            break
        length += len(b)
        if length > MAX_BYTES:
            raise LabDenied('Existing file exceeds size cap')
        chunks.append(b)
    return b''.join(chunks)


def make_disposable_lab() -> Path:
    """Create a scratch-only root; no product repo path is ever accepted by CLI."""
    root = Path(tempfile.mkdtemp(prefix='agentflow_assurance_', dir=tempfile.gettempdir())).resolve()
    root.chmod(0o700)
    (root / MARKER).write_text('scratch-only\n', encoding='utf-8')
    (root / 'src').mkdir(mode=0o700)
    return root


class HardenedScratchWriter:
    def __init__(self, root: Path | str):
        literal = Path(root).expanduser()
        if literal.is_symlink():
            raise LabDenied('Root is symlink')
        self.root = literal.resolve(strict=True)
        tempbase = Path(tempfile.gettempdir()).resolve(strict=True)
        if self.root == tempbase or tempbase not in self.root.parents or not self.root.name.startswith('agentflow_assurance_'):
            raise LabDenied('Only unique scratch lab directories are allowed')
        meta = self.root.stat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.getuid() or (meta.st_mode & 0o077):
            raise LabDenied('Scratch root must be owned and private')
        marker = self.root / MARKER
        if marker.is_symlink() or not marker.is_file() or marker.read_bytes() != b'scratch-only\n':
            raise LabDenied('Missing exact lab-only marker')
        # No state in a home-directory app, no keys, no production filesystem paths.
        self.epoch = 1

    def proposal(self, relative: str, new_content: bytes) -> TestOnlyProposal:
        """Create a test proposal using a current snapshot (not a real grant)."""
        checked_parts(relative)
        if not isinstance(new_content, bytes) or len(new_content) > MAX_BYTES:
            raise LabDenied('Invalid bytes')
        # A proposal is only accepted if the expected baseline is supplied by
        # the caller / fixture. Caller must pass a baseline, not rely on a read
        # of an attacker-controlled path as authorization.
        raise LabDenied('Use explicit test proposal; no implicit authorization')

    def apply(self, p: TestOnlyProposal, contents: bytes) -> dict:
        if not isinstance(p, TestOnlyProposal) or p.issuer != 'DISPOSABLE_TEST_HARNESS_ONLY':
            raise LabDenied('No test-only proposal')
        parts = checked_parts(p.relative_path)
        if (type(p.epoch) is not int or p.epoch != self.epoch or
            p.before_sha256 != MISSING and not (isinstance(p.before_sha256, str) and SHA.fullmatch(p.before_sha256)) or
            not isinstance(p.after_sha256, str) or not SHA.fullmatch(p.after_sha256)):
            raise LabDenied('Invalid or stale test proposal')
        if not isinstance(contents, bytes) or len(contents) > MAX_BYTES or digest(contents) != p.after_sha256:
            raise LabDenied('Patch content does not match bound digest')
        fds: list[int] = []
        temp_name: Optional[str] = None
        parentfd: Optional[int] = None
        lockfd: Optional[int] = None
        try:
            rootfd = os.open(self.root, _dirflags())
            fds.append(rootfd)
            opened_root = os.fstat(rootfd)
            if (opened_root.st_uid != os.getuid() or (opened_root.st_mode & 0o077)):
                raise LabDenied('Untrusted scratch root permissions')
            if opened_root.st_ino != self.root.stat().st_ino or opened_root.st_dev != self.root.stat().st_dev:
                raise LabDenied('Scratch root changed')
            lockfd = os.open(LOCK, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) |
                             getattr(os, 'O_CLOEXEC', 0), 0o600, dir_fd=rootfd)
            fds.append(lockfd)
            _check_regular(lockfd, label='Lock file')
            fcntl.flock(lockfd, fcntl.LOCK_EX)
            parentfd = rootfd
            for part in parts[:-1]:
                nxt = os.open(part, _dirflags(), dir_fd=parentfd)
                fds.append(nxt)
                dstat = os.fstat(nxt)
                if not stat.S_ISDIR(dstat.st_mode) or dstat.st_uid != os.getuid() or (dstat.st_mode & 0o022):
                    raise LabDenied('Unsafe parent directory permissions')
                parentfd = nxt
            name = parts[-1]
            try:
                oldfd = os.open(name, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) |
                                getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_CLOEXEC', 0), dir_fd=parentfd)
            except FileNotFoundError:
                oldfd = None
            info = None
            if oldfd is None:
                before = MISSING
                new_mode = 0o644
            else:
                fds.append(oldfd)
                info = _check_regular(oldfd, label='Existing target')
                before = digest(_read_limited(oldfd))
                new_mode = stat.S_IMODE(info.st_mode) & 0o777
            if before != p.before_sha256:
                raise LabDenied('Stale baseline; no mutation')
            # Re-verify destination's inode at commit time. This helps catch
            # non-cooperative renames but CANNOT close a hostile TOCTOU race.
            try:
                linked = os.stat(name, dir_fd=parentfd, follow_symlinks=False)
            except FileNotFoundError:
                linked = None
            if (info is None and linked is not None or
                info is not None and (linked is None or (linked.st_dev, linked.st_ino) != (info.st_dev, info.st_ino))):
                raise LabDenied('Destination changed before commit')
            temp_name = '.agentflow-lab-tmp-' + os.urandom(16).hex()
            tmpfd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                            getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0),
                            0o600, dir_fd=parentfd)
            try:
                os.fchmod(tmpfd, new_mode)
                written = 0
                while written < len(contents):
                    count = os.write(tmpfd, contents[written:])
                    if count <= 0:
                        raise LabDenied('Short write')
                    written += count
                os.fsync(tmpfd)
            finally:
                os.close(tmpfd)
            # Recheck before atomic replacement. No malicious concurrent writer
            # is allowed under the actual OS security precondition.
            try:
                at_commit = os.stat(name, dir_fd=parentfd, follow_symlinks=False)
            except FileNotFoundError:
                at_commit = None
            if (info is None and at_commit is not None or info is not None and
                (at_commit is None or (at_commit.st_dev, at_commit.st_ino, at_commit.st_nlink) !=
                                     (info.st_dev, info.st_ino, info.st_nlink))):
                raise LabDenied('Destination raced during staging')
            os.replace(temp_name, name, src_dir_fd=parentfd, dst_dir_fd=parentfd)
            temp_name = None
            os.fsync(parentfd)
            return {
                'relative_path': p.relative_path, 'before': before, 'after': digest(contents),
                'epoch': p.epoch, 'method': 'TEST_ONLY_ATOMIC_REPLACE',
                'write_authorized': False, 'enforced': False,
            }
        except (OSError, OverflowError, ValueError) as e:
            raise LabDenied(f'Denied scratch file operation: {type(e).__name__}') from e
        finally:
            if temp_name is not None and parentfd is not None:
                try:
                    os.unlink(temp_name, dir_fd=parentfd)
                except OSError:
                    pass
            if lockfd is not None:
                try:
                    fcntl.flock(lockfd, fcntl.LOCK_UN)
                except OSError:
                    pass
            for fd in reversed(fds):
                try:
                    os.close(fd)
                except OSError:
                    pass

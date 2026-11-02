"""Cooperative atomic compare-and-replace LAB on scratch files ONLY.

NOT A PRODUCTION WRITE BROKER. Anyone with direct filesystem access can bypass
this module, replace parent directories, alter locks, or write through another
path. It cannot protect Codex/Claude sessions running under the same user.
The lab requires a marker and a scratch root beneath the system temp folder.
"""
from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path
import stat
import tempfile

MARKER = '.AGENTFLOW_MUTATION_LAB_ONLY'
MISSING = 'MISSING'


class MutationLabError(Exception):
    pass


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class MutationLab:
    def __init__(self, root: str | Path):
        literal=Path(root).expanduser()
        if literal.is_symlink():
            raise MutationLabError('Lab root may not be a symlink')
        self.root=literal.resolve(strict=True)
        tempbase=Path(tempfile.gettempdir()).resolve(strict=True)
        if self.root == tempbase or tempbase not in self.root.parents:
            raise MutationLabError('Lab can ONLY use a subdirectory under system temp')
        marker=self.root / MARKER
        if marker.is_symlink() or not marker.is_file() or marker.read_text()!='scratch-only\n':
            raise MutationLabError('Missing exact test-only marker')

    def apply(self, relative: str, *, expected_sha256: str, new_content: bytes) -> dict:
        if (not isinstance(relative,str) or not relative or relative.startswith('/') or
            '\\' in relative or '\x00' in relative or
            any(p in ('','.','..') for p in relative.split('/'))):
            raise MutationLabError('Unsafe relative path')
        parts=relative.split('/')
        if any(p in ('.git','.agentflow',MARKER) for p in parts):
            raise MutationLabError('Git/metadata/marker paths are prohibited in lab')
        if not isinstance(new_content,bytes) or len(new_content)>2*1024*1024:
            raise MutationLabError('Invalid or oversized content')
        if not isinstance(expected_sha256,str) or (expected_sha256 != MISSING and
            not (len(expected_sha256)==64 and all(ch in '0123456789abcdef' for ch in expected_sha256))):
            raise MutationLabError('Invalid baseline digest')
        flags=os.O_RDONLY | getattr(os,'O_DIRECTORY',0) | getattr(os,'O_NOFOLLOW',0)
        fds=[]; temp_name=None; parentfd=None
        try:
            rootfd=os.open(self.root,flags)
            fds.append(rootfd)
            parentfd=rootfd
            for part in parts[:-1]:
                nxt=os.open(part,flags,dir_fd=parentfd)
                fds.append(nxt);parentfd=nxt
            # Cooperative exclusive flock prevents compare-then-replace races among lab workers.
            lockfd=os.open('.agentflow_lab.lock',os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),
                           0o600,dir_fd=parentfd)
            fds.append(lockfd)
            fcntl.flock(lockfd,fcntl.LOCK_EX)
            oldfd=None
            try:
                oldfd=os.open(parts[-1],os.O_RDONLY|getattr(os,'O_NOFOLLOW',0),dir_fd=parentfd)
            except FileNotFoundError:
                pass
            try:
                if oldfd is None:
                    before=MISSING
                else:
                    fds.append(oldfd)
                    st=os.fstat(oldfd)
                    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                        raise MutationLabError('Target must be a regular file without hardlinks')
                    if st.st_size>2*1024*1024:
                        raise MutationLabError('Oversized existing file')
                    contents=b''
                    while True:
                        block=os.read(oldfd,65536)
                        if not block:break
                        contents+=block
                        if len(contents)>2*1024*1024:
                            raise MutationLabError('Oversized existing file')
                    before=sha256(contents)
                if before!=expected_sha256:
                    raise MutationLabError('Stale expected sha256: refusing to overwrite')
                temp_name=f'.tmp-agentflow-{os.getpid()}-{os.urandom(8).hex()}'
                tempfd=os.open(temp_name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),
                               0o600,dir_fd=parentfd)
                try:
                    offset=0
                    while offset<len(new_content):
                        offset+=os.write(tempfd,new_content[offset:])
                    os.fsync(tempfd)
                finally:
                    os.close(tempfd)
                # Atomic name replacement within one directory for cooperating lab clients.
                os.replace(temp_name,parts[-1],src_dir_fd=parentfd,dst_dir_fd=parentfd)
                temp_name=None
                os.fsync(parentfd)
                return {'relative_path':relative,'before':before,'after':sha256(new_content),
                        'algorithm':'COOPERATIVE_LAB_ONLY', 'enforced':False}
            finally:
                fcntl.flock(lockfd,fcntl.LOCK_UN)
        except (OSError,ValueError) as e:
            raise MutationLabError(f'Filesystem lab refused operation: {type(e).__name__}: {e}') from e
        finally:
            if temp_name and fds:
                try:os.unlink(temp_name,dir_fd=parentfd)
                except OSError:pass
            for fd in reversed(fds):
                try:os.close(fd)
                except OSError:pass

"""Product status and capability assertions - intentionally cannot certify macOS GUI."""
from __future__ import annotations
from pathlib import Path
import platform

PROVIDERS=('codex_desktop','codex_cli','claude_desktop','claude_cli')

def capability_matrix():
    return {'host_os':platform.system(),
            'requirements':{'strict_human_approval':'NOT_CERTIFIED',
                            'mandatory_write_boundary':'NOT_CERTIFIED',
                            'same_worktree_multiwriter':'NOT_CERTIFIED',
                            'task_scoped_git':'NOT_CERTIFIED'},
            'providers':{provider:{'mode':'NOT_CERTIFIED',
                                   'code_write_enabled':False,'native_test':'NOT_RUN'}
                         for provider in PROVIDERS},
            'G2':'BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED',
            'installer_mode':'GUIDANCE_ONLY',
            'note':'Neither app discovery, signed mock receipts, nor local sandbox tests certify agent write confinement.'}

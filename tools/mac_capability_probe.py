#!/usr/bin/env python3
"""Read-only discovery report: never changes Codex/Claude config or tests real writes.

No model/API call is made. CLI presence and app bundle metadata are *hints*, not
native security certification. Running this on a Mac is NOT sufficient for G2.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from agentflow_security.gates import adapter_capability_matrix

BUNDLES={
    'codex_desktop':[Path('/Applications/Codex.app'),Path.home()/'Applications/Codex.app'],
    'claude_desktop':[Path('/Applications/Claude.app'),Path.home()/'Applications/Claude.app'],
}

def app_bundle_metadata(bundle:Path) -> dict:
    plist=bundle/'Contents/Info.plist'
    try:
        with plist.open('rb') as f:
            meta=plistlib.load(f)
    except (FileNotFoundError,PermissionError,plistlib.InvalidFileException):
        return {'bundle_path':str(bundle),'metadata':'UNAVAILABLE'}
    return {'bundle_path':str(bundle),'bundle_identifier':meta.get('CFBundleIdentifier'),
            'short_version':meta.get('CFBundleShortVersionString'),
            'build_version':meta.get('CFBundleVersion'),
            'metadata':'OBSERVED_NOT_CERTIFIED'}


def report():
    info=adapter_capability_matrix()
    info['probe_kind']='READ_ONLY_DISCOVERY'
    info['generated_epoch']=int(time.time())
    info['binary_locations']={name:shutil.which(binary) for name,binary in
                              [('codex_cli','codex'),('claude_cli','claude')]}
    info['gui_bundles']={name:[app_bundle_metadata(p) for p in paths if p.is_dir()]
                         for name,paths in BUNDLES.items()}
    info['required_native_checks']=[
        'Pin macOS version, Codex/Claude versions/builds, identity and sandbox mode',
        'Human approval provenance with agent unable to mint/approve own receipt',
        'Block direct writes via shell, patch, MCP and alternate tool paths',
        'Block write if hooks fail, are disabled, time out or are bypassed',
        'Test same-file race, symlink/hardlink/path traversal and rename races',
        'Test app session loss, stale lease and zombie writer fencing',
        'Test Git index, generated files and test DB isolation with 2 active sessions',
        'Test user-run/manual edits, resource freshness and crash recovery',
        'Demonstrate all enforcement under protected identity/OS permissions',
    ]
    info['G2']='BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED'
    return info


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,help='Optional report output (only to explicitly named file)')
    args=p.parse_args(argv)
    data=report()
    result=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        path=args.output.expanduser().resolve()
        if path.exists():
            p.error('Output already exists; refusing to overwrite')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8') as f:
            f.write(result)
    else:
        print(result)
    return 0

if __name__=='__main__':
    raise SystemExit(main())

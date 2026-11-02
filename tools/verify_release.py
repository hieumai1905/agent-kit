#!/usr/bin/env python3
"""Verify hashes against a manifest bundled with RC; not author authenticity."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'release'/'MANIFEST_SHA256.json'

def main():
    try:
        data=json.loads(MANIFEST.read_text(encoding='utf-8'))
        failures=[]
        for relative,expected in data['sha256'].items():
            candidate=ROOT/relative
            p=candidate.resolve()
            if candidate.is_symlink() or not p.is_relative_to(ROOT) or not p.is_file():
                failures.append(f'Missing, symlink or outside: {relative}');continue
            actual=hashlib.sha256(p.read_bytes()).hexdigest()
            if actual!=expected:failures.append(f'Hash mismatch: {relative}')
        expected=set(data['sha256'])
        permitted_unlisted={'release/MANIFEST_SHA256.json','release/PRACTICAL_SMOKE.json'}
        extras=[]
        for fp in ROOT.rglob('*'):
            if (not fp.is_file() or '.git' in fp.relative_to(ROOT).parts
                    or '__pycache__' in fp.parts or fp.suffix=='.pyc'):
                continue
            rel=fp.relative_to(ROOT).as_posix()
            if rel not in expected and rel not in permitted_unlisted:
                extras.append(rel)
        if extras:
            failures.append('Unexpected files: '+', '.join(extras[:20]))
        print(json.dumps({'files_verified':len(data['sha256']),'pass':not failures,
                          'failures':failures,
                          'note':'Manifest is in the same archive; this is not a publisher signature.'},
                         indent=2,ensure_ascii=False))
        return 0 if not failures else 2
    except Exception as e:
        print(f'ERROR: {type(e).__name__}: {e}',file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())

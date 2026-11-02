#!/usr/bin/env python3
"""Reproducible SI development-candidate ZIP + integrity manifest (NOT signed).

The generated file is NEVER a security certification or authorization grant.
Run outside a product repository. Check that acceptance evidence matches code.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE_ROOT='Agent_Workflow_V3_SI_Candidate'
EXCLUDE={'release/MANIFEST_SHA256.json'}


def eligible():
    files=[]
    for fp in ROOT.rglob('*'):
        if not fp.is_file() or '__pycache__' in fp.parts or fp.suffix=='.pyc' or '.release' in fp.parts:
            continue
        if fp.is_symlink():
            raise ValueError('Cannot package symlink: '+str(fp))
        if fp.suffix.lower() in ('.pem','.key','.p12','.pfx'):
            raise ValueError('Refuse sensitive key material: '+str(fp))
        if fp.relative_to(ROOT).as_posix() in EXCLUDE:continue
        files.append(fp)
    return sorted(files,key=lambda p:p.relative_to(ROOT).as_posix())


def build(output:Path) -> dict:
    source=eligible()
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source}
    manifest={'schema':2,'product':'Agent Workflow V3 SI01-SI14 Development Candidate',
              'release_class':'NON_CERTIFIED_SI_DEVELOPMENT_CANDIDATE',
              'note':'Only file integrity (NOT publisher identity, OS enforcement or trusted approval).',
              'sha256':hashes}
    mp=ROOT/'release/MANIFEST_SHA256.json'
    mp.write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    source.append(mp)
    output=output.expanduser().resolve()
    if output.is_relative_to(ROOT):raise ValueError('Output ZIP must be outside source tree')
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():output.unlink()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in source:
            name=ARCHIVE_ROOT+'/'+p.relative_to(ROOT).as_posix()
            info=zipfile.ZipInfo(name,date_time=(2026,10,29,12,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o755 if p.suffix=='.command' else 0o644)<<16
            z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(output) as z:
        bad=z.testzip()
        if bad:raise RuntimeError('ZIP CRC error '+bad)
        paths=z.namelist()
        if len(paths)!=len(set(paths)):raise RuntimeError('Duplicate entry')
        for rel,expected in hashes.items():
            if hashlib.sha256(z.read(ARCHIVE_ROOT+'/'+rel)).hexdigest()!=expected:
                raise RuntimeError('ZIP hash mismatch '+rel)
    zip_digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(zip_digest+'  '+output.name+'\n')
    return {'zip':str(output),'sha256':zip_digest,'source_files_hashed':len(hashes),
            'archive_files':len(source),'archive_bytes':output.stat().st_size,'verified':True}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',default=str(ROOT.parent/'Agent_Workflow_V3_SI01-SI14_Development_Candidate_2026-10-29.zip'))
    args=p.parse_args()
    print(json.dumps(build(Path(args.output)),indent=2,ensure_ascii=False))

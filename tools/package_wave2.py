#!/usr/bin/env python3
"""Build D2 development archive with manifest; refuses to claim G2 certification."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'Agent_Workflow_V3_D2_Trust_Enforcement_Prototype_2026-10-29.zip'
IGNORE={'__pycache__','.DS_Store','.pytest_cache','.mypy_cache'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def paths():
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or any(n in IGNORE for n in p.parts) or p.suffix in {'.pyc','.pyo'}:
            continue
        if p.relative_to(ROOT).as_posix()=='.release/WAVE2_MANIFEST.json':continue
        yield p

def main():
    evidence=json.loads((ROOT/'.release/WAVE2_ACCEPTANCE.json').read_text())
    if (evidence.get('g2_prototype_checks')!='PASS' or evidence['gate_status']['G2']=='PASS' or
        evidence.get('native_os_enforcement_tests')!='NOT_RUN'):
        raise RuntimeError('Cannot package: audit failed or falsely claims G2 certified')
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths()}
    manifest={
        'version':'D2_DEVELOPMENT_NOT_CERTIFIED',
        'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'gate_status':evidence['gate_status'],
        'prototype_checks_passed':True,
        'test_counts':{key:val['tests_executed'] for key,val in evidence['suites'].items()},
        'sha256':hashes,
        'critical_warning':'NOT an installable trusted approval or enforced multiwriter solution',
    }
    manifest_path=ROOT/'.release/WAVE2_MANIFEST.json'
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in [*paths(),manifest_path]:
            z.write(p,arcname=f'{ROOT.name}/{p.relative_to(ROOT).as_posix()}')
    with zipfile.ZipFile(OUT) as z:
        bad=z.testzip()
        if bad:raise RuntimeError('Corrupt zip member '+bad)
    print(json.dumps({'archive':str(OUT),'sha256':sha(OUT),'files':len(hashes)+1,
                      'total_tests':evidence['total_tests'],'G2':evidence['gate_status']['G2'],
                      'installable':False},ensure_ascii=False,indent=2))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Package audited D1 source; never writes to a user's repository."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'Agent_Workflow_V3_D1_Canonical_Foundation_2026-10-29.zip'
IGNORE={'__pycache__','.DS_Store','.pytest_cache','.mypy_cache'}

def files():
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or any(x in IGNORE for x in p.parts) or p.suffix in {'.pyc','.pyo'}:
            continue
        if p.relative_to(ROOT).as_posix()=='.release/WAVE1_MANIFEST.json':
            continue
        yield p

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    evidence=json.loads((ROOT/'.release/WAVE1_ACCEPTANCE.json').read_text())
    if evidence['gate_status']['G1']!='PASS':
        raise RuntimeError('G1 has not passed; refusing to package')
    hashes={p.relative_to(ROOT).as_posix():sha(p) for p in files()}
    manifest={'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
              'version':'D1_DEVELOPMENT_NOT_INSTALLABLE',
              'gate_status':evidence['gate_status'],
              'test_counts':{k:v['tests_executed'] for k,v in evidence['suites'].items()},
              'file_sha256':hashes,
              'certification':evidence['certification'],
              'warning':'No trusted human approval, enforced writes or GUI certification'}
    manifest_path=ROOT/'.release/WAVE1_MANIFEST.json'
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in [*files(), manifest_path]:
            rel=path.relative_to(ROOT).as_posix()
            z.write(path,arcname=f'{ROOT.name}/{rel}')
    with zipfile.ZipFile(OUT) as z:
        invalid=z.testzip()
        if invalid: raise RuntimeError('Archive integrity failure: '+invalid)
    print(json.dumps({'archive':str(OUT),'sha256':sha(OUT),
                      'files':len(hashes)+1,'bytes':OUT.stat().st_size,
                      'gate':'G1 PASS','certified':False},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()

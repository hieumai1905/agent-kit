#!/usr/bin/env python3
"""Create deterministic ZIP and local hash manifest. Not a publisher signature."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import stat
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ZIP_DEST=ROOT.parent/'Agent_Workflow_V3_Integration_Candidate_RC1_2026-10-29.zip'
OMITTED={'release/MANIFEST_SHA256.json','release/ONE_SHOT_ACCEPTANCE.json'}

def files():
    for p in ROOT.rglob('*'):
        if not p.is_file() or p.is_symlink():continue
        if '__pycache__' in p.parts or p.suffix=='.pyc':continue
        if p.relative_to(ROOT).as_posix() in OMITTED:continue
        if p.suffix.lower() in {'.pem','.key','.p12','.pfx'}:
            raise RuntimeError(f'Refuse private key material: {p}')
        if '.release' in p.parts:continue
        yield p

def build():
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files())}
    manifest={'schema':1,'product':'Agent Workflow V3 Integration Candidate RC.1',
              'note':'Integrity only: signer identity is NOT verified; package is NOT_CERTIFIED',
              'sha256':hashes}
    (ROOT/'release'/'MANIFEST_SHA256.json').write_text(
        json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    filenames=sorted(files(),key=lambda p:p.relative_to(ROOT).as_posix())
    manifest_path=ROOT/'release'/'MANIFEST_SHA256.json'
    filenames.append(manifest_path)
    with zipfile.ZipFile(ZIP_DEST,'w',compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9,allowZip64=True) as z:
        for path in filenames:
            name=path.relative_to(ROOT).as_posix()
            data=path.read_bytes()
            info=zipfile.ZipInfo('Agent_Workflow_V3_RC1/'+name,date_time=(2026,10,29,12,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o755 if path.name.endswith('.command') else 0o644)<<16
            z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        # Mutable smoke-report is included but not hashed, because rerunning tests changes it.
        report=ROOT/'release'/'ONE_SHOT_ACCEPTANCE.json'
        if report.exists():
            info=zipfile.ZipInfo('Agent_Workflow_V3_RC1/release/ONE_SHOT_ACCEPTANCE.json',
                                 date_time=(2026,10,29,12,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            z.writestr(info,report.read_bytes())
    result={'zip':str(ZIP_DEST),'sha256':hashlib.sha256(ZIP_DEST.read_bytes()).hexdigest(),
            'files_hashed':len(hashes),'files_in_zip':len(filenames)+int((ROOT/'release'/'ONE_SHOT_ACCEPTANCE.json').exists()),
            'bytes':ZIP_DEST.stat().st_size}
    (ROOT.parent/'Agent_Workflow_V3_RC1_SHA256SUMS.txt').write_text(result['sha256']+'  '+ZIP_DEST.name+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':build()

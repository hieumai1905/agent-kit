#!/usr/bin/env python3
"""Build/verify ONE minimal repo kit; no signing or native security claims."""
from __future__ import annotations
import hashlib,json,os,stat,sys,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT.parent/'Agent_Workflow_Kit_v1.0.1_2026-11-02.zip'
FOLDER='Agent_Workflow_V3_Repo_Kit'
SKIP={'release/MANIFEST_SHA256.json','release/ONE_SHOT_ACCEPTANCE.json','release/PRACTICAL_SMOKE.json'}

def source_files():
    result=[]
    for p in ROOT.rglob('*'):
        if p.is_symlink():raise ValueError('Refuse source symlinks: '+str(p))
        if not p.is_file():continue
        relative=p.relative_to(ROOT)
        text=relative.as_posix()
        if '.git' in relative.parts:continue
        if text in SKIP:continue
        if any(s in relative.parts for s in ('__pycache__','_render_setup','.pytest_cache','.release')):continue
        if p.suffix in ('.pyc','.pyo','.p12','.pfx','.pem','.key','.sqlite','.sqlite3','.db','.log'):
            raise ValueError('Disallowed binary/key/state in deliverable: '+text)
        if text.endswith('.DS_Store'):continue
        result.append(p)
    return sorted(result,key=lambda p:p.relative_to(ROOT).as_posix())

def main():
    files=source_files()
    manifest={'schema':2,'name':'Agent Workflow V3 Minimal Repo Integration Kit',
        'release_class':'PRACTICAL_ADVISORY_RELEASE_NOT_SECURITY_CERTIFIED',
        'version':'1.0.1',
        'purpose':'Repository instructions and optional local workflow tools, no new UI/platform',
        'not_certified':['G2 native approval/enforcement','G5 trusted code mutation','G7 macOS provider E2E'],
        'sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    mf=ROOT/'release/MANIFEST_SHA256.json'
    mf.write_text(json.dumps(manifest,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    files.append(mf)
    files.extend([ROOT/'release/ONE_SHOT_ACCEPTANCE.json',ROOT/'release/PRACTICAL_SMOKE.json'])
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    if OUTPUT.exists():OUTPUT.unlink()
    with zipfile.ZipFile(OUTPUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for file in files:
            info=zipfile.ZipInfo(FOLDER+'/'+file.relative_to(ROOT).as_posix(),date_time=(2026,11,2,12,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o755 if file.suffix=='.command' else 0o644)<<16
            z.writestr(info,file.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(OUTPUT) as z:
        if z.testzip():raise RuntimeError('ZIP CRC error')
        if len(z.namelist())!=len(set(z.namelist())):raise RuntimeError('Duplicate paths')
        for name,expected in manifest['sha256'].items():
            if hashlib.sha256(z.read(FOLDER+'/'+name)).hexdigest()!=expected:
                raise RuntimeError('ZIP hash mismatch: '+name)
        for info in z.infolist():
            if (info.external_attr>>16)&0o170000==stat.S_IFLNK:
                raise RuntimeError('Archive symlink forbidden')
    h=hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    digest_path=OUTPUT.with_suffix(OUTPUT.suffix+'.sha256')
    digest_path.write_text(f'{h}  {OUTPUT.name}\n')
    result={'pass':True,'zip':str(OUTPUT),'sha256':h,'files_hashed':len(manifest['sha256']),
            'zip_entries':len(files),'size_bytes':OUTPUT.stat().st_size,
            'security_certified':False,'output_hash_file':str(digest_path)}
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0
if __name__=='__main__':raise SystemExit(main())

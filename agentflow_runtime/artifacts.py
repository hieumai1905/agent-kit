"""Local-only artifact inventory and read-only INDEX inspection. No Git writer/hook."""
from contextlib import closing
import hashlib
import os
from pathlib import Path
import tempfile

from agentflow_core import StoreError
from .records import WorkflowRecords
from .practical import _git
from .status import HEX64

MARKERS = (b'AGENTFLOW_V3_GUIDANCE_ONLY', b'agentflow.checkpoint.v1',
           b'agentflow.slim.receipt.v1', b'agentflow.slim.baseline.v1')


class Artifacts:
    def __init__(self, repo, home=None):
        self.repo = Path(repo).resolve(strict=True)
        self.home = home

    def inventory(self):
        rec = WorkflowRecords(self.repo, self.home, initialize=False)
        if not rec.store.db_file.exists(): return None
        doc = rec.latest('LOCAL_ARTIFACTS')
        return doc['content'] if doc else None

    def register(self, items):
        if not isinstance(items, list) or not items or len(items)>100:
            raise StoreError('items must contain 1..100 artifact declarations')
        incoming=[]
        for item in items:
            if not isinstance(item,dict) or item.get('kind') not in ('GUIDANCE','RUNTIME') or not isinstance(item.get('reason'),str) or not item['reason'].strip():
                raise StoreError('Each artifact needs kind GUIDANCE/RUNTIME and a specific reason')
            p=Path(item.get('path','')).expanduser()
            if not p.is_absolute() or p.is_symlink(): raise StoreError('Artifact path must be absolute and not a symlink')
            p=p.resolve()
            inside=p.is_relative_to(self.repo)
            if inside and (item['kind']!='GUIDANCE' or p.parent!=self.repo or p.name not in ('AGENTS.md','CLAUDE.md')):
                raise StoreError('Kit runtime artifacts must be outside the product tree')
            if inside:
                tracked=_git(self.repo,'ls-files','--stage','--',p.name)
                if tracked is None or tracked: raise StoreError('Tracked/mixed guidance cannot be declared local-only')
            digest=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() and 0<p.stat().st_size<=8*1024*1024 else None
            incoming.append({'path':str(p),'kind':item['kind'],'reason':item['reason'], 'sha256':digest})
        rec=WorkflowRecords(self.repo,self.home)
        old=rec.latest('LOCAL_ARTIFACTS');content=old['content'] if old else {'schema':'agentflow.artifacts.v1','items':[],'fingerprints':[]}
        bypath={x['path']:x for x in content['items']}
        bypath.update({x['path']:x for x in incoming})
        fingerprints=set(content.get('fingerprints',[])) | {x['sha256'] for x in incoming if x['sha256']}
        body={**content,'items':list(bypath.values()),'fingerprints':sorted(fingerprints)}
        if old and body==old['content']: return {'no_changes':True,'revision':old['revision']}
        return rec.put('LOCAL_ARTIFACTS',body,expected_revision=old['revision'] if old else 0,status='UNVERIFIED_REPORT')

    def guidance_plan(self, classifications=None):
        root=_git(self.repo,'rev-parse','--show-toplevel')
        if root is None or Path(os.fsdecode(root).strip()).resolve()!=self.repo:
            return {'status':'BLOCKED','reasons':['Target must be the explicit Git root; no inferred parent or git init']}
        reasons=[];classifications=classifications or {}
        for name in ('AGENTS.md','CLAUDE.md'):
            p=self.repo/name
            tracked=_git(self.repo,'ls-files','--stage','--',name)
            if tracked is None or tracked: reasons.append(name+': tracked or index unreadable')
            if p.is_symlink(): reasons.append(name+': symlink')
            elif p.exists():
                raw=p.read_text(encoding='utf-8')
                first=raw.find('# BEGIN AGENTFLOW_V3_GUIDANCE_ONLY');last=raw.find('# END AGENTFLOW_V3_GUIDANCE_ONLY')
                outside=(raw[:first]+raw[last+len('# END AGENTFLOW_V3_GUIDANCE_ONLY'):]).strip() if first>=0 and last>=first else raw.strip()
                claim=classifications.get(name,{})
                if outside and (claim.get('kind')!='KIT_ONLY' or not claim.get('reason')):
                    reasons.append(name+': content outside managed block requires explicit kit-only classification; preserve product rules')
        if (self.repo/'AGENTS.override.md').exists(): reasons.append('AGENTS.override.md requires active-instruction conflict review before setup')
        return {'status':'BLOCKED' if reasons else 'READY_TO_APPLY','reasons':reasons,
                'rules':['/AGENTS.md','/CLAUDE.md'],'classification_trust':'AGENT_REPORTED_NOT_AUTHENTICATED'}

    def classify_product(self, items):
        """Save explicit path/content-bound provenance reports, never Git rights.

        A scope list alone is not origin evidence. These reports resolve only
        ambiguous content matches; known kit paths, markers and DBs still block.
        """
        from .continuity import _paths
        if not isinstance(items, list) or not items or len(items) > 100:
            raise StoreError('items must contain 1..100 product provenance reports')
        rec = WorkflowRecords(self.repo, self.home, initialize=False)
        old = rec.latest('LOCAL_ARTIFACTS') if rec.store.db_file.exists() else None
        if old is None:
            raise StoreError('Complete artifact setup before classifying product files')
        inv = old['content']
        known = {x['path'] for x in inv['items']}
        reports = {}
        for item in items:
            if not isinstance(item, dict) or not _paths([item.get('path')]):
                raise StoreError('Product report requires a safe relative file path')
            name = item['path']
            target = self.repo / name
            if target.is_symlink() or not target.resolve().is_relative_to(self.repo):
                raise StoreError('Product report cannot use symlink/outside paths')
            if str(target) in known:
                raise StoreError('Known kit artifacts cannot be reclassified as product files')
            sha = item.get('sha256')
            if not isinstance(sha, str) or not HEX64.fullmatch(sha):
                raise StoreError('Product report requires the exact observed content SHA-256')
            for field in ('source', 'reason'):
                if not isinstance(item.get(field), str) or not item[field].strip() or len(item[field]) > 2000:
                    raise StoreError('Product report requires a concise provenance ' + field)
            reports[name] = {k: item[k] for k in ('path', 'sha256', 'source', 'reason')}
        merged = {**inv.get('product_reports', {}), **reports}
        body = {**inv, 'product_reports': merged}
        if body == inv:
            return {'no_changes': True, 'revision': old['revision'], 'trusted': False, 'write_authorized': False}
        saved = rec.put('LOCAL_ARTIFACTS', body, expected_revision=old['revision'], status='UNVERIFIED_REPORT')
        return {**saved, 'write_authorized': False,
                'note': 'Reported product origin, not authenticated approval; exact content binding only.'}

    def protect_guidance(self):
        location=_git(self.repo,'rev-parse','--git-path','info/exclude')
        if location is None: raise StoreError('Cannot locate Git local exclude')
        p=Path(os.fsdecode(location).strip());p=p if p.is_absolute() else self.repo/p
        if p.is_symlink() or any(x.is_symlink() for x in p.parents): raise StoreError('Refuse symlinked local exclude location')
        old=p.read_bytes() if p.exists() else b''
        new=old
        for name in ('AGENTS.md','CLAUDE.md'):
            tracked=_git(self.repo,'ls-files','--stage','--',name)
            if tracked is None or tracked: raise StoreError('Cannot exclude tracked guidance: '+name)
            rule=('/'+name).encode()
            if rule not in new.splitlines(): new+=(b'\n' if new and not new.endswith(b'\n') else b'')+rule+b'\n'
        if new!=old:
            p.parent.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(dir=p.parent,prefix='.agentflow-exclude-')
            try:
                with os.fdopen(fd,'wb') as out: out.write(new);out.flush();os.fsync(out.fileno())
                if (p.read_bytes() if p.exists() else b'')!=old: raise StoreError('Local exclude changed concurrently; reconcile before retry')
                os.replace(tmp,p)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
        for name in ('AGENTS.md','CLAUDE.md'):
            ignored=_git(self.repo,'check-ignore','--',name)
            if not ignored: raise StoreError('Local exclude did not protect '+name+'; inspect negation rules')
        return {'path':str(p.resolve()),'changed':new!=old,'index_mutated':False,'hook_installed':False}

    def check(self, product_paths=None, *, inventory=None):
        inv=inventory if inventory is not None else self.inventory()
        if inv is None:return {'status':'BLOCKED','scope':'UNAVAILABLE','reasons':['No artifact inventory; complete setup or register known artifacts'],'write_authorized':False}
        raw=_git(self.repo,'diff','--cached','--name-only','-z','--diff-filter=ACMRT','--no-renames')
        if raw is None:return {'status':'BLOCKED','scope':'UNREADABLE','reasons':['Cannot read INDEX changes'],'write_authorized':False}
        paths=[os.fsdecode(x) for x in raw.split(b'\0') if x]
        untracked_raw=_git(self.repo,'ls-files','--others','--exclude-standard','-z')
        if untracked_raw is None:return {'status':'BLOCKED','scope':'UNREADABLE','reasons':['Cannot inspect untracked files'],'write_authorized':False}
        untracked=[os.fsdecode(x) for x in untracked_raw.split(b'\0') if x]
        if len(untracked)>500:return {'status':'BLOCKED','scope':'TRUNCATED','reasons':['More than 500 untracked paths; classify/narrow before checking'],'write_authorized':False}
        if len(paths)>500:return {'status':'BLOCKED','scope':'TRUNCATED','reasons':['More than 500 staged paths; narrow staging before checking'],'write_authorized':False}
        known={str(Path(x['path']).relative_to(self.repo)) for x in inv['items'] if Path(x['path']).is_relative_to(self.repo)}
        if product_paths is not None and (not isinstance(product_paths,list) or any(not isinstance(x,str) for x in product_paths)):
            raise StoreError('product_paths must be an explicit list of product paths')
        # Empty content has no provenance: an empty product module must not be
        # classified as a kit log merely because both hash to the empty digest.
        fingerprints=set(inv.get('fingerprints',[]))-{hashlib.sha256(b'').hexdigest()};reasons=[];unknown=[]
        matches=[];unresolved=[]
        # Hash equality requires equal byte length. Inspect bounded candidate
        # blobs once; large unrelated logs/verification assets cannot match them.
        blobs={};candidate_sizes=set();candidate_bytes=0
        for location,names in [('INDEX',paths),('UNTRACKED_WORKTREE',untracked)]:
            for name in names:
                if location=='INDEX':blob=_git(self.repo,'show',':'+name)
                else:
                    p=self.repo/name
                    if p.is_symlink() or not p.resolve().is_relative_to(self.repo):
                        reasons.append(name+': untracked symlink/outside path needs review');continue
                    if not p.is_file() or p.stat().st_size>8*1024*1024:
                        reasons.append(name+': untracked content unavailable/too large to inspect');continue
                    with p.open('rb') as source:blob=source.read(8*1024*1024+1)
                    if len(blob)>8*1024*1024:
                        reasons.append(name+': content grew beyond inspection limit');continue
                if blob is None:
                    reasons.append(name+': staged blob unreadable/too large');continue
                candidate_bytes+=len(blob)
                if candidate_bytes>64*1024*1024:
                    return {'status':'BLOCKED','scope':'TRUNCATED','reasons':['Candidate inspection exceeded 64 MiB; narrow scope'],'read_only':True,'write_authorized':False}
                blobs[(location,name)]=blob;candidate_sizes.add(len(blob))
        scanned=0;hashed=0;total=0
        if paths or untracked:
            # Include current children of registered runtime roots, including files
            # generated after setup; bounded scans must never silently pass.
            seen=set()
            for item in inv['items']:
                root=Path(item['path'])
                candidates=root.rglob('*') if root.is_dir() else [root]
                for p in candidates:
                    if '.git' in p.parts or '__pycache__' in p.parts or p.is_symlink() or not p.is_file():continue
                    if str(p) in seen:continue
                    seen.add(str(p));size=p.stat().st_size;scanned+=1
                    if len(seen)>5000:
                        return {'status':'BLOCKED','scope':'TRUNCATED','reasons':['Artifact metadata scan exceeded 5000 files; narrow registered roots'],'read_only':True,'write_authorized':False}
                    if not size or size not in candidate_sizes:continue
                    total+=size
                    if total>64*1024*1024:
                        return {'status':'BLOCKED','scope':'TRUNCATED','reasons':['Artifact-root scan exceeded bounds; review inventory before commit'],'read_only':True,'write_authorized':False}
                    with p.open('rb') as source:raw=source.read(size+1)
                    if len(raw)!=size: return {'status':'BLOCKED','scope':'CHANGED_DURING_READ','reasons':['Registered artifact changed during observation; reconcile'],'read_only':True,'write_authorized':False}
                    fingerprints.add(hashlib.sha256(raw).hexdigest());hashed+=1
        # Inventory paths must remain untracked, even when unchanged in the index.
        for name in known:
            tracked=_git(self.repo,'ls-files','--stage','--',name)
            if tracked is None or tracked:reasons.append(name+': kit artifact is tracked/in INDEX')
        def inspect_content(name, blob, location):
            kit_db=(blob.startswith(b'SQLite format 3\x00') and b'workflow_documents' in blob
                    and b'contract_revisions' in blob and b'audit_events' in blob)
            if name in known or kit_db or any(marker in blob for marker in MARKERS):
                matches.append({'path':name,'location':location,'kind':'KIT_ONLY',
                                'basis':'KNOWN_KIT_PATH_MARKER_OR_STATE'})
                reasons.append(name+': kit artifact/content found in '+location)
                return
            sha=hashlib.sha256(blob).hexdigest()
            if sha not in fingerprints:
                return
            # Equal bytes do not establish origin. An independently observed
            # existing product baseline or explicit bound report can resolve
            # this ambiguity. Neither overrides the strong kit signals above.
            head=_git(self.repo,'show','HEAD:'+name)
            report=inv.get('product_reports',{}).get(name,{})
            if head is not None and head==blob:
                kind='PRODUCT';basis='EXISTING_PRODUCT_HEAD'
            elif (isinstance(report,dict) and report.get('sha256')==sha
                    and report.get('source') and report.get('reason')):
                kind='PRODUCT';basis='BOUND_PRODUCT_REPORT_UNVERIFIED'
            else:
                kind='UNRESOLVED';basis='CONTENT_MATCH_WITHOUT_ORIGIN_EVIDENCE'
                unresolved.append(name)
                reasons.append(name+': content matches kit; origin unresolved, classify the exact product content before proceeding')
            matches.append({'path':name,'location':location,'kind':kind,'basis':basis})
        for name in paths:
            blob=blobs.get(('INDEX',name))
            if blob is None:continue
            inspect_content(name,blob,'INDEX')
            if product_paths is not None and name not in product_paths:unknown.append(name)
        for name in untracked:
            blob=blobs.get(('UNTRACKED_WORKTREE',name))
            if blob is None:continue
            inspect_content(name,blob,'UNTRACKED_WORKTREE')
        if unknown:reasons.append('Paths outside classified product scope: '+', '.join(unknown))
        return {'status':'BLOCKED' if reasons else 'CLEAR','scope':'INDEX_BLOBS_UNTRACKED_AND_REGISTERED_ROOTS',
                'reasons':reasons,'checked_index_paths':paths,'checked_untracked_paths':untracked,'inventory_items':len(inv['items']),
                'content_matches':matches,'unresolved_paths':list(dict.fromkeys(unresolved)),
                'scan_stats':{'metadata_files':scanned,'hashed_files':hashed,'hashed_bytes':total,'candidate_bytes':candidate_bytes},
                'read_only':True,'write_authorized':False,'enforced_commit_gate':False,
                'limits':['Agent-reported inventory/product origin is not authenticated; transformed/unregistered copies need review','No hook or OS confinement']}


def setup(repo,home,mode,apply=False,upgrade=False,classifications=None,*,delegated=False):
    from .installer import GuidanceInstaller
    manager=Artifacts(repo,home)
    plan=manager.guidance_plan(classifications)
    if plan['status']=='BLOCKED':return plan
    installer=GuidanceInstaller(repo,home,mode=mode,delegated_advisory=delegated)
    installed=installer.installed_status()
    if not delegated and 'OPT_IN_PROTOCOL_INSTALLED' in installed['delegation_files'].values():
        return {'status':'BLOCKED','reasons':['Existing delegated protocol selected; preserve with --delegated-advisory or obtain explicit decision before switching to direct-only']}
    preview=installer.inspect(upgrade=upgrade)
    if not apply:return {'status':'PREVIEW','guidance':preview,'local_only':plan,'applied':False}
    result=installer.apply(explicit=True,upgrade=upgrade)
    try:
        exclude=manager.protect_guidance()
    except (OSError,StoreError) as exc:
        return {'status':'BLOCKED','guidance':result,'reasons':['Guidance applied, Git protection incomplete: '+str(exc)],
                'next_action':'Inspect transaction/backup and reconcile; do not report SETUP_READY or roll back blindly'}
    rec=WorkflowRecords(repo,home)
    artifact_dir=rec.store.state_dir/'artifacts';artifact_dir.mkdir(exist_ok=True)
    root=Path(__file__).resolve().parents[1]
    manager.register([{'path':str(repo_path),'kind':kind,'reason':reason} for repo_path,kind,reason in
        [(Path(repo).resolve()/'AGENTS.md','GUIDANCE','Managed kit instructions'),
         (Path(repo).resolve()/'CLAUDE.md','GUIDANCE','Managed kit instructions'),
         (rec.store.state_dir,'RUNTIME','External workflow SQLite and inventory'),
         (installer.backup_root,'RUNTIME','External guidance backups'),
         (root,'RUNTIME','External kit runtime and local smoke output')]])
    check=manager.check()
    return {'status':'SETUP_LOCAL_READY' if check['status']=='CLEAR' else 'BLOCKED',
            'guidance':result,'local_exclude':exclude,'artifact_check':check,
            'artifact_directory':str(artifact_dir),
            'provider_instruction_loading':'MUST_READ_BACK_IN_CURRENT_SESSION','write_authorized':False}

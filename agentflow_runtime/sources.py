"""Explicit multi-repository source observations; metadata never grants rights."""
from pathlib import Path, PurePosixPath
import re

from agentflow_core import StoreError
from agentflow_core.db import digest
from .practical import _git
from .status import _Files, _aggregate, HEX64

SCHEMA = 'agentflow.sources.v1'
MAX_PATHS = 128
MAX_BYTES = 64 * 1024 * 1024


def paths(value, field):
    if not isinstance(value, list) or len(value) > MAX_PATHS:
        raise StoreError(field + ': expected a list of at most 128 explicit relative files')
    for name in value:
        if (not isinstance(name, str) or not name or len(name) > 400 or '\\' in name or '\x00' in name
                or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts
                or '.git' in PurePosixPath(name).parts or PurePosixPath(name).as_posix() != name
                or any(c in name for c in '*?[]')):
            raise StoreError(field + ': unsafe/nonliteral file path; directories/globs are not file footprints')
    if len(set(value)) != len(value):
        raise StoreError(field + ': duplicate paths')
    return sorted(value)


def registry(contract, anchor):
    entries = contract.get('repositories')
    if not isinstance(entries, list) or not 1 <= len(entries) <= 8:
        raise StoreError('repositories: declare 1..8 entries with key, absolute Git root, write_paths and optional read_paths')
    result = []; keys = set(); roots = set(); count = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise StoreError('repositories: each entry must be an object')
        key = entry.get('key')
        if not isinstance(key, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', key) or key in keys:
            raise StoreError('repositories.key: expected a unique short identifier')
        raw = entry.get('root')
        if not isinstance(raw, str) or not Path(raw).is_absolute():
            raise StoreError('repositories.root: expected an absolute existing Git root')
        root = Path(raw).resolve(strict=True)
        actual = _git(root, 'rev-parse', '--show-toplevel')
        if actual is None or Path(actual.decode().strip()).resolve() != root:
            raise StoreError('repositories.root: must be the exact Git root, not a parent/subdirectory')
        if any(root.is_relative_to(other) or other.is_relative_to(root) for other in roots):
            raise StoreError('repositories.root: duplicate/nested roots require explicit separate review')
        write = paths(entry.get('write_paths'), key + '.write_paths')
        read = paths(entry.get('read_paths', []), key + '.read_paths')
        count += len(set(write + read))
        keys.add(key); roots.add(root)
        result.append({'key': key, 'root': str(root), 'write_paths': write, 'read_paths': read})
    if not 1 <= count <= MAX_PATHS:
        raise StoreError('repositories: footprint must contain 1..128 files in total; keep it task-scoped')
    return sorted(result, key=lambda r: r['key'])


def external_scope(contract, anchor):
    """Recognize legacy absolute out-of-root scope without inventing file lists."""
    scope = contract.get('scope', {})
    functional = scope.get('functional', []) if isinstance(scope, dict) else []
    root = Path(anchor).resolve()
    return any(isinstance(text, str) and text.startswith('/')
               and not Path(text.split(':', 1)[0]).is_relative_to(root) for text in functional)


def capture(contract, anchor):
    entries = registry(contract, anchor); result = []; total = 0
    for entry in entries:
        inspector = _Files(entry['root'], max_files=MAX_PATHS, max_total_bytes=MAX_BYTES-total)
        files = {}
        for name in sorted(set(entry['write_paths'] + entry['read_paths'])):
            observed = inspector._observe(name)
            inspector.cache[name] = observed
            if observed.get('reason') == 'FILE_MISSING':
                if name not in entry['write_paths']:
                    raise StoreError('sources '+entry['key']+':'+name+': declared read-only input is missing')
                files[name] = None  # explicit absence, also used for planned additions/deletions
            elif observed.get('sha256'):
                files[name] = observed['sha256']
            else:
                raise StoreError('sources ' + entry['key'] + ':' + name + ': ' + observed.get('reason', 'UNREADABLE')
                                 + '; use explicit files, no directories/symlinks, and respect read bounds')
        total += inspector.bytes_read
        result.append({'key': entry['key'], 'root': entry['root'], 'files': files})
    return {'schema': SCHEMA, 'scope_sha256': digest(entries), 'repositories': result}


def observe(contract, anchor, manifest):
    try:
        expected = registry(contract, anchor)
        if not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA:
            raise StoreError('Missing source manifest; do not use a primary-repo anchor for another repo')
        if manifest.get('scope_sha256') != digest(expected):
            return {'status': 'STALE', 'coverage': 'INCOMPLETE', 'files': [], 'reason': 'SOURCE_SCOPE_CHANGED'}
        rows = manifest.get('repositories')
        if not isinstance(rows, list) or len(rows) != len(expected):
            raise StoreError('Source manifest must include every declared repository')
        bykey = {r.get('key'): r for r in rows if isinstance(r, dict)}
        if len(bykey) != len(rows) or set(bykey) != {r['key'] for r in expected}:
            raise StoreError('Source manifest repository keys missing/duplicated/unknown')
        checks = []; repos = []; total = 0
        for entry in expected:
            row = bykey[entry['key']]; files = row.get('files')
            names = set(entry['write_paths'] + entry['read_paths'])
            if row.get('root') != entry['root'] or not isinstance(files, dict) or set(files) != names:
                raise StoreError('Source coverage incomplete or root rebound for ' + entry['key'])
            inspector = _Files(entry['root'], max_files=MAX_PATHS, max_total_bytes=MAX_BYTES-total)
            states = []
            for name, sha in files.items():
                if sha is None and name not in entry['write_paths']:
                    raise StoreError('Read-only input cannot use planned write-file absence: '+entry['key']+':'+name)
                if sha is not None and (not isinstance(sha, str) or not HEX64.fullmatch(sha)):
                    raise StoreError('Invalid tested hash for ' + entry['key'] + ':' + name)
                actual = inspector._observe(name); inspector.cache[name] = actual
                if sha is None:
                    state = 'CURRENT' if actual.get('reason') == 'FILE_MISSING' else 'STALE' if actual.get('sha256') else 'UNKNOWN'
                else:
                    state = ('CURRENT' if actual['sha256'] == sha else 'STALE') if actual.get('sha256') else actual.get('status', 'UNKNOWN')
                states.append(state)
                checks.append({'path': entry['key'] + ':' + name, 'status': state})
            total += inspector.bytes_read
            repos.append({'key': entry['key'], 'files': len(files), 'status': _aggregate(states) if states else 'CURRENT'})
        return {'status': _aggregate([r['status'] for r in repos]), 'coverage': 'DECLARED_SCOPE_COMPLETE',
                'files': checks, 'repositories': repos, 'truncated': False,
                'scope_note': 'Only explicit declared files; no whole-repository or test-execution attestation'}
    except (StoreError, OSError, ValueError, RuntimeError) as exc:
        return {'status': 'UNKNOWN', 'coverage': 'INCOMPLETE', 'files': [], 'reason': str(exc)}


def legacy_coverage(contract, anchor, hashes, changed_paths=()):
    if contract.get('repositories') or external_scope(contract, anchor):
        return {'status': 'INCOMPLETE', 'reason': 'Multi-repo scope has no complete per-repo tested-source manifest'}
    missing = sorted(set(changed_paths or []) - set(hashes or {}))
    return {'status': 'INCOMPLETE', 'missing_paths': missing} if missing else {
        'status': 'DECLARED_PATHS_ONLY', 'files': len(hashes or {}), 'scope_note': 'Not full-repository coverage'}


def changed_files(contract, anchor, data):
    """Normalize actual changed files without converting them into source hashes."""
    entries={r['key']:r for r in registry(contract,anchor)}
    supplied=data.get('changed_sources')
    legacy=paths(data.get('changed_paths',[]),'changed_paths')
    if supplied is not None:
        if not isinstance(supplied,dict):raise StoreError('changed_sources: expected repo key -> relative files')
        result={}
        for key,names in supplied.items():
            if key not in entries:raise StoreError('changed_sources: unknown repository '+str(key))
            result[key]=paths(names,'changed_sources.'+key)
            if not set(result[key])<=set(entries[key]['write_paths']):
                raise StoreError('changed_sources must stay in the declared per-repo write footprint')
        if legacy and set(legacy)!={name for names in result.values() for name in names}:
            raise StoreError('changed_paths conflicts with changed_sources; reconcile actual per-repo changes')
        return result
    result={}
    for name in legacy:
        owners=[key for key,r in entries.items() if name in r['write_paths']]
        if len(owners)!=1:
            raise StoreError('changed_paths: unknown/ambiguous file '+name+'; use changed_sources with explicit repo keys')
        result.setdefault(owners[0],[]).append(name)
    return result

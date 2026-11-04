"""Small versioned project outcomes; reported requirements are never authority."""
import json
from agentflow_core import ConflictError, StoreError

KEY = 'project-outcome'


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 800:
        raise StoreError('Brief text must be nonempty and at most 800 characters')
    return value.strip()


def validate(data):
    if not isinstance(data, dict): raise StoreError('Brief must be an object')
    if set(data) - {'outcome','requirements','must_preserve','examples','open_questions'}:
        raise StoreError('Unknown brief fields; approval belongs to the contract decision')
    result = {'outcome': _text(data.get('outcome'))}
    rows = data.get('requirements')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 12:
        raise StoreError('Brief needs 1..12 requirements with key, text and actual USER source')
    result['requirements'] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'key','text','source'}:
            raise StoreError('Each requirement needs key, text and source; observations/assumptions stay separate')
        item = {k: _text(row[k]) for k in row}
        if len(item['key']) > 40 or not all(c.isalnum() or c in '-_' for c in item['key']):
            raise StoreError('Requirement key must be a short identifier')
        result['requirements'].append(item)
    if len({r['key'] for r in result['requirements']}) != len(rows): raise StoreError('Duplicate requirement key')
    for field in ('must_preserve','open_questions'):
        values = data.get(field, [])
        if not isinstance(values, list) or len(values) > 12: raise StoreError('Brief lists must be short')
        result[field] = [_text(x) for x in values]
    examples = data.get('examples')
    if not isinstance(examples, list) or not 1 <= len(examples) <= 6:
        raise StoreError('Brief needs 1..6 concrete input/actions/expected examples')
    result['examples'] = []
    for row in examples:
        if not isinstance(row, dict) or set(row) != {'input','actions','expected'}:
            raise StoreError('An example needs input, actions and visible expected result')
        result['examples'].append({k:_text(v) for k,v in row.items()})
    if len(json.dumps(result, ensure_ascii=False)) > 6000: raise StoreError('Brief exceeds 6000 characters; keep working context small')
    return result


def current(records):
    return records.latest('CHANGE_REPORT', key=KEY)


def save(records, data, expected_revision=0):
    content = validate(data)
    if current(records):
        from .coordination import writer
        if writer(records).get('held'):
            raise ConflictError('Pause/handoff the active milestone before reviewing a project brief revision')
    saved = records.put('CHANGE_REPORT', content, key=KEY, expected_revision=expected_revision)
    row = current(records)
    if row['revision'] != saved['revision'] or row['content'] != content:
        raise ConflictError('Brief readback changed; reread before effects')
    return {'status':'BRIEF_SAVED','brief':row['content'],'brief_revision':row['revision'],
            'trusted':False,'write_authorized':False,'next_action':'Review reported USER requirements and examples; this brief does not approve any implementation'}


def bind(records, data):
    row = current(records)
    if 'brief' in data:
        value = validate(data['brief'])
        if row and row['content'] != value:
            raise ConflictError('Project brief changed; explicitly review/update it with work brief before beginning a milestone')
        if not row:
            save(records, value)
            row = current(records)
    if not row: return {}
    addresses = data.get('addresses')
    keys = {r['key'] for r in row['content']['requirements']}
    if (not isinstance(addresses, list) or not addresses or any(not isinstance(k,str) or k not in keys for k in addresses)
            or len(set(addresses)) != len(addresses)):
        raise StoreError('A milestone under a project brief must name addresses: requirement keys actually in this approved scope')
    return {'brief_revision':row['revision'],'brief_sha256':row['sha256'],
            'addresses':addresses,'deferred_requirements':sorted(keys-set(addresses))}


def check(records, content):
    if 'brief_revision' not in content: return
    row = current(records)
    if not row or row['revision'] != content['brief_revision'] or row['sha256'] != content['brief_sha256']:
        raise ConflictError('Project requirements changed since this milestone; review scope and reconcile before effects')


def view(records, content):
    row = current(records)
    if not row: return {}
    return {'brief':row['content'],'brief_revision':row['revision'],
            'addresses':content.get('addresses',[]),'deferred_requirements':content.get('deferred_requirements',[]),
            'semantic_coverage':'AGENT_REPORTED_NOT_PROVEN'}

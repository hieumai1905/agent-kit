"""Assess coverage of explicitly UNVERIFIED reports, without executing commands."""
from agentflow_core import StoreError


def assess(contract, report):
    if not isinstance(report, dict):
        raise StoreError('Verification report must be an object')
    checks = report.get('checks', [])
    if not isinstance(checks, list) or len(checks) > 80:
        raise StoreError('checks must be a list of at most 80 reports')
    acceptance = contract.get('acceptance', [])
    preserve = contract.get('preserve', [])
    valid_refs = {f'A{i+1}' for i in range(len(acceptance))} | {f'P{i+1}' for i in range(len(preserve))}
    covered = set(); failed = []; incomplete = []; details = []
    for n, check in enumerate(checks):
        if not isinstance(check, dict):
            raise StoreError('Each check must be an object')
        refs = check.get('covers', [])
        if not isinstance(refs, list) or any(not isinstance(x, str) or x not in valid_refs for x in refs):
            raise StoreError('covers must reference current acceptance A1.. or preservation P1..')
        status = check.get('status')
        if status not in ('PASS', 'FAIL', 'NOT_RUN', 'SKIPPED', 'INCONCLUSIVE'):
            raise StoreError('Check status must be PASS, FAIL, NOT_RUN, SKIPPED or INCONCLUSIVE')
        executed = check.get('executed') is True
        proof = (isinstance(check.get('command'), str) and bool(check['command'].strip())
                 and isinstance(check.get('output_excerpt'), str) and bool(check['output_excerpt'].strip())
                 and type(check.get('exit_code')) is int)
        if status == 'PASS' and (not executed or not proof or check['exit_code'] != 0):
            incomplete.append(f'check {n+1}: PASS lacks a successful execution report')
        elif status == 'PASS':
            covered.update(refs)
        elif status == 'FAIL' or (executed and proof and check['exit_code'] != 0):
            failed.append(f'check {n+1}')
        else:
            incomplete.append(f'check {n+1}: {status}')
        details.append({**check, 'trust': 'UNVERIFIED_REPORT'})
    missing = sorted(valid_refs - covered)
    if not acceptance:
        incomplete.append('No current acceptance criteria')
    if contract.get('work_type') == 'BUG':
        reproduction = [x for x in checks if x.get('kind') == 'REPRODUCTION']
        if not any(x.get('status') == 'PASS' and x.get('executed') is True
                   and type(x.get('exit_code')) is int and x['exit_code'] == 0
                   and x.get('command') and x.get('output_excerpt') for x in reproduction):
            incomplete.append('Original bug reproduction not exercised successfully')
    verdict = 'FAILED_REPORTED' if failed else 'PARTIAL_REPORTED' if missing or incomplete else 'VERIFIED_REPORTED'
    return {'reported_verdict': verdict, 'coverage': 'COMPLETE' if not missing and not incomplete else 'INCOMPLETE',
            'missing_criteria': missing, 'incomplete_checks': incomplete, 'failed_checks': failed,
            'checks': details, 'trusted': False, 'write_authorized': False,
            'note': 'Coverage of agent reports only; commands were not executed/authenticated by this helper.'}

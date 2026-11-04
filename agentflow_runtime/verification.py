"""Assess coverage of explicitly UNVERIFIED reports, without executing commands."""
from agentflow_core import StoreError
from .evidence_target import target, expected, successful


def assess(contract, report):
    if not isinstance(report, dict):
        raise StoreError('Verification report must be an object')
    checks = report.get('checks', [])
    evidence_target=target(contract)
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
        expected_code=expected(check,contract)
        proof = (isinstance(check.get('command'), str) and bool(check['command'].strip())
                 and isinstance(check.get('output_excerpt'), str) and bool(check['output_excerpt'].strip())
                 and type(check.get('exit_code')) is int)
        if status == 'PASS' and (not executed or not proof or check['exit_code'] != expected_code):
            incomplete.append(f'check {n+1}: PASS lacks a successful execution report')
        elif status == 'PASS':
            covered.update(refs)
        elif status == 'FAIL' or (executed and proof and check['exit_code'] != expected_code):
            failed.append(f'check {n+1}')
        else:
            incomplete.append(f'check {n+1}: {status}')
        details.append({**check, 'trust': 'UNVERIFIED_REPORT'})
    missing = sorted(valid_refs - covered)
    if not acceptance:
        incomplete.append('No current acceptance criteria')
    if contract.get('work_type') == 'BUG':
        reproduction = [x for x in checks if x.get('kind') == 'REPRODUCTION']
        if not any(successful(x,contract) for x in reproduction):
            incomplete.append('Original bug reproduction not exercised successfully')
    workflow_required=evidence_target in ('CLI','UI')
    context='ACTUAL_CLI' if evidence_target=='CLI' else 'ACTUAL_WORKFLOW'
    workflow=[x for x in details if x.get('kind')=='USER_WORKFLOW' or evidence_target=='CLI' and x.get('execution_context')=='ACTUAL_CLI']
    exercised=any(x.get('execution_context')==context and successful(x,contract) for x in workflow)
    workflow_failed=any(x.get('execution_context')==context and x.get('executed') is True
                        and (x.get('status')=='FAIL' or type(x.get('exit_code')) is int and x['exit_code']!=expected(x,contract)) for x in workflow)
    if workflow_required and not exercised:
        incomplete.append('User workflow not exercised successfully through the actual interaction path; unit/mock/simulation is separate evidence')
    verdict = 'FAILED_REPORTED' if failed else 'PARTIAL_REPORTED' if missing or incomplete else 'VERIFIED_REPORTED'
    return {'reported_verdict': verdict, 'coverage': 'COMPLETE' if not missing and not incomplete else 'INCOMPLETE',
            'missing_criteria': missing, 'incomplete_checks': incomplete, 'failed_checks': failed,
            'user_workflow':{'required':workflow_required,
                'target':evidence_target,
                'status':'FAILED_REPORTED' if workflow_failed else 'EXERCISED_REPORTED' if exercised else 'NOT_EXERCISED_REPORTED' if workflow_required else 'NOT_REQUIRED',
                'trust':'UNVERIFIED_REPORT'},
            'evidence_summary':{'code_checks':'FAILED' if failed else 'INCOMPLETE' if missing else 'CHECKED_REPORTED',
                'cli':'EXERCISED_REPORTED' if evidence_target=='CLI' and exercised else 'PENDING' if evidence_target=='CLI' else 'NOT_IN_SCOPE',
                'ui':'EXERCISED_REPORTED' if evidence_target=='UI' and exercised else 'PENDING' if evidence_target=='UI' else 'NOT_IN_SCOPE'},
            'checks': details, 'trusted': False, 'write_authorized': False,
            'note': 'Coverage of agent reports only; commands were not executed/authenticated by this helper.'}

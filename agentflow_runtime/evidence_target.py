"""Explicit evidence scope, fixed before approval. Legacy contracts keep their gate."""
from pathlib import PurePosixPath
from agentflow_core import StoreError


def target(contract):
    value=contract.get('verification_target')
    if value is None:return 'UI' if contract.get('usage_scenario') else 'CODE'
    if value not in ('CODE','CLI','UI'):raise StoreError('verification_target must be CODE, CLI or UI')
    if value=='CODE' and contract.get('usage_scenario'):
        raise StoreError('CODE cannot remove a declared user workflow; choose CLI/UI before approval')
    if value=='UI' and not contract.get('usage_scenario'):
        raise StoreError('UI needs a concrete usage_scenario')
    if value=='CLI':
        entry=contract.get('cli_entrypoint')
        if not isinstance(entry,str) or not entry or '\\' in entry or PurePosixPath(entry).is_absolute() or any(x in ('.','..') for x in entry.split('/')):
            raise StoreError('CLI needs a safe relative cli_entrypoint in the declared source footprint')
    return value


def expected(check, contract):
    code=check.get('expected_exit_code',0)
    if type(code) is not int or not 0<=code<=125 or code==124:
        raise StoreError('expected_exit_code must be 0..125 excluding timeout 124')
    if code!=0 and not (target(contract)=='CLI' and check.get('execution_context')=='ACTUAL_CLI'):
        raise StoreError('Nonzero expected exits are only for actual CLI checks')
    return code


def successful(check, contract):
    code=expected(check,contract)
    return (check.get('status')=='PASS' and check.get('executed') is True
            and type(check.get('exit_code')) is int and check['exit_code']==code
            and isinstance(check.get('command'),str) and bool(check['command'].strip())
            and isinstance(check.get('output_excerpt'),str) and bool(check['output_excerpt'].strip()))

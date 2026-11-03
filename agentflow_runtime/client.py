"""Optional checked Python invocation. Prefer direct CLI for simple calls.

An unhandled failure exits the caller with the helper's code. This is not a
broker: callers can deliberately catch/ignore errors and no OS rights are given.
"""
import json
import subprocess
import sys


class HelperCallError(SystemExit):
    def __init__(self, code, report):
        self.report = report
        super().__init__(code)


def run_checked(argv, *, data=None, timeout=30):
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) for a in argv):
        raise TypeError('argv must be a nonempty list; shell strings are not supported')
    def fail(code, report):
        code = code if isinstance(code, int) and code > 0 else 2
        report = {**report, 'status':'BLOCKED', 'helper_exit_code':code,
                  'write_authorized':False, 'next_action':'Stop; reread/reconcile state before retrying a mutation'}
        print(json.dumps(report, ensure_ascii=False), file=sys.stderr)
        raise HelperCallError(code, report)
    try:
        proc = subprocess.run(argv, input=json.dumps(data, ensure_ascii=False) if data is not None else None,
                              text=True, capture_output=True, timeout=timeout, shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(2, {'error':'HelperInvocationError', 'message':str(exc)[:1200]})
    if proc.returncode:
        try: error=json.loads(proc.stderr)
        except ValueError: error={'error':'HelperFailure','message':(proc.stderr or proc.stdout)[-1800:]}
        fail(proc.returncode, error if isinstance(error,dict) else {'error':'HelperFailure'})
    try: result=json.loads(proc.stdout)
    except ValueError: fail(2, {'error':'InvalidHelperOutput','message':'Expected a JSON object; helper returned non-JSON output'})
    if not isinstance(result,dict): fail(2, {'error':'InvalidHelperOutput','message':'Expected a JSON object'})
    if 'prepatch_check' in result and not isinstance(result['prepatch_check'],dict):
        fail(2, {'error':'InvalidHelperOutput','message':'prepatch_check must be an object'})
    if (result.get('status')=='BLOCKED' or result.get('error') or result.get('isError')
            or result.get('readback_matches') is False or result.get('prepatch_check',{}).get('status')=='BLOCKED'
            or result.get('trusted') is True or result.get('write_authorized') is True):
        fail(2, {'error':'BlockedOrContradictoryHelperOutput','message':'Inspect helper response; no following patch may run', 'response':result})
    return result

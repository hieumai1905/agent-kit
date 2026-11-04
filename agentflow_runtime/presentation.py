"""Small everyday CLI views. Full records remain in SQLite/read-only resume."""


def work_result(value):
    keys=('action','task_id','record_id','revision','contract_sha256','readback_matches',
          'saved','no_changes','status','artifact_directory','handoff_saved','handoff_revision',
          'auto_complete','source_snapshot_file','scope_sha256','repositories','files','receipt','checks','reasons',
          'existing_task_lookup_performed','reason_code','checks_reused','log_files','project_context','brief','brief_revision',
          'session_ref','title','stage','source_state','writer',
          'read_only','read_only_product_and_db','next_action','next_command','trusted','write_authorized')
    result={key:value[key] for key in keys if key in value}
    if 'binding' in value:result['binding']=value['binding']
    if value.get('input_derivations'):result['input_derivations']=value['input_derivations']
    if 'implementation_plan' in value:result['implementation_plan']=value['implementation_plan']
    if 'matches' in value:
        match=value['matches'];result['matches']={k:match[k] for k in ('status','selected_task_id','choices') if k in match}
    if 'checkpoint' in value:result['checkpoint_revision']=value['checkpoint']['revision']
    if 'decision_readback' in value:
        decision=value['decision_readback']
        result['decision_readback']={k:decision[k] for k in ('kind','decision','contract_sha256','contract_revision') if k in decision} if isinstance(decision,dict) else decision
        result['decision_source_reference']=str(decision.get('source',''))[:300] if isinstance(decision,dict) else None
    if 'prepatch_check' in value:
        check=value['prepatch_check']
        result['prepatch_check']={k:check[k] for k in ('status','reasons','current_chat_decision_must_be_revalidated','write_authorized') if k in check}
    if 'verification' in value:
        v=value['verification']
        result['verification']={k:v[k] for k in ('reported_verdict','coverage','missing_criteria','incomplete_checks','failed_checks','source_coverage','user_workflow','evidence_summary','trusted','write_authorized') if k in v}
    if 'artifact_check' in value:
        a=value['artifact_check'];result['artifact_check']={k:a[k] for k in ('status','reasons','unresolved_paths') if k in a}
    if 'routing' in value:
        r=value['routing'];result['routing']={k:r[k] for k in ('declared_level','effective_level','warnings','routing_triggers') if k in r}
    if isinstance(value.get('source_coverage'),dict):
        result['source_coverage']={k:value['source_coverage'][k] for k in ('status','coverage','repositories','reason') if k in value['source_coverage']}
    # No mutation rerun is needed to expand output: resume/handoff are read-only.
    normal='receipt' in value or value.get('status')=='HANDOFF_SAVED'
    if normal:
        from pathlib import Path
        if result.get('receipt'):result['receipt']=Path(result['receipt']).name
        for key in ('task_id','record_id','revision','contract_sha256','handoff_revision','session_ref'):
            result.pop(key,None)
        if not result.get('project_context'):result.pop('project_context',None)
        if isinstance(result.get('decision_readback'),dict):
            result['decision_readback']={k:v for k,v in result['decision_readback'].items() if k in ('kind','decision')}
    else:
        result['details']='Read full records only for a missing fact; never repeat a mutation for verbosity'
    return result


def error_hint(message):
    if any(x in message.casefold() for x in ('implementation_plan','implementation_policy','implementation plan','refinement','contract review')):
        return {'field':'implementation_plan','hint':'Checkpoint a bounded technical refinement under the unchanged approved contract; default EXACT or outside/protected files need contract review. Read USAGE.md only if the policy shape is missing.'}
    if 'milestone' in message:
        return {'field':'milestone','allowed':['CONTRACT_DECISION','SCOPE_CHANGE','IMPLEMENTATION_VERIFICATION','HANDOFF'],
                'hint':'Ordinary in-scope progress uses HANDOFF with phase IMPLEMENTING'}
    if 'risk_summary' in message:
        return {'field':'risk_summary','expected_type':'nonempty string','hint':'Use contract-template --level DEEP; keep verified risk facts, do not invent evidence'}
    if 'source_paths' in message or 'Source file' in message:
        return {'field':'source_paths','expected_type':'explicit relative files, no directories/globs',
                'hint':'For sibling repos declare repositories with key/root/write_paths; work sources captures the complete footprint'}
    if 'repositories' in message or 'source coverage' in message.lower():
        return {'field':'repositories','example':{'key':'frontend','root':'/ABS/GIT_ROOT','write_paths':['tests/view.test.mjs']},
                'hint':'Declare all affected repos/files in the contract; capture with work sources before tests'}
    if 'Contract not ready' in message:
        return {'hint':'contract-template --level STANDARD or DEEP lists field shapes; check-contract validates before storage'}
    return None

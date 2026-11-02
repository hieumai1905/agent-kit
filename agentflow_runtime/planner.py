"""Contract-linked draft plan and DAG validation. No task claiming or execution."""
from __future__ import annotations
from collections import defaultdict
from agentflow_core import StoreError
from .records import WorkflowRecords
from .rig import meaningful


def validate_work_graph(items: list[dict]):
    if not isinstance(items,list) or not items or len(items)>250:
        raise StoreError('Work graph needs 1..250 items')
    keys=[]
    for item in items:
        if not isinstance(item,dict): raise StoreError('Invalid work item')
        key=item.get('key'); title=item.get('title'); proof=item.get('verification')
        if not isinstance(key,str) or not key or len(key)>80:
            raise StoreError('Work item key missing/invalid')
        if not isinstance(title,str) or not title.strip(): raise StoreError('Work item title missing')
        if (not isinstance(proof,list) or not proof
                or any(not meaningful(item,min_length=1) for item in proof)):
            raise StoreError('Each work item requires verification intent')
        keys.append(key)
    if len(set(keys))!=len(keys):raise StoreError('Duplicate work item keys')
    known=set(keys)
    dependents=defaultdict(list); indegree={key:0 for key in keys}
    for item in items:
        deps=item.get('depends_on',[])
        if (not isinstance(deps,list) or any(not isinstance(dep,str) or not dep for dep in deps)
                or len(deps)!=len(set(deps))):
            raise StoreError('Invalid dependencies')
        for dep in deps:
            if dep not in known or dep==item['key']:
                raise StoreError('Missing or self dependency')
            dependents[dep].append(item['key']);indegree[item['key']]+=1
    layers=[]; remaining=len(keys)
    while remaining:
        layer=[key for key in keys if indegree[key]==0]
        if not layer: raise StoreError('Work dependency cycle detected')
        layers.append(layer);remaining-=len(layer)
        for key in layer:
            indegree[key]=-1
            for next_key in dependents[key]:indegree[next_key]-=1
    return {'valid':True,'layers':layers,'work_item_count':len(keys),
            'independent_first_layer':layers[0],
            'safe_to_parallelize':False,
            'note':'Dependency independence does not prove file/resource write isolation.'}


class DraftPlanner:
    def __init__(self,repo,state_home=None):self.records=WorkflowRecords(repo,state_home)

    def plan(self,task_id: str,content: dict,*, expected_revision=0,save=False)->dict:
        if not isinstance(content,dict):
            raise StoreError('Plan must be a JSON object')
        task=self.records.core.get_task(task_id)
        contract=self.records.core.contract_revision(task_id)
        if not meaningful(content.get('selected_approach'),min_length=1):
            raise StoreError('Plan must name a non-placeholder selected_approach')
        if (not isinstance(content.get('verification_strategy'),list) or not content['verification_strategy']
                or any(not meaningful(item,min_length=1) for item in content['verification_strategy'])):
            raise StoreError('Plan requires verification_strategy')
        if content.get('contract_sha256') not in (None,contract['sha256']):
            raise StoreError('Plan contract hash mismatch')
        plan={**content,'task_id':task_id,'contract_revision':contract['revision'],
              'contract_sha256':contract['sha256'],
              'execution_permission':'NONE','status':'DRAFT_NOT_AUTHORIZED'}
        record=self.records.put('TECHNICAL_PLAN',plan,task_id=task_id,
                                expected_revision=expected_revision) if save else None
        return {'plan':plan,'record':record,'can_execute':False}

    def work_graph(self,task_id: str,items: list[dict], *,expected_revision=0,save=False):
        task=self.records.core.get_task(task_id)
        contract=self.records.core.contract_revision(task_id)
        validation=validate_work_graph(items)
        doc={'task_id':task_id,'items':items,'validation':validation,
             'contract_sha256':contract['sha256'],'contract_revision':contract['revision'],
             'status':'DRAFT_NOT_AUTHORIZED','no_execution_grant':True}
        record=self.records.put('WORK_GRAPH',doc,task_id=task_id,
                                expected_revision=expected_revision) if save else None
        return {'work_graph':doc,'record':record,'execution_ready':False}

    def ready_candidates(self,items:list[dict],completed:set[str]|None=None):
        validate_work_graph(items)
        done=completed or set()
        return {'logical_ready':[i['key'] for i in items if i['key'] not in done and
                                 all(dep in done for dep in i.get('depends_on',[]))],
                'write_authorized':False,
                'execution_state':'BLOCKED_G2_UNCERTIFIED'}

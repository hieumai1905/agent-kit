"""Stack-aware, minimal engineering/domain profile proposals; never auto-activate."""
from __future__ import annotations
from .discovery import RepoDiscovery
from .records import WorkflowRecords

DOMAIN_TRIGGERS={
 'ui_frontend':('ui','ux','react','next','tsx','design','css','component','giao diện','responsive','mobile'),
 'backend_api':('api','http','server','endpoint','backend','fastapi','graphql','grpc'),
 'database_data':('database','postgres','sql','db','migration','schema','data','dữ liệu'),
 'security_privacy':('auth','login','permission','token','security','secret','đăng nhập','quyền'),
 'performance_reliability':('cache','performance','latency','timeout','retry','tối ưu','hiệu năng'),
 'integration_observability':('webhook','integration','monitoring','logging','tracing','telemetry'),
 'desktop_mobile':('swift','tauri','electron','flutter','ios','android'),
 'ai_llm':('llm','agent','prompt','model','openai','anthropic'),
}

class EngineeringProfiler:
    def __init__(self,repo,state_home=None):
        self.discoverer=RepoDiscovery(repo)
        self.records=WorkflowRecords(repo,state_home)

    def propose(self)->dict:
        snapshot=self.discoverer.scan()
        configs=set(snapshot['configuration_files'])
        names=snapshot['package_summary'].get('dependency_names',[])
        probable=[]
        for name in names:
            if name in ('next','react','vue','svelte','express','fastify','prisma','vitest','playwright'):
                probable.append(name)
        tooling={'formatter':'OBSERVE_EXISTING', 'linter':'OBSERVE_EXISTING',
                 'typechecker':'OBSERVE_EXISTING','tests':'OBSERVE_EXISTING'}
        if 'tsconfig.json' in configs:tooling['typechecker']='TypeScript config present; strict mode NOT assumed'
        if 'pyproject.toml' in configs:tooling['python']='pyproject.toml present; tools NOT assumed'
        domains=['security_privacy']
        if any(x in probable for x in ('next','react','vue','svelte')) or any(
                x.startswith('TypeScript/React') for x in snapshot['languages_observed']):
            domains.append('ui_frontend')
        if any(x in probable for x in ('express','fastify')):domains.append('backend_api')
        if 'prisma' in probable:domains.append('database_data')
        profile={'status':'PROPOSED_NOT_APPROVED',
                 'languages_observed':snapshot['languages_observed'],
                 'framework_evidence':probable,'tooling':tooling,
                 'architecture':'PRESERVE_AND_ASSESS_EXISTING',
                 'quality_philosophy':'Correct + Safe; Simple, Concise, Maintainable; patterns only when justified',
                 'new_dependency_policy':'PROPOSE_WITH_RATIONALE',
                 'legacy_policy':'IMPROVE_ONLY_WITHIN_APPROVED_SCOPE',
                 'detected_domains':sorted(set(domains)),
                 'missing_evidence':['Architecture boundaries need review',
                                     'Formatter/linter/typecheck conventions need review',
                                     'Domain-specific applicability needs review'],
                 'source':'AUTOMATED_DISCOVERY_UNTRUSTED'}
        return profile

    def applicable_domains(self,request: str, files: list[str]|None=None):
        joined=(request+' '+' '.join(files or [])).casefold()
        matches=[]
        for domain,triggers in DOMAIN_TRIGGERS.items():
            if domain=='security_privacy' or any(token in joined for token in triggers):
                matches.append(domain)
        return {'domains':matches,'level':'CANDIDATE_NOT_AUTHORIZED',
                'policy_activated':False,
                'reason':'Task/domain matching is a recommendation; project profile approval is required'}

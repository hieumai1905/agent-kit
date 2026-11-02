"""User-controlled, non-routing model recommendations with explicit unknowns."""
from __future__ import annotations

class ModelAdvisor:
    LEVELS={'QUICK':'FAST','STANDARD':'BALANCED','DEEP':'DEEP'}

    def recommend(self,task_level: str, catalog: list[dict] | None=None,
                  current_provider: str|None=None, usage:dict|None=None):
        if task_level not in self.LEVELS: raise ValueError('Use QUICK/STANDARD/DEEP')
        capability=self.LEVELS[task_level]
        candidates=[]
        for model in catalog or []:
            if not isinstance(model,dict):continue
            if model.get('allowed') is not True or model.get('available') is not True: continue
            if model.get('tier') not in {'FAST','BALANCED','DEEP'}:continue
            if current_provider and model.get('provider')!=current_provider:continue
            candidates.append(model)
        tier_pref={"FAST":['FAST','BALANCED','DEEP'],
                   "BALANCED":['BALANCED','DEEP','FAST'],
                   "DEEP":['DEEP','BALANCED','FAST']}[capability]
        candidates.sort(key=lambda m:(tier_pref.index(m['tier']),m.get('name','')))
        trusted_usage=(usage if (isinstance(usage,dict) and usage.get('status')=='KNOWN'
                           and usage.get('source') and usage.get('observed_at')) else None)
        # Critical work must not be recommended onto weaker tiers just to save usage.
        if task_level=='DEEP':
            candidates=[m for m in candidates if m['tier']=='DEEP']
        selected=candidates[0] if candidates else None
        return {'recommended_tier':capability,
                'suggested_model':selected.get('name') if selected else None,
                'model_provider':selected.get('provider') if selected else current_provider,
                'catalog_status':'USER_SUPPLIED_FILTERED' if catalog else 'UNKNOWN',
                'usage_status':'KNOWN' if trusted_usage else 'UNKNOWN',
                'usage_source':trusted_usage['source'] if trusted_usage else None,
                'automatic_switch':False,'automatic_subagents':False,
                'human_escalation_recommended':bool(task_level=='DEEP' and not selected),
                'warning':('No verified model availability/catalog. No model switch performed.'
                           if not selected else 'Model suitability is advisory, not proof of quality or permission.')}

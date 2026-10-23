"""Cached saved-artifact inference. No Flask imports, DB writes or retraining."""
from functools import lru_cache
from .preprocessing import read_json
from .explainability import explain

@lru_cache(maxsize=1)
def load_artifacts():
    return {name:read_json('models/netease/'+filename) for name,filename in {
        'model':'hybrid.json','features':'features.json','profiles':'display_profiles.json','tasks':'task_index.json'}.items()}

def recommend_agents(task, top_k=5):
    if not isinstance(task,dict) or type(top_k) is not int or not 1<=top_k<=100:
        raise ValueError('Supply a task dictionary and top_k between 1 and 100.')
    data=load_artifacts(); mode=task.get('mode','benchmark')
    if mode not in ('benchmark','application_demo'):
        raise ValueError('Unknown inference mode.')
    operations=task.get('operations',{})
    if mode=='benchmark':
        if operations or 'candidate_worker_ids' in task or 'capability_ids' in task:
            raise ValueError('Benchmark mode uses fixed source capability/candidate membership and neutral context.')
        entry=data['tasks'].get(str(task.get('source_task_id','')))
        if not entry or entry['split']!='test':
            raise ValueError('Benchmark inference requires a held-out NetEase source_task_id.')
        capabilities=[entry['capability']]; candidates=entry['candidate_worker_ids']
    else:
        capabilities=task.get('capability_ids',[]); candidates=task.get('candidate_worker_ids',[])
        if not isinstance(capabilities,list) or not capabilities or not isinstance(candidates,list) or not candidates:
            raise ValueError('Application demo requires explicit capability_ids and mapped candidate_worker_ids.')
        capabilities=list(dict.fromkeys(capabilities)); candidates=list(dict.fromkeys(candidates))
        if any(c not in data['model']['capabilities'] for c in capabilities):
            raise ValueError('Unknown capability; do not silently map onboarding task names.')
        if any(w not in data['features'] for w in candidates):
            raise ValueError('Candidate has no explicit NetEase source identity mapping.')
    results=[]
    for worker in candidates:
        profile=dict(data['profiles'][worker])
        values=[data['features'][worker][cap] for cap in capabilities]
        components=[sum(v['new'][i] for v in values)/len(values) for i in range(3)]
        base=sum(v*w for v,w in zip(components,data['model']['weights']))
        score=base; reasons=[]
        for cap,feature in zip(capabilities,values):
            reasons.extend(explain(cap,feature,profile))
        operational=operations.get(worker) if mode=='application_demo' else None
        if operational is not None:
            available=operational.get('availability'); workload=operational.get('workload'); capacity=operational.get('capacity')
            if type(available) is not bool or type(workload) is not int or type(capacity) is not int or not 0<=workload<=capacity or capacity<=0:
                raise ValueError('Invalid availability/workload/capacity context.')
            if not available or workload>=capacity:
                continue
            score=.9*base+.1*(1-workload/capacity)
            profile.update(availability=available,workload=workload,capacity=capacity)
            profile['provenance']={**profile['provenance'],**{k:'supplied application state; excluded from benchmark' for k in ('availability','workload','capacity')}}
            reasons.append('Application context: 10% free-capacity adjustment; excluded from NetEase evaluation.')
        results.append({**profile,'score':score,'base_score':base,
            'components':dict(zip(('content','collaborative','knowledge_graph'),components)),
            'explanation':list(dict.fromkeys(reasons)),
            'graph_paths':[v['graph']['path'] for v in values if v['graph']['path']],
            'mode':mode,'score_type':'ranking score, not success probability',
            'context_used':operational is not None})
    results.sort(key=lambda r:(-r['score'],r['source_worker_id']))
    return [{**row,'rank':i+1} for i,row in enumerate(results[:top_k])]

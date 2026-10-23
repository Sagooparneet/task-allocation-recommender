"""Optional, pure adapter for a LATER manual integration stage.

No routes, model classes, SQL queries or database writes. Caller supplies objects
already loaded and authorized by its existing Flask service.
"""
from .recommender import recommend_agents

def recommend_for_flask(task, agents, worker_bindings, capability_mapping, top_k=5):
    """worker_bindings: {str(flask_agent_id): real source_worker_id}.

    capability_mapping: {task_type: [source capability IDs]} is an explicitly
    configured DEMONSTRATION mapping, not a learned onboarding equivalence.
    """
    capabilities=capability_mapping.get(task.task_type)
    if not capabilities:
        raise ValueError('No explicit proxy-capability mapping for this task type.')
    required={link.skill.name for link in getattr(task,'task_skills',[])}
    by_source={}
    for agent in agents:
        source=worker_bindings.get(str(agent.id))
        if not source or not agent.availability:
            continue
        known_skills={link.skill.name for link in getattr(agent,'agent_skills',[])}
        if not required.issubset(known_skills):
            continue
        if source in by_source:
            raise ValueError('Two Flask agents cannot share one source worker binding.')
        by_source[source]=agent
    if not by_source:
        return []
    ranked=recommend_agents({'mode':'application_demo','capability_ids':capabilities,
        'candidate_worker_ids':list(by_source)},top_k=top_k)
    result=[]
    for row in ranked:
        agent=by_source[row['source_worker_id']]
        result.append({**row,'agent_display_id':row['agent_id'], 'agent_id':agent.id,
            'task_id':task.id,'task_type':task.task_type,
            'match_percentage':round(row['score']*100,1),
            'cbf_score':row['components']['content'],'cf_score':row['components']['collaborative'],
            'kg_score':row['components']['knowledge_graph'],
            'workload':agent.workload,'availability':agent.availability,
            'performance_score':None if row['historical_success_rate'] is None else row['historical_success_rate']*100,
            'explanations':row['explanation'],'explanation':' '.join(row['explanation']),
            'application_note':'Explicit demo identity/capability mapping; NetEase accuracy is not an onboarding accuracy claim.'})
    return result

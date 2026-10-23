import time
from collections import Counter
from .preprocessing import ROOT, load_data, read_json, save_json
from .content_based import build_profiles, score as content_score
from .knowledge_graph import build_graph, graph_features, save_graph
from .display_profiles import make_profiles
from .evaluation import feature_groups, evaluate
from ..salesmesh_ml.engine import HybridRecommender

def prepare_artifacts():
    groups,splits=load_data()
    model=HybridRecommender.load(ROOT/'models/netease/legacy_model.json')
    training=[row for tid in splits['train'] for row in groups[tid]]
    # Verify the preserved model contains precisely the real training interactions.
    history={}
    for row in training:
        pair=history.setdefault(row['agent_id'],{}).setdefault('NetEase capability '+row['capability'],[0,0])
        pair[0]+=row['success']; pair[1]+=1
    assert history==model.history
    content=build_profiles(training)
    graph=build_graph(training)
    ids=sorted(a['id'] for a in model.agents)
    capabilities=sorted({r['capability'] for rows in groups.values() for r in rows})
    graph_values=graph_features(graph,ids,capabilities)
    save_graph(graph,ROOT/'models/netease/knowledge_graph.json')
    profiles={a['id']:a for a in model.agents}
    features={}
    for worker in ids:
        features[worker]={}
        for cap in capabilities:
            category='NetEase capability '+cap
            legacy=model.components(profiles[worker],{'id':'feature-query','category':category,'skill':category,'location':'NOT_RECORDED'})
            features[worker][cap]={'legacy':legacy,
                'new':[content_score(content.get(worker,{}),[cap]),legacy[1],graph_values[worker][cap]['score']],
                'quality':profiles[worker]['quality'],'graph':graph_values[worker][cap]}
    save_json('models/netease/features.json',features)
    save_json('models/netease/capability_profiles.json',content)
    save_json('models/netease/display_profiles.json',make_profiles(model,content))
    # Membership and capability only: no answer/truth/success in inference index.
    index={tid:{'capability':rows[0]['capability'],'candidate_worker_ids':[r['agent_id'] for r in rows],
                'split':rows[0]['split']} for tid,rows in groups.items()}
    save_json('models/netease/task_index.json',index)
    stats={'nodes':graph.number_of_nodes(),'edges':graph.number_of_edges(),
        'node_types':dict(Counter(a['kind'] for _,a in graph.nodes(data=True))),
        'edge_types':dict(Counter(a['relation'] for _,_,a in graph.edges(data=True))),
        'training_observations':len(training),'graph_input':'training split only'}
    save_json('reports/graph_statistics.json',stats)
    return stats

def tune():
    groups,splits=load_data(); features=read_json('models/netease/features.json')
    validation=feature_groups(groups,splits['validation'],features)
    # Architecture constraint, fixed before testing: each of CBF, CF and KG contributes >=10%.
    grid=[(x/10,y/10,(10-x-y)/10) for x in range(1,9) for y in range(1,10-x)]
    trials=[{'weights':list(w),'metrics':evaluate(validation,w,3)} for w in grid]
    best=max(trials,key=lambda t:t['metrics']['map_at_k'])
    save_json('reports/validation_search.json',trials)
    artifact={'schema_version':2,'weights':best['weights'],'selected_on':'validation MAP@3',
        'constraint':'each component weight >= 0.1, fixed before test evaluation',
        'operations_in_benchmark':False,'capabilities':sorted(next(iter(features.values()))),
        'dataset':'NetEaseCrowd existing proxy subset','graph':'training-only NetworkX path features'}
    save_json('models/netease/hybrid.json',artifact)
    return best

def final_evaluation():
    started=time.perf_counter()
    groups,splits=load_data(); features=read_json('models/netease/features.json')
    artifact=read_json('models/netease/hybrid.json')
    test=feature_groups(groups,splits['test'],features)
    legacy=feature_groups(groups,splits['test'],features,'legacy')
    weights=read_json('models/netease/legacy_model.json')['weights']
    legacy_result=evaluate(legacy,weights,3)
    # Reproduction is computed, never assigned from the reference report.
    import math
    reference=read_json('models/netease/legacy_evaluation.json')['metrics']['hybrid']
    for key in ('top1_success','precision_at_k','recall_at_k','map'):
        assert math.isclose(legacy_result[key],reference[key],abs_tol=1e-12)
    configs={'legacy_hybrid':(legacy,weights),'content_only':(test,(1,0,0)),
        'collaborative_only':(test,(0,1,0)),'kg_only':(test,(0,0,1)),
        'quality_only':(legacy,(0,0,1)),'new_kg_hybrid':(test,artifact['weights'])}
    results={name:{str(k):evaluate(g,w,k) for k in (1,3,5)} for name,(g,w) in configs.items()}
    # Report how much graph removal changes rankings; no tuning is done with this result.
    w=artifact['weights']; ablated=(w[0]/(w[0]+w[1]),w[1]/(w[0]+w[1]),0)
    def top(group,weights):
        return min(group,key=lambda r:(-sum(a*b for a,b in zip(r[1],weights)),r[0]))[0]
    changed=sum(top(g,w)!=top(g,ablated) for g in test)
    report={'sample_counts':{s:{'tasks':len(ids),'observations':sum(len(groups[t]) for t in ids)} for s,ids in splits.items()},
        'workers':len(features),'weights':artifact['weights'],'results':results,
        'graph_ablation':{'top1_rankings_changed':changed,'test_tasks':len(test),
            'no_graph_metrics':evaluate(test,ablated,3)},
        'evaluation_seconds':time.perf_counter()-started,
        'scope':'Held-out observed-participant replay on NetEaseCrowd used as a proxy for task allocation.',
        'test_reuse':'This benchmark was previously inspected; changed-model comparisons are retrospective, not a new blind generalization claim.',
        'metric_definitions':{'map':'full-ranking macro average precision',
            'map_at_k':'macro truncated AP: sum of Precision@i for relevant i<=K divided by min(K,total relevant)',
            'ndcg_at_k':'binary gains with log2 rank discounts; zero-positive tasks contribute zero',
            'top1_success':'fraction of tasks with a correct first-ranked observed worker',
            'precision_at_k':'correct top-K divided by K; missing slots count zero'},
        'limitations':['Synthetic names/locations/workload are not evaluation features.',
            'Operational onboarding capability mappings are illustrative and require domain validation.',
            'Repeated workers/tasks can make independent-task confidence intervals optimistic.']}
    save_json('reports/final_evaluation.json',report)
    return report

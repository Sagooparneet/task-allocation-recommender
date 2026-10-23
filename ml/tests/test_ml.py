import math
from types import SimpleNamespace as Obj
from ml.src.preprocessing import load_data, read_json, ROOT
from ml.src.evaluation import evaluate, feature_groups
from ml.src.knowledge_graph import build_graph, graph_features, load_graph
from ml.src.recommender import recommend_agents, load_artifacts
from ml.src.flask_adapter import recommend_for_flask

def test_metric_definitions():
    group=[[('a',[3],0),('b',[2],1),('c',[1],1)]]
    result=evaluate(group,[1],3)
    assert result['precision_at_k']==2/3
    assert result['recall_at_k']==1
    assert math.isclose(result['map_at_k'],(.5+2/3)/2)
    assert math.isclose(result['ndcg_at_k'],(1/math.log2(3)+1/math.log2(4))/(1+1/math.log2(3)))
    assert evaluate([[('x',[1],0)]],[1],3)['map_at_k']==0

def test_graph_relationships_actually_change_score():
    rows=[dict(agent_id='1',task_id='t1',capability='50',success=1,timestamp=1),
          dict(agent_id='2',task_id='t1',capability='50',success=1,timestamp=1),
          dict(agent_id='2',task_id='t2',capability='50',success=0,timestamp=2)]
    graph=build_graph(rows)
    before=graph_features(graph,['1','2'],['50'])['1']['50']
    assert before['shared_task_neighbors']==1
    graph.remove_edge('worker:2','task:t1')
    after=graph_features(graph,['1','2'],['50'])['1']['50']
    # The direct capability statistic is unchanged but the graph path no longer exists.
    assert after['shared_task_neighbors']==0
    # Change the peer's category evidence to demonstrate its contribution explicitly.
    graph=build_graph(rows)
    graph['worker:2']['capability:50']['successes']=2
    changed=graph_features(graph,['1','2'],['50'])['1']['50']
    assert changed['score']!=before['score']

def test_graph_excludes_nontraining_tasks():
    graph=load_graph(ROOT/'models/netease/knowledge_graph.json')
    groups,splits=load_data()
    assert all('task:'+tid not in graph for s in ('validation','test','purged') for tid in splits[s])
    assert sum(e['relation']=='COMPLETED' for _,_,e in graph.edges(data=True))==sum(len(groups[t]) for t in splits['train'])

def test_legacy_reproduction_and_new_runtime_parity():
    groups,splits=load_data(); data=load_artifacts()
    old=feature_groups(groups,splits['test'],data['features'],'legacy')
    oldweights=read_json('models/netease/legacy_model.json')['weights']
    computed=evaluate(old,oldweights,3)
    expected=read_json('models/netease/legacy_evaluation.json')['metrics']['hybrid']
    assert math.isclose(computed['top1_success'],expected['top1_success'],abs_tol=1e-12)
    for tid in splits['test'][:30]:
        ranked=recommend_agents({'source_task_id':tid},top_k=5)
        offline=feature_groups(groups,[tid],data['features'])[0]
        weights=data['model']['weights']
        offline.sort(key=lambda r:(-sum(a*b for a,b in zip(r[1],weights)),r[0]))
        assert [r['source_worker_id'] for r in ranked]==[r[0] for r in offline[:5]]
        assert all(math.isclose(r['score'],sum(a*b for a,b in zip(o[1],weights))) for r,o in zip(ranked,offline))

def test_display_fields_do_not_affect_benchmark_and_context_is_rejected():
    import pytest
    data=load_artifacts(); tid=next(t for t,e in data['tasks'].items() if e['split']=='test')
    before=recommend_agents({'source_task_id':tid})
    worker=before[0]['source_worker_id']; profile=data['profiles'][worker]
    original=dict(profile)
    try:
        profile.update(agent_name='Different synthetic name',location='Different demo place',workload=999,availability=False)
        after=recommend_agents({'source_task_id':tid})
        assert [(r['source_worker_id'],r['score']) for r in before]==[(r['source_worker_id'],r['score']) for r in after]
        with pytest.raises(ValueError): recommend_agents({'source_task_id':tid,'operations':{worker:{}}})
    finally:
        profile.clear(); profile.update(original)
    assert len({p['agent_id'] for p in data['profiles'].values()})==1653
    assert len({p['agent_name'] for p in data['profiles'].values()})==1653

def test_application_adapter_requires_explicit_mapping_and_uses_db_id():
    import pytest
    data=load_artifacts(); worker=next(iter(data['features']))
    task=Obj(id=77,task_type='Demo task',task_skills=[])
    agent=Obj(id=921,name='Existing database display',availability=True,workload=2,agent_skills=[])
    with pytest.raises(ValueError): recommend_for_flask(task,[agent],{'921':worker},{})
    assert recommend_for_flask(task,[agent],{}, {'Demo task':['50']})==[]
    rows=recommend_for_flask(task,[agent],{'921':worker},{'Demo task':['50']})
    assert rows[0]['agent_id']==921 and rows[0]['source_worker_id']==worker
    assert rows[0]['mode']=='application_demo'
    agent.availability=False
    assert recommend_for_flask(task,[agent],{'921':worker},{'Demo task':['50']})==[]

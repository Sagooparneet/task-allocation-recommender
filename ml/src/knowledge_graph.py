"""A genuine training-only NetworkX graph whose paths generate ranking features."""
import math
from collections import Counter, defaultdict
import networkx as nx

def build_graph(training_rows):
    graph = nx.DiGraph()
    for row in training_rows:
        worker, task, capability = 'worker:'+row['agent_id'], 'task:'+row['task_id'], 'capability:'+row['capability']
        graph.add_node(worker, kind='Worker', source_id=row['agent_id'])
        graph.add_node(task, kind='Task', source_id=row['task_id'])
        graph.add_node(capability, kind='Capability', source_id=row['capability'])
        graph.add_edge(worker, task, relation='COMPLETED', success=row['success'], timestamp=row['timestamp'])
        graph.add_edge(task, capability, relation='REQUIRES_CAPABILITY')
        if not graph.has_edge(worker, capability):
            graph.add_edge(worker, capability, relation='HAS_CAPABILITY', count=0, successes=0)
        edge = graph[worker][capability]
        edge['count'] += 1
        edge['successes'] += row['success']
    return graph

def graph_features(graph, worker_ids, capabilities):
    # Neighbor weights come from actual Worker -> Task <- Worker paths.
    counts, degrees, shared = {}, {}, defaultdict(Counter)
    for node, attrs in graph.nodes(data=True):
        if attrs['kind'] == 'Worker':
            counts[node] = {graph.nodes[v]['source_id']:[e['successes'], e['count']]
                            for _, v, e in graph.out_edges(node, data=True) if e['relation']=='HAS_CAPABILITY'}
            degrees[node] = sum(e['relation']=='COMPLETED' for _, _, e in graph.out_edges(node, data=True))
        elif attrs['kind'] == 'Task':
            participants = [u for u, _, e in graph.in_edges(node, data=True) if e['relation']=='COMPLETED']
            for u in participants:
                shared[u].update(v for v in participants if v != u)
    result = {}
    for worker_id in worker_ids:
        node = 'worker:'+worker_id
        result[worker_id] = {}
        for capability in capabilities:
            successes, count = counts.get(node, {}).get(capability, [0,0])
            own = (successes+2)/(count+4)
            total = weighted = 0.0
            for neighbor, overlap in shared[node].items():
                s, n = counts.get(neighbor, {}).get(capability, [0,0])
                if n:
                    weight = overlap/math.sqrt(max(1,degrees.get(node,0)*degrees.get(neighbor,0)))
                    weighted += weight*(s+2)/(n+4)
                    total += weight
            peer = weighted/total if total else .5
            result[worker_id][capability] = {
                'score': .6*own + .4*peer, 'category_successes':successes,
                'category_count':count, 'neighbor_prior':peer,
                'shared_task_neighbors':len(shared[node]),
                'path':['worker:'+worker_id,'HAS_CAPABILITY','capability:'+capability] if count else []}
    return result

def save_graph(graph, path):
    import json
    path.write_text(json.dumps(nx.node_link_data(graph, edges='edges'), separators=(',',':')), encoding='utf-8')

def load_graph(path):
    import json
    return nx.node_link_graph(json.loads(path.read_text(encoding='utf-8')), edges='edges')

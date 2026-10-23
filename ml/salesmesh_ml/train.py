"""Fit category histories; tune hybrid weights on validation MAP; evaluate once on test."""
import argparse
import json
import math
import statistics
import time
from pathlib import Path
from .engine import HybridRecommender, ValidationError, validate_agents, validate_task, rejection_reasons, number


def prepare(data):
    agents = validate_agents(data['agents'])
    tasks = [validate_task(t) for t in data['tasks']]
    if len({t['id'] for t in tasks}) != len(tasks): raise ValidationError('duplicate task IDs')
    for t in tasks: number(t.get('timestamp'), 'task.timestamp', 0, 1e15)
    if len({t['timestamp'] for t in tasks}) != len(tasks):
        raise ValidationError('task timestamps must be distinct; supply a chronological numeric sequence')
    tasks.sort(key=lambda t: t['timestamp'])
    by_id = {t['id']: t for t in tasks}
    rows = data['interactions']
    # Fit validates duplicates, labels and referenced agents without retaining this model.
    HybridRecommender.fit(agents, rows)
    for row in rows:
        if row['task_id'] not in by_id: raise ValidationError('interaction has unknown task')
        if row['category'] != by_id[row['task_id']]['category']:
            raise ValidationError('interaction category disagrees with task')
    return agents, tasks, rows


def vectors(model, tasks, rows):
    labels = {}
    for row in rows: labels.setdefault(row['task_id'], {})[row['agent_id']] = row['success']
    result = []
    start = time.perf_counter()
    for t in tasks:
        candidates = validate_agents(t.get('agents', model.agents))
        candidates = [a for a in candidates if not rejection_reasons(a, t)]
        y = labels.get(t['id'], {})
        missing = [a['id'] for a in candidates if a['id'] not in y]
        if missing:
            raise ValidationError(f"{t['id']}: missing suitability labels for {len(missing)} eligible candidates. "
                                  'Unobserved candidates cannot be treated as failures. Use --fit-only for ordinary assignment logs.')
        result.append([(a['id'], model.components(a, t), y[a['id']], a['workload']) for a in candidates])
    return result, (time.perf_counter() - start) * 1000


def metrics(groups, weights, k=3, rule=False):
    ps, recalls, aps, hits = [], [], [], []
    empty = zero_positive = 0
    for group in groups:
        ranked = sorted(group, key=lambda r: (r[3], r[0]) if rule else (-sum(x*w for x,w in zip(r[1], weights)), r[0]))
        if not ranked:
            empty += 1
            continue
        positives = sum(r[2] for r in ranked)
        zero_positive += positives == 0
        ps.append(sum(r[2] for r in ranked[:k]) / k)
        recalls.append(sum(r[2] for r in ranked[:k]) / positives if positives else 0)
        hits.append(ranked[0][2])
        seen = ap = 0
        for position, row in enumerate(ranked, 1):
            if row[2]: seen += 1; ap += seen / position
        aps.append(ap / positives if positives else 0)
    if not hits: raise ValidationError('no tasks with eligible candidates in evaluation split')
    n = len(hits); p = statistics.mean(hits); z = 1.96
    center = (p+z*z/(2*n))/(1+z*z/n)
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return {'precision_at_k': statistics.mean(ps), 'recall_at_k': statistics.mean(recalls),
            'map': statistics.mean(aps), 'top1_success': p,
            'top1_wilson_95_interval': [max(0,center-half), min(1,center+half)],
            'evaluated_tasks': n, 'empty_candidate_tasks': empty, 'zero_positive_tasks': zero_positive, 'k': k}


def train(data, fit_only=False):
    agents, tasks, rows = prepare(data)
    provenance = {'dataset': data.get('name', 'user supplied'), 'synthetic': data.get('synthetic', None),
                  'algorithm': 'content + neighbor-smoothed category history + explicit graph context'}
    if fit_only:
        model = HybridRecommender.fit(agents, rows, metadata={**provenance, 'validation': 'not evaluated', 'weights_source': 'default'})
        return model, {'status': 'fit_only', 'accuracy': None, 'message': 'Histories fitted. No ranking evaluation performed.'}
    if len(tasks) < 20: raise ValidationError('at least 20 chronological tasks are required for 70/15/15 evaluation')
    a, b = int(len(tasks)*.70), int(len(tasks)*.85)
    training, validation, testing = tasks[:a], tasks[a:b], tasks[b:]
    train_ids = {t['id'] for t in training}
    model = HybridRecommender.fit(agents, [r for r in rows if r['task_id'] in train_ids], metadata=provenance)
    val_groups, _ = vectors(model, validation, rows)
    grid = [(x/10, y/10, (10-x-y)/10) for x in range(11) for y in range(11-x)]
    best = max(grid, key=lambda w: metrics(val_groups, w)['map'])
    model.weights = list(best)
    model.metadata.update({'weights_source': 'validation MAP grid search', 'training_last_timestamp': training[-1]['timestamp'],
                           'training_task_count': len(training), 'validation_task_count': len(validation),
                           'test_task_count': len(testing)})
    # Construct test features only after the model selection decision is complete.
    test_groups, elapsed_ms = vectors(model, testing, rows)
    results = {name: metrics(test_groups, weights, rule=name == 'rule_based') for name, weights in
               [('hybrid', best), ('content', (1,0,0)), ('collaborative', (0,1,0)), ('rule_based', (0,0,1))]}
    report = {'metadata': model.metadata, 'weights': model.weights, 'metrics': results,
              'feature_computation_ms_per_test_task': elapsed_ms/len(testing),
              'split_task_ids': {'train': [t['id'] for t in training], 'validation': [t['id'] for t in validation], 'test': [t['id'] for t in testing]},
              'definitions': {'precision_at_k': 'sum of relevant top-k results divided by k (missing slots count as zero)',
                              'recall_at_k': 'relevant top-k divided by all relevant eligible candidates',
                              'map': 'mean full-ranking average precision; zero-positive tasks contribute zero',
                              'top1_success': 'fraction of evaluated tasks whose first-ranked candidate has label 1'},
              'limitations': 'Synthetic results do not establish real-world accuracy. Scores are not calibrated probabilities. '
                             'Use profiles/quality known before outcomes, and task-specific agents snapshots for changing availability or workload. '
                             'Wilson interval assumes independent tasks and may be optimistic with correlated outcomes. '
                             'Ordinary one-assignment-per-task logs cannot provide full-ranking ground truth.'}
    return model, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default='data/demo.json')
    parser.add_argument('--output', default='models/synthetic-demo/model.json')
    parser.add_argument('--report', default='models/synthetic-demo/evaluation.json')
    parser.add_argument('--fit-only', action='store_true')
    args = parser.parse_args()
    try:
        model, report = train(json.loads(Path(args.data).read_text(encoding='utf-8-sig')), args.fit_only)
        model.save(args.output)
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({'model': args.output, 'report': args.report, 'metrics': report.get('metrics', {})}, indent=2))
    except (ValueError, KeyError, TypeError) as error:
        parser.exit(2, f'Invalid training data: {error}\n')


if __name__ == '__main__': main()

"""Explicit macro-averaged ranking metrics, including truncated AP and NDCG."""
import math
import statistics

def evaluate(groups, weights, k=3):
    rows = []
    for group in groups:
        ranked = sorted(group, key=lambda row:(-sum(v*w for v,w in zip(row[1],weights)),row[0]))
        labels = [r[2] for r in ranked]
        positives = sum(labels)
        seen = full_ap = truncated_ap = 0
        for position, y in enumerate(labels,1):
            if y:
                seen += 1
                full_ap += seen/position
                if position <= k:
                    truncated_ap += seen/position
        dcg = sum(y/math.log2(i+2) for i,y in enumerate(labels[:k]))
        ideal = sum(1/math.log2(i+2) for i in range(min(k,positives)))
        rows.append({'top1_success':labels[0], 'precision_at_k':sum(labels[:k])/k,
            'recall_at_k':sum(labels[:k])/positives if positives else 0,
            'map_at_k':truncated_ap/min(k,positives) if positives else 0,
            'map':full_ap/positives if positives else 0,
            'ndcg_at_k':dcg/ideal if ideal else 0, 'hit_at_k':int(any(labels[:k]))})
    if not rows:
        raise ValueError('No tasks to evaluate')
    result = {key:statistics.mean(row[key] for row in rows) for key in rows[0]}
    n=len(rows); p=result['top1_success']; z=1.96
    center=(p+z*z/(2*n))/(1+z*z/n)
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    result.update(k=k,evaluated_tasks=n,top1_wilson_95_interval=[center-half,center+half])
    return result

def feature_groups(groups, task_ids, features, component='new'):
    return [[(row['agent_id'],features[row['agent_id']][row['capability']][component],row['success'])
             for row in groups[tid]] for tid in task_ids]

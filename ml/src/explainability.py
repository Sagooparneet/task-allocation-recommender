def explain(capability, feature, display):
    evidence = feature['graph']
    reasons = []
    if feature['new'][0] > 0:
        reasons.append(f"Training participation supports capability {capability} (compatibility {feature['new'][0]:.2f}).")
    else:
        reasons.append(f'No training participation recorded for capability {capability}; cold-start evidence is limited.')
    reasons.append(f"Recorded training outcomes for this capability: {evidence['category_successes']}/{evidence['category_count']} successful.")
    if evidence['category_count']:
        reasons.append(f"Knowledge graph links this worker to capability {capability} through completed training tasks.")
    if evidence['shared_task_neighbors']:
        reasons.append(f"Graph co-participation links to {evidence['shared_task_neighbors']} training workers contribute a neighbor prior.")
    reasons.append('Display name and location are synthetic demonstration attributes; they do not determine benchmark scores.')
    return reasons

"""Preserve the previously validated neighbor-smoothed collaborative score."""
def score(model, source_worker_id, capability, profiles_by_id):
    category = 'NetEase capability ' + capability
    task = {'id':'feature-query', 'category':category, 'skill':category, 'location':'NOT_RECORDED'}
    return model.components(profiles_by_id[source_worker_id], task)[1]

"""Group existing evidence for display without changing recommendation scores."""
from app.services.skill_display_labels import skill_label


def worker_summary(features, capabilities):
    rows = []
    for code in dict.fromkeys(capabilities):
        evidence = features[code]['graph']
        rows.append({
            'label': skill_label(code),
            'successful': evidence['category_successes'],
            'total': evidence['category_count'],
        })
    return {
        'skills': rows,
        'successful': sum(row['successful'] for row in rows),
        'total': sum(row['total'] for row in rows),
        'with_history': sum(row['total'] > 0 for row in rows),
        'shared_history_used': any(features[code]['graph']['shared_task_neighbors'] > 0
                                   for code in dict.fromkeys(capabilities)),
    }

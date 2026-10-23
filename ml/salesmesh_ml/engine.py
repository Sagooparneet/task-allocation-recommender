"""Content, collaborative and explicit graph-context ranking. Standard library only."""
import json
import math
from pathlib import Path


class ValidationError(ValueError):
    pass


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f'{name} must be a nonempty string')
    return value.strip()


def number(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValidationError(f'{name} must be a finite number between {minimum} and {maximum}')
    return value


def validate_agents(agents):
    if not isinstance(agents, list) or len(agents) > 10000:
        raise ValidationError('agents must be a list with at most 10000 entries')
    result = []
    ids = set()
    for raw in agents:
        if not isinstance(raw, dict):
            raise ValidationError('each agent must be an object')
        a = dict(raw)
        for field in ('id', 'location'):
            a[field] = text(a.get(field), 'agent.' + field)
        if a['id'] in ids:
            raise ValidationError('duplicate agent id: ' + a['id'])
        ids.add(a['id'])
        a['name'] = text(a.get('name', a['id']), 'agent.name')
        for field in ('skills', 'certifications'):
            if not isinstance(a.get(field), list):
                raise ValidationError('agent.' + field + ' must be a list')
            a[field] = sorted(set(text(v, field) for v in a[field]))
        for field in ('verified', 'available'):
            if type(a.get(field)) is not bool:
                raise ValidationError('agent.' + field + ' must be boolean')
        for field, low in (('capacity', 1), ('workload', 0)):
            number(a.get(field), field, low, 100000)
            if not isinstance(a[field], int):
                raise ValidationError(field + ' must be an integer')
        if a['workload'] > a['capacity']:
            raise ValidationError('workload cannot exceed capacity')
        number(a.get('quality'), 'quality', 0, 1)
        result.append(a)
    return result


def validate_task(raw):
    if not isinstance(raw, dict):
        raise ValidationError('task must be an object')
    t = dict(raw)
    for field in ('id', 'category', 'skill', 'location'):
        t[field] = text(t.get(field), 'task.' + field)
    return t


def rejection_reasons(a, t):
    reasons = []
    if not a['verified']: reasons.append('identity_not_verified')
    if not a['available']: reasons.append('unavailable')
    if a['workload'] >= a['capacity']: reasons.append('capacity_full')
    if t['category'] not in a['certifications']: reasons.append('missing_certification')
    if t['skill'] not in a['skills']: reasons.append('missing_skill')
    return reasons


class HybridRecommender:
    """Read-only inference. The host application owns task assignment transactions."""
    def __init__(self, agents, history=None, weights=(.4, .5, .1), metadata=None):
        self.agents = validate_agents(agents)
        if not isinstance(weights, (list, tuple)) or len(weights) != 3:
            raise ValidationError('weights must contain content, collaborative, graph values')
        self.weights = [number(w, 'weight', 0, 1) for w in weights]
        if not math.isclose(sum(self.weights), 1, abs_tol=1e-9):
            raise ValidationError('weights must sum to one')
        self.history = history or {}
        if not isinstance(self.history, dict): raise ValidationError('history must be an object')
        for aid, categories in self.history.items():
            if not isinstance(categories, dict): raise ValidationError('history categories must be objects')
            for category, pair in categories.items():
                if not isinstance(pair, list) or len(pair) != 2 or any(type(x) is not int for x in pair) or not 0 <= pair[0] <= pair[1]:
                    raise ValidationError('history entries must be [successes, count] integers')
        self.metadata = metadata or {}

    @classmethod
    def fit(cls, agents, interactions, weights=(.4, .5, .1), metadata=None):
        checked = validate_agents(agents)
        ids = {a['id'] for a in checked}
        history, seen = {}, set()
        for row in interactions:
            if not isinstance(row, dict): raise ValidationError('interactions must contain objects')
            aid = text(row.get('agent_id'), 'agent_id')
            category = text(row.get('category'), 'category')
            tid = text(row.get('task_id'), 'task_id')
            if aid not in ids: raise ValidationError('interaction has unknown agent: ' + aid)
            if type(row.get('success')) is not int or row['success'] not in (0, 1):
                raise ValidationError('success must be integer 0 or 1')
            if (tid, aid) in seen: raise ValidationError('duplicate task-agent interaction')
            seen.add((tid, aid))
            h = history.setdefault(aid, {}).setdefault(category, [0, 0])
            h[0] += row['success']; h[1] += 1
        return cls(checked, history, weights, metadata)

    def components(self, a, t):
        h = self.history.get(a['id'], {}).get(t['category'], [0, 0])
        weighted = total = 0
        # Training-profile neighbors remain fixed even when current availability changes.
        for b in self.agents:
            if b['id'] == a['id']: continue
            bh = self.history.get(b['id'], {}).get(t['category'], [0, 0])
            union = set(a['skills']) | set(b['skills'])
            similarity = len(set(a['skills']) & set(b['skills'])) / max(1, len(union))
            if bh[1] and similarity:
                weighted += similarity * (bh[0] + 2) / (bh[1] + 4)
                total += similarity
        prior = weighted / total if total else .5
        return [
            .65 * (t['skill'] in a['skills']) + .35 * (a['location'] == t['location']),
            (h[0] + 4 * prior) / (h[1] + 4),
            .55 * a['quality'] + .45 * (1 - a['workload'] / a['capacity']),
        ]

    def recommend(self, task, agents, top_k=3, include_rejected=False):
        t = validate_task(task)
        current = validate_agents(agents)
        if type(top_k) is not int or not 1 <= top_k <= 100:
            raise ValidationError('top_k must be an integer from 1 to 100')
        ranked, rejected = [], []
        for a in current:
            reasons = rejection_reasons(a, t)
            if reasons:
                rejected.append({'agent_id': a['id'], 'reasons': reasons})
                continue
            values = self.components(a, t)
            h = self.history.get(a['id'], {}).get(t['category'], [0, 0])
            paths = [
                [a['id'], 'HAS_SKILL', t['skill']],
                [t['id'], 'REQUIRES', t['skill']],
                [a['id'], 'CERTIFIED_FOR', t['category']],
                [a['id'], 'LOCATED_IN', a['location']],
                [a['id'], 'FREE_CAPACITY', a['capacity'] - a['workload']],
            ]
            ranked.append({'agent_id': a['id'], 'name': a['name'],
                'score': sum(v*w for v,w in zip(values, self.weights)),
                'components': dict(zip(('content', 'collaborative', 'graph'), values)),
                'cold_start': h[1] == 0, 'history': {'successes': h[0], 'count': h[1]},
                'explanation': f"Certified for {t['category']}; has {t['skill']}; "
                    f"{'same region' if a['location'] == t['location'] else 'cross-region match'}; "
                    f"{a['capacity']-a['workload']} free slots. "
                    + (f'{h[0]}/{h[1]} successful historical category outcomes.' if h[1] else 'No category history; neighbor prior used.'),
                'graph_paths': paths})
        ranked.sort(key=lambda r: (-r['score'], r['agent_id']))
        result = {'task_id': t['id'], 'recommendations': ranked[:top_k], 'eligible_count': len(ranked),
                  'weights': self.weights, 'score_type': 'ranking_score_not_probability',
                  'model_metadata': self.metadata}
        if include_rejected: result['rejected'] = rejected
        return result

    def save(self, path):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({'schema_version': 1, 'agents': self.agents,
            'history': self.history, 'weights': self.weights, 'metadata': self.metadata}, indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        if data.get('schema_version') != 1: raise ValidationError('unsupported model schema')
        return cls(data['agents'], data['history'], data['weights'], data.get('metadata'))

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))

def save_json(relative, data):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')

def load_data():
    groups = {}
    with (ROOT / 'data/netease/observations.csv').open(encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            for column in ('timestamp', 'success', 'answer', 'truth', 'source_line'):
                row[column] = int(row[column])
            assert row['success'] == int(row['answer'] == row['truth'])
            groups.setdefault(row['task_id'], []).append(row)
    splits = read_json('data/netease/split_task_ids.json')
    assert len(set.union(*(set(v) for v in splits.values()))) == sum(map(len, splits.values())) == len(groups)
    pairs = set()
    times = {}
    for split, ids in splits.items():
        times[split] = []
        for tid in ids:
            rows = groups[tid]
            assert len({r['capability'] for r in rows}) == len({r['truth'] for r in rows}) == 1
            for row in rows:
                assert row['split'] == split
                key = (tid, row['agent_id'])
                assert key not in pairs
                pairs.add(key)
                times[split].append(row['timestamp'])
    assert max(times['train']) < min(times['validation'])
    assert max(times['validation']) < min(times['test'])
    return groups, splits

def verify_source_rows(groups):
    manifest = read_json('data/raw/netease/manifest.json')
    lookup = {}
    for rows in groups.values():
        for row in rows:
            lookup.setdefault(row['source_file'], {})[row['source_line']] = row
    verified = 0
    for item in manifest['files']:
        path = ROOT / 'data/raw/netease' / item['filename']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], path.name
        if path.name not in lookup:
            continue
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for line, source in enumerate(csv.DictReader(stream), 2):
                derived = lookup[path.name].get(line)
                if derived is None:
                    continue
                for raw, clean in [('taskId','task_id'),('workerId','agent_id'),('capability','capability'),('answer','answer'),('truth','truth'),('completeTime','timestamp')]:
                    assert source[raw] == str(derived[clean]), (path.name,line,raw)
                verified += 1
    assert verified == sum(map(len, groups.values()))
    return verified

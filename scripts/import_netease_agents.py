from pathlib import Path
import argparse
import json
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import OnboardingAgent, Skill, AgentSkill, Task, TaskAssignment
from ml.src.recommender import load_artifacts

DISABLED_PASSWORD = '!NETEASE_DEMO_LOGIN_DISABLED'
LEGACY = {1: 'Grace Achieng', 2: 'Brian Mwangi', 3: 'Amina Hassan', 4: 'Kevin Kiptoo'}


def atomic_pending(path, payload):
    with path.open('w', encoding='utf-8') as stream:
        json.dump(payload, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def import_agents(app, mapping_path=None):
    mapping_path = Path(mapping_path or Path(app.instance_path) / 'netease_agent_bindings.json')
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    pending = mapping_path.with_name(mapping_path.name + '.pending')
    lock = mapping_path.with_name(mapping_path.name + '.lock')
    # Prevent concurrent imports. A stale lock after interruption needs inspection.
    with lock.open('x', encoding='utf-8') as handle:
        handle.write(str(os.getpid()))
    committed = False
    try:
        with app.app_context():
            profiles = load_artifacts()['profiles']
            if len(profiles) != 1653:
                raise ValueError('Expected the verified set of 1,653 NetEase profiles.')
            if any(p['source_worker_id'] != worker for worker,p in profiles.items()):
                raise ValueError('Profile/source-ID mismatch.')
            existing = OnboardingAgent.query.all()
            by_email = {a.email.lower(): a for a in existing}
            present = {worker: by_email[f'netease-{worker}@demo.invalid'] for worker in profiles
                       if f'netease-{worker}@demo.invalid' in by_email}

            if present:
                if len(present) != len(profiles):
                    raise ValueError('Partial/colliding import detected. No changes made; inspect before continuing.')
                expected = {str(a.id): worker for worker,a in present.items()}
                source = mapping_path if mapping_path.exists() else pending
                if not source.exists():
                    raise ValueError('Agents already exist without an import mapping. Stop for inspection.')
                payload = json.loads(source.read_text(encoding='utf-8'))
                if payload.get('worker_bindings') != expected or payload.get('status') != 'ready':
                    raise ValueError('Existing mapping does not match database identities.')
                if source == pending:
                    os.replace(pending, mapping_path)
                return {'result':'Already imported; mapping verified. No database changes.',
                        'imported_agents':len(present), 'total_agents':len(existing),
                        'tasks':Task.query.count(), 'assignments':TaskAssignment.query.count(),
                        'mapping_file':str(mapping_path)}

            if mapping_path.exists():
                raise ValueError('Mapping exists but its agents are absent. Stop for inspection.')
            if {a.id:a.name for a in existing} != LEGACY:
                raise ValueError('Existing agents differ from the four previewed records. Run a new preview first.')

            task_count, assignment_count = Task.query.count(), TaskAssignment.query.count()
            if task_count != 7:
                raise ValueError('Task count changed since preview. Run a new preview before importing.')
            skill_by_name = {s.name:s for s in Skill.query.all()}
            capability_names = sorted({skill for p in profiles.values() for skill in p['skills']})
            if not set(capability_names).issubset({'NetEase capability '+c for c in ('50','53','56','69')}):
                raise ValueError('Unexpected capability labels.')
            for name in capability_names:
                if name not in skill_by_name:
                    item=Skill(name=name)
                    db.session.add(item)
                    skill_by_name[name]=item
            db.session.flush()
            bindings, display_ids, cold_start_ids = {}, {}, []
            for worker, profile in sorted(profiles.items()):
                rate = profile['historical_success_rate']
                agent = OnboardingAgent(
                    name=profile['agent_name'], email=f'netease-{worker}@demo.invalid',
                    password_hash=DISABLED_PASSWORD,
                    specialization='NetEase proxy demonstration', location=profile['location'],
                    availability=True, workload=0,
                    # Existing UI expects a numeric value; zero-count profiles are
                    # explicitly marked unknown in mapping, not measured 0% success.
                    performance_score=100*rate if rate is not None else 0.0)
                db.session.add(agent)
                db.session.flush()
                bindings[str(agent.id)] = worker
                display_ids[str(agent.id)] = profile['agent_id']
                if rate is None:
                    cold_start_ids.append(agent.id)
                for name in profile['skills']:
                    db.session.add(AgentSkill(agent_id=agent.id, skill_id=skill_by_name[name].id,
                                             proficiency_level='Observed participation'))
            for agent in existing:
                agent.availability=False
            db.session.flush()
            assert Task.query.count()==task_count and TaskAssignment.query.count()==assignment_count
            payload={'schema_version':1,'status':'ready',
                'integration_status':'profiles imported; recommendation service not connected',
                'worker_bindings':bindings,'display_ids':display_ids,
                'legacy_agent_ids':sorted(LEGACY),'unknown_performance_agent_ids':cold_start_ids,
                'notes':['Names and Kenyan locations are synthetic display attributes.',
                    'Availability=True and workload=0 are initial application demonstration state.',
                    'Skills reflect training participation, not professional certification.',
                    'NetEase capability IDs have not been relabeled as onboarding skills.',
                    'Performance is unknown for listed cold-start IDs; stored zero is only a schema/UI placeholder.',
                    'Imported accounts have unusable passwords. Existing accounts keep their passwords.']}
            # Pending mapping is ignored by future service code. If the final rename
            # fails after commit, rerunning verifies IDs and recovers this exact file.
            atomic_pending(pending, payload)
            db.session.commit()
            committed=True
            os.replace(pending, mapping_path)
            return {'result':'Import completed', 'imported_agents':len(bindings),
                'total_agents':OnboardingAgent.query.count(), 'old_agents_marked_unavailable':len(existing),
                'tasks':Task.query.count(),'assignments':TaskAssignment.query.count(),
                'unknown_performance_profiles':len(cold_start_ids),'mapping_file':str(mapping_path)}
    except Exception:
        if not committed:
            with app.app_context():
                db.session.rollback()
        raise
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args=parser.parse_args()
    if not args.apply:
        parser.error('Use --apply only after the backup and preview stages passed.')
    print(json.dumps(import_agents(create_app()), indent=2))

import datetime as _deadline_datetime

def _future_task_deadline():
    return (_deadline_datetime.datetime.now(_deadline_datetime.timezone(_deadline_datetime.timedelta(hours=3))) + _deadline_datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")

"""Exercise production routes using a disposable copy, never a live database.

Login credentials are tested separately. This script creates authenticated test
sessions without enabling any dataset worker's account.
"""
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import sys
import tempfile

from sqlalchemy.engine import URL


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run_check(project, temporary_parent=None):
    project = Path(project).resolve()
    sys.path.insert(0, str(project))
    source = project / 'instance' / 'deployment_test'
    source_db = source / 'task_allocation.db'
    for filename in ('task_allocation.db', 'netease_agent_bindings.json',
                     'onboarding_capability_mapping.json', 'setup_complete.json'):
        require((source / filename).is_file(), f'Missing setup file: {filename}')

    parent = Path(temporary_parent or project / 'instance').resolve()
    require(parent.is_dir(), 'Temporary parent directory does not exist.')
    with tempfile.TemporaryDirectory(prefix='workflow-check-', dir=parent) as name:
        instance = Path(name).resolve()
        require(instance.parent == parent, 'Unexpected temporary directory.')
        database = instance / 'task_allocation.db'
        require(database != source_db.resolve(), 'Refusing to use source database.')
        # SQLite backup provides a consistent snapshot, including WAL contents.
        original = sqlite3.connect(source_db.resolve().as_uri() + '?mode=ro', uri=True)
        copied = sqlite3.connect(database)
        try:
            original.backup(copied)
        finally:
            copied.close()
            original.close()
        for filename in ('netease_agent_bindings.json', 'onboarding_capability_mapping.json'):
            shutil.copyfile(source / filename, instance / filename)

        settings = {
            'INTELLITASK_SECRET_KEY': secrets.token_hex(32),
            'INTELLITASK_DATABASE_URL': URL.create(
                'sqlite', database=str(database)
            ).render_as_string(hide_password=False),
            'INTELLITASK_INSTANCE_PATH': str(instance),
        }
        previous = {key: os.environ.get(key) for key in settings}
        os.environ.update(settings)
        app = None
        try:
            from wsgi import app
            from app.extensions import db
            from app.models import Supervisor, Skill, Task, TaskAssignment, OnboardingAgent
            from app.services.netease_recommendation_service import NetEaseRecommendationService
            with app.app_context():
                require(Path(db.engine.url.database).resolve() == database,
                        'Refusing unexpected database connection.')
                require(not app.debug, 'Debugging must be disabled.')
                supervisor = Supervisor.query.first()
                require(supervisor is not None, 'No test supervisor found.')
                supervisor_id = supervisor.id
                skill_id = Skill.query.filter_by(name='NetEase capability 56').one().id
            base = 'https://localhost'
            title = 'Deployment workflow check ' + secrets.token_hex(6)
            with app.test_client() as client:
                with client.session_transaction(base_url=base) as session:
                    session['_user_id'] = f'supervisor:{supervisor_id}'
                    session['_fresh'] = True
                response = client.post('/supervisor/task/create', base_url=base, data={"deadline": _future_task_deadline(),
                    'task_type': '__other__', 'custom_task_type': title,
                    'description': 'Disposable application workflow test.',
                    'location': 'Nairobi', 'priority': 'Medium',
                    'required_skills': str(skill_id),
                })
                require(response.status_code == 302, 'Task creation failed.')
                with app.app_context():
                    task_id = Task.query.filter_by(task_type=title).one().id
                    results = NetEaseRecommendationService().get_recommendations(task_id)
                    require(bool(results), 'No NetEase recommendations returned.')
                    agent_id = results[0]['agent_id']
                    workload = db.session.get(OnboardingAgent, agent_id).workload or 0
                print('Task creation and NetEase inference: PASS')
                response = client.get(f'/supervisor/task/{task_id}/recommendations', base_url=base)
                require(response.status_code == 200, 'Recommendation page failed.')
                require(results[0]['source_worker_id'].encode() in response.data,
                        'Source worker ID missing from page.')
                with client.session_transaction(base_url=base) as session:
                    token = session['assignment_csrf_token']
                print('Recommendations displayed on page: PASS')
                form = {'agent_id': agent_id, 'assignment_csrf_token': token}
                for _ in range(2):
                    response = client.post(f'/supervisor/task/{task_id}/assign',
                                           base_url=base, data=form)
                    require(response.status_code == 302, 'Assignment request failed.')
                with app.app_context():
                    assignments = TaskAssignment.query.filter_by(task_id=task_id).all()
                    require(len(assignments) == 1, 'Expected exactly one assignment.')
                    assignment_id = assignments[0].id
                    require(assignments[0].agent_id == agent_id, 'Wrong worker assigned.')
                    require(db.session.get(Task, task_id).status == 'Assigned', 'Task not assigned.')
                    require(db.session.get(OnboardingAgent, agent_id).workload == workload + 1,
                            'Workload did not increase exactly once.')
                print('Assignment, duplicate protection, and workload: PASS')
                with client.session_transaction(base_url=base) as session:
                    session.clear()
                    session['_user_id'] = f'agent:{agent_id}'
                    session['_fresh'] = True
                response = client.get('/agent/dashboard', base_url=base)
                require(response.status_code == 200 and title.encode() in response.data,
                        'Assigned task missing from worker dashboard.')
                for _ in range(2):
                    response = client.post(f'/agent/assignment/{assignment_id}/complete', base_url=base)
                    require(response.status_code == 302, 'Completion request failed.')
                with app.app_context():
                    require(db.session.get(Task, task_id).status == 'Completed', 'Task not completed.')
                    require(db.session.get(TaskAssignment, assignment_id).status == 'Completed',
                            'Assignment not completed.')
                    require(db.session.get(OnboardingAgent, agent_id).workload == workload,
                            'Completion did not restore workload correctly.')
                print('Worker dashboard, completion, and repeat completion: PASS')
        finally:
            if app is not None:
                with app.app_context():
                    from app.extensions import db
                    db.session.remove()
                    db.engine.dispose()
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    print('Temporary copy removed. Source databases were not changed.')
    print('This checks Flask routes, not a public HTTPS server or real worker login.')


if __name__ == '__main__':
    run_check(Path(__file__).resolve().parents[1])

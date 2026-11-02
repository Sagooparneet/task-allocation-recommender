from pathlib import Path
import json
import pytest
from sqlalchemy import null
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models import (OnboardingAgent, Administrator, Supervisor, IndependentWorkerRegistration,
    AgentSkill, Skill, Task, TaskSkill, TaskAssignment, WorkerSourceBinding)
from app.services.independent_workers import PENDING_PASSWORD
from app.services.independent_worker_matching import matching_workers
from app.services.netease_recommendation_service import NetEaseRecommendationService
from app.services.worker_capacity import active_task_count
from test_workflow import create_test_task


def visit(client, method, path, **kwargs):
    with client.application.app_context():
        return client.open(path, method=method, **kwargs)


def login(client, email='supervisor@test.com'):
    return visit(client, 'POST', '/auth/login', data={'email':email, 'password':'password123'})


def new_worker(name='New Worker', email='new@example.com'):
    worker=OnboardingAgent(name=name, email=email, location='Mombasa', availability=True,
        account_disabled=False, workload=0, performance_score=null())
    worker.set_password('password123')
    db.session.add(worker);db.session.flush()
    db.session.add(IndependentWorkerRegistration(agent_id=worker.id,
        created_by_admin_id=Administrator.query.first().id))
    db.session.add(AgentSkill(agent_id=worker.id, skill_id=Skill.query.filter_by(name='KYC Verification').first().id,
        proficiency_level='Administrator confirmed'))
    db.session.commit()
    return worker


def form(client, task_id, agent_id):
    login(client)
    assert visit(client,'GET',f'/supervisor/task/{task_id}/recommendations').status_code==200
    with client.session_transaction() as session:
        return {'agent_id':agent_id, 'assignment_csrf_token':session['assignment_csrf_token']}


def assign(client, task_id, data):
    return visit(client,'POST',f'/supervisor/task/{task_id}/assign-new-worker',data=data)


def assert_pending(task_id):
    db.session.expire_all()
    assert db.session.get(Task,task_id).status=='Pending'
    assert TaskAssignment.query.filter_by(task_id=task_id).count()==0


def test_separate_list_does_not_change_model_order_scores_or_bindings(app,client):
    task_id=create_test_task(app)
    baseline=NetEaseRecommendationService().get_recommendations(task_id)
    path=Path(app.instance_path)/'netease_agent_bindings.json';before=path.read_bytes()
    worker=new_worker()
    matches=matching_workers(task_id)
    assert matches==[{'agent_id':worker.id,'name':'New Worker','city':'Mombasa','active_tasks':0}]
    assert NetEaseRecommendationService().get_recommendations(task_id)==baseline
    form(client,task_id,worker.id)
    html=visit(client,'GET',f'/supervisor/task/{task_id}/recommendations').get_data(as_text=True)
    section=html.split('<section id="new-worker-matches"')[1].split('</section>')[0]
    assert 'New Worker' in section and 'Ranking score' not in section and '/100' not in section
    assert 'Services matched' in section and 'Mombasa' in section
    assert path.read_bytes()==before and db.session.get(WorkerSourceBinding,worker.id) is None


def test_assignment_duplicate_protection_and_worker_progress(app,client):
    task_id=create_test_task(app);worker=new_worker();worker_id=worker.id
    baseline=NetEaseRecommendationService().get_recommendations(task_id)
    data=form(client,task_id,worker_id)
    assert assign(client,task_id,data).status_code==302
    assign(client,task_id,data)
    db.session.expire_all()
    rows=TaskAssignment.query.filter_by(task_id=task_id).all();assert len(rows)==1
    assignment_id=rows[0].id
    assert rows[0].agent_id==worker_id and rows[0].status=='Assigned'
    assert db.session.get(OnboardingAgent,worker_id).workload==1
    public=app.test_client();login(public,worker.email)
    assert visit(public,'GET','/agent/dashboard').status_code==200
    with public.session_transaction() as session:
        progress={'task_progress_csrf_token':session['task_progress_csrf_token']}
    for action in ('start','complete','complete'):
        assert visit(public,'POST',f'/agent/assignment/{assignment_id}/{action}',data=progress).status_code==302
    db.session.expire_all()
    assert db.session.get(Task,task_id).status=='Completed'
    assert db.session.get(TaskAssignment,assignment_id).completed_at is not None
    assert db.session.get(OnboardingAgent,worker_id).workload==0
    assert db.session.get(OnboardingAgent,worker_id).performance_score is None
    assert not db.session.get(WorkerSourceBinding,worker_id)
    assert NetEaseRecommendationService().get_recommendations(task_id)==baseline


@pytest.mark.parametrize('case',['unavailable','disabled','pending','partial','unconfirmed','registration_removed','bound_database','bound_file','capacity'])
def test_ineligible_and_stale_forms_are_rejected(app,client,case):
    task_id=create_test_task(app);worker=new_worker();worker_id=worker.id
    data=form(client,task_id,worker_id)
    if case=='unavailable':worker.availability=False
    elif case=='disabled':worker.account_disabled=True
    elif case=='pending':worker.password_hash=PENDING_PASSWORD
    elif case=='partial':
        other=Skill(name='SIM Registration');db.session.add(other);db.session.flush()
        db.session.add(TaskSkill(task_id=task_id,skill_id=other.id))
    elif case=='unconfirmed':AgentSkill.query.filter_by(agent_id=worker_id).first().proficiency_level='Unconfirmed'
    elif case=='registration_removed':db.session.delete(db.session.get(IndependentWorkerRegistration,worker_id))
    elif case=='bound_database':db.session.add(WorkerSourceBinding(agent_id=worker_id,source_worker_id='unrelated-source'))
    elif case=='bound_file':
        path=Path(app.instance_path)/'netease_agent_bindings.json';document=json.loads(path.read_text())
        document['worker_bindings'][str(worker_id)]='12345';path.write_text(json.dumps(document))
    elif case=='capacity':
        for n in range(3):
            other_id=create_test_task(app)
            db.session.add(TaskAssignment(task_id=other_id,agent_id=worker_id,
                supervisor_id=Supervisor.query.first().id,status='In progress' if n==0 else 'Assigned'))
            db.session.commit()
        worker.workload=0
    db.session.commit()
    assert matching_workers(task_id)==[]
    assign(client,task_id,data);assert_pending(task_id)
    assert db.session.get(OnboardingAgent,worker_id).workload==0


def test_empty_and_unsupported_requirements_never_match(app):
    task_id=create_test_task(app);new_worker()
    TaskSkill.query.filter_by(task_id=task_id).delete();db.session.commit()
    assert matching_workers(task_id)==[]
    db.session.add(TaskSkill(task_id=task_id,skill_id=Skill.query.filter_by(name='Customer Service').first().id));db.session.commit()
    assert matching_workers(task_id)==[]


def test_dataset_workers_cannot_be_assigned_through_new_worker_action(app,client):
    task_id=create_test_task(app);worker=OnboardingAgent.query.first()
    assign(client,task_id,form(client,task_id,worker.id));assert_pending(task_id)


def test_new_worker_cannot_be_assigned_through_model_action(app,client):
    task_id=create_test_task(app);worker=new_worker();data=form(client,task_id,worker.id)
    visit(client,'POST',f'/supervisor/task/{task_id}/assign',data=data)
    assert_pending(task_id)


@pytest.mark.parametrize('email',['admin@test.com','netease-6376@demo.invalid'])
def test_non_supervisors_cannot_assign(app,client,email):
    task_id=create_test_task(app);worker=new_worker();login(client,email)
    assert assign(client,task_id,{'agent_id':worker.id}).status_code in (302,403)
    assert_pending(task_id)


def test_ownership_csrf_and_get_are_protected(app,client):
    task_id=create_test_task(app);worker=new_worker();data=form(client,task_id,worker.id)
    assert visit(client,'GET',f'/supervisor/task/{task_id}/assign-new-worker').status_code==405
    assign(client,task_id,{**data,'assignment_csrf_token':'wrong'});assert_pending(task_id)
    other=Supervisor(name='Other',email='other@test.com',password_hash='disabled');db.session.add(other);db.session.flush()
    db.session.get(Task,task_id).supervisor_id=other.id;db.session.commit()
    assert assign(client,task_id,data).status_code==403
    assert visit(client,'GET',f'/supervisor/task/{task_id}/recommendations').status_code==403
    assert_pending(task_id)


def test_model_outage_does_not_block_independent_service_matching(app,client,monkeypatch):
    from app.services.recommendation_service import HybridRecommendationService
    def unavailable(*args,**kwargs):raise ValueError('Unavailable model')
    monkeypatch.setattr(HybridRecommendationService,'get_recommendations',unavailable)
    task_id=create_test_task(app);worker=new_worker();data=form(client,task_id,worker.id)
    page=visit(client,'GET',f'/supervisor/task/{task_id}/recommendations')
    assert b'Recommendations unavailable' in page.data and b'New workers matching this task' in page.data
    assign(client,task_id,data)
    assert TaskAssignment.query.filter_by(task_id=task_id,agent_id=worker.id).count()==1


def test_services_rechecked_after_candidate_selection(app,client,monkeypatch):
    import app.supervisor.routes as routes
    task_id=create_test_task(app);worker=new_worker();data=form(client,task_id,worker.id)
    stale=matching_workers(task_id)
    AgentSkill.query.filter_by(agent_id=worker.id).delete();db.session.commit()
    real=routes.matching_workers;calls=[]
    def first_stale(*args):
        calls.append(1)
        return stale if len(calls)==1 else real(*args)
    monkeypatch.setattr(routes,'matching_workers',first_stale)
    assign(client,task_id,data);assert_pending(task_id)
    assert len(calls)==2 and db.session.get(OnboardingAgent,worker.id).workload==0


def test_failed_commit_preserves_task_and_workload(app,client,monkeypatch):
    task_id=create_test_task(app);worker=new_worker();data=form(client,task_id,worker.id)
    def fail():raise SQLAlchemyError('Simulated failure')
    with monkeypatch.context() as patch:
        patch.setattr(db.session,'commit',fail);assign(client,task_id,data)
    assert_pending(task_id)
    assert db.session.get(OnboardingAgent,worker.id).workload==0


def test_three_task_limit_uses_real_counts_and_completed_tasks_free_slots(app,client):
    worker=new_worker();worker_id=worker.id
    for n in range(4):
        task_id=create_test_task(app);data=form(client,task_id,worker_id);assign(client,task_id,data)
    db.session.expire_all()
    assert active_task_count(worker_id)==3
    assert_pending(task_id)
    completed=TaskAssignment.query.filter_by(agent_id=worker_id).first();completed.status='Completed';db.session.commit()
    assert matching_workers(task_id)[0]['active_tasks']==2
    assign(client,task_id,data)
    assert active_task_count(worker_id)==3


def test_alphabetical_pagination_and_display_names(app,client):
    task_id=create_test_task(app)
    for n in range(11):new_worker(f'Worker {10-n:02}',f'worker{n}@example.com')
    login(client)
    page=visit(client,'GET',f'/supervisor/task/{task_id}/recommendations').get_data(as_text=True)
    section=page.split('<section id="new-worker-matches"')[1]
    assert 'Worker 00' in section and 'Worker 10' not in section and 'Page 1 of 2' in section
    page=visit(client,'GET',f'/supervisor/task/{task_id}/recommendations?new_page=2').get_data(as_text=True)
    section=page.split('<section id="new-worker-matches"')[1]
    assert 'Worker 10' in section and 'Worker 00' not in section


def test_concurrent_new_assignments_cannot_exceed_capacity(app,client,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import app.supervisor.routes as routes
    worker=new_worker();worker_id=worker.id
    for n in range(2):
        existing=create_test_task(app)
        db.session.add(TaskAssignment(task_id=existing,agent_id=worker_id,
            supervisor_id=Supervisor.query.first().id,status='Assigned'))
        db.session.commit()
    worker.workload=2;db.session.commit()
    task_ids=[create_test_task(app),create_test_task(app)]
    clients=[app.test_client(),app.test_client()]
    forms=[form(browser,task_id,worker_id) for browser,task_id in zip(clients,task_ids)]
    real=routes.matching_workers;barrier=threading.Barrier(2);local=threading.local()
    def synchronize_first_match(*args):
        result=real(*args)
        if not getattr(local,'checked',False):
            local.checked=True;barrier.wait(timeout=15)
        return result
    monkeypatch.setattr(routes,'matching_workers',synchronize_first_match)
    def attempt(index):
        return assign(clients[index],task_ids[index],forms[index]).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(attempt,[0,1]))==[302,302]
    db.session.expire_all()
    assert active_task_count(worker_id)==3
    assert TaskAssignment.query.filter(TaskAssignment.task_id.in_(task_ids)).count()==1
    assert sorted(db.session.get(Task,t).status for t in task_ids)==['Assigned','Pending']
    assert db.session.get(OnboardingAgent,worker_id).workload==3

from pathlib import Path
import pytest
from sqlalchemy import text
from app.extensions import db
from app.models import TaskAssignment
from test_admin_workers import login, worker, add_assignment


def form(client, agent, action='deactivate'):
    assert client.get(f'/admin/workers/{agent.id}/account-status').status_code == 200
    with client.session_transaction() as session:
        return dict(csrf_token=session['worker_account_csrf_token'], action=action, confirm='yes')


def test_deactivate_reactivate_preserves_identity_and_history(app, client):
    agent = worker()
    add_assignment(agent, 'Finished work', 'Completed')
    original = {c.name:getattr(agent,c.name) for c in agent.__table__.columns
                if c.name not in ('availability','account_disabled')}
    history = db.session.execute(text('SELECT * FROM task_assignments')).all()
    tasks = db.session.execute(text('SELECT * FROM tasks')).all()
    binding = Path(app.instance_path)/'netease_agent_bindings.json'
    original_binding = binding.read_bytes()
    login(client)
    path = f'/admin/workers/{agent.id}/account-status'
    data = form(client,agent)
    assert client.post(path,data={**data,'email':'bad@test.invalid','workload':'0'}).status_code == 302
    db.session.expire_all()
    assert agent.account_disabled and not agent.availability
    assert b'Reactivate account' in client.get(f'/admin/workers/{agent.id}').data
    assert client.post(path,data=data).status_code == 422
    assert client.post(path,data=form(client,agent,'reactivate')).status_code == 302
    db.session.expire_all()
    assert not agent.account_disabled and not agent.availability
    assert {key:getattr(agent,key) for key in original} == original
    assert db.session.execute(text('SELECT * FROM task_assignments')).all() == history
    assert db.session.execute(text('SELECT * FROM tasks')).all() == tasks
    assert binding.read_bytes() == original_binding


@pytest.mark.parametrize('status',['Assigned','In progress'])
def test_unfinished_work_blocks_deactivation_even_with_forged_post(app,client,status):
    agent=worker()
    login(client)
    data=form(client,agent)
    # Work added after the confirmation page was opened is also protected.
    add_assignment(agent,'Still working',status)
    before=db.session.execute(text('SELECT * FROM task_assignments')).all()
    response=client.post(f'/admin/workers/{agent.id}/account-status',data=data)
    assert response.status_code == 422 and b'unfinished tasks' in response.data
    db.session.expire_all()
    assert not agent.account_disabled and agent.availability
    assert db.session.execute(text('SELECT * FROM task_assignments')).all() == before


def test_inconsistent_task_status_is_protected(app,client):
    agent=worker()
    add_assignment(agent,'Mismatch','Completed')
    assignment=TaskAssignment.query.filter_by(agent_id=agent.id).first()
    assignment.task.status='In progress'
    db.session.commit()
    login(client)
    assert client.post(f'/admin/workers/{agent.id}/account-status',data=form(client,agent)).status_code==422
    assert not agent.account_disabled


@pytest.mark.parametrize('email',['supervisor@test.com','netease-6376@demo.invalid'])
def test_non_admin_cannot_change_account(app,client,email):
    agent=worker()
    login(client,email)
    path=f'/admin/workers/{agent.id}/account-status'
    assert client.get(path).status_code==403
    assert client.post(path,data={'action':'deactivate'}).status_code==403


def test_confirmation_csrf_and_readonly_get(app,client):
    agent=worker()
    path=f'/admin/workers/{agent.id}/account-status'
    assert client.post(path).status_code==302
    login(client)
    data=form(client,agent)
    assert not agent.account_disabled
    assert client.post(path,data={'action':'deactivate','confirm':'yes'}).status_code==400
    response=client.post(path,data={**data,'confirm':''})
    assert response.status_code==422 and b'href="#confirm"' in response.data
    assert client.post(path,data={**data,'action':'delete'}).status_code==400
    assert client.get('/admin/workers/999999/account-status').status_code==404
    assert not agent.account_disabled


def test_disabled_account_cannot_be_made_available(app,client):
    agent=worker()
    login(client)
    availability_path=f'/admin/workers/{agent.id}/availability'
    client.get(availability_path)
    with client.session_transaction() as session:
        old=dict(csrf_token=session['worker_availability_csrf_token'],original_availability='available',availability='available')
    client.post(f'/admin/workers/{agent.id}/account-status',data=form(client,agent))
    assert client.post(availability_path,data=old).status_code==422
    db.session.expire_all()
    assert agent.account_disabled and not agent.availability

from app.extensions import db
from app.models import Supervisor, Task


def login(client, email='admin@test.com'):
    return client.post('/auth/login', data={'email': email, 'password': 'password123'})


def account():
    return Supervisor.query.filter_by(email='supervisor@test.com').one()


def form(client, path, token_key):
    response = client.get(path)
    assert response.status_code == 200
    with client.session_transaction() as values:
        return values[token_key]


def test_edit_name_only_and_stale_edit_protected(app, client):
    record = account()
    old_hash, old_email = record.password_hash, record.email
    login(client)
    path = f'/admin/supervisors/{record.id}/edit'
    token = form(client, path, 'supervisor_edit_csrf_token')
    response = client.post(path, data={'csrf_token':token, 'original_name':record.name,
        'name':'New Team Lead', 'email':'ignored@example.com', 'account_disabled':'on'})
    assert response.status_code == 302
    db.session.expire_all()
    assert (record.name, record.email, record.password_hash, record.account_disabled) == (
        'New Team Lead', old_email, old_hash, False)
    response = client.post(path, data={'csrf_token':token, 'original_name':'Test Supervisor', 'name':'Stale'})
    assert response.status_code == 422 and b'changed in another session' in response.data
    assert record.name == 'New Team Lead'


def test_invalid_name_and_csrf(app, client):
    record = account()
    login(client)
    path = f'/admin/supervisors/{record.id}/edit'
    token = form(client, path, 'supervisor_edit_csrf_token')
    assert client.post(path, data={'csrf_token':'wrong','name':'Bad'}).status_code == 400
    response = client.post(path, data={'csrf_token':token,'original_name':record.name,'name':' '})
    assert response.status_code == 422 and b'aria-invalid="true"' in response.data
    assert record.name == 'Test Supervisor'


def test_unfinished_task_blocks_deactivation(app, client):
    record = account()
    db.session.add(Task(task_type='Current work', supervisor_id=record.id, status='Pending'))
    db.session.commit()
    login(client)
    path = f'/admin/supervisors/{record.id}/account-status'
    token = form(client, path, 'supervisor_account_csrf_token')
    response = client.post(path, data={'csrf_token':token,'action':'deactivate','confirm':'yes'})
    assert response.status_code == 422
    assert b'unfinished tasks' in response.data
    db.session.expire_all()
    assert not record.account_disabled


def test_deactivate_and_reactivate_preserve_account(app, client):
    record = account()
    saved = (record.email, record.password_hash)
    login(client)
    path = f'/admin/supervisors/{record.id}/account-status'
    token = form(client, path, 'supervisor_account_csrf_token')
    assert client.post(path, data={'csrf_token':token,'action':'deactivate'}).status_code == 422
    response = client.post(path, data={'csrf_token':token,'action':'deactivate','confirm':'yes'})
    assert response.status_code == 302
    db.session.expire_all()
    assert record.account_disabled
    assert (record.email,record.password_hash) == saved
    token = form(client, path, 'supervisor_account_csrf_token')
    response = client.post(path, data={'csrf_token':token,'action':'reactivate','confirm':'yes'})
    assert response.status_code == 302
    db.session.expire_all()
    assert not record.account_disabled
    assert (record.email,record.password_hash) == saved


def test_role_restrictions_and_missing_account(app, client):
    login(client, 'supervisor@test.com')
    assert client.get('/admin/supervisors/1/edit').status_code == 403
    assert client.get('/admin/supervisors/1/account-status').status_code == 403
    client.get('/auth/logout')
    login(client)
    assert client.get('/admin/supervisors/999/edit').status_code == 404
    assert client.get('/admin/supervisors/999/account-status').status_code == 404

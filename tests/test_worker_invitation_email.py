from datetime import timedelta
import hashlib
import re
import base64
from email import policy
from email.parser import BytesParser
from types import SimpleNamespace
import pytest
pytestmark = pytest.mark.usefixtures('legacy_setup_code')
from app.extensions import db
from app.models import OnboardingAgent, WorkerSetupInvitation, WorkerSourceBinding
from app.services.independent_workers import PENDING_PASSWORD
from app.services.invitation_email import email_settings, EmailConfigurationError
import app.services.invitation_email as email_service
from app.services.worker_setup import issue_invitation, utcnow
from test_worker_password_setup import new_worker, visit, login, setup_form, PASSWORD


@pytest.fixture(autouse=True)
def fake_gmail(monkeypatch):
    calls={'messages': [], 'connections': [], 'requests': []}
    class Transport:
        def __init__(self,credentials):
            calls['connections'].append(credentials)
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,endpoint,**kwargs):
            calls['requests'].append((endpoint,kwargs))
            message=BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(kwargs['json']['raw']))
            calls['messages'].append((message,str(message['From']),[str(message['To'])]))
            return SimpleNamespace(status_code=200,json=lambda:{'id':'fake-google-message-id'})
    monkeypatch.setattr(email_service,'_authorized_session',Transport)
    return calls


@pytest.fixture()
def gmail(app):
    app.config.update(INTELLITASK_GMAIL_ADDRESS='sender@gmail.com',
        INTELLITASK_INVITATION_BASE_URL='https://intellitask.example')
    app.extensions['intellitask_gmail_credentials']=SimpleNamespace(refresh_token='fake-refresh-token')
    return app.config


def email_form(client,worker_id,**changes):
    login(client)
    visit(client,'GET',f'/admin/workers/{worker_id}/setup')
    with client.session_transaction() as session:
        data={'csrf_token':session['worker_setup_admin_csrf'],'confirm':'yes','delivery':'email'}
    data.update(changes)
    return data


def post_email(client,worker_id,data):
    return visit(client,'POST',f'/admin/workers/{worker_id}/setup',data=data)


def test_email_uses_registered_recipient_configured_url_and_single_use_setup(app,client,new_worker,gmail,fake_gmail):
    data=email_form(client,new_worker,recipient='attacker@example.com',base_url='https://attacker.example')
    response=post_email(client,new_worker,data)
    assert response.status_code==200 and b'Invitation submitted to Gmail' in response.data
    message,sender,recipients=fake_gmail['messages'][0]
    assert recipients==['independent@example.com'] and message['To']=='independent@example.com'
    assert sender=='sender@gmail.com' and message['From']==sender
    endpoint,kwargs=fake_gmail['requests'][0]
    assert endpoint=='https://gmail.googleapis.com/gmail/v1/users/sender%40gmail.com/messages/send'
    assert kwargs['timeout']==20 and kwargs['allow_redirects'] is False and kwargs['max_allowed_time']==40
    body=message.get_content()
    token=re.search(r'https://intellitask.example/auth/worker-setup#([A-Za-z0-9_-]{43})',body).group(1)
    assert 'attacker' not in body and 'abcdefghijklmnop' not in body and PASSWORD not in body
    row=db.session.get(WorkerSetupInvitation,new_worker,populate_existing=True)
    assert row.token_hash==hashlib.sha256(token.encode()).hexdigest()
    assert db.session.get(OnboardingAgent,new_worker).password_hash==PENDING_PASSWORD
    public=app.test_client()
    result=visit(public,'POST','/auth/worker-setup',data=setup_form(public,token))
    assert result.status_code==302
    db.session.expire_all();worker=db.session.get(OnboardingAgent,new_worker)
    assert worker.check_password(PASSWORD) and not worker.account_disabled and not worker.availability
    assert not db.session.get(WorkerSourceBinding,new_worker)


def test_request_host_cannot_change_emailed_link(app,client,new_worker,gmail,fake_gmail):
    data=email_form(client,new_worker)
    # Send a real untrusted Host header with the existing authenticated session.
    cookie=client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    client.set_cookie(app.config['SESSION_COOKIE_NAME'],cookie.value,domain='attacker.example')
    response=visit(client,'POST',f'/admin/workers/{new_worker}/setup',base_url='http://attacker.example',data=data)
    assert response.status_code==200
    body=fake_gmail['messages'][0][0].get_content()
    assert 'https://intellitask.example/auth/worker-setup#' in body and 'attacker.example' not in body


@pytest.mark.parametrize('base',['http://public.example','https://user:pass@example.com','https://example.com?secret=x',
    'https://example.com#token','https://example.com/subpath','https://example.com:invalid','not a url','https://example.com\\evil'])
def test_invalid_website_address_is_rejected(gmail,base):
    gmail['INTELLITASK_INVITATION_BASE_URL']=base
    with pytest.raises(EmailConfigurationError):email_settings(gmail)


@pytest.mark.parametrize('base',['https://example.com','http://127.0.0.1:5001','http://localhost:5001'])
def test_https_and_local_test_addresses_are_supported(gmail,base):
    gmail['INTELLITASK_INVITATION_BASE_URL']=base
    assert email_settings(gmail)[2]==base


def test_missing_settings_preserve_existing_invitation(app,client,new_worker,gmail,fake_gmail):
    data=email_form(client,new_worker)
    token,expiry=issue_invitation(new_worker,1)
    before=db.session.get(WorkerSetupInvitation,new_worker).token_hash
    app.extensions.pop('intellitask_gmail_credentials',None)
    response=post_email(client,new_worker,data)
    assert response.status_code==422 and b'has not been configured' in response.data
    assert db.session.get(WorkerSetupInvitation,new_worker,populate_existing=True).token_hash==before
    assert not fake_gmail['messages']


@pytest.mark.parametrize('failure',['authentication','network','refused','malformed','redirect'])
def test_delivery_failure_does_not_claim_success_or_change_credentials(app,client,new_worker,gmail,fake_gmail,monkeypatch,failure,caplog):
    secret='provider-secret-that-must-not-be-exposed'
    class BrokenTransport:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):
            if failure=='network':raise OSError(secret)
            status={'authentication':401,'refused':403,'malformed':200,'redirect':302}[failure]
            return SimpleNamespace(status_code=status,json=lambda:{'private':secret})
    monkeypatch.setattr(email_service,'_authorized_session',BrokenTransport)
    response=post_email(client,new_worker,email_form(client,new_worker))
    assert response.status_code==200 and b'Email submission could not be confirmed' in response.data
    assert b'Invitation submitted to Gmail' not in response.data and secret.encode() not in response.data
    assert secret not in caplog.text
    token=re.search(r'id="invitation-code" readonly value="([A-Za-z0-9_-]{43})"',response.get_data(as_text=True)).group(1)
    row=db.session.get(WorkerSetupInvitation,new_worker,populate_existing=True)
    assert row.token_hash==hashlib.sha256(token.encode()).hexdigest() and row.consumed_at is None
    assert db.session.get(OnboardingAgent,new_worker).password_hash==PENDING_PASSWORD


def test_email_reissue_is_throttled_then_replaces_old_link(app,client,new_worker,gmail,fake_gmail):
    data=email_form(client,new_worker)
    assert post_email(client,new_worker,data).status_code==200
    first=db.session.get(WorkerSetupInvitation,new_worker,populate_existing=True).token_hash
    assert post_email(client,new_worker,data).status_code==422
    assert len(fake_gmail['messages'])==1
    assert db.session.get(WorkerSetupInvitation,new_worker,populate_existing=True).token_hash==first
    row=db.session.get(WorkerSetupInvitation,new_worker);row.issued_at=utcnow()-timedelta(minutes=2);db.session.commit()
    assert post_email(client,new_worker,data).status_code==200
    assert len(fake_gmail['messages'])==2
    assert db.session.get(WorkerSetupInvitation,new_worker,populate_existing=True).token_hash!=first


def test_manual_invitation_still_works_without_email_credentials(app,client,new_worker,fake_gmail):
    app.extensions.pop('intellitask_gmail_credentials',None)
    response=post_email(client,new_worker,email_form(client,new_worker,delivery='manual'))
    assert response.status_code==200 and b'No email has been sent' in response.data
    assert not fake_gmail['connections']


def test_get_bad_csrf_and_missing_confirmation_never_send_email(app,client,new_worker,gmail,fake_gmail):
    data=email_form(client,new_worker)
    assert not fake_gmail['connections']
    assert post_email(client,new_worker,{**data,'csrf_token':'invalid'}).status_code==400
    assert post_email(client,new_worker,{**data,'confirm':''}).status_code==422
    assert post_email(client,new_worker,{**data,'delivery':'invented'}).status_code==422
    assert not fake_gmail['connections'] and WorkerSetupInvitation.query.count()==0


def test_completed_accounts_cannot_receive_setup_email(app,client,new_worker,gmail,fake_gmail):
    data=email_form(client,new_worker)
    worker=db.session.get(OnboardingAgent,new_worker);worker.set_password(PASSWORD);worker.account_disabled=False;db.session.commit()
    assert post_email(client,new_worker,data).status_code==409
    assert not fake_gmail['connections']


def test_database_failure_prevents_email(app,client,new_worker,gmail,fake_gmail,monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    data=email_form(client,new_worker)
    def fail():raise SQLAlchemyError('Simulated commit failure')
    with monkeypatch.context() as patch:
        patch.setattr(db.session,'commit',fail)
        assert post_email(client,new_worker,data).status_code==422
    assert not fake_gmail['connections'] and WorkerSetupInvitation.query.count()==0


@pytest.mark.parametrize('fails',[False,True])
def test_local_launcher_uses_existing_installation_and_only_process_credentials(monkeypatch,capsys,fails):
    from pathlib import Path
    import runpy
    import sys
    scripts=Path(__file__).resolve().parents[1]/'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    namespace=runpy.run_path(str(scripts/'run_5001_with_gmail_api.py'),run_name='launcher_test')
    values=namespace['main'].__globals__
    credentials=SimpleNamespace(refresh_token='private-refresh-token')
    monkeypatch.setitem(values,'credential_path',lambda root:Path('fake-encrypted-file'))
    monkeypatch.setitem(values,'load_credentials',lambda path:credentials)
    calls=[]
    fake_app=SimpleNamespace(config={},extensions={})
    def run(**kwargs):
        calls.append(kwargs)
        assert fake_app.extensions['intellitask_gmail_credentials'] is credentials
        if fails:raise RuntimeError('Simulated startup failure')
    fake_app.run=run
    paths=[]
    def load_app(path,run_name):
        paths.append((path,run_name))
        return {'app':fake_app}
    monkeypatch.setattr(runpy,'run_path',load_app)
    if fails:
        with pytest.raises(RuntimeError):namespace['main']()
    else:namespace['main']()
    assert paths[0][0].endswith('run_netease_test.py') and paths[0][1]=='gmail_local_app'
    assert calls==[{'host':'127.0.0.1','port':5001,'debug':False,'use_reloader':False}]
    assert fake_app.config['INTELLITASK_INVITATION_BASE_URL']=='http://127.0.0.1:5001'
    assert 'intellitask_gmail_credentials' not in fake_app.extensions
    assert 'private-refresh-token' not in capsys.readouterr().out


@pytest.mark.parametrize('email',['supervisor@test.com','netease-6376@demo.invalid'])
def test_other_roles_cannot_send_worker_invitations(app,client,new_worker,gmail,fake_gmail,email):
    login(client,email=email)
    response=post_email(client,new_worker,{'confirm':'yes','delivery':'email'})
    assert response.status_code==403 and not fake_gmail['connections']
    assert WorkerSetupInvitation.query.count()==0

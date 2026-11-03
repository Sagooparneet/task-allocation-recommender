from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
from pathlib import Path
import re
import threading
import pytest
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models import OnboardingAgent, IndependentWorkerRegistration, WorkerSetupInvitation, Administrator, WorkerSourceBinding
from app.services.independent_workers import PENDING_PASSWORD
import app.services.worker_setup as setup

PASSWORD = 'my-new-worker-passphrase-123'
pytestmark = pytest.mark.usefixtures('legacy_setup_code')


@pytest.fixture()
def new_worker(app):
    worker = OnboardingAgent(name='Independent Person', email='independent@example.com',
        password_hash=PENDING_PASSWORD, account_disabled=True, availability=False, workload=0)
    db.session.add(worker);db.session.flush()
    db.session.add(IndependentWorkerRegistration(agent_id=worker.id,
        created_by_admin_id=Administrator.query.first().id))
    db.session.commit()
    return worker.id


def visit(client, method, path, **kwargs):
    with client.application.app_context():
        return client.open(path,method=method,**kwargs)


def login(client,email='admin@test.com'):
    return visit(client,'POST','/auth/login',data={'email':email,'password':'password123'})


def invitation(client, worker_id):
    login(client)
    path=f'/admin/workers/{worker_id}/setup'
    assert visit(client,'GET',path).status_code == 200
    with client.session_transaction() as session:
        data={'csrf_token':session['worker_setup_admin_csrf'],'confirm':'yes'}
    response=visit(client,'POST',path,data=data)
    assert response.status_code == 200
    token=re.search(r'id="invitation-code" readonly value="([A-Za-z0-9_-]{43})"',response.get_data(as_text=True)).group(1)
    return token,response


def setup_form(client,token,**changes):
    response=visit(client,'GET','/auth/worker-setup')
    assert response.status_code == 200
    with client.session_transaction() as session:
        data={'csrf_token':session['worker_setup_public_csrf'], 'setup_token':token,
              'email':'independent@example.com','password':PASSWORD,'password_confirm':PASSWORD,
              'action':'complete','verification_code':'123456'}
    data.update(changes)
    return data


def test_issue_and_redeem_preserve_existing_identities_enable_only_new_login(app,client,new_worker):
    old={w.id:(w.email,w.password_hash,w.account_disabled,w.availability,w.workload) for w in OnboardingAgent.query.all() if w.id!=new_worker}
    binding=Path(app.instance_path)/'netease_agent_bindings.json';before=binding.read_bytes()
    token,response=invitation(client,new_worker)
    assert response.headers['Cache-Control']=='no-store, private'
    assert response.headers['Referrer-Policy']=='no-referrer'
    db.session.expire_all()
    row=db.session.get(WorkerSetupInvitation,new_worker)
    assert row.token_hash==hashlib.sha256(token.encode()).hexdigest()
    assert row.expires_at-row.issued_at==timedelta(hours=24)
    assert row.consumed_at is None
    assert db.session.get(OnboardingAgent,new_worker).password_hash==PENDING_PASSWORD
    with client.session_transaction() as session:
        assert token not in str(dict(session))
    assert token.encode() not in visit(client,'GET',f'/admin/workers/{new_worker}/setup').data
    public=app.test_client();data=setup_form(public,token)
    result=visit(public,'POST','/auth/worker-setup',data=data)
    assert result.status_code==302 and result.location.endswith('/auth/login')
    db.session.expire_all()
    worker=db.session.get(OnboardingAgent,new_worker)
    assert not worker.account_disabled and not worker.availability and worker.workload==0
    assert worker.check_password(PASSWORD) and worker.password_hash!=PASSWORD
    assert db.session.get(WorkerSetupInvitation,new_worker).consumed_at is not None
    assert not db.session.get(WorkerSourceBinding,new_worker)
    assert {w.id:(w.email,w.password_hash,w.account_disabled,w.availability,w.workload) for w in OnboardingAgent.query.all() if w.id!=new_worker}==old
    assert binding.read_bytes()==before
    login_response=visit(public,'POST','/auth/login',data={'email':worker.email,'password':PASSWORD})
    assert login_response.status_code==302 and login_response.location.endswith('/agent/dashboard')
    assert visit(public,'GET','/agent/dashboard').status_code==200
    assert visit(client,'POST',f'/admin/workers/{new_worker}/setup').status_code==409


def test_reissue_invalidates_old_invitation_and_replay_cannot_change_password(app,client,new_worker):
    old,_=invitation(client,new_worker);new,_=invitation(client,new_worker)
    assert old!=new
    public=app.test_client()
    response=visit(public,'POST','/auth/worker-setup',data=setup_form(public,old))
    assert response.status_code==422
    assert visit(public,'POST','/auth/worker-setup',data=setup_form(public,new)).status_code==302
    before=db.session.get(OnboardingAgent,new_worker,populate_existing=True).password_hash
    other='another-long-password-456'
    response=visit(public,'POST','/auth/worker-setup',data=setup_form(public,new,password=other,password_confirm=other))
    assert response.status_code==422
    assert db.session.get(OnboardingAgent,new_worker,populate_existing=True).password_hash==before


@pytest.mark.parametrize('case',['expired','used','wrong_email','wrong_token'])
def test_invalid_invitation_does_not_enable_account(app,client,new_worker,case):
    token,_=invitation(client,new_worker)
    row=db.session.get(WorkerSetupInvitation,new_worker,populate_existing=True)
    if case=='expired':
        row.issued_at=setup.utcnow()-timedelta(days=2);row.expires_at=setup.utcnow()-timedelta(days=1)
    if case=='used':row.consumed_at=setup.utcnow()
    db.session.commit()
    public=app.test_client();data=setup_form(public,token)
    if case=='wrong_email':data['email']='different@example.com'
    if case=='wrong_token':data['setup_token']='A'*43
    response=visit(public,'POST','/auth/worker-setup',data=data)
    assert response.status_code==422 and b'invalid, expired, or already used' in response.data
    assert token.encode() not in response.data and PASSWORD.encode() not in response.data
    worker=db.session.get(OnboardingAgent,new_worker,populate_existing=True)
    assert worker.password_hash==PENDING_PASSWORD and worker.account_disabled and not worker.availability


@pytest.mark.parametrize('password,confirmation',[('short','short'),('x'*129,'x'*129),(' '*12,' '*12),(PASSWORD,'different')])
def test_password_validation_does_not_consume_invitation(app,client,new_worker,password,confirmation):
    token,_=invitation(client,new_worker);public=app.test_client()
    response=visit(public,'POST','/auth/worker-setup',data=setup_form(public,token,password=password,password_confirm=confirmation))
    assert response.status_code==422 and b'aria-invalid="true"' in response.data
    assert token.encode() not in response.data and PASSWORD.encode() not in response.data
    assert db.session.get(WorkerSetupInvitation,new_worker,populate_existing=True).consumed_at is None


@pytest.mark.parametrize('email',['supervisor@test.com','netease-6376@demo.invalid'])
def test_invitation_is_admin_only(client,new_worker,email):
    login(client,email)
    assert visit(client,'GET',f'/admin/workers/{new_worker}/setup').status_code==403
    assert visit(client,'POST',f'/admin/workers/{new_worker}/setup').status_code==403
    assert WorkerSetupInvitation.query.count()==0


def test_anonymous_and_bad_csrf_cannot_issue_or_consume(app,client,new_worker):
    path=f'/admin/workers/{new_worker}/setup'
    assert visit(client,'POST',path).status_code==302
    login(client);visit(client,'GET',path)
    assert visit(client,'POST',path,data={'csrf_token':'wrong','confirm':'yes'}).status_code==400
    assert WorkerSetupInvitation.query.count()==0
    token,_=invitation(client,new_worker);public=app.test_client()
    assert visit(public,'POST','/auth/worker-setup',data=setup_form(public,token,csrf_token='wrong')).status_code==400
    assert db.session.get(WorkerSetupInvitation,new_worker,populate_existing=True).consumed_at is None


def test_dataset_and_existing_accounts_cannot_receive_setup(client):
    login(client)
    worker=OnboardingAgent.query.filter_by(email='netease-6376@demo.invalid').one()
    before=worker.password_hash
    assert visit(client,'GET',f'/admin/workers/{worker.id}/setup').status_code==409
    assert visit(client,'POST',f'/admin/workers/{worker.id}/setup').status_code==409
    assert WorkerSetupInvitation.query.count()==0
    db.session.expire_all();assert worker.password_hash==before


def test_signed_in_session_cannot_redeem_another_account(client,new_worker):
    token,_=invitation(client,new_worker)
    assert b'private browser window' in visit(client,'GET','/auth/worker-setup').data
    assert visit(client,'POST','/auth/worker-setup',data={'setup_token':token,'password':PASSWORD}).status_code==403
    assert db.session.get(WorkerSetupInvitation,new_worker,populate_existing=True).consumed_at is None


def test_failed_commit_rolls_back_token_consumption_and_password(app,client,new_worker,monkeypatch):
    token,_=invitation(client,new_worker)
    public=app.test_client();data=setup_form(public,token)
    def fail():raise SQLAlchemyError('Simulated transaction failure')
    with monkeypatch.context() as patch:
        patch.setattr(db.session,'commit',fail)
        assert visit(public,'POST','/auth/worker-setup',data=data).status_code==422
    db.session.expire_all()
    assert db.session.get(WorkerSetupInvitation,new_worker).consumed_at is None
    worker=db.session.get(OnboardingAgent,new_worker)
    assert worker.password_hash==PENDING_PASSWORD and worker.account_disabled


def test_concurrent_redemption_has_exactly_one_winner(app,client,new_worker,monkeypatch):
    token,_=invitation(client,new_worker)
    original_hash=setup.generate_password_hash
    barrier=threading.Barrier(2)
    def hash_then_wait(password):
        result=original_hash(password);barrier.wait(timeout=15);return result
    monkeypatch.setattr(setup,'generate_password_hash',hash_then_wait)
    def attempt(password):
        with app.app_context():
            try:
                setup.redeem_invitation(token,'independent@example.com',password)
                return password
            except setup.SetupUnavailable:
                return None
            finally:
                db.session.remove()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(attempt,[PASSWORD,'another-unique-password-456']))
    winners=[value for value in results if value]
    assert len(winners)==1
    db.session.expire_all()
    assert db.session.get(OnboardingAgent,new_worker).check_password(winners[0])
    assert db.session.get(WorkerSetupInvitation,new_worker).consumed_at is not None


def test_reissue_between_initial_check_and_claim_rejects_stale_token(app,client,new_worker,monkeypatch):
    token,_=invitation(client,new_worker)
    admin_id=Administrator.query.first().id
    original_hash=setup.generate_password_hash
    def replace_before_claim(password):
        setup.issue_invitation(new_worker,admin_id)
        return original_hash(password)
    monkeypatch.setattr(setup,'generate_password_hash',replace_before_claim)
    with pytest.raises(setup.SetupUnavailable):
        setup.redeem_invitation(token,'independent@example.com',PASSWORD)
    db.session.expire_all()
    assert db.session.get(OnboardingAgent,new_worker).password_hash==PENDING_PASSWORD
    assert db.session.get(WorkerSetupInvitation,new_worker).consumed_at is None

from app.models import IndependentWorkerRegistration
from app.services.independent_workers import pending_account_setup
import secrets
from urllib.parse import urlsplit

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import WorkVenue, OnboardingAgent, TaskAssignment, Task, AgentSkill, Skill, Supervisor

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
CITIES = ('Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret')


def require_admin():
    if current_user.role != 'administrator':
        abort(403)


def form_token():
    if 'venue_form_token' not in session:
        session['venue_form_token'] = secrets.token_urlsafe(32)
    return session['venue_form_token']


@admin_bp.route('/dashboard')
@login_required
def dashboard():
    require_admin()
    return render_template('admin/dashboard.html', total=WorkVenue.query.count(),
                           active=WorkVenue.query.filter_by(is_active=True).count())




@admin_bp.route('/supervisors/new', methods=['GET', 'POST'])
@login_required
def new_supervisor():
    require_admin()
    import unicodedata
    from app.services.independent_workers import valid_email, email_in_use
    from app.services.supervisor_setup import PENDING_PASSWORD

    session.setdefault('supervisor_create_csrf_token', secrets.token_urlsafe(32))
    values = {'name': '', 'email': ''}
    errors = {}
    if request.method == 'POST':
        expected = session['supervisor_create_csrf_token']
        supplied = request.form.get('csrf_token', '')
        if not secrets.compare_digest(expected.encode(), supplied.encode()):
            abort(400, description='This form expired. Reload the page and try again.')
        values = {key: request.form.get(key, '').strip() for key in values}
        values['email'] = values['email'].lower()
        name, email = values['name'], values['email']
        if not name or len(name) > 100 or any(unicodedata.category(char).startswith('C') for char in name):
            errors['name'] = 'Enter a name of 1 to 100 characters without hidden formatting characters.'
        if not valid_email(email) or email.startswith('netease-') or email.endswith('.invalid'):
            errors['email'] = "Enter the supervisor's own email address."
        elif email_in_use(email):
            errors['email'] = 'This email address is already used by an account.'
        if not errors:
            record = Supervisor(name=name, email=email, password_hash=PENDING_PASSWORD,
                                account_disabled=True)
            db.session.add(record)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                errors['email'] = 'This email address is already used by an account.'
            else:
                session.pop('supervisor_create_csrf_token', None)
                flash('Supervisor added. Password setup is required before sign-in.', 'success')
                return redirect(url_for('admin.supervisors'))
    return render_template('admin/supervisor_new.html', values=values,
                           errors=errors, csrf_token=session['supervisor_create_csrf_token']), (422 if errors else 200)


@admin_bp.route('/supervisors/<int:supervisor_id>/setup', methods=['GET', 'POST'])
@login_required
def supervisor_setup(supervisor_id):
    from datetime import timedelta
    from sqlalchemy.exc import SQLAlchemyError
    from app.models import SupervisorSetupInvitation
    from app.services.supervisor_setup import issue_invitation, pending_account_setup, utcnow
    from app.services.worker_setup import private_response
    from app.services.invitation_email import (
        email_settings, send_supervisor_setup_email,
        EmailConfigurationError, EmailDeliveryError,
    )

    require_admin()
    record = db.session.get(Supervisor, supervisor_id, populate_existing=True)
    if record is None:
        abort(404)
    if not pending_account_setup(record):
        abort(409, description='Initial setup is only available for pending supervisors.')
    session.setdefault('supervisor_setup_admin_csrf', secrets.token_urlsafe(32))
    errors = {}
    setup_token = None
    expiry = None
    delivery = 'manual'
    email_submitted = False
    email_failed = False
    if request.method == 'POST':
        supplied = request.form.get('csrf_token', '')
        if not secrets.compare_digest(session['supervisor_setup_admin_csrf'].encode(), supplied.encode()):
            abort(400, description='This form expired. Reload the page and try again.')
        if request.form.get('confirm') != 'yes':
            errors['confirm'] = 'Confirm that this invitation is for the registered supervisor.'
        delivery = request.form.get('delivery', 'manual')
        if delivery not in ('manual', 'email'):
            errors['delivery'] = 'Choose how to share this invitation.'
        settings = None
        if not errors and delivery == 'email':
            try:
                settings = email_settings()
            except EmailConfigurationError as exc:
                errors['delivery'] = str(exc)
        if not errors:
            try:
                setup_token, expiry = issue_invitation(supervisor_id, current_user.id,
                    minimum_interval=timedelta(minutes=1) if delivery == 'email' else None)
            except (SQLAlchemyError, OSError, ValueError, TypeError, AttributeError):
                db.session.rollback()
                errors['confirm'] = 'The invitation could not be created. Check that setup is still pending. For email, wait one minute between invitations.'
            else:
                if delivery == 'email':
                    try:
                        send_supervisor_setup_email(record.email, record.name,
                            setup_token, expiry, settings)
                        email_submitted = True
                    except (EmailDeliveryError, EmailConfigurationError):
                        email_failed = True
                        # Keep the committed link available for manual sharing.
                        # A provider error cannot confirm that delivery failed.
    invitation = db.session.get(SupervisorSetupInvitation, supervisor_id, populate_existing=True)
    active = bool(invitation and invitation.consumed_at is None and invitation.expires_at > utcnow())
    return private_response(render_template('admin/supervisor_setup.html', record=record,
        errors=errors, setup_token=setup_token, active_invitation=active,
        setup_path=url_for('auth.supervisor_setup'), delivery=delivery,
        email_submitted=email_submitted, email_failed=email_failed,
        expiry=(expiry + timedelta(hours=3)).strftime('%d %b %Y, %H:%M') if expiry else None,
        csrf_token=session['supervisor_setup_admin_csrf']), 422 if errors else 200)


@admin_bp.route('/supervisors', methods=['GET'])
@login_required
def supervisors():
    require_admin()
    search = request.args.get('q', '').strip()[:100]
    status = request.args.get('status', '')
    query = Supervisor.query
    if search:
        needle = search.lower()
        query = query.filter(db.or_(
            func.lower(Supervisor.name).contains(needle, autoescape=True),
            func.lower(Supervisor.email).contains(needle, autoescape=True)))
    if status in ('active', 'inactive'):
        query = query.filter(Supervisor.account_disabled.is_(status == 'inactive'))
    else:
        status = ''
    page_number = max(1, request.args.get('page', 1, type=int) or 1)
    page = query.order_by(Supervisor.id).paginate(page=page_number, per_page=20, error_out=False)
    ids = [item.id for item in page.items]
    task_counts = dict(db.session.query(Task.supervisor_id, func.count(Task.id))
        .filter(Task.supervisor_id.in_(ids)).group_by(Task.supervisor_id).all()) if ids else {}
    return render_template('admin/supervisors.html', page=page, search=search,
                           status=status, task_counts=task_counts)


@admin_bp.route('/venues')
@login_required
def venues():
    require_admin()
    city = request.args.get('city', '')
    status = request.args.get('status', '')
    query = WorkVenue.query
    if city in CITIES:
        query = query.filter_by(city=city)
    else:
        city = ''
    if status in ('active', 'inactive'):
        query = query.filter_by(is_active=status == 'active')
    else:
        status = ''
    page = query.order_by(WorkVenue.city, WorkVenue.name).paginate(per_page=20, error_out=False)
    return render_template('admin/venues.html', page=page, cities=CITIES, city=city, status=status)


@admin_bp.route('/venues/new', methods=['GET', 'POST'])
@admin_bp.route('/venues/<int:venue_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_venue(venue_id=None):
    require_admin()
    venue = db.session.get(WorkVenue, venue_id) if venue_id is not None else None
    if venue_id is not None and venue is None:
        abort(404)
    fields = ('city', 'name', 'address', 'directions', 'map_url')
    values = {key: (getattr(venue, key) or '') if venue else '' for key in fields}
    values['is_active'] = venue.is_active if venue else True
    errors = {}
    if request.method == 'POST':
        expected = session.get('venue_form_token', '')
        supplied = request.form.get('csrf_token', '')
        if not expected or not secrets.compare_digest(expected.encode('utf-8'), supplied.encode('utf-8')):
            abort(400, description='This form expired. Reload the page and try again.')
        values = {key: request.form.get(key, '').strip() for key in fields}
        values['is_active'] = request.form.get('is_active') == 'on'
        if values['city'] not in CITIES:
            errors['city'] = 'Choose one of the listed cities.'
        for key, limit in (('name', 160), ('address', 300)):
            if not values[key] or len(values[key]) > limit:
                errors[key] = f'Enter a {key} of 1 to {limit} characters.'
        if len(values['directions']) > 2000:
            errors['directions'] = 'Keep directions within 2,000 characters.'
        link = values['map_url']
        if link:
            try:
                parsed = urlsplit(link)
                valid = (parsed.scheme == 'https' and parsed.hostname and not parsed.username
                         and not parsed.password and not any(c.isspace() for c in link)
                         and '\\' not in link and len(link) <= 1000)
            except ValueError:
                valid = False
            if not valid:
                errors['map_url'] = 'Use a full HTTPS map link, without spaces or sign-in details.'
        duplicate = WorkVenue.query.filter(
            WorkVenue.city == values['city'], func.lower(WorkVenue.name) == values['name'].lower())
        if venue:
            duplicate = duplicate.filter(WorkVenue.id != venue.id)
        if duplicate.first():
            errors['name'] = 'A location with this name already exists in this city.'
        if not errors:
            record = venue or WorkVenue()
            for key, value in values.items():
                setattr(record, key, value)
            db.session.add(record)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                errors['name'] = 'This location could not be saved. Check for a duplicate name.'
            else:
                flash('Work location updated.' if venue else 'Work location added.', 'success')
                return redirect(url_for('admin.venues'))
    return render_template('admin/venue_form.html', venue=venue, values=values,
                           errors=errors, cities=CITIES, csrf_token=form_token()), (422 if errors else 200)


@admin_bp.route('/workers')
@login_required
def workers():
    require_admin()
    from sqlalchemy import or_
    from app.services.worker_directory import directory_names
    names = directory_names()
    search = request.args.get('q', '').strip()[:100]
    availability = request.args.get('availability', '')
    query = OnboardingAgent.query
    if search:
        ids = [worker_id for worker_id, name in names.items() if search.casefold() in name.casefold()]
        if search.isascii() and search.isdecimal() and len(search) < 10:
            ids.append(int(search))
        query = query.filter(or_(OnboardingAgent.id.in_(ids),
            func.lower(OnboardingAgent.email).contains(search.lower(), autoescape=True)))
    if availability in ('available', 'unavailable'):
        query = query.filter(OnboardingAgent.availability.is_(availability == 'available'))
    else:
        availability = ''
    page_number = max(1, request.args.get('page', 1, type=int) or 1)
    page = query.order_by(OnboardingAgent.id).paginate(page=page_number, per_page=20, error_out=False)
    ids = [worker.id for worker in page.items]
    active_counts = dict(db.session.query(TaskAssignment.agent_id, func.count(TaskAssignment.id))
        .filter(TaskAssignment.agent_id.in_(ids), TaskAssignment.status != 'Completed')
        .group_by(TaskAssignment.agent_id).all())
    return render_template('admin/workers.html', page=page, names=names,
        active_counts=active_counts, search=search, availability=availability)


@admin_bp.route('/workers/<int:worker_id>')
@login_required
def worker_profile(worker_id):
    require_admin()
    from app.services.worker_directory import directory_names
    from app.services.skill_display_labels import skill_label
    from sqlalchemy.orm import joinedload
    from datetime import timedelta
    worker = db.session.get(OnboardingAgent, worker_id)
    if worker is None:
        abort(404)
    names = directory_names()
    owned = TaskAssignment.query.filter_by(agent_id=worker.id)
    counts = dict(db.session.query(TaskAssignment.status, func.count(TaskAssignment.id))
        .filter(TaskAssignment.agent_id == worker.id).group_by(TaskAssignment.status).all())
    status = request.args.get('status', '')
    if status in ('Assigned', 'In progress', 'Completed'):
        owned = owned.filter_by(status=status)
    else:
        status = ''
    page_number = max(1, request.args.get('page', 1, type=int) or 1)
    page = owned.options(joinedload(TaskAssignment.task)).order_by(TaskAssignment.id.desc()).paginate(
        page=page_number, per_page=10, error_out=False)
    services = sorted({skill_label(name) for name, in db.session.query(Skill.name).join(
        AgentSkill, AgentSkill.skill_id == Skill.id).filter(AgentSkill.agent_id == worker.id).all()})
    times = {item.id: {
        'started': (item.started_at + timedelta(hours=3)).strftime('%d %b %Y, %H:%M') if item.started_at else None,
        'completed': (item.completed_at + timedelta(hours=3)).strftime('%d %b %Y, %H:%M') if item.completed_at else None,
    } for item in page.items}
    return render_template('admin/worker_profile.html', worker=worker, name=names[worker.id],
        services=services, page=page, status=status, counts=counts, times=times,
        independent_registration=db.session.get(IndependentWorkerRegistration, worker.id),
        setup_pending=pending_account_setup(worker),
        total=sum(counts.values()), active=sum(value for key, value in counts.items() if key != 'Completed'))


@admin_bp.route('/workers/<int:worker_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_worker(worker_id):
    require_admin()
    import unicodedata
    from sqlalchemy import update
    from app.services.worker_directory import directory_names
    worker = db.session.get(OnboardingAgent, worker_id, populate_existing=True)
    if worker is None:
        abort(404)
    session.setdefault('worker_edit_csrf_token', secrets.token_urlsafe(32))
    name = directory_names()[worker.id]
    value = name
    original = worker.profile_display_name or ''
    errors = {}
    if request.method == 'POST':
        expected = session.get('worker_edit_csrf_token', '')
        supplied = request.form.get('csrf_token', '')
        if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
            abort(400, description='This form expired. Reload the page and try again.')
        value = request.form.get('display_name', '').strip()
        original = request.form.get('original_display_name', '')
        if not value or len(value) > 100:
            errors['display_name'] = 'Enter a display name of 1 to 100 characters.'
        elif any(unicodedata.category(char).startswith('C') for char in value):
            errors['display_name'] = 'Use a name without control or hidden formatting characters.'
        if not errors:
            previous = OnboardingAgent.profile_display_name.is_(None) if not original else OnboardingAgent.profile_display_name == original
            # Only the presentation field is writable, even if extra fields
            # are submitted. Compare-and-set prevents overwriting a newer edit.
            changed = db.session.execute(update(OnboardingAgent).where(
                OnboardingAgent.id == worker.id, previous
            ).values(profile_display_name=value).execution_options(synchronize_session=False)).rowcount
            if changed != 1:
                db.session.rollback()
                errors['display_name'] = 'This name was changed in another session. Reload this page before saving.'
            else:
                db.session.commit()
                flash('Worker display name updated.', 'success')
                return redirect(url_for('admin.worker_profile', worker_id=worker.id))
    return render_template('admin/worker_edit.html', worker=worker, name=name,
        value=value, original=original, errors=errors,
        csrf_token=session['worker_edit_csrf_token']), (422 if errors else 200)


@admin_bp.route('/workers/<int:worker_id>/availability', methods=['GET', 'POST'])
@login_required
def worker_availability(worker_id):
    require_admin()
    from sqlalchemy import update
    from app.services.worker_directory import directory_names
    worker = db.session.get(OnboardingAgent, worker_id, populate_existing=True)
    if worker is None:
        abort(404)
    session.setdefault('worker_availability_csrf_token', secrets.token_urlsafe(32))
    original = 'unknown' if worker.availability is None else ('available' if worker.availability else 'unavailable')
    value = 'available' if worker.availability else 'unavailable'
    errors = {}
    if request.method == 'POST':
        expected = session['worker_availability_csrf_token']
        supplied = request.form.get('csrf_token', '')
        if not secrets.compare_digest(expected.encode(), supplied.encode()):
            abort(400, description='This form expired. Reload the page and try again.')
        value = request.form.get('availability', '')
        original = request.form.get('original_availability', '')
        if value not in ('available', 'unavailable'):
            errors['availability'] = 'Choose Available or Unavailable.'
        if original not in ('available', 'unavailable', 'unknown'):
            errors['availability'] = 'Reload this page before saving availability.'
        if not errors:
            previous = None if original == 'unknown' else original == 'available'
            changed = db.session.execute(update(OnboardingAgent).where(
                OnboardingAgent.id == worker.id,
                OnboardingAgent.availability.is_(previous),
                OnboardingAgent.account_disabled.is_(False),
            ).values(availability=value == 'available').execution_options(synchronize_session=False)).rowcount
            if changed != 1:
                db.session.rollback()
                errors['availability'] = 'Availability or account status changed. Reload this page before saving.'
            else:
                db.session.commit()
                flash('Availability for new assignments updated.', 'success')
                return redirect(url_for('admin.worker_profile', worker_id=worker.id))
    active = TaskAssignment.query.filter(TaskAssignment.agent_id == worker.id,
                                        TaskAssignment.status != 'Completed').count()
    return render_template('admin/worker_availability.html', worker=worker,
        name=directory_names()[worker.id], active=active, value=value, original=original,
        errors=errors, csrf_token=session['worker_availability_csrf_token']), (422 if errors else 200)


@admin_bp.route('/workers/<int:worker_id>/account-status', methods=['GET', 'POST'])
@login_required
def worker_account_status(worker_id):
    require_admin()
    from sqlalchemy import select, update, exists, or_
    from app.models import Task
    from app.services.worker_directory import directory_names
    worker = db.session.get(OnboardingAgent, worker_id, populate_existing=True)
    if worker is None:
        abort(404)
    if pending_account_setup(worker):
        flash('Account setup is required before this worker can sign in or receive assignments.', 'info')
        return redirect(url_for('admin.worker_profile', worker_id=worker.id))
    session.setdefault('worker_account_csrf_token', secrets.token_urlsafe(32))
    errors = {}
    action = 'reactivate' if worker.account_disabled else 'deactivate'
    # Treat inconsistent or unknown status as unfinished, rather than disabling
    # someone whose work might still require their access.
    unfinished = exists().where(
        TaskAssignment.agent_id == worker_id,
        TaskAssignment.task_id == Task.id,
        or_(TaskAssignment.status.is_(None), TaskAssignment.status != 'Completed',
            Task.status.is_(None), Task.status != 'Completed'))
    if request.method == 'POST':
        supplied = request.form.get('csrf_token', '')
        if not secrets.compare_digest(session['worker_account_csrf_token'].encode(), supplied.encode()):
            abort(400, description='This form expired. Reload the page and try again.')
        action = request.form.get('action', '')
        if action not in ('deactivate', 'reactivate'):
            abort(400)
        if request.form.get('confirm') != 'yes':
            errors['confirm'] = 'Confirm this account change before saving.'
        if not errors:
            # PostgreSQL serializes this with assignment's conditional worker
            # update. Recheck unfinished work AFTER obtaining the worker lock.
            db.session.execute(select(OnboardingAgent.id).where(
                OnboardingAgent.id == worker_id).with_for_update()).scalar_one()
            conditions = [OnboardingAgent.id == worker_id,
                          OnboardingAgent.account_disabled.is_(action == 'reactivate')]
            if action == 'deactivate':
                conditions.append(~unfinished)
            result = db.session.execute(update(OnboardingAgent).where(*conditions).values(
                account_disabled=action == 'deactivate', availability=False
            ).execution_options(synchronize_session=False))
            if result.rowcount != 1:
                db.session.rollback()
                errors['confirm'] = 'This account changed or has unfinished tasks. Reload the profile and check its tasks before trying again.'
            else:
                db.session.commit()
                flash('Worker account deactivated.' if action == 'deactivate' else
                      'Worker account reactivated. Availability remains off until you change it.', 'success')
                return redirect(url_for('admin.worker_profile', worker_id=worker_id))
    blocked = bool(db.session.execute(select(unfinished)).scalar())
    return render_template('admin/worker_account_status.html', worker=worker,
        name=directory_names()[worker_id], action=action, blocked=blocked,
        errors=errors, csrf_token=session['worker_account_csrf_token']), (422 if errors else 200)


@admin_bp.route('/workers/new', methods=['GET', 'POST'])
@login_required
def new_worker():
    require_admin()
    import unicodedata
    from sqlalchemy import null
    from app.services.independent_workers import (
        PENDING_PASSWORD, registration_services, valid_email, email_in_use, require_unbound_identity,
    )
    from app.services.skill_display_labels import skill_label
    services = sorted(registration_services(), key=lambda skill: (skill_label(skill.name), skill.id))
    allowed_ids = {skill.id for skill in services}
    session.setdefault('worker_create_csrf_token', secrets.token_urlsafe(32))
    values = {'name': '', 'email': '', 'city': '', 'confirmed': False}
    selected_ids = set()
    errors = {}
    if request.method == 'POST':
        supplied = request.form.get('csrf_token', '')
        if not secrets.compare_digest(session['worker_create_csrf_token'].encode(), supplied.encode()):
            abort(400, description='This form expired. Reload the page and try again.')
        values = {key: request.form.get(key, '').strip() for key in ('name', 'email', 'city')}
        values['email'] = values['email'].lower()
        values['confirmed'] = request.form.get('confirmed') == 'yes'
        if not values['name'] or len(values['name']) > 100 or any(unicodedata.category(c).startswith('C') for c in values['name']):
            errors['name'] = 'Enter a name of 1 to 100 characters without hidden formatting characters.'
        email = values['email']
        if not valid_email(email) or email.startswith('netease-') or email.endswith('.invalid'):
            errors['email'] = "Enter the worker's own email address, not a demonstration account address."
        elif email_in_use(email):
            errors['email'] = 'This email address is already used by an account.'
        if values['city'] not in CITIES:
            errors['city'] = 'Choose a base city from the list.'
        raw = request.form.getlist('services')
        if raw and len(raw) <= 100 and all(item.isascii() and item.isdecimal() and len(item) <= 10 for item in raw):
            selected_ids = {int(item) for item in raw}
        if not selected_ids or not selected_ids.issubset(allowed_ids):
            errors['services'] = 'Select at least one of the listed services.'
        if not values['confirmed']:
            errors['confirmed'] = "Confirm that you have checked the worker's selected services."
        if not errors:
            worker = OnboardingAgent(name=values['name'], email=email,
                location=values['city'], password_hash=PENDING_PASSWORD,
                availability=False, account_disabled=True, workload=0,
                performance_score=null())
            try:
                db.session.add(worker)
                db.session.flush()
                require_unbound_identity(worker.id)
                db.session.add(IndependentWorkerRegistration(agent_id=worker.id, created_by_admin_id=current_user.id))
                for skill_id in sorted(selected_ids):
                    db.session.add(AgentSkill(agent_id=worker.id, skill_id=skill_id,
                                              proficiency_level='Administrator confirmed'))
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                errors['email'] = 'The worker could not be added. Check that the email is not already in use and try again.'
            except (OSError, ValueError, TypeError, AttributeError):
                db.session.rollback()
                from flask import current_app
                current_app.logger.warning('Independent worker creation refused because identity configuration could not be verified.')
                errors['name'] = 'The worker could not be added safely. Ask the administrator to check the identity configuration.'
            else:
                session.pop('worker_create_csrf_token', None)
                flash('Worker added. Account setup is required before sign-in and assignments.', 'success')
                return redirect(url_for('admin.worker_profile', worker_id=worker.id))
    return render_template('admin/worker_new.html', values=values, selected_ids=selected_ids,
        services=services, cities=CITIES, errors=errors,
        csrf_token=session['worker_create_csrf_token']), (422 if errors else 200)


@admin_bp.route('/workers/<int:worker_id>/setup', methods=['GET', 'POST'])
@login_required
def worker_setup(worker_id):
    from datetime import timedelta
    from sqlalchemy.exc import SQLAlchemyError
    from app.models import WorkerSetupInvitation
    from app.services.worker_directory import directory_names
    from app.services.worker_setup import issue_invitation, private_response, utcnow
    require_admin()
    worker = db.session.get(OnboardingAgent, worker_id, populate_existing=True)
    if worker is None:
        abort(404)
    if not pending_account_setup(worker) or not worker.account_disabled:
        abort(409, description='Initial setup is only available for pending new workers.')
    session.setdefault('worker_setup_admin_csrf', secrets.token_urlsafe(32))
    errors = {}
    setup_token = None
    expiry = None
    delivery = 'manual'
    email_submitted = False
    email_failed = False
    from app.services.invitation_email import email_settings, send_setup_email, EmailConfigurationError, EmailDeliveryError
    if request.method == 'POST':
        supplied = request.form.get('csrf_token', '')
        if not secrets.compare_digest(session['worker_setup_admin_csrf'].encode(), supplied.encode()):
            abort(400, description='This form expired. Reload the page and try again.')
        if request.form.get('confirm') != 'yes':
            errors['confirm'] = 'Confirm that you will share the invitation privately with this worker.'
        delivery = request.form.get('delivery', 'manual')
        if delivery not in ('manual', 'email'):
            errors['delivery'] = 'Choose how to share this invitation.'
        settings = None
        if not errors and delivery == 'email':
            try:
                settings = email_settings()
            except EmailConfigurationError as exc:
                errors['delivery'] = str(exc)
        if not errors:
            try:
                setup_token, expiry = issue_invitation(worker_id, current_user.id,
                    minimum_interval=timedelta(minutes=1) if delivery == 'email' else None)
            except (SQLAlchemyError, OSError, ValueError, TypeError, AttributeError):
                db.session.rollback()
                errors['confirm'] = 'The invitation could not be created. Check that setup is still pending. For email, wait one minute between invitations.'
            else:
                if delivery == 'email':
                    try:
                        send_setup_email(worker.email, worker.profile_display_name or worker.name,
                            setup_token, expiry, settings)
                        email_submitted = True
                    except (EmailDeliveryError, EmailConfigurationError):
                        email_failed = True
                        # The invitation is already committed. Preserve it for manual
                        # sharing; never report a confirmed delivery after an API failure.
    invitation = db.session.get(WorkerSetupInvitation, worker_id, populate_existing=True)
    active = bool(invitation and invitation.consumed_at is None and invitation.expires_at > utcnow())
    return private_response(render_template('admin/worker_setup.html', worker=worker,
        name=directory_names()[worker_id], errors=errors, setup_token=setup_token,
        setup_path=url_for('auth.worker_setup'), active_invitation=active,
        delivery=delivery, email_submitted=email_submitted, email_failed=email_failed,
        expiry=(expiry + timedelta(hours=3)).strftime('%d %b %Y, %H:%M') if expiry else None,
        csrf_token=session['worker_setup_admin_csrf']), 422 if errors else 200)


@admin_bp.route('/supervisors/<int:supervisor_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_supervisor(supervisor_id):
    require_admin()
    import unicodedata
    from sqlalchemy import update
    record = db.session.get(Supervisor, supervisor_id, populate_existing=True)
    if record is None:
        abort(404)
    session.setdefault('supervisor_edit_csrf_token', secrets.token_urlsafe(32))
    value = record.name
    original = record.name
    errors = {}
    if request.method == 'POST':
        expected = session['supervisor_edit_csrf_token']
        supplied = request.form.get('csrf_token', '')
        if not secrets.compare_digest(expected.encode(), supplied.encode()):
            abort(400, description='This form expired. Reload the page and try again.')
        value = request.form.get('name', '').strip()
        original = request.form.get('original_name', '')
        if not value or len(value) > 100:
            errors['name'] = 'Enter a name of 1 to 100 characters.'
        elif any(unicodedata.category(char).startswith('C') for char in value):
            errors['name'] = 'Use a name without control or hidden formatting characters.'
        if not errors:
            changed = db.session.execute(update(Supervisor).where(
                Supervisor.id == supervisor_id, Supervisor.name == original,
            ).values(name=value).execution_options(synchronize_session=False)).rowcount
            if changed != 1:
                db.session.rollback()
                errors['name'] = 'This name changed in another session. Reload before saving.'
            else:
                db.session.commit()
                flash('Supervisor name updated.', 'success')
                return redirect(url_for('admin.supervisors'))
    return render_template('admin/supervisor_edit.html', record=record, value=value,
        original=original, errors=errors, csrf_token=session['supervisor_edit_csrf_token']), (422 if errors else 200)


@admin_bp.route('/supervisors/<int:supervisor_id>/account-status', methods=['GET', 'POST'])
@login_required
def supervisor_account_status(supervisor_id):
    require_admin()
    from sqlalchemy import select, update, exists, or_
    from app.services.supervisor_setup import pending_account_setup
    record = db.session.get(Supervisor, supervisor_id, populate_existing=True)
    if record is None:
        abort(404)
    if pending_account_setup(record):
        abort(409, description='Password setup is required before changing this account status.')
    session.setdefault('supervisor_account_csrf_token', secrets.token_urlsafe(32))
    action = 'reactivate' if record.account_disabled else 'deactivate'
    errors = {}
    unfinished = exists().where(
        Task.supervisor_id == supervisor_id,
        or_(Task.status.is_(None), Task.status != 'Completed'))
    if request.method == 'POST':
        supplied = request.form.get('csrf_token', '')
        if not secrets.compare_digest(session['supervisor_account_csrf_token'].encode(), supplied.encode()):
            abort(400, description='This form expired. Reload the page and try again.')
        action = request.form.get('action', '')
        if action not in ('deactivate', 'reactivate'):
            abort(400)
        if request.form.get('confirm') != 'yes':
            errors['confirm'] = 'Confirm this account change before saving.'
        if not errors:
            db.session.execute(select(Supervisor.id).where(
                Supervisor.id == supervisor_id).with_for_update()).scalar_one()
            conditions = [Supervisor.id == supervisor_id,
                          Supervisor.account_disabled.is_(action == 'reactivate')]
            if action == 'deactivate':
                conditions.append(~unfinished)
            changed = db.session.execute(update(Supervisor).where(*conditions).values(
                account_disabled=action == 'deactivate').execution_options(synchronize_session=False)).rowcount
            if changed != 1:
                db.session.rollback()
                errors['confirm'] = 'This account changed or has unfinished tasks. Reload and check its tasks.'
            else:
                db.session.commit()
                flash('Supervisor account reactivated.' if action == 'reactivate' else
                      'Supervisor account deactivated.', 'success')
                return redirect(url_for('admin.supervisors'))
    blocked = bool(db.session.execute(select(unfinished)).scalar()) if action == 'deactivate' else False
    return render_template('admin/supervisor_account_status.html', record=record,
        action=action, blocked=blocked, errors=errors,
        csrf_token=session['supervisor_account_csrf_token']), (422 if errors else 200)

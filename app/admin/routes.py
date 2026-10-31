import secrets
from urllib.parse import urlsplit

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import WorkVenue, OnboardingAgent, TaskAssignment, Task, AgentSkill, Skill

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

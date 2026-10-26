import secrets
from urllib.parse import urlsplit

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import WorkVenue

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

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.models import Supervisor, OnboardingAgent, Administrator


auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth"
)


def redirect_by_role(user):
    if user.role == "supervisor":
        return redirect(url_for("supervisor.dashboard"))

    if user.role == "agent":
        return redirect(url_for("agent.dashboard"))

    if user.role == "administrator":
        return redirect(url_for("admin.dashboard"))

    return redirect(url_for("home"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect_by_role(current_user)

    errors = {}
    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email:
            errors['email'] = 'Enter your email address.'
        if not password:
            errors['password'] = 'Enter your password.'
        if errors:
            return render_template('auth/login.html', errors=errors)

        user = Supervisor.query.filter_by(email=email).first()

        if not user:
            user = OnboardingAgent.query.filter_by(email=email).first()

        if not user:
            user = Administrator.query.filter_by(email=email).first()

        if user and user.is_active and user.check_password(password):

            login_user(user)

            flash(
                "Login successful.",
                "success"
            )

            return redirect_by_role(user)

        errors['__all__'] = 'Invalid email or password.'

    return render_template(
        "auth/login.html", errors=errors
    )


@auth_bp.route("/logout")
@login_required
def logout():

    logout_user()

    flash(
        "You have been logged out.",
        "info"
    )

    return redirect(
        url_for("auth.login")
    )


@auth_bp.route('/worker-setup', methods=['GET', 'POST'])
def worker_setup():
    import secrets
    from flask import abort, session
    from sqlalchemy.exc import SQLAlchemyError
    from app.services.independent_workers import valid_email
    from app.services.worker_setup import redeem_invitation, private_response, SetupUnavailable, INVALID_INVITATION
    if current_user.is_authenticated:
        return private_response(render_template('auth/worker_setup.html', signed_in=True,
            errors={}, email='', csrf_token=''), 403 if request.method == 'POST' else 200)
    session.setdefault('worker_setup_public_csrf', secrets.token_urlsafe(32))
    errors = {}
    email = ''
    if request.method == 'POST':
        supplied = request.form.get('csrf_token', '')
        if not secrets.compare_digest(session['worker_setup_public_csrf'].encode(), supplied.encode()):
            abort(400, description='This form expired. Reload the setup page and try again.')
        token = request.form.get('setup_token', '')
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirmation = request.form.get('password_confirm', '')
        if not valid_email(email):
            errors['email'] = 'Enter the email address your administrator registered.'
        if not token:
            errors['setup_token'] = 'Open your invitation link or paste your setup code.'
        if not 12 <= len(password) <= 128 or not password.strip():
            errors['password'] = 'Choose a password of 12 to 128 characters.'
        if password != confirmation:
            errors['password_confirm'] = 'Enter the same password again.'
        if not errors:
            try:
                redeem_invitation(token, email, password)
            except (SetupUnavailable, OSError, ValueError, TypeError, AttributeError):
                errors['setup_token'] = INVALID_INVITATION
            except SQLAlchemyError:
                errors['setup_token'] = 'Setup could not be completed. Try again or contact your administrator.'
            else:
                session.clear()
                flash('Your password is set. Sign in with your email and new password.', 'success')
                return private_response(redirect(url_for('auth.login')))
    # Passwords and tokens never return in response HTML or the session cookie.
    return private_response(render_template('auth/worker_setup.html', signed_in=False,
        errors=errors, email=email, csrf_token=session['worker_setup_public_csrf']), 422 if errors else 200)


@auth_bp.route('/supervisor-setup', methods=['GET', 'POST'])
def supervisor_setup():
    import secrets
    from flask import abort, session
    from sqlalchemy.exc import SQLAlchemyError
    from app.services.independent_workers import valid_email
    from app.services.worker_setup import private_response
    from app.services.supervisor_setup import redeem_invitation, SetupUnavailable, INVALID_INVITATION

    if current_user.is_authenticated:
        return private_response(render_template('auth/supervisor_setup.html', signed_in=True,
            errors={}, email='', csrf_token=''), 403 if request.method == 'POST' else 200)
    session.setdefault('supervisor_setup_public_csrf', secrets.token_urlsafe(32))
    errors = {}
    email = ''
    if request.method == 'POST':
        supplied = request.form.get('csrf_token', '')
        if not secrets.compare_digest(session['supervisor_setup_public_csrf'].encode(), supplied.encode()):
            abort(400, description='This form expired. Reload the setup page and try again.')
        token = request.form.get('setup_token', '')
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirmation = request.form.get('password_confirm', '')
        if not valid_email(email):
            errors['email'] = 'Enter the email address your administrator registered.'
        if not token:
            errors['setup_token'] = 'Open your invitation link or paste your setup code.'
        if not 12 <= len(password) <= 128 or not password.strip():
            errors['password'] = 'Choose a password of 12 to 128 characters.'
        if password != confirmation:
            errors['password_confirm'] = 'Enter the same password again.'
        if not errors:
            try:
                redeem_invitation(token, email, password)
            except (SetupUnavailable, OSError, ValueError, TypeError, AttributeError):
                errors['setup_token'] = INVALID_INVITATION
            except SQLAlchemyError:
                errors['setup_token'] = 'Setup could not be completed. Try again or contact your administrator.'
            else:
                session.clear()
                flash('Your password is set. Sign in with your email and new password.', 'success')
                return private_response(redirect(url_for('auth.login')))
    return private_response(render_template('auth/supervisor_setup.html', signed_in=False,
        errors=errors, email=email, csrf_token=session['supervisor_setup_public_csrf']), 422 if errors else 200)

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.models import Supervisor, OnboardingAgent, Administrator
from app.auth.google_signin import google_signin_available, start as google_start, callback as google_callback


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
            return render_template('auth/login.html', errors=errors,
                                   google_signin_available=google_signin_available())

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
        "auth/login.html", errors=errors,
        google_signin_available=google_signin_available()
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


from app.auth.password_reset_pages import (
    forgot_password_page, forgot_password_sent_page, reset_password_page,
)

auth_bp.add_url_rule('/forgot-password', 'forgot_password', forgot_password_page, methods=['GET', 'POST'])
auth_bp.add_url_rule('/forgot-password/sent', 'forgot_password_sent', forgot_password_sent_page)
auth_bp.add_url_rule('/reset-password', 'reset_password', reset_password_page, methods=['GET', 'POST'])
auth_bp.add_url_rule('/google', 'google_start', google_start, methods=['GET'])
auth_bp.add_url_rule('/google/callback', 'google_callback', google_callback, methods=['GET'])


@auth_bp.route('/worker-setup', methods=['GET', 'POST'])
def worker_setup():
    from app.auth.setup_flow import first_time_setup
    return first_time_setup('worker')


@auth_bp.route('/supervisor-setup', methods=['GET', 'POST'])
def supervisor_setup():
    from app.auth.setup_flow import first_time_setup
    return first_time_setup('supervisor')

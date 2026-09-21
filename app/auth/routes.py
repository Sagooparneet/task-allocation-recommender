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

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = Supervisor.query.filter_by(email=email).first()

        if not user:
            user = OnboardingAgent.query.filter_by(email=email).first()

        if not user:
            user = Administrator.query.filter_by(email=email).first()

        if user and user.check_password(password):

            login_user(user)

            flash(
                "Login successful.",
                "success"
            )

            return redirect_by_role(user)

        flash(
            "Invalid email or password.",
            "danger"
        )

    return render_template(
        "auth/login.html"
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
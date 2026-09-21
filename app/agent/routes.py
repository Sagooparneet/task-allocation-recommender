from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user


agent_bp = Blueprint(
    "agent",
    __name__,
    url_prefix="/agent"
)


@agent_bp.route("/dashboard")
@login_required
def dashboard():

    if current_user.role != "agent":
        return redirect(url_for("home"))

    return render_template(
        "agent/dashboard.html"
    )
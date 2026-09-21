from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user


supervisor_bp = Blueprint(
    "supervisor",
    __name__,
    url_prefix="/supervisor"
)


@supervisor_bp.route("/dashboard")
@login_required
def dashboard():

    if current_user.role != "supervisor":
        return redirect(url_for("home"))

    return render_template(
        "supervisor/dashboard.html"
    )
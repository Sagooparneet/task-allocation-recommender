from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin"
)


@admin_bp.route("/dashboard")
@login_required
def dashboard():

    if current_user.role != "administrator":
        return redirect(url_for("home"))

    return render_template(
        "admin/dashboard.html"
    )
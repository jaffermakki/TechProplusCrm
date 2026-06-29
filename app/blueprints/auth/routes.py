from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import csrf
from app.models.staff import Staff
from app.models.audit import AuditLog

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET"])
def pin_login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    staff_list = Staff.query.filter_by(active=True).order_by(Staff.name).all()
    return render_template("auth/pin_login.html", staff_list=staff_list)


@bp.route("/login/<int:staff_id>", methods=["POST"])
@csrf.exempt
def submit_pin(staff_id):
    """AJAX endpoint: the numeric keypad in the UI posts the typed PIN here."""
    pin = (request.json or {}).get("pin", "") if request.is_json else request.form.get("pin", "")
    member = Staff.query.get_or_404(staff_id)

    if not member.active:
        return jsonify({"ok": False, "error": "This staff account is disabled."}), 403

    if member.check_pin(pin):
        login_user(member)
        AuditLog.record("login", f"{member.name} signed in", staff_id=member.id)
        return jsonify({"ok": True, "redirect": url_for("dashboard.index")})

    return jsonify({"ok": False, "error": "Incorrect PIN."}), 401


@bp.route("/logout")
@login_required
def logout():
    AuditLog.record("logout", f"{current_user.name} signed out")
    logout_user()
    flash("Signed out.", "blue")
    return redirect(url_for("auth.pin_login"))

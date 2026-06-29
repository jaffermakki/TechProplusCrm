from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.staff import Staff, ROLES
from app.models.location import Location
from app.models.audit import AuditLog
from app.utils.decorators import role_required

bp = Blueprint("staff", __name__, url_prefix="/staff")


@bp.route("/")
@login_required
@role_required("owner", "manager")
def index():
    staff_list = Staff.query.order_by(Staff.name).all()
    return render_template("staff/index.html", staff_list=staff_list, roles=ROLES)


@bp.route("/add", methods=["GET", "POST"])
@login_required
@role_required("owner", "manager")
def add_staff():
    locations = Location.query.filter_by(active=True).order_by(Location.name).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        pin = request.form.get("pin", "").strip()
        role = request.form.get("role", "staff")
        location_id = request.form.get("location_id") or None

        if len(pin) < 4:
            flash("PIN must be at least 4 digits.", "amber")
            return render_template("staff/add.html", roles=ROLES, locations=locations)

        member = Staff(name=name, role=role, location_id=location_id)
        member.set_pin(pin)
        db.session.add(member)
        db.session.commit()
        AuditLog.record("staff_created", f"{name} ({role})")
        flash(f"{name} added.", "green")
        return redirect(url_for("staff.index"))

    return render_template("staff/add.html", roles=ROLES, locations=locations)


@bp.route("/<int:staff_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("owner", "manager")
def edit_staff(staff_id):
    member = Staff.query.get_or_404(staff_id)
    locations = Location.query.filter_by(active=True).order_by(Location.name).all()

    if request.method == "POST":
        member.name = request.form.get("name", "").strip()
        member.role = request.form.get("role", member.role)
        member.location_id = request.form.get("location_id") or None
        new_pin = request.form.get("pin", "").strip()
        if new_pin:
            if len(new_pin) < 4:
                flash("PIN must be at least 4 digits.", "amber")
                return render_template("staff/edit.html", member=member, roles=ROLES, locations=locations)
            member.set_pin(new_pin)
        db.session.commit()
        flash("Staff member updated.", "green")
        return redirect(url_for("staff.index"))

    return render_template("staff/edit.html", member=member, roles=ROLES, locations=locations)


@bp.route("/<int:staff_id>/toggle-active", methods=["POST"])
@login_required
@role_required("owner", "manager")
def toggle_active(staff_id):
    member = Staff.query.get_or_404(staff_id)
    if member.id == current_user.id:
        flash("You can't disable your own account.", "amber")
        return redirect(url_for("staff.index"))

    member.active = not member.active
    db.session.commit()
    AuditLog.record("staff_toggled", f"{member.name} active={member.active}")
    return redirect(url_for("staff.index"))

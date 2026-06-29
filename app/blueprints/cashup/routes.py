from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.cash_session import CashSession
from app.models.audit import AuditLog

bp = Blueprint("cashup", __name__, url_prefix="/cashup")


@bp.route("/")
@login_required
def index():
    open_session = CashSession.query.filter_by(staff_id=current_user.id, closed_at=None).first()
    recent_sessions = CashSession.query.order_by(CashSession.opened_at.desc()).limit(15).all()
    return render_template("cashup/index.html", open_session=open_session, recent_sessions=recent_sessions)


@bp.route("/open", methods=["POST"])
@login_required
def open_session():
    existing = CashSession.query.filter_by(staff_id=current_user.id, closed_at=None).first()
    if existing:
        flash("You already have an open cash session.", "amber")
        return redirect(url_for("cashup.index"))

    opening_float = float(request.form.get("opening_float", 0) or 0)
    cash_session = CashSession(staff_id=current_user.id, opening_float=opening_float)
    db.session.add(cash_session)
    db.session.commit()
    AuditLog.record("cash_session_opened", f"Opening float ${opening_float:.2f}")
    flash("Cash session opened.", "green")
    return redirect(url_for("cashup.index"))


@bp.route("/<int:session_id>/close", methods=["POST"])
@login_required
def close_session(session_id):
    cash_session = CashSession.query.get_or_404(session_id)
    if cash_session.closed_at is not None:
        flash("This session is already closed.", "amber")
        return redirect(url_for("cashup.index"))

    counted_cash = float(request.form.get("counted_cash", 0) or 0)
    expected_cash = float(cash_session.opening_float) + cash_session.cash_sales_total()

    cash_session.counted_cash = counted_cash
    cash_session.expected_cash = expected_cash
    cash_session.variance = round(counted_cash - expected_cash, 2)
    cash_session.notes = request.form.get("notes", "").strip()
    cash_session.closed_at = datetime.utcnow()
    db.session.commit()

    AuditLog.record(
        "cash_session_closed",
        f"Session #{cash_session.id} variance ${cash_session.variance:.2f}",
    )
    flash(f"Session closed. Variance: ${cash_session.variance:.2f}", "blue")
    return redirect(url_for("cashup.index"))

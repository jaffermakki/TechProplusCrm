from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.repair import Repair, STATUS_ORDER, STATUS_LABELS
from app.models.customer import Customer
from app.models.staff import Staff
from app.models.audit import AuditLog
from app.services.invoicing import complete_sale, CartError
from app.services.repairs import (
    create_repair,
    advance_status,
    save_costs,
    add_part_by_sku,
    warranty_alerts_for_customer,
    CostRequiredError,
    PartNotFoundError,
    InsufficientPartStockError,
)

bp = Blueprint("repairs", __name__, url_prefix="/repairs")


@bp.route("/")
@login_required
def kanban():
    q = request.args.get("q", "").strip()
    query = Repair.query.join(Customer)
    if q:
        query = query.filter(
            db.or_(Customer.name.ilike(f"%{q}%"), Repair.device.ilike(f"%{q}%"), Customer.phone.ilike(f"%{q}%"), db.cast(Repair.ticket_no, db.String).ilike(f"%{q}%"))
        )
    repairs = query.order_by(Repair.created_at.desc()).all()

    columns = {status: [] for status in STATUS_ORDER}
    for r in repairs:
        columns.setdefault(r.status, []).append(r)

    return render_template(
        "repairs/kanban.html",
        columns=columns,
        status_order=STATUS_ORDER,
        status_labels=STATUS_LABELS,
        q=q,
    )


@bp.route("/customer-lookup")
@login_required
def customer_lookup():
    """AJAX endpoint for the new-repair form: looks up a customer by phone and
    returns their info plus any active warranty alerts, matching the original's
    lookupRepairCustomer() behavior."""
    from flask import jsonify

    phone = request.args.get("phone", "").strip()
    customer = Customer.query.filter_by(phone=phone).first() if phone else None
    if not customer:
        return jsonify({"found": False})

    alerts = warranty_alerts_for_customer(customer)
    return jsonify({
        "found": True,
        "id": customer.id,
        "name": customer.name,
        "loyalty_points": customer.loyalty_points_balance,
        "warranty_alerts": [
            {
                "ticket_no": a["repair"].ticket_no,
                "device": a["repair"].device,
                "issue": a["repair"].issue,
                "days_remaining": a["days_remaining"],
                "expires_at": a["expires_at"].strftime("%b %d, %Y") if a["expires_at"] else "",
            }
            for a in alerts
        ],
    })


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_repair():
    technicians = Staff.query.filter_by(active=True).order_by(Staff.name).all()

    if request.method == "POST":
        customer_id = request.form.get("customer_id")
        if not customer_id:
            customer = Customer(
                name=request.form.get("customer_name", "").strip(),
                phone=request.form.get("customer_phone", "").strip(),
                email=request.form.get("customer_email", "").strip(),
            )
            db.session.add(customer)
            db.session.flush()
            customer_id = customer.id
        else:
            customer = Customer.query.get(customer_id)

        promised_by_raw = request.form.get("promised_by", "").strip()
        promised_by = datetime.strptime(promised_by_raw, "%Y-%m-%d").date() if promised_by_raw else None
        estimated_cost_raw = request.form.get("estimated_cost", "").strip()
        estimated_cost = float(estimated_cost_raw) if estimated_cost_raw else None
        technician_id = request.form.get("technician_id") or None

        repair = create_repair(
            customer=customer,
            device=request.form.get("device", "").strip(),
            issue=request.form.get("issue", "").strip(),
            description=request.form.get("description", "").strip(),
            estimated_cost=estimated_cost,
            promised_by=promised_by,
            warranty_days=int(request.form.get("warranty_days", 90) or 90),
            technician_id=technician_id,
            location_id=current_user.location_id,
        )
        AuditLog.record("repair_created", f"Ticket #{repair.ticket_no} for {repair.device}")
        flash(f"Repair ticket #{repair.ticket_no} created.", "green")
        return redirect(url_for("repairs.detail", repair_id=repair.id))

    customers = Customer.query.order_by(Customer.name).all()
    return render_template("repairs/new.html", customers=customers, technicians=technicians)


@bp.route("/<int:repair_id>")
@login_required
def detail(repair_id):
    repair = Repair.query.get_or_404(repair_id)
    technicians = Staff.query.filter_by(active=True).order_by(Staff.name).all()
    history = repair.status_history.order_by(db.desc("created_at")).all()
    return render_template(
        "repairs/detail.html",
        repair=repair,
        status_order=STATUS_ORDER,
        status_labels=STATUS_LABELS,
        technicians=technicians,
        history=history,
    )


@bp.route("/<int:repair_id>/advance", methods=["POST"])
@login_required
def advance(repair_id):
    repair = Repair.query.get_or_404(repair_id)
    next_status = request.form.get("status")
    note = request.form.get("note", "").strip()
    force = bool(request.form.get("force"))

    if next_status not in STATUS_ORDER:
        return redirect(request.referrer or url_for("repairs.kanban"))

    try:
        advance_status(repair, next_status, note=note, force=force)
    except CostRequiredError as exc:
        # Re-show the detail page with a confirmation prompt instead of silently
        # blocking - matches the original's confirm() dialog UX.
        flash(str(exc) + " Tick the box below and submit again to confirm.", "amber")
        return redirect(url_for("repairs.detail", repair_id=repair.id, confirm_status=next_status))

    AuditLog.record("repair_status_change", f"Ticket #{repair.ticket_no} -> {next_status}")
    flash(f"Ticket #{repair.ticket_no} moved to {STATUS_LABELS.get(next_status, next_status)}.", "green")
    return redirect(request.referrer or url_for("repairs.kanban"))


@bp.route("/<int:repair_id>/costs", methods=["POST"])
@login_required
def save_costs_route(repair_id):
    repair = Repair.query.get_or_404(repair_id)

    def parse(field):
        raw = request.form.get(field, "").strip()
        return float(raw) if raw else None

    save_costs(
        repair,
        estimated_cost=parse("estimated_cost"),
        approved_cost=parse("approved_cost"),
        final_cost=parse("final_cost"),
    )
    flash("Repair costs updated.", "green")
    return redirect(url_for("repairs.detail", repair_id=repair.id))


@bp.route("/<int:repair_id>/assign", methods=["POST"])
@login_required
def assign_technician(repair_id):
    repair = Repair.query.get_or_404(repair_id)
    repair.technician_id = request.form.get("technician_id") or None
    db.session.commit()
    flash("Technician assigned.", "green")
    return redirect(url_for("repairs.detail", repair_id=repair.id))


@bp.route("/<int:repair_id>/promised", methods=["POST"])
@login_required
def set_promised_date(repair_id):
    repair = Repair.query.get_or_404(repair_id)
    raw = request.form.get("promised_by", "").strip()
    repair.promised_by = datetime.strptime(raw, "%Y-%m-%d").date() if raw else None
    db.session.commit()
    flash("Promised date updated.", "green")
    return redirect(url_for("repairs.detail", repair_id=repair.id))


@bp.route("/<int:repair_id>/parts", methods=["POST"])
@login_required
def add_part(repair_id):
    repair = Repair.query.get_or_404(repair_id)
    sku = request.form.get("sku", "").strip()
    qty = int(request.form.get("qty", 1) or 1)

    try:
        product = add_part_by_sku(repair, sku, qty, staff_id=current_user.id)
    except (PartNotFoundError, InsufficientPartStockError, ValueError) as exc:
        flash(str(exc), "red")
        return redirect(url_for("repairs.detail", repair_id=repair.id))

    AuditLog.record("repair_part_added", f"Ticket #{repair.ticket_no}: {qty}x {product.sku}")
    flash(f"Added {qty}x {product.name}.", "green")
    return redirect(url_for("repairs.detail", repair_id=repair.id))


@bp.route("/<int:repair_id>/invoice", methods=["POST"])
@login_required
def generate_invoice(repair_id):
    repair = Repair.query.get_or_404(repair_id)

    # Single line item using the cost waterfall, matching the original's
    # generateRepairInvoice() exactly - not separate parts/labor lines.
    cart_lines = [{
        "description": f"Repair: {repair.device} — {repair.issue or 'service'} (#{repair.ticket_no})",
        "qty": 1,
        "unit_price": repair.billable_cost,
    }]

    try:
        invoice, _change_due = complete_sale(
            cart_lines=cart_lines,
            staff=current_user,
            customer=repair.customer,
            payment_method=request.form.get("payment_method", "cash"),
        )
    except CartError as exc:
        flash(str(exc), "red")
        return redirect(url_for("repairs.detail", repair_id=repair.id))

    invoice.type = "repair"
    repair.invoice_id = invoice.id
    db.session.commit()
    AuditLog.record("repair_invoiced", f"Ticket #{repair.ticket_no} -> Invoice {invoice.invoice_number}")
    flash(f"Repair invoiced as {invoice.invoice_number}.", "green")
    return redirect(url_for("pos.receipt", invoice_id=invoice.id))

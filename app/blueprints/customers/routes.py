from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.customer import Customer, StoreCreditLedger, LoyaltyLedger
from app.models.audit import AuditLog
from app.services.loyalty import issue_store_credit, InsufficientBalanceError

bp = Blueprint("customers", __name__, url_prefix="/customers")


@bp.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    query = Customer.query
    if q:
        query = query.filter(db.or_(Customer.name.ilike(f"%{q}%"), Customer.phone.ilike(f"%{q}%")))
    customers = query.order_by(Customer.name).all()
    return render_template("customers/index.html", customers=customers, q=q)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_customer():
    if request.method == "POST":
        customer = Customer(
            name=request.form.get("name", "").strip(),
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(customer)
        db.session.commit()
        AuditLog.record("customer_created", customer.name)
        flash("Customer added.", "green")
        return redirect(url_for("customers.detail", customer_id=customer.id))
    return render_template("customers/add.html")


@bp.route("/<int:customer_id>")
@login_required
def detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    invoices = customer.invoices.order_by(db.desc("created_at")).limit(20).all()
    repairs = customer.repairs.order_by(db.desc("created_at")).limit(20).all()
    store_credit_history = customer.store_credit_entries.order_by(db.desc("created_at")).limit(20).all()
    loyalty_history = customer.loyalty_entries.order_by(db.desc("created_at")).limit(20).all()
    return render_template(
        "customers/detail.html",
        customer=customer,
        invoices=invoices,
        repairs=repairs,
        store_credit_history=store_credit_history,
        loyalty_history=loyalty_history,
    )


@bp.route("/<int:customer_id>/notes", methods=["POST"])
@login_required
def save_notes(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    customer.notes = request.form.get("notes", "").strip()
    db.session.commit()
    flash("Notes saved.", "green")
    return redirect(url_for("customers.detail", customer_id=customer.id))


@bp.route("/<int:customer_id>/issue-credit", methods=["POST"])
@login_required
def issue_credit(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    amount = float(request.form.get("amount", 0) or 0)
    reason = request.form.get("reason", "Manual credit").strip()

    if amount <= 0:
        flash("Enter a positive amount.", "amber")
    else:
        issue_store_credit(customer, amount, reason=reason, staff_id=current_user.id)
        AuditLog.record("store_credit_issued", f"{customer.name} +${amount:.2f} ({reason})")
        flash(f"${amount:.2f} store credit issued to {customer.name}.", "green")

    return redirect(url_for("customers.detail", customer_id=customer.id))

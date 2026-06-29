from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.settings import ShopSettings, CA_PROVINCES
from app.models.location import Location
from app.models.audit import AuditLog
from app.utils.decorators import role_required

bp = Blueprint("settings", __name__, url_prefix="/settings")

VALID_TABS = ["shop", "locations", "tax", "invoice", "loyalty", "email", "sms", "danger"]


@bp.route("/")
@bp.route("/<tab>")
@login_required
@role_required("owner", "manager")
def index(tab="shop"):
    if tab not in VALID_TABS:
        tab = "shop"
    settings = ShopSettings.get()
    locations = Location.query.order_by(Location.name).all()
    return render_template("settings/index.html", settings=settings, tab=tab, provinces=CA_PROVINCES, locations=locations)


@bp.route("/locations/add", methods=["POST"])
@login_required
@role_required("owner", "manager")
def add_location():
    name = request.form.get("name", "").strip()
    address = request.form.get("address", "").strip()
    if not name:
        flash("Location name is required.", "amber")
        return redirect(url_for("settings.index", tab="locations"))

    loc = Location(name=name, address=address)
    db.session.add(loc)
    db.session.commit()
    AuditLog.record("location_created", name)
    flash(f"Location '{name}' added.", "green")
    return redirect(url_for("settings.index", tab="locations"))


@bp.route("/locations/<int:location_id>/toggle-active", methods=["POST"])
@login_required
@role_required("owner", "manager")
def toggle_location_active(location_id):
    loc = Location.query.get_or_404(location_id)
    loc.active = not loc.active
    db.session.commit()
    return redirect(url_for("settings.index", tab="locations"))


@bp.route("/shop", methods=["POST"])
@login_required
@role_required("owner", "manager")
def save_shop():
    settings = ShopSettings.get()
    settings.shop_name = request.form.get("shop_name", "").strip()
    settings.address = request.form.get("address", "").strip()
    settings.phone = request.form.get("phone", "").strip()
    db.session.commit()
    flash("Shop details saved.", "green")
    return redirect(url_for("settings.index", tab="shop"))


@bp.route("/tax", methods=["POST"])
@login_required
@role_required("owner", "manager")
def save_tax():
    settings = ShopSettings.get()
    settings.province = request.form.get("province", "ON")
    settings.currency = request.form.get("currency", "$")
    settings.tax_inclusive_pricing = bool(request.form.get("tax_inclusive_pricing"))
    db.session.commit()
    flash("Tax settings saved.", "green")
    return redirect(url_for("settings.index", tab="tax"))


@bp.route("/invoice", methods=["POST"])
@login_required
@role_required("owner", "manager")
def save_invoice():
    settings = ShopSettings.get()
    settings.invoice_prefix = request.form.get("invoice_prefix", "INV").strip().upper()
    settings.invoice_footer_note = request.form.get("invoice_footer_note", "").strip()
    db.session.commit()
    flash("Invoice settings saved.", "green")
    return redirect(url_for("settings.index", tab="invoice"))


@bp.route("/loyalty", methods=["POST"])
@login_required
@role_required("owner", "manager")
def save_loyalty():
    settings = ShopSettings.get()
    settings.loyalty_enabled = bool(request.form.get("loyalty_enabled"))
    settings.loyalty_points_per_dollar = float(request.form.get("loyalty_points_per_dollar", 1) or 1)
    settings.loyalty_points_redeem_rate = float(request.form.get("loyalty_points_redeem_rate", 100) or 100)
    db.session.commit()
    flash("Loyalty settings saved.", "green")
    return redirect(url_for("settings.index", tab="loyalty"))


@bp.route("/loyalty/issue-credit", methods=["POST"])
@login_required
@role_required("owner", "manager")
def manual_issue_credit():
    """Port of manualIssueCredit(): looks up the customer by phone number, matching the
    quick-issue box on the original Settings > Loyalty tab."""
    from app.services.loyalty import issue_store_credit_by_phone, CustomerNotFoundError

    phone = request.form.get("phone", "").strip()
    amount = request.form.get("amount", "").strip()

    try:
        amount_val = float(amount)
        if amount_val <= 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid amount.", "amber")
        return redirect(url_for("settings.index", tab="loyalty"))

    try:
        entry, customer = issue_store_credit_by_phone(phone, amount_val, staff_id=current_user.id)
    except CustomerNotFoundError:
        flash("No customer found with that phone number.", "red")
        return redirect(url_for("settings.index", tab="loyalty"))

    AuditLog.record("store_credit_issued", f"{customer.name} +${amount_val:.2f} (manual, by {current_user.name})")
    flash(f"${amount_val:.2f} store credit issued to {customer.name}.", "green")
    return redirect(url_for("settings.index", tab="loyalty"))


@bp.route("/email", methods=["POST"])
@login_required
@role_required("owner", "manager")
def save_email():
    settings = ShopSettings.get()
    settings.email_receipts_enabled = bool(request.form.get("email_receipts_enabled"))
    db.session.commit()
    flash("Email settings saved.", "green")
    return redirect(url_for("settings.index", tab="email"))


@bp.route("/sms", methods=["POST"])
@login_required
@role_required("owner", "manager")
def save_sms():
    settings = ShopSettings.get()
    settings.sms_enabled = bool(request.form.get("sms_enabled"))
    settings.sms_ready_template = request.form.get("sms_ready_template", "").strip()
    db.session.commit()
    flash("SMS settings saved.", "green")
    return redirect(url_for("settings.index", tab="sms"))


@bp.route("/danger/clear-data", methods=["POST"])
@login_required
@role_required("owner")
def clear_data():
    confirm = request.form.get("confirm_text", "")
    if confirm != "DELETE EVERYTHING":
        flash('Type "DELETE EVERYTHING" exactly to confirm.', "red")
        return redirect(url_for("settings.index", tab="danger"))

    from app.models import (
        Invoice, InvoiceItem, Refund, RefundItem, Repair, RepairPart, RepairPhoto,
        Product, StockAdjustment, Customer, StoreCreditLedger, LoyaltyLedger,
        HeldCart, HeldCartItem, CashSession,
    )

    for model in [RefundItem, Refund, InvoiceItem, Invoice, RepairPart, RepairPhoto, Repair,
                  StockAdjustment, Product, StoreCreditLedger, LoyaltyLedger, Customer,
                  HeldCartItem, HeldCart, CashSession]:
        model.query.delete()
    db.session.commit()

    AuditLog.record("DANGER_clear_all_data", f"by {current_user.name}")
    flash("All transactional data cleared. Staff and settings were kept.", "amber")
    return redirect(url_for("settings.index", tab="danger"))

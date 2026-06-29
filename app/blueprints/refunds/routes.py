from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.invoice import Invoice, InvoiceItem, Refund, RefundItem
from app.models.product import Product, StockAdjustment
from app.models.audit import AuditLog

bp = Blueprint("refunds", __name__, url_prefix="/refunds")


@bp.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    invoice = None
    if q:
        invoice = Invoice.query.filter_by(invoice_number=q.strip().upper()).first()
        if not invoice:
            flash("No invoice found with that number.", "amber")

    recent_refunds = Refund.query.order_by(Refund.created_at.desc()).limit(15).all()
    return render_template("refunds/index.html", q=q, invoice=invoice, recent_refunds=recent_refunds)


@bp.route("/<int:invoice_id>/process", methods=["POST"])
@login_required
def process_refund(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    restock = bool(request.form.get("restock"))
    reason = request.form.get("reason", "").strip()

    refund_total = 0.0
    refund = Refund(invoice_id=invoice.id, staff_id=current_user.id, amount=0, reason=reason, restock=restock)
    db.session.add(refund)
    db.session.flush()

    for item in invoice.items:
        qty_key = f"refund_qty_{item.id}"
        qty = int(request.form.get(qty_key, 0) or 0)
        if qty <= 0:
            continue
        qty = min(qty, item.qty)
        amount = round(float(item.unit_price) * qty, 2)
        refund_total += amount

        db.session.add(RefundItem(refund_id=refund.id, invoice_item_id=item.id, qty=qty, amount=amount))

        if restock and item.product_id:
            product = Product.query.get(item.product_id)
            if product:
                # Restock back to the location where the original sale happened -
                # not a flat catalog-wide number, since stock is now per-location.
                stock_row = product.stock_at(invoice.location_id)
                if stock_row is not None:
                    stock_row.qty_on_hand += qty
                    db.session.add(
                        StockAdjustment(product_id=product.id, location_id=invoice.location_id, staff_id=current_user.id, delta=qty, reason=f"Refund on {invoice.invoice_number}")
                    )

    if refund_total <= 0:
        db.session.rollback()
        flash("Select at least one item/quantity to refund.", "amber")
        return redirect(url_for("refunds.index", q=invoice.invoice_number))

    refund.amount = refund_total
    db.session.commit()
    AuditLog.record("refund_processed", f"${refund_total:.2f} on {invoice.invoice_number}")
    flash(f"Refunded ${refund_total:.2f} on {invoice.invoice_number}.", "green")
    return redirect(url_for("refunds.index", q=invoice.invoice_number))

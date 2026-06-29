from flask import Blueprint, request, jsonify, url_for
from flask_login import login_required

from app.models.customer import Customer
from app.models.repair import Repair
from app.models.invoice import Invoice
from app.models.product import Product

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/search")
@login_required
def global_search():
    """Port of globalUnifiedSearch() - searches customers, repairs, invoices, products at once."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])

    results = []

    for c in Customer.query.filter(
        (Customer.name.ilike(f"%{q}%")) | (Customer.phone.ilike(f"%{q}%"))
    ).limit(5):
        results.append({"type": "customer", "label": c.name, "sub": c.phone, "url": url_for("customers.detail", customer_id=c.id)})

    for r in Repair.query.join(Customer).filter(
        (Repair.device.ilike(f"%{q}%")) | (Customer.name.ilike(f"%{q}%"))
    ).limit(5):
        results.append({"type": "repair", "label": f"{r.device} — {r.customer.name}", "sub": r.status_label, "url": url_for("repairs.detail", repair_id=r.id)})

    for inv in Invoice.query.filter(Invoice.invoice_number.ilike(f"%{q}%")).limit(5):
        results.append({"type": "invoice", "label": inv.invoice_number, "sub": f"${inv.total:.2f}", "url": url_for("pos.receipt", invoice_id=inv.id)})

    for p in Product.query.filter(
        (Product.name.ilike(f"%{q}%")) | (Product.sku.ilike(f"%{q}%"))
    ).limit(5):
        results.append({"type": "product", "label": p.name, "sub": p.sku, "url": url_for("inventory.index", q=p.sku)})

    return jsonify(results)

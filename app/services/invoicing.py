"""Port of calcTotals/completeSale from the original POS module.

This is the highest-risk-of-bugs piece to port (per ARCHITECTURE.md), so it is kept as a
single, well-tested entry point: `complete_sale(...)`. Every write (invoice, items, stock
deduction, loyalty earn, store credit redemption) happens inside one DB transaction - if
anything fails, the whole sale rolls back instead of leaving inventory or ledgers half-updated.

Loyalty math matches the original exactly (see services/loyalty.py for the full rationale):
- Redeeming points is locked to whole multiples of `loyalty_points_redeem_rate` (default 100).
  Requesting an amount that isn't a clean multiple rounds DOWN, it never rejects outright,
  matching `Math.floor(requested / rate) * rate` in the original.
- Dollar value of redeemed points = points / rate, not points * some per-point price.
- Points earned = floor(final_total * points_per_dollar), calculated on the truly final
  total (after tax, after store credit applied) - matching where completeSale() in the
  original calls this, which is after `total` is fully computed.
"""
from app.extensions import db
from app.models.product import Product, StockAdjustment
from app.models.invoice import Invoice, InvoiceItem
from app.models.settings import ShopSettings
from app.services.tax import calc_canadian_tax
from app.services.loyalty import (
    earn_loyalty_points,
    redeem_points_at_pos,
    redeem_store_credit,
    max_redeemable_points,
    points_to_dollar_value,
    InsufficientBalanceError,
)
from app.utils.ids import next_invoice_number


class CartError(Exception):
    pass


def calc_cart_totals(cart_lines, settings: ShopSettings, loyalty_points_redeemed=0, store_credit_used=0, customer=None):
    """cart_lines: list of {"product": Product, "qty": int} OR {"description", "qty", "unit_price"} for
    ad-hoc/repair lines. Returns a dict matching what the checkout screen needs to display.

    loyalty_points_redeemed is the REQUESTED amount - it gets floored to the nearest clean
    multiple of the redeem rate before being applied, exactly like the original POS screen.
    """
    subtotal = 0.0
    for line in cart_lines:
        if "product" in line and line["product"] is not None:
            unit_price = float(line["product"].price)
        else:
            unit_price = float(line.get("unit_price", 0))
        subtotal += unit_price * int(line["qty"])

    points_to_apply = 0
    loyalty_discount = 0.0
    if loyalty_points_redeemed and customer:
        rate = int(settings.loyalty_points_redeem_rate) if settings.loyalty_points_redeem_rate else 0
        if rate > 0:
            requested = int(loyalty_points_redeemed)
            floored = (requested // rate) * rate
            points_to_apply = min(floored, max_redeemable_points(customer, settings))
            loyalty_discount = points_to_dollar_value(points_to_apply, settings)

    taxable = max(subtotal - loyalty_discount, 0)
    tax = calc_canadian_tax(taxable, settings.province)

    total_before_credit = float(tax["grand_total"])
    store_credit_used = min(float(store_credit_used), total_before_credit)
    if customer:
        store_credit_used = min(store_credit_used, customer.store_credit_balance)
    final_total = round(total_before_credit - store_credit_used, 2)

    return {
        "subtotal": round(subtotal, 2),
        "loyalty_points_applied": points_to_apply,
        "loyalty_discount": loyalty_discount,
        "taxable": taxable,
        "gst": float(tax["gst"]),
        "pst": float(tax["pst"]),
        "hst": float(tax["hst"]),
        "tax_total": float(tax["total_tax"]),
        "store_credit_used": round(store_credit_used, 2),
        "total": final_total,
    }


def complete_sale(
    *,
    cart_lines,
    staff,
    customer=None,
    payment_method="cash",
    loyalty_points_redeemed=0,
    store_credit_used=0,
    cash_session=None,
    tendered=None,
    split_payment=None,
):
    """cart_lines: list of dicts, each either:
        {"product": Product, "qty": int}                       (inventory item)
        {"description": str, "qty": int, "unit_price": float}   (ad-hoc / repair line)

    tendered: amount of cash physically handed over (for change calculation) - optional.
    split_payment: optional {"method": str, "amount": float} for a second payment method
        covering part of the total (e.g. $20 cash + rest on card), matching the original's
        split-tender support at checkout.

    Returns (Invoice, change_due: float).

    If cash_session is not explicitly passed, the staff member's currently open cash
    session (if any) is attached automatically - this is what cash-up variance
    calculations key off of, so cash sales must always be linked to a session.
    """
    if not cart_lines:
        raise CartError("Cart is empty")

    if cash_session is None:
        from app.models.cash_session import CashSession

        cash_session = CashSession.query.filter_by(staff_id=staff.id, closed_at=None).first()

    settings = ShopSettings.get()

    # Validate stock up front so we fail before writing anything. Stock is checked
    # against the staff member's own location, not the combined total across shops.
    has_inventory_items = any(line.get("product") is not None for line in cart_lines)
    if has_inventory_items and staff.location_id is None:
        raise CartError("This staff account has no location assigned - ask an owner/manager to set one in Staff settings before selling inventory items.")

    for line in cart_lines:
        product = line.get("product")
        if product is not None:
            available = product.qty_at(staff.location_id)
            if available < line["qty"]:
                raise CartError(f"Not enough stock for {product.name} at your location (have {available}, need {line['qty']})")

    if loyalty_points_redeemed and not customer:
        raise CartError("Cannot redeem loyalty points without a customer attached")
    if store_credit_used and not customer:
        raise CartError("Cannot use store credit without a customer attached")

    totals = calc_cart_totals(
        cart_lines,
        settings,
        loyalty_points_redeemed=loyalty_points_redeemed,
        store_credit_used=store_credit_used,
        customer=customer,
    )

    final_payment_method = payment_method
    if split_payment and split_payment.get("method") and float(split_payment.get("amount", 0) or 0) > 0:
        final_payment_method = f"{payment_method}+{split_payment['method']}"

    change_due = 0.0
    if tendered is not None:
        tendered = float(tendered)
        if tendered < totals["total"]:
            raise CartError("Tendered amount is less than the total")
        change_due = round(tendered - totals["total"], 2)

    invoice = Invoice(
        invoice_number=next_invoice_number(),
        type="sale",
        customer_id=customer.id if customer else None,
        staff_id=staff.id,
        subtotal=totals["subtotal"],
        gst_amount=totals["gst"],
        pst_amount=totals["pst"],
        hst_amount=totals["hst"],
        loyalty_discount=totals["loyalty_discount"],
        store_credit_used=totals["store_credit_used"],
        total=totals["total"],
        payment_method=final_payment_method,
        cash_session_id=cash_session.id if cash_session else None,
        location_id=staff.location_id,
    )
    db.session.add(invoice)
    db.session.flush()  # get invoice.id without committing yet

    for line in cart_lines:
        product = line.get("product")
        if product is not None:
            item = InvoiceItem(
                invoice_id=invoice.id,
                product_id=product.id,
                description=product.name,
                qty=line["qty"],
                unit_price=product.price,
            )
            stock_row = product.stock_at(staff.location_id)
            stock_row.qty_on_hand -= line["qty"]
            db.session.add(StockAdjustment(
                product_id=product.id,
                location_id=staff.location_id,
                staff_id=staff.id,
                delta=-line["qty"],
                reason=f"Sale {invoice.invoice_number}",
            ))
        else:
            item = InvoiceItem(
                invoice_id=invoice.id,
                description=line["description"],
                qty=line["qty"],
                unit_price=line["unit_price"],
            )
        db.session.add(item)

    if customer:
        if totals["loyalty_points_applied"] > 0:
            from app.models.customer import LoyaltyLedger

            db.session.add(LoyaltyLedger(
                customer_id=customer.id,
                points=-totals["loyalty_points_applied"],
                reason=f"Redeemed on {invoice.invoice_number}",
                invoice_id=invoice.id,
            ))
        if totals["store_credit_used"] > 0:
            redeem_store_credit(customer, totals["store_credit_used"], reason=f"Used on {invoice.invoice_number}", invoice_id=invoice.id)

        # Points are earned on the truly final total, after tax and after store credit -
        # matching completeSale()'s `ptsEarned = Math.floor(total * settings.pointsPerDollar)`
        earn_loyalty_points(customer, totals["total"], settings, reason=f"Earned on {invoice.invoice_number}", invoice_id=invoice.id)

        # Lifetime spend + last visit tracking (customer.spent / customer.lastVisit in the original)
        from datetime import datetime

        customer.spent = float(customer.spent or 0) + totals["total"]
        customer.last_visit = datetime.utcnow()
        db.session.add(customer)

    db.session.commit()
    return invoice, change_due

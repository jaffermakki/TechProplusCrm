"""Loyalty & store credit - ported to match the original app's exact mechanics.

Key behaviors carried over from the original JS (these are not arbitrary choices -
they were reverse-engineered from the real source):

1. REDEMPTION IS LOCKED TO WHOLE MULTIPLES of `points_redeem_rate` (default 100).
   A customer with 250 points can redeem 100 or 200, never 150 or 37. The original's
   redeemPointsAtPOS() does: `Math.floor(requested / rate) * rate`. We do the same -
   round down to the nearest clean multiple rather than silently accepting partial
   amounts the original would have refused.

2. DOLLAR VALUE = points / points_redeem_rate (NOT points * some per-point rate).
   With the default rate of 100, 100 points = $1.00, 250 points (rounded down to 200
   redeemable) = $2.00. The settings field is literally labeled "Points Needed for
   $1 Credit" - editing it changes the denominator, not a multiplier.

3. POINTS EARNED use floor(), not round(), and are calculated on the FINAL invoice
   total (after tax, after any discounts) - not the pre-tax subtotal.

4. Manually issuing store credit (e.g. from Settings) is looked up by PHONE NUMBER,
   matching the original's manualIssueCredit(), and produces a synthetic record_number
   (e.g. "SC-A1B2C3") so it's visible in transaction/audit history the same way the
   original logged a STORE_CREDIT_ISSUED pseudo-invoice - without needing a real
   Invoice row, since no sale occurred.

Both ledgers remain append-only (see models/customer.py) - balances are always derived
by summing, never cached, so they stay auditable and recomputable.
"""
import uuid
from app.extensions import db
from app.models.customer import Customer, StoreCreditLedger, LoyaltyLedger


class InsufficientBalanceError(Exception):
    pass


class CustomerNotFoundError(Exception):
    pass


def _generate_record_number() -> str:
    """Port of: 'SC-' + uid().slice(3,9).toUpperCase()"""
    return "SC-" + uuid.uuid4().hex[:6].upper()


def issue_store_credit(customer, amount, reason="", staff_id=None, invoice_id=None):
    """Issue store credit to a customer. If not tied to an invoice (a manual issue),
    a synthetic record_number is generated so it shows up in transaction history."""
    amount = float(amount)
    if amount <= 0:
        raise ValueError("Store credit issue amount must be positive")

    entry = StoreCreditLedger(
        customer_id=customer.id,
        amount=amount,
        reason=reason,
        staff_id=staff_id,
        invoice_id=invoice_id,
        record_number=None if invoice_id else _generate_record_number(),
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def issue_store_credit_by_phone(phone, amount, reason="Manual issue by staff", staff_id=None):
    """Port of manualIssueCredit(): looks up the customer by phone number rather than
    ID - this is the workflow used on the Settings > Loyalty tab's quick-issue box."""
    phone = (phone or "").strip()
    customer = Customer.query.filter_by(phone=phone).first()
    if not customer:
        raise CustomerNotFoundError(f"No customer found with phone number {phone}")
    return issue_store_credit(customer, amount, reason=reason, staff_id=staff_id), customer


def redeem_store_credit(customer, amount, reason="", staff_id=None, invoice_id=None):
    amount = float(amount)
    if amount <= 0:
        raise ValueError("Store credit redeem amount must be positive")
    if customer.store_credit_balance < amount:
        raise InsufficientBalanceError(
            f"{customer.name} only has {customer.store_credit_balance:.2f} in store credit"
        )
    entry = StoreCreditLedger(
        customer_id=customer.id, amount=-amount, reason=reason, staff_id=staff_id, invoice_id=invoice_id
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def earn_loyalty_points(customer, total_after_tax, settings, reason="Purchase", invoice_id=None):
    """Port of: ptsEarned = Math.floor(total * settings.pointsPerDollar)
    IMPORTANT: this floors, it does not round, and the input is the FINAL total
    (after tax/discounts), matching exactly where the original calls this in completeSale()."""
    if not settings.loyalty_enabled:
        return None
    points = int(float(total_after_tax) * float(settings.loyalty_points_per_dollar))
    if points <= 0:
        return None
    entry = LoyaltyLedger(customer_id=customer.id, points=points, reason=reason, invoice_id=invoice_id)
    db.session.add(entry)
    db.session.commit()
    return entry


def max_redeemable_points(customer, settings) -> int:
    """The largest amount the customer could redeem, rounded DOWN to a clean multiple
    of points_redeem_rate. Port of:
        Math.floor(posCustomer.points / settings.pointsRedeemRate) * settings.pointsRedeemRate
    """
    rate = int(settings.loyalty_points_redeem_rate)
    if rate <= 0:
        return 0
    return (customer.loyalty_points_balance // rate) * rate


def points_to_dollar_value(points, settings) -> float:
    """Port of: dollarValue = points / settings.pointsRedeemRate"""
    rate = float(settings.loyalty_points_redeem_rate)
    if rate <= 0:
        return 0.0
    return round(float(points) / rate, 2)


def redeem_points_at_pos(customer, requested_points, settings, reason="Redeemed at POS", invoice_id=None):
    """Port of redeemPointsAtPOS(): the requested amount is rounded DOWN to the nearest
    clean multiple of points_redeem_rate before being applied - matching:
        pts = Math.floor(parseInt(use) / rate) * rate
    Returns (loyalty_ledger_entry, dollar_value_applied, points_actually_redeemed).
    Raises if even the floored amount is <= 0 or exceeds the customer's balance."""
    rate = int(settings.loyalty_points_redeem_rate)
    requested_points = int(requested_points)
    pts = (requested_points // rate) * rate if rate > 0 else 0

    if pts <= 0:
        raise ValueError(f"Enter at least {rate} points (redemption must be in multiples of {rate})")
    if pts > customer.loyalty_points_balance:
        raise InsufficientBalanceError(f"{customer.name} only has {customer.loyalty_points_balance} points")

    dollar_value = points_to_dollar_value(pts, settings)
    entry = LoyaltyLedger(customer_id=customer.id, points=-pts, reason=reason, invoice_id=invoice_id)
    db.session.add(entry)
    db.session.commit()
    return entry, dollar_value, pts


def redeem_loyalty_as_credit(customer, points, settings, staff_id=None):
    """Port of redeemLoyaltyAsCredit(): converts points directly into store credit at
    dollarValue = points / pointsRedeemRate, in one atomic operation. Unlike POS
    redemption this does NOT floor to a clean multiple - the original function takes
    the exact points value passed in (typically from a staff-entered prompt)."""
    points = int(points)
    if points <= 0:
        raise ValueError("Points must be positive")
    if customer.loyalty_points_balance < points:
        raise InsufficientBalanceError(f"{customer.name} only has {customer.loyalty_points_balance} points")

    dollar_value = points_to_dollar_value(points, settings)

    loyalty_entry = LoyaltyLedger(customer_id=customer.id, points=-points, reason="Converted to store credit")
    credit_entry = StoreCreditLedger(
        customer_id=customer.id,
        amount=dollar_value,
        reason=f"Converted from {points} loyalty points",
        staff_id=staff_id,
        record_number=_generate_record_number(),
    )
    db.session.add(loyalty_entry)
    db.session.add(credit_entry)
    db.session.commit()
    return credit_entry

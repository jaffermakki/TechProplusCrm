"""Repair ticket business logic - ported to match the original's exact mechanics.

Key behaviors carried over from the original JS:
1. Ticket numbers are sequential across ALL repairs (not per-location), starting at
   1001, matching `Math.max(...repairs.map(r=>r.ticketNo))+1`.
2. Moving a repair to COMPLETED without an approved or final cost set requires
   explicit confirmation (the original used a JS confirm() dialog) - callers must
   pass force=True to proceed without one set, otherwise a CostRequiredError is
   raised so the UI can show a confirmation prompt.
3. Adding a part looks the product up by SKU, deducts stock at the repair's
   location immediately, and merges quantities if the same SKU is added twice -
   matching addRepairPart() exactly.
4. The warranty check (used when creating a new repair for an existing customer)
   surfaces any of that customer's previous repairs still within their warranty
   window, with days remaining and expiry date - so staff can ask "is this a
   warranty return?" before opening a new paid ticket.
"""
from datetime import datetime
from app.extensions import db
from app.models.repair import Repair, RepairPart, RepairStatusHistory
from app.models.product import Product, StockAdjustment
from app.models.customer import Customer


class CostRequiredError(Exception):
    """Raised when advancing to COMPLETED without a cost set and force=False."""
    pass


class PartNotFoundError(Exception):
    pass


class InsufficientPartStockError(Exception):
    pass


def next_ticket_no() -> int:
    """Port of: Math.max(...repairs.map(r=>r.ticketNo))+1, starting at 1001."""
    highest = db.session.query(db.func.max(Repair.ticket_no)).scalar()
    return (highest + 1) if highest else 1001


def create_repair(*, customer, device, issue="", description="", estimated_cost=None,
                   promised_by=None, warranty_days=90, technician_id=None, location_id=None):
    repair = Repair(
        ticket_no=next_ticket_no(),
        customer_id=customer.id,
        device=device,
        issue=issue,
        description=description,
        estimated_cost=estimated_cost,
        promised_by=promised_by,
        warranty_days=warranty_days or 90,
        technician_id=technician_id,
        location_id=location_id,
        status="RECEIVED",
    )
    db.session.add(repair)
    db.session.flush()
    db.session.add(RepairStatusHistory(repair_id=repair.id, status="RECEIVED", note="Ticket created"))
    db.session.commit()
    return repair


def advance_status(repair: Repair, new_status: str, note: str = "", force: bool = False):
    """Port of advanceRepair(): raises CostRequiredError if moving to COMPLETED with
    no approved/final cost set and force is False, so the caller can show a
    confirmation prompt (matching the original's `confirm()` dialog) and retry with
    force=True if the staff member proceeds anyway."""
    if new_status == "COMPLETED" and not repair.approved_cost and not repair.final_cost and not force:
        raise CostRequiredError("No approved or final cost has been set for this repair. Mark as completed anyway?")

    repair.status = new_status
    repair.updated_at = datetime.utcnow()
    db.session.add(RepairStatusHistory(repair_id=repair.id, status=new_status, note=note))
    db.session.commit()
    return repair


def save_costs(repair: Repair, *, estimated_cost=None, approved_cost=None, final_cost=None):
    repair.estimated_cost = estimated_cost
    repair.approved_cost = approved_cost
    repair.final_cost = final_cost
    db.session.commit()
    return repair


def add_part_by_sku(repair: Repair, sku: str, qty: int = 1, staff_id=None):
    """Port of addRepairPart(): looks up the product by SKU, deducts stock at the
    repair's location, and merges with an existing RepairPart row for the same SKU
    rather than creating a duplicate line."""
    sku = (sku or "").strip().upper()
    if not sku:
        raise ValueError("Enter a part SKU")

    product = Product.query.filter(db.func.upper(Product.sku) == sku).first()
    if not product:
        raise PartNotFoundError(f'No product with SKU "{sku}"')

    available = product.qty_at(repair.location_id)
    if available < qty:
        raise InsufficientPartStockError(f"Only {available} of {product.name} in stock at this location")

    stock_row = product.stock_at(repair.location_id)
    stock_row.qty_on_hand -= qty
    db.session.add(StockAdjustment(
        product_id=product.id,
        location_id=repair.location_id,
        staff_id=staff_id,
        delta=-qty,
        reason=f"Used on repair #{repair.ticket_no}",
    ))

    existing = repair.parts.filter_by(product_id=product.id).first()
    if existing:
        existing.qty += qty
    else:
        db.session.add(RepairPart(repair_id=repair.id, product_id=product.id, description=product.name, qty=qty, unit_cost=product.cost))

    db.session.commit()
    return product


def warranty_alerts_for_customer(customer: Customer):
    """Port of the warranty check shown when looking up a customer for a new repair.
    Returns a list of dicts for any of the customer's previous repairs still within
    their warranty window: {"repair": Repair, "days_remaining": int, "expires_at": datetime}.
    """
    alerts = []
    candidates = Repair.query.filter(
        Repair.customer_id == customer.id,
        Repair.status.in_(["COMPLETED", "COLLECTED"]),
    ).all()

    for r in candidates:
        if r.is_under_warranty:
            alerts.append({
                "repair": r,
                "days_remaining": r.warranty_days_remaining,
                "expires_at": r.warranty_expires_at,
            })

    return alerts

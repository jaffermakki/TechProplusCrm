from datetime import datetime
from app.extensions import db


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40), default="")
    email = db.Column(db.String(160), default="")
    notes = db.Column(db.Text, default="")
    spent = db.Column(db.Numeric(10, 2), nullable=False, default=0)  # lifetime total spend
    last_visit = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoices = db.relationship("Invoice", backref="customer", lazy="dynamic")
    repairs = db.relationship("Repair", backref="customer", lazy="dynamic")
    store_credit_entries = db.relationship("StoreCreditLedger", backref="customer", lazy="dynamic")
    loyalty_entries = db.relationship("LoyaltyLedger", backref="customer", lazy="dynamic")

    @property
    def store_credit_balance(self):
        total = db.session.query(db.func.coalesce(db.func.sum(StoreCreditLedger.amount), 0)).filter(
            StoreCreditLedger.customer_id == self.id
        ).scalar()
        return float(total or 0)

    @property
    def loyalty_points_balance(self):
        total = db.session.query(db.func.coalesce(db.func.sum(LoyaltyLedger.points), 0)).filter(
            LoyaltyLedger.customer_id == self.id
        ).scalar()
        return int(total or 0)

    def __repr__(self):
        return f"<Customer {self.name}>"


class StoreCreditLedger(db.Model):
    """Append-only ledger. Positive amount = issued, negative = redeemed.
    customer.store_credit_balance is always derived by summing this table - never trust
    a cached balance column, this *is* the source of truth.

    When credit is manually issued (not from a POS sale), a synthetic record_number is
    generated (e.g. "SC-A1B2C3") so it shows up in transaction history/reports the same
    way the original app logged a STORE_CREDIT_ISSUED invoice - without needing a real
    Invoice row, since no sale actually occurred.
    """

    __tablename__ = "store_credit_ledger"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    reason = db.Column(db.String(255), default="")
    record_number = db.Column(db.String(40), nullable=True)  # e.g. "SC-A1B2C3" for manual issues
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"))
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class LoyaltyLedger(db.Model):
    """Append-only ledger. Positive points = earned, negative = redeemed."""

    __tablename__ = "loyalty_ledger"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), default="")
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

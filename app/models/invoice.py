from datetime import datetime
from app.extensions import db

INVOICE_TYPE_SALE = "sale"
INVOICE_TYPE_REPAIR = "repair"

PAYMENT_METHODS = ["cash", "debit", "credit", "store_credit", "mixed"]


class Invoice(db.Model):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(40), unique=True, nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False, default=INVOICE_TYPE_SALE)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)

    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    gst_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    pst_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    hst_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    loyalty_discount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    store_credit_used = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    payment_method = db.Column(db.String(20), default="cash")
    voided = db.Column(db.Boolean, default=False)
    cash_session_id = db.Column(db.Integer, db.ForeignKey("cash_sessions.id"), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("InvoiceItem", backref="invoice", lazy="dynamic", cascade="all, delete-orphan")
    refunds = db.relationship("Refund", backref="invoice", lazy="dynamic")
    repairs = db.relationship("Repair", backref="invoice", lazy="dynamic", foreign_keys="Repair.invoice_id")

    @property
    def tax_total(self):
        return float(self.gst_amount or 0) + float(self.pst_amount or 0) + float(self.hst_amount or 0)

    @property
    def total_refunded(self):
        total = db.session.query(db.func.coalesce(db.func.sum(Refund.amount), 0)).filter(
            Refund.invoice_id == self.id
        ).scalar()
        return float(total or 0)

    def __repr__(self):
        return f"<Invoice {self.invoice_number} ${self.total}>"


class InvoiceItem(db.Model):
    """Normalizes what the original JS kept as an in-memory `cart` array on the invoice."""

    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repairs.id"), nullable=True)
    description = db.Column(db.String(200), nullable=False)
    qty = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    @property
    def line_total(self):
        return float(self.unit_price or 0) * (self.qty or 0)


class Refund(db.Model):
    __tablename__ = "refunds"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    reason = db.Column(db.String(255), default="")
    restock = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("RefundItem", backref="refund", lazy="dynamic", cascade="all, delete-orphan")


class RefundItem(db.Model):
    __tablename__ = "refund_items"

    id = db.Column(db.Integer, primary_key=True)
    refund_id = db.Column(db.Integer, db.ForeignKey("refunds.id"), nullable=False)
    invoice_item_id = db.Column(db.Integer, db.ForeignKey("invoice_items.id"), nullable=False)
    qty = db.Column(db.Integer, nullable=False, default=1)
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)

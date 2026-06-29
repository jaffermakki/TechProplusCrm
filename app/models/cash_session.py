from datetime import datetime
from app.extensions import db


class CashSession(db.Model):
    __tablename__ = "cash_sessions"

    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)
    opening_float = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    counted_cash = db.Column(db.Numeric(10, 2), nullable=True)
    expected_cash = db.Column(db.Numeric(10, 2), nullable=True)
    variance = db.Column(db.Numeric(10, 2), nullable=True)
    notes = db.Column(db.Text, default="")
    opened_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    invoices = db.relationship("Invoice", backref="cash_session", lazy="dynamic")

    @property
    def is_open(self):
        return self.closed_at is None

    def cash_sales_total(self):
        from app.models.invoice import Invoice

        total = db.session.query(db.func.coalesce(db.func.sum(Invoice.total), 0)).filter(
            Invoice.cash_session_id == self.id,
            Invoice.payment_method == "cash",
            Invoice.voided.is_(False),
        ).scalar()
        return float(total or 0)

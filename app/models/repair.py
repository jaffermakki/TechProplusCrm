from datetime import datetime, timedelta
from app.extensions import db

STATUS_ORDER = ["RECEIVED", "DIAGNOSED", "WAITING", "IN_PROGRESS", "READY", "COMPLETED", "COLLECTED"]

STATUS_LABELS = {
    "RECEIVED": "Received",
    "DIAGNOSED": "Diagnosed",
    "WAITING": "Waiting for Parts",
    "IN_PROGRESS": "In Progress",
    "READY": "Ready for Pickup",
    "COMPLETED": "Completed",
    "COLLECTED": "Collected",
}

DEFAULT_WARRANTY_DAYS = 90


class Repair(db.Model):
    """Ported field-for-field from the original's repair object, including the
    three-stage cost model (estimated -> approved -> final), warranty tracking, and
    assigned technician - these were all present in the original and missing from
    the first pass of this rewrite."""

    __tablename__ = "repairs"

    id = db.Column(db.Integer, primary_key=True)
    ticket_no = db.Column(db.Integer, unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)

    device = db.Column(db.String(160), nullable=False)
    issue = db.Column(db.Text, default="")
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="RECEIVED")

    # Three-stage cost model, matching the original exactly: an estimate is given to
    # the customer up front, then an approved cost once they agree (which may differ
    # from the estimate), then a final cost at completion (which may differ again if
    # the job turned out to be more/less work). generate_invoice() uses whichever is
    # set, preferring final > approved > estimated > 0 - the same waterfall as the
    # original's `r.finalCost||r.approvedCost||r.estimatedCost||0`.
    estimated_cost = db.Column(db.Numeric(10, 2), nullable=True)
    approved_cost = db.Column(db.Numeric(10, 2), nullable=True)
    final_cost = db.Column(db.Numeric(10, 2), nullable=True)

    promised_by = db.Column(db.Date, nullable=True)
    warranty_days = db.Column(db.Integer, nullable=False, default=DEFAULT_WARRANTY_DAYS)

    notes = db.Column(db.Text, default="")
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parts = db.relationship("RepairPart", backref="repair", lazy="dynamic", cascade="all, delete-orphan")
    photos = db.relationship("RepairPhoto", backref="repair", lazy="dynamic", cascade="all, delete-orphan")
    status_history = db.relationship(
        "RepairStatusHistory", backref="repair", lazy="dynamic",
        cascade="all, delete-orphan", order_by="RepairStatusHistory.created_at",
    )
    technician = db.relationship("Staff", foreign_keys=[technician_id])

    @property
    def status_label(self):
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def billable_cost(self) -> float:
        """The cost waterfall used for invoicing: final > approved > estimated > 0,
        matching the original's `r.finalCost||r.approvedCost||r.estimatedCost||0`."""
        for value in (self.final_cost, self.approved_cost, self.estimated_cost):
            if value is not None:
                return float(value)
        return 0.0

    @property
    def is_overdue(self) -> bool:
        """Port of: r.promisedBy && r.promisedBy < todayStr && !['COMPLETED','COLLECTED'].includes(status)"""
        if not self.promised_by or self.status in ("COMPLETED", "COLLECTED"):
            return False
        return self.promised_by < datetime.utcnow().date()

    @property
    def completed_at(self):
        """Looks up the COMPLETED entry in status history, NOT created_at - matching
        the original's warranty calculation, which keys off when the repair was
        actually finished, not when the ticket was opened."""
        entry = (
            self.status_history.filter_by(status="COMPLETED")
            .order_by(RepairStatusHistory.created_at.desc())
            .first()
        )
        return entry.created_at if entry else None

    @property
    def warranty_expires_at(self):
        completed = self.completed_at
        if not completed:
            return None
        return completed + timedelta(days=self.warranty_days or DEFAULT_WARRANTY_DAYS)

    @property
    def is_under_warranty(self) -> bool:
        if self.status not in ("COMPLETED", "COLLECTED"):
            return False
        expiry = self.warranty_expires_at
        return expiry is not None and expiry > datetime.utcnow()

    @property
    def warranty_days_remaining(self) -> int:
        expiry = self.warranty_expires_at
        if not expiry:
            return 0
        delta = expiry - datetime.utcnow()
        return max(0, delta.days + (1 if delta.seconds > 0 else 0))

    def __repr__(self):
        return f"<Repair #{self.ticket_no} {self.device} [{self.status}]>"


class RepairStatusHistory(db.Model):
    """Append-only log of every status change, matching the original's r.statusHistory
    array. This is what completed_at/warranty calculations key off of, and what the
    repair detail page shows as a timeline."""

    __tablename__ = "repair_status_history"

    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repairs.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    note = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RepairPart(db.Model):
    """A part consumed by a repair. Looked up by product SKU (matching the original's
    addRepairPart, which takes a typed SKU) and deducts stock at the repair's location
    immediately on add - this was a real gap in the first version of this rewrite,
    where parts were just a disconnected text log."""

    __tablename__ = "repair_parts"

    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repairs.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    description = db.Column(db.String(200), nullable=False)
    qty = db.Column(db.Integer, default=1)
    unit_cost = db.Column(db.Numeric(10, 2), default=0)


class RepairPhoto(db.Model):
    __tablename__ = "repair_photos"

    id = db.Column(db.Integer, primary_key=True)
    repair_id = db.Column(db.Integer, db.ForeignKey("repairs.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

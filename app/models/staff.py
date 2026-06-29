from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db

ROLE_OWNER = "owner"
ROLE_MANAGER = "manager"
ROLE_STAFF = "staff"
ROLES = [ROLE_OWNER, ROLE_MANAGER, ROLE_STAFF]


class Staff(UserMixin, db.Model):
    __tablename__ = "staff"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    pin_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STAFF)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    avatar_letter = db.Column(db.String(2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoices = db.relationship("Invoice", backref="staff", lazy="dynamic")
    cash_sessions = db.relationship("CashSession", backref="staff", lazy="dynamic")
    audit_entries = db.relationship("AuditLog", backref="staff", lazy="dynamic")

    def set_pin(self, raw_pin: str):
        self.pin_hash = generate_password_hash(raw_pin)

    def check_pin(self, raw_pin: str) -> bool:
        return check_password_hash(self.pin_hash, raw_pin)

    def has_role(self, *roles) -> bool:
        return self.role in roles

    @property
    def initial(self):
        return (self.avatar_letter or self.name[:1] or "?").upper()

    def __repr__(self):
        return f"<Staff {self.name} ({self.role})>"

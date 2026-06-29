from datetime import datetime
from app.extensions import db


class Location(db.Model):
    """A physical shop location. Added to support multiple shop computers sharing one
    database - lets reports break sales/repairs down by which shop they happened at,
    and lets each shop track its own independent stock levels for the shared product
    catalog (see LocationStock).
    """

    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), default="")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    staff = db.relationship("Staff", backref="location", lazy="dynamic")
    invoices = db.relationship("Invoice", backref="location", lazy="dynamic")
    repairs = db.relationship("Repair", backref="location", lazy="dynamic")
    stock_rows = db.relationship("LocationStock", backref="location", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Location {self.name}>"

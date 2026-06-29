from datetime import datetime
from app.extensions import db


class HeldCart(db.Model):
    """A parked sale (port of holdCart/recallHeldCart). Normalized instead of a JSON blob
    so held items can reference live product rows."""

    __tablename__ = "held_carts"

    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    label = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("HeldCartItem", backref="held_cart", lazy="dynamic", cascade="all, delete-orphan")


class HeldCartItem(db.Model):
    __tablename__ = "held_cart_items"

    id = db.Column(db.Integer, primary_key=True)
    held_cart_id = db.Column(db.Integer, db.ForeignKey("held_carts.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    qty = db.Column(db.Integer, nullable=False, default=1)

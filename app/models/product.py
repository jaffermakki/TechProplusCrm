from datetime import datetime
from app.extensions import db

CATEGORIES = ["Phones", "Tablets", "Laptops", "Accessories", "Parts", "Other"]


class Product(db.Model):
    """The shared catalog entry (name, SKU, price, cost) - same across all locations.
    Stock levels are NOT stored here; see LocationStock. Use product.stock_at(location_id)
    or product.total_qty_on_hand for actual counts."""

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(60), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(60), default="Other")
    subcategory = db.Column(db.String(60), default="")
    cost = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    stock_adjustments = db.relationship("StockAdjustment", backref="product", lazy="dynamic")
    location_stock = db.relationship("LocationStock", backref="product", lazy="dynamic", cascade="all, delete-orphan")

    def stock_at(self, location_id):
        """Returns the LocationStock row for this product at a given location,
        creating one with zero quantity if it doesn't exist yet (e.g. a new location
        was added after this product already existed)."""
        if location_id is None:
            return None
        row = self.location_stock.filter_by(location_id=location_id).first()
        if row is None:
            row = LocationStock(product_id=self.id, location_id=location_id, qty_on_hand=0)
            db.session.add(row)
            db.session.flush()
        return row

    def qty_at(self, location_id) -> int:
        """Convenience: just the number, without creating a row if one doesn't exist."""
        if location_id is None:
            return 0
        row = self.location_stock.filter_by(location_id=location_id).first()
        return row.qty_on_hand if row else 0

    @property
    def total_qty_on_hand(self) -> int:
        """Sum of stock across every location - used for the catalog-wide inventory
        view and the 'low stock' check when no specific location is in context."""
        total = db.session.query(db.func.coalesce(db.func.sum(LocationStock.qty_on_hand), 0)).filter(
            LocationStock.product_id == self.id
        ).scalar()
        return int(total or 0)

    @property
    def low_stock_locations(self):
        """List of LocationStock rows that are at or below their reorder point."""
        return [row for row in self.location_stock if row.qty_on_hand <= row.reorder_point]

    @property
    def low_stock(self) -> bool:
        """True if ANY location is low - used for the catalog-wide low-stock badge."""
        return len(self.low_stock_locations) > 0

    def __repr__(self):
        return f"<Product {self.sku} {self.name}>"


class LocationStock(db.Model):
    """Per-location stock level for a product. One row per (product, location) pair.
    This is the actual source of truth for 'how many do we have' - Product itself
    carries no quantity. Each location's reorder_point is independent too, since a
    high-traffic shop might want a higher reorder threshold than a quiet one."""

    __tablename__ = "location_stock"
    __table_args__ = (db.UniqueConstraint("product_id", "location_id", name="uq_product_location"),)

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    qty_on_hand = db.Column(db.Integer, nullable=False, default=0)
    reorder_point = db.Column(db.Integer, nullable=False, default=2)

    @property
    def low_stock(self) -> bool:
        return self.qty_on_hand <= self.reorder_point


class StockAdjustment(db.Model):
    """Append-only log of stock changes (sale, manual adjust, import, refund restock).
    Now scoped to a location, since the same product can move independently at each shop."""

    __tablename__ = "stock_adjustments"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"))
    delta = db.Column(db.Integer, nullable=False)  # positive = added, negative = removed
    reason = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

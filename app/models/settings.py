from app.extensions import db

# Canadian province tax table, ported exactly from the original calcCanadianTax/CA_PROVINCES
CA_PROVINCES = {
    "AB": {"label": "Alberta", "gst": 5.0, "pst": 0.0, "hst": 0.0},
    "BC": {"label": "British Columbia", "gst": 5.0, "pst": 7.0, "hst": 0.0},
    "MB": {"label": "Manitoba", "gst": 5.0, "pst": 7.0, "hst": 0.0},
    "NB": {"label": "New Brunswick", "gst": 0.0, "pst": 0.0, "hst": 15.0},
    "NL": {"label": "Newfoundland and Labrador", "gst": 0.0, "pst": 0.0, "hst": 15.0},
    "NS": {"label": "Nova Scotia", "gst": 0.0, "pst": 0.0, "hst": 15.0},
    "NT": {"label": "Northwest Territories", "gst": 5.0, "pst": 0.0, "hst": 0.0},
    "NU": {"label": "Nunavut", "gst": 5.0, "pst": 0.0, "hst": 0.0},
    "ON": {"label": "Ontario", "gst": 0.0, "pst": 0.0, "hst": 13.0},
    "PE": {"label": "Prince Edward Island", "gst": 0.0, "pst": 0.0, "hst": 15.0},
    "QC": {"label": "Quebec", "gst": 5.0, "pst": 9.975, "hst": 0.0},
    "SK": {"label": "Saskatchewan", "gst": 5.0, "pst": 6.0, "hst": 0.0},
    "YT": {"label": "Yukon", "gst": 5.0, "pst": 0.0, "hst": 0.0},
}


class ShopSettings(db.Model):
    """Singleton-style settings row. There should only ever be one row (id=1)."""

    __tablename__ = "shop_settings"

    id = db.Column(db.Integer, primary_key=True)

    # Shop tab
    shop_name = db.Column(db.String(160), nullable=False, default="Your Shop")
    address = db.Column(db.String(255), default="")
    phone = db.Column(db.String(40), default="")
    logo_path = db.Column(db.String(255), default="")

    # Tax tab
    province = db.Column(db.String(2), nullable=False, default="ON")
    tax_inclusive_pricing = db.Column(db.Boolean, default=False)
    currency = db.Column(db.String(4), nullable=False, default="$")

    # Invoice tab
    invoice_prefix = db.Column(db.String(20), default="INV")
    invoice_next_number = db.Column(db.Integer, default=1001)
    invoice_footer_note = db.Column(db.String(255), default="Thank you for your business!")

    # Loyalty tab - field names and defaults match the original app exactly:
    # "Points Earned per $1 Spent" (pointsPerDollar, default 1) and
    # "Points Needed for $1 Credit" (pointsRedeemRate, default 100).
    # dollar_value = points / points_redeem_rate - NOT points * some dollar-per-point rate.
    loyalty_enabled = db.Column(db.Boolean, default=True)
    loyalty_points_per_dollar = db.Column(db.Float, default=1.0)
    loyalty_points_redeem_rate = db.Column(db.Float, default=100.0)

    # Email tab
    email_receipts_enabled = db.Column(db.Boolean, default=False)

    # SMS tab
    sms_enabled = db.Column(db.Boolean, default=False)
    sms_ready_template = db.Column(
        db.Text,
        default="Hi {customer_name}, your {device} repair is ready for pickup at {shop_name}!",
    )

    def tax_rates(self):
        return CA_PROVINCES.get(self.province, CA_PROVINCES["ON"])

    @classmethod
    def get(cls):
        """Fetch the singleton settings row, creating it with defaults if missing."""
        settings = cls.query.get(1)
        if settings is None:
            settings = cls(id=1)
            db.session.add(settings)
            db.session.commit()
        return settings

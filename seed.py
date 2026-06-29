"""Seed script: creates tables, a default location, the first owner account, default
settings, and a handful of sample products/customers so the app is immediately usable
for testing.

Usage:
    python seed.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db
from app.models.staff import Staff, ROLE_OWNER, ROLE_STAFF
from app.models.location import Location
from app.models.settings import ShopSettings
from app.models.product import Product, LocationStock
from app.models.customer import Customer

app = create_app(os.environ.get("FLASK_ENV", "development"))


def run():
    with app.app_context():
        db.create_all()

        if ShopSettings.query.get(1) is None:
            settings = ShopSettings(
                id=1,
                shop_name=app.config["SHOP_NAME_DEFAULT"],
                province=app.config["SHOP_PROVINCE_DEFAULT"],
                currency=app.config["SHOP_CURRENCY_DEFAULT"],
            )
            db.session.add(settings)
            print("Created default shop settings.")

        # Every staff member needs a location to sell inventory items (see
        # services/invoicing.py), so seed one default location if none exist yet.
        # If you're setting up multiple shops, add the others from Settings → Locations
        # and reassign staff there - this default is just so the app works immediately.
        default_location = Location.query.first()
        if default_location is None:
            default_location = Location(name="Main Location", address="")
            db.session.add(default_location)
            db.session.flush()
            print("Created default location: 'Main Location' (rename/add more in Settings → Locations)")

        if Staff.query.count() == 0:
            owner = Staff(name="Owner", role=ROLE_OWNER, avatar_letter="O", location_id=default_location.id)
            owner.set_pin("1234")
            db.session.add(owner)

            tech = Staff(name="Sam Tech", role=ROLE_STAFF, avatar_letter="S", location_id=default_location.id)
            tech.set_pin("4321")
            db.session.add(tech)
            print("Created staff accounts: Owner (PIN 1234), Sam Tech (PIN 4321) — both assigned to Main Location")

        if Product.query.count() == 0:
            sample_products = [
                {"sku": "SCR-IP12", "name": "iPhone 12 Screen (Black)", "category": "Parts", "cost": 28.00, "price": 79.99, "qty": 12},
                {"sku": "BAT-S21", "name": "Samsung S21 Battery", "category": "Parts", "cost": 14.00, "price": 39.99, "qty": 8},
                {"sku": "CASE-UNI", "name": "Universal Phone Case", "category": "Accessories", "cost": 3.00, "price": 14.99, "qty": 40},
                {"sku": "CHG-USBC", "name": "USB-C Fast Charger", "category": "Accessories", "cost": 6.00, "price": 24.99, "qty": 25},
                {"sku": "TG-IP13", "name": "iPhone 13 Tempered Glass", "category": "Accessories", "cost": 1.50, "price": 9.99, "qty": 50},
            ]
            for sp in sample_products:
                qty = sp.pop("qty")
                product = Product(**sp)
                db.session.add(product)
                db.session.flush()
                db.session.add(LocationStock(product_id=product.id, location_id=default_location.id, qty_on_hand=qty, reorder_point=2))
            print(f"Created {len(sample_products)} sample products with stock at Main Location.")

        if Customer.query.count() == 0:
            db.session.add(Customer(name="Jordan Lee", phone="416-555-0142", email="jordan@example.com"))
            db.session.add(Customer(name="Priya Shah", phone="647-555-0198", email="priya@example.com"))
            print("Created 2 sample customers.")

        db.session.commit()
        print("\nSeed complete. Run the app with: python wsgi.py")


if __name__ == "__main__":
    run()

import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.product import Product, StockAdjustment, LocationStock, CATEGORIES
from app.models.location import Location
from app.models.audit import AuditLog
from app.services.inventory_import import parse_supplier_lines

bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@bp.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    query = Product.query
    if q:
        query = query.filter(db.or_(Product.name.ilike(f"%{q}%"), Product.sku.ilike(f"%{q}%")))
    products = query.order_by(Product.name).all()
    locations = Location.query.filter_by(active=True).order_by(Location.name).all()

    # Build a {product_id: {location_id: qty}} lookup so the table can show one
    # column per location without N+1 queries per row.
    stock_lookup = {}
    for row in LocationStock.query.all():
        stock_lookup.setdefault(row.product_id, {})[row.location_id] = row.qty_on_hand

    return render_template(
        "inventory/index.html",
        products=products,
        categories=CATEGORIES,
        q=q,
        locations=locations,
        stock_lookup=stock_lookup,
    )


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_product():
    locations = Location.query.filter_by(active=True).order_by(Location.name).all()

    if request.method == "POST":
        sku = request.form.get("sku", "").strip() or f"SKU-{uuid.uuid4().hex[:8].upper()}"
        product = Product(
            sku=sku,
            name=request.form.get("name", "").strip(),
            category=request.form.get("category", "Other"),
            subcategory=request.form.get("subcategory", "").strip(),
            cost=float(request.form.get("cost", 0) or 0),
            price=float(request.form.get("price", 0) or 0),
        )
        db.session.add(product)
        db.session.flush()

        # Starting stock is entered per-location (defaults to 0 for any location left blank)
        reorder_point = int(request.form.get("reorder_point", 2) or 2)
        for loc in locations:
            qty = int(request.form.get(f"qty_loc_{loc.id}", 0) or 0)
            db.session.add(LocationStock(product_id=product.id, location_id=loc.id, qty_on_hand=qty, reorder_point=reorder_point))

        db.session.commit()
        AuditLog.record("product_created", f"{product.sku} — {product.name}")
        flash("Product added.", "green")
        return redirect(url_for("inventory.index"))

    return render_template("inventory/add.html", categories=CATEGORIES, locations=locations)


@bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    locations = Location.query.filter_by(active=True).order_by(Location.name).all()

    if request.method == "POST":
        product.name = request.form.get("name", "").strip()
        product.category = request.form.get("category", "Other")
        product.subcategory = request.form.get("subcategory", "").strip()
        product.cost = float(request.form.get("cost", 0) or 0)
        product.price = float(request.form.get("price", 0) or 0)
        product.active = bool(request.form.get("active"))

        reorder_point = int(request.form.get("reorder_point", 2) or 2)
        for loc in locations:
            row = product.stock_at(loc.id)
            row.reorder_point = reorder_point

        db.session.commit()
        flash("Product updated.", "green")
        return redirect(url_for("inventory.index"))

    return render_template("inventory/edit.html", product=product, categories=CATEGORIES, locations=locations)


@bp.route("/<int:product_id>/adjust", methods=["POST"])
@login_required
def adjust_stock(product_id):
    product = Product.query.get_or_404(product_id)
    location_id = request.form.get("location_id", "").strip()
    delta = int(request.form.get("delta", 0) or 0)
    reason = request.form.get("reason", "Manual adjustment").strip()

    if not location_id:
        flash("Choose a location to adjust stock for.", "amber")
        return redirect(url_for("inventory.index"))
    location_id = int(location_id)

    stock_row = product.stock_at(location_id)
    new_qty = stock_row.qty_on_hand + delta
    if new_qty < 0:
        flash("Adjustment would make stock negative — rejected.", "red")
        return redirect(url_for("inventory.index"))

    stock_row.qty_on_hand = new_qty
    db.session.add(StockAdjustment(product_id=product.id, location_id=location_id, staff_id=current_user.id, delta=delta, reason=reason))
    db.session.commit()
    AuditLog.record("stock_adjusted", f"{product.sku} {delta:+d} at location #{location_id} ({reason})")
    flash("Stock updated.", "green")
    return redirect(url_for("inventory.index"))


@bp.route("/import", methods=["GET", "POST"])
@login_required
def bulk_import():
    preview_rows, errors = [], []
    raw_text = ""
    locations = Location.query.filter_by(active=True).order_by(Location.name).all()
    selected_location_id = request.form.get("location_id", "")

    if request.method == "POST":
        raw_text = request.form.get("raw_text", "")
        action = request.form.get("action", "preview")
        preview_rows, errors = parse_supplier_lines(raw_text)

        if action == "confirm" and preview_rows:
            if not selected_location_id:
                flash("Choose which location this delivery is for.", "amber")
                return render_template("inventory/import.html", raw_text=raw_text, preview_rows=preview_rows, errors=errors, locations=locations, selected_location_id=selected_location_id)
            location_id = int(selected_location_id)

            created, updated = 0, 0
            for row in preview_rows:
                product = Product.query.filter_by(sku=row["sku"]).first() if row["sku"] else None
                if not product:
                    product = Product(
                        sku=row["sku"] or f"SKU-{uuid.uuid4().hex[:8].upper()}",
                        name=row["name"],
                        price=row["price"],
                        cost=row["price"] * 0.6,
                    )
                    db.session.add(product)
                    db.session.flush()
                    created += 1
                else:
                    product.price = row["price"]
                    updated += 1

                stock_row = product.stock_at(location_id)
                stock_row.qty_on_hand += row["qty"]
                db.session.add(StockAdjustment(product_id=product.id, location_id=location_id, staff_id=current_user.id, delta=row["qty"], reason="Bulk import"))

            db.session.commit()
            loc_name = Location.query.get(location_id).name
            AuditLog.record("inventory_bulk_import", f"{created} created, {updated} updated at {loc_name}")
            flash(f"Import complete: {created} created, {updated} updated at {loc_name}.", "green")
            return redirect(url_for("inventory.index"))

    return render_template("inventory/import.html", raw_text=raw_text, preview_rows=preview_rows, errors=errors, locations=locations, selected_location_id=selected_location_id)

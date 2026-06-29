from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models.product import Product
from app.models.customer import Customer
from app.models.settings import ShopSettings
from app.models.held_cart import HeldCart, HeldCartItem
from app.models.audit import AuditLog
from app.services.invoicing import calc_cart_totals, complete_sale, CartError
from app.services.loyalty import InsufficientBalanceError, max_redeemable_points

bp = Blueprint("pos", __name__, url_prefix="/pos")

CART_SESSION_KEY = "pos_cart"
CART_CUSTOMER_KEY = "pos_customer_id"


def _get_cart() -> dict:
    """Cart kept server-side in the Flask session: {product_id (str): qty}."""
    return session.setdefault(CART_SESSION_KEY, {})


def _cart_lines():
    cart = _get_cart()
    lines = []
    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        if product:
            lines.append({"product": product, "qty": qty})
    return lines


def _cart_customer():
    cid = session.get(CART_CUSTOMER_KEY)
    return Customer.query.get(cid) if cid else None


@bp.route("/")
@login_required
def index():
    products = Product.query.filter_by(active=True).order_by(Product.name).all()
    settings = ShopSettings.get()
    cart_lines = _cart_lines()
    customer = _cart_customer()
    totals = calc_cart_totals(cart_lines, settings, customer=customer) if cart_lines else None
    max_points = max_redeemable_points(customer, settings) if customer else 0
    held_carts = HeldCart.query.order_by(HeldCart.created_at.desc()).limit(10).all()

    # Stock shown/checked is for the logged-in staff member's own location - each shop
    # only sees and sells against its own stock count, not the combined total.
    stock_by_product = {p.id: p.qty_at(current_user.location_id) for p in products}

    return render_template(
        "pos/index.html",
        products=products,
        cart_lines=cart_lines,
        customer=customer,
        totals=totals,
        settings=settings,
        held_carts=held_carts,
        max_redeemable_points=max_points,
        stock_by_product=stock_by_product,
        no_location_assigned=current_user.location_id is None,
    )


@bp.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    cart = _get_cart()
    key = str(product_id)
    new_qty = cart.get(key, 0) + 1
    available = product.qty_at(current_user.location_id)
    if new_qty > available:
        flash(f"Only {available} of {product.name} in stock at your location.", "amber")
    else:
        cart[key] = new_qty
        session.modified = True
    return redirect(url_for("pos.index"))


@bp.route("/cart/qty/<int:product_id>", methods=["POST"])
@login_required
def change_qty(product_id):
    delta = int(request.form.get("delta", 0))
    cart = _get_cart()
    key = str(product_id)
    if key in cart:
        cart[key] = max(0, cart[key] + delta)
        if cart[key] == 0:
            del cart[key]
        session.modified = True
    return redirect(url_for("pos.index"))


@bp.route("/cart/remove/<int:product_id>", methods=["POST"])
@login_required
def remove_from_cart(product_id):
    cart = _get_cart()
    cart.pop(str(product_id), None)
    session.modified = True
    return redirect(url_for("pos.index"))


@bp.route("/cart/clear", methods=["POST"])
@login_required
def clear_cart():
    session[CART_SESSION_KEY] = {}
    session.pop(CART_CUSTOMER_KEY, None)
    session.modified = True
    return redirect(url_for("pos.index"))


@bp.route("/cart/customer", methods=["POST"])
@login_required
def set_customer():
    customer_id = request.form.get("customer_id", "").strip()
    if customer_id:
        session[CART_CUSTOMER_KEY] = int(customer_id)
    else:
        session.pop(CART_CUSTOMER_KEY, None)
    session.modified = True
    return redirect(url_for("pos.index"))


@bp.route("/customers/search")
@login_required
def search_customers():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    matches = Customer.query.filter(
        db.or_(Customer.name.ilike(f"%{q}%"), Customer.phone.ilike(f"%{q}%"))
    ).limit(10).all()
    return jsonify([{"id": c.id, "name": c.name, "phone": c.phone} for c in matches])


@bp.route("/hold", methods=["POST"])
@login_required
def hold_cart():
    cart = _get_cart()
    if not cart:
        flash("Cart is empty - nothing to hold.", "amber")
        return redirect(url_for("pos.index"))

    held = HeldCart(staff_id=current_user.id, customer_id=session.get(CART_CUSTOMER_KEY))
    db.session.add(held)
    db.session.flush()
    for pid, qty in cart.items():
        db.session.add(HeldCartItem(held_cart_id=held.id, product_id=int(pid), qty=qty))
    db.session.commit()

    session[CART_SESSION_KEY] = {}
    session.pop(CART_CUSTOMER_KEY, None)
    session.modified = True
    flash("Cart held. You can recall it later.", "green")
    return redirect(url_for("pos.index"))


@bp.route("/recall/<int:held_id>", methods=["POST"])
@login_required
def recall_cart(held_id):
    held = HeldCart.query.get_or_404(held_id)
    cart = {}
    for item in held.items:
        cart[str(item.product_id)] = item.qty
    session[CART_SESSION_KEY] = cart
    if held.customer_id:
        session[CART_CUSTOMER_KEY] = held.customer_id
    session.modified = True

    db.session.delete(held)
    db.session.commit()
    return redirect(url_for("pos.index"))


@bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
    cart_lines = _cart_lines()
    customer = _cart_customer()
    payment_method = request.form.get("payment_method", "cash")
    loyalty_points = int(request.form.get("loyalty_points_redeemed", 0) or 0)
    store_credit = float(request.form.get("store_credit_used", 0) or 0)
    tendered_raw = request.form.get("tendered", "").strip()
    tendered = float(tendered_raw) if tendered_raw else None

    split_method = request.form.get("split_method", "").strip()
    split_amount = float(request.form.get("split_amount", 0) or 0)
    split_payment = {"method": split_method, "amount": split_amount} if split_method and split_amount > 0 else None

    try:
        invoice, change_due = complete_sale(
            cart_lines=cart_lines,
            staff=current_user,
            customer=customer,
            payment_method=payment_method,
            loyalty_points_redeemed=loyalty_points,
            store_credit_used=store_credit,
            tendered=tendered,
            split_payment=split_payment,
        )
    except (CartError, InsufficientBalanceError) as exc:
        flash(str(exc), "red")
        return redirect(url_for("pos.index"))

    session[CART_SESSION_KEY] = {}
    session.pop(CART_CUSTOMER_KEY, None)
    session.modified = True

    AuditLog.record("sale_completed", f"Invoice {invoice.invoice_number} for ${invoice.total}")
    msg = f"Sale complete — {invoice.invoice_number}"
    if change_due > 0:
        msg += f" — change due: ${change_due:.2f}"
    flash(msg, "green")
    return redirect(url_for("pos.receipt", invoice_id=invoice.id))


@bp.route("/receipt/<int:invoice_id>")
@login_required
def receipt(invoice_id):
    from app.models.invoice import Invoice

    invoice = Invoice.query.get_or_404(invoice_id)
    settings = ShopSettings.get()
    return render_template("print/invoice.html", invoice=invoice, settings=settings)

from datetime import datetime, timedelta
from flask import Blueprint, render_template
from flask_login import login_required

from app.extensions import db
from app.models.invoice import Invoice
from app.models.repair import Repair, STATUS_ORDER
from app.models.product import Product
from app.models.customer import Customer
from app.services.reports import sales_trend_by_location

bp = Blueprint("dashboard", __name__, url_prefix="/")


@bp.route("/")
@login_required
def index():
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    todays_invoices = Invoice.query.filter(Invoice.created_at >= today_start, Invoice.voided.is_(False)).all()
    todays_sales_total = sum(float(i.total) for i in todays_invoices)
    todays_sales_count = len(todays_invoices)

    open_repairs = Repair.query.filter(Repair.status.notin_(["COLLECTED"])).all()
    open_repairs_count = len(open_repairs)
    ready_repairs_count = sum(1 for r in open_repairs if r.status == "READY")
    overdue_repairs = [r for r in open_repairs if r.is_overdue]

    from app.models.repair import STATUS_LABELS

    # Repairs-by-status breakdown for the dashboard widget - counts ALL repairs
    # (including COLLECTED) so the full pipeline shape is visible, not just open ones.
    # Built as plain lists, not a dict, for the chart - Jinja's attribute access on a
    # dict resolves .values()/.keys() to Python's built-in dict methods rather than
    # the intended key lookup (a real bug hit earlier in this project), so the
    # lists are built here in Python instead of relying on dict.values() in the template.
    all_repairs_for_status = Repair.query.all()
    repairs_by_status = {status: 0 for status in STATUS_ORDER}
    for r in all_repairs_for_status:
        repairs_by_status[r.status] = repairs_by_status.get(r.status, 0) + 1
    status_chart_labels = [STATUS_LABELS.get(s, s) for s in STATUS_ORDER]
    status_chart_values = [repairs_by_status.get(s, 0) for s in STATUS_ORDER]

    low_stock_products = Product.query.filter(Product.active.is_(True)).all()
    low_stock_products = [p for p in low_stock_products if p.low_stock]

    recent_invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(8).all()
    recent_customers = Customer.query.order_by(Customer.created_at.desc()).limit(5).all()

    # 7-day sales trend, summed across all locations - matches the original
    # dashboard's 7-day sales bar chart, which this rewrite was initially missing.
    week_start = today_start - timedelta(days=6)
    trend = sales_trend_by_location(week_start, today_start + timedelta(days=1), granularity="day")
    seven_day_labels = trend["labels"]
    seven_day_totals = trend["totals"]

    return render_template(
        "dashboard/index.html",
        todays_sales_total=todays_sales_total,
        todays_sales_count=todays_sales_count,
        open_repairs_count=open_repairs_count,
        ready_repairs_count=ready_repairs_count,
        overdue_repairs=overdue_repairs,
        low_stock_products=low_stock_products,
        recent_invoices=recent_invoices,
        recent_customers=recent_customers,
        seven_day_labels=seven_day_labels,
        seven_day_totals=seven_day_totals,
        status_chart_labels=status_chart_labels,
        status_chart_values=status_chart_values,
    )

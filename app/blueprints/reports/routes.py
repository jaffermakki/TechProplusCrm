from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, send_file, Response
from flask_login import login_required

from app.services.reports import (
    date_range_sales,
    eod_summary,
    top_selling_products,
    repair_turnaround_stats,
    sales_by_location,
    repairs_by_location,
    sales_trend_by_location,
)
from app.services.exports import invoices_to_csv, month_end_workbook
from app.utils.decorators import role_required

bp = Blueprint("reports", __name__, url_prefix="/reports")


def _parse_range():
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    start = datetime.strptime(start_str, "%Y-%m-%d") if start_str else today - timedelta(days=7)
    end = (datetime.strptime(end_str, "%Y-%m-%d") if end_str else today) + timedelta(days=1)
    return start, end


@bp.route("/")
@login_required
def index():
    start, end = _parse_range()
    sales = date_range_sales(start, end)
    top_products = top_selling_products(start, end)
    repair_stats = repair_turnaround_stats(start, end)
    return render_template(
        "reports/index.html",
        sales=sales,
        top_products=top_products,
        repair_stats=repair_stats,
        start=start,
        end=end - timedelta(days=1),
    )


@bp.route("/eod")
@login_required
def eod():
    summary = eod_summary()
    return render_template("print/eod_report.html", summary=summary, day=datetime.utcnow())


@bp.route("/locations")
@login_required
@role_required("owner", "manager")
def locations_overview():
    """Cross-location snapshot - designed to be checked from a phone browser.
    Defaults to today; date range is adjustable via query params like the main
    reports page."""
    start, end = _parse_range()
    sales_rows = sales_by_location(start, end)
    repair_rows = repairs_by_location(start, end)
    grand_total = round(sum(r["total"] for r in sales_rows), 2)
    return render_template(
        "reports/locations.html",
        sales_rows=sales_rows,
        repair_rows=repair_rows,
        grand_total=grand_total,
        start=start,
        end=end - timedelta(days=1),
    )


@bp.route("/locations/trend")
@login_required
@role_required("owner", "manager")
def locations_trend():
    """Day-to-day or month-to-month comparison of locations against each other over
    time - not just a single date range's total. Defaults to the last 14 days."""
    granularity = request.args.get("granularity", "day")
    if granularity not in ("day", "month"):
        granularity = "day"

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    if granularity == "month":
        default_start = (today.replace(day=1) - timedelta(days=180)).replace(day=1)
    else:
        default_start = today - timedelta(days=13)

    start = datetime.strptime(start_str, "%Y-%m-%d") if start_str else default_start
    end = (datetime.strptime(end_str, "%Y-%m-%d") if end_str else today) + timedelta(days=1)

    trend = sales_trend_by_location(start, end, granularity=granularity)

    return render_template(
        "reports/locations_trend.html",
        trend=trend,
        granularity=granularity,
        start=start,
        end=end - timedelta(days=1),
    )


@bp.route("/export/csv")
@login_required
def export_csv():
    start, end = _parse_range()
    sales = date_range_sales(start, end)
    csv_data = invoices_to_csv(sales["invoices"])
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=invoices_export.csv"},
    )


@bp.route("/export/xlsx")
@login_required
def export_xlsx():
    start, end = _parse_range()
    sales = date_range_sales(start, end)
    top_products = top_selling_products(start, end)
    workbook = month_end_workbook(sales["invoices"], top_products)
    return send_file(
        workbook,
        as_attachment=True,
        download_name="month_end_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

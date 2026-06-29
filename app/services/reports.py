from datetime import datetime, timedelta
from app.extensions import db
from app.models.invoice import Invoice, InvoiceItem
from app.models.repair import Repair


def date_range_sales(start: datetime, end: datetime):
    invoices = (
        Invoice.query.filter(Invoice.created_at >= start, Invoice.created_at < end, Invoice.voided.is_(False))
        .order_by(Invoice.created_at)
        .all()
    )
    total_sales = sum(float(i.total) for i in invoices)
    total_tax = sum(i.tax_total for i in invoices)
    by_payment_method = {}
    for inv in invoices:
        by_payment_method.setdefault(inv.payment_method, 0.0)
        by_payment_method[inv.payment_method] += float(inv.total)

    return {
        "invoices": invoices,
        "count": len(invoices),
        "total_sales": round(total_sales, 2),
        "total_tax": round(total_tax, 2),
        "by_payment_method": by_payment_method,
    }


def eod_summary(day: datetime = None):
    day = day or datetime.utcnow()
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return date_range_sales(start, end)


def top_selling_products(start: datetime, end: datetime, limit=10):
    rows = (
        db.session.query(
            InvoiceItem.description,
            db.func.sum(InvoiceItem.qty).label("total_qty"),
            db.func.sum(InvoiceItem.qty * InvoiceItem.unit_price).label("total_revenue"),
        )
        .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
        .filter(Invoice.created_at >= start, Invoice.created_at < end, Invoice.voided.is_(False))
        .group_by(InvoiceItem.description)
        .order_by(db.desc("total_revenue"))
        .limit(limit)
        .all()
    )
    return [{"description": r[0], "qty": int(r[1]), "revenue": float(r[2])} for r in rows]


def repair_turnaround_stats(start: datetime, end: datetime):
    repairs = Repair.query.filter(Repair.created_at >= start, Repair.created_at < end).all()
    completed = [r for r in repairs if r.status in ("COMPLETED", "COLLECTED")]
    avg_hours = None
    if completed:
        durations = [(r.updated_at - r.created_at).total_seconds() / 3600 for r in completed]
        avg_hours = round(sum(durations) / len(durations), 1)
    return {
        "total_repairs": len(repairs),
        "completed": len(completed),
        "avg_turnaround_hours": avg_hours,
    }


def sales_by_location(start: datetime, end: datetime):
    """Breaks down sales totals per shop location for the given date range, plus an
    "Unassigned" bucket for any invoices created by staff with no location set
    (e.g. before locations were configured). Returns a list sorted by total descending,
    each entry: {"location": Location|None, "name": str, "count": int, "total": float}.
    """
    from app.models.location import Location

    invoices = (
        Invoice.query.filter(Invoice.created_at >= start, Invoice.created_at < end, Invoice.voided.is_(False))
        .all()
    )

    locations = {loc.id: loc for loc in Location.query.all()}
    buckets = {}

    for inv in invoices:
        key = inv.location_id
        if key not in buckets:
            buckets[key] = {"location": locations.get(key), "name": locations[key].name if key in locations else "Unassigned", "count": 0, "total": 0.0}
        buckets[key]["count"] += 1
        buckets[key]["total"] += float(inv.total)

    rows = list(buckets.values())
    for row in rows:
        row["total"] = round(row["total"], 2)
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows


def sales_trend_by_location(start: datetime, end: datetime, granularity: str = "day"):
    """Buckets sales into day-by-day or month-by-month periods, broken down per location,
    for comparing how locations are trending against each other over time (not just a
    single date range's total). Returns:
        {
            "labels": ["Jun 01", "Jun 02", ...] or ["Jan 2026", "Feb 2026", ...],
            "locations": [{"name": str, "location_id": int|None, "values": [float, ...]}],
            "totals": [float, ...],  # combined total per period, across all locations
        }
    granularity: "day" or "month". Each location's `values` list lines up index-for-index
    with `labels`, so this can feed a chart with one series per location directly.
    """
    from app.models.location import Location

    invoices = (
        Invoice.query.filter(Invoice.created_at >= start, Invoice.created_at < end, Invoice.voided.is_(False))
        .all()
    )

    locations = {loc.id: loc.name for loc in Location.query.all()}

    def period_key(dt):
        if granularity == "month":
            return dt.strftime("%Y-%m")
        return dt.strftime("%Y-%m-%d")

    def period_label(key):
        if granularity == "month":
            return datetime.strptime(key, "%Y-%m").strftime("%b %Y")
        return datetime.strptime(key, "%Y-%m-%d").strftime("%b %d")

    # Build the full ordered list of period keys in range, so empty days/months still
    # show up as zero rather than being skipped (important for a clean chart x-axis).
    period_keys = []
    if granularity == "month":
        cursor = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        while cursor < end:
            period_keys.append(cursor.strftime("%Y-%m"))
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)
    else:
        cursor = start
        while cursor < end:
            period_keys.append(cursor.strftime("%Y-%m-%d"))
            cursor += timedelta(days=1)

    location_series = {}  # location_id (or None) -> {period_key: total}
    for inv in invoices:
        loc_id = inv.location_id
        key = period_key(inv.created_at)
        location_series.setdefault(loc_id, {})
        location_series[loc_id][key] = location_series[loc_id].get(key, 0.0) + float(inv.total)

    series_rows = []
    for loc_id, period_totals in location_series.items():
        name = locations.get(loc_id, "Unassigned")
        values = [round(period_totals.get(k, 0.0), 2) for k in period_keys]
        series_rows.append({"location_id": loc_id, "name": name, "values": values})

    series_rows.sort(key=lambda r: sum(r["values"]), reverse=True)

    totals = [round(sum(row["values"][i] for row in series_rows), 2) for i in range(len(period_keys))]

    return {
        "labels": [period_label(k) for k in period_keys],
        "locations": series_rows,
        "totals": totals,
    }


def repairs_by_location(start: datetime, end: datetime):
    """Same idea as sales_by_location but for repair ticket counts and open/ready counts,
    so the cross-location view can show 'Shop A has 3 ready for pickup' at a glance."""
    from app.models.location import Location

    repairs = Repair.query.filter(Repair.created_at >= start, Repair.created_at < end).all()
    locations = {loc.id: loc for loc in Location.query.all()}
    buckets = {}

    for r in repairs:
        key = r.location_id
        if key not in buckets:
            buckets[key] = {
                "location": locations.get(key),
                "name": locations[key].name if key in locations else "Unassigned",
                "total": 0,
                "ready": 0,
                "open": 0,
            }
        buckets[key]["total"] += 1
        if r.status == "READY":
            buckets[key]["ready"] += 1
        if r.status != "COLLECTED":
            buckets[key]["open"] += 1

    rows = list(buckets.values())
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows

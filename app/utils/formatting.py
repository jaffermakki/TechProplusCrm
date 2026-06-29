from datetime import datetime, date


def fmt_money(value, currency="$") -> str:
    try:
        return f"{currency}{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return f"{currency}0.00"


def fmt_date(value, fallback="—") -> str:
    if not value:
        return fallback
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(value, (datetime, date)):
        return value.strftime("%d %b %Y")
    return fallback


def fmt_datetime(value, fallback="—") -> str:
    if not value:
        return fallback
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y, %I:%M %p")
    return fallback

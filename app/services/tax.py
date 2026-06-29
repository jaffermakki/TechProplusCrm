"""Port of the original calcCanadianTax() JS function.

Given a taxable subtotal and a province code, returns the GST/PST/HST breakdown.
Some provinces use a combined HST instead of separate GST+PST.
"""
from decimal import Decimal, ROUND_HALF_UP
from app.models.settings import CA_PROVINCES


def _round2(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calc_canadian_tax(taxable_amount, province_code: str) -> dict:
    """Returns {'gst': Decimal, 'pst': Decimal, 'hst': Decimal, 'total_tax': Decimal, 'grand_total': Decimal}"""
    rates = CA_PROVINCES.get(province_code, CA_PROVINCES["ON"])
    taxable = Decimal(str(taxable_amount))

    gst = _round2(taxable * Decimal(str(rates["gst"])) / 100)
    pst = _round2(taxable * Decimal(str(rates["pst"])) / 100)
    hst = _round2(taxable * Decimal(str(rates["hst"])) / 100)

    total_tax = gst + pst + hst
    return {
        "gst": gst,
        "pst": pst,
        "hst": hst,
        "total_tax": total_tax,
        "grand_total": _round2(taxable + total_tax),
    }


def tax_breakdown_label(province_code: str) -> str:
    rates = CA_PROVINCES.get(province_code, CA_PROVINCES["ON"])
    parts = []
    if rates["gst"]:
        parts.append(f"GST {rates['gst']:g}%")
    if rates["pst"]:
        parts.append(f"PST {rates['pst']:g}%")
    if rates["hst"]:
        parts.append(f"HST {rates['hst']:g}%")
    return " + ".join(parts) if parts else "No tax"

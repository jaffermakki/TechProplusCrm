"""Port of parseIgenLines() - parses pasted supplier price-list text into structured rows.

The original parser handled messy, inconsistently-spaced supplier text like:
    IPHONE 12 SCREEN BLACK   $45.00   QTY:10
    SKU1234 | Samsung S21 Battery | 25.50 | 5

Since the exact supplier format wasn't fully recoverable from the obfuscated source, this
implements a permissive parser covering the common patterns: tab/pipe/multi-space delimited
columns, with a SKU (optional), name, price, and quantity. Adjust `_SPLIT_RE` and `_PRICE_RE`
if your real supplier export differs - this is the single function to edit.
"""
import re

_SPLIT_RE = re.compile(r"\s*\|\s*|\t+|\s{2,}")
_PRICE_RE = re.compile(r"\$?\s*(\d+(?:\.\d{1,2})?)")
_QTY_RE = re.compile(r"(?:qty|x)\s*:?\s*(\d+)", re.IGNORECASE)


def parse_supplier_lines(raw_text: str):
    """Returns (parsed_rows, errors). Each parsed row:
        {"sku": str|None, "name": str, "price": float, "qty": int}
    """
    parsed_rows = []
    errors = []

    for line_no, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        qty_match = _QTY_RE.search(line)
        qty = int(qty_match.group(1)) if qty_match else 1
        line_wo_qty = _QTY_RE.sub("", line).strip()

        columns = [c.strip() for c in _SPLIT_RE.split(line_wo_qty) if c.strip()]

        price = None
        price_idx = None
        for idx, col in enumerate(columns):
            m = _PRICE_RE.fullmatch(col) or _PRICE_RE.search(col) if "$" in col else _PRICE_RE.fullmatch(col)
            if m:
                price = float(m.group(1))
                price_idx = idx
                break

        if price is None:
            errors.append({"line_no": line_no, "raw": raw_line, "error": "No price found"})
            continue

        sku = None
        name_parts = [c for i, c in enumerate(columns) if i != price_idx]
        if name_parts and re.fullmatch(r"[A-Za-z0-9_-]{3,20}", name_parts[0]) and len(name_parts) > 1:
            sku = name_parts.pop(0)

        name = " ".join(name_parts).strip()
        if not name:
            errors.append({"line_no": line_no, "raw": raw_line, "error": "No product name found"})
            continue

        parsed_rows.append({"sku": sku, "name": name, "price": price, "qty": qty})

    return parsed_rows, errors

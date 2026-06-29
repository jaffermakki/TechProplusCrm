"""Port of generateInvoiceNumber(), made safe for concurrent requests.

The original JS kept a counter in localStorage - fine for one browser tab, unsafe with
multiple staff checking out simultaneously. Here we use a DB-level row lock (SELECT ... FOR
UPDATE under Postgres; SQLite falls back to its own serialization) so two concurrent requests
can never receive the same invoice number.
"""
from app.extensions import db
from app.models.settings import ShopSettings


def next_invoice_number() -> str:
    settings = db.session.query(ShopSettings).filter(ShopSettings.id == 1).with_for_update().first()
    if settings is None:
        settings = ShopSettings.get()

    number = settings.invoice_next_number
    settings.invoice_next_number = number + 1
    db.session.add(settings)
    db.session.commit()

    return f"{settings.invoice_prefix}-{number:06d}"

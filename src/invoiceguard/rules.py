"""Business rules over an extracted invoice. Each failure is a specific, human-readable reason."""

import re
from decimal import Decimal

from invoiceguard.schema import REQUIRED_FIELDS, Invoice, LineItem

TOLERANCE = Decimal("0.01")
SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}
FIELD_LABELS = {
    "vendor_name": "vendor", "invoice_number": "invoice number", "invoice_date": "invoice date",
    "due_date": "due date", "currency": "currency", "subtotal": "subtotal", "tax": "tax",
    "total": "total", "po_number": "PO number",
}
# Backstop for instructions aimed at an AI system; the model is also told to ignore them.
INJECTION = re.compile(
    r"\b(ignore|disregard)\b.{0,40}\binstructions?\b|^\s*(system|assistant)\s*:|you are now",
    re.IGNORECASE | re.MULTILINE,
)


def money(value: Decimal, currency: str | None) -> str:
    prefix = SYMBOLS.get(currency or "", f"{currency} " if currency else "")
    return f"{prefix}{value:,.2f}"


def missing_fields(inv: Invoice) -> list[str]:
    return [
        f"Missing {FIELD_LABELS[name]}" for name in REQUIRED_FIELDS
        if getattr(inv, name).value is None
    ]


def bad_line_amounts(items: tuple[LineItem, ...], currency: str | None) -> list[str]:
    return [
        f"{i.description}: {i.quantity:f} x {money(i.unit_price, currency)} is "
        f"{money(i.quantity * i.unit_price, currency)}, line says {money(i.amount, currency)}"
        for i in items
        if abs(i.quantity * i.unit_price - i.amount) > TOLERANCE
    ]


def line_sum_mismatch(inv: Invoice, currency: str | None) -> list[str]:
    subtotal = inv.subtotal.value
    if not inv.line_items or subtotal is None:
        return []
    line_sum = sum((i.amount for i in inv.line_items), Decimal("0"))
    if abs(line_sum - subtotal) <= TOLERANCE:
        return []
    return [f"Line items add to {money(line_sum, currency)}, "
            f"subtotal says {money(subtotal, currency)}"]


def total_mismatch(inv: Invoice, currency: str | None) -> list[str]:
    subtotal, tax, total = inv.subtotal.value, inv.tax.value, inv.total.value
    if None in (subtotal, tax, total) or abs(subtotal + tax - total) <= TOLERANCE:
        return []
    return [f"Subtotal plus tax is {money(subtotal + tax, currency)}, "
            f"total says {money(total, currency)}"]


def due_before_issue(inv: Invoice) -> list[str]:
    issued, due = inv.invoice_date.value, inv.due_date.value
    if issued is None or due is None or due >= issued:
        return []
    return [f"Due date {due.isoformat()} is before invoice date {issued.isoformat()}"]


def injection_text(text: str) -> list[str]:
    match = INJECTION.search(text)
    if not match:
        return []
    return [f'Document contains instructions aimed at an AI system: "{match.group(0).strip()}"']


def unverified_fields(grounded: dict[str, bool]) -> list[str]:
    return [
        f"{FIELD_LABELS[name].capitalize()} could not be verified against the document"
        for name, verified in grounded.items() if not verified
    ]


def check(inv: Invoice, text: str, grounded: dict[str, bool] | None = None) -> tuple[str, ...]:
    """All rule failures for an invoice; empty means every rule passed.

    grounded maps each extracted field to whether its evidence was verified.
    """
    if inv.doc_type == "not_invoice":
        return ()
    currency = inv.currency.value
    return tuple(
        missing_fields(inv)
        + unverified_fields(grounded or {})
        + bad_line_amounts(inv.line_items, currency)
        + line_sum_mismatch(inv, currency)
        + total_mismatch(inv, currency)
        + due_before_issue(inv)
        + injection_text(text)
    )

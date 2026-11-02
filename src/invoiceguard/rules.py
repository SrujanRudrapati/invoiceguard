"""Business rules over an extracted invoice. Each failure is a specific, human-readable reason."""

import re
from dataclasses import dataclass
from decimal import Decimal

from invoiceguard.schema import FIELD_LABELS, REQUIRED_FIELDS, Invoice, LineItem

TOLERANCE = Decimal("0.01")
SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}
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
        f"{i.description}: {i.quantity.normalize():f} x {money(i.unit_price, currency)} is "
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


def due_before_issue(inv: Invoice, unverified: dict[str, str]) -> list[str]:
    """Skipped when either date is unverified: a misread date would produce a false chip."""
    if {"invoice_date", "due_date"} & unverified.keys():
        return []
    issued, due = inv.invoice_date.value, inv.due_date.value
    if issued is None or due is None or due >= issued:
        return []
    return [f"Due date {due.isoformat()} is before invoice date {issued.isoformat()}"]


def injection_text(text: str) -> list[str]:
    match = INJECTION.search(text)
    if not match:
        return []
    start = text.rfind("\n", 0, match.start()) + 1
    end = text.find("\n", match.end())
    line = text[start:end if end >= 0 else len(text)].strip()
    return [f'Document contains instructions aimed at an AI system: "{line}"']


@dataclass(frozen=True)
class RuleResult:
    name: str
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


def evaluate(inv: Invoice, text: str,
             unverified: dict[str, str] | None = None) -> tuple[RuleResult, ...]:
    """Every rule with its outcome, in display order. Non-invoices have no rules."""
    if inv.doc_type == "not_invoice":
        return ()
    unverified = unverified or {}
    currency = inv.currency.value
    return (
        RuleResult("Required fields present", tuple(missing_fields(inv))),
        RuleResult("Evidence found in the document", tuple(unverified.values())),
        RuleResult("Line amounts equal quantity times price",
                   tuple(bad_line_amounts(inv.line_items, currency))),
        RuleResult("Line items add to subtotal", tuple(line_sum_mismatch(inv, currency))),
        RuleResult("Subtotal plus tax equals total", tuple(total_mismatch(inv, currency))),
        RuleResult("Due date on or after invoice date",
                   tuple(due_before_issue(inv, unverified))),
        RuleResult("No instructions aimed at an AI system", tuple(injection_text(text))),
    )


def check(inv: Invoice, text: str, unverified: dict[str, str] | None = None) -> tuple[str, ...]:
    """All rule failures for an invoice; empty means every rule passed.

    unverified maps each field whose evidence did not check out to grounding's reason.
    """
    return tuple(f for rule in evaluate(inv, text, unverified) for f in rule.failures)

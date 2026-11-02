"""Route a document to approve / review / reject, with human-readable reasons."""

from dataclasses import dataclass

from invoiceguard.schema import REQUIRED_FIELDS, Invoice, Route


@dataclass(frozen=True)
class Decision:
    route: Route
    reasons: tuple[str, ...]


def route(invoice: Invoice, rule_failures: tuple[str, ...] = ()) -> Decision:
    """Reject only non-invoices; any missing field or failed rule sends the doc to a person."""
    if invoice.doc_type == "not_invoice":
        return Decision("reject", ("Not an invoice",))
    missing = tuple(
        f"Missing {name.replace('_', ' ')}"
        for name in REQUIRED_FIELDS
        if getattr(invoice, name).value is None
    )
    reasons = missing + rule_failures
    return Decision("review" if reasons else "approve", reasons)

"""Route a document to approve / review / reject, with human-readable reasons."""

from dataclasses import dataclass

from invoiceguard.schema import Invoice, Route


@dataclass(frozen=True)
class Decision:
    route: Route
    reasons: tuple[str, ...]


def route(invoice: Invoice, failures: tuple[str, ...] = ()) -> Decision:
    """Reject only non-invoices; any rule or grounding failure sends the doc to a person."""
    if invoice.doc_type == "not_invoice":
        return Decision("reject", ("Not an invoice",))
    return Decision("review" if failures else "approve", failures)

from datetime import date
from decimal import Decimal

from invoiceguard.route import route
from invoiceguard.schema import Extracted, Invoice


def complete_invoice() -> Invoice:
    return Invoice(
        doc_type="invoice", vendor_name=Extracted(value="Acme"),
        invoice_number=Extracted(value="A1"), invoice_date=Extracted(value=date(2026, 9, 1)),
        due_date=Extracted(value=date(2026, 10, 1)), currency=Extracted(value="USD"),
        subtotal=Extracted(value=Decimal("10")), tax=Extracted(value=Decimal("0")),
        total=Extracted(value=Decimal("10")),
    )


def test_non_invoice_is_rejected():
    assert route(Invoice(doc_type="not_invoice")).route == "reject"


def test_complete_invoice_without_po_is_approved():
    decision = route(complete_invoice())
    assert (decision.route, decision.reasons) == ("approve", ())


def test_missing_field_goes_to_review_with_specific_reason():
    inv = complete_invoice().model_copy(update={"due_date": Extracted()})
    decision = route(inv)
    assert (decision.route, decision.reasons) == ("review", ("Missing due date",))


def test_rule_failures_go_to_review():
    decision = route(complete_invoice(), ("Total does not match",))
    assert decision.route == "review"

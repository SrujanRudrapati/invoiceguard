import pytest

from invoiceguard.route import route
from invoiceguard.schema import Invoice

INVOICE = Invoice(doc_type="invoice")
NOT_INVOICE = Invoice(doc_type="not_invoice")


@pytest.mark.parametrize(
    ("invoice", "failures", "expected_route", "expected_reasons"),
    [
        (NOT_INVOICE, (), "reject", ("Not an invoice",)),
        (NOT_INVOICE, ("Missing total",), "reject", ("Not an invoice",)),
        (INVOICE, (), "approve", ()),
        (INVOICE, ("Missing due date",), "review", ("Missing due date",)),
        (INVOICE, ("a", "b"), "review", ("a", "b")),
    ],
)
def test_routing_table(invoice, failures, expected_route, expected_reasons):
    decision = route(invoice, failures)
    assert (decision.route, decision.reasons) == (expected_route, expected_reasons)

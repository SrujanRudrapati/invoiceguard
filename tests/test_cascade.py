"""Cascade decisions with a fake extract(): who escalates, who doesn't, and what it costs."""

from datetime import date
from decimal import Decimal

import pytest

from invoiceguard import cascade, extract_llm
from invoiceguard.config import HAIKU_MODEL, SONNET_MODEL
from invoiceguard.extract_llm import ExtractionFailed, LLMResult
from invoiceguard.ingest import Document
from invoiceguard.schema import Extracted, Invoice

TEXT = ("Acme Co\nInvoice number: A1\nInvoice date: 2026-09-01\nDue date: 2026-10-01\n"
        "Currency: USD\nSubtotal: 10.00\nTax: 0.00\nTotal: 10.00")
AMBIGUOUS_TEXT = TEXT.replace("2026-09-01", "10/05/2026").replace("2026-10-01", "11/04/2026")


def doc(text: str = TEXT) -> Document:
    return Document(text=text, boxes=(None,) * len(text))


def good_invoice(**overrides) -> Invoice:
    fields = {
        "vendor_name": Extracted(value="Acme Co", evidence="Acme Co"),
        "invoice_number": Extracted(value="A1", evidence="Invoice number: A1"),
        "invoice_date": Extracted(value=date(2026, 9, 1), evidence="Invoice date: 2026-09-01"),
        "due_date": Extracted(value=date(2026, 10, 1), evidence="Due date: 2026-10-01"),
        "currency": Extracted(value="USD", evidence="Currency: USD"),
        "subtotal": Extracted(value=Decimal("10.00"), evidence="Subtotal: 10.00"),
        "tax": Extracted(value=Decimal("0.00"), evidence="Tax: 0.00"),
        "total": Extracted(value=Decimal("10.00"), evidence="Total: 10.00"),
    }
    return Invoice(doc_type="invoice", **{**fields, **overrides})


@pytest.fixture
def fake(monkeypatch):
    """Script per-model outcomes; record which models were called."""
    outcomes: dict[str, object] = {}
    calls: list[str] = []

    def extract(doc, model, client):
        calls.append(model)
        outcome = outcomes[model]
        if isinstance(outcome, Exception):
            raise outcome
        return LLMResult(outcome, usd=0.001 if model == HAIKU_MODEL else 0.01, attempts=1)

    monkeypatch.setattr(extract_llm, "extract", extract)
    monkeypatch.setattr(extract_llm, "make_client", lambda: object())
    return outcomes, calls


def run(text: str = TEXT):
    return cascade.cascade_extractor()(doc(text))


def test_verified_haiku_result_is_kept(fake):
    outcomes, calls = fake
    outcomes[HAIKU_MODEL] = good_invoice()
    result = run()
    assert calls == [HAIKU_MODEL] and not result.escalated and result.usd == 0.001


def test_unverified_required_field_escalates_and_routes_on_sonnet(fake):
    outcomes, calls = fake
    outcomes[HAIKU_MODEL] = good_invoice(total=Extracted(value=Decimal("0"),
                                                         evidence="Total: 10.00"))
    outcomes[SONNET_MODEL] = good_invoice()
    result = run()
    assert calls == [HAIKU_MODEL, SONNET_MODEL]
    assert result.escalated and result.model == SONNET_MODEL
    assert result.invoice.total.value == Decimal("10.00")
    assert result.usd == pytest.approx(0.011)


def test_haiku_extraction_failure_escalates_and_keeps_its_cost(fake):
    outcomes, calls = fake
    outcomes[HAIKU_MODEL] = ExtractionFailed("bad json twice", usd=0.002)
    outcomes[SONNET_MODEL] = good_invoice()
    result = run()
    assert result.escalated and result.usd == pytest.approx(0.012)


def test_arithmetic_error_does_not_escalate(fake):
    outcomes, calls = fake
    wrong_math = TEXT.replace("Total: 10.00", "Total: 99.00")
    outcomes[HAIKU_MODEL] = good_invoice(total=Extracted(value=Decimal("99.00"),
                                                         evidence="Total: 99.00"))
    assert not run(wrong_math).escalated and calls == [HAIKU_MODEL]


def test_ambiguous_date_does_not_escalate(fake):
    outcomes, calls = fake
    outcomes[HAIKU_MODEL] = good_invoice(
        invoice_date=Extracted(value=date(2026, 10, 5), evidence="Invoice date: 10/05/2026"),
        due_date=Extracted(value=date(2026, 11, 4), evidence="Due date: 11/04/2026"))
    assert not run(AMBIGUOUS_TEXT).escalated and calls == [HAIKU_MODEL]


def test_field_absent_from_page_does_not_escalate(fake):
    outcomes, calls = fake
    outcomes[HAIKU_MODEL] = good_invoice(due_date=Extracted())
    assert not run().escalated


def test_non_invoice_does_not_escalate(fake):
    outcomes, calls = fake
    outcomes[HAIKU_MODEL] = Invoice(doc_type="not_invoice")
    assert not run().escalated


def test_sonnet_failure_becomes_failed_extraction(fake):
    outcomes, calls = fake
    outcomes[HAIKU_MODEL] = ExtractionFailed("bad", usd=0.002)
    outcomes[SONNET_MODEL] = ExtractionFailed("also bad", usd=0.02)
    result = run()
    assert result.escalated and result.error and result.usd == pytest.approx(0.022)

from datetime import date
from decimal import Decimal

import pytest

from invoiceguard.baseline import extract, extract_line_items, parse_date, parse_money
from invoiceguard.grounding import locate
from invoiceguard.ingest import Document, load_document


def doc_of(text: str) -> Document:
    return Document(text=text, boxes=(None,) * len(text))


TWO_COLUMN = """Keystone Freight Inc.
Invoice
Billed to Invoice number: F4444 PO number: PO-42966
Northwind Holdings LLC Invoice date: September 29, 2026 Currency: EUR
Due date: October 29, 2026
Description Qty Unit price Amount
Consulting hours 7.5 150.00 1,125.00
Subtotal: 1,125.00
Tax: 213.75
Total: 1,338.75"""

MESSY_RECEIPT = """Cedar & Pine Consulting
INVOICE
Inv #: INV-2026-8926
Dated: 13 Sep 2026
Amt Due: $1,540.00
Cleaning service
7 $220.00 $1,540.00
Net $1,540.00
VAT/Tax $0.00
Amt Due $1,540.00"""

STANDARD_RECEIPT = """Cedar & Pine Consulting
INVOICE
Invoice number: 10087
Cleaning service
7 220.00 1,540.00
Total 1,540.00"""


def test_parse_money_and_all_template_date_formats():
    assert parse_money("1,540.00") == Decimal("1540.00")
    expected = date(2026, 9, 13)
    for raw in ("2026-09-13", "September 13, 2026", "09/13/2026"):
        assert parse_date(raw) == expected


def test_messy_date_format_is_held_out():
    with pytest.raises(ValueError):
        parse_date("13 Sep 2026")


def test_two_column_layout_takes_only_the_value_token():
    inv = extract(doc_of(TWO_COLUMN))
    assert inv.invoice_number.value == "F4444"
    assert inv.po_number.value == "PO-42966"
    assert inv.invoice_date.value == date(2026, 9, 29)
    assert inv.currency.value == "EUR"
    assert inv.total.value == Decimal("1338.75")
    assert inv.vendor_name.value == "Keystone Freight Inc."


def test_messy_labels_are_held_out():
    inv = extract(doc_of(MESSY_RECEIPT))
    assert inv.doc_type == "invoice"
    assert inv.invoice_number.value is None
    assert inv.invoice_date.value is None
    assert inv.total.value is None
    assert inv.line_items == ()  # currency-symbol rows are not parsed


def test_receipt_rows_split_across_two_lines():
    inv = extract(doc_of(STANDARD_RECEIPT))
    assert inv.invoice_number.value == "10087"
    (item,) = inv.line_items
    assert (item.description, item.quantity, item.amount) == (
        "Cleaning service", Decimal("7"), Decimal("1540.00"))


def test_table_header_is_not_a_line_item():
    items = extract_line_items(TWO_COLUMN)
    assert [i.description for i in items] == ["Consulting hours"]


def test_document_without_the_word_invoice_is_not_an_invoice():
    assert extract(doc_of("Lumen Software Ltd\nQuotation\nQuote total: 9.00")).doc_type == (
        "not_invoice")


def test_evidence_is_a_quote_with_boxes_on_real_pdfs(generated):
    data_dir, rows = generated
    standard = (r for r in rows if r.fields.doc_type == "invoice" and r.category != "messy")
    for row in standard:
        doc = load_document(data_dir / row.file)
        total = extract(doc).total
        assert total.value is not None, row.doc_id
        assert locate(doc.text, total.evidence) is not None, row.doc_id
        assert total.evidence_boxes, row.doc_id

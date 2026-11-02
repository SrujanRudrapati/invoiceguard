from datetime import date
from decimal import Decimal

from invoiceguard.grounding import (
    Verification,
    dates_in,
    is_verified,
    locate,
    merge_line_boxes,
    normalize,
    slash_order,
    verify_invoice,
)
from invoiceguard.ingest import Document
from invoiceguard.schema import Box, Extracted, Invoice


def test_normalize_casefolds_collapses_whitespace_and_unifies_punctuation():
    assert normalize("  Total:\n\t 4,714.13 ") == "total: 4,714.13"
    assert normalize("“Net” 30 – days") == '"net" 30 - days'


def test_locate_returns_span_in_original_text():
    text = "Header\nDue   date:\n2026–11–25\nFooter"
    start, end = locate(text, "due date: 2026-11-25")
    assert text[start:end] == "Due   date:\n2026–11–25"


def test_locate_survives_casefold_expansion():
    text = "Straße GmbH Total: 10.00"
    start, end = locate(text, "total: 10.00")
    assert text[start:end] == "Total: 10.00"


def test_locate_rejects_paraphrase_and_empty_quote():
    assert locate("Total: 10.00", "Total 10.00") is None
    assert locate("Total: 10.00", "") is None
    assert locate("Total: 10.00", None) is None


def test_merge_line_boxes_unions_per_line_and_skips_gaps():
    a = Box(page=0, x0=10, top=100, x1=15, bottom=110)
    b = Box(page=0, x0=15, top=100.5, x1=20, bottom=110)
    c = Box(page=0, x0=10, top=120, x1=14, bottom=130)
    merged = merge_line_boxes((a, None, b, None, c))
    assert merged == (Box(page=0, x0=10, top=100, x1=20, bottom=110), c)


# ---------- value consistency ----------

DOC_TEXT = "Acme Co\nInvoice date: 03 Nov 2026\nInv #:  INV-7\nTotal: 6,447.00\nTax: 0.00"


def doc() -> Document:
    return Document(text=DOC_TEXT, boxes=(None,) * len(DOC_TEXT))


def test_quote_exists_but_value_contradicts_it_is_unverified():
    field = Extracted(value=Decimal("0"), evidence="Total: 6,447.00")
    assert not is_verified(doc(), field)


def test_money_value_matches_quote_numerically():
    assert is_verified(doc(), Extracted(value=Decimal("6447"), evidence="Total: 6,447.00"))
    assert is_verified(doc(), Extracted(value=Decimal("0.00"), evidence="Tax: 0.00"))


def test_date_value_parsed_from_quote():
    assert is_verified(doc(), Extracted(value=date(2026, 11, 3),
                                        evidence="Invoice date: 03 Nov 2026"))
    assert not is_verified(doc(), Extracted(value=date(2026, 3, 11),
                                            evidence="Invoice date: 03 Nov 2026"))


def test_string_value_must_be_contained_and_whitespace_is_normalized():
    assert is_verified(doc(), Extracted(value="INV-7", evidence="inv #: inv-7"))
    assert not is_verified(doc(), Extracted(value="INV-8", evidence="Inv #: INV-7"))


def test_missing_or_absent_quote_is_unverified():
    assert not is_verified(doc(), Extracted(value=Decimal("6447"), evidence=None))
    assert not is_verified(doc(), Extracted(value=Decimal("6447"), evidence="Total: 6447.00"))


# ---------- slash dates: order resolved per document ----------


def text_doc(text: str) -> Document:
    return Document(text=text, boxes=(None,) * len(text))


def test_slash_order_comes_from_any_unambiguous_date_on_the_page():
    assert slash_order("Invoice date: 09/26/2026\nDue date: 11/10/2026") == "MDY"
    assert slash_order("Invoice date: 26/09/2026\nDue date: 10/11/2026") == "DMY"
    assert slash_order("Invoice date: 10/05/2026\nDue date: 11/04/2026") is None
    assert slash_order("no dates here") is None


def test_resolved_document_reads_ambiguous_date_in_document_order():
    doc = text_doc("Invoice date: 09/26/2026\nDue date: 11/10/2026")
    checks = verify_invoice(doc, Invoice(
        doc_type="invoice",
        due_date=Extracted(value=date(2026, 11, 10), evidence="Due date: 11/10/2026")))
    assert checks["due_date"] == Verification(True)


def test_misread_on_resolved_document_is_unverified_not_ambiguous():
    doc = text_doc("Invoice date: 09/26/2026\nDue date: 11/10/2026")
    checks = verify_invoice(doc, Invoice(
        doc_type="invoice",
        due_date=Extracted(value=date(2026, 10, 11), evidence="Due date: 11/10/2026")))
    assert checks["due_date"] == Verification(
        False, "Due date could not be verified against the document")


def test_all_ambiguous_document_gets_specific_reason_and_no_escalation_flag():
    doc = text_doc("Invoice date: 10/05/2026\nDue date: 11/04/2026")
    checks = verify_invoice(doc, Invoice(
        doc_type="invoice",
        invoice_date=Extracted(value=date(2026, 10, 5), evidence="Invoice date: 10/05/2026")))
    assert checks["invoice_date"] == Verification(
        False, "Ambiguous date 10/05/2026 (MM/DD or DD/MM)", ambiguous=True)


def test_same_day_and_month_is_not_ambiguous():
    doc = text_doc("Invoice date: 05/05/2026")
    field = Extracted(value=date(2026, 5, 5), evidence="Invoice date: 05/05/2026")
    assert verify_invoice(doc, Invoice(doc_type="invoice", invoice_date=field))[
        "invoice_date"].verified


def test_other_date_formats_are_unaffected_by_slash_order():
    assert dates_in("Dated: 03 Nov 2026", order=None) == {date(2026, 11, 3)}

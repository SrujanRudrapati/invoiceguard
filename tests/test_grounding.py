from datetime import date
from decimal import Decimal

from invoiceguard.grounding import dates_in, is_verified, locate, merge_line_boxes, normalize
from invoiceguard.ingest import Document
from invoiceguard.schema import Box, Extracted


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


def test_slash_dates_accept_either_reading():
    assert date(2026, 11, 3) in dates_in("Due: 11/03/2026")
    assert date(2026, 3, 11) in dates_in("Due: 11/03/2026")

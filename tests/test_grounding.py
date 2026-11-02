from invoiceguard.grounding import locate, merge_line_boxes, normalize
from invoiceguard.schema import Box


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

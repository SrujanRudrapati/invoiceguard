"""Hard set: labels written from fixed values, checked against the rendered PDFs."""

from decimal import Decimal

import pdfplumber
import pytest
from make_hard import DOCS, HARD_LABELS_PATH, generate

from invoiceguard.schema import LabelRow


@pytest.fixture(scope="module")
def hard(tmp_path_factory):
    out = tmp_path_factory.mktemp("hard")
    rows = generate(out / "hard", out / "labels_hard.jsonl")
    return out, rows


def text_of(path) -> tuple[str, int]:
    with pdfplumber.open(path) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages), len(pdf.pages)


def test_six_schema_valid_rows_one_per_difficulty(hard):
    out, rows = hard
    parsed = [LabelRow.model_validate_json(line)
              for line in (out / "labels_hard.jsonl").read_text().splitlines()]
    assert len(parsed) == 6 and {r.defects[0] for r in parsed} == {d.defect for d in DOCS}
    assert all((out / r.file).exists() for r in parsed)


def test_labels_add_up(hard):
    _, rows = hard
    for row in rows:
        f = row.fields
        assert sum((i.amount for i in f.line_items), Decimal("0")) == f.subtotal, row.doc_id
        assert f.subtotal + f.tax == f.total, row.doc_id


def test_printed_total_matches_label_in_document_format(hard):
    out, rows = hard
    for doc, row in zip(DOCS, rows, strict=True):
        text, _ = text_of(out / row.file)
        assert doc.fmt(row.fields.total) in text, row.doc_id


def test_specific_difficulties_are_really_on_the_page(hard):
    out, rows = hard
    by_id = {r.doc_id: r for r in rows}
    assert "1.706,46" in text_of(out / "hard/hard_001.pdf")[0]
    assert "One thousand two hundred fifty" in text_of(out / "hard/hard_002.pdf")[0]
    assert by_id["hard_003"].fields.total < 0 and by_id["hard_003"].expected_route == "review"
    assert "floor 3 east wing" in by_id["hard_004"].fields.line_items[0].description
    assert by_id["hard_005"].fields.vendor_name == "Northern Lights Industrial Supply Company Ltd."
    assert text_of(out / "hard/hard_006.pdf")[1] == 2


def test_committed_hard_labels_match_generator(hard):
    if not HARD_LABELS_PATH.exists():
        pytest.skip("run `make data` first")
    out, _ = hard
    assert HARD_LABELS_PATH.read_text() == (out / "labels_hard.jsonl").read_text()

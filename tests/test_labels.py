"""Generator output: label schema, category mix, and labels that match the rendered PDFs."""

from collections import Counter
from decimal import Decimal
from pathlib import Path

import pdfplumber
import pytest
from make_synthetic import INJECTION_TEXT, generate

from invoiceguard.config import LABELS_PATH
from invoiceguard.schema import REQUIRED_FIELDS, LabelRow

EXPECTED_COUNTS = {
    ("clean", "approve"): 12,
    ("messy", "approve"): 4,
    ("arithmetic_error", "review"): 3,
    ("missing_field", "review"): 2,
    ("non_invoice", "reject"): 2,
    ("injection", "review"): 1,
}


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[LabelRow]]:
    out = tmp_path_factory.mktemp("data")
    generate(out / "docs", out / "labels.jsonl")
    lines = (out / "labels.jsonl").read_text().splitlines()
    return out, [LabelRow.model_validate_json(line) for line in lines]


def pdf_text(data_dir: Path, row: LabelRow) -> str:
    with pdfplumber.open(data_dir / row.file) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def arithmetic_checks(row: LabelRow) -> dict[str, bool]:
    f = row.fields
    return {
        "line_amounts": all(i.quantity * i.unit_price == i.amount for i in f.line_items),
        "line_sum": sum((i.amount for i in f.line_items), Decimal("0")) == f.subtotal,
        "total": f.subtotal + f.tax == f.total,
    }


def test_writes_24_pdfs_and_24_schema_valid_rows(generated):
    data_dir, rows = generated
    assert len(rows) == 24
    assert len(list((data_dir / "docs").glob("*.pdf"))) == 24
    assert len({r.doc_id for r in rows}) == 24
    assert all((data_dir / r.file).exists() and r.source == "synthetic" for r in rows)


def test_category_mix_and_routes(generated):
    _, rows = generated
    assert Counter((r.category, r.expected_route) for r in rows) == EXPECTED_COUNTS


def test_approve_docs_are_complete_and_add_up(generated):
    _, rows = generated
    for row in (r for r in rows if r.expected_route == "approve"):
        assert all(getattr(row.fields, name) is not None for name in REQUIRED_FIELDS), row.doc_id
        assert row.fields.line_items, row.doc_id
        assert all(arithmetic_checks(row).values()), row.doc_id


def test_each_arithmetic_error_breaks_exactly_one_check(generated):
    _, rows = generated
    broken = [r for r in rows if r.category == "arithmetic_error"]
    failures = [[k for k, ok in arithmetic_checks(r).items() if not ok] for r in broken]
    assert sorted(f[0] for f in failures) == ["line_amounts", "line_sum", "total"]
    assert all(len(f) == 1 for f in failures)


def test_missing_field_docs_lack_exactly_that_field(generated):
    _, rows = generated
    missing = {r.defects[0]: r for r in rows if r.category == "missing_field"}
    assert missing.keys() == {"missing_invoice_number", "missing_due_date"}
    assert missing["missing_invoice_number"].fields.invoice_number is None
    assert missing["missing_due_date"].fields.due_date is None


def test_non_invoices_carry_only_doc_type(generated):
    _, rows = generated
    for row in (r for r in rows if r.category == "non_invoice"):
        assert row.fields.doc_type == "not_invoice"
        assert all(getattr(row.fields, name) is None for name in REQUIRED_FIELDS)


def test_printed_text_matches_labels(generated):
    data_dir, rows = generated
    for row in (r for r in rows if r.fields.doc_type == "invoice"):
        text = pdf_text(data_dir, row)
        assert row.fields.vendor_name in text, row.doc_id
        assert f"{row.fields.total:,.2f}" in text, row.doc_id
        if row.fields.invoice_number:
            assert row.fields.invoice_number in text, row.doc_id


def test_injection_footer_is_printed_and_never_approved(generated):
    data_dir, rows = generated
    (row,) = [r for r in rows if r.category == "injection"]
    assert INJECTION_TEXT in pdf_text(data_dir, row)
    assert row.expected_route == "review"


def test_generation_is_deterministic(generated, tmp_path):
    data_dir, _ = generated
    generate(tmp_path / "docs", tmp_path / "labels.jsonl")
    assert (tmp_path / "labels.jsonl").read_text() == (data_dir / "labels.jsonl").read_text()
    for pdf in (data_dir / "docs").glob("*.pdf"):
        assert (tmp_path / "docs" / pdf.name).read_bytes() == pdf.read_bytes(), pdf.name


def test_committed_labels_match_generator(generated):
    if not LABELS_PATH.exists():
        pytest.skip("run `make data` first")
    data_dir, _ = generated
    assert LABELS_PATH.read_text() == (data_dir / "labels.jsonl").read_text()

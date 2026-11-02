from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from run_eval import evaluate
from scoring import (
    DocRecord,
    aggregate,
    line_item_match,
    norm_value,
    percentile,
    score_fields,
    verified_wrong,
)

from invoiceguard.pipeline import baseline_extractor
from invoiceguard.schema import InvoiceFields, LineItem

ITEM = LineItem(description="Chair", quantity=Decimal("2"), unit_price=Decimal("5"),
                amount=Decimal("10"))
RECORD = DocRecord(
    doc_id="d", source="synthetic", gold_route="approve", pred_route="approve", reasons=(),
    field_hits={"total": True}, items_matched=1, items_total=1, exact=True,
    grounded={"total": True}, latency_ms=10.0, usd=0.0, escalated=False,
)


def test_norm_value_formats():
    assert norm_value(date(2026, 11, 3)) == "2026-11-03"
    assert norm_value(Decimal("4812.5")) == "4812.50"
    assert norm_value("  ACME   Corp ") == "acme corp"
    assert norm_value(None) is None


def test_line_item_extra_rows_count_against_accuracy():
    assert line_item_match((ITEM,), (ITEM, ITEM)) == (1, 2)
    assert line_item_match((ITEM,), ()) == (0, 1)


def test_score_fields_counts_absent_po_as_correct_and_non_invoice_by_type():
    gold = InvoiceFields(doc_type="invoice", total=Decimal("10.00"), line_items=(ITEM,))
    hits, matched, total, exact = score_fields(gold, gold.model_copy(
        update={"total": Decimal("10")}))
    assert hits["po_number"] and hits["total"] and exact and (matched, total) == (1, 1)
    not_inv = InvoiceFields(doc_type="not_invoice")
    assert score_fields(not_inv, gold) == (None, 0, 0, False)


def test_percentile_nearest_rank():
    values = [float(v) for v in range(1, 21)]
    assert percentile(values, 50) == 10.0
    assert percentile(values, 95) == 19.0


def test_review_recall_is_strict_reject_of_a_review_doc_is_a_miss():
    records = [
        replace(RECORD, gold_route="review", pred_route="review"),
        replace(RECORD, gold_route="review", pred_route="approve"),
        replace(RECORD, gold_route="review", pred_route="reject"),
        replace(RECORD, gold_route="reject", pred_route="approve"),
    ]
    metrics = aggregate(records)
    assert (metrics["review_caught"], metrics["review_n"]) == (1, 3)
    assert metrics["reject_acc"] == 0.0
    assert metrics["confusion"]["review"] == {"approve": 1, "review": 1, "reject": 1}


def test_aggregate_of_empty_set_is_all_none():
    metrics = aggregate([])
    assert metrics["n_docs"] == 0 and metrics["field_acc"] is None


@pytest.mark.integration
def test_baseline_end_to_end_on_generated_data(generated):
    data_dir, rows = generated
    records, results = evaluate(baseline_extractor, rows, data_dir)
    metrics = aggregate(records)
    assert metrics["n_docs"] == 24 and len(results) == 24
    assert metrics["verified_wrong"] == 0
    # regex quotes are literal text; only all-ambiguous slash dates stay unverified
    unverified = {(r.doc_id, name) for r in records for name, ok in r.grounded.items() if not ok}
    ambiguous_docs = {r.doc_id for r in rows if r.file in {"docs/doc_015.pdf", "docs/doc_020.pdf"}}
    assert unverified and {doc_id for doc_id, _ in unverified} == ambiguous_docs
    assert {name for _, name in unverified} <= {"invoice_date", "due_date"}


def test_verified_wrong_counts_only_verified_fields_with_wrong_values():
    records = [
        replace(RECORD, field_hits={"total": False, "tax": False, "vendor_name": True},
                grounded={"total": True, "tax": False, "vendor_name": True}),
        replace(RECORD, field_hits=None, grounded={"total": True}),  # non-invoice: not scored
    ]
    assert verified_wrong(records) == 1
    assert aggregate(records)["verified_wrong"] == 1

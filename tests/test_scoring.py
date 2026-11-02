from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from run_eval import evaluate
from scoring import DocRecord, aggregate, line_item_match, norm_value, percentile, score_fields

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


def test_review_recall_counts_review_docs_not_auto_approved():
    records = [
        replace(RECORD, gold_route="review", pred_route="approve"),
        replace(RECORD, gold_route="review", pred_route="reject"),
        replace(RECORD, gold_route="reject", pred_route="approve"),
    ]
    metrics = aggregate(records)
    assert (metrics["review_caught"], metrics["review_n"]) == (1, 2)
    assert metrics["reject_acc"] == 0.0
    assert metrics["confusion"]["review"] == {"approve": 1, "review": 0, "reject": 1}


def test_aggregate_of_empty_set_is_all_none():
    metrics = aggregate([])
    assert metrics["n_docs"] == 0 and metrics["field_acc"] is None


@pytest.mark.integration
def test_baseline_end_to_end_on_generated_data(generated):
    data_dir, rows = generated
    records, results = evaluate(baseline_extractor, rows, data_dir)
    metrics = aggregate(records)
    assert metrics["n_docs"] == 24 and len(results) == 24
    assert metrics["grounding"] == 1.0  # regex evidence is literal document text

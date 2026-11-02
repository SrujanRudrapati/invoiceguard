"""Pure scoring: per-doc records and aggregate metrics. No I/O here."""

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from statistics import mean

from invoiceguard.schema import SCALAR_FIELDS, InvoiceFields, LineItem

CENT = Decimal("0.01")
ROUTES = ("approve", "review", "reject")


@dataclass(frozen=True)
class DocRecord:
    doc_id: str
    source: str
    gold_route: str
    pred_route: str
    reasons: tuple[str, ...]
    field_hits: dict[str, bool] | None  # None when gold is not an invoice
    items_matched: int
    items_total: int
    exact: bool
    grounded: dict[str, bool]
    latency_ms: float
    usd: float
    escalated: bool
    predicted: dict = field(default_factory=dict)


def norm_value(value: object) -> str | None:
    """ISO dates, money/quantities to 2 dp, casefolded whitespace-collapsed strings."""
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value.quantize(CENT, ROUND_HALF_UP))
    return " ".join(str(value).split()).casefold()


def norm_item(item: LineItem) -> tuple[str | None, ...]:
    return tuple(norm_value(v) for v in (item.description, item.quantity, item.unit_price,
                                         item.amount))


def line_item_match(gold: tuple[LineItem, ...], pred: tuple[LineItem, ...]) -> tuple[int, int]:
    """(matched, max(len gold, len pred)): extra predicted rows count against accuracy."""
    matched = Counter(map(norm_item, gold)) & Counter(map(norm_item, pred))
    return sum(matched.values()), max(len(gold), len(pred))


def score_fields(gold: InvoiceFields, pred: InvoiceFields) -> tuple[dict | None, int, int, bool]:
    """(field_hits, items_matched, items_total, doc_exact)."""
    type_ok = gold.doc_type == pred.doc_type
    if gold.doc_type == "not_invoice":
        return None, 0, 0, type_ok
    hits = {n: norm_value(getattr(gold, n)) == norm_value(getattr(pred, n)) for n in SCALAR_FIELDS}
    matched, total = line_item_match(gold.line_items, pred.line_items)
    return hits, matched, total, type_ok and all(hits.values()) and matched == total


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile."""
    ordered = sorted(values)
    return ordered[max(math.ceil(pct / 100 * len(ordered)) - 1, 0)]


def ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def confusion(records: list[DocRecord]) -> dict[str, dict[str, int]]:
    counts = Counter((r.gold_route, r.pred_route) for r in records)
    return {g: {p: counts[(g, p)] for p in ROUTES} for g in ROUTES}


def field_counts(records: list[DocRecord]) -> tuple[int, int]:
    hits = [h for r in records if r.field_hits for h in r.field_hits.values()]
    return sum(hits), len(hits)


def aggregate(records: list[DocRecord]) -> dict:
    field_hit, field_n = field_counts(records)
    review = [r for r in records if r.gold_route == "review"]
    reject = [r for r in records if r.gold_route == "reject"]
    grounded = [g for r in records for g in r.grounded.values()]
    latencies = [r.latency_ms for r in records]
    return {
        "n_docs": len(records),
        "field_acc": ratio(field_hit, field_n),
        "line_item_acc": ratio(sum(r.items_matched for r in records),
                               sum(r.items_total for r in records)),
        "doc_exact": ratio(sum(r.exact for r in records), len(records)),
        "review_caught": sum(r.pred_route != "approve" for r in review),
        "review_n": len(review),
        "review_recall": ratio(sum(r.pred_route != "approve" for r in review), len(review)),
        "reject_acc": ratio(sum(r.pred_route == "reject" for r in reject), len(reject)),
        "auto_approve": ratio(sum(r.pred_route == "approve" for r in records), len(records)),
        "grounding": ratio(sum(grounded), len(grounded)),
        "escalation_rate": ratio(sum(r.escalated for r in records), len(records)),
        "p50_ms": percentile(latencies, 50) if latencies else None,
        "p95_ms": percentile(latencies, 95) if latencies else None,
        "usd_per_doc": mean(r.usd for r in records) if records else None,
        "confusion": confusion(records),
    }

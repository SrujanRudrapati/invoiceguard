"""Reviewer actions. A save with edits also becomes a new eval case (source "reviewer")."""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import InvalidOperation
from pathlib import Path

from invoiceguard import store
from invoiceguard.extract_llm import DATE_FIELDS, MONEY_FIELDS, parse_scalar
from invoiceguard.logging_utils import append_jsonl
from invoiceguard.schema import SCALAR_FIELDS, Invoice, InvoiceFields, LabelRow, field_label

log = logging.getLogger(__name__)


class ReviewError(Exception):
    pass


class NotFound(ReviewError):
    pass


class AlreadyReviewed(ReviewError):
    pass


class InvalidEdit(ReviewError):
    pass


@dataclass(frozen=True)
class ReviewOutcome:
    review_id: int
    action: str
    added_to_eval_set: bool


def parse_edit(name: str, raw: str | None) -> object:
    if name not in SCALAR_FIELDS:
        raise InvalidEdit(f"Unknown field: {name}")
    if raw is None or not raw.strip():
        return None
    label = field_label(name)
    try:
        return parse_scalar(name, raw.strip())
    except (InvalidOperation, ValueError) as exc:
        if name in MONEY_FIELDS:
            raise InvalidEdit(f"{label} must be a number like 4812.50") from exc
        if name in DATE_FIELDS:
            raise InvalidEdit(f"{label} must be a date like 2026-12-01") from exc
        raise InvalidEdit(f"{label} is not valid") from exc


def corrected_fields(invoice: Invoice, edits: dict[str, str | None]) -> InvoiceFields:
    """The extracted values with the reviewer's edits applied; validates every edit first."""
    parsed = {name: parse_edit(name, raw) for name, raw in edits.items()}
    return invoice.values().model_copy(update=parsed)


def pending(conn: sqlite3.Connection, doc_id: str) -> tuple[sqlite3.Row, sqlite3.Row]:
    doc, extraction = store.document(conn, doc_id), store.latest_extraction(conn, doc_id)
    if doc is None or extraction is None:
        raise NotFound(f"No document {doc_id}")
    if store.is_reviewed(conn, doc_id):
        raise AlreadyReviewed(f"{doc_id} was already reviewed")
    return doc, extraction


def append_eval_case(path: Path, doc_id: str, file: str, fields: InvoiceFields) -> None:
    row = LabelRow(doc_id=doc_id, file=file, source="reviewer", category="reviewed",
                   expected_route="approve", fields=fields, reviewed_at=datetime.now(UTC))
    append_jsonl(path, row.model_dump(mode="json"))


def approve(conn: sqlite3.Connection, doc_id: str, edits: dict[str, str | None],
            eval_path: Path) -> ReviewOutcome:
    doc, extraction = pending(conn, doc_id)
    if not edits:
        review_id = store.add_review(conn, doc_id, extraction["id"], "approve")
        return ReviewOutcome(review_id, "approve", added_to_eval_set=False)
    invoice = Invoice.model_validate_json(extraction["invoice_json"])
    fields = corrected_fields(invoice, edits)  # raises before anything is written
    review_id = store.add_review(conn, doc_id, extraction["id"], "save_and_approve", fields)
    append_eval_case(eval_path, doc_id, doc["file"], fields)
    with conn:
        store.audit(conn, "eval_set", doc_id, "added",
                    {"doc_id": doc_id, "review_id": review_id, "edited": sorted(edits)})
    log.info("review %s: %s corrected %s, added to eval set", review_id, doc_id, sorted(edits))
    return ReviewOutcome(review_id, "save_and_approve", added_to_eval_set=True)


def reject(conn: sqlite3.Connection, doc_id: str) -> ReviewOutcome:
    _, extraction = pending(conn, doc_id)
    review_id = store.add_review(conn, doc_id, extraction["id"], "reject")
    return ReviewOutcome(review_id, "reject", added_to_eval_set=False)

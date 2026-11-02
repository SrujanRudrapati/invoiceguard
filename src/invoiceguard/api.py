"""FastAPI for the review app. Local tool: no auth by design (see CLAUDE.md).

Run: uv run uvicorn invoiceguard.api:app --port 8000
"""

import json
import logging
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from invoiceguard import review, rules, store
from invoiceguard.config import DATA_DIR, DB_PATH, HISTORY_PATH, REVIEWED_LABELS_PATH
from invoiceguard.grounding import verify_invoice
from invoiceguard.ingest import load_document
from invoiceguard.schema import SCALAR_FIELDS, Invoice, field_label

log = logging.getLogger(__name__)
app = FastAPI(title="InvoiceGuard")
MONEY = {"subtotal", "tax", "total"}
DATES = {"invoice_date", "due_date"}


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edits: dict[str, str | None] = {}


def db_path() -> Path:
    return Path(os.environ.get("INVOICEGUARD_DB", DB_PATH))


def eval_path() -> Path:
    return Path(os.environ.get("INVOICEGUARD_REVIEWED_LABELS", REVIEWED_LABELS_PATH))


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = store.connect(db_path(), check_same_thread=False)  # one connection per request
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def http_error(exc: review.ReviewError) -> HTTPException:
    code = {review.NotFound: 404, review.AlreadyReviewed: 409, review.InvalidEdit: 422}
    return HTTPException(status_code=code.get(type(exc), 400), detail=str(exc))


def queue_item(row: sqlite3.Row) -> dict:
    values = Invoice.model_validate_json(row["invoice_json"]).values()
    return {"doc_id": row["doc_id"], "status": row["status"],
            "review_action": row["review_action"], "vendor": values.vendor_name,
            "total": None if values.total is None else str(values.total),
            "currency": values.currency, "reasons": json.loads(row["reasons_json"])}


@app.get("/queue")
def get_queue(conn: Conn,
              status: Literal["review", "approve", "reject"] = "review") -> list[dict]:
    return [queue_item(row) for row in store.queue(conn, status)]


def field_view(name: str, invoice: Invoice, checks: dict) -> dict:
    field, check = getattr(invoice, name), checks.get(name)
    kind = "money" if name in MONEY else "date" if name in DATES else "text"
    return {
        "name": name, "label": field_label(name), "kind": kind,
        "value": invoice.values().model_dump(mode="json")[name],
        "evidence": field.evidence, "boxes": [b.model_dump() for b in field.evidence_boxes],
        "verified": None if check is None else check.verified,
        "note": None if check is None or check.verified else check.reason,
    }


def doc_detail(doc_id: str, conn: sqlite3.Connection) -> dict:
    doc, row = store.document(conn, doc_id), store.status_of(conn, doc_id)
    if doc is None or row is None:
        raise HTTPException(status_code=404, detail=f"No document {doc_id}")
    invoice = Invoice.model_validate_json(row["invoice_json"])
    pdf = load_document(DATA_DIR / doc["file"])
    checks = verify_invoice(pdf, invoice)
    unverified = {n: c.reason for n, c in checks.items() if not c.verified}
    return {
        "doc_id": doc_id, "status": row["status"], "route": row["route"],
        "review_action": row["review_action"], "model": row["model"],
        "escalated": bool(row["escalated"]), "doc_type": invoice.doc_type,
        "currency": invoice.currency.value, "reasons": json.loads(row["reasons_json"]),
        "page_sizes": [list(size) for size in pdf.page_sizes],
        "fields": [field_view(n, invoice, checks) for n in SCALAR_FIELDS],
        "line_items": [item.model_dump(mode="json") for item in invoice.line_items],
        "rules": [{"name": r.name, "passed": r.passed, "failures": list(r.failures)}
                  for r in rules.evaluate(invoice, pdf.text, unverified)],
        "audit": [{"action": a["action"], "entity": a["entity"], "at": a["created_at"],
                   "detail": json.loads(a["detail_json"])} for a in store.audit_for(conn, doc_id)],
    }


@app.get("/docs/{doc_id}")
def get_doc(doc_id: str, conn: Conn) -> dict:
    return doc_detail(doc_id, conn)


@app.get("/docs/{doc_id}/pdf")
def get_pdf(doc_id: str, conn: Conn) -> FileResponse:
    doc = store.document(conn, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"No document {doc_id}")
    path = (DATA_DIR / doc["file"]).resolve()
    if DATA_DIR.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(path, media_type="application/pdf")


@app.post("/docs/{doc_id}/approve")
def post_approve(doc_id: str, body: ApproveRequest,
                 conn: Conn) -> dict:
    try:
        outcome = review.approve(conn, doc_id, body.edits, eval_path())
    except review.ReviewError as exc:
        raise http_error(exc) from exc
    return {"review_id": outcome.review_id, "action": outcome.action,
            "added_to_eval_set": outcome.added_to_eval_set}


@app.post("/docs/{doc_id}/reject")
def post_reject(doc_id: str, conn: Conn) -> dict:
    try:
        outcome = review.reject(conn, doc_id)
    except review.ReviewError as exc:
        raise http_error(exc) from exc
    return {"review_id": outcome.review_id, "action": outcome.action, "added_to_eval_set": False}


def read_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@app.get("/evals")
def get_evals() -> dict:
    """All history rows, plus the latest tag's row per (set, system) for the results table."""
    history = read_history(HISTORY_PATH)
    latest_tag = history[-1]["tag"] if history else None
    latest = {}
    for row in history:
        if row["tag"] == latest_tag:
            latest[f'{row.get("set", "main")}/{row["system"]}'] = row
    return {"latest_tag": latest_tag, "latest": list(latest.values()), "history": history}

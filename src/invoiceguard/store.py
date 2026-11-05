"""SQLite store: documents, extractions, reviews, and an audit_log row for every write."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from invoiceguard.pipeline import DocResult
from invoiceguard.schema import InvoiceFields

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    file TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
    system TEXT NOT NULL,
    model TEXT NOT NULL,
    invoice_json TEXT NOT NULL,
    route TEXT NOT NULL CHECK (route IN ('approve', 'review', 'reject')),
    reasons_json TEXT NOT NULL,
    grounded_json TEXT NOT NULL,
    usd REAL NOT NULL,
    latency_ms REAL NOT NULL,
    escalated INTEGER NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id),
    extraction_id INTEGER NOT NULL REFERENCES extractions(id),
    action TEXT NOT NULL CHECK (action IN ('approve', 'save_and_approve', 'reject')),
    corrected_json TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(path: Path | str, check_same_thread: bool = True) -> sqlite3.Connection:
    """check_same_thread=False only for one-connection-per-request use (FastAPI may open and
    close a sync dependency on different worker threads)."""
    conn = sqlite3.connect(path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def audit(conn: sqlite3.Connection, entity: str, entity_id: object, action: str,
          detail: dict) -> None:
    conn.execute(
        "INSERT INTO audit_log (entity, entity_id, action, detail_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (entity, str(entity_id), action, json.dumps(detail, default=str), now()),
    )


def add_document(conn: sqlite3.Connection, doc_id: str, file: str) -> None:
    with conn:
        conn.execute("INSERT OR IGNORE INTO documents (doc_id, file, created_at) VALUES (?, ?, ?)",
                     (doc_id, file, now()))
        audit(conn, "document", doc_id, "ingested", {"file": file})


def save_extraction(conn: sqlite3.Connection, doc_id: str, system: str,
                    result: DocResult) -> int:
    ext, decision = result.extraction, result.decision
    with conn:
        cursor = conn.execute(
            "INSERT INTO extractions (doc_id, system, model, invoice_json, route, reasons_json,"
            " grounded_json, usd, latency_ms, escalated, error, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (doc_id, system, ext.model, ext.invoice.model_dump_json(), decision.route,
             json.dumps(decision.reasons), json.dumps(result.grounded), ext.usd,
             result.latency_ms, int(ext.escalated), ext.error, now()),
        )
        audit(conn, "extraction", cursor.lastrowid, "routed",
              {"doc_id": doc_id, "route": decision.route, "reasons": decision.reasons})
    return cursor.lastrowid


def add_review(conn: sqlite3.Connection, doc_id: str, extraction_id: int, action: str,
               corrected: InvoiceFields | None = None) -> int:
    corrected_json = corrected.model_dump_json() if corrected else None
    with conn:
        cursor = conn.execute(
            "INSERT INTO reviews (doc_id, extraction_id, action, corrected_json, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (doc_id, extraction_id, action, corrected_json, now()),
        )
        audit(conn, "review", cursor.lastrowid, action,
              {"doc_id": doc_id, "extraction_id": extraction_id, "corrected": bool(corrected)})
    return cursor.lastrowid


def latest_extraction(conn: sqlite3.Connection, doc_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM extractions WHERE doc_id = ? ORDER BY id DESC LIMIT 1", (doc_id,)
    ).fetchone()


def audit_entries(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()


def document(conn: sqlite3.Connection, doc_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()


def is_reviewed(conn: sqlite3.Connection, doc_id: str) -> bool:
    return conn.execute("SELECT 1 FROM reviews WHERE doc_id = ?", (doc_id,)).fetchone() is not None


STATUS_SQL = """
    SELECT e.*,
           CASE WHEN r.action IS NULL THEN e.route
                WHEN r.action = 'reject' THEN 'reject'
                ELSE 'approve' END AS status,
           r.action AS review_action
    FROM extractions e
    LEFT JOIN reviews r ON r.doc_id = e.doc_id
    WHERE e.id = (SELECT MAX(id) FROM extractions WHERE doc_id = e.doc_id)
"""


def queue(conn: sqlite3.Connection, status: str = "review") -> list[sqlite3.Row]:
    """Latest extraction per document with its status: the reviewer's decision if there is
    one, otherwise the system's route. status="review" is the work queue."""
    return conn.execute(f"SELECT * FROM ({STATUS_SQL}) WHERE status = ? ORDER BY doc_id",
                        (status,)).fetchall()


def status_of(conn: sqlite3.Connection, doc_id: str) -> sqlite3.Row | None:
    return conn.execute(f"SELECT * FROM ({STATUS_SQL}) WHERE doc_id = ?", (doc_id,)).fetchone()


def audit_for(conn: sqlite3.Connection, doc_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM audit_log
        WHERE (entity = 'document' AND entity_id = ?)
           OR json_extract(detail_json, '$.doc_id') = ?
        ORDER BY id
        """,
        (doc_id, doc_id),
    ).fetchall()


def systems_used(conn: sqlite3.Connection) -> list[str]:
    return [row["system"] for row in
            conn.execute("SELECT DISTINCT system FROM extractions ORDER BY system").fetchall()]

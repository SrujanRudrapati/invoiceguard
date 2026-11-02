import json
import sqlite3

import pytest

from invoiceguard import store
from invoiceguard.pipeline import DocResult, Extraction
from invoiceguard.route import Decision
from invoiceguard.schema import Invoice, InvoiceFields

RESULT = DocResult(
    extraction=Extraction(Invoice(doc_type="invoice"), model="claude-haiku-5-5", usd=0.0002),
    decision=Decision("review", ("Missing total",)),
    grounded={"vendor_name": True},
    latency_ms=812.0,
)


@pytest.fixture
def conn():
    connection = store.connect(":memory:")
    yield connection
    connection.close()


def test_extraction_round_trip_and_audit_trail(conn):
    store.add_document(conn, "doc_001", "docs/doc_001.pdf")
    ext_id = store.save_extraction(conn, "doc_001", "haiku", RESULT)
    store.add_review(conn, "doc_001", ext_id, "save_and_approve",
                     InvoiceFields(doc_type="invoice", total=None))

    row = store.latest_extraction(conn, "doc_001")
    assert (row["route"], json.loads(row["reasons_json"])) == ("review", ["Missing total"])
    assert Invoice.model_validate_json(row["invoice_json"]).doc_type == "invoice"
    actions = [(a["entity"], a["action"]) for a in store.audit_entries(conn)]
    assert actions == [("document", "ingested"), ("extraction", "routed"),
                       ("review", "save_and_approve")]


def test_review_action_is_constrained(conn):
    store.add_document(conn, "doc_001", "docs/doc_001.pdf")
    ext_id = store.save_extraction(conn, "doc_001", "haiku", RESULT)
    with pytest.raises(sqlite3.IntegrityError):
        store.add_review(conn, "doc_001", ext_id, "maybe")
    assert len(store.audit_entries(conn)) == 2  # failed write left no audit row


def test_extraction_requires_known_document(conn):
    with pytest.raises(sqlite3.IntegrityError):
        store.save_extraction(conn, "missing", "haiku", RESULT)

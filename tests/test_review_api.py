"""Review service + API handlers on a DB seeded offline with the regex system."""

import json

import pytest
from fastapi import HTTPException

from invoiceguard import api, review, store
from invoiceguard.pipeline import baseline_extractor, run_document
from invoiceguard.schema import LabelRow


@pytest.fixture
def seeded(generated, tmp_path, monkeypatch):
    data_dir, rows = generated
    monkeypatch.setattr(api, "DATA_DIR", data_dir)
    conn = store.connect(tmp_path / "test.sqlite3")
    for row in rows:
        store.add_document(conn, row.doc_id, row.file)
        store.save_extraction(conn, row.doc_id, "baseline",
                              run_document(data_dir / row.file, baseline_extractor))
    yield conn, rows, tmp_path / "labels_reviewed.jsonl"
    conn.close()


def review_doc_missing_due_date(rows) -> str:
    return next(r.doc_id for r in rows if "missing_due_date" in r.defects)


def eval_rows(path) -> list[LabelRow]:
    if not path.exists():
        return []
    return [LabelRow.model_validate_json(line) for line in path.read_text().splitlines()]


def test_save_and_approve_with_edit_adds_exactly_one_eval_row(seeded):
    conn, rows, eval_path = seeded
    doc_id = review_doc_missing_due_date(rows)
    outcome = review.approve(conn, doc_id, {"due_date": "2026-12-01"}, eval_path)

    (added,) = eval_rows(eval_path)
    assert outcome.added_to_eval_set and outcome.action == "save_and_approve"
    assert (added.doc_id, added.source) == (doc_id, "reviewer")
    assert added.fields.due_date.isoformat() == "2026-12-01" and added.reviewed_at
    actions = [(a["entity"], a["action"]) for a in store.audit_for(conn, doc_id)]
    assert ("review", "save_and_approve") in actions and ("eval_set", "added") in actions


def test_plain_approve_adds_no_eval_row(seeded):
    conn, rows, eval_path = seeded
    outcome = review.approve(conn, review_doc_missing_due_date(rows), {}, eval_path)
    assert not outcome.added_to_eval_set and eval_rows(eval_path) == []


def test_invalid_edit_writes_nothing(seeded):
    conn, rows, eval_path = seeded
    doc_id = review_doc_missing_due_date(rows)
    with pytest.raises(review.InvalidEdit, match="Due date must be a date like 2026-12-01"):
        review.approve(conn, doc_id, {"due_date": "next Tuesday"}, eval_path)
    assert not store.is_reviewed(conn, doc_id) and eval_rows(eval_path) == []


def test_second_decision_on_same_doc_is_refused(seeded):
    conn, rows, eval_path = seeded
    doc_id = review_doc_missing_due_date(rows)
    review.reject(conn, doc_id)
    with pytest.raises(review.AlreadyReviewed):
        review.approve(conn, doc_id, {}, eval_path)


def test_queue_filters_by_status_and_moves_reviewed_docs(seeded):
    conn, rows, eval_path = seeded
    to_review = api.get_queue(conn, "review")
    assert to_review and all(item["status"] == "review" for item in to_review)
    doc_id = to_review[0]["doc_id"]
    review.approve(conn, doc_id, {}, eval_path)
    assert doc_id not in {i["doc_id"] for i in api.get_queue(conn, "review")}
    assert doc_id in {i["doc_id"] for i in api.get_queue(conn, "approve")}
    assert {i["doc_id"] for i in api.get_queue(conn, "reject")} == {
        r.doc_id for r in rows if r.category == "non_invoice"}


def test_doc_detail_has_fields_boxes_rules_and_audit(seeded):
    conn, rows, _ = seeded
    clean = next(r.doc_id for r in rows if r.category == "clean")
    detail = api.get_doc(clean, conn)
    total = next(f for f in detail["fields"] if f["name"] == "total")
    assert total["verified"] and total["boxes"] and total["kind"] == "money"
    assert detail["page_sizes"] and detail["status"] == "approve"
    assert all(rule["passed"] for rule in detail["rules"])
    assert detail["audit"][0]["action"] == "ingested"
    json.dumps(detail)  # serializable as returned


def test_api_maps_errors_to_status_codes(seeded):
    conn, rows, _ = seeded
    with pytest.raises(HTTPException) as missing:
        api.get_doc("nope", conn)
    doc_id = review_doc_missing_due_date(rows)
    with pytest.raises(HTTPException) as invalid:
        api.post_approve(doc_id, api.ApproveRequest(edits={"total": "lots"}), conn)
    api.post_reject(doc_id, conn)
    with pytest.raises(HTTPException) as twice:
        api.post_reject(doc_id, conn)
    assert (missing.value.status_code, invalid.value.status_code,
            twice.value.status_code) == (404, 422, 409)


def test_evals_latest_ignores_untagged_runs(tmp_path, monkeypatch):
    rows = [{"tag": "v4", "system": "haiku", "set": "main"},
            {"tag": "v4", "system": "cascade", "set": "main"},
            {"tag": "", "system": "baseline", "set": "main"}]
    path = tmp_path / "history.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(api, "HISTORY_PATH", path)
    evals = api.get_evals()
    assert evals["latest_tag"] == "v4"
    assert {r["system"] for r in evals["latest"]} == {"haiku", "cascade"}
    assert len(evals["history"]) == 3

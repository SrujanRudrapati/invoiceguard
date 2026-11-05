"""SYSTEM=replay: recorded model responses (mocked) through live grounding, rules and routing."""

import json

import pytest

from invoiceguard import api, process, replay, store
from invoiceguard.ingest import Document, load_document
from invoiceguard.pipeline import run_document

RECORDINGS = [json.loads(line) for line in replay.RECORDED_PATH.read_text().splitlines()]


def test_recording_covers_the_main_set_and_cost_nothing_to_replay():
    assert len(RECORDINGS) == 24
    assert len({r["text_sha256"] for r in RECORDINGS}) == 24


def test_replay_reproduces_every_recorded_route_offline(generated, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    data_dir, rows = generated
    extractor = replay.replay_extractor()
    expected = {r["doc_id"]: r["recorded_route"] for r in RECORDINGS}
    for row in rows:
        result = run_document(data_dir / row.file, extractor)
        assert result.extraction.error is None, row.doc_id
        assert result.extraction.usd == 0.0
        assert result.decision.route == expected[row.doc_id], row.doc_id


def test_evidence_boxes_are_rebuilt_from_the_live_document(generated):
    data_dir, rows = generated
    clean = next(r for r in rows if r.category == "clean")
    doc = load_document(data_dir / clean.file)
    invoice = replay.replay_extractor()(doc).invoice
    assert invoice.total.evidence_boxes and all(b.page == 0 for b in invoice.total.evidence_boxes)


def test_unrecorded_document_fails_clearly():
    doc = Document(text="Some other invoice", boxes=(None,) * 18)
    extraction = replay.replay_extractor()(doc)
    assert extraction.error == replay.NOT_RECORDED


@pytest.mark.parametrize(("key", "expected"), [("sk-test", "cascade"), (None, "replay")])
def test_auto_uses_replay_only_without_a_key(monkeypatch, key, expected):
    if key:
        monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    else:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert process.resolve_system("auto") == expected
    assert process.resolve_system("baseline") == "baseline"


def test_status_reports_mocked_when_queue_came_from_replay(generated, tmp_path, monkeypatch):
    data_dir, rows = generated
    monkeypatch.setattr(process, "DATA_DIR", data_dir)
    db = tmp_path / "demo.sqlite3"
    process.process("replay", db_path=db, docs_dir=data_dir / "docs")
    conn = store.connect(db)
    status = api.get_status(conn)
    conn.close()
    assert status == {"systems": ["replay"], "mocked": True,
                      "mocked_label": "recorded model responses (mocked)"}

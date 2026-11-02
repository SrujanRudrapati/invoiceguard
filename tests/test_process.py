import pytest

from invoiceguard import config, process


def test_missing_key_leaves_existing_db_untouched(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    db = tmp_path / "demo.sqlite3"
    db.write_bytes(b"previous demo")
    with pytest.raises(config.MissingAPIKeyError):
        process.process("cascade", db_path=db, docs_dir=tmp_path)
    assert db.read_bytes() == b"previous demo"


def test_baseline_processes_offline(generated, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    data_dir, rows = generated
    monkeypatch.setattr(process, "DATA_DIR", data_dir)
    counts = process.process("baseline", db_path=tmp_path / "d.sqlite3", docs_dir=data_dir / "docs")
    assert sum(counts.values()) == len(rows) == 24

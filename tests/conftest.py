"""Shared fixture: a fresh generated dataset in a temp dir, built once per test session."""

from pathlib import Path

import pytest
from make_synthetic import generate

from invoiceguard.schema import LabelRow


@pytest.fixture(scope="session")
def generated(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[LabelRow]]:
    out = tmp_path_factory.mktemp("data")
    generate(out / "docs", out / "labels.jsonl")
    lines = (out / "labels.jsonl").read_text().splitlines()
    return out, [LabelRow.model_validate_json(line) for line in lines]

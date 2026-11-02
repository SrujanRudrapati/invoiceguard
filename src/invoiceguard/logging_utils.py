"""One JSON line per model call: tokens, latency, cost, outcome."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from invoiceguard import config

log = logging.getLogger("invoiceguard.model_calls")


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def log_model_call(**fields: object) -> dict:
    record = {"timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"), **fields}
    append_jsonl(config.MODEL_CALLS_PATH, record)
    log.info("model call %s", record)
    return record

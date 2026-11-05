"""SYSTEM=replay: recorded model responses (mocked), so the pipeline runs with no API key.

Extraction is replaced by a lookup of the model's recorded output for the same document text;
grounding, evidence boxes, rules and routing all run live on it. Costs $0.
"""

import hashlib
import json
import logging
from pathlib import Path

from invoiceguard.config import DATA_DIR
from invoiceguard.grounding import evidence_boxes
from invoiceguard.ingest import Document
from invoiceguard.pipeline import Extraction, Extractor
from invoiceguard.schema import SCALAR_FIELDS, Invoice

log = logging.getLogger(__name__)
RECORDED_PATH = DATA_DIR / "recorded" / "cascade_v4.jsonl"
REPLAY_LABEL = "recorded model responses (mocked)"
NOT_RECORDED = "No recorded model response for this document"


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_recordings(path: Path) -> dict[str, dict]:
    if not path.exists():
        raise FileNotFoundError(f"replay needs {path}; it is committed with the repo")
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {row["text_sha256"]: row for row in rows}


def with_live_boxes(doc: Document, invoice: Invoice) -> Invoice:
    """Evidence boxes are recomputed from this document, never taken from the recording."""
    updates = {}
    for name in SCALAR_FIELDS:
        field = getattr(invoice, name)
        if field.evidence:
            updates[name] = field.model_copy(
                update={"evidence_boxes": evidence_boxes(doc, field.evidence)})
    return invoice.model_copy(update=updates)


def replay_extractor(path: Path = RECORDED_PATH) -> Extractor:
    recordings = load_recordings(path)

    def run(doc: Document) -> Extraction:
        row = recordings.get(text_sha256(doc.text))
        if row is None:
            log.warning("%s (text hash not in %s)", NOT_RECORDED, path.name)
            return Extraction(Invoice(doc_type="invoice"), "replay", error=NOT_RECORDED)
        invoice = with_live_boxes(doc, Invoice.model_validate(row["invoice"]))
        return Extraction(invoice, f"{row['model']} (recorded)", escalated=row["escalated"])

    return run

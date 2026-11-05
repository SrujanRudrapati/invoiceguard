"""Build data/recorded/<name>.jsonl from a cascade eval run, for SYSTEM=replay.

Each row is one document's parsed model output (values, evidence quotes, line items) as the
run recorded it, keyed by a hash of the document text. Raw API payloads were never stored, so
this is the model's answer after parsing, not the HTTP response.

Usage: uv run python scripts/record_replay.py runs/<ts>_cascade.jsonl data/recorded/cascade_v4.jsonl
"""

import argparse
import json
from pathlib import Path

from invoiceguard.config import DATA_DIR, HAIKU_MODEL, LABELS_PATH, SONNET_MODEL
from invoiceguard.ingest import load_document
from invoiceguard.replay import text_sha256
from invoiceguard.schema import SCALAR_FIELDS, Extracted, Invoice, LabelRow


def recorded_invoice(row: dict) -> Invoice:
    values, quotes = row["predicted"], row["evidence"]
    scalars = {name: Extracted(value=values[name], evidence=quotes.get(name))
               for name in SCALAR_FIELDS if values[name] is not None}
    return Invoice.model_validate(
        {"doc_type": values["doc_type"], "line_items": values["line_items"], **scalars})


def recording(row: dict, label: LabelRow) -> dict:
    text = load_document(DATA_DIR / label.file).text
    return {
        "doc_id": row["doc_id"],
        "text_sha256": text_sha256(text),
        "model": SONNET_MODEL if row["escalated"] else HAIKU_MODEL,
        "escalated": row["escalated"],
        "recorded_usd": row["usd"],
        "recorded_route": row["pred_route"],
        "invoice": recorded_invoice(row).model_dump(mode="json"),  # no boxes: rebuilt live
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    labels = {row.doc_id: row for row in map(LabelRow.model_validate_json,
                                             LABELS_PATH.read_text().splitlines())}
    rows = [json.loads(line) for line in args.run.read_text().splitlines()]
    synthetic = [r for r in rows if r["source"] == "synthetic"]  # reviewer rows repeat docs
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(recording(r, labels[r["doc_id"]])) + "\n"
                                for r in synthetic))
    print(f"Recorded {len(synthetic)} model responses to {args.out}")


if __name__ == "__main__":
    main()

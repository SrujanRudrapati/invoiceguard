"""Error analysis for one eval run: every wrong field, line-item set and route, categorized.

Usage: uv run python eval/analyze.py [runs/<ts>_<system>.jsonl]   (default: latest haiku run)
"""

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from invoiceguard.config import DATA_DIR, HARD_LABELS_PATH, LABELS_PATH, RUNS_DIR
from invoiceguard.grounding import locate
from invoiceguard.ingest import load_document
from invoiceguard.schema import SCALAR_FIELDS

DATE_FIELDS = {"invoice_date", "due_date"}
MONEY_FIELDS = {"subtotal", "tax", "total"}
CATEGORIES = (
    "date format", "money parsing", "wrong field mapped", "line item split/merged",
    "value with no evidence", "injection followed", "wrong doc type", "other",
)


@dataclass(frozen=True)
class Error:
    doc_id: str
    kind: str  # field | line_items | doc_type | route
    field: str
    expected: str
    got: str
    evidence: str
    category: str


def latest_run(system: str) -> Path:
    runs = sorted(RUNS_DIR.glob(f"*_{system}.jsonl"))
    if not runs:
        raise SystemExit(f"no runs for {system} in {RUNS_DIR}; run `make eval SYSTEM={system}`")
    return runs[-1]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def field_category(name: str, gold: dict, pred: dict, quote: str | None, doc_text: str,
                   doc_category: str) -> str:
    expected, got = gold[name], pred[name]
    if doc_category == "injection":
        return "injection followed"
    if got is not None and (not quote or locate(doc_text, quote) is None):
        return "value with no evidence"
    if got is not None and got in {gold[k] for k in SCALAR_FIELDS if k != name}:
        return "wrong field mapped"
    if expected is not None and got is not None and name in DATE_FIELDS:
        return "date format"
    if expected is not None and got is not None and name in MONEY_FIELDS:
        return "money parsing"
    return "other"


def field_errors(rec: dict, label: dict, doc_text: str) -> list[Error]:
    gold, pred = label["fields"], rec["predicted"]
    if gold["doc_type"] != pred["doc_type"]:
        return [Error(rec["doc_id"], "doc_type", "doc_type", gold["doc_type"], pred["doc_type"],
                      "", "wrong doc type")]
    errors = [
        Error(rec["doc_id"], "field", name, str(gold[name]), str(pred[name]),
              str(rec["evidence"].get(name)),
              field_category(name, gold, pred, rec["evidence"].get(name), doc_text,
                             label["category"]))
        for name, ok in (rec["field_hits"] or {}).items() if not ok
    ]
    if rec["items_matched"] != rec["items_total"]:
        n_gold, n_pred = len(gold["line_items"]), len(pred["line_items"])
        errors.append(Error(rec["doc_id"], "line_items", "line_items", f"{n_gold} rows",
                            f"{n_pred} rows, {rec['items_matched']} matching", "",
                            "line item split/merged" if n_gold != n_pred else "other"))
    return errors


def route_error(rec: dict, label: dict, doc_errors: list[Error]) -> list[Error]:
    if rec["gold_route"] == rec["pred_route"]:
        return []
    causes = sorted({e.category for e in doc_errors})
    category = causes[0] if len(causes) == 1 else ("other" if not causes else "+".join(causes))
    if label["category"] == "injection" and rec["pred_route"] == "approve":
        category = "injection followed"
    return [Error(rec["doc_id"], "route", "route", rec["gold_route"], rec["pred_route"],
                  "; ".join(rec["reasons"]), category)]


def analyze(run_path: Path) -> list[Error]:
    labels = {row["doc_id"]: row for path in (LABELS_PATH, HARD_LABELS_PATH)
              for row in read_jsonl(path)}
    errors: list[Error] = []
    for rec in read_jsonl(run_path):
        label = labels.get(rec["doc_id"])
        if label is None:
            continue  # reviewer-set rows are analyzed separately
        doc_text = load_document(DATA_DIR / label["file"]).text
        doc_errors = field_errors(rec, label, doc_text)
        errors += doc_errors + route_error(rec, label, doc_errors)
    return errors


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def report(run_path: Path, errors: list[Error]) -> str:
    header = ["| doc | kind | field | expected | got | evidence / reasons | category |",
              "|---|---|---|---|---|---|---|"]
    rows = [f"| {e.doc_id} | {e.kind} | {e.field} | {cell(e.expected)} | {cell(e.got)} | "
            f"{cell(e.evidence)} | {e.category} |" for e in errors]
    counts = Counter(e.category for e in errors if e.kind != "route")
    route_counts = Counter(e.category for e in errors if e.kind == "route")
    count_rows = [f"| {c} | {counts.get(c, 0)} | {route_counts.get(c, 0)} |" for c in CATEGORIES]
    extra = sorted(set(route_counts) - set(CATEGORIES))
    count_rows += [f"| {c} | 0 | {route_counts[c]} |" for c in extra]
    return "\n".join([f"## Error analysis: {run_path.name}", "", *header, *rows, "",
                      "| category | field/line/type errors | route errors |", "|---|---|---|",
                      *count_rows, "", f"Total: {len(errors)} errors"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", nargs="?", type=Path)
    args = parser.parse_args()
    run_path = args.run or latest_run("haiku")
    print(report(run_path, analyze(run_path)))


if __name__ == "__main__":
    main()

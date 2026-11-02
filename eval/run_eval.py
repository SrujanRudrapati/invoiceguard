"""Run one system over the labeled set; write per-doc results, print a table, append history.

Usage: uv run python eval/run_eval.py --system baseline [--set main|hard] [--tag v0]
"""

import argparse
import json
import subprocess
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from scoring import DocRecord, aggregate, score_fields

from invoiceguard.cascade import cascade_extractor
from invoiceguard.config import (
    DATA_DIR,
    HAIKU_MODEL,
    HARD_LABELS_PATH,
    HISTORY_PATH,
    LABELS_PATH,
    REVIEWED_LABELS_PATH,
    RUNS_DIR,
    SONNET_MODEL,
)
from invoiceguard.pipeline import (
    DocResult,
    Extractor,
    baseline_extractor,
    llm_extractor,
    run_document,
)
from invoiceguard.schema import SCALAR_FIELDS, LabelRow

# Built lazily so `baseline` never needs an API key.
SYSTEMS: dict[str, Callable[[], Extractor]] = {
    "baseline": lambda: baseline_extractor,
    "haiku": lambda: llm_extractor(HAIKU_MODEL),
    "sonnet": lambda: llm_extractor(SONNET_MODEL),
    "cascade": cascade_extractor,
}
SYSTEM_MODELS = {"baseline": "regex", "haiku": HAIKU_MODEL, "sonnet": SONNET_MODEL,
                 "cascade": f"{HAIKU_MODEL}->{SONNET_MODEL}"}
HISTORY_KEYS = (
    "field_acc", "line_item_acc", "doc_exact", "review_recall", "reject_acc", "auto_approve",
    "grounding", "verified_wrong", "escalation_rate", "p50_ms", "p95_ms", "usd_per_doc", "n_docs",
)


def load_labels(path: Path) -> list[LabelRow]:
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    return [LabelRow.model_validate_json(line) for line in lines if line.strip()]


def git_sha() -> str:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout

    sha = git("rev-parse", "--short", "HEAD").strip()
    return f"{sha}-dirty" if git("status", "--porcelain").strip() else sha


def to_record(label: LabelRow, result: DocResult) -> DocRecord:
    hits, matched, total, exact = score_fields(label.fields, result.extraction.invoice.values())
    return DocRecord(
        doc_id=label.doc_id, source=label.source, gold_route=label.expected_route,
        pred_route=result.decision.route, reasons=result.decision.reasons, field_hits=hits,
        items_matched=matched, items_total=total, exact=exact, grounded=result.grounded,
        latency_ms=result.latency_ms, usd=result.extraction.usd,
        escalated=result.extraction.escalated,
        predicted=result.extraction.invoice.values().model_dump(mode="json"),
        evidence={n: getattr(result.extraction.invoice, n).evidence for n in SCALAR_FIELDS},
    )


def evaluate(
    extractor: Extractor, labels: list[LabelRow], data_dir: Path
) -> tuple[list[DocRecord], dict[str, DocResult]]:
    """Each distinct file is processed once, even if it appears in both label sets."""
    results: dict[str, DocResult] = {}
    for label in labels:
        if label.file not in results:
            results[label.file] = run_document(data_dir / label.file, extractor)
    return [to_record(label, results[label.file]) for label in labels], results


def fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}" if value < 0.01 else f"{value:.3f}"
    return "n/a" if value is None else str(value)


def markdown_report(system: str, metrics: dict, reviewed: dict) -> str:
    rows = [f"| {k} | {fmt(metrics[k])} |" for k in HISTORY_KEYS]
    rows.insert(3, f"| review caught | {metrics['review_caught']}/{metrics['review_n']} |")
    rows.append(f"| reviewer set n / field_acc | {reviewed['n_docs']} / "
                f"{fmt(reviewed['field_acc'])} |")
    matrix = ["| gold \\ pred | approve | review | reject |", "|---|---|---|---|"]
    matrix += [f"| {g} | " + " | ".join(str(n) for n in preds.values()) + " |"
               for g, preds in metrics["confusion"].items()]
    return "\n".join([f"## {system}", "", "| metric | value |", "|---|---|", *rows, "",
                      "Route confusion", "", *matrix])


def write_outputs(system: str, label_set: str, tag: str, records: list[DocRecord],
                  metrics: dict) -> Path:
    now = datetime.now(UTC)
    RUNS_DIR.mkdir(exist_ok=True)
    suffix = "" if label_set == "main" else f"_{label_set}"
    run_path = RUNS_DIR / f"{now:%Y%m%dT%H%M%SZ}_{system}{suffix}.jsonl"
    run_path.write_text("".join(json.dumps(asdict(r)) + "\n" for r in records))
    history = {"timestamp": now.isoformat(timespec="seconds"), "git_sha": git_sha(), "tag": tag,
               "system": system, "model": SYSTEM_MODELS[system], "set": label_set,
               **{k: metrics[k] for k in HISTORY_KEYS}}
    with HISTORY_PATH.open("a") as fh:
        fh.write(json.dumps(history) + "\n")
    return run_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", required=True, choices=list(SYSTEMS))
    parser.add_argument("--set", dest="label_set", choices=("main", "hard"), default="main")
    parser.add_argument("--tag", default="")
    args = parser.parse_args()

    if args.label_set == "hard":
        labels = load_labels(HARD_LABELS_PATH)
    else:
        labels = load_labels(LABELS_PATH) + load_labels(REVIEWED_LABELS_PATH)
    records, _ = evaluate(SYSTEMS[args.system](), labels, DATA_DIR)
    scored = aggregate([r for r in records if r.source == "synthetic"])
    reviewed_metrics = aggregate([r for r in records if r.source == "reviewer"])
    run_path = write_outputs(args.system, args.label_set, args.tag, records, scored)
    print(markdown_report(f"{args.system} ({args.label_set} set)", scored, reviewed_metrics))
    print(f"\nPer-doc results: {run_path}\nAppended: {HISTORY_PATH}")


if __name__ == "__main__":
    main()

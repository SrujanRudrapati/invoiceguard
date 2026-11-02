"""One comparison table per label set from runs/history.jsonl: latest row per system for a tag.

Usage: uv run python eval/compare.py --tag v3
"""

import argparse
import json

from invoiceguard.config import HISTORY_PATH

SYSTEMS = ("baseline", "haiku", "sonnet", "cascade")
COLUMNS = ("field_acc", "line_item_acc", "doc_exact", "review_recall", "reject_acc",
           "auto_approve", "grounding", "verified_wrong", "escalation_rate", "p50_ms",
           "p95_ms", "usd_per_doc", "n_docs")


def fmt(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6f}" if value < 0.01 else f"{value:.3f}"
    return str(value)


def latest_rows(tag: str) -> dict[tuple[str, str], dict]:
    rows = [json.loads(line) for line in HISTORY_PATH.read_text().splitlines() if line.strip()]
    return {(r.get("set", "main"), r["system"]): r for r in rows if r["tag"] == tag}


def table(label_set: str, rows: dict[tuple[str, str], dict]) -> str:
    lines = [f"### {label_set} set", "", "| system | " + " | ".join(COLUMNS) + " |",
             "|---" * (len(COLUMNS) + 1) + "|"]
    for system in SYSTEMS:
        row = rows.get((label_set, system))
        if row:
            lines.append(f"| {system} | " + " | ".join(fmt(row[c]) for c in COLUMNS) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    rows = latest_rows(args.tag)
    if not rows:
        raise SystemExit(f"no history rows tagged {args.tag!r}")
    print("\n\n".join(table(s, rows) for s in ("main", "hard")))


if __name__ == "__main__":
    main()

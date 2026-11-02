"""Reset the DB and process every PDF in data/docs with one system.

Usage: uv run python -m invoiceguard.process [--system cascade]
"""

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from invoiceguard import store
from invoiceguard.config import DATA_DIR, DB_PATH, DOCS_DIR, MissingAPIKeyError
from invoiceguard.pipeline import run_document
from invoiceguard.systems import SYSTEMS

log = logging.getLogger(__name__)
WORKERS = 4


def process(system: str, db_path: Path = DB_PATH, docs_dir: Path = DOCS_DIR) -> dict[str, int]:
    """Returns how many documents landed in each route."""
    extractor = SYSTEMS[system]()  # first: a missing key must not wipe the existing DB
    db_path.unlink(missing_ok=True)
    conn = store.connect(db_path)
    paths = sorted(docs_dir.glob("*.pdf"))
    counts: dict[str, int] = {}
    with ThreadPoolExecutor(WORKERS) as pool:  # extraction in threads, writes on this thread
        for path, result in zip(paths, pool.map(lambda p: run_document(p, extractor), paths),
                                strict=True):
            store.add_document(conn, path.stem, str(path.relative_to(DATA_DIR)))
            store.save_extraction(conn, path.stem, system, result)
            counts[result.decision.route] = counts.get(result.decision.route, 0) + 1
    conn.close()
    return counts


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", choices=list(SYSTEMS), default="cascade")
    args = parser.parse_args()
    try:
        counts = process(args.system)
    except MissingAPIKeyError as exc:
        raise SystemExit(str(exc)) from exc
    summary = ", ".join(f"{n} {route}" for route, n in sorted(counts.items()))
    print(f"Processed {sum(counts.values())} documents with {args.system}: {summary}")


if __name__ == "__main__":
    main()

"""Single home for paths, model IDs and prices."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
DOCS_DIR = DATA_DIR / "docs"
LABELS_PATH = DATA_DIR / "labels.jsonl"
REVIEWED_LABELS_PATH = DATA_DIR / "labels_reviewed.jsonl"
RUNS_DIR = ROOT / "runs"
HISTORY_PATH = RUNS_DIR / "history.jsonl"

HAIKU_MODEL = "claude-haiku-5-5"
SONNET_MODEL = "claude-sonnet-5-5"

# USD per 1M tokens. Unverified: check against current pricing docs before the final run.
PRICES_PER_MTOK = {
    HAIKU_MODEL: {"input": 0.10, "output": 0.50},
    SONNET_MODEL: {"input": 2.00, "output": 10.00},
}


def anthropic_api_key() -> str:
    """Read the key lazily so offline code (data, tests) never needs it."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set; copy .env.example to .env")
    return key

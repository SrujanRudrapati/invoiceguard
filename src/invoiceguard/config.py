"""Single home for paths, model IDs and prices."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
DOCS_DIR = DATA_DIR / "docs"
LABELS_PATH = DATA_DIR / "labels.jsonl"
HARD_LABELS_PATH = DATA_DIR / "labels_hard.jsonl"
REVIEWED_LABELS_PATH = DATA_DIR / "labels_reviewed.jsonl"
RUNS_DIR = ROOT / "runs"
HISTORY_PATH = RUNS_DIR / "history.jsonl"
MODEL_CALLS_PATH = RUNS_DIR / "model_calls.jsonl"
DB_PATH = DATA_DIR / "invoiceguard.sqlite3"

HAIKU_MODEL = "claude-haiku-5-5"
SONNET_MODEL = "claude-sonnet-5-5"

# USD per 1M tokens. Checked 2026-11-02 against the claude-api skill's model table (cached
# 2026-10-06); Haiku rate applies to prompts up to 100K tokens. Re-check before the final run.
PRICES_PER_MTOK = {
    HAIKU_MODEL: {"input": 0.10, "output": 0.50},
    SONNET_MODEL: {"input": 2.00, "output": 10.00},
}

# Thinking off: Haiku 5.5 accepts "disabled" at effort <= high (default medium);
# Sonnet 5.5 rejects "disabled" and uses "between_tools" instead.
THINKING_OFF = {
    HAIKU_MODEL: {"type": "disabled"},
    SONNET_MODEL: {"type": "between_tools"},
}
LLM_TIMEOUT_S = 30.0
LLM_MAX_RETRIES = 3  # SDK retries 408/409/429/5xx (incl. 529) with exponential backoff
LLM_MAX_TOKENS = 4096


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICES_PER_MTOK[model]
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000


def anthropic_api_key() -> str:
    """Read the key lazily so offline code (data, tests) never needs it."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set; copy .env.example to .env")
    return key

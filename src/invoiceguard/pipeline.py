"""One document end to end: ingest -> extract -> ground -> route."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from invoiceguard import baseline
from invoiceguard.grounding import grounding_flags
from invoiceguard.ingest import Document, load_document
from invoiceguard.route import Decision, route
from invoiceguard.schema import Invoice


@dataclass(frozen=True)
class Extraction:
    invoice: Invoice
    model: str
    escalated: bool = False
    usd: float = 0.0


Extractor = Callable[[Document], Extraction]


@dataclass(frozen=True)
class DocResult:
    extraction: Extraction
    decision: Decision
    grounded: dict[str, bool]
    latency_ms: float


def baseline_extractor(doc: Document) -> Extraction:
    return Extraction(invoice=baseline.extract(doc), model="regex")


def run_document(path: Path, extractor: Extractor) -> DocResult:
    start = time.perf_counter()
    doc = load_document(path)
    extraction = extractor(doc)
    decision = route(extraction.invoice)
    latency_ms = (time.perf_counter() - start) * 1000
    return DocResult(extraction, decision, grounding_flags(doc, extraction.invoice), latency_ms)

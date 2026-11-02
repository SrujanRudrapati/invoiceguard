"""One document end to end: ingest -> extract -> ground -> rules -> route."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from invoiceguard import baseline, extract_llm, rules
from invoiceguard.grounding import Verification, verify_invoice
from invoiceguard.ingest import Document, load_document
from invoiceguard.route import Decision, route
from invoiceguard.schema import Invoice

log = logging.getLogger(__name__)
EXTRACTION_FAILED_REASON = "Extraction failed; enter the fields by hand"


@dataclass(frozen=True)
class Extraction:
    invoice: Invoice
    model: str
    escalated: bool = False
    usd: float = 0.0
    error: str | None = None


Extractor = Callable[[Document], Extraction]


@dataclass(frozen=True)
class DocResult:
    extraction: Extraction
    decision: Decision
    grounded: dict[str, bool]
    latency_ms: float


def baseline_extractor(doc: Document) -> Extraction:
    return Extraction(invoice=baseline.extract(doc), model="regex")


def llm_extractor(model: str) -> Extractor:
    client = extract_llm.make_client()

    def run(doc: Document) -> Extraction:
        try:
            result = extract_llm.extract(doc, model, client)
        except extract_llm.ExtractionFailed as exc:
            log.warning("extraction failed: %s", exc)
            return Extraction(Invoice(doc_type="invoice"), model, usd=exc.usd, error=str(exc))
        return Extraction(result.invoice, model, usd=result.usd)

    return run


def failures_for(doc: Document, extraction: Extraction,
                 checks: dict[str, Verification]) -> tuple[str, ...]:
    if extraction.error:
        return (EXTRACTION_FAILED_REASON,)
    unverified = tuple(v.reason for v in checks.values() if not v.verified)
    return rules.check(extraction.invoice, doc.text, unverified)


def run_document(path: Path, extractor: Extractor) -> DocResult:
    start = time.perf_counter()
    doc = load_document(path)
    extraction = extractor(doc)
    checks = verify_invoice(doc, extraction.invoice)
    decision = route(extraction.invoice, failures_for(doc, extraction, checks))
    latency_ms = (time.perf_counter() - start) * 1000
    grounded = {name: v.verified for name, v in checks.items()}
    return DocResult(extraction, decision, grounded, latency_ms)

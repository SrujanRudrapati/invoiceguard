"""Haiku first; re-run a doc on Sonnet once only when Haiku's reading can't be trusted.

Escalate when: Haiku's extraction failed after its retry, or a required field Haiku extracted
is unverified (quote missing or contradicting the value).
Never escalate for: arithmetic rule failures (the invoice is wrong, not the reading),
ambiguous slash dates (the ambiguity is in the document), fields absent from the page,
or non-invoices.
"""

import logging

from invoiceguard import extract_llm
from invoiceguard.config import HAIKU_MODEL, SONNET_MODEL
from invoiceguard.grounding import verify_invoice
from invoiceguard.ingest import Document
from invoiceguard.pipeline import Extraction, Extractor
from invoiceguard.schema import REQUIRED_FIELDS, Invoice

log = logging.getLogger(__name__)


def escalation_reason(doc: Document, invoice: Invoice) -> str | None:
    if invoice.doc_type == "not_invoice":
        return None
    checks = verify_invoice(doc, invoice)
    bad = [name for name in REQUIRED_FIELDS
           if name in checks and not checks[name].verified and not checks[name].ambiguous]
    return f"unverified: {', '.join(bad)}" if bad else None


def run_fallback(doc: Document, client, spent: float, reason: str) -> Extraction:
    log.info("escalating to %s: %s", SONNET_MODEL, reason)
    try:
        result = extract_llm.extract(doc, SONNET_MODEL, client)
    except extract_llm.ExtractionFailed as exc:
        log.warning("fallback extraction failed: %s", exc)
        return Extraction(Invoice(doc_type="invoice"), SONNET_MODEL, escalated=True,
                          usd=spent + exc.usd, error=str(exc))
    return Extraction(result.invoice, SONNET_MODEL, escalated=True, usd=spent + result.usd)


def cascade_extractor() -> Extractor:
    client = extract_llm.make_client()

    def run(doc: Document) -> Extraction:
        try:
            first = extract_llm.extract(doc, HAIKU_MODEL, client)
        except extract_llm.ExtractionFailed as exc:
            return run_fallback(doc, client, exc.usd, f"{HAIKU_MODEL} failed: {exc}")
        reason = escalation_reason(doc, first.invoice)
        if reason is None:
            return Extraction(first.invoice, HAIKU_MODEL, usd=first.usd)
        return run_fallback(doc, client, first.usd, reason)

    return run

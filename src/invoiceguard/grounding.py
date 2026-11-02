"""Check that evidence quotes exist in the document and support the extracted value.

A field is verified only if (1) its quote is found in the document text, normalized-exact
(casefold, collapse whitespace, unify quotes and dashes; no fuzzy matching), and (2) the value
agrees with the quote: money and dates are parsed out of the quote, strings must be contained.
Anything else is unverified.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from invoiceguard.ingest import Document
from invoiceguard.schema import SCALAR_FIELDS, Box, Extracted, Invoice

LINE_TOLERANCE_PT = 2.0
UNIFY = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
})


@lru_cache(maxsize=64)
def normalize_with_map(text: str) -> tuple[str, tuple[int, ...]]:
    """Normalized text, plus the source index in `text` of every normalized character."""
    chars: list[str] = []
    sources: list[int] = []
    space_at: int | None = None
    for i, ch in enumerate(text):
        if ch.isspace():
            if chars and space_at is None:
                space_at = i
            continue
        if space_at is not None:
            chars.append(" ")
            sources.append(space_at)
            space_at = None
        for folded in ch.translate(UNIFY).casefold():  # casefold may expand, e.g. ß -> ss
            chars.append(folded)
            sources.append(i)
    return "".join(chars), tuple(sources)


def normalize(text: str) -> str:
    return normalize_with_map(text)[0]


def locate(text: str, quote: str | None) -> tuple[int, int] | None:
    """Span [start, end) of the first normalized match of quote in text, in original indices."""
    needle = normalize(quote or "")
    if not needle:
        return None
    haystack, sources = normalize_with_map(text)
    start = haystack.find(needle)
    if start < 0:
        return None
    return sources[start], sources[start + len(needle) - 1] + 1


def merge_line_boxes(boxes: tuple[Box | None, ...]) -> tuple[Box, ...]:
    """Union consecutive character boxes that sit on the same line of the same page."""
    merged: list[Box] = []
    for box in (b for b in boxes if b is not None):
        last = merged[-1] if merged else None
        same_line = last and last.page == box.page and abs(last.top - box.top) < LINE_TOLERANCE_PT
        if not same_line:
            merged.append(box)
            continue
        merged[-1] = Box(
            page=box.page, x0=min(last.x0, box.x0), top=min(last.top, box.top),
            x1=max(last.x1, box.x1), bottom=max(last.bottom, box.bottom),
        )
    return tuple(merged)


def evidence_boxes(doc: Document, quote: str | None) -> tuple[Box, ...]:
    span = locate(doc.text, quote)
    return merge_line_boxes(doc.boxes[span[0]:span[1]]) if span else ()


NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
# (pattern, formats to try); slash dates accept both month-first and day-first readings
DATE_PATTERNS = (
    (re.compile(r"\d{4}-\d{2}-\d{2}"), ("%Y-%m-%d",)),
    (re.compile(r"[A-Z][a-z]+ \d{1,2}, \d{4}"), ("%B %d, %Y", "%b %d, %Y")),
    (re.compile(r"\d{1,2} [A-Z][a-z]+ \d{4}"), ("%d %b %Y", "%d %B %Y")),
    (re.compile(r"\d{1,2}/\d{1,2}/\d{4}"), ("%m/%d/%Y", "%d/%m/%Y")),
)


def numbers_in(quote: str) -> set[Decimal]:
    found = set()
    for raw in NUMBER.findall(quote):
        try:
            found.add(Decimal(raw.replace(",", "")))
        except InvalidOperation:
            continue
    return found


def parse_any(raw: str, formats: tuple[str, ...]) -> set[date]:
    parsed = set()
    for fmt in formats:
        try:
            parsed.add(datetime.strptime(raw, fmt).date())
        except ValueError:
            continue
    return parsed


def dates_in(quote: str) -> set[date]:
    return {
        d for pattern, formats in DATE_PATTERNS
        for raw in pattern.findall(quote) for d in parse_any(raw, formats)
    }


def value_matches_quote(value: object, quote: str) -> bool:
    if isinstance(value, Decimal):
        return value in numbers_in(quote)  # Decimal equality is numeric: 6447 == 6447.00
    if isinstance(value, date):
        return value in dates_in(quote)
    return normalize(str(value)) in normalize(quote)


def is_verified(doc: Document, field: Extracted) -> bool:
    if field.value is None or not field.evidence:
        return False
    return locate(doc.text, field.evidence) is not None and value_matches_quote(
        field.value, field.evidence)


def grounding_flags(doc: Document, invoice: Invoice) -> dict[str, bool]:
    """For each non-null scalar field: True if verified, False if unverified."""
    return {
        name: is_verified(doc, field)
        for name in SCALAR_FIELDS
        if (field := getattr(invoice, name)).value is not None
    }

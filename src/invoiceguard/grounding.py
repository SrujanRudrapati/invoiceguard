"""Check that evidence quotes exist in the document and support the extracted value.

A field is verified only if (1) its quote is found in the document text, normalized-exact
(casefold, collapse whitespace, unify quotes and dashes; no fuzzy matching), and (2) the value
agrees with the quote: money and dates are parsed out of the quote, strings must be contained.
Anything else is unverified.

Slash dates (10/05/2026) are read in the order the document itself proves: if any slash date on
the page has a part > 12, that order applies to all of them. If none does, an ambiguous date is
unverified with its own reason and is not escalated, because the ambiguity is in the document.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from invoiceguard.ingest import Document
from invoiceguard.schema import FIELD_LABELS, SCALAR_FIELDS, Box, Extracted, Invoice

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
SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
SLASH_FORMATS = {"MDY": ("%m/%d/%Y",), "DMY": ("%d/%m/%Y",), None: ("%m/%d/%Y", "%d/%m/%Y")}
DATE_PATTERNS = (
    (re.compile(r"\d{4}-\d{2}-\d{2}"), ("%Y-%m-%d",)),
    (re.compile(r"[A-Z][a-z]+ \d{1,2}, \d{4}"), ("%B %d, %Y", "%b %d, %Y")),
    (re.compile(r"\d{1,2} [A-Z][a-z]+ \d{4}"), ("%d %b %Y", "%d %B %Y")),
)


@dataclass(frozen=True)
class Verification:
    verified: bool
    reason: str | None = None
    ambiguous: bool = False  # ambiguity is in the document; a stronger model cannot fix it


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


def slash_order(text: str) -> str | None:
    """MDY or DMY when some slash date on the document can only be read one way, else None."""
    orders = {
        "DMY" if int(first) > 12 else "MDY"
        for first, second, _ in SLASH_DATE.findall(text)
        if int(first) > 12 or int(second) > 12
    }
    return orders.pop() if len(orders) == 1 else None


def ambiguous_slash_dates(quote: str, order: str | None) -> list[str]:
    if order is not None:
        return []
    return [f"{a}/{b}/{y}" for a, b, y in SLASH_DATE.findall(quote)
            if a != b and int(a) <= 12 and int(b) <= 12]


def dates_in(quote: str, order: str | None = None) -> set[date]:
    found = {
        d for pattern, formats in DATE_PATTERNS
        for raw in pattern.findall(quote) for d in parse_any(raw, formats)
    }
    slash = {d for m in SLASH_DATE.finditer(quote) for d in parse_any(m.group(0),
                                                                     SLASH_FORMATS[order])}
    return found | slash


def value_matches_quote(value: object, quote: str, order: str | None = None) -> bool:
    if isinstance(value, Decimal):
        return value in numbers_in(quote)  # Decimal equality is numeric: 6447 == 6447.00
    if isinstance(value, date):
        return value in dates_in(quote, order)
    return normalize(str(value)) in normalize(quote)


def verify_field(doc: Document, name: str, field: Extracted, order: str | None) -> Verification:
    label = FIELD_LABELS[name].capitalize()
    unverified = Verification(False, f"{label} could not be verified against the document")
    if not field.evidence or locate(doc.text, field.evidence) is None:
        return unverified
    if isinstance(field.value, date) and (raw := ambiguous_slash_dates(field.evidence, order)):
        return Verification(False, f"Ambiguous date {raw[0]} (MM/DD or DD/MM)", ambiguous=True)
    if not value_matches_quote(field.value, field.evidence, order):
        return unverified
    return Verification(True)


def verify_invoice(doc: Document, invoice: Invoice) -> dict[str, Verification]:
    """One Verification per non-null scalar field. Slash-date order is resolved per document."""
    order = slash_order(doc.text)
    return {
        name: verify_field(doc, name, field, order)
        for name in SCALAR_FIELDS
        if (field := getattr(invoice, name)).value is not None
    }


def is_verified(doc: Document, field: Extracted, name: str = "total") -> bool:
    if field.value is None:
        return False
    return verify_field(doc, name, field, slash_order(doc.text)).verified


def grounding_flags(doc: Document, invoice: Invoice) -> dict[str, bool]:
    """For each non-null scalar field: True if verified, False if unverified."""
    return {name: v.verified for name, v in verify_invoice(doc, invoice).items()}

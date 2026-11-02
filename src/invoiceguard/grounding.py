"""Check that evidence quotes exist in the document and map them to page boxes.

Matching is normalized-exact: casefold, collapse whitespace, unify quotes and dashes.
No fuzzy matching, so a paraphrased quote counts as ungrounded.
"""

from functools import lru_cache

from invoiceguard.ingest import Document
from invoiceguard.schema import SCALAR_FIELDS, Box, Invoice

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


def grounding_flags(doc: Document, invoice: Invoice) -> dict[str, bool]:
    """For each non-null scalar field: is its evidence quote found in the document?"""
    return {
        name: locate(doc.text, field.evidence) is not None
        for name in SCALAR_FIELDS
        if (field := getattr(invoice, name)).value is not None
    }

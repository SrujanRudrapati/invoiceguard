"""Regex baseline: label-anchored patterns, typed value patterns, evidence = the matched text.

Written for the standard labels and date formats only. The messy layouts (abbreviated labels,
"03 Nov 2026" dates, currency symbols) are deliberately held out.
"""

import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal

from invoiceguard.grounding import merge_line_boxes
from invoiceguard.ingest import Document
from invoiceguard.schema import Extracted, Invoice, LineItem

MONEY = r"[\d,]+\.\d{2}"
QTY = r"\d+(?:\.\d+)?"
ID = r"[A-Za-z0-9][A-Za-z0-9-]*"
DATE = r"\d{4}-\d{2}-\d{2}|[A-Z][a-z]+ \d{1,2}, \d{4}|\d{2}/\d{2}/\d{4}"
DATE_FORMATS = ("%Y-%m-%d", "%B %d, %Y", "%m/%d/%Y")
TITLE_LINE = re.compile(r"^(invoice|quotation|shipping notice)$", re.IGNORECASE)
FULL_ROW = re.compile(rf"^(?P<desc>.+?) (?P<qty>{QTY}) (?P<unit>{MONEY}) (?P<amount>{MONEY})$",
                      re.MULTILINE)
NUMBERS_ROW = re.compile(rf"^(?P<qty>{QTY}) (?P<unit>{MONEY}) (?P<amount>{MONEY})$")


def parse_money(raw: str) -> Decimal:
    return Decimal(raw.replace(",", ""))


def parse_date(raw: str) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date: {raw!r}")


# field -> (label alternatives, value pattern, parser)
FIELD_PATTERNS: dict[str, tuple[str, str, Callable]] = {
    "invoice_number": (r"Invoice number", ID, str),
    "invoice_date": (r"Invoice date", DATE, parse_date),
    "due_date": (r"Due date", DATE, parse_date),
    "po_number": (r"PO number", ID, str),
    "currency": (r"Currency", r"[A-Z]{3}", str),
    "subtotal": (r"Subtotal", MONEY, parse_money),
    "tax": (r"\bTax\b", MONEY, parse_money),
    "total": (r"\bTotal\b", MONEY, parse_money),
}


def extract_field(doc: Document, labels: str, value: str, parse: Callable) -> Extracted:
    match = re.search(rf"(?:{labels})[ \t]*:?[ \t]*(?P<value>{value})", doc.text)
    if not match:
        return Extracted()
    return Extracted(
        value=parse(match["value"]),
        evidence=match.group(0),
        evidence_boxes=merge_line_boxes(doc.boxes[match.start():match.end()]),
    )


def extract_vendor(doc: Document) -> Extracted:
    """Vendor is the first line that isn't a document title."""
    offset = 0
    for line in doc.text.split("\n"):
        if line.strip() and not TITLE_LINE.match(line.strip()):
            boxes = merge_line_boxes(doc.boxes[offset:offset + len(line)])
            return Extracted(value=line.strip(), evidence=line, evidence_boxes=boxes)
        offset += len(line) + 1
    return Extracted()


def to_item(desc: str, row: re.Match) -> LineItem:
    return LineItem(description=desc.strip(), quantity=Decimal(row["qty"]),
                    unit_price=parse_money(row["unit"]), amount=parse_money(row["amount"]))


def extract_line_items(text: str) -> tuple[LineItem, ...]:
    """Table rows on one line, or receipt rows: description line, then a numbers-only line."""
    lines = text.split("\n")
    items = []
    for prev, line in zip(["", *lines], lines, strict=False):
        if numbers := NUMBERS_ROW.match(line):
            items.append(to_item(prev, numbers))
        elif full := FULL_ROW.match(line):
            items.append(to_item(full["desc"], full))
    return tuple(items)


def extract(doc: Document) -> Invoice:
    is_invoice = re.search(r"\binvoice\b", doc.text, re.IGNORECASE) is not None
    if not is_invoice:
        return Invoice(doc_type="not_invoice")
    fields = {name: extract_field(doc, *spec) for name, spec in FIELD_PATTERNS.items()}
    return Invoice(doc_type="invoice", vendor_name=extract_vendor(doc),
                   line_items=extract_line_items(doc.text), **fields)

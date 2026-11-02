"""Render the 6-doc hard set (data/hard/) and its labels (data/labels_hard.jsonl).

Labels are written here from fixed values, before any model has seen these documents.
Each doc isolates one difficulty; dates are ISO everywhere so they do not add a second one.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from make_synthetic import BUYER, MARGIN, PAGE_H, PAGE_W, THANKS, draw_footers, draw_pairs
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen.canvas import Canvas

from invoiceguard.config import DATA_DIR, HARD_LABELS_PATH
from invoiceguard.schema import InvoiceFields, LabelRow, LineItem

HARD_DIR = DATA_DIR / "hard"
CENT = Decimal("0.01")
ROW_H = 15
COLUMNS = ("Description", "Qty", "Unit price", "Amount")


def us(v: Decimal) -> str:
    return f"{v:,.2f}"


def eu(v: Decimal) -> str:
    """4,812.50 -> 4.812,50"""
    return f"{v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


@dataclass(frozen=True)
class Row:
    desc_lines: tuple[str, ...]
    qty: Decimal
    unit: Decimal

    @property
    def amount(self) -> Decimal:
        return (self.qty * self.unit).quantize(CENT, ROUND_HALF_UP)


@dataclass(frozen=True)
class HardDoc:
    doc_id: str
    defect: str
    expected_route: str
    vendor_lines: tuple[str, ...]
    title: str
    number_label: str
    invoice_number: str
    invoice_date: date
    due_date: date | None
    po_number: str | None
    currency: str
    rows: tuple[Row, ...]
    tax_rate: Decimal
    fmt: Callable[[Decimal], str] = us
    total_suffix: str = ""
    extra_header: tuple[tuple[str, str], ...] = ()
    rows_per_page: int = 30

    @property
    def subtotal(self) -> Decimal:
        return sum((r.amount for r in self.rows), Decimal("0"))

    @property
    def tax(self) -> Decimal:
        return (self.subtotal * self.tax_rate).quantize(CENT, ROUND_HALF_UP)

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.tax


def items(spec: list[tuple[str, str, str]]) -> tuple[Row, ...]:
    return tuple(Row((d,), Decimal(q), Decimal(u)) for d, q, u in spec)


TWO_PAGE_ITEMS = [
    (f"{name} ({n})", str(n % 4 + 1), price)
    for n, (name, price) in enumerate([
        ("Toner cartridge", "84.50"), ("Printer paper, case", "42.75"), ("Laptop stand", "39.99"),
        ("Desk lamp", "27.00"), ("Whiteboard markers", "9.80"), ("Stapler", "14.25"),
        ("Monitor arm", "119.00"), ("USB-C dock", "189.00"), ("Webcam", "74.90"),
        ("Headset", "59.00"), ("Keyboard", "49.50"), ("Mouse", "24.00"), ("HDMI cable", "8.99"),
        ("Power strip", "21.40"), ("Cable ties, bag", "6.30"), ("Label printer", "139.00"),
        ("Label tape", "18.60"), ("Shredder", "210.00"), ("Filing box", "12.75"),
        ("Envelope pack", "15.20"), ("Notebook pack", "22.40"), ("Pen box", "11.90"),
        ("Desk organizer", "19.95"), ("Footrest", "44.00"), ("Chair mat", "68.00"),
        ("Coat hook", "7.50"),
    ], start=1)
]

DOCS = (
    HardDoc("hard_001", "european_number_format", "approve", ("Brauerei Adler GmbH",),
            "Rechnung / Invoice", "Invoice number", "RE-2026-0311", date(2026, 10, 14),
            date(2026, 11, 13), None, "EUR",
            items([("Keg beer, 50 l", "12", "89.50"), ("Keg deposit", "12", "30.00")]),
            Decimal("0.19"), fmt=eu),
    HardDoc("hard_002", "total_in_words", "approve", ("Cobalt Support Services",), "Invoice",
            "Invoice number", "CSS-88412", date(2026, 10, 1), date(2026, 10, 31), "PO-55120",
            "USD", items([("Annual support plan", "1", "1250.00")]), Decimal("0"),
            total_suffix=" (One thousand two hundred fifty US dollars)"),
    HardDoc("hard_003", "credit_note", "review", ("Acme Office Supply Co.",), "Credit note",
            "Credit note number", "CN-2026-0042", date(2026, 10, 20), None, None, "USD",
            items([("Returned office chair", "-2", "289.00")]), Decimal("0.0825"),
            extra_header=(("Original invoice", "INV-2026-0142"),)),
    HardDoc("hard_004", "wrapped_descriptions", "approve", ("Granite Network Systems",),
            "Invoice", "Invoice number", "GNS-30177", date(2026, 9, 18), date(2026, 10, 18),
            "PO-61234", "USD",
            (Row(("Network cabling installation,", "floor 3 east wing"), Decimal("1"),
                 Decimal("2400.00")),
             Row(("On-site engineer time", "(weekend rate)"), Decimal("6"), Decimal("180.00"))),
            Decimal("0.05")),
    HardDoc("hard_005", "vendor_name_two_lines", "approve",
            ("Northern Lights Industrial", "Supply Company Ltd."), "Invoice", "Invoice number",
            "NL-7781", date(2026, 10, 7), date(2026, 11, 6), None, "GBP",
            items([("Safety gloves, box", "10", "18.50"), ("Hi-vis vest", "20", "7.25")]),
            Decimal("0.20")),
    HardDoc("hard_006", "two_pages", "approve", ("Harbourview Office Supply",), "Invoice",
            "Invoice number", "HOS-2026-1190", date(2026, 10, 2), date(2026, 11, 1), "PO-70315",
            "USD", items(TWO_PAGE_ITEMS), Decimal("0.0825"), rows_per_page=16),
)


# ---------- drawing ----------

def draw_header(c: Canvas, doc: HardDoc) -> float:
    c.setFont("Helvetica-Bold", 18)
    for n, line in enumerate(doc.vendor_lines):
        c.drawString(MARGIN, PAGE_H - 72 - 22 * n, line)
    c.setFont("Helvetica-Bold", 22)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 72, doc.title)
    c.setFont("Helvetica", 10)
    c.drawString(MARGIN, PAGE_H - 140, f"Bill to: {BUYER}")
    pairs = [(doc.number_label, doc.invoice_number), ("Invoice date", doc.invoice_date.isoformat()),
             ("Due date", doc.due_date.isoformat() if doc.due_date else None),
             ("PO number", doc.po_number), *doc.extra_header, ("Currency", doc.currency)]
    return draw_pairs(c, tuple((k, v) for k, v in pairs if v), PAGE_W - 170, PAGE_H - 110)


def column_rights() -> list[float]:
    x1 = PAGE_W - MARGIN
    col_w = (x1 - MARGIN) * 0.5 / 3
    return [x1 - (3 - k) * col_w for k in range(4)]


def draw_table_header(c: Canvas, y: float) -> float:
    rights = column_rights()
    c.setFont("Helvetica-Bold", 10)
    c.drawString(MARGIN + 4, y, COLUMNS[0])
    for right, name in zip(rights[1:], COLUMNS[1:], strict=True):
        c.drawRightString(right - 4, y, name)
    c.line(MARGIN, y - 5, PAGE_W - MARGIN, y - 5)
    c.setFont("Helvetica", 10)
    return y - ROW_H - 3


def draw_row(c: Canvas, doc: HardDoc, row: Row, y: float) -> float:
    rights = column_rights()
    cells = (f"{row.qty:f}", doc.fmt(row.unit), doc.fmt(row.amount))
    for right, cell in zip(rights[1:], cells, strict=True):
        c.drawRightString(right - 4, y, cell)
    for line in row.desc_lines:
        c.drawString(MARGIN + 4, y, line)
        y -= ROW_H
    return y


def draw_page_number(c: Canvas, page: int, pages: int) -> None:
    if pages > 1:
        c.setFont("Helvetica", 8)
        c.drawRightString(PAGE_W - MARGIN, 44, f"Page {page} of {pages}")


def render(doc: HardDoc, path: Path) -> None:
    chunks = [doc.rows[i:i + doc.rows_per_page]
              for i in range(0, len(doc.rows), doc.rows_per_page)]
    c = Canvas(str(path), pagesize=LETTER, invariant=1)
    y = draw_table_header(c, min(draw_header(c, doc), PAGE_H - 160) - 20)
    for n, chunk in enumerate(chunks, start=1):
        if n > 1:
            c.setFont("Helvetica-Bold", 12)
            c.drawString(MARGIN, PAGE_H - 72, f"{' '.join(doc.vendor_lines)}, {doc.title.lower()} "
                                              f"{doc.invoice_number} (continued)")
            y = draw_table_header(c, PAGE_H - 110)
        for row in chunk:
            y = draw_row(c, doc, row, y)
        if n < len(chunks):
            c.setFont("Helvetica", 9)
            c.drawString(MARGIN, y - 10, "Continued on next page")
            draw_page_number(c, n, len(chunks))
            c.showPage()
    c.line(MARGIN, y + 7, PAGE_W - MARGIN, y + 7)
    c.setFont("Helvetica", 10)
    draw_pairs(c, (("Subtotal", doc.fmt(doc.subtotal)), ("Tax", doc.fmt(doc.tax)),
                   ("Total", doc.fmt(doc.total) + doc.total_suffix)), PAGE_W - 130, y - 12)
    draw_page_number(c, len(chunks), len(chunks))
    draw_footers(c, (THANKS,))
    c.showPage()
    c.save()


# ---------- labels ----------

def to_label(doc: HardDoc) -> LabelRow:
    line_items = tuple(
        LineItem(description=" ".join(r.desc_lines), quantity=r.qty, unit_price=r.unit,
                 amount=r.amount)
        for r in doc.rows
    )
    fields = InvoiceFields(
        doc_type="invoice", vendor_name=" ".join(doc.vendor_lines),
        invoice_number=doc.invoice_number, invoice_date=doc.invoice_date,
        due_date=doc.due_date, po_number=doc.po_number, currency=doc.currency,
        subtotal=doc.subtotal, tax=doc.tax, total=doc.total, line_items=line_items,
    )
    return LabelRow(doc_id=doc.doc_id, file=f"hard/{doc.doc_id}.pdf", source="synthetic",
                    category="hard", expected_route=doc.expected_route, defects=(doc.defect,),
                    fields=fields)


def generate(out_dir: Path = HARD_DIR, labels_path: Path = HARD_LABELS_PATH) -> list[LabelRow]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for doc in DOCS:
        render(doc, out_dir / f"{doc.doc_id}.pdf")
    rows = [to_label(doc) for doc in DOCS]
    labels_path.write_text("".join(row.model_dump_json() + "\n" for row in rows))
    return rows


if __name__ == "__main__":
    written = generate()
    print(f"Wrote {len(written)} PDFs to {HARD_DIR} and labels to {HARD_LABELS_PATH}")

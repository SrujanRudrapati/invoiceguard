"""Pydantic models shared by labels, extraction output and evals."""

from datetime import date
from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")

DocType = Literal["invoice", "not_invoice"]
Route = Literal["approve", "review", "reject"]
Category = Literal[
    "clean", "messy", "arithmetic_error", "missing_field", "non_invoice", "injection"
]
Source = Literal["synthetic", "reviewer"]

SCALAR_FIELDS = (
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "due_date",
    "po_number",
    "currency",
    "subtotal",
    "tax",
    "total",
)
REQUIRED_FIELDS = tuple(f for f in SCALAR_FIELDS if f != "po_number")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LineItem(Strict):
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


class InvoiceFields(Strict):
    """Values as printed on the document; None means absent from the page."""

    doc_type: DocType
    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    po_number: str | None = None
    currency: str | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    line_items: tuple[LineItem, ...] = ()


class Box(Strict):
    """Rectangle in PDF points, origin top-left; page is 0-based."""

    page: int
    x0: float
    top: float
    x1: float
    bottom: float


class Extracted(Strict, Generic[T]):
    value: T | None = None
    evidence: str | None = None  # verbatim quote from the document
    evidence_boxes: tuple[Box, ...] = ()


class Invoice(Strict):
    """System output: every scalar carries the quote that supports it."""

    doc_type: DocType
    vendor_name: Extracted[str] = Extracted[str]()
    invoice_number: Extracted[str] = Extracted[str]()
    invoice_date: Extracted[date] = Extracted[date]()
    due_date: Extracted[date] = Extracted[date]()
    po_number: Extracted[str] = Extracted[str]()
    currency: Extracted[str] = Extracted[str]()
    subtotal: Extracted[Decimal] = Extracted[Decimal]()
    tax: Extracted[Decimal] = Extracted[Decimal]()
    total: Extracted[Decimal] = Extracted[Decimal]()
    line_items: tuple[LineItem, ...] = ()

    def values(self) -> InvoiceFields:
        """Drop evidence so output can be compared with labels."""
        scalars = {name: getattr(self, name).value for name in SCALAR_FIELDS}
        return InvoiceFields(doc_type=self.doc_type, line_items=self.line_items, **scalars)


class LabelRow(Strict):
    doc_id: str
    file: str
    source: Source
    category: Category
    expected_route: Route
    defects: tuple[str, ...] = ()
    fields: InvoiceFields

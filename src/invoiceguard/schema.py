"""Pydantic models shared by labels, extraction output and evals."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

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


class LabelRow(Strict):
    doc_id: str
    file: str
    source: Source
    category: Category
    expected_route: Route
    defects: tuple[str, ...] = ()
    fields: InvoiceFields

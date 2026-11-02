"""PDF -> text with one bounding box per character, so any text span maps back to the page."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from invoiceguard.schema import Box

log = logging.getLogger(__name__)
PAGE_BREAK = "\n\n"


class IngestError(Exception):
    pass


@dataclass(frozen=True)
class Document:
    text: str
    boxes: tuple[Box | None, ...]  # boxes[i] is text[i]'s box; None for layout spaces/newlines


def char_box(page: int, char: dict | None) -> Box | None:
    if char is None:
        return None
    return Box(page=page, x0=char["x0"], top=char["top"], x1=char["x1"], bottom=char["bottom"])


def load_document(path: Path) -> Document:
    texts: list[str] = []
    boxes: list[Box | None] = []
    try:
        with pdfplumber.open(path) as pdf:
            for n, page in enumerate(pdf.pages):
                if n:
                    texts.append(PAGE_BREAK)
                    boxes.extend([None] * len(PAGE_BREAK))
                textmap = page.get_textmap()  # same string as extract_text(), plus char refs
                texts.append(textmap.as_string)
                boxes.extend(char_box(n, char) for _, char in textmap.tuples)
    except (OSError, PdfminerException) as exc:
        log.error("ingest failed for %s: %s", path, exc)
        raise IngestError(f"cannot read {path}: {exc}") from exc
    return Document(text="".join(texts), boxes=tuple(boxes))

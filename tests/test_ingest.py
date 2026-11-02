from pathlib import Path

import pytest

from invoiceguard.ingest import IngestError, load_document


def test_text_and_boxes_align_on_every_generated_doc(generated):
    data_dir, rows = generated
    for row in rows:
        doc = load_document(data_dir / row.file)
        assert len(doc.text) == len(doc.boxes), row.doc_id
        pairs = zip(doc.text, doc.boxes, strict=True)
        assert all(box is None for ch, box in pairs if ch == "\n"), row.doc_id


def test_vendor_name_chars_have_boxes_on_page_zero(generated):
    data_dir, rows = generated
    row = rows[0]
    doc = load_document(data_dir / row.file)
    start = doc.text.index(row.fields.vendor_name)
    boxes = doc.boxes[start:start + len(row.fields.vendor_name)]
    assert all(b is not None and b.page == 0 and b.x1 > b.x0 for b in boxes if b)
    assert boxes[0] is not None


def test_unreadable_file_raises_typed_error(tmp_path: Path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(IngestError):
        load_document(bad)

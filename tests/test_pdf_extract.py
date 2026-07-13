import io

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.services import pdf_extract


def _build_pdf(text: str, *, encrypt: bool = False) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    page = writer.pages[0]

    content = f"BT /F1 12 Tf 72 700 Td ({text}) Tj ET".encode()
    stream_obj = DecodedStreamObject()
    stream_obj.set_data(content)
    writer._objects.append(stream_obj)
    page[NameObject("/Contents")] = writer.get_reference(stream_obj)

    font_dict = DictionaryObject()
    font_dict[NameObject("/Type")] = NameObject("/Font")
    font_dict[NameObject("/Subtype")] = NameObject("/Type1")
    font_dict[NameObject("/BaseFont")] = NameObject("/Helvetica")
    writer._objects.append(font_dict)
    font_ref = writer.get_reference(font_dict)

    resources = DictionaryObject()
    font_res = DictionaryObject()
    font_res[NameObject("/F1")] = font_ref
    resources[NameObject("/Font")] = font_res
    page[NameObject("/Resources")] = resources

    if encrypt:
        writer.encrypt(user_password="secret", owner_password="secret2")

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_extract_text_returns_real_content():
    pdf_bytes = _build_pdf("Clinic hours are 10am to 6pm")
    text = pdf_extract.extract_text(pdf_bytes)
    assert "Clinic hours are 10am to 6pm" in text


def test_extract_text_rejects_non_pdf_bytes():
    with pytest.raises(pdf_extract.PdfExtractionError):
        pdf_extract.extract_text(b"this is not a pdf at all")


def test_extract_text_rejects_encrypted_pdf():
    pdf_bytes = _build_pdf("Secret content", encrypt=True)
    with pytest.raises(pdf_extract.PdfExtractionError, match="password-protected"):
        pdf_extract.extract_text(pdf_bytes)


def test_extract_text_rejects_pdf_with_no_text_layer():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)

    with pytest.raises(pdf_extract.PdfExtractionError, match="scanned image"):
        pdf_extract.extract_text(buf.getvalue())

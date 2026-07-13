"""Plain text extraction from uploaded PDFs. Text-layer only -- scanned/
image-only PDFs (no embedded text layer) will extract as empty and should
be rejected by the caller rather than silently ingested as an empty
document."""

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_PAGES = 200


class PdfExtractionError(Exception):
    """Raised for any PDF that can't be read or has no extractable text."""


def extract_text(pdf_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except (PdfReadError, ValueError) as exc:
        raise PdfExtractionError("That file isn't a valid PDF.") from exc

    if reader.is_encrypted:
        raise PdfExtractionError("This PDF is password-protected -- remove the password and try again.")

    if len(reader.pages) > MAX_PDF_PAGES:
        raise PdfExtractionError(f"PDF has too many pages (max {MAX_PDF_PAGES}).")

    pages_text = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(p.strip() for p in pages_text if p.strip())

    if not text.strip():
        raise PdfExtractionError(
            "Couldn't find any text in this PDF -- it may be a scanned image "
            "without a text layer, which isn't supported yet."
        )
    return text

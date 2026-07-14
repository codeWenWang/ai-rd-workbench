from dataclasses import dataclass, field
from io import BytesIO

from pypdf import PdfReader

from app.domain.errors import ValidationError


@dataclass(slots=True)
class LoadedPage:
    content: str
    metadata: dict[str, object] = field(default_factory=dict)


def load_text(content: str, *, source_name: str = "text") -> list[LoadedPage]:
    text = content.strip()
    if not text:
        raise ValidationError("text content is empty")
    return [LoadedPage(text, {"source_name": source_name})]


def load_pdf(data: bytes, *, source_name: str, max_bytes: int, max_pages: int) -> list[LoadedPage]:
    if not data:
        raise ValidationError("PDF is empty")
    if len(data) > max_bytes:
        raise ValidationError("PDF exceeds upload size limit")
    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:
        raise ValidationError("invalid PDF file") from exc
    if len(reader.pages) > max_pages:
        raise ValidationError("PDF exceeds page limit")
    pages = [
        LoadedPage((page.extract_text() or "").strip(), {"source_name": source_name, "page_number": index})
        for index, page in enumerate(reader.pages, start=1)
    ]
    pages = [page for page in pages if page.content]
    if not pages:
        raise ValidationError("PDF contains no extractable text")
    return pages

import re
import uuid
from io import BytesIO

from pypdf import PdfReader

from app.config import settings


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)


def semantic_chunk(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """语义分块：按段落和句子边界切分，保持语义完整性。"""
    chunk_size = chunk_size or settings.rag_chunk_size
    overlap = overlap or settings.rag_chunk_overlap

    text = text.strip()
    if not text:
        return []

    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 1 <= chunk_size:
            current = f"{current}\n{para}".strip() if current else para
        else:
            if current:
                chunks.extend(_split_long_chunk(current, chunk_size, overlap))
            if len(para) <= chunk_size:
                current = para
            else:
                chunks.extend(_split_long_chunk(para, chunk_size, overlap))
                current = ""

    if current:
        chunks.extend(_split_long_chunk(current, chunk_size, overlap))

    return [c.strip() for c in chunks if c.strip()]


def _split_long_chunk(text: str, chunk_size: int, overlap: int) -> list[str]:
    sentences = re.split(r"(?<=[。！？.!?])\s*", text)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if not sentence:
            continue
        if len(current) + len(sentence) <= chunk_size:
            current += sentence
        else:
            if current:
                chunks.append(current)
            if len(sentence) > chunk_size:
                for i in range(0, len(sentence), chunk_size - overlap):
                    chunks.append(sentence[i : i + chunk_size])
                current = ""
            else:
                current = sentence

    if current:
        chunks.append(current)

    if overlap > 0 and len(chunks) > 1:
        merged = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:] if len(chunks[i - 1]) > overlap else chunks[i - 1]
            merged.append(prev_tail + chunks[i])
        return merged

    return chunks


def generate_id() -> str:
    return str(uuid.uuid4())

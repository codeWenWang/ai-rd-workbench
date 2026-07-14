from dataclasses import dataclass

import tiktoken

from app.infrastructure.documents.loaders import LoadedPage


@dataclass(slots=True)
class SplitPart:
    content: str
    token_count: int
    metadata: dict[str, object]


def split_pages(pages: list[LoadedPage], *, chunk_size: int = 500, chunk_overlap: int = 50) -> list[SplitPart]:
    encoding = tiktoken.get_encoding("cl100k_base")
    overlap = min(chunk_overlap, chunk_size - 1)
    step = chunk_size - overlap
    parts: list[SplitPart] = []
    for page in pages:
        tokens = encoding.encode(page.content)
        for start in range(0, len(tokens), step):
            selected = tokens[start : start + chunk_size]
            if not selected:
                break
            content = encoding.decode(selected).strip()
            if content:
                parts.append(SplitPart(content, len(selected), dict(page.metadata)))
            if start + chunk_size >= len(tokens):
                break
    return parts

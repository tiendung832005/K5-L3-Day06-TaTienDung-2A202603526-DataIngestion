"""Implement fixed-size and structure-aware chunking."""
from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int = 500, overlap: int = 50) -> list[Chunk]:
    """Split text into overlapping windows and retain page metadata."""
    if size <= 0:
        raise ValueError("size must be > 0")
    if overlap < 0 or overlap >= size:
        raise ValueError("0 <= overlap < size required")

    text = page.text.strip()
    if not text:
        return []

    chunks: list[Chunk] = []
    step = size - overlap
    start = 0
    idx = 0

    while start < len(text):
        end = min(start + size, len(text))
        piece = text[start:end].strip()
        if piece:
            chunk_id = f"{page.document_id}_p{page.page:03d}_fix_{idx:03d}"
            meta = {
                **page.metadata,
                "chunk_index": idx,
                "char_start": start,
                "char_end": end,
                "chunk_strategy": "fixed_size",
            }
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=page.document_id,
                    source=page.source,
                    page=page.page,
                    text=piece,
                    metadata=meta,
                )
            )
            idx += 1
        if end >= len(text):
            break
        start += step

    return chunks


def by_paragraph(page: DocumentPage, max_size: int = 600) -> list[Chunk]:
    """Group paragraphs, split oversized paragraphs and retain metadata."""
    if max_size <= 0:
        raise ValueError("max_size must be > 0")

    text = page.text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    current_buf = ""
    idx = 0

    def _flush(buf_text: str, c_idx: int) -> Chunk:
        chunk_id = f"{page.document_id}_p{page.page:03d}_par_{c_idx:03d}"
        meta = {
            **page.metadata,
            "chunk_index": c_idx,
            "chunk_strategy": "by_paragraph",
        }
        return Chunk(
            chunk_id=chunk_id,
            document_id=page.document_id,
            source=page.source,
            page=page.page,
            text=buf_text.strip(),
            metadata=meta,
        )

    for para in paragraphs:
        if len(para) > max_size:
            if current_buf:
                chunks.append(_flush(current_buf, idx))
                idx += 1
                current_buf = ""
            sentences = para.replace(". ", ".\n").split("\n")
            sub_buf = ""
            for sent in sentences:
                if not sub_buf:
                    sub_buf = sent
                elif len(sub_buf) + 1 + len(sent) <= max_size:
                    sub_buf += " " + sent
                else:
                    while len(sub_buf) > max_size:
                        chunks.append(_flush(sub_buf[:max_size], idx))
                        idx += 1
                        sub_buf = sub_buf[max_size:]
                    if sub_buf:
                        chunks.append(_flush(sub_buf, idx))
                        idx += 1
                    sub_buf = sent
            if sub_buf:
                current_buf = sub_buf
        else:
            if not current_buf:
                current_buf = para
            elif len(current_buf) + 2 + len(para) <= max_size:
                current_buf += "\n\n" + para
            else:
                chunks.append(_flush(current_buf, idx))
                idx += 1
                current_buf = para

    if current_buf:
        while len(current_buf) > max_size:
            chunks.append(_flush(current_buf[:max_size], idx))
            idx += 1
            current_buf = current_buf[max_size:]
        if current_buf.strip():
            chunks.append(_flush(current_buf, idx))

    return chunks

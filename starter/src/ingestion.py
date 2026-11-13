"""Read and normalize source data."""
import re
import unicodedata
from pathlib import Path
from pypdf import PdfReader
from .models import DocumentPage


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace without discarding paragraph structure."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Tách theo đoạn văn (2 dấu xuống dòng trở lên) trước, sau đó nối các dòng bị ngắt cứng trong cùng 1 đoạn
    raw_paragraphs = re.split(r"\n\s*\n", text)
    clean_paragraphs = []
    for para in raw_paragraphs:
        joined = re.sub(r"\s+", " ", para).strip()
        if joined:
            clean_paragraphs.append(joined)
    return "\n\n".join(clean_paragraphs)


def _detect_section(text: str) -> str:
    lowered = text.lower()
    for sec in ["security", "architecture", "deployment", "operations", "compliance"]:
        if f"section: {sec}" in lowered or f"[{sec}]" in lowered:
            return sec
    return "general"


def load_pdf(path: Path, document_id: str, source: str, extra_metadata: dict | None = None) -> list[DocumentPage]:
    """Extract each physical page; keep its page number and source."""
    reader = PdfReader(str(path))
    pages: list[DocumentPage] = []
    base_meta = extra_metadata or {}

    for idx, raw_page in enumerate(reader.pages, start=1):
        raw_text = raw_page.extract_text() or ""
        norm_text = normalize_text(raw_text)

        lower_text = norm_text.lower()
        is_excluded = (
            len(norm_text) < 100
            or "table of contents" in lower_text
            or "mục lục" in lower_text
            or "cover page" in lower_text
            or "references only" in lower_text
        )

        section = base_meta.get("section") or _detect_section(norm_text)
        page_meta = {
            **base_meta,
            "section": section,
            "char_count": len(norm_text),
            "is_empty": len(norm_text) == 0,
            "is_useful": not is_excluded,
        }

        pages.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=idx,
                text=norm_text,
                metadata=page_meta,
            )
        )
    return pages

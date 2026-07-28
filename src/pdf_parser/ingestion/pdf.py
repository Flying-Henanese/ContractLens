from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from pdf_parser.errors import InvalidPdfError


def iter_pdf_pages(path: Path) -> Iterator[tuple[int, bytes]]:
    """Yield one self-contained PDF per page using 1-based page numbers."""
    try:
        reader = PdfReader(path)
    except (OSError, PdfReadError) as exc:
        raise InvalidPdfError(f"无法读取 PDF：{path}") from exc

    if reader.is_encrypted and reader.decrypt("") == 0:
        raise InvalidPdfError("PDF 已加密，请先解除密码保护")
    if not reader.pages:
        raise InvalidPdfError("PDF 不包含任何页面")

    for page_num, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        output = BytesIO()
        writer.write(output)
        yield page_num, output.getvalue()

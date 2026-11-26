from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from pdf_parser.errors import InvalidPdfError


@dataclass(frozen=True)
class PdfPart:
    content: bytes
    first_page: int
    page_count: int


def read_pdf_parts(path: Path, *, part_count: int) -> list[PdfPart]:
    """Read a PDF intact or divide it into balanced, contiguous page ranges."""
    if part_count < 1:
        raise ValueError("part_count must be positive")

    try:
        with path.open("rb") as stream:
            reader = PdfReader(stream)
            page_count = _validate_pdf(reader)
            part_count = min(part_count, page_count)
            if part_count == 1:
                stream.seek(0)
                return [PdfPart(stream.read(), first_page=1, page_count=page_count)]

            base_size, remainder = divmod(page_count, part_count)
            parts: list[PdfPart] = []
            start = 0
            for index in range(part_count):
                size = base_size + int(index < remainder)
                stop = start + size
                parts.append(PdfPart(_write_pages(reader, start, stop), start + 1, size))
                start = stop
            return parts
    except (OSError, PdfReadError) as exc:
        raise InvalidPdfError(f"无法读取 PDF：{path}") from exc


def count_pdf_pages(path: Path) -> int:
    try:
        return _validate_pdf(PdfReader(path))
    except (OSError, PdfReadError) as exc:
        raise InvalidPdfError(f"无法读取 PDF：{path}") from exc


def iter_pdf_pages(path: Path) -> Iterator[tuple[int, bytes]]:
    """Yield one self-contained PDF per page using 1-based page numbers."""
    try:
        reader = PdfReader(path)
        page_count = _validate_pdf(reader)
    except (OSError, PdfReadError) as exc:
        raise InvalidPdfError(f"无法读取 PDF：{path}") from exc

    for page_index in range(page_count):
        yield page_index + 1, _write_pages(reader, page_index, page_index + 1)


def _write_pages(reader: PdfReader, start: int, stop: int) -> bytes:
    writer = PdfWriter()
    for page_index in range(start, stop):
        writer.add_page(reader.pages[page_index])
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _validate_pdf(reader: PdfReader) -> int:
    if reader.is_encrypted and reader.decrypt("") == 0:
        raise InvalidPdfError("PDF 已加密，请先解除密码保护")
    page_count = len(reader.pages)
    if page_count == 0:
        raise InvalidPdfError("PDF 不包含任何页面")
    return page_count

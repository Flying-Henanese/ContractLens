from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Iterator
from itertools import islice
from pathlib import Path
from typing import Any, Protocol

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from pdf_parser.clients.paddlex import PaddleXClient
from pdf_parser.config import Settings
from pdf_parser.errors import InvalidImageError, InvalidPdfError
from pdf_parser.ingestion.image import detect_image_format
from pdf_parser.ingestion.pdf import iter_pdf_pages
from pdf_parser.models import PageResult, ParseResponse, ResultData
from pdf_parser.normalization.paddlex import normalize_page

ProgressCallback = Callable[[int, int], None]


class PageClient(Protocol):
    async def parse_pdf_page(self, page_pdf: bytes, page_num: int) -> dict[str, Any]: ...
    async def parse_image(self, image: bytes) -> dict[str, Any]: ...


async def parse_pdf(
    path: Path,
    settings: Settings | None = None,
    progress: ProgressCallback | None = None,
    client: PageClient | None = None,
) -> ParseResponse:
    settings = settings or Settings()
    total_pages = _count_pages(path)
    pages = iter_pdf_pages(path)

    if client is not None:
        page_results = await _parse_pages(pages, total_pages, settings, client, progress)
    else:
        async with PaddleXClient(settings) as paddlex:
            page_results = await _parse_pages(pages, total_pages, settings, paddlex, progress)

    return ParseResponse(data=ResultData(doc_recognize_result=page_results))


async def parse_image(
    path: Path,
    settings: Settings | None = None,
    progress: ProgressCallback | None = None,
    client: PageClient | None = None,
) -> ParseResponse:
    try:
        image = path.read_bytes()
    except OSError as exc:
        raise InvalidImageError(f"Unable to read image: {path}") from exc
    if detect_image_format(image) is None:
        raise InvalidImageError("Unsupported or invalid image file")

    settings = settings or Settings()
    started_at = time.perf_counter()
    if client is not None:
        raw_page = await client.parse_image(image)
    else:
        async with PaddleXClient(settings) as paddlex:
            raw_page = await paddlex.parse_image(image)

    page_result = normalize_page(raw_page, page_num=1, started_at=started_at)
    if progress:
        progress(1, 1)
    return ParseResponse(data=ResultData(doc_recognize_result=[page_result]))


async def _parse_pages(
    pages: Iterator[tuple[int, bytes]],
    total_pages: int,
    settings: Settings,
    client: PageClient,
    progress: ProgressCallback | None,
) -> list[PageResult]:
    results: list[PageResult] = []
    while batch := list(islice(pages, settings.concurrency)):
        parsed = await asyncio.gather(
            *(_parse_one(client, page_num, page_pdf) for page_num, page_pdf in batch)
        )
        results.extend(parsed)
        if progress:
            progress(len(results), total_pages)
    results.sort(key=lambda page: page.page_num)
    return results


async def _parse_one(client: PageClient, page_num: int, page_pdf: bytes) -> PageResult:
    started_at = time.perf_counter()
    raw_page = await client.parse_pdf_page(page_pdf, page_num)
    return normalize_page(raw_page, page_num, started_at)


def _count_pages(path: Path) -> int:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise InvalidPdfError("PDF 已加密，请先解除密码保护")
        count = len(reader.pages)
    except (OSError, PdfReadError) as exc:
        raise InvalidPdfError(f"无法读取 PDF：{path}") from exc
    if count == 0:
        raise InvalidPdfError("PDF 不包含任何页面")
    return count

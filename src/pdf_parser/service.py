from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Iterator
from itertools import islice
from pathlib import Path
from typing import Any, Protocol

from pdf_parser.clients.paddlex import PaddleXClient
from pdf_parser.config import Settings
from pdf_parser.errors import InvalidImageError
from pdf_parser.ingestion.image import detect_image_format
from pdf_parser.ingestion.pdf import PdfPart, count_pdf_pages, iter_pdf_pages, read_pdf_parts
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
    total_pages = count_pdf_pages(path)
    pages = iter_pdf_pages(path)

    if client is not None:
        page_results = await _parse_pages(pages, total_pages, settings, client, progress)
    else:
        async with PaddleXClient(settings) as paddlex:
            page_results = await _parse_pages(pages, total_pages, settings, paddlex, progress)

    return ParseResponse(data=ResultData(doc_recognize_result=page_results))


async def parse_pdf_whole(path: Path, settings: Settings) -> ParseResponse:
    return await _parse_pdf_parts(path, settings, part_count=1)


async def parse_pdf_split(path: Path, settings: Settings) -> ParseResponse:
    return await _parse_pdf_parts(path, settings, part_count=4)


async def _parse_pdf_parts(path: Path, settings: Settings, *, part_count: int) -> ParseResponse:
    parts = read_pdf_parts(path, part_count=part_count)
    async with PaddleXClient(settings) as client:
        tasks = [asyncio.create_task(_parse_pdf_part(client, part)) for part in parts]
        try:
            part_results = await asyncio.gather(*tasks)
        finally:
            # Drain cancelled requests before closing the shared client.
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    return ParseResponse(
        data=ResultData(doc_recognize_result=[page for pages in part_results for page in pages])
    )


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


async def _parse_pdf_part(client: PaddleXClient, part: PdfPart) -> list[PageResult]:
    started_at = time.perf_counter()
    raw_pages = await client.parse_pdf_pages(
        part.content, first_page=part.first_page, page_count=part.page_count
    )
    return [
        normalize_page(raw_page, page_num, started_at)
        for page_num, raw_page in enumerate(raw_pages, start=part.first_page)
    ]

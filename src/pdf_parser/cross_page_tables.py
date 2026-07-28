"""Detect tables that may continue from the preceding page.

This module is intentionally independent from PDF parsing and PaddleX normalization.
It consumes an already generated result JSON and reports candidates without changing
the source document or merging table contents.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CrossPageTableCandidate:
    previous_page_num: int
    previous_detail_index: int
    current_page_num: int
    current_detail_index: int
    column_count: int
    previous_layout_bbox: list[int]
    current_layout_bbox: list[int]


@dataclass(frozen=True)
class _TableElement:
    page_num: int
    detail_index: int
    column_count: int
    layout_bbox: list[int]


class _TableColumnParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.table_depth = 0
        self.in_row = False
        self.current_columns = 0
        self.row_columns: list[int] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self.table_depth += 1
            return
        if self.table_depth != 1:
            return
        if tag == "tr":
            self.in_row = True
            self.current_columns = 0
        elif tag in {"td", "th"} and self.in_row:
            colspan = dict(attrs).get("colspan")
            try:
                span = int(colspan) if colspan is not None else 1
            except ValueError:
                span = 1
            self.current_columns += max(span, 1)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "table":
            self.table_depth = max(self.table_depth - 1, 0)
        elif tag == "tr" and self.table_depth == 1 and self.in_row:
            self.row_columns.append(self.current_columns)
            self.in_row = False


def table_column_count(table_html: str) -> int | None:
    """Return the maximum logical column count, expanding HTML ``colspan`` values."""
    if not table_html.strip():
        return None
    parser = _TableColumnParser()
    parser.feed(table_html)
    parser.close()
    nonempty_rows = [count for count in parser.row_columns if count > 0]
    return max(nonempty_rows, default=None)


def detect_cross_page_tables(payload: dict[str, Any]) -> list[CrossPageTableCandidate]:
    """Detect page-top tables whose column count matches the preceding page's last table."""
    pages = _extract_pages(payload)
    pages_by_number = {
        page_num: page for page in pages if (page_num := _page_number(page)) is not None
    }
    candidates: list[CrossPageTableCandidate] = []

    for current_page_num in sorted(pages_by_number):
        previous_page = pages_by_number.get(current_page_num - 1)
        if previous_page is None:
            continue
        current_page = pages_by_number[current_page_num]
        previous_table = _last_table(previous_page)
        if previous_table is None:
            continue

        details = _details(current_page)
        for table in _tables(current_page):
            if not _has_no_element_above(table, details):
                continue
            if table.column_count != previous_table.column_count:
                continue
            candidates.append(
                CrossPageTableCandidate(
                    previous_page_num=previous_table.page_num,
                    previous_detail_index=previous_table.detail_index,
                    current_page_num=table.page_num,
                    current_detail_index=table.detail_index,
                    column_count=table.column_count,
                    previous_layout_bbox=previous_table.layout_bbox,
                    current_layout_bbox=table.layout_bbox,
                )
            )

    return candidates


def detect_cross_page_tables_file(path: str | Path) -> list[CrossPageTableCandidate]:
    """Read a parser result JSON file and return cross-page table candidates."""
    source = Path(path)
    with source.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError("结果 JSON 顶层必须是对象")
    return detect_cross_page_tables(payload)


def _extract_pages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    pages = data.get("doc_recognize_result") if isinstance(data, dict) else None
    if not isinstance(pages, list):
        raise ValueError("结果 JSON 缺少 data.doc_recognize_result 数组")
    return [page for page in pages if isinstance(page, dict)]


def _page_number(page: dict[str, Any]) -> int | None:
    value = page.get("page_num")
    return value if isinstance(value, int) and value >= 1 else None


def _details(page: dict[str, Any]) -> list[dict[str, Any]]:
    details = page.get("document_details")
    if not isinstance(details, list):
        return []
    return [detail for detail in details if isinstance(detail, dict)]


def _tables(page: dict[str, Any]) -> list[_TableElement]:
    page_num = _page_number(page)
    if page_num is None:
        return []
    tables = []
    for detail_index, detail in enumerate(_details(page)):
        if not _is_table(detail):
            continue
        bbox = _bbox(detail.get("layout_bbox"))
        columns = table_column_count(str(detail.get("text") or ""))
        if not bbox or columns is None:
            continue
        tables.append(
            _TableElement(
                page_num=page_num,
                detail_index=detail_index,
                column_count=columns,
                layout_bbox=bbox,
            )
        )
    return tables


def _is_table(detail: dict[str, Any]) -> bool:
    element_type = str(detail.get("type") or "").casefold()
    layout_label = str(detail.get("layout_label") or "").casefold()
    return element_type == "table" or layout_label == "table"


def _bbox(value: Any) -> list[int]:
    if not isinstance(value, list) or len(value) != 4:
        return []
    if not all(isinstance(item, (int, float)) for item in value):
        return []
    bbox = [round(float(item)) for item in value]
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return []
    return bbox


def _last_table(page: dict[str, Any]) -> _TableElement | None:
    tables = _tables(page)
    if not tables:
        return None
    return max(
        tables,
        key=lambda item: (item.layout_bbox[3], item.layout_bbox[1], item.detail_index),
    )


def _has_no_element_above(table: _TableElement, details: list[dict[str, Any]]) -> bool:
    table_top = table.layout_bbox[1]
    for detail_index, detail in enumerate(details):
        if detail_index == table.detail_index:
            continue
        other_bbox = _bbox(detail.get("layout_bbox"))
        if other_bbox and other_bbox[1] < table_top:
            return False
    return True


def _main() -> None:
    parser = argparse.ArgumentParser(description="识别结果 JSON 中可能跨页的表格")
    parser.add_argument("json_file", type=Path, help="pdf-parser 生成的结果 JSON")
    args = parser.parse_args()
    try:
        candidates = detect_cross_page_tables_file(args.json_file)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    result = {"cross_page_table_candidates": [asdict(item) for item in candidates]}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()

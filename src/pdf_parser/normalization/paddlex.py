from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

from pdf_parser.models import DocumentDetail, PageResult, Point, Position
from pdf_parser.normalization.seal import append_seal_details, build_content

LABEL_TYPE_MAP = {
    "doc_title": "Title",
    "title": "Title",
    "paragraph_title": "Section-header",
    "section_header": "Section-header",
    "table": "Table",
    "image": "Picture",
    "figure": "Picture",
    "chart": "Picture",
    "formula": "Formula",
    "seal": "Seal",
}


def normalize_page(raw_page: dict[str, Any], page_num: int, started_at: float) -> PageResult:
    pruned = raw_page.get("prunedResult") or {}
    width = _positive_int(pruned.get("width"), default=0)
    height = _positive_int(pruned.get("height"), default=0)
    ocr_lines = _extract_ocr_lines(pruned.get("overall_ocr_res") or {})

    raw_blocks = pruned.get("parsing_res_list") or []
    blocks = [block for block in raw_blocks if isinstance(block, dict)]
    blocks.sort(key=_block_sort_key)
    seal_results = pruned.get("seal_res_list") or []
    if isinstance(seal_results, list) and any(isinstance(result, dict) for result in seal_results):
        blocks = [
            block
            for block in blocks
            if str(block.get("block_label") or block.get("label") or "").lower() != "seal"
        ]

    details: list[DocumentDetail] = []
    for index, block in enumerate(blocks):
        bbox = _bbox(block.get("block_bbox") or block.get("bbox"))
        label = str(block.get("block_label") or block.get("label") or "text")
        layout_fallback_text = _clean_text(block.get("block_content") or block.get("text"))
        text = layout_fallback_text
        if not text and bbox:
            text = _text_inside_bbox(ocr_lines, bbox)
        details.append(
            _make_detail(
                block,
                index,
                label,
                text,
                bbox,
                layout_fallback_text=layout_fallback_text,
            )
        )

    if not details:
        details = _details_from_ocr(ocr_lines)

    append_seal_details(
        details,
        seal_results,
        pruned.get("layout_det_res") or {},
        raw_page.get("markdown") or {},
        page_num,
        width,
        height,
    )
    content, content_references = build_content(details)

    if not content:
        markdown = raw_page.get("markdown") or {}
        content = _clean_text(markdown.get("text"))
        content_references = []

    if not width or not height:
        width, height = _infer_dimensions(details, width, height)

    return PageResult(
        page_num=page_num,
        document_content=content,
        image_width=width,
        image_height=height,
        document_details=details,
        content_references=content_references,
        parse_time=round(time.perf_counter() - started_at, 3),
    )


def _extract_ocr_lines(ocr: dict[str, Any]) -> list[tuple[str, float | None, list[int]]]:
    texts = ocr.get("rec_texts") or []
    scores = ocr.get("rec_scores") or []
    boxes = ocr.get("rec_boxes") or ocr.get("rec_polys") or []
    lines: list[tuple[str, float | None, list[int]]] = []
    for index, value in enumerate(texts):
        text = _clean_text(value)
        if not text:
            continue
        score = _float_or_none(scores[index]) if index < len(scores) else None
        bbox = _bbox(boxes[index]) if index < len(boxes) else []
        lines.append((text, score, bbox))
    lines.sort(key=lambda item: (item[2][1], item[2][0]) if item[2] else (10**9, 10**9))
    return lines


def _details_from_ocr(
    lines: Iterable[tuple[str, float | None, list[int]]],
) -> list[DocumentDetail]:
    details = []
    for index, (text, score, bbox) in enumerate(lines):
        details.append(
            DocumentDetail(
                type="Text",
                text=text,
                position=_position(bbox),
                layout_label="text",
                layout_mapped_type="Text",
                layout_score=score,
                layout_order=float(index),
                layout_reading_index=index,
                layout_bbox=bbox,
            )
        )
    return details


def _make_detail(
    block: dict[str, Any],
    index: int,
    label: str,
    text: str,
    bbox: list[int],
    *,
    layout_fallback_text: str,
) -> DocumentDetail:
    mapped_type = LABEL_TYPE_MAP.get(label.lower(), "Text")
    order = _float_or_none(block.get("block_order"))
    score = _float_or_none(
        block.get("layout_score") or block.get("block_score") or block.get("score")
    )
    return DocumentDetail(
        type=mapped_type,
        text=text,
        position=_position(bbox),
        layout_label=label,
        layout_mapped_type=mapped_type,
        layout_score=score,
        layout_order=float(index) if order is None else order,
        layout_reading_index=index,
        layout_bbox=bbox,
        layout_fallback_text=layout_fallback_text,
    )


def _text_inside_bbox(
    lines: Iterable[tuple[str, float | None, list[int]]], block_bbox: list[int]
) -> str:
    selected = []
    x0, y0, x1, y1 = block_bbox
    for text, _, bbox in lines:
        if not bbox:
            continue
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            selected.append(text)
    return "\n".join(selected)


def _block_sort_key(block: dict[str, Any]) -> tuple[float, float, float]:
    order = _float_or_none(block.get("block_order"))
    bbox = _bbox(block.get("block_bbox") or block.get("bbox"))
    if order is not None:
        return (0, order, 0)
    if bbox:
        return (1, bbox[1], bbox[0])
    return (2, _float_or_none(block.get("block_id")) or 0, 0)


def _bbox(value: Any) -> list[int]:
    if not isinstance(value, (list, tuple)):
        return []
    if len(value) == 4 and all(isinstance(item, (int, float)) for item in value):
        return [round(float(item)) for item in value]
    points = [item for item in value if isinstance(item, (list, tuple)) and len(item) >= 2]
    if points:
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        return [round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys))]
    return []


def _position(bbox: list[int]) -> list[Position]:
    if not bbox:
        return []
    x0, y0, x1, y1 = bbox
    return [
        Position(
            points=[
                Point(x=x0, y=y0),
                Point(x=x1, y=y0),
                Point(x=x1, y=y1),
                Point(x=x0, y=y1),
            ]
        )
    ]


def _infer_dimensions(
    details: Iterable[DocumentDetail], width: int, height: int
) -> tuple[int, int]:
    boxes = [detail.layout_bbox for detail in details if detail.layout_bbox]
    if not boxes:
        return width, height
    return width or max(box[2] for box in boxes), height or max(box[3] for box in boxes)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def _positive_int(value: Any, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

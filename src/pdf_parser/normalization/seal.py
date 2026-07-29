from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pdf_parser.models import (
    ContentReference,
    DocumentDetail,
    Point,
    Position,
    SealDetail,
    SealText,
)

_SEAL_IMAGE_PATTERN = re.compile(
    r"(?:^|/)img_in_seal_box_(-?\d+)_(-?\d+)_(-?\d+)_(-?\d+)\.(?:jpg|jpeg|png)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _SealRegion:
    bbox: list[int]
    score: float | None = None
    fallback_text: str = ""


def append_seal_details(
    details: list[DocumentDetail],
    seal_results: Any,
    layout_result: Any,
    markdown: Any,
    page_num: int,
    page_width: int,
    page_height: int,
    parsing_blocks: Any,
) -> None:
    results = (
        [result for result in seal_results if isinstance(result, dict)]
        if isinstance(seal_results, list)
        else []
    )
    if not results:
        _append_detected_seal_details(
            details,
            layout_result,
            parsing_blocks,
            page_num,
            page_width,
            page_height,
        )
        return

    regions = _resolve_seal_regions(
        results,
        layout_result,
        markdown,
        page_width,
        page_height,
    )
    pairs = list(zip(results, regions, strict=True))
    if pairs and all(region is not None for _, region in pairs):
        pairs.sort(key=lambda pair: (pair[1].bbox[1], pair[1].bbox[0]))

    for seal_index, (result, region) in enumerate(pairs, start=1):
        ocr = result.get("seal_ocr_res") or result.get("ocr_res") or result
        if not isinstance(ocr, dict):
            continue

        seal_texts = _extract_seal_texts(ocr, region, page_width, page_height)
        reference_token = f"[印章{seal_index}]"
        recognized_text = "\n".join(item.text for item in seal_texts if item.text)
        detail_text = f"{reference_token} {recognized_text}" if recognized_text else reference_token
        index = len(details)
        region_bbox = region.bbox if region is not None else _union_bbox(seal_texts)
        details.append(
            SealDetail(
                text=detail_text,
                position=_position_from_bbox(region_bbox),
                layout_score=region.score if region is not None else None,
                layout_order=float(index),
                layout_reading_index=index,
                layout_bbox=region_bbox,
                seal_id=f"page-{page_num}-seal-{seal_index}",
                seal_index=seal_index,
                reference_token=reference_token,
                seal_region_bbox=region.bbox if region is not None else [],
                texts=seal_texts,
            )
        )


def _append_detected_seal_details(
    details: list[DocumentDetail],
    layout_result: Any,
    parsing_blocks: Any,
    page_num: int,
    page_width: int,
    page_height: int,
) -> None:
    regions = _standalone_seal_regions(
        layout_result,
        parsing_blocks,
        page_width,
        page_height,
    )
    for seal_index, region in enumerate(regions, start=1):
        reference_token = f"[印章{seal_index}]"
        index = len(details)
        details.append(
            SealDetail(
                text=reference_token,
                position=_position_from_bbox(region.bbox),
                layout_score=region.score,
                layout_order=float(index),
                layout_reading_index=index,
                layout_bbox=region.bbox,
                layout_fallback_text=region.fallback_text,
                seal_id=f"page-{page_num}-seal-{seal_index}",
                seal_index=seal_index,
                reference_token=reference_token,
                seal_region_bbox=region.bbox,
                texts=[],
            )
        )


def build_content(
    details: Iterable[DocumentDetail],
) -> tuple[str, list[ContentReference]]:
    parts: list[str] = []
    references: list[ContentReference] = []
    offset = 0
    for detail in details:
        if not detail.text:
            continue
        if parts:
            offset += 1
        detail_start = offset
        parts.append(detail.text)
        if isinstance(detail, SealDetail):
            token_offset = detail.text.find(detail.reference_token)
            if token_offset >= 0:
                start = detail_start + token_offset
                references.append(
                    ContentReference(
                        token=detail.reference_token,
                        target_id=detail.seal_id,
                        start_offset=start,
                        end_offset=start + len(detail.reference_token),
                    )
                )
        offset += len(detail.text)
    return "\n".join(parts).strip(), references


def _standalone_seal_regions(
    layout_result: Any,
    parsing_blocks: Any,
    page_width: int,
    page_height: int,
) -> list[_SealRegion]:
    layout_regions = _layout_seal_regions(layout_result)
    parsing_regions = _parsing_seal_regions(parsing_blocks)
    fallback_by_bbox = {
        tuple(region.bbox): region.fallback_text
        for region in parsing_regions
        if region.fallback_text
    }
    if layout_regions:
        regions = [
            _SealRegion(
                region.bbox,
                region.score,
                fallback_by_bbox.get(tuple(region.bbox), ""),
            )
            for region in layout_regions
        ]
    else:
        regions = parsing_regions

    clamped = [_clamp_region(region, page_width, page_height) for region in regions]
    clamped.sort(key=lambda region: (region.bbox[1], region.bbox[0]))
    return clamped


def _resolve_seal_regions(
    seal_results: list[dict[str, Any]],
    layout_result: Any,
    markdown: Any,
    page_width: int,
    page_height: int,
) -> list[_SealRegion | None]:
    explicit_regions = [_explicit_seal_region(result) for result in seal_results]
    markdown_regions = _markdown_seal_regions(markdown)
    layout_regions = _layout_seal_regions(layout_result)
    markdown_matches = len(markdown_regions) == len(seal_results)
    layout_matches = len(layout_regions) == len(seal_results)

    resolved: list[_SealRegion | None] = []
    for index, explicit_region in enumerate(explicit_regions):
        if explicit_region is not None:
            region = explicit_region
        elif markdown_matches:
            score = layout_regions[index].score if layout_matches else None
            region = _SealRegion(markdown_regions[index].bbox, score)
        elif layout_matches:
            region = layout_regions[index]
        else:
            region = None
        resolved.append(
            _clamp_region(region, page_width, page_height) if region is not None else None
        )
    return resolved


def _explicit_seal_region(result: dict[str, Any]) -> _SealRegion | None:
    for key in ("crop_bbox", "seal_region_bbox", "region_bbox"):
        bbox = _bbox(result.get(key))
        if bbox:
            return _SealRegion(bbox)
    return None


def _markdown_seal_regions(markdown: Any) -> list[_SealRegion]:
    if not isinstance(markdown, dict):
        return []
    images = markdown.get("images") or {}
    if not isinstance(images, dict):
        return []
    regions = []
    for path in images:
        match = _SEAL_IMAGE_PATTERN.search(str(path).replace("\\", "/"))
        if match:
            regions.append(_SealRegion([int(value) for value in match.groups()]))
    return regions


def _parsing_seal_regions(parsing_blocks: Any) -> list[_SealRegion]:
    if not isinstance(parsing_blocks, list):
        return []
    regions = []
    for block in parsing_blocks:
        if not isinstance(block, dict):
            continue
        bbox = _bbox(block.get("block_bbox") or block.get("bbox"))
        if bbox:
            regions.append(
                _SealRegion(
                    bbox,
                    fallback_text=_clean_text(block.get("block_content") or block.get("text")),
                )
            )
    return regions


def _layout_seal_regions(layout_result: Any) -> list[_SealRegion]:
    if not isinstance(layout_result, dict):
        return []
    regions = []
    for box in layout_result.get("boxes") or []:
        if not isinstance(box, dict):
            continue
        if str(box.get("label", "")).lower() != "seal":
            continue
        bbox = _crop_bbox(box.get("coordinate"))
        if bbox:
            regions.append(_SealRegion(bbox, _float_or_none(box.get("score"))))
    return regions


def _extract_seal_texts(
    ocr: dict[str, Any],
    region: _SealRegion | None,
    page_width: int,
    page_height: int,
) -> list[SealText]:
    texts = ocr.get("rec_texts") or []
    scores = ocr.get("rec_scores") or []
    polygons = ocr.get("rec_polys") or []
    boxes = ocr.get("rec_boxes") or []
    results = []
    for index, value in enumerate(texts):
        text = _clean_text(value)
        if not text:
            continue
        score = _float_or_none(scores[index]) if index < len(scores) else None
        local_polygon = _polygon(polygons[index]) if index < len(polygons) else []
        if not local_polygon and index < len(boxes):
            local_polygon = _polygon_from_bbox(_bbox(boxes[index]))
        page_polygon = []
        if region is not None and local_polygon:
            page_polygon = _translate_polygon(local_polygon, region.bbox)
            page_polygon = _clamp_polygon(page_polygon, page_width, page_height)
        results.append(
            SealText(
                text=text,
                ocr_confidence=score,
                position=_position_from_polygon(page_polygon),
                layout_bbox=_bbox(page_polygon),
            )
        )
    return results


def _crop_bbox(value: Any) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return []
    try:
        bbox = [int(float(item)) for item in value]
    except (TypeError, ValueError):
        return []
    return bbox if bbox[2] > bbox[0] and bbox[3] > bbox[1] else []


def _bbox(value: Any) -> list[int]:
    if not isinstance(value, (list, tuple)):
        return []
    if len(value) == 4 and all(isinstance(item, (int, float)) for item in value):
        return [round(float(item)) for item in value]
    polygon = _polygon(value)
    if not polygon:
        return []
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return [min(xs), min(ys), max(xs), max(ys)]


def _polygon(value: Any) -> list[list[int]]:
    if not isinstance(value, (list, tuple)):
        return []
    polygon = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            polygon.append([round(float(point[0])), round(float(point[1]))])
        except (TypeError, ValueError):
            continue
    return polygon


def _polygon_from_bbox(bbox: list[int]) -> list[list[int]]:
    if not bbox:
        return []
    x0, y0, x1, y1 = bbox
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _translate_polygon(polygon: list[list[int]], crop_bbox: list[int]) -> list[list[int]]:
    offset_x, offset_y = crop_bbox[0], crop_bbox[1]
    return [[x + offset_x, y + offset_y] for x, y in polygon]


def _clamp_polygon(polygon: list[list[int]], page_width: int, page_height: int) -> list[list[int]]:
    if page_width <= 0 or page_height <= 0:
        return polygon
    return [[min(max(x, 0), page_width), min(max(y, 0), page_height)] for x, y in polygon]


def _clamp_region(region: _SealRegion, page_width: int, page_height: int) -> _SealRegion:
    bbox = region.bbox
    if page_width > 0 and page_height > 0:
        x0, y0, x1, y1 = bbox
        bbox = [
            min(max(x0, 0), page_width),
            min(max(y0, 0), page_height),
            min(max(x1, 0), page_width),
            min(max(y1, 0), page_height),
        ]
    return _SealRegion(bbox, region.score, region.fallback_text)


def _position_from_bbox(bbox: list[int]) -> list[Position]:
    return _position_from_polygon(_polygon_from_bbox(bbox))


def _position_from_polygon(polygon: list[list[int]]) -> list[Position]:
    if not polygon:
        return []
    return [Position(points=[Point(x=x, y=y) for x, y in polygon])]


def _union_bbox(texts: Iterable[SealText]) -> list[int]:
    boxes = [text.layout_bbox for text in texts if text.layout_bbox]
    if not boxes:
        return []
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

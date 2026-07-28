from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from pdf_parser.models import ParseResponse


class ContractValidationError(ValueError):
    """The normalized parser result violates the public output contract."""


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise ContractValidationError(message)


def _validate_bbox(value: Any, width: int, height: int, path: str) -> None:
    if value == []:
        return
    _expect(
        isinstance(value, list) and len(value) == 4,
        f"{path} must be [] or [x0,y0,x1,y1]",
    )
    _expect(all(isinstance(item, (int, float)) for item in value), f"{path} must be numeric")
    x0, y0, x1, y1 = value
    _expect(0 <= x0 <= x1 <= width, f"{path} x coordinates exceed width {width}: {value}")
    _expect(0 <= y0 <= y1 <= height, f"{path} y coordinates exceed height {height}: {value}")


def _validate_positions(value: Any, width: int, height: int, path: str) -> None:
    _expect(isinstance(value, list), f"{path} must be a list")
    for position_index, position in enumerate(value):
        position_path = f"{path}[{position_index}]"
        _expect(isinstance(position, dict), f"{position_path} must be an object")
        points = position.get("points")
        _expect(isinstance(points, list) and points, f"{position_path}.points must be non-empty")
        for point_index, point in enumerate(points):
            point_path = f"{position_path}.points[{point_index}]"
            _expect(isinstance(point, dict), f"{point_path} must be an object")
            x, y = point.get("x"), point.get("y")
            _expect(isinstance(x, (int, float)), f"{point_path}.x must be numeric")
            _expect(isinstance(y, (int, float)), f"{point_path}.y must be numeric")
            _expect(0 <= x <= width and 0 <= y <= height, f"{point_path} is outside the page")


def _validate_page(page: Any, page_index: int) -> int:
    path = f"data.doc_recognize_result[{page_index}]"
    _expect(isinstance(page, dict), f"{path} must be an object")

    page_num = page.get("page_num")
    _expect(isinstance(page_num, int) and page_num >= 1, f"{path}.page_num must be positive")
    content = page.get("document_content")
    _expect(
        isinstance(content, str) and content.strip(), f"{path}.document_content must be non-empty"
    )
    width, height = page.get("image_width"), page.get("image_height")
    _expect(isinstance(width, int) and width > 0, f"{path}.image_width must be positive")
    _expect(isinstance(height, int) and height > 0, f"{path}.image_height must be positive")
    _expect(isinstance(page.get("parse_time"), (int, float)), f"{path}.parse_time must be numeric")

    details = page.get("document_details")
    references = page.get("content_references")
    _expect(isinstance(details, list), f"{path}.document_details must be a list")
    _expect(isinstance(references, list), f"{path}.content_references must be a list")

    seal_ids: set[str] = set()
    for detail_index, detail in enumerate(details):
        detail_path = f"{path}.document_details[{detail_index}]"
        _expect(isinstance(detail, dict), f"{detail_path} must be an object")
        _validate_bbox(detail.get("layout_bbox"), width, height, f"{detail_path}.layout_bbox")
        _validate_positions(detail.get("position", []), width, height, f"{detail_path}.position")
        if detail.get("type") != "Seal":
            continue

        seal_id = detail.get("seal_id")
        token = detail.get("reference_token")
        _expect(isinstance(seal_id, str) and seal_id, f"{detail_path}.seal_id is required")
        _expect(seal_id not in seal_ids, f"duplicate seal_id: {seal_id}")
        seal_ids.add(seal_id)
        _expect(isinstance(token, str) and token, f"{detail_path}.reference_token is required")
        _expect(
            detail.get("coordinate_space") == "page_pixels_top_left",
            f"{detail_path}.coordinate_space is invalid",
        )
        _validate_bbox(
            detail.get("seal_region_bbox"),
            width,
            height,
            f"{detail_path}.seal_region_bbox",
        )
        texts = detail.get("texts")
        _expect(isinstance(texts, list), f"{detail_path}.texts must be a list")
        for text_index, seal_text in enumerate(texts):
            text_path = f"{detail_path}.texts[{text_index}]"
            _expect(isinstance(seal_text, dict), f"{text_path} must be an object")
            _validate_bbox(seal_text.get("layout_bbox"), width, height, f"{text_path}.layout_bbox")
            _validate_positions(
                seal_text.get("position", []), width, height, f"{text_path}.position"
            )

    referenced_ids: set[str] = set()
    for reference_index, reference in enumerate(references):
        reference_path = f"{path}.content_references[{reference_index}]"
        _expect(isinstance(reference, dict), f"{reference_path} must be an object")
        token = reference.get("token")
        target_id = reference.get("target_id")
        start, end = reference.get("start_offset"), reference.get("end_offset")
        _expect(
            reference.get("target_type") == "Seal", f"{reference_path}.target_type must be Seal"
        )
        _expect(target_id in seal_ids, f"{reference_path}.target_id does not identify a page seal")
        _expect(
            isinstance(start, int) and isinstance(end, int),
            f"{reference_path} offsets must be integers",
        )
        _expect(0 <= start < end <= len(content), f"{reference_path} offsets are outside content")
        _expect(content[start:end] == token, f"{reference_path} offsets do not select {token!r}")
        _expect(target_id not in referenced_ids, f"seal {target_id} has duplicate references")
        referenced_ids.add(target_id)

    _expect(referenced_ids == seal_ids, f"{path} must reference every seal exactly once")
    return page_num


def validate(payload: Any) -> None:
    _expect(isinstance(payload, dict), "top-level JSON must be an object")
    _expect(
        all(key in payload for key in ("code", "message", "tips", "data")),
        "top-level fields are required",
    )
    raw_data = payload.get("data")
    _expect(isinstance(raw_data, dict), "data must be an object")
    _expect(
        "status" in raw_data and "doc_recognize_result" in raw_data,
        "data status and pages are required",
    )

    try:
        payload = ParseResponse.model_validate(payload).model_dump(mode="json")
    except PydanticValidationError as exc:
        raise ContractValidationError(f"output structure is invalid: {exc}") from exc

    _expect(isinstance(payload, dict), "top-level JSON must be an object")
    _expect(payload.get("code") == "success", "top-level code must be success")
    _expect(payload.get("message") == "", "top-level message must be empty on success")
    _expect(payload.get("tips") is None, "top-level tips must be null on success")
    data = payload.get("data")
    _expect(isinstance(data, dict), "data must be an object")
    _expect(data.get("status") == 4, "data.status must be 4 on success")
    pages = data.get("doc_recognize_result")
    _expect(isinstance(pages, list) and pages, "data.doc_recognize_result must be non-empty")
    page_numbers = [_validate_page(page, index) for index, page in enumerate(pages)]
    _expect(
        page_numbers == sorted(set(page_numbers)), "pages must be unique and sorted by page_num"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a normalized pdf-parser result JSON.")
    parser.add_argument("result", type=Path, help="Path to *_result.json")
    args = parser.parse_args()

    try:
        with args.result.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
        validate(payload)
    except (OSError, json.JSONDecodeError, ContractValidationError) as exc:
        parser.exit(1, f"validation failed: {exc}\n")

    print(f"validation passed: {args.result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

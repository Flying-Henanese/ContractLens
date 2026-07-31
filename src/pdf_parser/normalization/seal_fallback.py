from __future__ import annotations

import base64
import binascii
import re
from typing import Any, Protocol

from pdf_parser.clients.vlm import SealVLMResult
from pdf_parser.models import PageResult, SealDetail, SealText
from pdf_parser.normalization.seal import build_content

_SEAL_IMAGE_PATTERN = re.compile(
    r"(?:^|/)img_in_seal_box_(-?\d+)_(-?\d+)_(-?\d+)_(-?\d+)\.(?:jpg|jpeg|png)$",
    re.IGNORECASE,
)


class SealRecognizer(Protocol):
    async def transcribe_seal(self, image: bytes) -> SealVLMResult: ...


async def apply_seal_fallback(
    page: PageResult,
    raw_page: dict[str, Any],
    client: SealRecognizer,
    *,
    ocr_threshold: float,
) -> PageResult:
    crops = _seal_crops(raw_page.get("markdown"))
    changed = False
    details = list(page.document_details)

    for index, detail in enumerate(details):
        if not isinstance(detail, SealDetail):
            continue
        reason = _fallback_reason(detail, ocr_threshold)
        if reason is None:
            continue

        crop = crops.get(tuple(detail.seal_region_bbox))
        if crop is None:
            details[index] = _with_audit(
                detail,
                source="paddlex",
                status="missing_crop",
                reason=reason,
            )
            changed = True
            continue

        try:
            result = await client.transcribe_seal(crop)
        except Exception:
            details[index] = _with_audit(
                detail,
                source="paddlex",
                status="failed",
                reason=reason,
            )
            changed = True
            continue

        if result.status != "accepted" or result.text is None:
            details[index] = _with_audit(
                detail,
                source="paddlex",
                status=result.status,
                reason=reason,
            )
            changed = True
            continue

        details[index] = _with_vlm_text(detail, result.text, reason)
        changed = True

    if not changed:
        return page
    document_content, references = build_content(details)
    return page.model_copy(
        update={
            "document_details": details,
            "document_content": document_content,
            "content_references": references,
        }
    )


def _fallback_reason(detail: SealDetail, threshold: float) -> str | None:
    if not detail.texts:
        return "missing_ocr_text"
    scores = [item.ocr_confidence for item in detail.texts]
    if any(score is None for score in scores):
        return "missing_ocr_confidence"
    if any(score < threshold for score in scores if score is not None):
        return "low_ocr_confidence"
    return None


def _with_vlm_text(detail: SealDetail, text: str, reason: str) -> SealDetail:
    values = detail.model_dump()
    values.update(
        {
            "text": f"{detail.reference_token} {text}",
            "texts": [
                SealText(
                    text=text,
                    ocr_confidence=None,
                    position=[],
                    layout_bbox=[],
                )
            ],
            "recognition_source": "vlm",
            "fallback_status": "applied",
            "fallback_reason": reason,
            "paddlex_texts": [item.model_dump() for item in detail.texts],
        }
    )
    return SealDetail.model_validate(values)


def _with_audit(
    detail: SealDetail,
    *,
    source: str,
    status: str,
    reason: str,
) -> SealDetail:
    values = detail.model_dump()
    values.update(
        {
            "recognition_source": source,
            "fallback_status": status,
            "fallback_reason": reason,
        }
    )
    return SealDetail.model_validate(values)


def _seal_crops(markdown: Any) -> dict[tuple[int, int, int, int], bytes]:
    if not isinstance(markdown, dict):
        return {}
    images = markdown.get("images")
    if not isinstance(images, dict):
        return {}

    crops: dict[tuple[int, int, int, int], bytes] = {}
    for path, encoded in images.items():
        match = _SEAL_IMAGE_PATTERN.search(str(path).replace("\\", "/"))
        if match is None or not isinstance(encoded, str):
            continue
        payload = (
            encoded.split(",", 1)[1] if encoded.startswith("data:") and "," in encoded else encoded
        )
        try:
            image = base64.b64decode(payload, validate=True)
        except (ValueError, binascii.Error):
            continue
        if image:
            crops[tuple(int(value) for value in match.groups())] = image
    return crops

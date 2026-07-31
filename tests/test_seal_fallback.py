import base64
from io import BytesIO

import pytest
from PIL import Image

from pdf_parser.clients.vlm import SealVLMResult
from pdf_parser.errors import VLMError
from pdf_parser.models import PageResult, SealDetail, SealText
from pdf_parser.normalization.seal_fallback import apply_seal_fallback


def _png_base64() -> str:
    stream = BytesIO()
    Image.new("RGB", (8, 8), color=(200, 20, 20)).save(stream, format="PNG")
    return base64.b64encode(stream.getvalue()).decode("ascii")


def _page(*, score: float | None = 0.4, with_text: bool = True) -> PageResult:
    texts = (
        [SealText(text="Paddle文字", ocr_confidence=score, layout_bbox=[10, 20, 30, 40])]
        if with_text
        else []
    )
    seal = SealDetail(
        text="[印章1] Paddle文字" if with_text else "[印章1]",
        position=[],
        layout_order=0,
        layout_reading_index=0,
        layout_bbox=[10, 20, 30, 40],
        seal_id="page-1-seal-1",
        seal_index=1,
        reference_token="[印章1]",
        seal_region_bbox=[10, 20, 30, 40],
        texts=texts,
    )
    return PageResult(
        page_num=1,
        document_content=seal.text,
        image_width=100,
        image_height=100,
        document_details=[seal],
        content_references=[],
        parse_time=0,
    )


def _raw_page(encoded: str | None = None) -> dict:
    images = {}
    if encoded is not None:
        images["imgs/img_in_seal_box_10_20_30_40.png"] = encoded
    return {"markdown": {"images": images}}


class FakeRecognizer:
    def __init__(self, result: SealVLMResult | Exception):
        self.result = result
        self.calls = 0

    async def transcribe_seal(self, image: bytes) -> SealVLMResult:
        assert image.startswith(b"\x89PNG")
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.asyncio
async def test_low_confidence_seal_is_replaced_only_after_vlm_acceptance():
    client = FakeRecognizer(SealVLMResult(status="accepted", text="模型文字"))
    original = _page()

    result = await apply_seal_fallback(
        original,
        _raw_page(_png_base64()),
        client,
        ocr_threshold=0.9,
    )

    seal = result.document_details[0]
    assert isinstance(seal, SealDetail)
    assert client.calls == 1
    assert seal.text == "[印章1] 模型文字"
    assert seal.texts[0].text == "模型文字"
    assert seal.texts[0].ocr_confidence is None
    assert seal.seal_id == "page-1-seal-1"
    assert seal.seal_region_bbox == [10, 20, 30, 40]
    assert seal.recognition_source == "vlm"
    assert seal.fallback_status == "applied"
    assert seal.paddlex_texts[0]["text"] == "Paddle文字"
    assert result.document_content == "[印章1] 模型文字"
    assert result.content_references[0].target_id == "page-1-seal-1"


@pytest.mark.asyncio
async def test_high_confidence_seal_does_not_call_vlm_or_change_output():
    client = FakeRecognizer(SealVLMResult(status="accepted", text="不应使用"))
    original = _page(score=0.95)
    before = original.model_dump()

    result = await apply_seal_fallback(
        original,
        _raw_page(_png_base64()),
        client,
        ocr_threshold=0.9,
    )

    assert client.calls == 0
    assert result.model_dump() == before


@pytest.mark.asyncio
async def test_missing_ocr_text_triggers_vlm_for_detected_seal():
    client = FakeRecognizer(SealVLMResult(status="accepted", text="完整文字"))

    result = await apply_seal_fallback(
        _page(with_text=False),
        _raw_page(_png_base64()),
        client,
        ocr_threshold=0.9,
    )

    seal = result.document_details[0]
    assert client.calls == 1
    assert isinstance(seal, SealDetail)
    assert seal.fallback_reason == "missing_ocr_text"
    assert seal.texts[0].text == "完整文字"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("vlm_result", "expected_status"),
    [
        (SealVLMResult(status="mismatch"), "mismatch"),
        (SealVLMResult(status="unreadable"), "unreadable"),
        (VLMError("unavailable"), "failed"),
    ],
)
async def test_vlm_rejection_or_failure_preserves_paddlex(vlm_result, expected_status):
    client = FakeRecognizer(vlm_result)
    original = _page()

    result = await apply_seal_fallback(
        original,
        _raw_page(_png_base64()),
        client,
        ocr_threshold=0.9,
    )

    seal = result.document_details[0]
    assert isinstance(seal, SealDetail)
    assert seal.text == "[印章1] Paddle文字"
    assert seal.texts[0].text == "Paddle文字"
    assert seal.recognition_source == "paddlex"
    assert seal.fallback_status == expected_status


@pytest.mark.asyncio
async def test_missing_crop_preserves_paddlex_without_calling_vlm():
    client = FakeRecognizer(SealVLMResult(status="accepted", text="不应使用"))

    result = await apply_seal_fallback(
        _page(),
        _raw_page(),
        client,
        ocr_threshold=0.9,
    )

    seal = result.document_details[0]
    assert isinstance(seal, SealDetail)
    assert client.calls == 0
    assert seal.texts[0].text == "Paddle文字"
    assert seal.fallback_status == "missing_crop"


def test_audit_extras_do_not_change_declared_seal_json_schema():
    properties = SealDetail.model_json_schema()["properties"]
    assert "recognition_source" not in properties
    assert "fallback_status" not in properties
    assert "fallback_reason" not in properties
    assert "paddlex_texts" not in properties

import base64
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfWriter

from pdf_parser.clients.vlm import SealVLMResult
from pdf_parser.config import Settings
from pdf_parser.service import parse_pdf


def _make_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as stream:
        writer.write(stream)


def _crop() -> str:
    stream = BytesIO()
    Image.new("RGB", (8, 8), color=(200, 20, 20)).save(stream, format="PNG")
    return base64.b64encode(stream.getvalue()).decode("ascii")


class FakePageClient:
    async def parse_pdf_page(self, page_pdf: bytes, page_num: int) -> dict:
        return {
            "prunedResult": {
                "width": 100,
                "height": 100,
                "seal_res_list": [
                    {
                        "seal_ocr_res": {
                            "rec_texts": ["低分结果"],
                            "rec_scores": [0.3],
                            "rec_boxes": [[0, 0, 10, 10]],
                        }
                    }
                ],
            },
            "markdown": {
                "images": {
                    "imgs/img_in_seal_box_10_20_30_40.png": _crop(),
                }
            },
        }


class FakeVLMClient:
    def __init__(self):
        self.calls = 0

    async def transcribe_seal(self, image: bytes) -> SealVLMResult:
        self.calls += 1
        return SealVLMResult(status="accepted", text="兜底结果")


@pytest.mark.asyncio
async def test_service_applies_injected_vlm_only_when_enabled(tmp_path):
    source = tmp_path / "input.pdf"
    _make_pdf(source)
    vlm = FakeVLMClient()

    result = await parse_pdf(
        source,
        Settings(_env_file=None, vlm_enabled=True),
        client=FakePageClient(),
        vlm_client=vlm,
    )

    assert vlm.calls == 1
    assert result.data.doc_recognize_result[0].document_content == "[印章1] 兜底结果"


@pytest.mark.asyncio
async def test_service_keeps_existing_output_when_vlm_is_disabled(tmp_path):
    source = tmp_path / "input.pdf"
    _make_pdf(source)
    vlm = FakeVLMClient()

    result = await parse_pdf(
        source,
        Settings(_env_file=None, vlm_enabled=False),
        client=FakePageClient(),
        vlm_client=vlm,
    )

    assert vlm.calls == 0
    seal = result.data.doc_recognize_result[0].document_details[0]
    assert seal.texts[0].text == "低分结果"
    assert not hasattr(seal, "fallback_status")

from pathlib import Path

import pytest
from pypdf import PdfWriter

from pdf_parser.config import Settings
from pdf_parser.service import parse_pdf


class FakeClient:
    def __init__(self):
        self.pages = []

    async def parse_pdf_page(self, page_pdf: bytes, page_num: int) -> dict:
        assert page_pdf.startswith(b"%PDF")
        self.pages.append(page_num)
        return {
            "prunedResult": {
                "width": 595,
                "height": 842,
                "parsing_res_list": [
                    {
                        "block_label": "text",
                        "block_content": f"第 {page_num} 页",
                        "block_bbox": [10, 10, 100, 40],
                        "block_order": 0,
                    }
                ],
            }
        }


def make_pdf(path: Path, pages: int) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with path.open("wb") as stream:
        writer.write(stream)


@pytest.mark.asyncio
async def test_parse_pdf_preserves_all_pages_and_reports_progress(tmp_path):
    source = tmp_path / "input.pdf"
    make_pdf(source, 3)
    client = FakeClient()
    progress = []

    result = await parse_pdf(
        source,
        Settings(endpoint="http://unused", concurrency=2),
        progress=lambda done, total: progress.append((done, total)),
        client=client,
    )

    pages = result.data.doc_recognize_result
    assert [page.page_num for page in pages] == [1, 2, 3]
    assert [page.document_content for page in pages] == ["第 1 页", "第 2 页", "第 3 页"]
    assert client.pages == [1, 2, 3]
    assert progress == [(2, 3), (3, 3)]
    assert result.code == "success"

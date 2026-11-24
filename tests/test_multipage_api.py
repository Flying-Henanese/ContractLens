import asyncio
import base64
import json
from io import BytesIO

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from pdf_parser.api import app

PADDLEX_ENDPOINT = "http://paddlex.test"
WHOLE_ROUTE = "/api/v1/documents/parse-whole"
SPLIT_ROUTE = "/api/v1/documents/parse-split"


def make_pdf(page_count: int) -> bytes:
    writer = PdfWriter()
    for index in range(page_count):
        writer.add_blank_page(width=100 + index, height=200)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def paddlex_response(page_widths: list[int]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "errorCode": 0,
            "result": {
                "layoutParsingResults": [
                    {
                        "prunedResult": {
                            "width": width,
                            "height": 200,
                            "layout_det_res": {
                                "boxes": [{"label": "seal", "coordinate": [10, 10, 20, 20]}]
                            },
                        },
                    }
                    for width in page_widths
                ]
            },
        },
    )


@respx.mock
def test_parse_whole_sends_original_pdf_in_one_request(monkeypatch):
    monkeypatch.setenv("PDF_PARSER_ENDPOINT", PADDLEX_ENDPOINT)
    route = respx.post(f"{PADDLEX_ENDPOINT}/layout-parsing").mock(
        return_value=paddlex_response([100, 101, 102])
    )
    pdf = make_pdf(3)

    response = TestClient(app).post(
        WHOLE_ROUTE, files={"file": ("input.pdf", pdf, "application/pdf")}
    )

    assert response.status_code == 200
    assert route.call_count == 1
    body = json.loads(route.calls[0].request.content)
    assert body["fileType"] == 0
    assert base64.b64decode(body["file"]) == pdf
    pages = response.json()["data"]["doc_recognize_result"]
    assert [page["page_num"] for page in pages] == [1, 2, 3]
    assert [page["image_width"] for page in pages] == [100, 101, 102]


@respx.mock
def test_parse_whole_reports_upstream_error_without_copying_response_text(monkeypatch):
    monkeypatch.setenv("PDF_PARSER_ENDPOINT", PADDLEX_ENDPOINT)
    respx.post(f"{PADDLEX_ENDPOINT}/layout-parsing").mock(
        return_value=httpx.Response(400, json={"errorCode": 37, "errorMsg": "PDF contents"})
    )

    response = TestClient(app).post(
        WHOLE_ROUTE, files={"file": ("input.pdf", make_pdf(3), "application/pdf")}
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "第 1–3 页解析失败：HTTP 400，PaddleX errorCode=37"}


@pytest.mark.parametrize(
    ("page_count", "expected_parts"),
    [
        (10, [[100, 101, 102], [103, 104, 105], [106, 107], [108, 109]]),
        (2, [[100], [101]]),
    ],
)
@respx.mock
def test_parse_split_sends_balanced_parts_concurrently_and_preserves_page_order(
    monkeypatch, page_count, expected_parts
):
    monkeypatch.setenv("PDF_PARSER_ENDPOINT", PADDLEX_ENDPOINT)
    monkeypatch.setenv("PDF_PARSER_CONCURRENCY", "1")
    all_started = asyncio.Event()
    last_completed = asyncio.Event()
    submitted = []
    completed = []

    async def receive_part(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["fileType"] == 0
        pdf = PdfReader(BytesIO(base64.b64decode(body["file"])))
        widths = [int(page.mediabox.width) for page in pdf.pages]
        submitted.append(widths)
        if len(submitted) == len(expected_parts):
            all_started.set()
        await asyncio.wait_for(all_started.wait(), timeout=2)
        if widths == expected_parts[0]:
            await asyncio.wait_for(last_completed.wait(), timeout=2)
        completed.append(widths)
        if widths == expected_parts[-1]:
            last_completed.set()
        return paddlex_response(widths)

    respx.post(f"{PADDLEX_ENDPOINT}/layout-parsing").mock(side_effect=receive_part)
    response = TestClient(app).post(
        SPLIT_ROUTE, files={"file": ("input.pdf", make_pdf(page_count), "application/pdf")}
    )

    assert response.status_code == 200
    assert sorted(submitted) == expected_parts
    assert completed.index(expected_parts[-1]) < completed.index(expected_parts[0])
    pages = response.json()["data"]["doc_recognize_result"]
    assert [page["page_num"] for page in pages] == list(range(1, page_count + 1))
    assert [page["image_width"] for page in pages] == list(range(100, 100 + page_count))
    assert [page["content_references"][0]["target_id"] for page in pages] == [
        f"page-{page_num}-seal-1" for page_num in range(1, page_count + 1)
    ]


@pytest.mark.parametrize("endpoint", [WHOLE_ROUTE, SPLIT_ROUTE])
@respx.mock
def test_new_endpoints_still_accept_images(monkeypatch, endpoint):
    monkeypatch.setenv("PDF_PARSER_ENDPOINT", PADDLEX_ENDPOINT)
    route = respx.post(f"{PADDLEX_ENDPOINT}/layout-parsing").mock(
        return_value=paddlex_response([100])
    )
    image = b"\x89PNG\r\n\x1a\nfixture"

    response = TestClient(app).post(endpoint, files={"file": ("page.png", image, "image/png")})

    assert response.status_code == 200
    assert route.call_count == 1
    body = json.loads(route.calls[0].request.content)
    assert body["fileType"] == 1
    assert base64.b64decode(body["file"]) == image
    assert response.json()["data"]["doc_recognize_result"][0]["page_num"] == 1


@respx.mock
def test_split_returns_failure_and_cancels_pending_parts_when_a_page_is_missing(monkeypatch):
    monkeypatch.setenv("PDF_PARSER_ENDPOINT", PADDLEX_ENDPOINT)
    rest_started = asyncio.Event()
    sibling_requests = 0
    cancelled = 0

    async def receive_part(request: httpx.Request) -> httpx.Response:
        nonlocal sibling_requests, cancelled
        body = json.loads(request.content)
        if body["logId"] == "pdf-parser-pages-1-2":
            await asyncio.wait_for(rest_started.wait(), timeout=2)
            return paddlex_response([100])

        sibling_requests += 1
        if sibling_requests == 3:
            rest_started.set()
        try:
            await asyncio.wait_for(asyncio.Event().wait(), timeout=2)
        except asyncio.CancelledError:
            cancelled += 1
            raise
        raise AssertionError("expected sibling request to be cancelled")

    respx.post(f"{PADDLEX_ENDPOINT}/layout-parsing").mock(side_effect=receive_part)
    response = TestClient(app).post(
        SPLIT_ROUTE, files={"file": ("input.pdf", make_pdf(5), "application/pdf")}
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "第 1–2 页响应页数异常：期望 2 页，实际 1 页"}
    assert cancelled == 3

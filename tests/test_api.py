import inspect
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from pdf_parser.api import (
    DOCUMENT_TIMEOUT_SECONDS,
    RECEIPT_TIMEOUT_SECONDS,
    app,
)
from pdf_parser.errors import PaddleXError
from pdf_parser.models import ParseResponse, ResultData

client = TestClient(app)


def test_document_route_is_sync_and_uses_300_second_timeout(monkeypatch):
    observed: dict[str, object] = {}

    async def fake_parse_pdf(path: Path, settings):
        observed["path"] = path
        observed["content"] = path.read_bytes()
        observed["timeout"] = settings.timeout_seconds
        return ParseResponse(data=ResultData(doc_recognize_result=[]))

    monkeypatch.setattr("pdf_parser.api.parse_pdf", fake_parse_pdf)

    response = client.post(
        "/api/v1/documents/parse",
        files={"file": ("sample.pdf", b"%PDF-test", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["code"] == "success"
    assert observed["content"] == b"%PDF-test"
    assert observed["timeout"] == DOCUMENT_TIMEOUT_SECONDS == 300
    assert not Path(observed["path"]).exists()
    assert not inspect.iscoroutinefunction(_route("/api/v1/documents/parse").endpoint)


def test_document_route_accepts_supported_image(monkeypatch):
    observed = {}

    async def fake_parse_image(path: Path, settings):
        observed["content"] = path.read_bytes()
        observed["timeout"] = settings.timeout_seconds
        return ParseResponse(data=ResultData(doc_recognize_result=[]))

    monkeypatch.setattr("pdf_parser.api.parse_image", fake_parse_image)
    image = b"\x89PNG\r\n\x1a\nvalid-image"
    response = client.post(
        "/api/v1/documents/parse",
        files={"file": ("sample.png", image, "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["code"] == "success"
    assert observed["content"] == image
    assert observed["timeout"] == DOCUMENT_TIMEOUT_SECONDS


def test_document_route_rejects_invalid_image_upload():
    response = client.post(
        "/api/v1/documents/parse",
        files={"file": ("sample.png", b"image", "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "上传文件不是有效的受支持图像"


def test_document_route_rejects_empty_file():
    response = client.post(
        "/api/v1/documents/parse",
        files={"file": ("sample.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "上传文件不能为空"


def test_document_route_maps_paddlex_failure_to_bad_gateway(monkeypatch):
    async def fail_parse_pdf(*_args, **_kwargs):
        raise PaddleXError("远端解析失败")

    monkeypatch.setattr("pdf_parser.api.parse_pdf", fail_parse_pdf)

    response = client.post(
        "/api/v1/documents/parse",
        files={"file": ("sample.pdf", b"%PDF-test", "application/pdf")},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "远端解析失败"


def test_receipt_route_is_sync_accepts_pdf_or_image_and_reports_placeholder():
    for filename, content_type in (
        ("receipt.pdf", "application/pdf"),
        ("receipt.jpg", "image/jpeg"),
        ("receipt.png", "image/png"),
    ):
        response = client.post(
            "/api/v1/receipts/recognize",
            files={"file": (filename, b"test", content_type)},
        )

        assert response.status_code == 501
        assert str(int(RECEIPT_TIMEOUT_SECONDS)) in response.json()["detail"]

    assert RECEIPT_TIMEOUT_SECONDS == 120
    assert not inspect.iscoroutinefunction(_route("/api/v1/receipts/recognize").endpoint)


def test_receipt_route_rejects_unsupported_file_type():
    response = client.post(
        "/api/v1/receipts/recognize",
        files={"file": ("receipt.txt", b"text", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == "仅支持上传PDF 或图像票据"


def _route(path: str) -> APIRoute:
    return next(route for route in app.routes if isinstance(route, APIRoute) and route.path == path)

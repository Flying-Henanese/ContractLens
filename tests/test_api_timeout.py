from fastapi.testclient import TestClient

from pdf_parser.api import app


def test_document_route_maps_processing_timeout_to_gateway_timeout(monkeypatch):
    async def timeout_parse_pdf(*_args, **_kwargs):
        raise TimeoutError

    monkeypatch.setattr("pdf_parser.api.parse_pdf", timeout_parse_pdf)

    response = TestClient(app).post(
        "/api/v1/documents/parse",
        files={"file": ("sample.pdf", b"%PDF-test", "application/pdf")},
    )

    assert response.status_code == 504
    assert response.json()["detail"] == "文档处理超过 300 秒"

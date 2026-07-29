import base64
import json

import httpx
import pytest
import respx

from pdf_parser.clients.paddlex import PaddleXClient
from pdf_parser.config import Settings
from pdf_parser.errors import PaddleXError


@pytest.mark.asyncio
@respx.mock
async def test_client_sends_a_single_pdf_page():
    route = respx.post("http://paddlex.test/layout-parsing").mock(
        return_value=httpx.Response(
            200,
            json={
                "errorCode": 0,
                "errorMsg": "Success",
                "result": {"layoutParsingResults": [{"prunedResult": {}}]},
            },
        )
    )
    settings = Settings(endpoint="http://paddlex.test", retries=0)

    async with PaddleXClient(settings) as client:
        result = await client.parse_pdf_page(b"%PDF-test", page_num=7)

    request_body = json.loads(route.calls[0].request.content)
    assert base64.b64decode(request_body["file"]) == b"%PDF-test"
    assert request_body["fileType"] == 0
    assert request_body["useLayoutDetection"] is True
    assert request_body["layoutThreshold"] == 0.5
    assert request_body["visualize"] is False
    assert request_body["logId"] == "pdf-parser-page-7"
    assert result == {"prunedResult": {}}


@pytest.mark.asyncio
@respx.mock
async def test_client_reports_pipeline_error():
    respx.post("http://paddlex.test/layout-parsing").mock(
        return_value=httpx.Response(500, json={"errorCode": 500, "errorMsg": "bad model"})
    )
    settings = Settings(endpoint="http://paddlex.test", retries=0)

    async with PaddleXClient(settings) as client:
        with pytest.raises(PaddleXError, match="第 3 页解析失败：bad model"):
            await client.parse_pdf_page(b"%PDF-test", page_num=3)


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    ("response", "expected_message"),
    [
        (
            httpx.Response(200, text="not-json"),
            "第 4 页：PaddleX 返回的不是 JSON",
        ),
        (
            httpx.Response(200, json=[]),
            "第 4 页：PaddleX 返回的 JSON 顶层不是对象",
        ),
    ],
)
async def test_client_response_shape_errors_include_page_context(
    response: httpx.Response,
    expected_message: str,
):
    respx.post("http://paddlex.test/layout-parsing").mock(return_value=response)
    settings = Settings(endpoint="http://paddlex.test", retries=0)

    async with PaddleXClient(settings) as client:
        with pytest.raises(PaddleXError, match=expected_message):
            await client.parse_pdf_page(b"%PDF-test", page_num=4)

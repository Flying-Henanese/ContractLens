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

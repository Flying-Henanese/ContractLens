import base64
import json

import httpx
import pytest
import respx

from pdf_parser.clients.paddlex import PaddleXClient
from pdf_parser.config import Settings
from pdf_parser.ingestion.image import detect_image_format


def test_detect_image_format_accepts_supported_signatures_and_rejects_other_data():
    assert detect_image_format(b"BMrest") == "bmp"
    assert detect_image_format(b"\xff\xd8\xffrest") == "jpeg"
    assert detect_image_format(b"\x89PNG\r\n\x1a\nrest") == "png"
    assert detect_image_format(b"II*\x00rest") == "tiff"
    assert detect_image_format(b"RIFFabcdWEBPrest") == "webp"
    assert detect_image_format(b"not an image") is None


@pytest.mark.asyncio
@respx.mock
async def test_client_sends_image_with_image_file_type():
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

    async with PaddleXClient(Settings(endpoint="http://paddlex.test", retries=0)) as client:
        result = await client.parse_image(b"\x89PNG\r\n\x1a\nimage")

    request_body = json.loads(route.calls[0].request.content)
    assert base64.b64decode(request_body["file"]) == b"\x89PNG\r\n\x1a\nimage"
    assert request_body["fileType"] == 1
    assert result == {"prunedResult": {}}

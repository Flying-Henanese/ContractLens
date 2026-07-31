import json
from io import BytesIO

import httpx
import pytest
import respx
from PIL import Image

from pdf_parser.clients.vlm import VLMClient
from pdf_parser.config import Settings
from pdf_parser.errors import VLMError


def _png() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (8, 8), color=(220, 20, 20)).save(stream, format="PNG")
    return stream.getvalue()


def _response(status: str, text: str | None) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(
                            {"status": status, "text": text},
                            ensure_ascii=False,
                        )
                    },
                }
            ]
        },
    )


@pytest.mark.asyncio
@respx.mock
async def test_vlm_accepts_only_matching_original_and_red_views():
    route = respx.post("http://vlm.test/v1/chat/completions").mock(
        side_effect=[
            _response("readable", "测试 印章"),
            _response("readable", "测试印章"),
        ]
    )
    settings = Settings(
        _env_file=None,
        vlm_endpoint="http://vlm.test",
        vlm_model="seal-model",
        vlm_max_attempts=1,
    )

    async with VLMClient(settings) as client:
        result = await client.transcribe_seal(_png())

    assert result.status == "accepted"
    assert result.text == "测试印章"
    assert route.call_count == 2
    for call in route.calls:
        payload = json.loads(call.request.content)
        assert payload["model"] == "seal-model"
        assert payload["temperature"] == 0
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["messages"][0]["content"][1]["image_url"]["url"].startswith(
            "data:image/png;base64,"
        )


@pytest.mark.asyncio
@respx.mock
async def test_vlm_rejects_disagreement_between_views():
    respx.post("http://vlm.test/v1/chat/completions").mock(
        side_effect=[
            _response("readable", "甲公司"),
            _response("readable", "乙公司"),
        ]
    )
    settings = Settings(
        _env_file=None,
        vlm_endpoint="http://vlm.test",
        vlm_max_attempts=1,
    )

    async with VLMClient(settings) as client:
        result = await client.transcribe_seal(_png())

    assert result.status == "mismatch"
    assert result.text is None


@pytest.mark.asyncio
@respx.mock
async def test_vlm_rejects_partial_or_unreadable_content():
    respx.post("http://vlm.test/v1/chat/completions").mock(
        side_effect=[
            _response("unreadable", None),
            _response("readable", "可见部分"),
        ]
    )
    settings = Settings(
        _env_file=None,
        vlm_endpoint="http://vlm.test",
        vlm_max_attempts=1,
    )

    async with VLMClient(settings) as client:
        result = await client.transcribe_seal(_png())

    assert result.status == "unreadable"
    assert result.text is None


@pytest.mark.asyncio
@respx.mock
async def test_vlm_error_does_not_include_remote_body():
    respx.post("http://vlm.test/v1/chat/completions").mock(
        return_value=httpx.Response(400, text="sensitive downstream stack")
    )
    settings = Settings(
        _env_file=None,
        vlm_endpoint="http://vlm.test",
        vlm_max_attempts=1,
    )

    async with VLMClient(settings) as client:
        with pytest.raises(VLMError) as caught:
            await client.transcribe_seal(_png())

    assert "HTTP 400" in str(caught.value)
    assert "sensitive" not in str(caught.value)


@pytest.mark.asyncio
@respx.mock
async def test_vlm_retries_transient_statuses(monkeypatch):
    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("pdf_parser.clients.vlm.asyncio.sleep", no_sleep)
    route = respx.post("http://vlm.test/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(500),
            _response("readable", "一致"),
            httpx.Response(500),
            _response("readable", "一致"),
        ]
    )
    settings = Settings(
        _env_file=None,
        vlm_endpoint="http://vlm.test",
        vlm_max_attempts=2,
    )

    async with VLMClient(settings) as client:
        result = await client.transcribe_seal(_png())

    assert result.status == "accepted"
    assert route.call_count == 4

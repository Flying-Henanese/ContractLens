from __future__ import annotations

import asyncio
import base64
import json
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

import httpx
from PIL import Image, UnidentifiedImageError

from pdf_parser.config import Settings
from pdf_parser.errors import VLMError

_SEAL_PROMPT = """你是印章文字的严格转写器。输入只包含一个已检测到的印章区域。
只转写印章本身直接可见的文字，忽略正文、表格文字、五角星、边框、圆环和图案。
禁止依据常识、上下文或常见公司名称补全、猜测、纠错或扩写。
只有当印章全部文字都能明确辨认时，返回 status="readable" 和完整原文。
只要任意字符模糊、残缺、被遮挡或无法确认，必须返回 status="unreadable" 且 text=null。
不要返回部分结果。严格遵循给定 JSON Schema。"""

_MAX_SEAL_PIXELS = 16_000_000
_MAX_TRANSCRIPTION_CHARS = 256

_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "seal_transcription",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["readable", "unreadable"]},
                "text": {"type": ["string", "null"]},
            },
            "required": ["status", "text"],
            "additionalProperties": False,
        },
    },
}


@dataclass(frozen=True)
class SealVLMResult:
    status: Literal["accepted", "unreadable", "mismatch"]
    text: str | None = None


@dataclass(frozen=True)
class _ViewResult:
    status: Literal["readable", "unreadable"]
    text: str | None


class _RetryableVLMError(RuntimeError):
    pass


class VLMClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=settings.vlm_timeout_seconds,
            trust_env=settings.trust_env,
        )
        self._semaphore = asyncio.Semaphore(settings.vlm_concurrency)

    async def __aenter__(self) -> VLMClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def transcribe_seal(self, image: bytes) -> SealVLMResult:
        original, red_isolated = _prepare_seal_views(image)
        tasks = [
            asyncio.create_task(self._transcribe_view(original)),
            asyncio.create_task(self._transcribe_view(red_isolated)),
        ]
        try:
            first, second = await asyncio.gather(*tasks)
        except BaseException as exc:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if isinstance(exc, (VLMError, asyncio.CancelledError)):
                raise
            raise VLMError("VLM seal transcription failed") from exc

        if first.status == "unreadable" or second.status == "unreadable":
            return SealVLMResult(status="unreadable")

        first_text = _normalize_text(first.text)
        second_text = _normalize_text(second.text)
        if not first_text or not second_text:
            return SealVLMResult(status="unreadable")
        if first_text != second_text:
            return SealVLMResult(status="mismatch")
        return SealVLMResult(status="accepted", text=first_text)

    async def _transcribe_view(self, image: bytes) -> _ViewResult:
        payload = {
            "model": self.settings.vlm_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _SEAL_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    "data:image/png;base64,"
                                    + base64.b64encode(image).decode("ascii")
                                )
                            },
                        },
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": 512,
            "response_format": _RESPONSE_FORMAT,
        }

        last_error: Exception | None = None
        for attempt in range(1, self.settings.vlm_max_attempts + 1):
            try:
                async with self._semaphore:
                    response = await self._client.post(self.settings.vlm_chat_url, json=payload)
                if response.status_code == 429 or response.status_code >= 500:
                    raise _RetryableVLMError(f"transient HTTP {response.status_code}")
                if response.status_code != 200:
                    raise VLMError(f"VLM request rejected with HTTP {response.status_code}")
                return _decode_view_response(response)
            except (httpx.TransportError, httpx.TimeoutException, _RetryableVLMError) as exc:
                last_error = exc
                if attempt == self.settings.vlm_max_attempts:
                    break
                await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 4.0))

        raise VLMError(
            f"VLM request failed after {self.settings.vlm_max_attempts} attempts"
        ) from last_error


def _prepare_seal_views(image: bytes) -> tuple[bytes, bytes]:
    try:
        with Image.open(BytesIO(image)) as source:
            if source.width * source.height > _MAX_SEAL_PIXELS:
                raise VLMError("Seal crop exceeds the pixel limit")
            rgb = source.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise VLMError("Invalid seal crop image") from exc

    original_stream = BytesIO()
    rgb.save(original_stream, format="PNG")

    red_view = Image.new("RGB", rgb.size, color=(255, 255, 255))
    source_pixels = rgb.load()
    target_pixels = red_view.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            red, green, blue = source_pixels[x, y]
            if red >= 100 and red >= 1.35 * green and red >= 1.35 * blue:
                target_pixels[x, y] = (red, green, blue)
    red_stream = BytesIO()
    red_view.save(red_stream, format="PNG")
    return original_stream.getvalue(), red_stream.getvalue()


def _decode_view_response(response: httpx.Response) -> _ViewResult:
    try:
        body = response.json()
        choice = body["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("response was not completed")
        content = choice["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("message content is not a string")
        value = json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise VLMError("VLM returned an invalid structured response") from exc

    if not isinstance(value, dict) or set(value) != {"status", "text"}:
        raise VLMError("VLM response does not match the seal schema")
    status = value["status"]
    text = value["text"]
    if status == "unreadable" and text is None:
        return _ViewResult(status="unreadable", text=None)
    normalized = _normalize_text(text) if isinstance(text, str) else ""
    if status == "readable" and normalized and len(normalized) <= _MAX_TRANSCRIPTION_CHARS:
        return _ViewResult(status="readable", text=text)
    raise VLMError("VLM response violates seal transcription rules")


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(normalized.split())

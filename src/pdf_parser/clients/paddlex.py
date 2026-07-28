from __future__ import annotations

import base64
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from pdf_parser.config import Settings
from pdf_parser.errors import PaddleXError


class PaddleXClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=settings.timeout_seconds, trust_env=settings.trust_env
        )

    async def __aenter__(self) -> PaddleXClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        try:
            response = await self._client.get(self.settings.health_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PaddleXError(f"PaddleX 健康检查失败：{exc}") from exc
        return self._decode_response(response, context="PaddleX 健康检查")

    async def parse_pdf_page(self, page_pdf: bytes, page_num: int) -> dict[str, Any]:
        payload = {
            "file": base64.b64encode(page_pdf).decode("ascii"),
            "fileType": 0,
            "visualize": False,
            "logId": f"pdf-parser-page-{page_num}",
        }

        retryer = AsyncRetrying(
            stop=stop_after_attempt(self.settings.retries + 1),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
            reraise=True,
        )
        try:
            async for attempt in retryer:
                with attempt:
                    response = await self._client.post(self.settings.inference_url, json=payload)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise PaddleXError(f"第 {page_num} 页请求 PaddleX 失败：{exc}") from exc

        context = f"第 {page_num} 页"
        body = self._decode_response(response, context=context)
        if response.status_code != 200 or body.get("errorCode") != 0:
            message = body.get("errorMsg") or f"HTTP {response.status_code}"
            raise PaddleXError(f"{context}解析失败：{message}")

        results = (body.get("result") or {}).get("layoutParsingResults") or []
        if len(results) != 1:
            raise PaddleXError(f"{context}响应页数异常：期望 1 页，实际 {len(results)} 页")
        return results[0]

    @staticmethod
    def _decode_response(response: httpx.Response, *, context: str) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise PaddleXError(
                f"{context}：PaddleX 返回的不是 JSON（HTTP {response.status_code}）"
            ) from exc
        if not isinstance(body, dict):
            raise PaddleXError(f"{context}：PaddleX 返回的 JSON 顶层不是对象")
        return body

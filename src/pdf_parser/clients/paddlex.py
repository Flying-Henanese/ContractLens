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
        pages = await self._parse_pdf_pages(
            page_pdf, first_page=page_num, page_count=1, include_error_message=True
        )
        return pages[0]

    async def parse_pdf_pages(
        self, pdf: bytes, *, first_page: int, page_count: int
    ) -> list[dict[str, Any]]:
        return await self._parse_pdf_pages(
            pdf, first_page=first_page, page_count=page_count, include_error_message=False
        )

    async def _parse_pdf_pages(
        self, pdf: bytes, *, first_page: int, page_count: int, include_error_message: bool
    ) -> list[dict[str, Any]]:
        if page_count == 1:
            context = f"第 {first_page} 页"
            log_id = f"pdf-parser-page-{first_page}"
        else:
            last_page = first_page + page_count - 1
            context = f"第 {first_page}–{last_page} 页"
            log_id = f"pdf-parser-pages-{first_page}-{last_page}"
        payload = {
            "file": base64.b64encode(pdf).decode("ascii"),
            "fileType": 0,
            "useLayoutDetection": self.settings.use_layout_detection,
            "layoutThreshold": self.settings.layout_threshold,
            "visualize": False,
            "logId": log_id,
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
            raise PaddleXError(f"{context}请求 PaddleX 失败：{exc}") from exc

        body = self._decode_response(response, context=context)
        error_code = body.get("errorCode")
        if response.status_code != 200 or error_code != 0:
            message = f"HTTP {response.status_code}"
            if include_error_message:
                message = body.get("errorMsg") or message
            elif isinstance(error_code, int):
                message = f"{message}，PaddleX errorCode={error_code}"
            raise PaddleXError(f"{context}解析失败：{message}")

        result = body.get("result") or {}
        if not isinstance(result, dict):
            raise PaddleXError(f"{context}：PaddleX 的 result 不是对象")
        pages = result.get("layoutParsingResults") or []
        if not isinstance(pages, list) or any(not isinstance(page, dict) for page in pages):
            raise PaddleXError(f"{context}：PaddleX 的 layoutParsingResults 不是页面对象列表")
        if len(pages) != page_count:
            raise PaddleXError(f"{context}响应页数异常：期望 {page_count} 页，实际 {len(pages)} 页")
        return pages

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

    async def parse_image(self, image: bytes) -> dict[str, Any]:
        """Parse one image through the PaddleX layout-parsing service."""
        payload = {
            "file": base64.b64encode(image).decode("ascii"),
            "fileType": 1,
            "useLayoutDetection": self.settings.use_layout_detection,
            "layoutThreshold": self.settings.layout_threshold,
            "visualize": False,
            "logId": "pdf-parser-image",
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
            raise PaddleXError(f"Image request to PaddleX failed: {exc}") from exc

        context = "image"
        body = self._decode_response(response, context=context)
        if response.status_code != 200 or body.get("errorCode") != 0:
            message = body.get("errorMsg") or f"HTTP {response.status_code}"
            raise PaddleXError(f"Image parsing failed: {message}")

        results = (body.get("result") or {}).get("layoutParsingResults") or []
        if len(results) != 1:
            raise PaddleXError(
                f"Image response count mismatch: expected 1, received {len(results)}"
            )
        return results[0]

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile, status

from pdf_parser.config import Settings
from pdf_parser.errors import InvalidImageError, InvalidPdfError, PaddleXError
from pdf_parser.ingestion.image import detect_image_format
from pdf_parser.models import ParseResponse
from pdf_parser.service import parse_image, parse_pdf

DOCUMENT_TIMEOUT_SECONDS = 300.0
RECEIPT_TIMEOUT_SECONDS = 120.0

_DOCUMENT_PDF_SUFFIXES = {".pdf"}
_DOCUMENT_PDF_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}
_IMAGE_CONTENT_TYPES_BY_SUFFIX = {
    ".bmp": "image/bmp",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}
_RECEIPT_SUFFIXES = _DOCUMENT_PDF_SUFFIXES | set(_IMAGE_CONTENT_TYPES_BY_SUFFIX)
_RECEIPT_CONTENT_TYPES = _DOCUMENT_PDF_CONTENT_TYPES | set(_IMAGE_CONTENT_TYPES_BY_SUFFIX.values())

app = FastAPI(
    title="PDF Parser API",
    version="0.1.0",
    description="基于远端 PaddleX Pipeline 的同步文档与票据识别接口。",
)
app.state.document_timeout_seconds = DOCUMENT_TIMEOUT_SECONDS
app.state.receipt_timeout_seconds = RECEIPT_TIMEOUT_SECONDS


@app.post(
    "/api/v1/documents/parse",
    response_model=ParseResponse,
    summary="同步解析 PDF 或图像文档",
)
def parse_document(
    file: Annotated[UploadFile, File(description="需要解析的 PDF 或图像文件")],
) -> ParseResponse:
    """同步等待文档解析完成，最长等待 300 秒。"""
    input_kind = _validate_document_upload(file)

    with TemporaryDirectory(prefix="pdf-parser-document-") as temp_dir:
        suffix = Path(file.filename or "").suffix.lower()
        input_path = Path(temp_dir) / f"input{suffix}"
        with input_path.open("wb") as target:
            shutil.copyfileobj(file.file, target)
        if input_path.stat().st_size == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件不能为空")
        if input_kind == "image" and detect_image_format(input_path.read_bytes()) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="上传文件不是有效的受支持图像",
            )

        settings = Settings(timeout_seconds=DOCUMENT_TIMEOUT_SECONDS)
        parser = (
            parse_pdf(input_path, settings=settings)
            if input_kind == "pdf"
            else parse_image(input_path, settings=settings)
        )
        try:
            return asyncio.run(asyncio.wait_for(parser, timeout=DOCUMENT_TIMEOUT_SECONDS))
        except TimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"文档处理超过 {int(DOCUMENT_TIMEOUT_SECONDS)} 秒",
            ) from exc
        except (InvalidPdfError, InvalidImageError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except (PaddleXError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="文档临时文件处理失败",
            ) from exc


@app.post(
    "/api/v1/receipts/recognize",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="同步识别票据",
)
def recognize_receipt(
    file: Annotated[UploadFile, File(description="需要识别的票据 PDF 或图像")],
) -> None:
    """预留票据识别入口，后续实现将使用 120 秒超时。"""
    _validate_upload(
        file,
        allowed_suffixes=_RECEIPT_SUFFIXES,
        allowed_content_types=_RECEIPT_CONTENT_TYPES,
        expected="PDF 或图像票据",
    )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "票据识别接口已预留，识别逻辑尚未实现"
            f"（处理超时配置为 {int(RECEIPT_TIMEOUT_SECONDS)} 秒）"
        ),
    )


def _validate_document_upload(file: UploadFile) -> Literal["pdf", "image"]:
    suffix = Path(file.filename or "").suffix.lower()
    content_type = (file.content_type or "").lower()
    if suffix in _DOCUMENT_PDF_SUFFIXES and content_type in _DOCUMENT_PDF_CONTENT_TYPES:
        return "pdf"
    if _IMAGE_CONTENT_TYPES_BY_SUFFIX.get(suffix) == content_type:
        return "image"
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="仅支持上传 PDF 或 BMP/JPEG/PNG/TIFF/WEBP 图像文件",
    )


def _validate_upload(
    file: UploadFile,
    *,
    allowed_suffixes: set[str],
    allowed_content_types: set[str],
    expected: str,
) -> None:
    suffix = Path(file.filename or "").suffix.lower()
    content_type = (file.content_type or "").lower()
    if suffix not in allowed_suffixes or content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"仅支持上传{expected}",
        )

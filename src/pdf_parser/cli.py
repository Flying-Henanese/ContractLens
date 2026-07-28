from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import httpx
import orjson
import typer

from pdf_parser.clients.paddlex import PaddleXClient
from pdf_parser.config import Settings
from pdf_parser.errors import PdfParserError
from pdf_parser.service import parse_pdf

_DEFAULT_SETTINGS = Settings()

app = typer.Typer(
    name="pdf-parser",
    help="使用远端 PaddleX Layout Parsing 服务解析 PDF。",
    no_args_is_help=True,
)


@app.command("parse")
def parse_command(
    input_pdf: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=True, dir_okay=False, readable=True),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="输出 JSON，默认写入 output/。"),
    ] = None,
    endpoint: Annotated[str, typer.Option(help="PaddleX 服务地址。")] = _DEFAULT_SETTINGS.endpoint,
    timeout: Annotated[
        float, typer.Option(help="单页请求超时秒数。", min=1)
    ] = _DEFAULT_SETTINGS.timeout_seconds,
    retries: Annotated[
        int, typer.Option(help="网络失败重试次数。", min=0, max=10)
    ] = _DEFAULT_SETTINGS.retries,
    concurrency: Annotated[
        int, typer.Option(help="并行处理页数。服务资源有限时建议保持 1。", min=1, max=16)
    ] = _DEFAULT_SETTINGS.concurrency,
) -> None:
    """解析一个 PDF 并输出兼容 JSON。"""
    if input_pdf.suffix.lower() != ".pdf":
        typer.echo("错误：输入文件必须是 PDF。", err=True)
        raise typer.Exit(2)

    output = output or Path("output") / f"{input_pdf.stem}_result.json"
    settings = Settings(
        endpoint=endpoint,
        timeout_seconds=timeout,
        retries=retries,
        concurrency=concurrency,
    )

    def show_progress(done: int, total: int) -> None:
        typer.echo(f"已完成 {done}/{total} 页")

    try:
        result = asyncio.run(parse_pdf(input_pdf, settings, progress=show_progress))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(
            orjson.dumps(
                result.model_dump(),
                option=orjson.OPT_INDENT_2,
            )
        )
    except (PdfParserError, OSError, httpx.HTTPError) as exc:
        typer.echo(f"解析失败：{exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"结果已写入：{output.resolve()}")


@app.command("health")
def health_command(
    endpoint: Annotated[str, typer.Option(help="PaddleX 服务地址。")] = _DEFAULT_SETTINGS.endpoint,
) -> None:
    """检查 PaddleX 服务是否健康。"""

    async def check() -> dict:
        settings = Settings(endpoint=endpoint)
        async with PaddleXClient(settings) as client:
            return await client.health()

    try:
        result = asyncio.run(check())
    except (PdfParserError, httpx.HTTPError) as exc:
        typer.echo(f"服务不可用：{exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())

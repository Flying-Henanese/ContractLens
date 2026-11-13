"""Single-page, bounded, no-retry CUDA experiment; output stays in output/smoke."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import importlib.util
import io
import json
import math
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader, PdfWriter

from pdf_parser.models import ParseResponse, ResultData
from pdf_parser.normalization.paddlex import normalize_page

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "contract_validator", ROOT / ".harness/scripts/validate_result.py"
)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def percentile(values: list[float], quantile: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)] if values else 0


async def run(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run):
        raise ValueError("run must be a simple directory name")
    out = ROOT / "output/smoke" / args.run
    out.mkdir(parents=True, exist_ok=False)
    source = Path(args.pdf)
    reader = PdfReader(source)
    pages = (
        list(range(1, len(reader.pages) + 1))
        if args.pages == "all"
        else [int(p) for p in args.pages.split(",")]
    )
    if len(pages) != len(set(pages)) or not all(1 <= p <= len(reader.pages) for p in pages):
        raise ValueError("Invalid or duplicate page list")
    inputs: dict[int, str] = {}
    pdf_dir = ROOT / "tmp/pdfs" / args.run
    pdf_dir.mkdir(parents=True, exist_ok=True)
    for page in pages:
        writer = PdfWriter()
        writer.add_page(reader.pages[page - 1])
        stream = io.BytesIO()
        writer.write(stream)
        data = stream.getvalue()
        (pdf_dir / f"{page:04}.pdf").write_bytes(data)
        inputs[page] = base64.b64encode(data).decode("ascii")
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "source_pages": len(reader.pages),
                "pages": pages,
                "concurrency": args.concurrency,
                "deadline_s": 120,
                "retries": 0,
                "endpoint": args.endpoint,
                "max_json_bytes": max(len(p) for p in inputs.values()) + 200,
            },
            indent=2,
        )
    )
    queue: asyncio.Queue[int] = asyncio.Queue()
    for page in pages:
        queue.put_nowait(page)
    stopped = asyncio.Event()
    records: list[dict[str, Any]] = []
    async with httpx.AsyncClient(trust_env=False, timeout=120) as client:

        async def sample() -> None:
            with (out / "telemetry.jsonl").open("w") as log:
                while not stopped.is_set():
                    sample_data: dict[str, Any] = {"time": time.time()}
                    try:
                        response = await client.get("http://127.0.0.1:8118/metrics", timeout=5)
                        sample_data["vllm"] = [
                            line
                            for line in response.text.splitlines()
                            if not line.startswith("#")
                            and any(
                                name in line
                                for name in (
                                    "num_requests_running",
                                    "num_requests_waiting",
                                    "generation_tokens_total",
                                    "prompt_tokens_total",
                                    "gpu_cache_usage_perc",
                                    "kv_cache_usage_perc",
                                    "request_success_total",
                                )
                            )
                        ]
                        proc = await asyncio.create_subprocess_exec(
                            "nvidia-smi",
                            "--query-gpu=index,utilization.gpu,memory.used,power.draw",
                            "--format=csv,noheader,nounits",
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,
                        )
                        stdout, _ = await proc.communicate()
                        sample_data["gpu"] = stdout.decode().splitlines()
                        sample_data["loadavg"] = Path("/proc/loadavg").read_text().strip()
                    except Exception as exc:
                        sample_data["error_type"] = type(exc).__name__
                    log.write(json.dumps(sample_data) + "\n")
                    log.flush()
                    try:
                        await asyncio.wait_for(stopped.wait(), 1)
                    except TimeoutError:
                        pass

        async def worker() -> None:
            while not queue.empty() and not stopped.is_set():
                page = queue.get_nowait()
                started = time.perf_counter()
                record: dict[str, Any] = {
                    "page": page,
                    "start": time.time(),
                    "id": f"{args.run}-{page}",
                    "success": False,
                }
                try:
                    async with asyncio.timeout(120):
                        response = await client.post(
                            args.endpoint + "/layout-parsing",
                            json={
                                "file": inputs[page],
                                "fileType": 0,
                                "visualize": False,
                                "useLayoutDetection": True,
                                "layoutThreshold": 0.5,
                            },
                            headers={"X-Request-ID": record["id"]},
                        )
                    record["http_status"] = response.status_code
                    record["upstream"] = response.headers.get("X-Pipeline-Upstream")
                    response.raise_for_status()
                    raw = response.json()
                    if raw.get("errorCode") != 0:
                        raise ValueError("Remote business failure")
                    results = raw["result"]["layoutParsingResults"]
                    if len(results) != 1:
                        raise ValueError("Single page response cardinality violation")
                    normalized = normalize_page(results[0], page, started)
                    payload = ParseResponse(
                        data=ResultData(doc_recognize_result=[normalized])
                    ).model_dump(mode="json")
                    (out / f"{page:04}_result.json").write_text(
                        json.dumps(payload, ensure_ascii=False)
                    )
                    record["success"] = True
                    record["dimensions"] = [normalized.image_width, normalized.image_height]
                    record["blocks"] = len(normalized.document_details)
                    record["content_sha256"] = hashlib.sha256(
                        normalized.document_content.encode()
                    ).hexdigest()
                    try:
                        validator.validate(payload)
                        record["strict_valid"] = True
                    except validator.ContractValidationError as exc:
                        record["strict_valid"] = False
                        record["quality_error"] = str(exc)
                except Exception as exc:
                    record["error_type"] = type(exc).__name__
                    # Stop issuing new work on the first failure. Existing requests settle.
                    stopped.set()
                record["seconds"] = time.perf_counter() - started
                record["end"] = time.time()
                records.append(record)
                with (out / "pages.jsonl").open("a") as log:
                    log.write(json.dumps(record) + "\n")
                print(
                    json.dumps(
                        {
                            k: record[k]
                            for k in ("page", "success", "seconds", "upstream")
                            if k in record
                        }
                    ),
                    flush=True,
                )

        started = time.perf_counter()
        sampler = asyncio.create_task(sample())
        await asyncio.gather(*(worker() for _ in range(args.concurrency)))
        elapsed = time.perf_counter() - started
        stopped.set()
        await sampler
    completed = {r["page"] for r in records}
    for page in pages:
        if page not in completed:
            records.append({"page": page, "success": False, "error_type": "NotSubmitted"})
    latencies = [r["seconds"] for r in records if "seconds" in r]
    summary = {
        "requested": len(pages),
        "success": sum(r["success"] for r in records),
        "strict_valid": sum(r.get("strict_valid", False) for r in records),
        "seconds": elapsed,
        "pages_per_second": sum(r["success"] for r in records) / elapsed,
        "p50": percentile(latencies, 0.5),
        "p95": percentile(latencies, 0.95),
        "p99": percentile(latencies, 0.99),
        "records": sorted(records, key=lambda r: r["page"]),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "records"}), flush=True)
    if summary["success"] != len(pages):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--pages", default="1,2,3,4,5,6,7,8")
    parser.add_argument("--concurrency", type=int, choices=range(1, 9), default=8)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8880")
    asyncio.run(run(parser.parse_args()))

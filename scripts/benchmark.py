#!/usr/bin/env python3
"""对 PaddleOCR-VL /layout-parsing 接口执行一个轻量并发压测。"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import math
import pathlib
import statistics
import sys
import time
import urllib.error
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=pathlib.Path, help="本地 PDF、图片或 TIFF 文件")
    parser.add_argument("--base-url", default="http://127.0.0.1:8880")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--requests", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--warmup", type=int, default=1)
    return parser.parse_args()


def percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * ratio) - 1)
    return ordered[index]


def send_request(url: str, body: bytes, timeout: float) -> tuple[float, int]:
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response_body = response.read()
        status = response.status
    elapsed = time.perf_counter() - started

    payload = json.loads(response_body)
    if status != 200 or payload.get("errorCode", 0) != 0:
        raise RuntimeError(
            f"HTTP {status}, errorCode={payload.get('errorCode')}, "
            f"errorMsg={payload.get('errorMsg')}"
        )
    pages = len(payload.get("result", {}).get("layoutParsingResults", []))
    return elapsed, pages


def main() -> int:
    args = parse_args()
    if args.concurrency < 1 or args.requests < 1 or args.warmup < 0:
        raise SystemExit("concurrency/requests 必须大于 0，warmup 不能小于 0")
    if not args.input.is_file():
        raise SystemExit(f"找不到输入文件：{args.input}")

    suffix = args.input.suffix.lower()
    file_type = 0 if suffix == ".pdf" else 1
    encoded = base64.b64encode(args.input.read_bytes()).decode("ascii")
    request_payload = {
        "file": encoded,
        "fileType": file_type,
        "visualize": False,
        "returnMarkdownImages": False,
        "prettifyMarkdown": False,
    }
    body = json.dumps(request_payload, separators=(",", ":")).encode("utf-8")
    url = args.base_url.rstrip("/") + "/layout-parsing"

    print(f"目标：{url}")
    print(f"输入：{args.input} ({args.input.stat().st_size / 1024 / 1024:.2f} MiB)")
    print(f"并发：{args.concurrency}，正式请求：{args.requests}，预热：{args.warmup}")

    for index in range(args.warmup):
        elapsed, pages = send_request(url, body, args.timeout)
        print(f"预热 {index + 1}/{args.warmup}: {elapsed:.3f}s, {pages} 页")

    latencies: list[float] = []
    pages_total = 0
    errors: list[str] = []
    wall_started = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(send_request, url, body, args.timeout)
            for _ in range(args.requests)
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                elapsed, pages = future.result()
                latencies.append(elapsed)
                pages_total += pages
            except (OSError, ValueError, RuntimeError, urllib.error.HTTPError) as exc:
                errors.append(str(exc))

    wall_elapsed = time.perf_counter() - wall_started
    print()
    print(f"成功：{len(latencies)}，失败：{len(errors)}，墙钟时间：{wall_elapsed:.3f}s")
    if latencies:
        print(
            "延迟："
            f"avg={statistics.fmean(latencies):.3f}s, "
            f"p50={percentile(latencies, 0.50):.3f}s, "
            f"p95={percentile(latencies, 0.95):.3f}s, "
            f"max={max(latencies):.3f}s"
        )
        print(f"吞吐：{len(latencies) / wall_elapsed:.3f} 请求/s, {pages_total / wall_elapsed:.3f} 页/s")
    if errors:
        for error in errors[:10]:
            print(f"错误：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""Synthetic boundary probes; never uploads real document content."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


async def run(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run):
        raise ValueError("Invalid run name")
    out = ROOT / "output/smoke" / args.run
    out.mkdir(parents=True, exist_ok=False)
    async with httpx.AsyncClient(trust_env=False, timeout=15) as client:

        async def probe(index: int) -> dict[str, str | int]:
            response = await client.post(
                "http://127.0.0.1:8880/layout-parsing",
                json={},
                headers={"X-Request-ID": f"{args.run}-{index}"},
            )
            return {
                "status": response.status_code,
                "upstream": response.headers.get("X-Pipeline-Upstream", ""),
            }

        results = await asyncio.gather(*(probe(i) for i in range(16)))
    if args.fault:
        assert any(r["status"] == 502 for r in results), results
        assert all(r["status"] in (422, 502) for r in results), results
        assert all("," not in str(r["upstream"]) for r in results), results
    else:
        assert all(r["status"] == 422 for r in results), results
        if args.expected_upstream:
            assert args.expected_upstream in {r["upstream"] for r in results}, results
    # An oversized declared body must be rejected before receiving any body bytes.
    reader, writer = await asyncio.open_connection("127.0.0.1", 8880)
    writer.write(
        (
            "POST /layout-parsing HTTP/1.1\r\nHost: localhost\r\n"
            f"X-Request-ID: {args.run}-oversize\r\nContent-Length: 67108865\r\n"
            "Connection: close\r\nContent-Type: application/json\r\n\r\n"
        ).encode()
    )
    await writer.drain()
    status = (await asyncio.wait_for(reader.readline(), 10)).decode().strip()
    writer.close()
    await writer.wait_closed()
    assert " 413 " in status, status
    payload = {"probes": results, "oversize_status": status, "fault": args.fault}
    (out / "checks.json").write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--fault", action="store_true")
    parser.add_argument("--expected-upstream")
    asyncio.run(run(parser.parse_args()))

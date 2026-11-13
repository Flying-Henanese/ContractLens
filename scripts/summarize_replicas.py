"""Summarize sampled DP/GPU load without reading document text."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any


def summarize(directory: Path) -> dict[str, Any]:
    summary = json.loads((directory / "summary.json").read_text())
    samples = [
        json.loads(line) for line in (directory / "telemetry.jsonl").read_text().splitlines()
    ]
    samples = [s for s in samples if s.get("vllm")]
    engines: dict[str, dict[str, list[float]]] = {}
    gpus: dict[str, list[float]] = {}
    for sample in samples:
        for line in sample["vllm"]:
            match = re.match(r'vllm:(\w+)\{.*engine="(\d+)".*\} ([\d.e+-]+)$', line)
            if match and match[1] in {
                "num_requests_running",
                "num_requests_waiting",
                "generation_tokens_total",
                "prompt_tokens_total",
                "kv_cache_usage_perc",
            }:
                engines.setdefault(match[2], {}).setdefault(match[1], []).append(float(match[3]))
        for line in sample.get("gpu", []):
            fields = line.split(",")
            gpus.setdefault(fields[0].strip(), []).append(float(fields[1]))
    duration = samples[-1]["time"] - samples[0]["time"] if len(samples) > 1 else 0
    ranks = {}
    for engine, metrics in engines.items():
        running = metrics.get("num_requests_running", [0])
        waiting = metrics.get("num_requests_waiting", [0])
        tokens = metrics.get("generation_tokens_total", [0])
        ranks[engine] = {
            "running_mean": statistics.mean(running),
            "running_max": max(running),
            "idle_fraction": sum(n == 0 for n in running) / len(running),
            "waiting_mean": statistics.mean(waiting),
            "waiting_max": max(waiting),
            "generation_tokens_per_second": (tokens[-1] - tokens[0]) / duration if duration else 0,
        }
    records = summary.pop("records")
    by_worker: dict[str, int] = {}
    for record in records:
        worker = record.get("upstream")
        if worker:
            by_worker[worker] = by_worker.get(worker, 0) + 1
    return {
        "run": directory.name,
        **summary,
        "sampling_seconds": duration,
        "ranks": ranks,
        "gpu_util_mean": {k: statistics.mean(v) for k, v in gpus.items()},
        "upstream_pages": by_worker,
        "quality_failures": [
            {"page": r["page"], "reason": r.get("quality_error")}
            for r in records
            if r.get("strict_valid") is False
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directories", nargs="+", type=Path)
    arguments = parser.parse_args()
    for directory in arguments.directories:
        print(json.dumps(summarize(directory), indent=2))

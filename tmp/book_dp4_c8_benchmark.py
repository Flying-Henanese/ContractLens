import asyncio
import importlib.util
import io
import json
import math
import os
import statistics
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pypdf import PdfReader, PdfWriter
from pdf_parser.models import ParseResponse

SOURCE = Path('/Users/zhoushujian/Downloads/Generative AI on Kubernetes Operationalizing Large Language Models (Roland Huss, Daniele Zonca) (z-library.sk, 1lib.sk, z-lib.sk).pdf')
ROOT = Path('output/smoke/book_dp4_c8_recompile64_20261112')
URL = 'http://192.168.0.67:8888/api/v1/documents/parse'
CONCURRENCY = 8
spec = importlib.util.spec_from_file_location('contract_validator', '.harness/scripts/validate_result.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


async def main():
    ROOT.mkdir(parents=True, exist_ok=False)
    (ROOT / 'pages').mkdir()
    reader = PdfReader(SOURCE)
    count = len(reader.pages)
    started = time.perf_counter()
    records = []
    active = 0
    peak = 0
    stop = asyncio.Event()
    stop_reason = None
    failure_streak = 0
    queue = asyncio.Queue()
    for index in range(count):
        queue.put_nowait(index)
    metadata = {'source': str(SOURCE), 'pages': count, 'endpoint': URL, 'dp': 4,
                'max_concurrency': CONCURRENCY, 'request_unit': 'one PDF page',
                'client_retries': 0, 'recompile_limit': 64,
                'started_utc': datetime.now(timezone.utc).isoformat()}
    write_json(ROOT / 'metadata.json', metadata)
    gpu_file = (ROOT / 'gpu.csv').open('w')
    monitor = subprocess.Popen(['ssh', 't4', 'nvidia-smi --query-gpu=timestamp,index,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw --format=csv -l 5'], stdout=gpu_file, stderr=subprocess.DEVNULL)

    def snapshot(status):
        completed = len(records)
        successful = [r['seconds'] for r in records if r['success']]
        ordered = sorted(successful)
        elapsed = time.perf_counter() - started
        value = {'status': status, 'total_pages': count, 'completed': completed,
                 'successful': len(successful), 'failed': completed-len(successful),
                 'quality_failed': sum(r.get('quality') == 'failed' for r in records),
                 'in_flight': active, 'peak_in_flight': peak, 'elapsed_seconds': round(elapsed, 2),
                 'successful_pages_per_second': round(len(successful)/elapsed, 4),
                 'latency_seconds': {'mean': round(statistics.mean(successful), 2) if successful else None,
                                     'p50': round(statistics.median(successful), 2) if successful else None,
                 'p95': round(ordered[math.ceil(len(ordered)*0.95)-1], 2) if ordered else None},
                 'errors': dict(Counter(r.get('error', 'cancelled') for r in records if not r['success'])),
                 'stop_reason': stop_reason}
        write_json(ROOT / 'progress.json', value)
        return value

    async def worker(client):
        nonlocal active, peak, failure_streak, stop_reason
        while not queue.empty() and not stop.is_set():
            index = queue.get_nowait()
            writer = PdfWriter()
            writer.add_page(reader.pages[index])
            stream = io.BytesIO()
            writer.write(stream)
            data = stream.getvalue()
            assert len(PdfReader(io.BytesIO(data)).pages) == 1
            active += 1
            peak = max(peak, active)
            t = time.perf_counter()
            record = {'page': index+1, 'request_pages': 1, 'success': False}
            try:
                response = await client.post(URL, files={'file': (f'page-{index+1:04d}.pdf', data, 'application/pdf')})
                record['http_status'] = response.status_code
                response.raise_for_status()
                payload = response.json()
                parsed = ParseResponse.model_validate(payload)
                pages = parsed.data.doc_recognize_result
                if payload.get('code') != 'success' or len(pages) != 1:
                    raise ValueError('Unexpected response status or page count')
                write_json(ROOT / 'pages' / f'page-{index+1:04d}.json', payload)
                record['success'] = True
                failure_streak = 0
                record['page_parse_seconds'] = [p.parse_time for p in pages]
                try:
                    validator.validate(payload)
                    record['quality'] = 'passed'
                except validator.ContractValidationError:
                    record['quality'] = 'failed'
            except httpx.HTTPStatusError as exc:
                record['error'] = f'HTTP {exc.response.status_code}'
                failure_streak += 1
                if failure_streak >= 3:
                    stop_reason = 'three consecutive failed HTTP responses'
                    stop.set()
            except asyncio.CancelledError:
                record['error'] = 'cancelled'
                raise
            except Exception as exc:
                record['error'] = type(exc).__name__
            finally:
                record['seconds'] = round(time.perf_counter()-t, 3)
                active -= 1
                records.append(record)
                with (ROOT / 'requests.jsonl').open('a') as f:
                    f.write(json.dumps(record)+'\n')
                progress = snapshot('running')
                print(json.dumps({'completed': len(records), 'total': count, **record}), flush=True)
                queue.task_done()

    async def report():
        while True:
            await asyncio.sleep(30)
            print(json.dumps(snapshot('running')), flush=True)

    async def watch_container():
        nonlocal stop_reason
        baseline = None
        while True:
            proc = await asyncio.create_subprocess_exec(
                'ssh', 't4', 'docker inspect contractlens-paddleocr-vlm-server-1 --format "{{.RestartCount}} {{.State.Health.Status}}"',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                fields = stdout.decode().strip().split()
                if fields and fields[0].isdigit():
                    restarts = int(fields[0])
                    if baseline is None:
                        baseline = restarts
                        write_json(ROOT / 'container_baseline.json', {'restart_count': baseline})
                    elif restarts != baseline:
                        stop_reason = f'vLLM container restarted: {baseline} -> {restarts}'
                        stop.set()
                        print(json.dumps({'alert': stop_reason}), flush=True)
                        return
            await asyncio.sleep(10)

    reporter = asyncio.create_task(report())
    watcher = asyncio.create_task(watch_container())
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=330, limits=httpx.Limits(max_connections=8, max_keepalive_connections=8)) as client:
            health = await client.get('http://192.168.0.67:8880/health')
            health.raise_for_status()
            await asyncio.gather(*(worker(client) for _ in range(CONCURRENCY)))
        summary = snapshot('interrupted' if stop.is_set() else 'completed')
        summary.update(metadata)
        write_json(ROOT / 'summary.json', summary)
        print('FINAL '+json.dumps(summary), flush=True)
    finally:
        reporter.cancel()
        watcher.cancel()
        await asyncio.gather(reporter, watcher, return_exceptions=True)
        snapshot('interrupted' if len(records) < count else 'completed')
        monitor.terminate()
        try:
            monitor.wait(timeout=10)
        except subprocess.TimeoutExpired:
            monitor.kill()
            monitor.wait()
        gpu_file.close()


asyncio.run(main())

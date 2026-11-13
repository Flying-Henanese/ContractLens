"""Independent page timeouts must not hide a failed shared backend."""

import argparse
import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "health_status, expected_exit, expected_attempts", [(200, 1, 2), (503, 2, 1)]
)
async def test_timeout_continuation_requires_healthy_backend(
    tmp_path, monkeypatch, respx_mock, health_status, expected_exit, expected_attempts
):
    spec = importlib.util.spec_from_file_location(
        "benchmark_replicas", ROOT / "scripts/benchmark_replicas.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    source = tmp_path / "input.pdf"
    writer = PdfWriter()
    for _ in range(2):
        writer.add_blank_page(width=100, height=100)
    writer.write(source)
    post = respx_mock.post("http://127.0.0.1:8880/layout-parsing").mock(
        side_effect=[
            httpx.ReadTimeout("synthetic timeout"),
            httpx.Response(
                200,
                json={
                    "errorCode": 0,
                    "result": {
                        "layoutParsingResults": [
                            {
                                "prunedResult": {
                                    "width": 100,
                                    "height": 100,
                                    "parsing_res_list": [
                                        {
                                            "block_label": "text",
                                            "block_content": "Synthetic text",
                                            "block_bbox": [0, 0, 10, 10],
                                        }
                                    ],
                                }
                            }
                        ]
                    },
                },
            ),
        ]
    )
    respx_mock.get("http://127.0.0.1:8118/metrics").respond(200, text="")
    respx_mock.get("http://127.0.0.1:8118/health").respond(health_status)
    respx_mock.get("http://127.0.0.1:8880/health").respond(200)
    arguments = argparse.Namespace(
        pdf=str(source),
        run="timeout-test",
        pages="1,2",
        concurrency=1,
        endpoint="http://127.0.0.1:8880",
        repetition_penalty=None,
        continue_timeout_pages=True,
    )
    with pytest.raises(SystemExit) as error:
        await module.run(arguments)
    assert error.value.code == expected_exit
    assert post.call_count == expected_attempts
    result = json.loads((tmp_path / "output/smoke/timeout-test/summary.json").read_text())
    assert result["success"] == expected_attempts - 1
    assert [r["page"] for r in result["records"]] == [1, 2]
    if health_status == 503:
        assert result["records"][1]["error_type"] == "NotSubmitted"

"""Validate the resolved topology without Docker daemon or Ascend hardware."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("workers", [2, 4])
def test_resolved_ascend_replicas(workers):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose CLI required (no daemon needed)")
    command = [
        "docker",
        "compose",
        "-f",
        "compose.ascend.yaml",
        "-f",
        "compose.replicas.ascend.yaml",
    ]
    if workers == 4:
        command += ["-f", "compose.replicas4.ascend.yaml"]
    result = subprocess.run(
        command + ["config", "--format", "json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    services = json.loads(result.stdout)["services"]
    proxy = services["paddleocr-vl-api"]
    assert proxy["image"].startswith("nginx:")
    assert not proxy.get("devices")
    assert not proxy.get("privileged")
    assert not proxy.get("command")
    assert len(proxy["depends_on"]) == workers
    assert services["api"]["environment"]["PDF_PARSER_ENDPOINT"] == "http://paddleocr-vl-api:8080"
    for index in range(1, workers + 1):
        worker = services[f"pipeline-{index}"]
        assert "latest-huawei-npu" in worker["image"]
        assert "CUDA_VISIBLE_DEVICES" not in worker["environment"]
        assert not worker.get("ports")
        assert worker["environment"]["ASCEND_RT_VISIBLE_DEVICES"] == "7"
        assert any(
            (device["source"] if isinstance(device, dict) else device.split(":")[0])
            == "/dev/davinci7"
            for device in worker["devices"]
        )
        assert "paddleocr-vlm-server" in worker["depends_on"]
    assert services["paddleocr-vlm-server"]["environment"]["VLM_DATA_PARALLEL_SIZE"] == "3"

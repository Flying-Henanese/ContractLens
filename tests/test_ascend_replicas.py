"""Validate the resolved topology without Docker daemon or Ascend hardware."""

import json
import os
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
    template = next(
        Path(volume["source"])
        for volume in proxy["volumes"]
        if volume["target"] == "/etc/nginx/templates/default.conf.template"
    )
    assert "client_max_body_size 256m;" in template.read_text(encoding="utf-8")
    assert services["api"]["environment"]["PDF_PARSER_ENDPOINT"] == "http://paddleocr-vl-api:8080"
    for index in range(1, workers + 1):
        worker = services[f"pipeline-{index}"]
        assert "latest-huawei-npu" in worker["image"]
        assert "CUDA_VISIBLE_DEVICES" not in worker["environment"]
        assert not worker.get("ports")
        assert worker["environment"]["ASCEND_RT_VISIBLE_DEVICES"] == "3"
        assert any(
            (device["source"] if isinstance(device, dict) else device.split(":")[0])
            == "/dev/davinci7"
            for device in worker["devices"]
        )
        assert "paddleocr-vlm-server" in worker["depends_on"]
    assert services["paddleocr-vlm-server"]["environment"]["VLM_DATA_PARALLEL_SIZE"] == "3"


def _colocated_config(**overrides: str) -> subprocess.CompletedProcess[str]:
    if not (bash := shutil.which("bash")):
        pytest.skip("Bash required for the deployment configuration script")
    return subprocess.run(
        [bash, "scripts/docker.sh", "config", "--format", "json"],
        cwd=ROOT,
        env=os.environ
        | {
            "CONTRACTLENS_PLATFORM": "ascend",
            "CONTRACTLENS_PIPELINE_MODE": "colocated",
            "CONTRACTLENS_PIPELINE_WORKERS": "2",
            "CONTRACTLENS_COLOCATED_NPU_IDS": "",
            "CONTRACTLENS_COLOCATED_PIPELINE_RT_IDS": "",
            "CONTRACTLENS_COLOCATED_VLM_RT_IDS": "",
            "VLM_DATA_PARALLEL_SIZE": "3",
            "VLM_DATA_PARALLEL_BACKEND": "ray",
            "VLM_NPU_IDS": "7,8,9",
        }
        | overrides,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("overrides", "device_ids", "pipeline_ids", "vlm_ids"),
    [
        ({}, "4,5,6,7", "4,5,6,7", "4,5,6,7"),
        (
            {
                "CONTRACTLENS_COLOCATED_NPU_IDS": "7,9,10,3",
                "CONTRACTLENS_COLOCATED_PIPELINE_RT_IDS": "0,0,0,0",
                "CONTRACTLENS_COLOCATED_VLM_RT_IDS": "3,11,1,0",
            },
            "7,9,10,3",
            "0,0,0,0",
            "0,1,3,11",
        ),
    ],
)
def test_resolved_ascend_colocated(overrides, device_ids, pipeline_ids, vlm_ids):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose CLI required (no daemon needed)")
    result = _colocated_config(**overrides)
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    workers = {f"pipeline-{index}" for index in range(1, 5)}
    assert set(services) == workers | {"api", "paddleocr-vl-api", "paddleocr-vlm-server"}
    proxy = services["paddleocr-vl-api"]
    assert set(proxy["depends_on"]) == workers
    assert not proxy.get("devices")
    assert "server pipeline-3:8080" in proxy["environment"]["PIPELINE_EXTRA_UPSTREAMS"]
    assert "server pipeline-4:8080" in proxy["environment"]["PIPELINE_EXTRA_UPSTREAMS"]
    assert services["api"]["environment"]["PDF_PARSER_ENDPOINT"] == "http://paddleocr-vl-api:8080"
    for index, (physical_id, visible_id) in enumerate(
        zip(device_ids.split(","), pipeline_ids.split(","), strict=True), start=1
    ):
        worker = services[f"pipeline-{index}"]
        assert worker["environment"]["ASCEND_RT_VISIBLE_DEVICES"] == visible_id
        assert set(worker["depends_on"]) == {"paddleocr-vlm-server"}
        assert not worker.get("ports")
        mounted_devices = {
            device["source"] if isinstance(device, dict) else device.split(":")[0]
            for device in worker["devices"]
        }
        assert mounted_devices == {
            f"/dev/davinci{physical_id}",
            "/dev/davinci_manager",
            "/dev/devmm_svm",
            "/dev/hisi_hdc",
        }
    vlm = services["paddleocr-vlm-server"]
    assert vlm["environment"]["ASCEND_RT_VISIBLE_DEVICES"] == vlm_ids
    assert vlm["entrypoint"] == ["vllm"]
    assert vlm["command"][0] == "serve"
    assert not vlm.get("ports")
    for option, expected in {
        "--tensor-parallel-size": "1",
        "--data-parallel-size": "4",
        "--data-parallel-backend": "mp",
        "--api-server-count": "1",
    }.items():
        assert vlm["command"][vlm["command"].index(option) + 1] == expected


@pytest.mark.parametrize(
    ("variable", "value", "message"),
    [
        ("CONTRACTLENS_PLATFORM", "cuda", "requires Ascend"),
        ("CONTRACTLENS_COLOCATED_NPU_IDS", "4,5,6", "four comma-separated"),
        ("CONTRACTLENS_COLOCATED_NPU_IDS", "4,5,4,7", "distinct"),
        ("CONTRACTLENS_COLOCATED_PIPELINE_RT_IDS", "0,0,x,0", "four comma-separated"),
        ("CONTRACTLENS_COLOCATED_VLM_RT_IDS", "0,1,2,2", "distinct"),
    ],
)
def test_invalid_ascend_colocated_config(variable, value, message):
    result = _colocated_config(**{variable: value})
    assert result.returncode == 2
    assert message in result.stderr

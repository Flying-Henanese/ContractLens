"""Validate the resolved topology without Docker daemon or Ascend hardware."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE_SERVICES = {"api", "paddleocr-vl-api", "paddleocr-vlm-server"}


@pytest.fixture
def compose_project(tmp_path):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose CLI required (no daemon needed)")
    for path in ROOT.glob("compose*.yaml"):
        shutil.copyfile(path, tmp_path / path.name)
    return tmp_path


def resolve_compose(project, dotenv=None):
    if dotenv is not None:
        (project / ".env").write_text(dotenv, encoding="utf-8")
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(
            ("COMPOSE_", "CONTRACTLENS_", "PDF_PARSER_", "VLM_", "PIPELINE_", "ASCEND_", "API_PORT")
        )
    }
    result = subprocess.run(
        ["docker", "compose", "-f", "compose.yaml", "config", "--format", "json"],
        cwd=project,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    config = json.loads(result.stdout)
    assert config["name"] == "contractlens"
    return config["services"]


@pytest.mark.parametrize(
    ("dotenv", "workers"),
    [
        (None, 4),
        ("CONTRACTLENS_PLATFORM=ascend\n", 4),
        (
            "CONTRACTLENS_PLATFORM=ascend\n"
            "CONTRACTLENS_PIPELINE_MODE=replicas\n"
            "CONTRACTLENS_PIPELINE_WORKERS=2\n",
            2,
        ),
    ],
)
def test_resolved_ascend_replicas(compose_project, dotenv, workers):
    services = resolve_compose(compose_project, dotenv)
    worker_names = {f"pipeline-{index}" for index in range(1, workers + 1)}
    assert services.keys() == CORE_SERVICES | worker_names
    proxy = services["paddleocr-vl-api"]
    assert proxy["image"].startswith("nginx:")
    assert not proxy.get("devices")
    assert not proxy.get("privileged")
    assert not proxy.get("command")
    assert proxy["depends_on"].keys() == worker_names
    upstreams = proxy["environment"]["PIPELINE_EXTRA_UPSTREAMS"]
    assert ("server pipeline-3:8080" in upstreams) == (workers == 4)
    assert ("server pipeline-4:8080" in upstreams) == (workers == 4)
    template = next(
        Path(volume["source"])
        for volume in proxy["volumes"]
        if volume["target"] == "/etc/nginx/templates/default.conf.template"
    )
    original_template = ROOT / template.relative_to(compose_project)
    assert "client_max_body_size 256m;" in original_template.read_text(encoding="utf-8")
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


@pytest.mark.parametrize(
    ("dotenv", "device_var"),
    [
        ("CONTRACTLENS_PLATFORM=cuda\n", "CUDA_VISIBLE_DEVICES"),
        (
            "CONTRACTLENS_PLATFORM=ascend\nCONTRACTLENS_PIPELINE_MODE=single\n",
            "ASCEND_RT_VISIBLE_DEVICES",
        ),
    ],
)
def test_dotenv_selects_platform_and_configures_gateway(compose_project, dotenv, device_var):
    services = resolve_compose(compose_project, dotenv + "PDF_PARSER_PORT=9876\n")
    assert services.keys() == CORE_SERVICES
    assert device_var in services["paddleocr-vl-api"]["environment"]
    assert services["api"]["ports"][0]["published"] == "9876"

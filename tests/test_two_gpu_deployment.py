"""Reject invalid GPU placement before invoking Docker or changing services."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("selectors", [("2", "2"), ("02", "2"), ("x", "3"), ("", "3")])
def test_two_gpu_rejects_invalid_placement(tmp_path: Path, selectors: tuple[str, str]) -> None:
    environment = tmp_path / "deployment.env"
    environment.write_text(f"COLOCATED_GPU_1={selectors[0]}\nCOLOCATED_GPU_2={selectors[1]}\n")
    env = os.environ.copy()
    env.pop("COLOCATED_GPU_1", None)
    env.pop("COLOCATED_GPU_2", None)
    env["CONTRACTLENS_ENV_FILE"] = str(environment)
    process = subprocess.run(
        ["bash", str(ROOT / "scripts/docker-two-gpu.sh"), "up"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 2
    assert "host GPU" in process.stderr

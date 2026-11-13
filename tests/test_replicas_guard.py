"""The experimental selector must reject Ascend before invoking Docker."""

import os
import subprocess
from pathlib import Path


def test_replicas_rejects_ascend_before_docker():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["bash", str(root / "scripts/docker.sh"), "up"],
        env={
            **os.environ,
            "CONTRACTLENS_PLATFORM": "ascend",
            "CONTRACTLENS_PIPELINE_MODE": "replicas",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "supports CUDA only" in result.stderr

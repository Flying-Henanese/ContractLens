from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_separates_cuda_build_and_runtime_stages():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "nvidia/cuda:${CUDA_VERSION}-devel-ubuntu${UBUNTU_VERSION} AS builder" in dockerfile
    assert "nvidia/cuda:${CUDA_VERSION}-runtime-ubuntu${UBUNTU_VERSION} AS runtime" in dockerfile
    assert dockerfile.index(" AS builder") < dockerfile.index(" AS runtime")
    runtime = dockerfile.split(" AS runtime", maxsplit=1)[1]
    assert "COPY --from=builder" in runtime
    assert "COPY --from=uv" not in runtime
    assert "USER 10001:10001" in runtime
    assert 'ENTRYPOINT ["pdf-parser-api"]' in runtime


def test_compose_targets_amd64_cuda_and_existing_service_port():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "platform: linux/amd64" in compose
    assert 'CUDA_VERSION: "12.2.2"' in compose
    assert '"${PDF_PARSER_PORT:-8888}:8888"' in compose
    assert "driver: nvidia" in compose
    assert "count: all" in compose
    assert "read_only: true" in compose


def test_docker_build_context_excludes_user_data_and_local_environment():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in dockerignore
    assert "resources" in dockerignore
    assert "output" in dockerignore
    assert ".venv" in dockerignore


def test_linux_docker_helper_wraps_expected_compose_actions():
    helper = (ROOT / "scripts" / "docker.sh").read_text(encoding="utf-8")

    assert helper.startswith("#!/usr/bin/env bash\n")
    assert "set -Eeuo pipefail" in helper
    for action in ("config", "build", "up", "down", "restart", "logs", "ps"):
        assert f"    {action})" in helper
    assert "docker compose" in helper
    assert not (ROOT / "scripts" / "docker.ps1").exists()

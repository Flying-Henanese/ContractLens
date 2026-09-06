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


def test_ascend_dockerfile_is_multi_arch_and_separates_build_from_runtime():
    dockerfile = (ROOT / "Dockerfile.ascend").read_text(encoding="utf-8")

    assert "ARG ASCEND_BASE_IMAGE=ubuntu:22.04" in dockerfile
    assert "FROM ${ASCEND_BASE_IMAGE} AS builder" in dockerfile
    assert "FROM ${ASCEND_BASE_IMAGE} AS runtime" in dockerfile
    assert dockerfile.index(" AS builder") < dockerfile.index(" AS runtime")
    runtime = dockerfile.split(" AS runtime", maxsplit=1)[1]
    assert "COPY --from=builder" in runtime
    assert "COPY --from=uv" not in runtime
    assert "USER 10001:10001" in runtime
    assert 'ENTRYPOINT ["pdf-parser-api"]' in runtime


def test_unified_cuda_compose_starts_gateway_and_inference_stack_together():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "dockerfile: ${PDF_PARSER_DOCKERFILE:-Dockerfile}" in compose
    assert 'CUDA_VERSION: "12.2.2"' in compose
    assert '"${PDF_PARSER_PORT:-8888}:8888"' in compose
    assert "platform:" not in compose
    assert "read_only: true" in compose
    assert "PYTHONPATH: /app/src" in compose
    assert "- --reload" in compose
    assert "- --reload-dir" in compose
    assert "- /app/src" in compose
    assert "source: ./src" in compose
    assert "target: /app/src" in compose
    assert "paddleocr-vlm-server:" in compose
    assert "paddleocr-vl-api:" in compose
    assert "http://paddleocr-vl-api:8080" in compose
    assert "paddleocr-vl-api:" in compose.split("depends_on:", maxsplit=1)[1]
    assert "./paddleocr-server/PaddleOCR-VL-1.6.yaml" in compose
    assert "./paddleocr-server/vllm_config.yaml" in compose


def test_unified_ascend_compose_keeps_gateway_and_inference_in_one_lifecycle():
    compose = (ROOT / "compose.ascend.yaml").read_text(encoding="utf-8")

    assert "api:" in compose
    assert "paddleocr-vlm-server:" in compose
    assert "paddleocr-vl-api:" in compose
    assert "http://paddleocr-vl-api:8080" in compose
    assert "ASCEND_RT_VISIBLE_DEVICES" in compose
    assert "./paddleocr-server/docker/vlm-entrypoint-ascend.sh" in compose
    assert "${VLM_NPU_IDS:-4,5,6}" in compose
    assert "${VLM_DATA_PARALLEL_SIZE:-3}" in compose
    assert "${VLM_GPU_MEMORY_UTILIZATION:-0.3}" in compose
    assert "${PIPELINE_NPU_ID:-7}" in compose


def test_ascend_environment_template_preserves_inference_defaults():
    env_template = (ROOT / ".env.ascend.template").read_text(encoding="utf-8")

    assert "PIPELINE_NPU_ID=7" in env_template
    assert "VLM_NPU_IDS=4,5,6" in env_template
    assert "VLM_DATA_PARALLEL_SIZE=3" in env_template
    assert "VLM_GPU_MEMORY_UTILIZATION=0.3" in env_template


def test_docker_build_context_excludes_user_data_and_local_environment():
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".env" in dockerignore
    assert "resources" in dockerignore
    assert "output" in dockerignore
    assert ".venv" in dockerignore
    assert "paddleocr-server" in dockerignore


def test_linux_docker_helper_wraps_expected_compose_actions():
    helper = (ROOT / "scripts" / "docker.sh").read_text(encoding="utf-8")

    assert helper.startswith("#!/usr/bin/env bash\n")
    assert "set -Eeuo pipefail" in helper
    for action in ("config", "build", "up", "down", "restart", "logs", "ps"):
        assert f"    {action})" in helper
    assert "docker compose" in helper
    assert "CONTRACTLENS_PLATFORM" in helper
    assert "CONTRACTLENS_ENV_FILE" in helper
    assert "compose.ascend.yaml" in helper
    assert not (ROOT / "scripts" / "docker.ps1").exists()

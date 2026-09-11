# Runtime And Configuration

## Scope and authority

This directory documents the imported inference module. ContractLens production
configuration is authoritative at the repository root: `compose.yaml`,
`compose.ascend.yaml`, `.env.template`, `.env.ascend.template`, and
`scripts/docker.sh`. The local two-service Compose files are historical
inference-only references and are not a deployment entry point.

## Supported production environments

### CUDA

- Linux, Docker Compose, NVIDIA drivers and NVIDIA Container Toolkit.
- The root CUDA template assigns one Pipeline GPU and two VLM GPUs by default.

### Huawei Ascend

- Linux, Docker Compose, Ascend 910B with compatible driver, firmware and
  container runtime.
- The host must provide the Ascend driver, `npu-smi`, and DCMI mount paths.
- The root Ascend template assigns Pipeline NPU `7`, VLM NPUs `4,5,6`, data
  parallel size `3`, and HBM-use parameter `0.3` by default. These are
  configuration defaults, not proof that the root Ascend stack has run.

## Configuration layering

1. The root `.env.template` or `.env.ascend.template` supplies deployment
   parameters.
2. Root Compose starts the gateway, Pipeline, and VLM in one lifecycle. The
   gateway calls PaddleX through `http://paddleocr-vl-api:8080`.
3. Both inference services read this directory through the read-only mount at
   `/opt/paddleocr-server`.
4. The VLM entrypoint validates its visible-device count and generates a
   temporary configuration from `vllm_config.yaml`.
5. `PaddleOCR-VL-1.6.yaml` configures Pipeline behavior and reaches vLLM at
   `http://paddleocr-vlm-server:8118/v1`.

`VLM_NPU_IDS` or `VLM_GPU_IDS` must contain exactly
`VLM_DATA_PARALLEL_SIZE` devices; the Pipeline device must not overlap with the
VLM list. Compose parsing cannot validate either hardware condition.

## Operational entry

From the repository root:

```bash
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh config
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh up
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh ps
```

Build only when the gateway image inputs (`pyproject.toml`, `uv.lock`, Dockerfile,
or build arguments) change. Changes to this module's mounted entrypoint or Pipeline
configuration require the affected inference service to restart or be recreated;
they do not require an image rebuild.

## Verification limit

Static Compose parsing does not prove image availability, NPU drivers, mounted-device
compatibility, entrypoint execution, health checks, or parsing behavior. CUDA has a
recorded root-stack smoke result; Ascend does not yet. Record image digest, device
state, health endpoints, and a real parse result before claiming current Ascend
support.

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
- The root CUDA Compose defaults to Pipeline GPU `4` and VLM GPUs `5,6`
  (DP `2`). `docker/vlm-entrypoint.sh` checks the visible-device count and generates
  a temporary configuration from `vllm_config.yaml` for `paddleocr genai_server`.

### Huawei Ascend

- Linux, Docker Compose, Ascend 910B with compatible driver, firmware and
  container runtime.
- The host must provide the Ascend driver, `npu-smi`, DCMI mount paths, and local
  model files under `/data1/models/PaddlePaddle/PaddleOCR-VL`. Compose mounts that
  model directory read-only at `/models/PaddleOCR-VL`.
- The base Compose runs both inference services with `privileged: true`. The
  Pipeline sets `ASCEND_RT_VISIBLE_DEVICES` from `PIPELINE_NPU_ID` (default `7`).
  vLLM sets it from `VLM_NPU_IDS` (default `4,5,6`), with DP `3` and HBM-use parameter `0.3`.
- Ascend vLLM uses `quay.io/ascend/vllm-ascend:v0.30.0rc2` and starts `vllm serve`
  directly. Compose supplies the model path and serving flags. `ASCEND_VLM_IMAGE_TAG`
  remains in the env template. The effective image is set by `image:` in the root Ascend Compose.
- Replica workers default to `ASCEND_PRIVILEGED=false`. Their device mount uses
  `/dev/davinci${PIPELINE_NPU_ID:-7}` while their `ASCEND_RT_VISIBLE_DEVICES` is fixed
  at `3`. Check which physical device the target runtime exposes before enabling
  replicas. Changing `PIPELINE_NPU_ID` changes the worker mount only.

## Configuration layering

1. The root `.env.template` or `.env.ascend.template` supplies deployment
   parameters.
2. Root Compose manages the gateway, Pipeline, and VLM in one lifecycle. The
   gateway calls `http://paddleocr-vl-api:8080`; this service runs Nginx when
   Ascend replica mode is selected.
3. Root Compose mounts this directory read-only at `/opt/paddleocr-server` in
   the inference containers. PaddleX reads its Pipeline YAML there, and the CUDA
   VLM entrypoint reads its configuration template there.
4. `PaddleOCR-VL-1.6.yaml` configures Pipeline behavior and reaches vLLM at
   `http://paddleocr-vlm-server:8118/v1`.

`VLM_NPU_IDS` or `VLM_GPU_IDS` must contain exactly
`VLM_DATA_PARALLEL_SIZE` devices; the Pipeline device must not overlap with the
VLM list. Check the full mapping before starting Ascend, whose direct startup bypasses
the repository's scripted device-count check. Compose parsing resolves the values only.

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

# Project Overview

## Current role

`paddleocr-server/` is the inference module imported into the ContractLens
monorepo. It supplies one PaddleOCR Pipeline and one vLLM service with multiple
data-parallel model ranks. The root repository owns the business API, public output
contract, deployment lifecycle, and production documentation.

The current product architecture is:

```text
External caller -> ContractLens gateway -> PaddleX Pipeline -> vLLM ranks
```

The module keeps CUDA and Ascend inference settings separate, but it is not an
independently deployable ContractLens product. Use root Compose and
`scripts/docker.sh`; never use this directory's historical two-service Compose or
host launcher to operate the product.

## Inference capabilities

- PaddleX `layout-parsing` receives documents from the gateway.
- PP-DocLayoutV3 performs preprocessing and layout analysis.
- The Pipeline fans layout crops out to PaddleOCR-VL-1.6-0.9B vLLM ranks.
- One vLLM API Server schedules data-parallel ranks; the Pipeline uses one internal
  service URL rather than manually managed model endpoints.
- CUDA and Ascend image, device and driver requirements remain module-owned.

## Important files

- `../compose.yaml`, `../compose.ascend.yaml`: supported production orchestration.
- `PaddleOCR-VL-1.6.yaml`: Pipeline topology and features.
- `vllm_config.yaml`: vLLM data-parallel template.
- `docker/vlm-entrypoint*.sh`: validates device count and writes temporary runtime
  configuration.
- `compose.yaml`, `compose.ascend.yaml`, `start_vl.sh`: imported historical
  inference-only references, not production entry points.

## Verification status

The root CUDA topology has completed one documented startup and parsing smoke test.
The root Ascend topology has static configuration evidence only; its hardware,
images, drivers and real parsing require target-host validation.

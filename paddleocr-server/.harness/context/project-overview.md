# Project Overview

## Current role

`paddleocr-server/` is the inference module imported into the ContractLens
monorepo. It supplies PaddleOCR Pipeline configuration and one vLLM service with
multiple data-parallel model ranks. The root repository owns the business API,
public output contract, deployment lifecycle, and
[production topology](../../../.harness/architecture/README.md#compose-拓扑).

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

- `../compose.yaml`: root entry point for platform and topology selection.
- `PaddleOCR-VL-1.6.yaml`: Pipeline topology and features.
- `vllm_config.yaml`, `docker/vlm-entrypoint.sh`: CUDA vLLM runtime template and
  startup script with a device-count check.
- `../compose.ascend.single.yaml`: defines Ascend vLLM with its model mount and CLI flags.
- `docker/vlm-entrypoint-ascend.sh`: retained startup script for the imported
  inference-only Ascend Compose.
- `compose.yaml`, `compose.ascend.yaml`, `start_vl.sh`: imported historical
  inference-only references, not production entry points.

## Verification status

The root CUDA topology has completed one documented startup and parsing smoke test.
The root Ascend topology has static configuration evidence only; its hardware,
images, drivers and real parsing require target-host validation.

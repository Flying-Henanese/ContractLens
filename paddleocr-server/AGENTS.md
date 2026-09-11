# Imported PaddleOCR Inference Module

## Scope and production boundary

`paddleocr-server/` is the imported PaddleOCR-VL inference module inside the
ContractLens monorepo. It owns PaddleX Pipeline, vLLM, CUDA/Ascend device and
model configuration; it does not own the public document API or the production
deployment lifecycle.

For ContractLens production, the only supported lifecycle entry is the repository
root:

```bash
CONTRACTLENS_PLATFORM={cuda|ascend} bash scripts/docker.sh <config|build|up|ps|logs|restart|down>
```

The root Compose file starts one three-service stack:

```text
api -> paddleocr-vl-api -> paddleocr-vlm-server
```

The local `compose*.yaml` files and `start_vl.sh` remain imported inference-only
references. They may help inspect the original hardware configuration, but must not
be used to deploy ContractLens or manage its production containers: they omit the
gateway and can conflict with the root Compose service names and ports.

## Verification status

- The root CUDA stack completed a 2026-09-11 startup, health, and real-parse smoke
  validation; see `../.harness/operations/remote-state.md`.
- The root Ascend stack has passed static Compose and shell checks only. Its image
  compatibility, driver mounts, startup, health checks, and real parsing have not
  been verified on an Ascend host.
- Historical statements about validating the inference module's two-service CUDA or
  Ascend setup do not prove the current root three-service deployment.

## Module responsibilities and constraints

The inference chain remains one PaddleX Pipeline followed by one vLLM API Server
with multiple data-parallel model ranks. Do not add a reverse proxy, Ray Serve, or
manually managed VLM addresses unless the user explicitly asks.

- Keep Pipeline and VLM physical GPU/NPU assignments separate.
- The number of `VLM_GPU_IDS` or `VLM_NPU_IDS` must equal
  `VLM_DATA_PARALLEL_SIZE`; the VLM entrypoint checks this at startup.
- Do not change model versions, image tags, inference dependencies, NCCL settings,
  Ascend driver mounts, `privileged`, shared memory, or model caches without explicit
  user direction and target-hardware evidence.
- Root Compose read-only mounts this complete directory at
  `/opt/paddleocr-server` in both inference services. Keep the entrypoints and
  Pipeline paths compatible with that mount.
- Never delete or alter the host PaddleX model cache, commit generated runtime YAML,
  logs, model files, `.env` files, or real user inputs/results.

## Key files

- `../compose.yaml`, `../compose.ascend.yaml`: supported CUDA/Ascend production
  orchestration.
- `../.env.template`, `../.env.ascend.template`: supported deployment templates.
- `docker/vlm-entrypoint.sh`, `docker/vlm-entrypoint-ascend.sh`: CUDA/Ascend VLM
  startup validation and runtime configuration generation.
- `PaddleOCR-VL-1.6.yaml`: Pipeline configuration. Its Compose VLM URL must remain
  `http://paddleocr-vlm-server:8118/v1`.
- `vllm_config.yaml`: vLLM template; entrypoints generate a temporary copy rather
  than modifying this file.
- `.harness/context/`: inference-internal configuration explanations. Root
  architecture and operations documents take precedence for deployment facts.

## Change and validation requirements

Keep changes small and update the matching root template, root Compose file,
documentation, and static tests when a shared configuration contract changes. Shell
scripts use Bash with `set -Eeuo pipefail`; quote paths and variables.

For an Ascend-related change, first validate the root topology:

```bash
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh config
bash -n paddleocr-server/docker/vlm-entrypoint-ascend.sh
git diff --check
```

On an approved Ascend host, first check NPU availability, driver mounts, images and
ports; then use the root lifecycle helper to start and inspect all three services.
Confirm gateway `/openapi.json`, PaddleX `/health`, VLM `/v1/models`, and a real
parse before claiming Ascend support. Do not report unavailable hardware as a
configuration failure.

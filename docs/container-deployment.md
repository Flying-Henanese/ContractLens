# Unified Docker Compose deployment

The repository contains the ContractLens gateway and an imported
`paddleocr-server` inference module. A single root Compose command manages their
shared lifecycle:

1. `paddleocr-vlm-server` starts the PaddleOCR-VL vLLM replicas;
2. `paddleocr-vl-api` waits for the model process, starts PaddleX, and exposes
   `/layout-parsing` on container port `8080`; and
3. `api` waits for PaddleX health, then exposes the ContractLens document API on
   port `8888`.

The gateway uses `http://paddleocr-vl-api:8080` only inside the Compose network.
`API_PORT` (default `8880`) is a host mapping for operator access and must not be
used as the internal URL. The CUDA Compose also retains `VLM_PORT` (default `8118`)
from the imported inference configuration. These raw ports are preserved for this
initial integration and must be reviewed before an Internet-facing release.

## Gateway images

### CUDA

The default `Dockerfile` uses two CUDA stages:

- `nvidia/cuda:12.2.2-devel-ubuntu22.04` installs the uv-managed Python 3.11 runtime
  and locked production dependencies.
- `nvidia/cuda:12.2.2-runtime-ubuntu22.04` receives only the managed Python runtime
  and completed virtual environment.

### Huawei Ascend

`Dockerfile.ascend` uses a multi-stage Ubuntu base and supports Docker's native
`linux/amd64` and `linux/arm64` builds. It intentionally does not install CANN,
Ascend drivers, or Paddle NPU packages because inference stays in the imported
PaddleOCR module. `ASCEND_BASE_IMAGE` can replace the default `ubuntu:22.04` base
when an organization requires an approved internal Ubuntu-derived image.

Both final gateway images run as UID/GID `10001`, use a read-only root filesystem,
and write temporary uploaded PDFs under the `/tmp` tmpfs.

## Compose configuration

Compose reads `.env`. Start from `.env.template` and review the gateway, inference
device, image, and model-cache settings. The gateway's Compose-only endpoint is
`PDF_PARSER_DOCKER_ENDPOINT=http://paddleocr-vl-api:8080`; it intentionally differs
from `PDF_PARSER_ENDPOINT`, which remains for standalone CLI/FastAPI use.

The default CUDA selection is:

```dotenv
PDF_PARSER_DOCKERFILE=Dockerfile
PDF_PARSER_IMAGE=pdf-parser:cuda12.2
PDF_PARSER_PORT=8888
PDF_PARSER_TMPFS_SIZE=2g
PADDLEX_CACHE_DIR=/home/mineru_dev/.paddlex
PIPELINE_GPU_ID=4
VLM_GPU_IDS=5,6
VLM_DATA_PARALLEL_SIZE=2
```

For an Ascend host, use `compose.ascend.yaml` through the lifecycle helper and set
the Ascend-specific gateway image and inference device values:

```dotenv
PDF_PARSER_ASCEND_DOCKERFILE=Dockerfile.ascend
PDF_PARSER_ASCEND_IMAGE=pdf-parser:ascend-ubuntu22.04
ASCEND_BASE_IMAGE=ubuntu:22.04
PIPELINE_NPU_ID=0
VLM_NPU_IDS=1,2
```

`compose.yaml` is the CUDA topology. `compose.ascend.yaml` keeps the imported
inference module's verified NPU driver mounts, `privileged` setting, and device
environment variables. Do not run the CUDA file on Ascend or the Ascend file on a
CUDA host.

## Host prerequisites

For either host, confirm:

1. Docker Engine and Docker Compose v2 are installed;
2. the host can pull the selected images;
3. the target host has the appropriate NVIDIA or Ascend container support and device
   drivers for the selected inference topology;
4. the PaddleX model-cache path exists and must not be cleared by deployment; and
5. an ARM64 Ascend host builds the gateway natively rather than forcing
   `linux/amd64` emulation.

## Active-iteration source mount

Both Compose files bind-mount `./src` read-only at `/app/src`, set
`PYTHONPATH=/app/src`, and start Uvicorn with reload restricted to that directory.
Python source changes are therefore detected without rebuilding the gateway image.

The mount does not replace the image-managed Python interpreter or locked
dependencies. Changes to `pyproject.toml`, `uv.lock`, either Dockerfile, either
Compose file, the imported inference configuration, or environment configuration
require a rebuild or container recreation.

## Review and lifecycle commands

The Linux helper defaults to CUDA and non-mutating validation:

```bash
bash scripts/docker.sh
bash scripts/docker.sh config
```

Build and start the gateway, PaddleX, and vLLM together:

```bash
bash scripts/docker.sh build
bash scripts/docker.sh up
bash scripts/docker.sh ps
bash scripts/docker.sh logs
```

Other supported actions are `restart` and `down`. The gateway health check requests
`http://127.0.0.1:8888/openapi.json` inside its container. The external document API
is available at `http://<host>:${PDF_PARSER_PORT}`.

For Ascend, prefix the same command with `CONTRACTLENS_PLATFORM=ascend`:

```bash
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh config
CONTRACTLENS_PLATFORM=ascend bash scripts/docker.sh up
```

## T4 rollout

The T4 server uses the CUDA selection unless the deployment owner explicitly selects
Ascend. Deployment must still follow the repository remote workflow: inspect the
remote branch and worktree, pull with `--ff-only`, validate Compose, update the
three-process stack together, inspect all health checks and logs, and run a real
parse smoke test. Dependency synchronization happens inside the gateway image build;
do not run `uv sync` on the host.

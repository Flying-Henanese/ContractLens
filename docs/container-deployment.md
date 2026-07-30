# Docker Compose deployment

The FastAPI client can be built for either the existing CUDA 12.2 environment or a
Huawei Ascend host. Both deployments use the same `compose.yaml`; only the selected
Dockerfile and image tag change.

Containerization does not move PaddleX inference into this repository. The service
continues to call the remote `layout-parsing` Pipeline configured by
`PDF_PARSER_ENDPOINT`, so the application container does not consume a local GPU or
NPU.

## Image designs

### CUDA

The default `Dockerfile` uses two CUDA stages:

- `nvidia/cuda:12.2.2-devel-ubuntu22.04` installs the uv-managed Python 3.11 runtime
  and locked production dependencies.
- `nvidia/cuda:12.2.2-runtime-ubuntu22.04` receives only the managed Python runtime
  and completed virtual environment.

### Huawei Ascend

`Dockerfile.ascend` uses a multi-stage Ubuntu base and supports Docker's native
`linux/amd64` and `linux/arm64` builds. It intentionally does not install CANN,
Ascend drivers, or Paddle NPU packages because this container performs no local model
inference. `ASCEND_BASE_IMAGE` can replace the default `ubuntu:22.04` base when an
organization requires an approved internal Ubuntu-derived image.

Both final images run as UID/GID `10001`, use a read-only root filesystem, and write
temporary uploaded PDFs under the `/tmp` tmpfs.

## Shared Compose configuration

Compose reads `.env`. Start from `.env.template` and review the remote endpoint plus
the container settings.

The default CUDA selection is:

```dotenv
PDF_PARSER_DOCKERFILE=Dockerfile
PDF_PARSER_IMAGE=pdf-parser:cuda12.2
PDF_PARSER_PORT=8888
PDF_PARSER_TMPFS_SIZE=2g
```

For an Ascend host, change only the image selection:

```dotenv
PDF_PARSER_DOCKERFILE=Dockerfile.ascend
PDF_PARSER_IMAGE=pdf-parser:ascend-ubuntu22.04
ASCEND_BASE_IMAGE=ubuntu:22.04
```

`compose.yaml` does not set `platform`, so Docker builds for the host's native CPU
architecture. It also does not reserve NVIDIA or Ascend devices: neither is used by
this remote-inference client. This is what makes the application service, ports,
environment, security settings, source mount, health check, and lifecycle commands
shareable across both hosts.

If local NPU inference is added in the future, it will require an Ascend-specific
Compose override for device nodes, driver libraries, and CANN settings; the current
shared file must not be assumed sufficient for that different architecture.

## Host prerequisites

For either host, confirm:

1. Docker Engine and Docker Compose v2 are installed;
2. the host can pull the selected base images and Python dependencies;
3. the container can reach `PDF_PARSER_ENDPOINT`;
4. an ARM64 Ascend host builds natively rather than forcing `linux/amd64` emulation.

No NVIDIA Container Toolkit, Ascend Docker Runtime, or NPU device mapping is required
for this client container.

## Active-iteration source mount

`compose.yaml` bind-mounts `./src` read-only at `/app/src`, sets
`PYTHONPATH=/app/src`, and starts Uvicorn with reload restricted to that directory.
Python source changes are therefore detected without rebuilding the image.

The mount does not replace the image-managed Python interpreter or locked
dependencies. Changes to `pyproject.toml`, `uv.lock`, either Dockerfile,
`compose.yaml`, or environment configuration require a rebuild or container
recreation.

## Review and lifecycle commands

The Linux helper defaults to non-mutating validation:

```bash
bash scripts/docker.sh
bash scripts/docker.sh config
```

Build and start the Dockerfile selected by `.env`:

```bash
bash scripts/docker.sh build
bash scripts/docker.sh up
bash scripts/docker.sh ps
bash scripts/docker.sh logs
```

Other supported actions are `restart` and `down`. The health check requests
`http://127.0.0.1:8888/openapi.json` inside the container. The external API is
available at `http://<host>:${PDF_PARSER_PORT}`.

## T4 rollout

The T4 server continues to use the default CUDA selection. Deployment must still
follow the repository remote workflow: inspect the remote branch and worktree, pull
with `--ff-only`, validate Compose, rebuild when container inputs change, update the
service, inspect health and logs, and run the real smoke test. Dependency
synchronization happens inside the image build; do not run `uv sync` on the host.

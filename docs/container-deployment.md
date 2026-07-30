# Docker Compose deployment

The FastAPI service can be built for CUDA 12.2, Linux amd64, and Ubuntu 22.04.
Containerization does not move PaddleX inference into this repository: the service
continues to call the remote `layout-parsing` Pipeline configured by
`PDF_PARSER_ENDPOINT`.

## Image design

The Dockerfile uses two CUDA stages:

- `nvidia/cuda:12.2.2-devel-ubuntu22.04` installs uv-managed Python 3.11 and the
  locked production dependencies. Compilers, uv, and its cache remain in this
  builder stage.
- `nvidia/cuda:12.2.2-runtime-ubuntu22.04` receives only the managed Python
  interpreter and the completed virtual environment.

The final process runs as UID/GID `10001`, uses a read-only root filesystem, and
writes temporary uploaded PDFs under the `/tmp` tmpfs.

## Configuration

Docker Compose reads the same variables as the existing `.env` file. Start from
`.env.template` and review at least:

```dotenv
PDF_PARSER_ENDPOINT=http://192.168.0.194:8080
PDF_PARSER_PORT=8888
PDF_PARSER_TMPFS_SIZE=2g
PDF_PARSER_IMAGE=pdf-parser:cuda12.2
```

`PDF_PARSER_PORT`, `PDF_PARSER_TMPFS_SIZE`, and `PDF_PARSER_IMAGE` are Compose-only
settings. Other `PDF_PARSER_*` values are passed into the application container.
Do not append `/layout-parsing` or `/health` to `PDF_PARSER_ENDPOINT`.

## Host prerequisites

Before deployment, confirm that the Linux x86_64 host has:

1. an NVIDIA driver compatible with CUDA 12.2;
2. Docker Engine and Docker Compose v2;
3. NVIDIA Container Toolkit configured for Docker;
4. network access from the container to `PDF_PARSER_ENDPOINT`.

The Compose service reserves all available NVIDIA GPUs. This preserves the requested
CUDA runtime contract, although the current PDF Parser client does not itself run
GPU inference.

## Active-iteration source mount

`compose.yaml` is configured for the current rapid-iteration phase. It bind-mounts
`./src` read-only at `/app/src`, sets `PYTHONPATH=/app/src`, and overrides the image
entrypoint with Uvicorn restricted to reload that directory. Python source changes are
therefore detected and reloaded without rebuilding or recreating the container.

The mount does not replace the image-managed Python interpreter or locked dependencies.
Changes to `pyproject.toml`, `uv.lock`, `Dockerfile`, `compose.yaml`, or environment
configuration still require a rebuild or container recreation. The source mount is
read-only; do not edit application code inside the container.
## Review and lifecycle commands

The Linux helper defaults to the non-mutating Compose validation action:

```bash
bash scripts/docker.sh
bash scripts/docker.sh config
```

After review and approval, the lifecycle is:

```bash
bash scripts/docker.sh build
bash scripts/docker.sh up
bash scripts/docker.sh ps
bash scripts/docker.sh logs
bash scripts/docker.sh restart
bash scripts/docker.sh down
```

`build` pulls current content for the pinned base tags. `up` starts the service in
the background with the `unless-stopped` restart policy. `down` removes the
container and Compose network but retains the locally built image.

The health check requests `http://127.0.0.1:8888/openapi.json` from inside the
container. The external API remains available on
`http://<host>:${PDF_PARSER_PORT}`.

## Future T4 rollout

Do not run the commands below until the local files are approved. The later server
rollout must still follow the repository remote deployment workflow:

1. inspect the remote branch and working tree and stop if it is dirty;
2. run `git pull --ff-only` in `/home/mineru_dev/projects/ContractLens`;
3. validate Compose configuration;
4. build the image;
5. start the service and inspect its health and logs;
6. run the repository remote smoke test against the deployed API.

Dependency synchronization happens inside the Docker image build. Do not run
`uv sync` separately on the T4 host.

---
status: completed
owner: Codex
created: 2026-07-29
updated: 2026-07-29
scope:
  - container-deployment
  - fastapi-service
supersedes: []
blocked_by: []
---

# Containerize the FastAPI service

## Goal and user value

Provide a reviewable local Docker deployment definition for the existing FastAPI
service so it can later be built and managed on the T4 server with Docker Compose.
The target is CUDA 12.2, Linux amd64, and Ubuntu, with a full build image and a
smaller runtime image.

## Current facts and constraints

- The application is a remote PaddleX Pipeline client; it does not run model
  inference locally.
- The service entry point is `pdf-parser-api`, listening on `0.0.0.0:8888`.
- Python 3.11 or newer is required and dependencies are locked by `uv.lock`.
- This phase must not connect to, build on, or start containers on the remote server.
- The runtime retains CUDA compatibility even though this client does not invoke it.

## Implementation stages

- [x] Inspect the existing entry point, settings, lockfile, and repository rules.
- [x] Add a two-stage CUDA Dockerfile and a narrow Docker build context.
- [x] Add a Compose service and a Linux Bash lifecycle helper.
- [x] Document local review, configuration, and future server rollout commands.
- [x] Validate local syntax and the repository delivery gate without building or
  starting the image.

## Validation and acceptance

- Compose YAML parsed successfully as `linux/amd64`.
- Linux Bash syntax validation accepted `scripts/docker.sh`.
- Static container configuration tests passed.
- `& .\.harness\scripts\check.ps1` passed with 41 tests and one third-party warning.
- Docker Compose CLI validation was unavailable because Docker is not installed.
- No image was built and no container was started.

## Progress log

- 2026-07-29: Confirmed the FastAPI entry point and Python 3.11 requirement.
- 2026-07-29: Added CUDA 12.2.2 Ubuntu 22.04 devel/runtime image stages, Compose GPU
  reservations, lifecycle commands, documentation, and static tests.
- 2026-07-29: Completed local static and repository validation.

## Unexpected discoveries

- The service has no local health route, so the health check uses `/openapi.json`
  without changing the public API.
- Ubuntu 22.04 does not provide the required Python by default. The builder uses
  uv-managed Python 3.11 and copies that interpreter into the runtime stage.
- Docker CLI is not installed in the local environment.

## Decision log

- Keep compilers, uv, and build caches in the CUDA `devel` stage only.
- Use the CUDA `runtime` image, a non-root user, read-only root filesystem, and a
  writable `/tmp` tmpfs in the final service.
- Keep remote deployment out of this change until the user confirms the files.

## Recovery and rollback

The container files are additive. Removing them returns the project to its existing
uv startup flow.

## Result summary

The repository now has a reviewable two-stage CUDA 12.2 container deployment for
Linux amd64, without any local or remote build/start action.

# syntax=docker/dockerfile:1.7

ARG CUDA_VERSION=12.2.2
ARG UBUNTU_VERSION=22.04
ARG PYTHON_VERSION=3.11
ARG UV_VERSION=0.11.32

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM nvidia/cuda:${CUDA_VERSION}-devel-ubuntu${UBUNTU_VERSION} AS builder

ARG PYTHON_VERSION

ENV DEBIAN_FRONTEND=noninteractive \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=automatic \
    UV_PYTHON_INSTALL_DIR=/opt/python

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv python install "${PYTHON_VERSION}" && \
    uv sync --frozen --no-install-project

COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable

FROM nvidia/cuda:${CUDA_VERSION}-runtime-ubuntu${UBUNTU_VERSION} AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 contractlens && \
    useradd --uid 10001 --gid contractlens --no-create-home --shell /usr/sbin/nologin contractlens

WORKDIR /app

COPY --from=builder --chown=contractlens:contractlens /opt/python /opt/python
COPY --from=builder --chown=contractlens:contractlens /app/.venv /app/.venv

USER 10001:10001

EXPOSE 8888

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8888/openapi.json', timeout=3)"]

ENTRYPOINT ["pdf-parser-api"]

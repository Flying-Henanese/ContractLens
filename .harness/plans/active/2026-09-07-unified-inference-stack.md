---
status: active
owner: Codex
created: 2026-09-07
updated: 2026-09-11
scope:
  - repository-layout
  - gateway-module
  - inference-module
  - provider-contract
  - deployment
  - verification
supersedes:
  - separate-repositories
  - static-remote-endpoint
blocked_by: []
---

# Unified document-inference stack

## Goal and user value

Consolidate `ContractLens` and `paddleocr-server` into one monorepo and one
deployable document-processing product.  The product must retain a single
business-facing HTTP interface while keeping model execution, hardware
configuration, and PaddleX-specific protocol details behind a narrow seam.

The desired outcome is not one Python environment or one container.  It is one
repository, one release process, and one Compose topology with three separately
deployable runtime processes:

1. the gateway module exposes the stable document API;
2. the PaddleX inference module performs document parsing; and
3. the vLLM process remains private to the inference module.

This gives callers one supported endpoint and allows the inference
implementation to change without spreading its details into business callers.

## Current facts and constraints

- The current `ContractLens` package is a gateway/adapter.  It validates input,
  currently splits PDFs into pages, calls `POST /layout-parsing`, and normalizes
  PaddleX output into the public `ParseResponse` contract.
- The imported `paddleocr-server/` inference module owns the inference topology.
  Its PaddleX process listens on container port `8080` and is published on host
  port `8880`; it calls its vLLM process over port `8118`.
- The gateway's currently configured default, `http://192.168.0.194:8080`, is
  a historical remote endpoint.  The current T4 deployment record identifies
  the PaddleOCR-VL endpoint as `http://192.168.0.67:8880`.  A host port and a
  container port must not be conflated.
- Both repositories depend on the raw PaddleX `layout-parsing` protocol:
  request JSON contains Base64 `file`, `fileType`, and inference options;
  successful responses contain `errorCode == 0` and
  `result.layoutParsingResults`.  The public ContractLens JSON is a separate
  compatibility contract and must not become the model-process output.
- The gateway targets Python 3.11+ and small CPU-only dependencies.  The
  inference repository has GPU/NPU-specific PaddleOCR, PaddleX, Torch, and
  vLLM dependencies with a broader Python range.  A shared virtual environment
  or lock file would couple unrelated runtime concerns and is explicitly out of
  scope.
- CUDA and Ascend deployments, GPU/NPU separation, model-cache mounts, and
  fail-fast output semantics are established operational constraints.  No
  migration step may delete a cache, alter a model version, or produce a
  partial successful parse.
- The existing active plan for whole-document submission remains valid: the
  target inference module can return all PDF pages in one request, while the
  gateway currently submits one page at a time.

## Current implementation scope

The initial delivery intentionally implemented only the following reversible
subset. It has since passed a CUDA T4 startup, endpoint, and real-parse smoke
validation; the remaining target architecture work is still deliberately
deferred:

1. preserve the `paddleocr-server` Git history under the literal
   `paddleocr-server/` directory in this repository;
2. extend the root CUDA and Ascend Compose files to start the gateway, PaddleX,
   and vLLM in one `up`/`down` lifecycle; and
3. route the gateway container to `paddleocr-vl-api:8080` through Compose DNS.

It does not yet move the gateway into `apps/gateway`, rename environment
variables, extract a protocol-contract module, change PDF submission granularity,
pin images, or restrict raw inference ports. The imported provider's existing
host ports remain available pending target-server verification. Those deferred
items are the later stages of this plan, not completed architecture facts.

## Target architecture

```text
External caller
  -> Gateway module (:8888, public)
       input validation, deadline/retry policy, provider adapter,
       result normalizer, stable ParseResponse
  -> Inference module (:8080 inside the Compose network, private)
       PaddleX Pipeline, PP-DocLayout, layout task preparation and reassembly
  -> VLM process (:8118 inside the Compose network, private)
       PaddleOCR-VL model replicas and continuous batching
```

The gateway module and inference module are independent deep modules.  Their
only runtime seam is a versioned provider contract.  The VLM process has no
gateway-facing interface: only the inference module knows its OpenAI-compatible
`/v1` interface and its device topology.

### Repository layout

`ContractLens` is the recommended canonical repository because it already owns
the business-facing name, output contract, FastAPI endpoint, and T4 application
location.  Import the inference repository with its Git history preserved.

```text
ContractLens/
  apps/gateway/                 # moved ContractLens application
    src/pdf_parser/
    tests/
    pyproject.toml
    uv.lock
    Dockerfile*
  modules/inference/            # imported paddleocr-server history
    compose.cuda.yaml
    compose.ascend.yaml
    PaddleOCR-VL-1.6.yaml
    vllm_config.yaml
    docker/
    scripts/
    pyproject.toml
  contracts/layout-parsing-v1/  # protocol specification and safe fixtures
    README.md
    request.schema.json
    response-excerpts/
  deploy/
    compose.yaml                # common three-process topology
    compose.cuda.yaml
    compose.ascend.yaml
    compose.diagnostics.yaml    # opt-in localhost-only raw-port access
  scripts/
    docker.sh                   # sole supported lifecycle entry
  docs/architecture/
```

`apps/gateway` and `modules/inference` retain separate `pyproject.toml` files,
virtual environments, locks, test commands, and image build contexts.  The root
is an orchestration repository, not a Python package.  This is intentional
depth: callers learn one gateway interface; inference complexity stays local to
its module.

### Runtime topology and exposure

The unified Compose deployment creates two networks:

- `edge`: only the gateway joins it and publishes `8888`.
- `inference-internal` (`internal: true`): gateway, PaddleX, and vLLM join it.

The gateway's Compose-only default provider URL is
`http://paddleocr-vl-api:8080`; it is service DNS plus the provider's container
port, never a host IP or published port.  `paddleocr-vl-api` no longer maps
`8880` by default, and `paddleocr-vlm-server` never maps `8118` by default.
An opt-in diagnostics overlay may map either port to `127.0.0.1` for an
authorized operator.  It must not make them Internet-facing.

The gateway must expose separate health meanings:

- liveness reports that the gateway process can accept requests;
- readiness reports whether its configured provider is reachable; and
- the existing parse route never reports a partial result if readiness changes
  during processing.

The process dependencies are startup hints only.  A healthy gateway is allowed
to start before the slow model processes complete their initialization; request
handling uses the provider deadline and mapped errors instead of assuming
Compose ordering is proof of inference readiness.

## Module interfaces

### Public gateway interface

`POST /api/v1/documents/parse` remains the sole supported business parse
interface.  It continues to receive a multipart PDF or supported image and to
return the existing `ParseResponse` JSON, including normalized page order,
seal identifiers, references, coordinates, and fail-fast behavior.  Existing
callers therefore need no model-specific change.

The gateway module owns:

- file type, MIME, binary-signature, empty-file, encrypted-PDF, and page-count
  validation;
- a total request deadline, retry budget, request correlation ID, and error
  mapping;
- normalization of raw provider pages into the stable public response; and
- redacted operational metrics: count, byte size, page count, status, attempt
  count, and latency only.  It never logs Base64, document body, or parsed text.

### Provider contract seam

Inside the gateway, all HTTP-specific knowledge belongs in one adapter behind
one small interface:

```python
class LayoutParsingProvider(Protocol):
    async def parse(
        self, document: ValidatedDocument, options: ParseOptions
    ) -> RawLayoutParsingDocument: ...
```

`ValidatedDocument` encapsulates validated bytes, input kind, filename-free
correlation metadata, and expected page count. `ParseOptions` holds the small,
document-level set of supported inference switches. `RawLayoutParsingDocument`
contains ordered provider pages and no public compatibility fields.

`PaddleXHttpProvider` is the first adapter at this seam.  It alone serializes
Base64, assigns `fileType`, calls `/layout-parsing`, checks HTTP status and
`errorCode`, and validates page-array shape.  The normalizer receives its result
without importing HTTP types or knowing the endpoint URL.  A fake adapter makes
gateway tests deterministic; a second real adapter is not needed until a real
provider variant exists.

The initial unified behavior submits one complete validated PDF once, sets
`fileType=0`, then verifies provider page count equals the locally observed page
count before normalizing in response order. Images use `fileType=1` and require
exactly one provider page. This completes the existing whole-document plan at
the correct seam instead of preserving page splitting as a transport leak.

### Failure and deadline interface

The gateway preserves fail-fast semantics and maps errors consistently:

| Condition | Public result | Retry |
| --- | --- | --- |
| Invalid or unsupported input | 400 | no |
| Provider connection failure, non-JSON response, invalid success shape | 502 | transport failures only |
| Total request deadline or provider timeout with no budget left | 504 | only while deadline budget remains |
| Provider business error (`errorCode != 0`) | 502 | no |
| Normalization/contract violation after provider success | 502 | no |

The total document deadline is authoritative.  Every retry receives only the
remaining time budget, so a nominal per-attempt timeout cannot extend a
300-second request indefinitely.  No retry may return a mixture of pages from
different attempts.

## Contract ownership and compatibility

Create `contracts/layout-parsing-v1` as the only shared source for the raw
provider seam. It contains a concise Markdown contract, request JSON Schema,
sanitized response excerpts covering text, table, seal, page dimensions and
provider errors, and fixture provenance without document content.

The contract explicitly fixes:

1. endpoint, method, JSON encoding, Base64 field, and `fileType` mapping;
2. the gateway-supported inference options and their defaults;
3. success and error envelope requirements;
4. ordered `layoutParsingResults` and document/image page-count rules;
5. fields consumed by the normalizer, with an `extra fields permitted` policy;
6. retryability, deadlines, and redaction requirements; and
7. provider image digest plus PaddleOCR/PaddleX/vLLM version as deployment
   evidence, not as a hard-coded source assumption.

Contract checks run without a GPU:

- adapter tests assert exact request serialization against an in-process mock;
- fixture tests assert parsing/normalization of representative response excerpts;
- a negative suite covers malformed envelopes, page-count mismatch, timeouts,
  and error mapping; and
- a compose-level gateway test uses a controllable mock provider.

Target-hardware smoke tests run separately on T4 and record only non-sensitive
summaries under the existing smoke-output policy. Before the first unified
release, pin currently verified inference images by immutable digest. Do not
silently retain mutable `latest-*` tags as the production compatibility promise.

## Configuration and operations

The gateway configuration is renamed by role, for example
`CONTRACTLENS_PROVIDER_BASE_URL`, `CONTRACTLENS_TOTAL_TIMEOUT_SECONDS`, and
`CONTRACTLENS_RETRY_LIMIT`. The former `PDF_PARSER_*` variables are accepted as
deprecated aliases for one release and produce a redacted startup warning.
Defaults differ by execution mode:

- unified Compose: provider service DNS and container port;
- local gateway development: an explicitly supplied URL; and
- no default public/private IP committed in source.

CUDA and Ascend overlays retain the established device assignments, mounts,
shared memory, and entrypoint validations.  The merge moves configuration
without changing their values or upgrading images/dependencies.  Model cache
paths become required deployment variables with the current T4 value preserved
only in an untracked environment file.

`scripts/docker.sh` becomes the sole release entry point. It must provide
`config`, `build`, `up`, `ps`, `logs`, `restart`, `down`, and `smoke` commands
that select CUDA or Ascend overlays explicitly. It never runs recursive cleanup,
removes model caches, or resets a worktree.

## Migration stages

### Stage 0 — freeze facts and select release authority

Choose `ContractLens` as the canonical repository, record the exact current
T4 image digests, provider OpenAPI/result observations, deployed branch, ports,
and model-cache mounts. Tag both source repositories with pre-merge release
tags. Decide whether an operator needs local diagnostics access to raw ports.

Acceptance: both source checkouts are clean; no current image is changed; the
pre-merge gateway can successfully call the existing provider endpoint.

### Stage 1 — history-preserving monorepo import

Create a dedicated merge branch in the canonical repository. Add the inference
repository as a temporary Git remote and use `git subtree add` without
`--squash` under `modules/inference`. Move the existing gateway files with
`git mv` into `apps/gateway`. Do not use `git merge --allow-unrelated-histories`
because root-level `README`, `pyproject`, and Compose files would produce an
unreviewable conflict set.

Acceptance: both module histories remain inspectable, each module's pre-merge
tests still run from its own directory, and no runtime behavior changes yet.

### Stage 2 — establish the contract module

Extract safe request/response fixtures and add the provider adapter seam in the
gateway without changing the external parse response. Retain the current
single-page adapter temporarily only behind the new interface, then add
whole-document contract tests.

Acceptance: unit and contract tests prove equivalent normalized output for the
same safe fixture, while no real document/Base64 appears in version control.

### Stage 3 — compose unification

Create base, CUDA, Ascend, and diagnostics Compose files. Wire the gateway to
`paddleocr-vl-api:8080` on the internal network, publish only gateway `8888`,
and preserve all hardware configuration through overlays. Add liveness and
readiness checks plus an operator smoke command.

Acceptance: both platform compose configurations parse; default topology has no
host mapping for `8880` or `8118`; the gateway health/readiness distinction is
testable with a mock provider.

### Stage 4 — document-level submission

Replace PDF page splitting with one provider request per complete PDF, validate
the returned page count, and normalize in response order. Remove the obsolete
page-concurrency configuration and documentation only after contract and real
provider smoke results are accepted.

Acceptance: a generated multi-page test PDF produces one provider call; a
page-count mismatch fails the entire document; image behavior remains one call
and one page; output compatibility tests pass.

### Stage 5 — staged T4 rollout

First deploy the new gateway against the existing inference processes to prove
the seam. Then schedule one controlled switch to the unified Compose topology;
the model devices cannot safely host duplicate inference stacks. Run a
representative parse smoke test and benchmark before allowing normal traffic.

Acceptance: gateway API output matches compatibility fixtures, provider and
gateway health checks pass, logs are redacted, and performance/error metrics are
compared to a pre-switch baseline.

### Stage 6 — deprecate the second repository

After a release window and rollback window, archive the separate
`paddleocr-server` repository with a README pointing to the monorepo. Do not
delete its history. Remove deprecated endpoint/configuration aliases only in a
subsequent versioned release.

Acceptance: a fresh clone of the canonical repository can build, configure, and
operate the entire stack using documented commands.

## Verification and acceptance

For every stage, run the closest module tests before combined checks. The final
gate includes gateway lint/tests, inference shell syntax/Python compile/Compose
configuration checks for CUDA and Ascend, contract tests, and `git diff --check`.
On available target hardware, run the unified smoke command with an approved
sample and compare output page count, coordinates, seals, errors, and latency
against the recorded baseline. Missing GPU/NPU hardware is reported as an
unexecuted validation, never as a configuration failure.

The merge is accepted only when:

- callers use `:8888` and receive unchanged public response semantics;
- provider and VLM internals are not caller dependencies;
- raw protocol compatibility is exercised in CI without remote hardware;
- default deployment exposes no raw inference/model port;
- CUDA and Ascend retain their verified operational contracts; and
- a rollback can restore the prior tagged deployment without cache deletion or
  data migration.

## Decision log

- 2026-09-07: Recommend a monorepo with separate gateway and inference modules,
  rather than a monolithic Python package or image. Reason: their dependency,
  hardware, release, and security concerns differ materially.
- 2026-09-07: Recommend `ContractLens` as canonical repository. Reason: it owns
  the external product interface and current T4 application deployment.
- 2026-09-07: Recommend a versioned raw provider contract module. Reason: the
  current implicit coupling is functional but not independently verifiable.
- 2026-09-07: Recommend internal-only `8080`/`8118` by default. Reason: the
  gateway is the intended public seam; raw ports need explicit operator choice.

## Open decisions

1. Confirm that `ContractLens` remains the repository and product name.
2. Choose the supported platform release order: CUDA first, Ascend first, or
   both as a hard gate.
3. Decide whether localhost-only raw-port diagnostics are required in the first
   unified release.
4. Confirm the acceptable external timeout and maximum upload size before
   enforcing a new request-size limit.

## Recovery and rollback

Keep both pre-merge tags, the existing independent Compose files, and the
previous gateway image available until the release window closes. If the unified
topology fails, stop only the new Compose project, restart the tagged previous
deployment, and point the gateway back to the verified provider URL. Do not run
volume deletion, cache cleanup, image pruning, Git reset, or model download as
part of rollback. There is no persistent application data migration to reverse.

## Progress log

- 2026-09-07: Captured current gateway/provider relationship and created this
  target design. No production code, configuration, image, remote deployment,
  or user document was changed.
- 2026-09-07: Created `codex/unify-inference-stack`, imported the
  `paddleocr-server` main history as `paddleocr-server/`, and added root CUDA
  and Ascend Compose topologies. The gateway depends on the PaddleX healthcheck
  and receives the internal `http://paddleocr-vl-api:8080` endpoint; PaddleX
  depends on the vLLM healthcheck. `scripts/docker.sh` selects the CUDA or
  Ascend topology through `CONTRACTLENS_PLATFORM`.
- 2026-09-11: Corrected the inference services to read their entrypoint and
  Pipeline configuration from a read-only `./paddleocr-server` directory mount.
  On T4 CUDA, `bash scripts/docker.sh config`, `up`, and `ps` succeeded; the
  gateway, PaddleX, and vLLM containers all became healthy. Gateway OpenAPI and
  PaddleX health checks succeeded, and a temporary text-bearing one-page PDF
  completed an end-to-end PaddleX parse whose result passed `validate_result.py`.
  The existing gateway and inference images were reused because no image input
  changed. GPU 4 served PaddleX and GPUs 5–6 served vLLM. This verifies the
  glue-only scope on CUDA, not Ascend, performance, or the later contract and
  port-isolation stages.

## Unexpected findings

- The gateway's default endpoint is historical and differs from the recorded
  current inference deployment. Unified Compose now resolves the host/container
  distinction through service DNS; standalone gateway use must still provide an
  explicitly reachable PaddleX endpoint.
- The gateway currently splits PDFs despite an active, evidence-backed plan to
  use a single whole-document provider request. The merge should complete that
  plan at the provider seam rather than preserve it indefinitely.

## Result summary

The glue-only monorepo and unified Compose implementation is complete and has
passed one CUDA T4 startup and real-parse smoke validation. The target
architecture remains active: provider-contract extraction, internal-only raw
ports, liveness/readiness separation, document-level PDF submission, Ascend
verification, and release/rollback work are not complete.

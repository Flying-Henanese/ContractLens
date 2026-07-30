---
status: active
owner: Codex
created: 2026-07-30
updated: 2026-07-30
scope:
  - src/pdf_parser/models.py
  - src/pdf_parser/normalization
  - src/pdf_parser/service.py
  - src/pdf_parser/api.py
  - tests
  - README.md
  - docs/api.md
supersedes: []
blocked_by: []
---

# Element image resources

## Goal and user value

Expose optional, stable image-resource metadata (`image_id`, `image_url`, and
`image_mime_type`) for parsed visual elements, so callers can retrieve the
original crop without depending on PaddleX's transient Base64 response.

## Current facts and constraints

- PaddleX response `markdown.images` is an in-memory mapping of logical names
  to Base64 image data. The current normalizer only uses seal-image names to
  resolve crop coordinates and discards image bytes.
- The public response has no image-resource fields. `SealDetail.seal_id` is an
  element identifier, not a stored image identifier.
- The implementation must not write Base64 or full remote responses to logs,
  diagnostics, or the repository. It must preserve unrelated working-tree
  changes.
- Remote capability must be verified with representative images and PDFs
  before deciding whether PaddleX supplies a crop for every target element, or
  whether the client must derive crops from a page image.

## Phases

1. Probe the remote service with representative repository inputs and record
   only non-sensitive summaries of element labels, crop-resource keys, MIME
   types, and coverage.
2. Define the output contract and storage boundary, including the behavior
   when PaddleX provides no crop for an element.
3. Implement models, resource persistence, normalization wiring, API handling,
   documentation, and focused tests.
4. Run focused tests, the repository check, and a remote smoke test where
   applicable; archive this plan with evidence.

## Acceptance criteria

- Remote evidence distinguishes supplied image crops from elements requiring
  client-side cropping.
- Every returned visual element has documented optional resource fields with
  unambiguous identifier, URL, and MIME semantics.
- No response exposes Base64; persisted resources are retrievable through the
  returned URL/ID according to the selected storage policy.
- Existing parse behavior and unrelated working-tree changes are preserved.

## Progress log

- 2026-07-30: Started. Previous single-image probe confirmed that seal crop
  images are returned in `markdown.images` as Base64 values. Broader element
  coverage is pending.

## Unexpected findings

- None yet.

## Decision log

- Pending remote coverage evidence and a storage-policy decision.

## Recovery and rollback

- Keep image-resource fields optional. If persistence fails, parsing must fail
  rather than return a successful response with dangling resource URLs.

## Result summary

- Pending.

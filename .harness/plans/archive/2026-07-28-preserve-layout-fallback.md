# Preserve PaddleX layout fallback content

Status: completed
Owner: Codex
Created: 2026-07-28
Last updated: 2026-07-28

## Goal and scope

Preserve a safe, text-only fallback representation from PaddleX layout results in the
normalized JSON, while retaining the existing page, table, and seal contracts. Inspect
the remote response for seal crop metadata and report whether object storage is needed;
do not upload document images or introduce an OSS dependency.

## Current facts and constraints

- The service response contains `markdown.images`; its keys may encode seal crop boxes,
  while values are Base64 and must never be persisted or logged.
- `DocumentDetail` permits extra fields, but has no declared `layout_fallback_text`.
- The user does not require `ocr_confidence` compatibility.
- User samples under `resources/` are read-only reference data.

## Phases

- [ ] Inspect sanitized remote response fields and sample AIGC metadata.
- [x] Add text-only fallback content to the output model and normalization, with tests.
- [x] Run offline checks and a one-page remote smoke test; record findings.

## Intended changes

- Update `models.py`, `normalization/paddlex.py`, `tests/test_normalization.py`, and
  README output documentation only as required by the verified response contract.
- Keep Base64 image values out of output. Do not add object storage configuration.

## Verification

- Unit tests cover fallback text for empty/processed layout content and absence when no
  fallback exists.
- Run `.harness/scripts/check.ps1` and one remote parse into `output/smoke/`.

## Progress log

- 2026-07-28: Plan created; remote and sample-data inspection in progress.

## Results

- The remote response contains a seal crop key `imgs/img_in_seal_box_619_1_852_231.jpg` in `markdown.images`, whose value is Base64. It returned no `seal_res_list`, so no structured seal OCR result or stable seal reference can be built from this response alone.
- The response has no native `layout_fallback_text`; normalized details now retain text-only `block_content` as that field. Base64 image values remain excluded.
- `tests/test_normalization.py` passed (6 tests), the full Harness check passed (25 tests), and a one-page remote smoke output contains fallback text without a Base64 data URI. The legacy result validator still reports the pre-existing missing `seal_id` for the generic `Seal` block.

## Decision log

- Preserve only textual/HTML fallback values that already occur in the remote response.
  Image crops remain transient because the existing output contract forbids persisting
  Markdown Base64 values.

## Progress log

- 2026-07-28: Completed remote inspection, model/normalizer/test/README update, and validation.

## Recovery and rollback

- Remove the new optional output field and its normalizer mapping to restore the prior
  output shape. No remote state or user samples are modified.

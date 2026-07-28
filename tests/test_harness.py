from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / ".harness" / "scripts" / "validate_result.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("harness_validate_result", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_payload() -> dict:
    token = "[印章1]"
    return {
        "code": "success",
        "message": "",
        "tips": None,
        "data": {
            "task_id": "",
            "file_url": "",
            "status": 4,
            "message": "",
            "doc_recognize_result": [
                {
                    "page_num": 1,
                    "document_content": token,
                    "image_width": 100,
                    "image_height": 200,
                    "document_details": [
                        {
                            "type": "Seal",
                            "text": "测试章",
                            "position": [],
                            "layout_label": "seal",
                            "layout_mapped_type": "Seal",
                            "layout_score": 0.9,
                            "layout_order": 0,
                            "layout_reading_index": 0,
                            "layout_bbox": [10, 20, 40, 50],
                            "seal_id": "page-1-seal-1",
                            "seal_index": 1,
                            "reference_token": token,
                            "seal_region_bbox": [10, 20, 40, 50],
                            "coordinate_space": "page_pixels_top_left",
                            "texts": [],
                        }
                    ],
                    "content_references": [
                        {
                            "token": token,
                            "target_type": "Seal",
                            "target_id": "page-1-seal-1",
                            "start_offset": 0,
                            "end_offset": len(token),
                        }
                    ],
                    "parse_time": 0.1,
                }
            ],
            "aigc": {
                "Label": "AIGCLabelType.AI_GENERATED",
                "ProcessingTypes": ["ocr"],
            },
        },
    }


def test_result_validator_reuses_models_and_accepts_cross_field_invariants():
    validator = _load_validator()
    validator.validate(_valid_payload())


def test_result_validator_rejects_invalid_reference_offset():
    validator = _load_validator()
    payload = _valid_payload()
    payload["data"]["doc_recognize_result"][0]["content_references"][0]["end_offset"] = 3

    with pytest.raises(validator.ContractValidationError, match="offsets do not select"):
        validator.validate(payload)


def test_result_validator_rejects_invalid_model_shape():
    validator = _load_validator()
    payload = _valid_payload()
    payload["data"]["doc_recognize_result"][0]["image_width"] = "wide"

    with pytest.raises(validator.ContractValidationError, match="output structure is invalid"):
        validator.validate(payload)


def test_harness_lint_passes_for_repository_structure():
    result = subprocess.run(
        [sys.executable, ".harness/scripts/harness_lint.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "harness validation passed" in result.stdout


def test_result_validator_cli(tmp_path: Path):
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(_valid_payload(), ensure_ascii=False), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), str(result_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "validation passed" in result.stdout

import time

import pytest
from pydantic import ValidationError

from pdf_parser.models import DocumentDetail, PageResult, SealDetail
from pdf_parser.normalization.paddlex import normalize_page


def test_normalize_page_uses_ocr_for_empty_table_block():
    raw = {
        "prunedResult": {
            "width": 1000,
            "height": 1400,
            "parsing_res_list": [
                {
                    "block_label": "doc_title",
                    "block_content": "技术规范书",
                    "block_bbox": [100, 50, 900, 150],
                    "block_order": 0,
                },
                {
                    "block_label": "table",
                    "block_content": "",
                    "block_bbox": [100, 200, 900, 800],
                    "block_order": 1,
                },
            ],
            "overall_ocr_res": {
                "rec_texts": ["技术规范书", "设备名称", "GPU服务器"],
                "rec_scores": [0.99, 0.96, 0.95],
                "rec_boxes": [
                    [100, 50, 900, 150],
                    [120, 220, 400, 280],
                    [450, 220, 850, 280],
                ],
            },
        },
        "markdown": {"text": ""},
    }

    result = normalize_page(raw, page_num=2, started_at=time.perf_counter())

    assert result.page_num == 2
    assert result.image_width == 1000
    assert result.image_height == 1400
    assert "设备名称\nGPU服务器" in result.document_content
    assert result.document_details[0].type == "Title"
    assert result.document_details[0].layout_fallback_text == result.document_details[0].text
    assert result.document_details[1].type == "Table"
    assert result.document_details[1].layout_fallback_text == ""
    assert result.document_details[1].layout_bbox == [100, 200, 900, 800]
    assert result.document_details[1].position[0].points[2].x == 900


def test_seal_polygons_are_translated_with_actual_markdown_crop_bbox():
    raw = {
        "prunedResult": {
            "width": 1000,
            "height": 1200,
            "parsing_res_list": [
                {
                    "block_label": "text",
                    "block_content": "投标人信息",
                    "block_bbox": [50, 50, 500, 100],
                }
            ],
            "layout_det_res": {
                "boxes": [
                    {
                        "label": "seal",
                        "score": 0.91,
                        "coordinate": [100.8, 200.2, 300.9, 400.7],
                    }
                ]
            },
            "seal_res_list": [
                {
                    "rec_texts": ["测试有限公司", "41"],
                    "rec_scores": [0.93, 0.85],
                    "rec_polys": [
                        [[10, 20], [50, 20], [50, 60], [10, 60]],
                        [[60, 70], [80, 70], [80, 90], [60, 90]],
                    ],
                    "rec_boxes": [],
                }
            ],
        },
        "markdown": {
            "text": "",
            "images": {"imgs/img_in_seal_box_100_200_300_400.jpg": "base64"},
        },
    }

    result = normalize_page(raw, page_num=3, started_at=time.perf_counter())

    seal = result.document_details[-1]
    assert isinstance(seal, SealDetail)
    assert seal.seal_id == "page-3-seal-1"
    assert seal.reference_token == "[印章1]"
    assert seal.seal_region_bbox == [100, 200, 300, 400]
    assert seal.layout_bbox == [100, 200, 300, 400]
    assert seal.texts[0].layout_bbox == [110, 220, 150, 260]
    assert seal.texts[0].position[0].points[0].model_dump() == {"x": 110, "y": 220}
    assert seal.texts[1].layout_bbox == [160, 270, 180, 290]
    assert result.content_references[0].target_id == seal.seal_id
    reference = result.content_references[0]
    assert result.document_content[reference.start_offset : reference.end_offset] == "[印章1]"


def test_structured_seal_replaces_duplicate_parsing_block():
    raw = {
        "prunedResult": {
            "width": 500,
            "height": 800,
            "parsing_res_list": [
                {
                    "block_label": "text",
                    "block_content": "盖章说明",
                    "block_bbox": [20, 20, 200, 60],
                    "block_order": 0,
                },
                {
                    "block_label": "seal",
                    "block_content": "重复的版面印章文字",
                    "block_bbox": [100, 100, 300, 300],
                    "block_order": 1,
                },
            ],
            "layout_det_res": {"boxes": [{"label": "seal", "coordinate": [100, 100, 300, 300]}]},
            "seal_res_list": [
                {
                    "rec_texts": ["测试有限公司"],
                    "rec_scores": [0.95],
                    "rec_polys": [[[10, 10], [100, 10], [100, 80], [10, 80]]],
                }
            ],
        },
        "markdown": {
            "images": {"imgs/img_in_seal_box_100_100_300_300.jpg": "base64"},
        },
    }

    result = normalize_page(raw, page_num=1, started_at=time.perf_counter())

    seals = [detail for detail in result.document_details if detail.type == "Seal"]
    assert len(seals) == 1
    assert isinstance(seals[0], SealDetail)
    assert seals[0].seal_id == "page-1-seal-1"
    assert "重复的版面印章文字" not in result.document_content
    assert result.document_content.count("[印章1]") == 1
    assert len(result.content_references) == 1


def test_multiple_seals_keep_result_pairing_and_use_visual_numbering():
    raw = {
        "prunedResult": {
            "width": 1000,
            "height": 1200,
            "parsing_res_list": [],
            "overall_ocr_res": {},
            "layout_det_res": {
                "boxes": [
                    {"label": "seal", "coordinate": [500, 600, 700, 800]},
                    {"label": "seal", "coordinate": [100, 100, 300, 300]},
                ]
            },
            "seal_res_list": [
                {
                    "rec_texts": ["下方印章"],
                    "rec_scores": [0.9],
                    "rec_polys": [[[10, 10], [50, 10], [50, 50], [10, 50]]],
                },
                {
                    "rec_texts": ["上方印章"],
                    "rec_scores": [0.95],
                    "rec_polys": [[[20, 20], [60, 20], [60, 60], [20, 60]]],
                },
            ],
        },
        "markdown": {
            "images": {
                "imgs/img_in_seal_box_500_600_700_800.jpg": "first",
                "imgs/img_in_seal_box_100_100_300_300.jpg": "second",
            }
        },
    }

    result = normalize_page(raw, page_num=1, started_at=time.perf_counter())

    seals = [detail for detail in result.document_details if isinstance(detail, SealDetail)]
    assert [seal.seal_id for seal in seals] == ["page-1-seal-1", "page-1-seal-2"]
    assert [seal.texts[0].text for seal in seals] == ["上方印章", "下方印章"]
    assert seals[0].texts[0].layout_bbox == [120, 120, 160, 160]
    assert seals[1].texts[0].layout_bbox == [510, 610, 550, 650]
    assert [ref.target_id for ref in result.content_references] == [
        "page-1-seal-1",
        "page-1-seal-2",
    ]


def test_layout_region_and_rec_boxes_are_used_when_markdown_crop_is_absent():
    raw = {
        "prunedResult": {
            "width": 500,
            "height": 800,
            "layout_det_res": {
                "boxes": [
                    {
                        "label": "seal",
                        "coordinate": [20.9, 30.8, 120.7, 130.6],
                    }
                ]
            },
            "seal_res_list": [
                {
                    "rec_texts": ["测试章"],
                    "rec_scores": [0.88],
                    "rec_polys": [],
                    "rec_boxes": [[1, 2, 10, 20]],
                }
            ],
        },
        "markdown": {},
    }

    result = normalize_page(raw, page_num=1, started_at=time.perf_counter())

    seal = result.document_details[-1]
    assert isinstance(seal, SealDetail)
    assert seal.seal_region_bbox == [20, 30, 120, 130]
    assert seal.texts[0].layout_bbox == [21, 32, 30, 50]


def test_unmatched_seal_regions_do_not_expose_local_coordinates_as_page_coordinates():
    raw = {
        "prunedResult": {
            "width": 500,
            "height": 800,
            "layout_det_res": {"boxes": [{"label": "seal", "coordinate": [20, 30, 120, 130]}]},
            "seal_res_list": [
                {
                    "rec_texts": ["印章一"],
                    "rec_scores": [0.9],
                    "rec_boxes": [[1, 2, 10, 20]],
                },
                {
                    "rec_texts": ["印章二"],
                    "rec_scores": [0.9],
                    "rec_boxes": [[5, 6, 15, 25]],
                },
            ],
        },
        "markdown": {},
    }

    result = normalize_page(raw, page_num=1, started_at=time.perf_counter())

    seals = [detail for detail in result.document_details if isinstance(detail, SealDetail)]
    assert len(seals) == 2
    assert all(not seal.seal_region_bbox for seal in seals)
    assert all(not seal.layout_bbox for seal in seals)
    assert all(not seal.texts[0].position for seal in seals)
    assert all(not seal.texts[0].layout_bbox for seal in seals)


def test_explicit_crop_bbox_has_per_seal_priority_over_complete_markdown_regions():
    raw = {
        "prunedResult": {
            "width": 1000,
            "height": 1200,
            "layout_det_res": {
                "boxes": [
                    {"label": "seal", "coordinate": [500, 600, 700, 800]},
                    {"label": "seal", "coordinate": [100, 100, 300, 300]},
                ]
            },
            "seal_res_list": [
                {
                    "crop_bbox": [700, 700, 900, 900],
                    "rec_texts": ["explicit seal"],
                    "rec_scores": [0.9],
                    "rec_polys": [[[10, 10], [50, 10], [50, 50], [10, 50]]],
                },
                {
                    "rec_texts": ["markdown seal"],
                    "rec_scores": [0.95],
                    "rec_polys": [[[20, 20], [60, 20], [60, 60], [20, 60]]],
                },
            ],
        },
        "markdown": {
            "images": {
                "imgs/img_in_seal_box_500_600_700_800.jpg": "first",
                "imgs/img_in_seal_box_100_100_300_300.jpg": "second",
            }
        },
    }

    result = normalize_page(raw, page_num=1, started_at=time.perf_counter())

    seals = [detail for detail in result.document_details if isinstance(detail, SealDetail)]
    assert [seal.texts[0].text for seal in seals] == ["markdown seal", "explicit seal"]
    assert seals[0].seal_region_bbox == [100, 100, 300, 300]
    assert seals[0].texts[0].layout_bbox == [120, 120, 160, 160]
    assert seals[1].seal_region_bbox == [700, 700, 900, 900]
    assert seals[1].texts[0].layout_bbox == [710, 710, 750, 750]


def test_layout_seal_without_ocr_becomes_structured_seal_detail():
    raw = {
        "prunedResult": {
            "width": 1191,
            "height": 1684,
            "parsing_res_list": [
                {
                    "block_label": "seal",
                    "block_content": "块级降级文本",
                    "block_bbox": [592, 0, 861, 222],
                    "block_order": 0,
                }
            ],
            "layout_det_res": {
                "boxes": [
                    {
                        "label": "seal",
                        "score": 0.9355565309524536,
                        "coordinate": [592, 0, 861, 222],
                    }
                ]
            },
        },
        "markdown": {"text": ""},
    }

    result = normalize_page(raw, page_num=1, started_at=time.perf_counter())

    assert len(result.document_details) == 1
    seal = result.document_details[0]
    assert isinstance(seal, SealDetail)
    assert seal.seal_id == "page-1-seal-1"
    assert seal.reference_token == "[印章1]"
    assert seal.layout_score == pytest.approx(0.9355565309524536)
    assert seal.layout_bbox == [592, 0, 861, 222]
    assert seal.seal_region_bbox == [592, 0, 861, 222]
    assert seal.position[0].points[2].model_dump() == {"x": 861, "y": 222}
    assert seal.layout_fallback_text == "块级降级文本"
    assert seal.text == "[印章1]"
    assert seal.texts == []
    assert result.document_content == "[印章1]"
    assert result.content_references[0].target_id == seal.seal_id


def test_page_result_rejects_unstructured_seal_detail():
    detail = DocumentDetail(
        type="Seal",
        text="不完整印章",
        layout_label="seal",
        layout_mapped_type="Seal",
        layout_order=0,
        layout_reading_index=0,
        layout_bbox=[10, 20, 30, 40],
    )

    with pytest.raises(ValidationError, match="必须使用 SealDetail"):
        PageResult(
            page_num=1,
            document_content="不完整印章",
            image_width=100,
            image_height=100,
            document_details=[detail],
            parse_time=0.1,
        )

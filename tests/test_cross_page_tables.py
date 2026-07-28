import json

import pytest

from pdf_parser.cross_page_tables import (
    detect_cross_page_tables,
    detect_cross_page_tables_file,
    table_column_count,
)


def _table(text: str, bbox: list[int]) -> dict:
    return {"type": "Table", "text": text, "layout_bbox": bbox}


def _page(page_num: int, details: list[dict]) -> dict:
    return {"page_num": page_num, "document_details": details}


def _payload(*pages: dict) -> dict:
    return {"data": {"doc_recognize_result": list(pages)}}


def test_table_column_count_expands_colspan():
    html = (
        "<table><tr><td>A</td><td colspan='2'>B</td></tr>"
        "<tr><td>C</td><td>D</td><td>E</td></tr></table>"
    )

    assert table_column_count(html) == 3


def test_detects_page_top_table_with_same_columns_as_previous_last_table():
    three_columns = "<table><tr><td>A</td><td colspan='2'>B</td></tr></table>"
    payload = _payload(
        _page(
            1,
            [
                _table("<table><tr><td>old</td></tr></table>", [10, 100, 900, 200]),
                _table(three_columns, [10, 500, 900, 1000]),
            ],
        ),
        _page(
            2,
            [
                _table(three_columns, [10, 20, 900, 500]),
                {"type": "Text", "text": "表格后的正文", "layout_bbox": [10, 600, 500, 650]},
            ],
        ),
    )

    candidates = detect_cross_page_tables(payload)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.previous_page_num == 1
    assert candidate.previous_detail_index == 1
    assert candidate.current_page_num == 2
    assert candidate.current_detail_index == 0
    assert candidate.column_count == 3
    assert candidate.previous_layout_bbox == [10, 500, 900, 1000]
    assert candidate.current_layout_bbox == [10, 20, 900, 500]


@pytest.mark.parametrize(
    "current_details",
    [
        [
            {"type": "Text", "text": "页眉", "layout_bbox": [10, 0, 200, 20]},
            _table("<table><tr><td>A</td><td>B</td></tr></table>", [10, 30, 900, 500]),
        ],
        [_table("<table><tr><td>A</td></tr></table>", [10, 0, 900, 500])],
    ],
)
def test_rejects_element_above_or_different_column_count(current_details):
    previous = _page(
        1,
        [_table("<table><tr><td>A</td><td>B</td></tr></table>", [10, 300, 900, 800])],
    )

    assert detect_cross_page_tables(_payload(previous, _page(2, current_details))) == []


def test_requires_immediately_preceding_page():
    html = "<table><tr><td>A</td><td>B</td></tr></table>"
    payload = _payload(
        _page(1, [_table(html, [10, 300, 900, 800])]),
        _page(3, [_table(html, [10, 0, 900, 500])]),
    )

    assert detect_cross_page_tables(payload) == []


def test_reads_candidates_from_json_file(tmp_path):
    html = "<table><tr><td>A</td><td>B</td></tr></table>"
    source = tmp_path / "result.json"
    source.write_text(
        json.dumps(
            _payload(
                _page(1, [_table(html, [10, 300, 900, 800])]),
                _page(2, [_table(html, [10, 0, 900, 500])]),
            )
        ),
        encoding="utf-8",
    )

    candidates = detect_cross_page_tables_file(source)

    assert len(candidates) == 1


def test_rejects_json_without_page_results():
    with pytest.raises(ValueError, match="doc_recognize_result"):
        detect_cross_page_tables({})

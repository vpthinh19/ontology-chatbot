import json

import pytest

from ontchatbot.runtime.render import render_rows


def _payload(rows):
    return json.loads(render_rows(rows))


def test_renders_empty_result_as_an_explicit_status() -> None:
    payload = _payload([])

    assert payload == {
        "trang_thai": "khong_co_thong_tin",
        "huong_dan": (
            "Có thể tra lại một lần với cách gọi ngắn khác; nếu vẫn không có "
            "thì dừng."
        ),
        "du_lieu": [],
        "nguon": [],
    }


def test_renders_rows_as_json_records() -> None:
    payload = _payload([{"answer": "Phòng Công tác Sinh viên"}])

    assert payload["trang_thai"] == "co_du_lieu"
    assert payload["du_lieu"] == [{"answer": "Phòng Công tác Sinh viên"}]


def test_keeps_all_distinct_rows_and_collapses_identical_ones() -> None:
    payload = _payload([{"answer": "A"}, {"answer": "B"}, {"answer": "A"}])

    assert payload["du_lieu"] == [{"answer": "A"}, {"answer": "B"}]


def test_keeps_multiple_columns_together_in_each_record() -> None:
    payload = _payload(
        [{"document": "Đơn bảo lưu", "url": "https://example.com"}]
    )

    assert payload["du_lieu"] == [
        {"document": "Đơn bảo lưu", "url": "https://example.com"}
    ]


def test_deduplicates_citations_and_links_without_losing_row_pairing() -> None:
    rows = [
        {
            "thuoctinh": "bước",
            "giatri": "Viết đơn",
            "nguon": "Điều 24",
            "duongdan": "https://example.com/quy-che",
        },
        {
            "thuoctinh": "bước",
            "giatri": "Nộp đơn",
            "nguon": "Điều 24",
            "duongdan": "https://example.com/quy-che",
        },
    ]

    payload = _payload(rows)

    # Trích dẫn xuất hiện đúng một lần, và quan hệ dữ kiện - nguồn nằm ở cấu
    # trúc chứ không ở một mã tham chiếu mà mô hình có thể in nhầm ra màn hình.
    assert payload["nguon"] == [
        {
            "trich_dan": "Điều 24",
            "duong_dan": "https://example.com/quy-che",
            "du_lieu": [
                {"thuoc_tinh": "bước", "gia_tri": "Viết đơn"},
                {"thuoc_tinh": "bước", "gia_tri": "Nộp đơn"},
            ],
        }
    ]
    assert "ma_nguon" not in json.dumps(payload, ensure_ascii=False)


def test_a_row_without_a_source_does_not_get_a_source_reference() -> None:
    payload = _payload(
        [
            {
                "thuoctinh": "tên gọi",
                "giatri": "Ngành đào tạo",
                "nguon": None,
                "duongdan": None,
            }
        ]
    )

    assert payload["du_lieu_khong_ro_nguon"] == [
        {"thuoc_tinh": "tên gọi", "gia_tri": "Ngành đào tạo"}
    ]
    assert payload.get("nguon") == []
    assert payload["nguon"] == []


def test_instruction_precedes_data_and_says_missing_detail_is_final() -> None:
    rendered = render_rows([{"answer": "A"}])
    payload = json.loads(rendered)

    assert rendered.index('"huong_dan"') < rendered.index('"du_lieu"')
    assert "Đọc hết" in payload["huong_dan"]
    assert "không tra lại cùng chủ đề" in payload["huong_dan"]


def test_rejects_inconsistent_columns() -> None:
    with pytest.raises(ValueError, match="same columns"):
        render_rows([{"answer": "A"}, {"value": "B"}])


def test_preserves_json_primitive_types() -> None:
    payload = _payload(
        [{"sốtiền": 7_200_000, "tốithiểu": 20.0, "đạt": True, "ghi_chú": None}]
    )

    assert payload["du_lieu"] == [
        {"sốtiền": 7_200_000, "tốithiểu": 20.0, "đạt": True, "ghi_chú": None}
    ]

"""Tổng hợp điểm lượt đo lại, đặt cạnh kết quả của bộ niêm phong (chỉ đọc ``../heldout``).

Chỉ số giữ đúng định nghĩa của báo cáo:
- tỷ lệ đạt: câu trả lời được chấm Đúng hoặc Từ chối đúng;
- tỷ lệ đủ thông tin: đạt, và sinh viên thật sự nhận đủ thông tin (câu không có đáp án trong văn bản, câu ngoài
  học vụ, hoặc câu có đáp án mà ontology có dữ liệu).

Thêm phần đo dòng đánh dấu mô hình viết: so với việc câu trả lời có thật sự nói thiếu thông tin hay không
(``noi_thieu`` do người chấm ghi), đặt cạnh cách dò cụm từ cũ trên cùng câu trả lời.

    uv run python resources/end-to-end/rerun-2026-09/score.py
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

from ontchatbot.runtime.chatlog import MISSING_PHRASES

HERE = Path(__file__).parent
SEALED = HERE.parent / "heldout"
PASS = {"Đúng", "Từ chối đúng"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def group(question: dict) -> str:
    if question["loai"] == "ngoai_hoc_vu":
        return "ngoài học vụ"
    if question["hanh_vi_dung"] == "noi_khong_co_thong_tin":
        return "không có trong dữ liệu"
    if question["ontology"] == "mot_phan":
        return "có một phần"
    return "có đáp án"


def full_info(question: dict, passed: bool) -> bool:
    return passed and (question["loai"] != "co_dap_an" or question["ontology"] == "co")


def main() -> None:
    questions = {q["id"]: q for q in load(HERE / "questions.json")}
    results = {r["id"]: r for r in load(HERE / "results-1.json")}
    grades = {g["id"]: g for g in load(HERE / "grades.json")}
    total = len(grades)

    passed = sum(g["dat"] for g in grades.values())
    full = sum(full_info(questions[i], g["dat"]) for i, g in grades.items())
    print(f"Lượt đo lại ({total} câu): đạt {passed}/{total} ({passed / total:.1%}), "
          f"đủ thông tin {full}/{total} ({full / total:.1%})")
    print("Mức:", dict(Counter(g["muc"] for g in grades.values())))
    print("Trích dẫn:", dict(Counter(g["trich_dan"] for g in grades.values() if g.get("trich_dan"))))
    for name in ("có đáp án", "có một phần", "không có trong dữ liệu", "ngoài học vụ"):
        ids = [i for i in grades if group(questions[i]) == name]
        ok = sum(grades[i]["dat"] for i in ids)
        print(f"  {name}: đạt {ok}/{len(ids)}")

    sealed = load(SEALED / "grades.json")
    for luot in sorted({g["luot"] for g in sealed}):
        rows = [g for g in sealed if g["luot"] == luot]
        ok = sum(g["dat"] for g in rows)
        fi = sum(full_info(questions[g["id"]], g["dat"]) for g in rows)
        print(f"Bộ niêm phong lượt {luot}: đạt {ok}/{len(rows)} ({ok / len(rows):.1%}), "
              f"đủ thông tin {fi}/{len(rows)} ({fi / len(rows):.1%})")
    changed = [(i, sorted({s["muc"] for s in sealed if s["id"] == i}), g["muc"]) for i, g in grades.items()
               if g["muc"] not in {s["muc"] for s in sealed if s["id"] == i}]
    print("Câu có mức không trùng lượt niêm phong nào (mức cũ → mới):")
    for question, before, now in changed:
        print(f"  {question}: {', '.join(before)} → {now}")

    said = {i for i, g in grades.items() if g.get("noi_thieu")}
    marked = {i for i, r in results.items() if "missing" in r.get("danh_dau", [])}
    phrased = {i for i, r in results.items() if any(p in r["tra_loi"].casefold() for p in MISSING_PHRASES)}
    print(f"Câu trả lời nói thiếu thông tin: {len(said)}")
    for name, found in (("dòng đánh dấu", marked), ("dò cụm từ cũ", phrased)):
        print(f"  {name}: bắt {len(found & said)}/{len(said)}, gắn thừa {len(found - said)} "
              f"{sorted(found - said)}, bỏ sót {sorted(said - found)}")
    outside = {i for i, q in questions.items() if q["loai"] == "ngoai_hoc_vu"}
    marked_out = {i for i, r in results.items() if "out_of_scope" in r.get("danh_dau", [])}
    print(f"  đánh dấu ngoài phạm vi: đúng {len(marked_out & outside)}/{len(outside)}, "
          f"thừa {sorted(marked_out - outside)}")

    seconds = sorted(r["giay"] for r in results.values())
    print(f"Thời gian mỗi câu: trung vị {statistics.median(seconds):.1f} s, "
          f"p95 {seconds[int(0.95 * (len(seconds) - 1))]:.1f} s, lâu nhất {seconds[-1]:.1f} s")


if __name__ == "__main__":
    main()

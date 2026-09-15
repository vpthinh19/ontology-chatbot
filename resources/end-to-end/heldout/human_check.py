"""Bốc mẫu câu trả lời cho nhóm chấm lại: phiếu Markdown, danh sách mẫu và dữ liệu cho trang chấm.

Mẫu ngẫu nhiên với seed cố định, lấy trên mọi câu trả lời của mọi lượt, rồi xếp theo mã câu và lượt.
Phiếu không chứa điểm của mô hình chấm.

    python resources/end-to-end/heldout/human_check.py --bo-de resources/end-to-end/heldout/v2
    python resources/end-to-end/heldout/human_check.py --bo-de <thư mục> --ra <thư mục khác> --du-lieu-trang <tệp>
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
SEED = 2026
TEN = {"tra_loi": "trả lời", "tra_loi_phan_co_va_noi_phan_thieu": "trả lời phần có, nói phần thiếu",
       "noi_khong_co_thong_tin": "nói không có thông tin", "tu_choi_ngoai_pham_vi": "từ chối (ngoài phạm vi)"}
# Người chấm đọc đáp án gốc lấy từ văn bản; dòng này nhắc rằng hành vi đúng đi theo dữ liệu chatbot có.
GHI_ONTOLOGY = {
    "khong": "ontology không có dữ liệu cho câu này; đáp án gốc lấy từ văn bản, chatbot đúng khi nói không có thông tin",
    "mot_phan": "ontology chỉ có một phần đáp án gốc (xem ghi chú biên tập); chatbot đúng khi trả lời phần có "
                "và nói rõ phần thiếu",
}


def can_cu(q: dict) -> str:
    return ", ".join(x for x in (q["tep"], q["vi_tri"]) if x)


def ghi_ontology(q: dict) -> str:
    if q["ontology"] == "khong" and q["loai"] != "co_dap_an":
        return ""  # đáp án gốc đã là "văn bản không quy định", không cần nhắc thêm
    return GHI_ONTOLOGY.get(q["ontology"], "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bo-de", type=Path, default=HERE, help="thư mục chứa questions.json và results-*.json")
    parser.add_argument("--ra", type=Path, help="thư mục ghi phiếu và danh sách mẫu; mặc định là --bo-de")
    parser.add_argument("--so-cau", type=int, default=25)
    parser.add_argument("--du-lieu-trang", type=Path, help="ghi thêm dữ liệu cho trang chấm vào tệp này")
    args = parser.parse_args()
    ra = args.ra or args.bo_de

    cau_hoi = {q["id"]: q for q in json.loads((args.bo_de / "questions.json").read_text(encoding="utf-8"))}
    tra_loi = {}
    for tep in sorted(args.bo_de.glob("results-*.json")):
        luot = int(tep.stem.removeprefix("results-"))
        for r in json.loads(tep.read_text(encoding="utf-8")):
            tra_loi[(r["id"], luot)] = r["tra_loi"]
    so_luot = len({luot for _, luot in tra_loi})
    mau = sorted(random.Random(SEED).sample(sorted(tra_loi), args.so_cau))

    md = ["# Mẫu chấm lại của nhóm", "",
          f"{len(mau)} câu trả lời bốc ngẫu nhiên (seed {SEED}) từ {len(tra_loi)} câu trả lời của {so_luot} lượt chạy.",
          "Chấm theo `rubric.md`, **không mở `grades.json` trước khi chấm xong**. Điền cột Mức (Đúng, Đúng một "
          "phần, Sai, Từ chối nhầm, Từ chối đúng, Bịa, Trả lời ngoài phạm vi) và cột Trích dẫn (dung, sai, "
          "khong_co; bỏ trống nếu không chấm).", ""]
    trang = []
    for n, (id_, luot) in enumerate(mau, start=1):
        q = cau_hoi[id_]
        md += [f"## {n}. {id_} · lượt {luot}", "",
               f"- **Câu hỏi:** {q['cau_hoi']}",
               f"- **Hành vi đúng:** {TEN[q['hanh_vi_dung']]}",
               f"- **Đáp án gốc:** {' · '.join(q['y_chinh'])}" + (f" ({can_cu(q)})" if can_cu(q) else "")]
        if q["bien_tap"]:
            md.append(f"- **Ghi chú biên tập:** {q['bien_tap']}")
        if ghi_ontology(q):
            md.append(f"- **Dữ liệu:** {ghi_ontology(q)}")
        van_ban = tra_loi[(id_, luot)] or "(không có câu trả lời)"
        md += ["", "**Câu trả lời của chatbot:**", ""]
        md += [f"> {dong}" for dong in van_ban.splitlines()]
        md += ["", "| Mức | Trích dẫn | Ghi chú |", "|---|---|---|", "|  |  |  |", ""]
        trang.append({"n": n, "id": id_, "luot": luot, "hv": q["hanh_vi_dung"], "hoi": q["cau_hoi"],
                      "goc": q["y_chinh"], "can_cu": can_cu(q), "bt": q["bien_tap"], "tl": van_ban,
                      "ont": q["ontology"], "loai": q["loai"]})

    ra.mkdir(parents=True, exist_ok=True)
    (ra / "human-check-sample.json").write_text(
        json.dumps([{"id": i, "luot": l} for i, l in mau], ensure_ascii=False, indent=1), encoding="utf-8")
    (ra / "human-check.md").write_text("\n".join(md), encoding="utf-8")
    if args.du_lieu_trang:
        args.du_lieu_trang.write_text(json.dumps(trang, ensure_ascii=False), encoding="utf-8")
    print(f"{len(mau)} câu trả lời → {ra / 'human-check.md'}")


if __name__ == "__main__":
    main()

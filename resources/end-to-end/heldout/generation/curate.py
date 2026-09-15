"""Lọc ba đầu ra của Codex thành bộ đề: bỏ trùng, sửa đáp án gốc, gắn mức dữ liệu ontology và hành vi đúng.

Mọi quyết định nằm trong bảng QUYET_DINH để xem lại được. Ghi ../questions.json và ../questions.md.

    python resources/end-to-end/heldout/generation/curate.py
"""
import collections
import json
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
ROOT = Path(__file__).resolve().parents[4]
SOURCES = ROOT / "references"

# ontology: co | mot_phan | khong ; None với câu ngoài học vụ. "bo" = bỏ câu.
QUYET_DINH = {
    "terra": {0: "co", 1: "co", 2: "khong", 3: "co", 4: "co", 5: "mot_phan", 6: "co", 7: "co", 8: "co",
              9: "co", 10: "khong", 11: "khong", 12: "khong", 13: "mot_phan", 14: "co", 15: "khong", 16: "co",
              17: "co", 18: "co", 19: "co", 20: "bo", 21: "co", 22: "co", 23: "khong", 24: "co", 25: "co",
              26: "khong", 27: "co", 28: "co", 29: "khong", 30: "co", 31: "co", 32: "khong", 33: None, 34: None},
    "sol": {0: "co", 1: "co", 2: "co", 3: "co", 4: "co", 5: "co", 6: "co", 7: "mot_phan", 8: "co", 9: "khong",
            10: "khong", 11: "bo", 12: "bo", 13: "co", 14: "co", 15: "khong", 16: "co", 17: "bo", 18: "co",
            19: "co", 20: "khong", 21: "co", 22: "bo", 23: "khong", 24: "co", 25: "co", 26: "bo", 27: "khong",
            28: "co", 29: "khong", 30: "co", 31: "khong", 32: "khong", 33: "bo", 34: "bo"},
    "luna": {0: "bo", 1: "khong", 2: "bo", 3: "khong", 4: "bo", 5: "bo", 6: "mot_phan", 7: "bo", 8: "co",
             9: "bo", 10: "bo", 11: "bo", 12: "bo", 13: "bo", 14: "co", 15: "bo", 16: "bo", 17: "co", 18: "bo",
             19: "bo", 20: "bo", 21: "co", 22: "bo", 23: "khong", 24: "bo", 25: "khong", 26: "bo", 27: "co",
             28: "bo", 29: "khong", 30: "co", 31: "mot_phan", 32: "khong", 33: None, 34: None},
}

LY_DO_BO = {
    ("terra", 20): "đáp án gốc 'không có' sai: Phụ lục 2 QĐ 1052 có liệt kê một phần các chương trình đặc biệt",
    ("sol", 11): "học phí thạc sĩ: ngoài đối tượng sinh viên đại học", ("sol", 12): "học phí tiến sĩ: ngoài đối tượng",
    ("sol", 17): "gần trùng luna#17 (TOEIC chương trình đặc biệt)", ("sol", 22): "gần trùng luna#21 (chuyển trường)",
    ("sol", 26): "đáp án lẫn có và không (ontology có nơi nộp phúc khảo, không có thời hạn)",
    ("sol", 33): "ngoài học vụ nhưng sát chuyện học tập, dễ tranh cãi khi chấm", ("sol", 34): "phép tính đơn giản, dễ tranh cãi khi chấm",
    ("luna", 0): "trùng sol#0", ("luna", 2): "gần trùng sol#1", ("luna", 4): "trùng terra#4 (tự hủy học phần)",
    ("luna", 5): "đáp án lẫn có và không (điểm chuyên cần khi rút học phần)", ("luna", 7): "gần trùng sol#6, sol#7",
    ("luna", 9): "gần trùng sol#9 (hồ sơ liên thông)", ("luna", 10): "câu còn chữ 'ngành X'",
    ("luna", 11): "trùng terra#11 (học phí kiểm định)", ("luna", 12): "sinh viên không hỏi (đối chiếu sao kê ngân hàng)",
    ("luna", 13): "trùng sol#13", ("luna", 15): "trùng sol#15", ("luna", 16): "trùng sol#18", ("luna", 18): "trùng sol#16",
    ("luna", 19): "gần trùng terra#11; trích dẫn lệch ký hiệu", ("luna", 20): "trùng sol#20", ("luna", 22): "trùng sol#21",
    ("luna", 24): "trùng sol#24", ("luna", 26): "đáp án lẫn có và không (phúc khảo)", ("luna", 28): "gần trùng sol#28 (MOS)",
}

K2_753 = ("Việc rút bớt học phần trong khối lượng học tập đã đăng ký của SV chỉ được chấp nhận tối đa trong "
          "tuần thứ hai học kỳ chính, tuần thứ nhất học kỳ phụ")
K2B_753 = ("Ngoài thời hạn trên, học phần vẫn được giữ nguyên như đã đăng ký và nếu SV không đi học được xem "
           "như tự ý bỏ học và phải nhận điểm 0 (không)")
K3_753 = ("Sinh viên tự thực hiện việc rút bớt học phần đã đăng ký trên Hệ thống quản lý đào tạo từ tài khoản cá "
          "nhân hoặc trực tiếp nộp đơn đề nghị rút bớt học phần tại Đơn vị quản lý đào tạo (Mẫu số 2 - Phiếu "
          "đăng ký/điều chỉnh học phần)")
GHI_753 = "Codex không được đọc QĐ 753; QĐ 1052 chỉ bãi bỏ quy định trái với nó nên Điều 10 QĐ 753 còn hiệu lực."

SUA = {
    ("terra", 4): dict(loai="co_dap_an", tep="Qd753.md", vi_tri="khoản 2, 3 Điều 10", trich_nguyen_van=[K3_753, K2_753],
                       y_chinh=["Được: sinh viên tự rút bớt (hủy) học phần đã đăng ký trên Hệ thống quản lý đào tạo từ tài khoản cá nhân, hoặc nộp đơn tại Đơn vị quản lý đào tạo",
                                "Chỉ được chấp nhận tối đa trong tuần thứ hai học kỳ chính, tuần thứ nhất học kỳ phụ"],
                       ghi_chu=GHI_753),
    ("terra", 5): dict(loai="co_dap_an", tep="Qd753.md", vi_tri="khoản 2 Điều 10", trich_nguyen_van=[K2_753, K2B_753],
                       y_chinh=["Rút bớt học phần chỉ được chấp nhận tối đa trong tuần thứ hai học kỳ chính (tuần thứ nhất học kỳ phụ); giữa kỳ đã quá hạn, học phần vẫn giữ nguyên như đã đăng ký",
                                "Văn bản không quy định việc hoàn học phí khi rút bớt học phần"],
                       ghi_chu=GHI_753 + " Vế hoàn tiền không có trong văn bản."),
    ("sol", 4): dict(loai="co_dap_an", tep="Qd753.md", vi_tri="khoản 2 Điều 10", trich_nguyen_van=[K2_753, K2B_753],
                     y_chinh=["Hạn rút bớt (hủy) là tối đa trong tuần thứ hai học kỳ chính, tuần thứ nhất học kỳ phụ; văn bản không nêu ngày cụ thể",
                              "Quá hạn, học phần giữ nguyên như đã đăng ký; không đi học thì nhận điểm 0"],
                     ghi_chu=GHI_753),
    ("sol", 5): dict(loai="co_dap_an", tep="Qd753.md", vi_tri="khoản 3 Điều 10", trich_nguyen_van=[K3_753],
                     y_chinh=["Nộp đơn đề nghị rút bớt học phần tại Đơn vị quản lý đào tạo, theo Mẫu số 2 - Phiếu đăng ký/điều chỉnh học phần",
                              "Hoặc tự rút bớt trên Hệ thống quản lý đào tạo từ tài khoản cá nhân"],
                     ghi_chu=GHI_753 + " Đơn vị quản lý đào tạo tương ứng Phòng Đào tạo Đại học."),
    ("terra", 8): dict(cau_hoi="Em đang học ở trường, muốn học thêm văn bằng thứ hai song song với ngành chính thì đăng ký lúc nào và dùng mẫu nào?",
                       ghi_chu="Sửa câu hỏi: 'văn bằng thứ hai' vốn có hai nghĩa (học cùng lúc hai chương trình / liên thông văn bằng 2)."),
    ("terra", 18): dict(ghi_chu="Mức học bổng theo QĐ 317, áp dụng năm học 2024–2025."),
    ("terra", 30): dict(ghi_chu="Mức học bổng theo QĐ 317, áp dụng năm học 2024–2025."),
}

HANH_VI = {"co": "tra_loi", "mot_phan": "tra_loi_phan_co_va_noi_phan_thieu", "khong": "noi_khong_co_thong_tin",
           None: "tu_choi_ngoai_pham_vi"}
DAU = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ")


def norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[*_#>`|\\]", " ", unicodedata.normalize("NFC", text))).strip().lower()


src = {p.name: norm(p.read_text(encoding="utf-8")) for p in SOURCES.iterdir() if p.suffix in (".md", ".txt")}
bo_de, bo, loi_trich = [], [], []
for model in ("terra", "sol", "luna"):
    for i, it in enumerate(json.loads((HERE / f"out-{model}.json").read_text(encoding="utf-8"))["cau_hoi"]):
        quyet = QUYET_DINH[model][i]
        if quyet == "bo":
            bo.append((f"{model}#{i}", it["cau_hoi"], LY_DO_BO[(model, i)]))
            continue
        sua = SUA.get((model, i), {})
        item = {**it, **{k: v for k, v in sua.items() if k != "ghi_chu"}}
        if item["loai"] == "co_dap_an":
            text = src.get(item["tep"] or "", "")
            if not text or any(norm(q) not in text for q in item["trich_nguyen_van"]):
                loi_trich.append(f"{model}#{i}")
        loai_goc = it["loai"]
        hanh_vi = HANH_VI[quyet]
        if item["loai"] == "khong_co_trong_van_ban":
            hanh_vi = "noi_khong_co_thong_tin"
        bo_de.append({
            "id": f"Q{len(bo_de) + 1:03d}", "sinh_boi": f"gpt-5.6-{model}#{i}", "chu_de": item["chu_de"],
            "cau_hoi": item["cau_hoi"], "khong_dau": not (set(item["cau_hoi"].lower()) & DAU),
            "loai": item["loai"], "y_chinh": item["y_chinh"], "tep": item["tep"], "vi_tri": item["vi_tri"],
            "trich_nguyen_van": item["trich_nguyen_van"], "ontology": quyet, "hanh_vi_dung": hanh_vi,
            "ghi_chu_codex": it["ghi_chu"],
            "bien_tap": " ".join(x for x in [f"Sửa loại từ {loai_goc}." if loai_goc != item["loai"] else "",
                                            sua.get("ghi_chu", "")] if x),
        })

(HERE.parent / "questions.json").write_text(json.dumps(bo_de, ensure_ascii=False, indent=1), encoding="utf-8")

TEN = {"tra_loi": "trả lời", "tra_loi_phan_co_va_noi_phan_thieu": "trả lời phần có, nói phần thiếu",
       "noi_khong_co_thong_tin": "nói không có thông tin", "tu_choi_ngoai_pham_vi": "từ chối (ngoài phạm vi)"}
md = ["| ID | Chủ đề | Câu hỏi | Ý chính của đáp án gốc | Căn cứ | Ontology | Hành vi đúng |", "|---|---|---|---|---|---|---|"]
for q in bo_de:
    can_cu = f"{q['tep'] or ''} {q['vi_tri'] or ''}".strip()
    md.append(f"| {q['id']} | {q['chu_de']} | {q['cau_hoi']} | {' · '.join(q['y_chinh'])} | {can_cu} | {q['ontology'] or '—'} | {TEN[q['hanh_vi_dung']]} |")
md += ["", "## Câu đã bỏ", "", "| Nguồn | Câu hỏi | Lý do |", "|---|---|---|"]
md += [f"| {a} | {b} | {c} |" for a, b, c in bo]
(HERE.parent / "questions.md").write_text("\n".join(md) + "\n", encoding="utf-8")

print("giữ:", len(bo_de), "· bỏ:", len(bo), "· trích dẫn lỗi:", loi_trich or "không")
for field in ("chu_de", "loai", "ontology", "hanh_vi_dung", "khong_dau"):
    print(field, dict(collections.Counter(q[field] for q in bo_de)))

"""Lọc ba đầu ra của Codex thành bộ đề: bỏ trùng, sửa đáp án gốc, gắn mức dữ liệu ontology và hành vi đúng.

Mọi quyết định nằm trong các bảng QUYET_DINH, LY_DO_BO và SUA để xem lại được. Ghi ../questions.json và
../questions.md.

    python resources/end-to-end/heldout/generation/curate.py
"""
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
ROOT = Path(__file__).resolve().parents[4]
SOURCES = ROOT / "references"
MO_HINH = ("sol", "terra", "luna")

# ontology: "co" | "mot_phan" | "khong" ; None với câu ngoài học vụ ; "bo" = bỏ câu (ghi lý do ở LY_DO_BO).
QUYET_DINH: dict[str, dict[int, str | None]] = {
    'sol': {0: 'co', 1: 'co', 2: 'khong', 3: 'bo', 4: 'khong', 5: 'khong', 6: 'khong', 7: 'khong', 8: 'khong', 9: 'khong', 10: 'khong', 11: 'khong', 12: 'khong', 13: 'co', 14: 'co', 15: 'khong', 16: 'bo', 17: 'co', 18: 'co', 19: 'bo', 20: 'khong', 21: 'khong', 22: 'co', 23: 'khong', 24: 'co', 25: 'co', 26: 'bo', 27: 'khong', 28: 'khong', 29: 'khong', 30: 'co', 31: 'co', 32: 'khong', 33: None, 34: None},
    'terra': {0: 'bo', 1: 'co', 2: 'co', 3: 'co', 4: 'bo', 5: 'khong', 6: 'co', 7: 'bo', 8: 'mot_phan', 9: 'bo', 10: 'khong', 11: 'bo', 12: 'bo', 13: 'co', 14: 'co', 15: 'khong', 16: 'bo', 17: 'bo', 18: 'bo', 19: 'bo', 20: 'khong', 21: 'co', 22: 'co', 23: 'khong', 24: 'mot_phan', 25: 'co', 26: 'bo', 27: 'co', 28: 'khong', 29: 'khong', 30: 'bo', 31: 'khong', 32: 'khong', 33: None, 34: None},
    'luna': {0: 'bo', 1: 'co', 2: 'bo', 3: 'khong', 4: 'co', 5: 'bo', 6: 'bo', 7: 'co', 8: 'bo', 9: 'bo', 10: 'bo', 11: 'bo', 12: 'bo', 13: 'bo', 14: 'khong', 15: 'co', 16: 'khong', 17: 'co', 18: 'co', 19: 'bo', 20: 'co', 21: 'khong', 22: 'bo', 23: 'bo', 24: 'khong', 25: 'co', 26: 'co', 27: 'khong', 28: 'co', 29: 'bo', 30: 'bo', 31: 'bo', 32: 'bo', 33: 'bo', 34: 'bo', 35: 'bo'},
}
LY_DO_BO: dict[tuple[str, int], str] = {
    ('sol', 3): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (quá hạn rút học phần thì giữ nguyên, bỏ học nhận điểm 0)',
    ('sol', 16): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (học phí giáo dục tổng quát khối ngành III)',
    ('sol', 19): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (khối lượng đăng ký, khoản 3 Điều 9)',
    ('sol', 26): 'đáp án lẫn có và không: ontology có nơi nộp đơn phúc khảo',
    ('terra', 0): 'ontology chỉ có tên khái niệm học phần thay thế; dễ tranh cãi khi chấm',
    ('terra', 4): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (đăng ký khối lượng học tập là bắt buộc)',
    ('terra', 7): 'cùng chỗ văn bản và cùng góc hỏi với một câu hỏi thử dùng khi phát triển (hồ sơ liên thông, khoản 3 Điều 19 QĐ 626)',
    ('terra', 9): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (thời điểm đăng ký liên thông)',
    ('terra', 11): 'gần trùng sol#11 (học phí cơ sở và chuyên ngành của chương trình kiểm định)',
    ('terra', 12): 'gần trùng sol#12 (học phí ngành Ngôn ngữ Anh); trích nguyên văn lệch ký hiệu bảng',
    ('terra', 16): 'gần trùng sol#17 và luna#18 (bảng chuẩn tiếng Anh chương trình đặc biệt)',
    ('terra', 17): 'gần trùng luna#17 (Ngoại ngữ B2.1 là học phần bắt buộc)',
    ('terra', 18): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (dòng Bậc 4 của bảng quy đổi chương trình chuẩn)',
    ('terra', 19): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (quy đổi chứng chỉ ngoại ngữ quốc tế của chương trình đặc biệt)',
    ('terra', 26): 'dễ nhầm với thủ tục phúc khảo có trong ontology; dễ tranh cãi khi chấm',
    ('terra', 30): 'ontology chỉ ghi 05 tháng mỗi học kỳ, số tháng trong năm phải suy ra; dễ tranh cãi khi chấm',
    ('luna', 0): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (sĩ số lớp thực hành tại phòng máy tính)',
    ('luna', 2): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (không tính tín chỉ Giáo dục thể chất, Giáo dục Quốc phòng – An ninh)',
    ('luna', 5): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (hạn rút bớt học phần)',
    ('luna', 6): 'cùng ý với một câu hỏi thử dùng khi phát triển (hoàn tiền khi rút học phần)',
    ('luna', 8): 'gần một câu hỏi thử dùng khi phát triển (thời điểm đăng ký chương trình thứ hai); đáp án lẫn có và không',
    ('luna', 9): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (bảo lưu học phần tương đương khi học hai chương trình)',
    ('luna', 10): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (điều kiện xét tốt nghiệp chương trình thứ hai)',
    ('luna', 11): 'ontology có thủ tục chuyển ngành chung; dễ tranh cãi khi chấm',
    ('luna', 12): 'gần trùng sol#11',
    ('luna', 13): 'gần trùng sol#11',
    ('luna', 19): 'gần trùng sol#18 (bảng chuẩn ngoại ngữ khác của chương trình đặc biệt)',
    ('luna', 22): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (điều kiện nghỉ học tạm thời vì lý do cá nhân)',
    ('luna', 23): 'ontology có thủ tục chuyển sang vừa làm vừa học cho diện buộc thôi học; dễ tranh cãi khi chấm',
    ('luna', 29): 'gần một câu hỏi thử dùng khi phát triển (lễ tốt nghiệp, khoản 4 Điều 23)',
    ('luna', 30): 'cùng ý với một câu hỏi thử dùng khi phát triển (chứng chỉ tin học để tốt nghiệp)',
    ('luna', 31): 'trùng dữ kiện với một câu hỏi thử dùng khi phát triển hệ thống (mức học bổng loại giỏi của hai chương trình)',
    ('luna', 32): 'cùng góc hỏi với một câu hỏi thử dùng khi phát triển (xếp loại học bổng theo điểm trung bình và rèn luyện)',
    ('luna', 33): 'đáp án lẫn có và không: ontology có nơi công bố danh sách dự kiến',
    ('luna', 34): 'trùng một câu hỏi thử dùng khi phát triển',
    ('luna', 35): 'trùng một câu hỏi thử dùng khi phát triển',
}
# Sửa trường của câu gốc; "ghi_chu" là ghi chú biên tập, bắt buộc với câu mot_phan (nêu phần ontology thiếu).
SUA: dict[tuple[str, int], dict] = {
    ('terra', 27): {'trich_nguyen_van': ['Hạng tốt nghiệp được xác định theo điểm trung bình chung tích lũy của toàn khoá học theo các mức như sau:', '| 2 | 8,00 ÷ 8,99 | Giỏi |'], 'ghi_chu': 'Sửa trích nguyên văn cho khớp bảng trong văn bản.'},
    ('terra', 8): {'ghi_chu': 'Ontology có ý người học liên thông đăng ký học theo kế hoạch chung như sinh viên khác; không có ý được xem xét miễn học và bảo lưu các học phần tương ứng.'},
    ('terra', 24): {'ghi_chu': 'Ontology có quy định điểm học phần chấm theo thang 10 và làm tròn đến một chữ số thập phân; không có cách tính điểm học phần từ điểm thành phần và trọng số.'},
}

HANH_VI = {"co": "tra_loi", "mot_phan": "tra_loi_phan_co_va_noi_phan_thieu", "khong": "noi_khong_co_thong_tin",
           None: "tu_choi_ngoai_pham_vi"}
DAU = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*_#>`|\\]", " ", unicodedata.normalize("NFC", text))).strip().lower()


src = {p.name: norm(p.read_text(encoding="utf-8")) for p in SOURCES.iterdir() if p.suffix in (".md", ".txt")}
bo_de, bo, loi = [], [], []
for model in MO_HINH:
    for i, it in enumerate(json.loads((HERE / f"out-{model}.json").read_text(encoding="utf-8"))["cau_hoi"]):
        ma = f"{model}#{i}"
        if i not in QUYET_DINH[model]:
            loi.append(f"{ma}: chưa có quyết định")
            continue
        quyet = QUYET_DINH[model][i]
        if quyet == "bo":
            if (model, i) not in LY_DO_BO:
                loi.append(f"{ma}: bỏ mà không ghi lý do")
            bo.append((ma, it["cau_hoi"], LY_DO_BO.get((model, i), "")))
            continue
        sua = SUA.get((model, i), {})
        item = {**it, **{k: v for k, v in sua.items() if k != "ghi_chu"}}
        if item["loai"] == "co_dap_an":
            text = src.get(item["tep"] or "", "")
            if not text or not item["trich_nguyen_van"] or any(norm(q) not in text for q in item["trich_nguyen_van"]):
                loi.append(f"{ma}: trích nguyên văn không khớp văn bản")
        if quyet == "mot_phan" and not sua.get("ghi_chu"):
            loi.append(f"{ma}: ontology một phần mà không ghi phần thiếu")
        if (item["loai"] == "ngoai_hoc_vu") != (quyet is None):
            loi.append(f"{ma}: loại {item['loai']} không khớp mức ontology {quyet}")
        hanh_vi = "noi_khong_co_thong_tin" if item["loai"] == "khong_co_trong_van_ban" else HANH_VI[quyet]
        bo_de.append({
            "id": f"Q{len(bo_de) + 1:03d}", "sinh_boi": f"gpt-5.6-{model}#{i}", "chu_de": item["chu_de"],
            "cau_hoi": item["cau_hoi"], "khong_dau": not (set(item["cau_hoi"].lower()) & DAU),
            "loai": item["loai"], "y_chinh": item["y_chinh"], "tep": item["tep"], "vi_tri": item["vi_tri"],
            "trich_nguyen_van": item["trich_nguyen_van"], "ontology": quyet, "hanh_vi_dung": hanh_vi,
            "ghi_chu_codex": it["ghi_chu"],
            "bien_tap": " ".join(x for x in [f"Sửa loại từ {it['loai']}." if it["loai"] != item["loai"] else "",
                                            sua.get("ghi_chu", "")] if x),
        })

if loi:
    sys.exit("chưa ghi được bộ đề:\n  " + "\n  ".join(loi))

(HERE.parent / "questions.json").write_text(json.dumps(bo_de, ensure_ascii=False, indent=1), encoding="utf-8")

TEN = {"tra_loi": "trả lời", "tra_loi_phan_co_va_noi_phan_thieu": "trả lời phần có, nói phần thiếu",
       "noi_khong_co_thong_tin": "nói không có thông tin", "tu_choi_ngoai_pham_vi": "từ chối (ngoài phạm vi)"}
md = ["| ID | Chủ đề | Câu hỏi | Ý chính của đáp án gốc | Căn cứ | Ontology | Hành vi đúng |",
      "|---|---|---|---|---|---|---|"]
for q in bo_de:
    can_cu = f"{q['tep'] or ''} {q['vi_tri'] or ''}".strip()
    md.append(f"| {q['id']} | {q['chu_de']} | {q['cau_hoi']} | {' · '.join(q['y_chinh'])} | {can_cu} | "
              f"{q['ontology'] or '—'} | {TEN[q['hanh_vi_dung']]} |")
md += ["", "## Câu đã bỏ", "", "| Nguồn | Câu hỏi | Lý do |", "|---|---|---|"]
md += [f"| {a} | {b} | {c} |" for a, b, c in bo]
(HERE.parent / "questions.md").write_text("\n".join(md) + "\n", encoding="utf-8")

print("giữ:", len(bo_de), "· bỏ:", len(bo))
for field in ("chu_de", "loai", "ontology", "hanh_vi_dung", "khong_dau"):
    print(field, dict(collections.Counter(q[field] for q in bo_de)))

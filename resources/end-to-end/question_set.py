"""Dựng bộ câu hỏi cho phép đo đầu-cuối, lấy từ chính tập chấm."""
import json, random
from collections import defaultdict
from pathlib import Path

TEST = Path("artifacts/kq3/t5gemma2/benchmark-test.json")
OUT = Path(__file__).with_name("cau-hoi.json")

cases = json.loads(TEST.read_text())["cases"]
rng = random.Random(42)

in_domain = [c for c in cases if c["evaluation_group"] == "node_queries" and c["expected_nodes"]]
off_domain = [c for c in cases if c["evaluation_group"] == "out_of_domain"]

# Phân tầng theo phong cách để bộ đo không nghiêng về một cách hỏi.
by_reg = defaultdict(list)
for c in in_domain:
    by_reg[c["register"]].append(c)
picked = []
for reg in sorted(by_reg):
    rows = sorted(by_reg[reg], key=lambda c: c["id"])
    rng.shuffle(rows)
    picked += rows[:15]

off = sorted(off_domain, key=lambda c: c["id"])
rng.shuffle(off)
off = off[:15]

# Câu hỏi mà đồ thị KHÔNG trả lời được: chủ đề có trong đồ thị, nhưng quan hệ
# được hỏi thì không. Đây là chỗ mô hình dễ lấp bằng suy luận nhất.
khong_tra_loi_duoc = [
    "Ngành Công nghệ thông tin yêu cầu chuẩn tiếng Anh đầu ra là bao nhiêu?",
    "Học phí ngành Kế toán một năm là bao nhiêu tiền?",
    "Điểm chuẩn ngành Ngôn ngữ Anh năm nay là bao nhiêu?",
    "Trưởng phòng Đào tạo tên là gì?",
    "Ký túc xá một tháng bao nhiêu tiền một sinh viên?",
    "Số điện thoại của phòng Công tác sinh viên là số nào?",
    "Ngành Quản trị kinh doanh học bao nhiêu tín chỉ thì tốt nghiệp?",
    "Lịch thi học kỳ 1 năm nay bắt đầu ngày nào?",
    "Sinh viên ngành Kỹ thuật ô tô có được miễn học phần tiếng Anh không?",
    "Mức học bổng ngành Du lịch cao nhất là bao nhiêu?",
]

payload = {
    "trong_pham_vi": [
        {"id": c["id"], "cau_hoi": c["input"], "register": c["register"],
         "query_id": c["query_id"], "node_dung": c["expected_nodes"]}
        for c in picked
    ],
    "ngoai_pham_vi": [
        {"id": c["id"], "cau_hoi": c["input"], "register": c["register"]} for c in off
    ],
    "do_thi_khong_co": [
        {"id": f"gap-{i:03d}", "cau_hoi": q} for i, q in enumerate(khong_tra_loi_duoc, 1)
    ],
}
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
print("trong phạm vi", len(payload["trong_pham_vi"]))
print("ngoài phạm vi", len(payload["ngoai_pham_vi"]))
print("đồ thị không có", len(payload["do_thi_khong_co"]))

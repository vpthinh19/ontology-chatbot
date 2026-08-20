"""Chấm lại: nguồn hợp lệ gồm cả danh sách chủ đề trong khuôn nhắc hệ thống.

Khuôn nhắc liệt kê tên thủ tục, biểu mẫu, ngành và đơn vị đọc thẳng từ đồ thị.
Trợ lý nhắc lại những tên đó khi giới thiệu mình giúp được gì; đó là dữ kiện có
nguồn, không phải bịa. Phép chấm cũ chỉ so với kết quả công cụ nên đếm nhầm.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, "src")
from ontchatbot.runtime.agent import build_instructions

HERE = Path(__file__).parent
R = json.loads((HERE / "results.json").read_text())
KHUON = build_instructions()

sys.path.insert(0, str(HERE))
from run import khong_bam_du_lieu  # dùng lại đúng phép trích số/viết tắt

# Không có bản ghi dữ liệu công cụ trong tệp kết quả, nên chấm lại phần bịa đặt
# bằng chính danh sách cũ trừ đi những gì khuôn nhắc đã nói.
for r in R:
    r["bia_dat_cu"] = r["bia_dat"]
    r["bia_dat"] = [t for t in r["bia_dat"] if t not in KHUON]

(HERE / "results-rescored.json").write_text(json.dumps(R, ensure_ascii=False, indent=1))
con = [(r["id"], r["nhom"], r["bia_dat"]) for r in R if r["bia_dat"]]
print("sau khi trừ tên lấy từ khuôn nhắc, còn", len(con), "câu có số/viết tắt ngoài nguồn:")
for i, n, b in con:
    print("   ", i, n, b)

"""Tổng hợp phép đo đầu-cuối thành các con số đưa vào README."""
import json, statistics as st
from collections import Counter
from pathlib import Path

R = json.loads((Path(__file__).parent / "results.json").read_text())
trong = [r for r in R if r["nhom"] == "trong_pham_vi"]
ngoai = [r for r in R if r["nhom"] == "ngoai_pham_vi"]
gap = [r for r in R if r["nhom"] == "do_thi_khong_co"]

def pc(a, b): return f"{a}/{b} = {a/b*100:.1f}%"

print("=" * 62)
print("NHÓM 1 — CÂU HỌC VỤ TRẢ LỜI ĐƯỢC  (", len(trong), "câu )")
print("  gọi công cụ trước khi trả lời :", pc(sum(1 for r in trong if r["so_lan_goi"]), len(trong)))
print("  lấy về đúng mục cần           :", pc(sum(1 for r in trong if r["lay_dung_muc"]), len(trong)))
print("  không có số/tên ngoài dữ liệu :", pc(sum(1 for r in trong if not r["bia_dat"]), len(trong)))
ca_hai = sum(1 for r in trong if r["lay_dung_muc"] and not r["bia_dat"])
print("  ĐÚNG MỤC **VÀ** BÁM DỮ LIỆU    :", pc(ca_hai, len(trong)))
print("  số lần gọi công cụ / câu      :", f"{sum(r['so_lan_goi'] for r in trong)/len(trong):.2f}")

for ten, nhom in (("NHÓM 2 — CÂU ĐỒ THỊ KHÔNG TRẢ LỜI ĐƯỢC (lấy từ tập chấm)", ngoai),
                  ("NHÓM 3 — CÂU HỎI CHẠM KHOẢNG TRỐNG (viết tay)", gap)):
    print("=" * 62)
    print(ten, " (", len(nhom), "câu )")
    print("  nói rõ dữ liệu không có       :", pc(sum(1 for r in nhom if r["noi_la_thieu"]), len(nhom)))
    print("  không có số/tên ngoài dữ liệu :", pc(sum(1 for r in nhom if not r["bia_dat"]), len(nhom)))
    xau = [r for r in nhom if not r["noi_la_thieu"]]
    for r in xau:
        print(f"    ⚠ {r['id']}: {r['cau_hoi'][:70]}")

print("=" * 62)
print("THỜI GIAN PHẢN HỒI ĐẦU-CUỐI (giây, đo tuần tự, một câu một lượt)")
g = sorted(r["giay"] for r in R)
print(f"  trung vị {st.median(g):.1f} · p95 {g[int(len(g)*0.95)]:.1f} · dài nhất {g[-1]:.1f} · ngắn nhất {g[0]:.1f}")
gt = sorted(r["giay"] for r in trong)
print(f"  riêng câu có tra cứu: trung vị {st.median(gt):.1f} · p95 {gt[int(len(gt)*0.95)]:.1f}")
gn = sorted(r["giay"] for r in R if r["so_lan_goi"] == 0)
if gn:
    print(f"  riêng câu không tra cứu: trung vị {st.median(gn):.1f} ({len(gn)} câu)")

print("=" * 62)
print("BỊA ĐẶT — mọi số/viết tắt xuất hiện trong câu trả lời mà dữ liệu không nói")
bia = [(r["id"], r["nhom"], r["bia_dat"]) for r in R if r["bia_dat"]]
print(f"  {len(bia)}/{len(R)} câu trả lời có ít nhất một mục như vậy")
for i, n, b in bia:
    print("   ", i, n, b)

print("=" * 62)
print("SỐ TỪ KHOÁ MỖI LẦN GỌI")
c = Counter(len(r["tu_khoa"]) for r in R if r["so_lan_goi"])
print("  ", dict(sorted(c.items())))

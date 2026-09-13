"""Tổng hợp phép đo đầu-cuối thành các con số đưa vào README."""

import json
import statistics as st
from collections import Counter
from pathlib import Path

R = json.loads((Path(__file__).parent / "results.json").read_text(encoding="utf-8"))
trong = [r for r in R if r["nhom"] == "trong_pham_vi"]
do_duoc = [r for r in trong if r.get("lay_dung_muc") is not None]
ngoai = [r for r in R if r["nhom"] == "ngoai_pham_vi"]
gap = [r for r in R if r["nhom"] == "do_thi_khong_co"]


def pc(a, b):
    return f"{a}/{b} = {a / b * 100:.1f}%" if b else f"{a}/0"


def p95(values):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * 0.95))]


print("=" * 66)
print(f"NHÓM 1 — CÂU CÓ DỮ KIỆN ({len(trong)} câu; {len(do_duoc)} câu chấm được mục đích)")
print("  gọi công cụ trước khi trả lời :", pc(sum(1 for r in trong if r["so_lan_goi"]), len(trong)))
print("  lấy về đúng mục cần           :", pc(sum(1 for r in do_duoc if r["lay_dung_muc"]), len(do_duoc)))
print("  không có số/tên ngoài dữ liệu :", pc(sum(1 for r in trong if not r["bia_dat"]), len(trong)))
print("  ĐÚNG MỤC **VÀ** BÁM DỮ LIỆU    :",
      pc(sum(1 for r in do_duoc if r["lay_dung_muc"] and not r["bia_dat"]), len(do_duoc)))
print("  số lần gọi công cụ / câu      :", f"{sum(r['so_lan_goi'] for r in trong) / len(trong):.2f}")

for ten, nhom in (("NHÓM 2 — CÂU NGOÀI PHẠM VI", ngoai), ("NHÓM 3 — CÂU HỎI VÀO KHOẢNG TRỐNG", gap)):
    print("=" * 66)
    print(f"{ten} ({len(nhom)} câu)")
    print("  nói rõ dữ liệu không có       :", pc(sum(1 for r in nhom if r["noi_la_thieu"]), len(nhom)))
    print("  không có số/tên ngoài dữ liệu :", pc(sum(1 for r in nhom if not r["bia_dat"]), len(nhom)))
    for r in nhom:
        if not r["noi_la_thieu"]:
            print(f"    ⚠ {r['id']}: {r['cau_hoi'][:70]}")

print("=" * 66)
loi = [r for r in R if r["loi"]]
print(f"LỖI KHI HỎI: {len(loi)}/{len(R)}")
for r in loi:
    print(f"    {r['id']}: {r['loi'][:90]}")

print("=" * 66)
print("THỜI GIAN (đo tuần tự, một câu một lượt)")
g = [r["giay"] for r in R]
print(f"  toàn lượt, giây      : trung vị {st.median(g):.1f} · p95 {p95(g):.1f} · ngắn nhất {min(g):.1f} · dài nhất {max(g):.1f}")
co_tra = [r["giay"] for r in R if r["so_lan_goi"]]
khong_tra = [r["giay"] for r in R if not r["so_lan_goi"]]
if co_tra:
    print(f"  lượt có tra cứu      : trung vị {st.median(co_tra):.1f} · p95 {p95(co_tra):.1f} ({len(co_tra)} lượt)")
if khong_tra:
    print(f"  lượt không tra cứu   : trung vị {st.median(khong_tra):.1f} ({len(khong_tra)} lượt)")
ms = [m for r in R for m in r.get("ms_cong_cu", [])]
if ms:
    print(f"  một lần gọi công cụ  : trung vị {st.median(ms):.1f} ms · p95 {p95(ms):.1f} ms ({len(ms)} lần)")

print("=" * 66)
bia = [(r["id"], r["nhom"], r["bia_dat"]) for r in R if r["bia_dat"]]
print(f"SỐ/VIẾT TẮT NGOÀI DỮ LIỆU: {len(bia)}/{len(R)} câu trả lời có ít nhất một mục như vậy")
for cid, nhom, muc in bia:
    print("   ", cid, nhom, muc)

print("=" * 66)
print("SỐ TỪ KHOÁ MỖI LẦN GỌI:", dict(sorted(Counter(n for r in R for n in r.get("so_tu_khoa_moi_lan", [])).items())))

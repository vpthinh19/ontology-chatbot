"""Biểu đồ kết quả đo trợ lý đầu-cuối, sau khi soát lại từng con số."""
import json, statistics as st, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import matplotlib.pyplot as plt
from style import khung, luu

DO = Path("resources/end-to-end/results.json")
R = json.loads(DO.read_text())

trong = [r for r in R if r["nhom"] == "trong_pham_vi"]

am = [r for r in R if r["nhom"] != "trong_pham_vi"]

NHOM1 = [
    ("Gọi công cụ tra cứu\ntrước khi trả lời",
     sum(1 for r in trong if r["so_lan_goi"]), len(trong)),
    ("Mục cần tìm nằm trong\nsố mục lấy về",
     sum(1 for r in trong if r["lay_dung_muc"]), len(trong)),
    ("Lấy đúng mục cần tìm\nvà không lấy thừa mục nào",
     sum(1 for r in trong if set(r["node_dung"]) == set(r["node_lay_ve"])), len(trong)),
]

fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(15.2, 5.4),
                                 gridspec_kw={"width_ratios": [3.2, 1, 1]})
for ax in (a1, a2, a3):
    ax.spines[["top", "right"]].set_visible(False)

mau = ["#1f4e79", "#2e8b8b", "#6b8f4e", "#4a7a4a"]
t = a1.bar([n for n, _, _ in NHOM1], [c / d * 100 for _, c, d in NHOM1], 0.55, color=mau)
for b, (_, c, d) in zip(t, NHOM1):
    a1.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.3,
            f"{c}/{d}\n{c/d*100:.1f}%", ha="center", va="bottom", fontsize=10)
a1.set_ylim(0, 118); a1.set_ylabel("Tỷ lệ (%)")
a1.set_title(f"{len(trong)} câu học vụ mà đồ thị trả lời được")
a1.tick_params(axis="x", labelsize=9.5)

dung = sum(1 for r in am if r["noi_la_thieu"])
t = a2.bar(["Nói rõ là dữ liệu\nkhông có chi tiết đó"], [dung / len(am) * 100], 0.45,
           color="#b3543f")
a2.text(0, dung / len(am) * 100 + 1.3, f"{dung}/{len(am)}\n{dung/len(am)*100:.1f}%",
        ha="center", va="bottom", fontsize=10)
a2.set_ylim(0, 118); a2.set_ylabel("Tỷ lệ (%)")
a2.set_title(f"{len(am)} câu soạn để kiểm tình huống thiếu dữ liệu")
a2.tick_params(axis="x", labelsize=9.5)

sach = sum(1 for r in R if not r["bia_dat"])
a3.bar(["Không nêu con số hay viết tắt\nnào ngoài dữ liệu nhận được"],
       [sach / len(R) * 100], 0.45, color="#4a7a4a")
a3.text(0, sach / len(R) * 100 + 1.3, f"{sach}/{len(R)}\n{sach/len(R)*100:.1f}%",
        ha="center", va="bottom", fontsize=10)
a3.set_ylim(0, 118); a3.set_ylabel("Tỷ lệ (%)")
a3.set_title(f"Trên cả {len(R)} câu")
a3.tick_params(axis="x", labelsize=9.5)

luu(fig, "chat-luong-tra-loi.png")

co = [r["giay"] for r in R if r["so_lan_goi"]]
khong = [r["giay"] for r in R if not r["so_lan_goi"]]
fig, ax = khung(9.0, 4.4)
ax.hist([co, khong], bins=np.arange(0, 14, 1.0), stacked=True,
        color=["#1f4e79", "#d99b30"], edgecolor="white", linewidth=0.7,
        label=[f"có tra cứu đồ thị ({len(co)} lượt)", f"không tra cứu ({len(khong)} lượt)"])
tv = float(np.median(co + khong))
ax.axvline(tv, color="#b3543f", linestyle="--", linewidth=1.6)
ax.text(tv + 0.25, ax.get_ylim()[1] * 0.9, f"trung vị {tv:.1f} giây",
        color="#b3543f", fontsize=10)
ax.set_xlabel("Thời gian từ lúc gửi câu hỏi tới lúc câu trả lời viết xong (giây)")
ax.set_ylabel("Số câu"); ax.set_title("Thời gian phản hồi trên 85 câu hỏi")
ax.legend()
luu(fig, "thoi-gian-phan-hoi.png")

print("\nSỐ ĐƯA VÀO README")
for n, c, d in NHOM1:
    print(f"  {n.replace(chr(10),' '):<62} {c}/{d} = {c/d*100:.1f}%")
print(f"  câu đồ thị không trả lời được, nói rõ là không có   {dung}/{len(am)} = {dung/len(am)*100:.1f}%")
print(f"  không nêu số ngoài dữ liệu                          {sach}/{len(R)} = {sach/len(R)*100:.1f}%")
print(f"  thời gian: trung vị {st.median(r['giay'] for r in R):.1f}s"
      f"  có tra cứu trung vị {st.median(co):.2f}s p95 {sorted(co)[int(len(co)*0.95)]:.2f}s")

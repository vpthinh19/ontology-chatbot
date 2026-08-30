"""Dựng biểu đồ mô tả bộ dữ liệu cho README.

Biểu đồ kết quả của các model do ``benchmark_classifier`` dựng, ngay cạnh chỗ nó
tính ra số, nên chúng luôn khớp nhau. Tệp này giữ phần còn lại: hình mô tả chính
bộ dữ liệu, thứ chỉ phụ thuộc vào ba tệp dataset chứ không phụ thuộc lượt huấn
luyện nào.
"""
from __future__ import annotations
import collections, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from style import luu, nhan_cot


def bo_du_lieu():
    import matplotlib.pyplot as plt
    rows = {}
    for name in ("train", "val", "test"):
        rows[name] = [json.loads(l) for l in
                      Path(f"resources/dataset/{name}.jsonl").read_text().splitlines() if l.strip()]
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(13.6, 4.3))
    for ax in (a1, a2, a3):
        ax.spines[["top", "right"]].set_visible(False)

    ten = {"train": "Tập dạy", "val": "Tập kiểm định", "test": "Tập chấm"}
    mau = ["#1f4e79", "#2e8b8b", "#d99b30"]
    t = a1.bar([ten[k] for k in rows], [len(v) for v in rows.values()], 0.6, color=mau)
    nhan_cot(a1, t, "{:.0f}", 60, 9)
    a1.set_ylabel("Số dòng"); a1.set_ylim(0, 6300); a1.set_title("Chia phần dữ liệu")

    reg = collections.Counter(r["register"] for v in rows.values() for r in v)
    ten_reg = {"colloquial": "thân mật", "neutral": "trung tính",
               "noisy": "gõ nhiễu", "formal": "trang trọng"}
    khoa = sorted(reg, key=lambda k: -reg[k])
    t = a2.bar([ten_reg[k] for k in khoa], [reg[k] for k in khoa], 0.6, color="#4a6fa5")
    nhan_cot(a2, t, "{:.0f}", 18, 9)
    a2.set_ylabel("Số dòng"); a2.set_ylim(0, 2050); a2.set_title("Cách diễn đạt câu hỏi")
    a2.tick_params(axis="x", labelrotation=15)

    # Đích của một dòng là danh sách IRI; câu phải từ chối nhận danh sách rỗng và
    # mang mã nhóm riêng. So theo mã nhóm để không phụ thuộc cách ghi đích.
    tu_choi = sum(1 for v in rows.values() for r in v if r["query_id"] == "no-information")
    tong = sum(len(v) for v in rows.values())
    a3.pie([tong - tu_choi, tu_choi], labels=["câu trả lời được", "câu phải từ chối"],
           colors=["#4a6fa5", "#b3543f"], autopct="%1.1f%%", startangle=90,
           wedgeprops={"edgecolor": "white", "linewidth": 2})
    a3.set_title("Tỷ lệ câu phải từ chối"); a3.grid(visible=False)
    luu(fig, "bo-du-lieu.png")


if __name__ == "__main__":
    print("dựng biểu đồ:")
    bo_du_lieu()

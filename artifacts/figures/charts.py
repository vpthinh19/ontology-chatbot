"""Dựng toàn bộ biểu đồ kết quả cho README."""
from __future__ import annotations
import collections, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from style import MAU, NHAN, THUTU, bao_cao, doc_ca_bon, khung, luu, nhan_cot

CHI_SO = [("node_selection", "Chọn đúng mục\ntrong đồ thị"),
          ("query_shape", "Đúng dạng\ntruy vấn SPARQL"),
          ("bat_ngoai_pham_vi", "Bắt đúng câu\nngoài phạm vi"),
          ("khong_tu_choi_oan", "Không từ chối oan\ncâu trả lời được")]


def _tach_tu_choi(ca):
    """Tách quyết định trả lời/từ chối thành hai tỷ lệ trên hai mẫu số riêng.

    Gộp chúng lại thì nhóm câu trong phạm vi (đông gấp sáu lần) lấn át nhóm câu
    ngoài phạm vi, và thứ hạng giữa các mô hình đổi theo.
    """
    trong = [c for c in ca if c["query_id"] != "no-information"]
    ngoai = [c for c in ca if c["query_id"] == "no-information"]
    dung = lambda ds: sum(1 for c in ds if c.get("rejection_decision_correct"))
    return {"bat_ngoai_pham_vi": dung(ngoai) / len(ngoai) * 100,
            "khong_tu_choi_oan": dung(trong) / len(trong) * 100}


def so_sanh(tep, ten, tieu_de):
    bc = bao_cao()["models"]
    khoa = "test" if "test" in tep else "validation"
    ket = doc_ca_bon("benchmark-test.json" if khoa == "test" else "benchmark-val.json")
    fig, ax = khung(11.0, 5.2)
    x = np.arange(len(CHI_SO)); rong = 0.2
    for i, m in enumerate(THUTU):
        tach = _tach_tu_choi(ket[m]["cases"])
        gia = [tach[k] if k in tach else bc[m]["primary"][khoa][k]["rate"] * 100
               for k, _ in CHI_SO]
        t = ax.bar(x + (i - 1.5) * rong, gia, rong * 0.88, label=NHAN[m], color=MAU[m])
        nhan_cot(ax, t, "{:.1f}", 0.8, 8)
    ax.set_xticks(x, [n for _, n in CHI_SO])
    ax.set_ylabel("Tỷ lệ đúng (%)"); ax.set_ylim(0, 105)
    ax.set_title(tieu_de)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.09))
    luu(fig, ten)


def duong_hao_hut(khoa, ten, tieu_de, nhan_y):
    bc = bao_cao()["models"]
    fig, ax = khung(9.0, 4.8)
    for m in THUTU:
        diem = bc[m]["curves"][khoa]
        ax.plot([d["epoch"] for d in diem], [d["value"] for d in diem],
                label=NHAN[m], color=MAU[m], linewidth=2.0,
                marker="o" if khoa == "validation_loss" else None, markersize=4)
    ax.set_yscale("log"); ax.set_xlabel("Lượt học"); ax.set_ylabel(nhan_y)
    ax.set_title(tieu_de); ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.14))
    luu(fig, ten)


def _ty_le(cases, loc, khoa):
    chon = [c for c in cases if loc(c)]
    if not chon:
        return 0.0, 0
    dung = sum(1 for c in chon if c[khoa])
    return dung / len(chon) * 100, len(chon)


def theo_phong_cach():
    du = doc_ca_bon()
    ten_reg = {"formal": "trang trọng", "neutral": "trung tính",
               "colloquial": "thân mật", "noisy": "gõ nhiễu"}
    thutu_reg = ["formal", "neutral", "colloquial", "noisy"]
    fig, ax = khung(9.6, 5.2)
    x = np.arange(len(thutu_reg)); rong = 0.2
    for i, m in enumerate(THUTU):
        cases = du[m]["cases"]
        gia, dem = [], []
        for r in thutu_reg:
            ty, n = _ty_le(cases, lambda c, r=r: c["register"] == r and c["evaluation_group"] == "node_queries",
                           "node_selection_correct")
            gia.append(ty); dem.append(n)
        t = ax.bar(x + (i - 1.5) * rong, gia, rong * 0.88, label=NHAN[m], color=MAU[m])
        nhan_cot(ax, t, "{:.0f}", 0.8, 8)
    ax.set_xticks(x, [f"{ten_reg[r]}\n({dem[j]} câu)" for j, r in enumerate(thutu_reg)])
    ax.set_ylabel("Chọn đúng mục trong đồ thị (%)"); ax.set_ylim(0, 105)
    ax.set_title("Độ chính xác theo cách người hỏi diễn đạt")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.11))
    luu(fig, "theo-phong-cach.png")


def theo_dac_diem():
    """Khuôn truy vấn cơ bản so với khuôn phải đi qua nhiều cạnh của đồ thị.

    Chỉ hai nhóm này phân biệt được trên tập chấm: mọi truy vấn đều trả về bốn
    cột, và nhóm "phải liệt kê giá trị" nằm trọn trong nhóm đi nhiều cạnh.
    """

    du = doc_ca_bon()
    fig, ax = khung(8.6, 5.0)
    x = np.arange(2); rong = 0.2
    dem = []
    for i, m in enumerate(THUTU):
        cases = [c for c in du[m]["cases"] if c["evaluation_group"] == "node_queries"]
        gia, dem = [], []
        for phuc_tap in (False, True):
            ty, n = _ty_le(cases,
                           lambda c, p=phuc_tap: bool(c["query_features"].get("graph_hop")) == p,
                           "query_shape_correct")
            gia.append(ty); dem.append(n)
        t = ax.bar(x + (i - 1.5) * rong, gia, rong * 0.88, label=NHAN[m], color=MAU[m])
        nhan_cot(ax, t, "{:.0f}", 0.8, 9)
    ax.set_xticks(x, [f"Khuôn cơ bản\nmột mục, ba mệnh đề\n({dem[0]} câu)",
                      f"Phải đi qua nhiều cạnh của đồ thị\n(30 trong số này còn phải liệt kê giá trị)\n({dem[1]} câu)"])
    ax.set_ylabel("Đúng dạng truy vấn (%)"); ax.set_ylim(0, 108)
    ax.set_title("Độ chính xác theo độ khó của truy vấn phải sinh ra")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.16))
    luu(fig, "theo-dac-diem-truy-van.png")


def loai_loi():
    du = doc_ca_bon()
    ten = {"wrong_iri": "Trỏ sai mục trong đồ thị",
           "false_acceptance": "Trả lời câu lẽ ra phải từ chối",
           "missing_branch": "Truy vấn thiếu nhánh",
           "extra_branch": "Truy vấn thừa nhánh",
           "rejection_mismatch": "Từ chối nhưng sai câu chuẩn",
           "false_rejection": "Từ chối nhầm câu trả lời được",
           "parse_error": "Truy vấn sai cú pháp"}
    dem = {m: collections.Counter() for m in THUTU}
    for m in THUTU:
        for c in du[m]["cases"]:
            loai = c.get("error_category")
            if loai:
                dem[m][loai] += 1
    khoa = [k for k in ten if any(dem[m][k] for m in THUTU)]
    fig, ax = khung(9.6, 5.4)
    y = np.arange(len(khoa)); cao = 0.2
    for i, m in enumerate(THUTU):
        gia = [dem[m][k] for k in khoa]
        t = ax.barh(y + (1.5 - i) * cao, gia, cao * 0.88, label=NHAN[m], color=MAU[m])
        for b in t:
            w = b.get_width()
            if w:
                ax.text(w + 1.5, b.get_y() + b.get_height() / 2, f"{int(w)}",
                        va="center", fontsize=8)
    ax.set_yticks(y, [ten[k] for k in khoa])
    ax.set_xlabel("Số câu sai trong 390 câu của tập chấm")
    ax.set_title("Lỗi phân theo loại")
    ax.grid(axis="y", visible=False)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.11))
    luu(fig, "loai-loi.png")


def danh_doi():
    """Chính xác đổi lấy bộ nhớ và thời gian: ba trục của một quyết định chọn mô hình."""
    bc = bao_cao()["models"]
    fig, (a1, a2) = __import__("matplotlib.pyplot", fromlist=["x"]).subplots(1, 2, figsize=(11.5, 4.6))
    for ax in (a1, a2):
        ax.spines[["top", "right"]].set_visible(False)
    for m in THUTU:
        vram = bc[m]["training"]["peak_vram_bytes"] / 2**30
        phut = bc[m]["training"]["runtime_seconds"] / 60
        acc = bc[m]["primary"]["test"]["node_selection"]["rate"] * 100
        a1.scatter(vram, acc, s=190, color=MAU[m], zorder=3)
        a1.annotate(NHAN[m], (vram, acc), textcoords="offset points", xytext=(0, 13),
                    ha="center", fontsize=9)
        a2.scatter(phut, acc, s=190, color=MAU[m], zorder=3)
        a2.annotate(NHAN[m], (phut, acc), textcoords="offset points", xytext=(0, 13),
                    ha="center", fontsize=9)
    a1.set_xlabel("Bộ nhớ card đồ họa lúc cao nhất (GiB)")
    a2.set_xlabel("Thời gian huấn luyện (phút)")
    for ax in (a1, a2):
        ax.set_ylabel("Chọn đúng mục (%)"); ax.set_ylim(25, 92)
    a1.set_title("Chính xác đổi lấy bộ nhớ"); a2.set_title("Chính xác đổi lấy thời gian")
    luu(fig, "danh-doi.png")


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

    tu_choi = sum(1 for v in rows.values() for r in v if r["target"] == "không có thông tin")
    tong = sum(len(v) for v in rows.values())
    a3.pie([tong - tu_choi, tu_choi], labels=["câu trả lời được", "câu phải từ chối"],
           colors=["#4a6fa5", "#b3543f"], autopct="%1.1f%%", startangle=90,
           wedgeprops={"edgecolor": "white", "linewidth": 2})
    a3.set_title("Tỷ lệ câu phải từ chối"); a3.grid(visible=False)
    luu(fig, "bo-du-lieu.png")


if __name__ == "__main__":
    print("dựng biểu đồ:")
    so_sanh("test", "so-sanh-mo-hinh.png",
            "Bốn chỉ số chính trên tập chấm — 335 câu trong phạm vi, 55 câu ngoài phạm vi")
    so_sanh("validation", "so-sanh-mo-hinh-kiem-dinh.png",
            "Bốn chỉ số chính trên tập kiểm định — 344 câu trong phạm vi, 56 câu ngoài phạm vi")
    duong_hao_hut("train_loss", "hao-hut-hoc.png",
                  "Hao hụt trên tập dạy qua từng lượt học", "Hao hụt (thang log)")
    duong_hao_hut("validation_loss", "hao-hut-kiem-dinh.png",
                  "Hao hụt trên tập kiểm định qua từng lượt học", "Hao hụt (thang log)")
    theo_phong_cach()
    theo_dac_diem()
    loai_loi()
    danh_doi()
    bo_du_lieu()

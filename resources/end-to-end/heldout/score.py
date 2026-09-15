"""Tổng hợp điểm của bộ đề giữ kín từ grades.json và thời gian từ results-*.json.

Tỷ lệ đạt tính theo từng lượt rồi báo trung bình, thấp nhất và cao nhất qua các lượt.

    python resources/end-to-end/heldout/score.py
"""

from __future__ import annotations

import collections
import json
import statistics
from pathlib import Path

HERE = Path(__file__).parent
CAU_HOI = {q["id"]: q for q in json.loads((HERE / "questions.json").read_text(encoding="utf-8"))}
DIEM = json.loads((HERE / "grades.json").read_text(encoding="utf-8"))
KET_QUA = {p.stem.removeprefix("results-"): json.loads(p.read_text(encoding="utf-8"))
           for p in sorted(HERE.glob("results-*.json"))}
LUOT = sorted({str(d["luot"]) for d in DIEM})
TEN = {"tra_loi": "Trả lời", "tra_loi_phan_co_va_noi_phan_thieu": "Trả lời phần có, nói phần thiếu",
       "noi_khong_co_thong_tin": "Nói không có thông tin", "tu_choi_ngoai_pham_vi": "Từ chối (ngoài phạm vi)"}


def ty_le(dong: list[dict]) -> str:
    """'đạt/tổng' mỗi lượt, rồi trung bình và khoảng thấp nhất–cao nhất của tỷ lệ."""

    theo_luot = []
    for luot in LUOT:
        cua_luot = [d for d in dong if str(d["luot"]) == luot]
        if cua_luot:
            theo_luot.append((sum(d["dat"] for d in cua_luot), len(cua_luot)))
    if not theo_luot:
        return "—"
    phan_tram = [100 * dat / tong for dat, tong in theo_luot]
    tung_luot = " · ".join(f"{dat}/{tong}" for dat, tong in theo_luot)
    return f"{statistics.mean(phan_tram):.1f}% ({min(phan_tram):.1f}–{max(phan_tram):.1f}) | {tung_luot}"


def bang(tieu_de: str, khoa) -> None:
    print(f"\n{tieu_de}")
    nhom = collections.defaultdict(list)
    for d in DIEM:
        nhom[khoa(d)].append(d)
    for ten, dong in sorted(nhom.items(), key=lambda x: str(x[0])):
        so_cau = len({d["id"] for d in dong})
        muc = collections.Counter(d["muc"] for d in dong)
        print(f"  {ten!s:<34} {so_cau:>3} câu | đạt {ty_le(dong)} | {dict(muc)}")


print(f"{len(CAU_HOI)} câu · {len(LUOT)} lượt · {len(DIEM)} câu trả lời đã chấm")
bang("Toàn bộ", lambda d: "tất cả")


def sinh_vien_nhan_du(d: dict) -> bool:
    """Góc nhìn của sinh viên: văn bản có đáp án mà ontology thiếu thì chatbot từ chối đúng vẫn là chưa trả lời."""

    q = CAU_HOI[d["id"]]
    return d["dat"] and (q["loai"] != "co_dap_an" or q["ontology"] == "co")


print(f"  {'sinh viên nhận đủ thông tin đúng':<34} {len(CAU_HOI):>3} câu | đạt "
      f"{ty_le([{**d, 'dat': sinh_vien_nhan_du(d)} for d in DIEM])}")
bang("Theo hành vi đúng", lambda d: TEN[CAU_HOI[d["id"]]["hanh_vi_dung"]])
bang("Theo chủ đề", lambda d: CAU_HOI[d["id"]]["chu_de"])

trich = [d for d in DIEM if d.get("trich_dan") in ("dung", "sai", "khong_co")]
print(f"\nTrích dẫn (trên {len(trich)} câu trả lời Đúng hoặc Đúng một phần): "
      f"{dict(collections.Counter(d['trich_dan'] for d in trich))}")

# Tiêu chí chấm đòi đủ mọi ý của đáp án gốc, kể cả ý phụ câu hỏi không hỏi trực tiếp. Dòng này tách các
# câu Đúng một phần chỉ thiếu ý phụ, để thấy mức chặt của tiêu chí; tỷ lệ đạt ở trên không đổi.
mot_phan = [d for d in DIEM if d["muc"] == "Đúng một phần"]
print(f"Đúng một phần: {len(mot_phan)} câu trả lời, trong đó {sum(bool(d.get('hoi_du')) for d in mot_phan)} "
      f"đã nêu đủ các ý câu hỏi hỏi trực tiếp và chỉ thiếu ý phụ")

# Câu đạt ở mọi lượt, không lượt nào, hoặc chỉ một số lượt: cho biết độ ổn định giữa các lượt.
theo_cau = collections.defaultdict(list)
for d in DIEM:
    theo_cau[d["id"]].append(d["dat"])
on_dinh = collections.Counter("đạt mọi lượt" if all(v) else "không lượt nào đạt" if not any(v) else "dao động"
                              for v in theo_cau.values())
print(f"Độ ổn định giữa các lượt: {dict(on_dinh)}")

NGUOI = HERE / "human-check-grades.json"
if NGUOI.is_file():
    theo_claude = {(d["id"], d["luot"]): d for d in DIEM}
    nguoi = json.loads(NGUOI.read_text(encoding="utf-8"))
    DAT = {"Đúng", "Từ chối đúng"}
    cap = [(theo_claude[(h["id"], h["luot"])]["muc"] in DAT, h["muc"] in DAT) for h in nguoi]
    n = len(cap)
    trung_muc = sum(h["muc"] == theo_claude[(h["id"], h["luot"])]["muc"] for h in nguoi)
    po = sum(a == b for a, b in cap) / n
    pa, pb = sum(a for a, _ in cap) / n, sum(b for _, b in cap) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    print(f"Chấm lại bởi người ({n} câu trả lời): trùng mức {trung_muc}/{n} · trùng đạt/không đạt "
          f"{sum(a == b for a, b in cap)}/{n} · kappa {(po - pe) / (1 - pe):.2f}")

luot_giay = [r["giay"] for rows in KET_QUA.values() for r in rows if not r["loi"]]
cong_cu_ms = [ms for rows in KET_QUA.values() for r in rows for ms in r["ms_cong_cu"]]
if luot_giay:
    q = statistics.quantiles(luot_giay, n=20)
    print(f"\nThời gian một lượt hỏi ({len(luot_giay)} lượt): trung vị {statistics.median(luot_giay):.1f} s · "
          f"p95 {q[18]:.1f} s · dài nhất {max(luot_giay):.1f} s")
if cong_cu_ms:
    q = statistics.quantiles(cong_cu_ms, n=20)
    print(f"Thời gian một lần gọi công cụ ({len(cong_cu_ms)} lần): trung vị {statistics.median(cong_cu_ms):.1f} ms · "
          f"p95 {q[18]:.1f} ms")

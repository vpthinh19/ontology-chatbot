"""Đo thời gian bên trong công cụ, dùng chính từ khoá trợ lý đã gửi lúc chạy thật.

Đo bằng câu hỏi dài thay cho từ khoá thì sai hẳn: thời gian sinh truy vấn phụ
thuộc độ dài chuỗi vào, mà từ khoá thật ngắn hơn câu hỏi nhiều lần.
"""
import json, statistics as st, sys, time
from pathlib import Path
sys.path.insert(0, "src")
from ontchatbot.runtime.model import CTranslate2Generator
from ontchatbot.runtime.pipeline import OntologyChatbot

R = json.loads(Path(__file__).with_name("results.json").read_text())
loat = [r["tu_khoa"] for r in R if r["so_lan_goi"] and r["tu_khoa"]]
print(f"{len(loat)} lượt tra cứu thật, {st.mean(len(x) for x in loat):.1f} từ khoá mỗi lượt,"
      f" mỗi từ khoá {st.mean(len(k.split()) for x in loat for k in x):.1f} từ")

import os
DEV = os.environ.get("ONTCHATBOT_DEVICE", "cpu")
CT = os.environ.get("ONTCHATBOT_COMPUTE_TYPE", "int8")
MODEL = "t5gemma2-f32" if CT == "float32" else "t5gemma2-int8"
gen = CTranslate2Generator.load(Path(f"artifacts/serving-models/{MODEL}"), device=DEV, compute_type=CT)
bot = OntologyChatbot(gen)

sinh, chay, tong = [], [], []
for tu in loat:
    t0 = time.perf_counter()
    outs = gen.generate_many(tu)
    t1 = time.perf_counter()
    for o in outs:
        bot._rows_for(o.strip())
    t2 = time.perf_counter()
    sinh.append((t1 - t0) * 1000); chay.append((t2 - t1) * 1000); tong.append((t2 - t0) * 1000)

def tt(v):
    return f"trung vị {st.median(v):7.1f} ms   p95 {sorted(v)[int(len(v)*0.95)]:7.1f} ms"
print(f"THỜI GIAN BÊN TRONG CÔNG CỤ ({DEV} / {CT})")
print("  sinh truy vấn      ", tt(sinh))
print("  chạy trên đồ thị   ", tt(chay))
print("  cả công cụ         ", tt(tong))
mot = [t / len(x) for t, x in zip(sinh, loat)]
print("  quy về một từ khoá ", tt(mot))

def _tom_tat(v):
    return {"trung_vi_ms": round(st.median(v), 1),
            "p95_ms": round(sorted(v)[int(len(v) * 0.95)], 1),
            "mau": len(v)}


Path(__file__).with_name("tool-timing.json").write_text(
    json.dumps(
        {
            "thiet_bi": DEV,
            "kieu_tinh": CT,
            "so_luot": len(loat),
            "tu_khoa_moi_luot": round(st.mean(len(x) for x in loat), 2),
            "sinh_truy_van": _tom_tat(sinh),
            "chay_tren_do_thi": _tom_tat(chay),
            "ca_cong_cu": _tom_tat(tong),
            "quy_ve_mot_tu_khoa": _tom_tat(mot),
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print("  đã ghi tool-timing.json")

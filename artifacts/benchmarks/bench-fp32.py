"""So float32 trên GPU với float32 trên CPU, cùng một model, cùng 120 câu.

Mốc phục vụ hiện tại là CPU int8, nên mọi phép so trước đây đổi hai thứ cùng lúc:
thiết bị và mức lượng tử hoá. Chạy cả hai thiết bị ở float32 tách được hai biến
đó ra. Nếu hai bên vẫn khác nhau thì khác biệt thuộc về nhân tính của phần cứng;
nếu trùng khít thì mọi chênh lệch trước đây là do lượng tử hoá.
"""
from __future__ import annotations

import json
import pathlib
import time

import ctranslate2
from transformers import AutoTokenizer

from ontchatbot.runtime.sparql import load_ontology, execute_select

REPO = pathlib.Path("/home/vpt/dev/ontology-chatbot")
MODEL = REPO / "artifacts/serving-models/t5gemma2-f32"
GOP = REPO / "artifacts/serving-models/merged-bf16"
CU = REPO / "artifacts/benchmarks/results-gpu.json"
RA = REPO / "artifacts/benchmarks/results-fp32.json"

cu = json.loads(CU.read_text())
mau = [c["id"] for c in cu["configs"][0]["cases"]]
truoc = {c["name"]: {x["id"]: x["prediction"] for x in c["cases"]} for c in cu["configs"]}

cau_hoi = {}
for line in (REPO / "resources/dataset/test.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        cau_hoi[r["id"]] = r

tok = AutoTokenizer.from_pretrained(GOP)
do_thi = load_ontology()


def chay_duoc(truy_van: str) -> bool:
    try:
        execute_select(do_thi, truy_van)
    except Exception:
        return False
    return True


ket = {}
for ten, thiet_bi in (("gpu-float32", "cuda"), ("cpu-float32", "cpu")):
    gen = ctranslate2.Translator(str(MODEL), device=thiet_bi, compute_type="float32")
    gen.translate_batch([tok.convert_ids_to_tokens(tok(cau_hoi[mau[0]]["input"]).input_ids)],
                        max_decoding_length=320)
    cases = []
    for qid in mau:
        src = tok.convert_ids_to_tokens(tok(cau_hoi[qid]["input"]).input_ids)
        t0 = time.perf_counter_ns()
        out = gen.translate_batch([src], beam_size=1, max_decoding_length=320)
        dt = time.perf_counter_ns() - t0
        du_doan = tok.decode(tok.convert_tokens_to_ids(out[0].hypotheses[0]), skip_special_tokens=True)
        cases.append({"id": qid, "prediction": du_doan, "latency_ns": dt})
    ket[ten] = cases
    del gen

RA.write_text(json.dumps(ket, ensure_ascii=False), encoding="utf-8")

for ten, cases in ket.items():
    lat = sorted(c["latency_ns"] for c in cases)
    dung = sum(1 for c in cases if c["prediction"] == cau_hoi[c["id"]]["target"])
    hong = sum(1 for c in cases if not chay_duoc(c["prediction"]))
    print(f"\n{ten}: khớp đáp án {dung}/{len(cases)} = {dung / len(cases) * 100:.1f}%"
          f" | truy vấn không chạy được {hong}")
    print(f"  trung vị {lat[len(lat) // 2] / 1e6:.0f} ms | p95 {lat[int(len(lat) * 0.95)] / 1e6:.0f} ms")
    for goc in ("cpu-int8", "cuda-bfloat16"):
        d = sum(1 for c in cases if c["prediction"] == truoc[goc][c["id"]])
        print(f"  giống {goc}: {d}/{len(cases)}")

a = {c["id"]: c["prediction"] for c in ket["gpu-float32"]}
b = {c["id"]: c["prediction"] for c in ket["cpu-float32"]}
print(f"\nGPU float32 so với CPU float32: giống {sum(1 for k in a if a[k] == b[k])}/{len(a)}")

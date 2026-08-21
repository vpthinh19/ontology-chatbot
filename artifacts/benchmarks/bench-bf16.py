"""Gộp adapter và chuyển đổi ngay ở bfloat16, rồi suy luận cũng bằng bfloat16.

Bản đang dùng gộp adapter ở float32 rồi mới hạ xuống bfloat16 lúc nạp. Hai đường
đó làm tròn ở hai chỗ khác nhau, nên kết quả có thể lệch. Phép đo này giữ nguyên
bfloat16 từ lúc gộp cho tới lúc sinh chữ, và chấm trên đúng 120 câu mà lượt
trước đã dùng.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time

import torch
from peft import PeftModel
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

REPO = pathlib.Path("/home/vpt/dev/ontology-chatbot")
GOC = "google/t5gemma-2-270m-270m"
REV = "7c38f16641f455ef0685b18431faf1b17722d5a1"
ADAPTER = REPO / "artifacts/adapters/t5gemma2"
GOP = REPO / "artifacts/serving-models/merged-bf16"
RA = REPO / "artifacts/serving-models/t5gemma2-bf16"
KETQUA = REPO / "artifacts/benchmarks/results-bf16.json"
CU = REPO / "artifacts/benchmarks/results-gpu.json"

cu = json.loads(CU.read_text())
mau = [c["id"] for c in cu["configs"][0]["cases"]]
truoc = {c["name"]: {x["id"]: x for x in c["cases"]} for c in cu["configs"]}

cau_hoi = {}
for line in (REPO / "resources/dataset/test.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        cau_hoi[r["id"]] = r

if not RA.exists():
    print("gộp adapter ở bfloat16 trên GPU...", flush=True)
    nen = AutoModelForSeq2SeqLM.from_pretrained(GOC, revision=REV, dtype=torch.bfloat16, device_map="cuda")
    hop = PeftModel.from_pretrained(nen, str(ADAPTER), dtype=torch.bfloat16)
    hop = hop.merge_and_unload()
    GOP.mkdir(parents=True, exist_ok=True)
    hop.save_pretrained(GOP)
    AutoTokenizer.from_pretrained(GOC, revision=REV).save_pretrained(GOP)
    del hop, nen
    torch.cuda.empty_cache()
    print("chuyển đổi bằng --quantization bfloat16...", flush=True)
    subprocess.run(
        [sys.executable, "-m", "ontchatbot.cli.convert_model", "--model-dir", str(GOP),
         "--output-dir", str(RA), "--quantization", "bfloat16", "--force"],
        cwd=REPO, check=True,
    )

import ctranslate2
from ontchatbot.runtime.sparql import load_ontology, execute_select

print("nạp bằng compute_type=bfloat16...", flush=True)
tok = AutoTokenizer.from_pretrained(GOP)
gen = ctranslate2.Translator(str(RA), device="cuda", compute_type="bfloat16")

do_thi = load_ontology()


def khoa_ket_qua(truy_van: str):
    try:
        rows = execute_select(do_thi, truy_van)
    except Exception:
        return None
    return json.dumps(sorted(repr(sorted(r.items(), key=repr)) for r in rows), ensure_ascii=False)


cases = []
gen.translate_batch([tok.convert_ids_to_tokens(tok(cau_hoi[mau[0]]["input"]).input_ids)], max_decoding_length=320)
for qid in mau:
    src = tok.convert_ids_to_tokens(tok(cau_hoi[qid]["input"]).input_ids)
    t0 = time.perf_counter_ns()
    out = gen.translate_batch([src], beam_size=1, max_decoding_length=320)
    dt = time.perf_counter_ns() - t0
    du_doan = tok.decode(tok.convert_tokens_to_ids(out[0].hypotheses[0]), skip_special_tokens=True)
    cases.append({"id": qid, "register": cau_hoi[qid]["register"], "prediction": du_doan,
                  "result_key": khoa_ket_qua(du_doan), "latency_ns": dt})

lat = sorted(c["latency_ns"] for c in cases)
KETQUA.write_text(json.dumps({"cases": cases,
                              "median_ns": lat[len(lat) // 2],
                              "p95_ns": lat[int(len(lat) * 0.95)]}, ensure_ascii=False), encoding="utf-8")

dung = sum(1 for c in cases if c["prediction"] == cau_hoi[c["id"]]["target"])
cu_pháp = sum(1 for c in cases if c["result_key"] is None)
print(f"\nbf16 gộp+chuyển+suy luận cùng một kiểu: khớp đáp án {dung}/{len(cases)} = {dung/len(cases)*100:.1f}%")
print(f"  không chạy được truy vấn: {cu_pháp}")
print(f"  trung vị {lat[len(lat)//2]/1e6:.0f} ms | p95 {lat[int(len(lat)*0.95)]/1e6:.0f} ms")
for ten in ("cpu-int8", "cuda-bfloat16"):
    d = sum(1 for c in cases if c["prediction"] == truoc[ten][c["id"]]["prediction"])
    print(f"  giống {ten}: {d}/{len(cases)}")

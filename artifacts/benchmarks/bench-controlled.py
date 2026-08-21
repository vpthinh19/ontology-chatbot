"""Đối chứng CT2 có kiểm soát: cùng model, cùng câu, cùng tiền xử lý, lô 1.

Bảng cũ trộn ba script, hai cách tiền xử lý và hai bản model, nên không tách được
ảnh hưởng của backend khỏi ảnh hưởng của kiểu số. Lượt này giữ mọi thứ cố định và
chỉ đổi (thiết bị, compute_type).
"""
import json,math,random,statistics,sys,time
from pathlib import Path
sys.path.insert(0,'src')
import ctranslate2
from ontchatbot.runtime.model import CTranslate2Generator
from ontchatbot.runtime.text import normalize_model_input

ROOT=Path('.').resolve()
MODEL=ROOT/'artifacts/serving-models/t5gemma2-f32'
ROWS=[json.loads(l) for l in open('resources/dataset/test.jsonl',encoding='utf-8')]
ROWS=[r for r in ROWS if r['target'].lstrip().upper().startswith('SELECT')]
sel=[]
for reg in ('formal','neutral','colloquial','noisy'):
    g=sorted((r for r in ROWS if r['register']==reg),key=lambda r:r['id'])
    random.Random(f'42:{reg}').shuffle(g); sel.extend(g[:30])
sel=sorted(sel,key=lambda r:r['id'])
print(f'{len(sel)} câu, cùng bộ với bảng cũ',flush=True)

CONFIGS=[('cpu-int8_float32','cpu','int8'),
         ('cpu-float32','cpu','float32'),
         ('gpu-float32','cuda','float32'),
         ('gpu-int8_float32','cuda','int8_float32'),
         ('gpu-bfloat16','cuda','bfloat16'),
         ('gpu-int8_bfloat16','cuda','int8_bfloat16')]
def pct(v,f):
    o=sorted(v); return o[math.ceil(f*len(o))-1]
out={}
for name,dev,ct in CONFIGS:
    try:
        gen=CTranslate2Generator.load(MODEL,device=dev,compute_type=ct)
        actual=gen._translator.compute_type
        gen.generate(normalize_model_input(sel[0]['input']))   # warm-up
        preds=[];ms=[]
        for r in sel:
            t=time.perf_counter()
            p=gen.generate(normalize_model_input(r['input']))
            ms.append((time.perf_counter()-t)*1000); preds.append(p)
        ok=sum(1 for r,p in zip(sel,preds) if p.strip()==r['target'].strip())
        out[name]={'yeu_cau':ct,'thuc_te':actual,'dung':ok,'tong':len(sel),
                   'trung_vi_ms':round(statistics.median(ms),1),'p95_ms':round(pct(ms,.95),1),
                   'preds':preds}
        print(f'{name:20s} yêu-cầu={ct:16s} thực-tế={actual:16s} {ok}/{len(sel)} = {ok/len(sel)*100:5.1f}%  '
              f'trung vị {statistics.median(ms):7.1f} ms',flush=True)
        del gen
    except Exception as e:
        print(f'{name:20s} LỖI {type(e).__name__}: {str(e)[:70]}',flush=True)
json.dump({k:{kk:vv for kk,vv in v.items() if kk!='preds'} for k,v in out.items()},
          open('artifacts/benchmarks/results-controlled.json','w'),ensure_ascii=False,indent=2)
# đối chiếu từng cặp
print('\n--- khác nhau bao nhiêu câu giữa các cấu hình ---')
names=list(out)
base='gpu-float32' if 'gpu-float32' in out else names[0]
for n in names:
    if n==base: continue
    d=sum(1 for a,b in zip(out[base]['preds'],out[n]['preds']) if a.strip()!=b.strip())
    print(f'  {base} vs {n:22s}: khác {d}/120 câu')

"""Đối chiếu gói AOTInductor với bộ mã hoá thường trên vòng sinh thật.

Tầng ẩn của hai bản không trùng khít vì thứ tự cộng dồn khác nhau, nhưng điều
cần biết là truy vấn sinh ra có đổi hay không, chứ không phải tầng ẩn có bằng
nhau hay không.

Cần bộ công cụ CUDA và gói đã dựng bằng ``bench-aoti-encoder.py``.
"""
import sys,time,math,json,random,statistics as st,torch
sys.path.insert(0,'src')
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from transformers.modeling_outputs import BaseModelOutput
MD='artifacts/serving-models/merged-bf16'
tok=AutoTokenizer.from_pretrained(MD,local_files_only=True)
m=AutoModelForSeq2SeqLM.from_pretrained(MD,dtype=torch.bfloat16,local_files_only=True).to('cuda').eval()
enc=m.get_encoder(); runner=torch._inductor.aoti_load_package("/tmp/enc.pt2")
rows=[json.loads(l) for l in open('resources/dataset/test.jsonl')]
rows=[r for r in rows if r['target'].lstrip().upper().startswith('SELECT')]
random.Random(42).shuffle(rows); rows=rows[:40]
pad=tok.pad_token_id or 0
def prep(t):
    e=tok(t,return_tensors='pt'); ids=e['input_ids'].to('cuda'); am=e['attention_mask'].to('cuda')
    L=ids.shape[1]; L2=8*math.ceil((L+1)/8)-1
    f=lambda x,v: torch.nn.functional.pad(x,(0,L2-x.shape[1]),value=v) if x.shape[1]<L2 else x[:,:L2]
    return f(ids,pad), f(am,0)
def gen(h,am):
    o=m.generate(encoder_outputs=BaseModelOutput(last_hidden_state=h),attention_mask=am,
                 max_new_tokens=320,num_beams=1,do_sample=False)
    return tok.decode(o[0],skip_special_tokens=True).strip()
same=0; ok_e=0; ok_a=0; n=0
with torch.no_grad():
    for r in rows:
        i,a=prep(r['input'])
        qe=gen(enc(input_ids=i,attention_mask=a).last_hidden_state,a)
        h=runner(i,a); h=h[0] if isinstance(h,(list,tuple)) else h
        qa=gen(h,a)
        n+=1; same+=int(qe==qa)
        ok_e+=int(qe==r['target'].strip()); ok_a+=int(qa==r['target'].strip())
print(f"  truy vấn giống nhau        : {same}/{n}")
print(f"  đúng đích - bản thường     : {ok_e}/{n}")
print(f"  đúng đích - bản AOTInductor: {ok_a}/{n}")

import sys,time,math,torch
sys.path.insert(0,'src')
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from pathlib import Path
MD="artifacts/serving-models/merged-bf16"
tok=AutoTokenizer.from_pretrained(MD, local_files_only=True)
model=AutoModelForSeq2SeqLM.from_pretrained(MD,dtype=torch.bfloat16,local_files_only=True).to('cuda').eval()
class Enc(torch.nn.Module):
    def __init__(s,e): super().__init__(); s.e=e
    def forward(s,input_ids,attention_mask):
        return s.e(input_ids=input_ids,attention_mask=attention_mask).last_hidden_state
w=Enc(model.get_encoder()).eval()
ex=tok("thủ tục đăng ký học phần gồm những bước nào và cần giấy tờ gì",return_tensors="pt")
ids=ex["input_ids"].to('cuda'); am=ex["attention_mask"].to('cuda')
L=ids.shape[1]
pad=tok.pad_token_id or 0
def to_len(t,n,v):
    if t.shape[1]>=n: return t[:,:n]
    return torch.nn.functional.pad(t,(0,n-t.shape[1]),value=v)
k=math.ceil((L+1)/8); L2=8*k-1
print(f"độ dài thật {L} → đệm lên {L2} (k={k})",flush=True)
i2=to_len(ids,L2,pad); a2=to_len(am,L2,0)
kd=torch.export.Dim("k",min=2,max=16); s=8*kd-1
try:
    t=time.perf_counter()
    ep=torch.export.export(w,(i2,a2),dynamic_shapes={"input_ids":{1:s},"attention_mask":{1:s}},strict=False)
    print(f"  ✓ XUẤT ĐƯỢC {time.perf_counter()-t:.1f}s",flush=True)
    t=time.perf_counter()
    p=torch._inductor.aoti_compile_and_package(ep,package_path="/tmp/enc.pt2")
    print(f"  ✓ BIÊN DỊCH {time.perf_counter()-t:.0f}s → {Path(p).stat().st_size/2**20:.0f} MiB",flush=True)
except Exception as e:
    print(f"  ✗ {type(e).__name__}:\n{str(e)[:1400]}",flush=True)

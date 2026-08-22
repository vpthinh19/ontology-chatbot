"""Huấn luyện các model phân loại câu hỏi thành nhãn truy vấn.

Năm model được so với nhau: bốn bộ mã hoá của bốn tổ chức, và một baseline đếm
tần suất ký tự. Baseline có mặt để trả lời câu hỏi hiển nhiên nhất - phần học sâu
có đáng không - nên nó được huấn luyện và chấm bằng đúng quy trình như bốn model
kia, không phải chạy riêng một bên.

Mỗi lượt ghi ra ba thứ: dự đoán và biểu diễn từng câu (``preds-<tag>.npz``), lịch
sử mất mát và điểm (``cls-<tag>.json``), và model để gọi lại (``model-<tag>/``).
"""

from __future__ import annotations

import json
import os
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np

from .labels import label_key, load_splits

ENCODERS = {
    "phobert": "vinai/phobert-base-v2",
    "xlmr": "FacebookAI/xlm-roberta-base",
    "visobert": "uitnlp/visobert",
    "bamibert": "Qualcomm-AI-Research/BamiBERT",
}
BASELINE = "tfidf"
ALL_MODELS = (*ENCODERS, BASELINE)

DISPLAY = {
    "phobert": "PhoBERT-v2",
    "xlmr": "XLM-R base",
    "visobert": "ViSoBERT",
    "bamibert": "BamiBERT",
    "tfidf": "TF-IDF + SVC",
}

MAX_LENGTH = 48
LORA_RANK = 16


def load_tokenizer(name: str):
    """Nạp tokenizer, kèm đường vòng cho model không công bố cấu hình tokenizer.

    Một trong bốn model không nạp được qua ``AutoTokenizer``. Tệp ``tokenizer.json``
    của nó bọc trực tiếp được và round-trip sạch, nên đường vòng chỉ bỏ qua lớp cấu
    hình thiếu, không đổi cách cắt từ.
    """
    from transformers import AutoTokenizer

    try:
        return AutoTokenizer.from_pretrained(name)
    except Exception:
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer
        from transformers import PreTrainedTokenizerFast

        tokenizer = PreTrainedTokenizerFast(
            tokenizer_object=Tokenizer.from_file(hf_hub_download(name, "tokenizer.json")))
        tokenizer.pad_token = tokenizer.pad_token or "<pad>"
        return tokenizer


def _write(out_dir: Path, tag: str, labels, rows, result, preds, vectors):
    dump = {"labels": [label_key(l) for l in labels]}
    for split in ("val", "test"):
        dump[f"{split}_pred"] = np.array(preds[split])
        dump[f"{split}_gold"] = np.array([r["y"] for r in rows[split]])
        dump[f"{split}_vec"] = vectors[split]
        dump[f"{split}_register"] = np.array([r["register"] for r in rows[split]])
        dump[f"{split}_family"] = np.array([r["query_id"] for r in rows[split]])
    np.savez_compressed(out_dir / f"preds-{tag}.npz", **dump)
    json.dump(result, open(out_dir / f"cls-{tag}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def _tally(rows, preds):
    hit, tot = Counter(), Counter()
    for row, pred in zip(rows, preds):
        scope = "ngoài phạm vi" if row["query_id"] == "no-information" else "trong phạm vi"
        for key in ("tất cả", scope, row["register"]):
            tot[key] += 1
            hit[key] += pred == row["y"]
    return {k: {"correct": hit[k], "count": tot[k]} for k in tot}


def train_baseline(rows, labels, out_dir: Path, seed: int = 1):
    """Baseline: TF-IDF ký tự và từ, phân loại tuyến tính.

    Dùng n-gram ký tự vì tiếng Việt trong tập này có cả câu mất dấu và sai chính
    tả; n-gram ký tự bắt được phần trùng mặt chữ mà n-gram từ bỏ lỡ.
    """
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import make_pipeline, make_union
    from sklearn.svm import LinearSVC

    print(f"\n{'=' * 70}\n{BASELINE}  ({DISPLAY[BASELINE]})\n{'=' * 70}")
    features = make_union(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True),
        TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1, sublinear_tf=True))
    model = make_pipeline(features, LinearSVC(C=1.0, random_state=seed))

    start = time.time()
    model.fit([r["input"] for r in rows["train"]], [r["y"] for r in rows["train"]])
    seconds = round(time.time() - start)

    matrix = features.transform([r["input"] for r in rows["train"]])
    reducer = TruncatedSVD(n_components=128, random_state=seed).fit(matrix)
    print(f"  {matrix.shape[1]} đặc trưng · huấn luyện {seconds}s")

    result = {"model": "TF-IDF char+word n-gram + LinearSVC", "labels": len(labels),
              "seconds": seconds, "history": []}
    preds, vectors = {}, {}
    for split in ("val", "test"):
        texts = [r["input"] for r in rows[split]]
        preds[split] = model.predict(texts).tolist()
        vectors[split] = reducer.transform(features.transform(texts)).astype(np.float32)
        result[split] = _tally(rows[split], preds[split])
        print(f"  {split}: " + "   ".join(
            f"{k} {100*result[split][k]['correct']/result[split][k]['count']:.1f}%"
            for k in ("trong phạm vi", "ngoài phạm vi")))
    _write(out_dir, BASELINE, labels, rows, result, preds, vectors)
    return result


def train_encoder(tag, rows, labels, out_dir: Path, *, epochs=32, batch=32,
                  lr=2e-4, seed=1):
    """Tinh chỉnh một bộ mã hoá bằng LoRA, cộng một lớp phân loại học từ đầu."""
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader
    from transformers import AutoModel
    from peft import LoraConfig, get_peft_model

    name = ENCODERS[tag]
    torch.manual_seed(seed)
    random.seed(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    tokenizer = load_tokenizer(name)
    base = AutoModel.from_pretrained(name)
    bert = get_peft_model(base, LoraConfig(
        r=LORA_RANK, lora_alpha=2 * LORA_RANK, lora_dropout=0.05,
        target_modules=["query", "value"], bias="none")).to(device)
    head = nn.Linear(base.config.hidden_size, len(labels)).to(device)
    trainable = [p for p in list(bert.parameters()) + list(head.parameters())
                 if p.requires_grad]

    print(f"\n{'=' * 70}\n{tag}  ({name})\n{'=' * 70}")
    print(f"  {base.config.num_hidden_layers} lớp · {base.config.hidden_size} chiều · "
          f"từ điển {base.config.vocab_size} · "
          f"{sum(p.numel() for p in base.parameters())/1e6:.0f}M tham số, "
          f"học {sum(p.numel() for p in trainable)/1e6:.2f}M")

    opt = torch.optim.AdamW(trainable, lr=lr, fused=True)
    loader = DataLoader(rows["train"], batch_size=batch, shuffle=True,
                        collate_fn=lambda b: b, drop_last=True)
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, lr, total_steps=epochs * len(loader), pct_start=0.1)

    def encode(texts):
        batch_ = tokenizer(texts, padding=True, truncation=True,
                           max_length=MAX_LENGTH, return_tensors="pt")
        return {k: v.to(device) for k, v in batch_.items()}

    def pooled_logits(chunk):
        enc = encode([r["input"] for r in chunk])
        hidden = bert(**enc).last_hidden_state
        mask = enc["attention_mask"].unsqueeze(-1).to(hidden.dtype)
        pooled = (hidden * mask).sum(1) / mask.sum(1)
        return pooled, head(pooled)

    @torch.no_grad()
    def run(split):
        bert.eval()
        loss_sum, preds, vecs = 0.0, [], []
        for i in range(0, len(rows[split]), 128):
            chunk = rows[split][i:i + 128]
            with torch.autocast("cuda", dtype=torch.bfloat16):
                pooled, logits = pooled_logits(chunk)
            logits = logits.float()
            target = torch.tensor([r["y"] for r in chunk], device=device)
            loss_sum += F.cross_entropy(logits, target, reduction="sum").item()
            preds += logits.argmax(1).tolist()
            vecs.append(pooled.float().cpu())
        bert.train()
        return loss_sum / len(rows[split]), preds, torch.cat(vecs).numpy()

    history, start = [], time.time()
    for epoch in range(1, epochs + 1):
        running = 0.0
        for chunk in loader:
            with torch.autocast("cuda", dtype=torch.bfloat16):
                _, logits = pooled_logits(chunk)
                loss = F.cross_entropy(
                    logits.float(), torch.tensor([r["y"] for r in chunk], device=device))
            loss.backward()
            opt.step()
            sched.step()
            opt.zero_grad(set_to_none=True)
            running += loss.item()
        val_loss, val_pred, _ = run("val")
        history.append({"epoch": epoch, "train_loss": round(running / len(loader), 4),
                        "val_loss": round(val_loss, 4)})
        if epoch % 8 == 0:
            acc = np.mean([p == r["y"] for p, r in zip(val_pred, rows["val"])])
            print(f"  epoch {epoch:>3}  train {running/len(loader):.4f}  "
                  f"val {val_loss:.4f}  acc {100*acc:.1f}%  ({time.time()-start:.0f}s)")

    result = {"model": name, "labels": len(labels),
              "seconds": round(time.time() - start), "history": history}
    preds, vectors = {}, {}
    for split in ("val", "test"):
        _, preds[split], vectors[split] = run(split)
        result[split] = _tally(rows[split], preds[split])
        print(f"  {split}: " + "   ".join(
            f"{k} {100*result[split][k]['correct']/result[split][k]['count']:.1f}%"
            for k in ("trong phạm vi", "ngoài phạm vi")))
    _write(out_dir, tag, labels, rows, result, preds, vectors)

    save_dir = out_dir / f"model-{tag}"
    os.makedirs(save_dir, exist_ok=True)
    bert.save_pretrained(save_dir)
    tokenizer.save_pretrained(save_dir)
    torch.save(head.state_dict(), save_dir / "head.pt")
    json.dump({"base_model": name, "labels": [label_key(l) for l in labels]},
              open(save_dir / "labels.json", "w", encoding="utf-8"), ensure_ascii=False)

    del bert, head, opt
    torch.cuda.empty_cache()
    return result

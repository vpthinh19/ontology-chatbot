"""Đẩy mô hình CT2 (deploy) lên Hugging Face Hub.

    HF_TOKEN=hf_xxx uv run --extra train python -m ontchatbot.scripts.upload_hf \
        [--model-dir artifacts/models/bartpho_ct2] [--repo vpthinh19/bartpho-ontology] [--private]

Mục đích (Phase 7): sau khi train → convert_ct2, đẩy thư mục CT2 lên HF để:
1. **Inference trực tiếp KHÔNG cần train** — ``model.py`` thiếu CT2 cục bộ sẽ ``snapshot_download``
   từ repo này (``config.FINETUNED_MODEL_NAME``).
2. **CI/CD** — GitHub Action kéo model này về rồi đóng Docker (``.github/workflows/build-docker.yml``).

Token đọc từ ``--token`` hoặc env ``HF_TOKEN`` (tạo ở https://huggingface.co/settings/tokens, quyền write).
``huggingface_hub`` có sẵn qua ``--extra train``. Chỉ đẩy CT2 (~400MB int8), KHÔNG đẩy model HF safetensors nặng.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ..config import CT2_MODEL_DIR, FINETUNED_MODEL_NAME

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Upload CT2 model → Hugging Face Hub")
    p.add_argument("--model-dir", default=str(CT2_MODEL_DIR), help="thư mục CT2 (mặc định config.CT2_MODEL_DIR)")
    p.add_argument("--repo", default=FINETUNED_MODEL_NAME, help="repo_id HF (mặc định config.FINETUNED_MODEL_NAME)")
    p.add_argument("--token", default=os.environ.get("HF_TOKEN"), help="HF write token (hoặc env HF_TOKEN)")
    p.add_argument("--private", action="store_true", help="tạo repo riêng tư")
    p.add_argument("--commit-message", default="upload CT2 int8 model (deploy)")
    args = p.parse_args()

    md = Path(args.model_dir)
    if not (md / "model.bin").exists():
        sys.exit(f"[upload] ⛔ {md} không có model.bin — chạy convert_ct2 trước khi upload.")
    if not args.token:
        sys.exit("[upload] ⛔ thiếu token — đặt env HF_TOKEN hoặc truyền --token (cần quyền write).")

    from huggingface_hub import HfApi
    api = HfApi(token=args.token)
    api.create_repo(args.repo, repo_type="model", private=args.private, exist_ok=True)
    print(f"[upload] đẩy {md} ({_dir_size_mb(md):.0f} MB) → {args.repo} …")
    api.upload_folder(folder_path=str(md), repo_id=args.repo, repo_type="model",
                      commit_message=args.commit_message)
    print(f"[upload] ✅ xong → https://huggingface.co/{args.repo}")


def _dir_size_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6


if __name__ == "__main__":
    main()

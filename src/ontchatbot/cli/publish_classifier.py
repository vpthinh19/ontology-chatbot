"""Đẩy đồ thị phân loại lên kho phát hành, rồi kiểm lại bằng mã băm.

Kho trên Hugging Face là kênh triển khai: ảnh Docker tải model từ đó lúc dựng, nên
kho lệch với model đã chấm điểm nghĩa là bản chạy thật khác bản được báo cáo, mà
nhìn từ ngoài không thấy gì bất thường.

Kích thước tệp không đủ để phát hiện chuyện đó - hai bản xuất của hai lượt huấn
luyện khác nhau có cùng kiến trúc thì bằng nhau đến từng byte về cỡ. Vì vậy sau khi
đẩy, lệnh này đọc mã băm mà kho khai cho từng tệp rồi so với mã băm tính tại máy, và
báo lỗi nếu lệch. Tệp lớn được kho lưu qua LFS và khai sẵn sha256; tệp nhỏ nằm thẳng
trong git nên so bằng mã băm blob của git.

Lệnh in ra mã commit sau khi đẩy. Đó là thứ cần ghim vào quy trình dựng ảnh, vì tên
nhánh còn di chuyển được còn mã commit thì không.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

DEFAULT_MODEL_DIR = Path("artifacts/entity-linking/onnx-xlmr")
DEFAULT_PATH_IN_REPO = "onnx-xlmr"

#: Đồ thị đã xuất phải khép kín: trọng số, bộ tách từ và bảng nhãn. Thiếu một tệp
#: thì ảnh triển khai dựng xong vẫn hỏng lúc khởi động chứ không hỏng lúc dựng.
#:
#: Đồ thị đã hợp nhất nằm trong danh sách dù dịch vụ vẫn chạy khi thiếu nó: lúc
#: đó dịch vụ chỉ khởi động chậm hơn, và không ai nhìn thấy nếu không chặn ở đây.
REQUIRED = (
    "classifier.onnx",
    "classifier.onnx.data",
    "classifier.optimized.onnx",
    "labels.json",
    "tokenizer.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_id(path: Path) -> str:
    """Mã băm mà git đặt cho nội dung tệp, dùng cho tệp không đi qua LFS."""
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def validate_model_directory(model_dir: Path) -> list[Path]:
    missing = [name for name in REQUIRED if not (model_dir / name).is_file()]
    if missing:
        raise SystemExit(f"thiếu tệp trong {model_dir}: {', '.join(missing)}")
    return [model_dir / name for name in REQUIRED]


def validate_onnx_model(model_dir: Path) -> int:
    """Chạy thử một câu để không đẩy lên một đồ thị hỏng.

    Nạp bằng đúng lớp mà dịch vụ dùng, nên lỗi nào chặn dịch vụ khởi động thì cũng
    chặn ở đây. Không cần đồ thị ontology: bước này chỉ hỏi model có chọn được nhãn.
    """
    from ..runtime.onnx_classifier import OnnxClassifierGenerator

    generator = OnnxClassifierGenerator.load(model_dir)
    generator.generate("điều kiện xét học bổng")
    return len(generator.labels)


def remote_hashes(api, repo: str, revision: str) -> dict[str, tuple[str, str]]:
    """Mã băm kho khai cho từng tệp: ``{đường dẫn: (kiểu, mã băm)}``."""
    info = api.model_info(repo, revision=revision, files_metadata=True)
    hashes = {}
    for file_info in info.siblings:
        if file_info.lfs is not None:
            hashes[file_info.rfilename] = ("sha256", file_info.lfs.sha256)
        elif file_info.blob_id is not None:
            hashes[file_info.rfilename] = ("blob", file_info.blob_id)
    return hashes


def compare_remote_files(
    local_files: list[Path], remote_files: dict, path_in_repo: str
) -> list[str]:
    """Trả về danh sách lệch; rỗng nghĩa là kho mang đúng nội dung vừa đẩy."""
    mismatches = []
    for file_path in local_files:
        key = f"{path_in_repo}/{file_path.name}" if path_in_repo else file_path.name
        if key not in remote_files:
            mismatches.append(f"{key}: kho không có tệp này")
            continue
        hash_type, remote_hash = remote_files[key]
        local_hash = (
            sha256_file(file_path)
            if hash_type == "sha256"
            else git_blob_id(file_path)
        )
        marker = "khớp" if local_hash == remote_hash else "LỆCH"
        print(f"  {marker:<6} {key:<34} {hash_type} {remote_hash[:16]}…")
        if local_hash != remote_hash:
            mismatches.append(f"{key}: kho {remote_hash}, tại máy {local_hash}")
    return mismatches


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--repo", required=True, help="ví dụ: tên-tài-khoản/tên-kho")
    parser.add_argument("--path-in-repo", default=DEFAULT_PATH_IN_REPO,
                        help="thư mục đích trong kho; để rỗng là đẩy vào gốc kho")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--message", default="Publish the FP16 ONNX classifier graph")
    parser.add_argument("--private", action="store_true",
                        help="tạo kho ở chế độ riêng tư nếu kho chưa tồn tại")
    parser.add_argument("--dry-run", action="store_true",
                        help="kiểm tệp và mã băm tại máy rồi dừng, không đẩy gì lên")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    local_files = validate_model_directory(args.model_dir)

    total_bytes = sum(file_path.stat().st_size for file_path in local_files)
    print(f"{args.model_dir} · {len(local_files)} tệp · {total_bytes / 1e9:.2f} GB")
    print(
        f"đồ thị chạy được trên CPU, "
        f"{validate_onnx_model(args.model_dir)} nhãn\n"
    )
    for file_path in local_files:
        print(
            f"  {file_path.name:<24} {file_path.stat().st_size:>13,} B  "
            f"sha256 {sha256_file(file_path)[:16]}…"
        )

    if args.dry_run:
        print("\n--dry-run: dừng trước khi đẩy")
        return

    from huggingface_hub import HfApi

    api = HfApi()
    who = api.whoami()
    print(f"\nđang đăng nhập với tài khoản {who['name']}")
    api.create_repo(args.repo, repo_type="model", private=args.private, exist_ok=True)
    commit = api.upload_folder(
        repo_id=args.repo,
        repo_type="model",
        folder_path=str(args.model_dir),
        path_in_repo=args.path_in_repo,
        revision=args.revision,
        commit_message=args.message,
    )

    print("\nđối chiếu mã băm kho khai với mã băm tính tại máy:")
    mismatches = compare_remote_files(
        local_files,
        remote_hashes(api, args.repo, args.revision),
        args.path_in_repo,
    )
    if mismatches:
        print("\n".join(f"  {line}" for line in mismatches), file=sys.stderr)
        raise SystemExit("kho KHÔNG mang đúng nội dung vừa đẩy")

    sha = getattr(commit, "oid", None) or api.model_info(args.repo, revision=args.revision).sha
    print(f"\nxong. Ghim mã commit này vào quy trình dựng ảnh:\n  {args.repo}@{sha}")


if __name__ == "__main__":
    main()

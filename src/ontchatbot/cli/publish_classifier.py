"""Đẩy đồ thị phân loại lên kho phát hành, rồi kiểm lại bằng mã băm.

Kho trên Hugging Face là kênh triển khai: ảnh Docker tải model từ đó lúc dựng, nên
kho lệch với model đã chấm điểm nghĩa là bản chạy thật khác bản được báo cáo, mà
nhìn từ ngoài không thấy gì bất thường.

Kích thước tệp không đủ để phát hiện chuyện đó — hai bản xuất của hai lượt huấn
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
REQUIRED = ("classifier.onnx", "classifier.onnx.data", "labels.json", "tokenizer.json")


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


def kiem_thu_muc(model_dir: Path) -> list[Path]:
    thieu = [ten for ten in REQUIRED if not (model_dir / ten).is_file()]
    if thieu:
        raise SystemExit(f"thiếu tệp trong {model_dir}: {', '.join(thieu)}")
    return [model_dir / ten for ten in REQUIRED]


def kiem_do_thi_chay_duoc(model_dir: Path) -> int:
    """Chạy thử một câu để không đẩy lên một đồ thị hỏng.

    Nạp bằng đúng lớp mà dịch vụ dùng, nên lỗi nào chặn dịch vụ khởi động thì cũng
    chặn ở đây. Không cần đồ thị ontology: bước này chỉ hỏi model có chọn được nhãn.
    """
    from ..runtime.onnx_classifier import OnnxClassifierGenerator

    generator = OnnxClassifierGenerator.load(model_dir, device="cpu")
    generator.generate("điều kiện xét học bổng")
    return len(generator.labels)


def ma_bam_tren_kho(api, repo: str, revision: str) -> dict[str, tuple[str, str]]:
    """Mã băm kho khai cho từng tệp: ``{đường dẫn: (kiểu, mã băm)}``."""
    info = api.model_info(repo, revision=revision, files_metadata=True)
    ket_qua = {}
    for tep in info.siblings:
        if tep.lfs is not None:
            ket_qua[tep.rfilename] = ("sha256", tep.lfs.sha256)
        elif tep.blob_id is not None:
            ket_qua[tep.rfilename] = ("blob", tep.blob_id)
    return ket_qua


def doi_chieu(tep_local: list[Path], tren_kho: dict, path_in_repo: str) -> list[str]:
    """Trả về danh sách lệch; rỗng nghĩa là kho mang đúng nội dung vừa đẩy."""
    lech = []
    for tep in tep_local:
        khoa = f"{path_in_repo}/{tep.name}" if path_in_repo else tep.name
        if khoa not in tren_kho:
            lech.append(f"{khoa}: kho không có tệp này")
            continue
        kieu, tren = tren_kho[khoa]
        duoi = sha256_file(tep) if kieu == "sha256" else git_blob_id(tep)
        dau = "khớp" if duoi == tren else "LỆCH"
        print(f"  {dau:<6} {khoa:<34} {kieu} {tren[:16]}…")
        if duoi != tren:
            lech.append(f"{khoa}: kho {tren}, tại máy {duoi}")
    return lech


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--repo", required=True, help="ví dụ: tên-tài-khoản/tên-kho")
    parser.add_argument("--path-in-repo", default=DEFAULT_PATH_IN_REPO,
                        help="thư mục đích trong kho; để rỗng là đẩy vào gốc kho")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--message", default="Publish the ONNX classifier graph")
    parser.add_argument("--private", action="store_true",
                        help="tạo kho ở chế độ riêng tư nếu kho chưa tồn tại")
    parser.add_argument("--dry-run", action="store_true",
                        help="kiểm tệp và mã băm tại máy rồi dừng, không đẩy gì lên")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    tep_local = kiem_thu_muc(args.model_dir)

    tong = sum(tep.stat().st_size for tep in tep_local)
    print(f"{args.model_dir} · {len(tep_local)} tệp · {tong / 1e9:.2f} GB")
    print(f"đồ thị chạy được, {kiem_do_thi_chay_duoc(args.model_dir)} nhãn\n")
    for tep in tep_local:
        print(f"  {tep.name:<24} {tep.stat().st_size:>13,} B  sha256 {sha256_file(tep)[:16]}…")

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
    lech = doi_chieu(tep_local, ma_bam_tren_kho(api, args.repo, args.revision),
                     args.path_in_repo)
    if lech:
        print("\n".join(f"  {dong}" for dong in lech), file=sys.stderr)
        raise SystemExit("kho KHÔNG mang đúng nội dung vừa đẩy")

    sha = getattr(commit, "oid", None) or api.model_info(args.repo, revision=args.revision).sha
    print(f"\nxong. Ghim mã commit này vào quy trình dựng ảnh:\n  {args.repo}@{sha}")


if __name__ == "__main__":
    main()

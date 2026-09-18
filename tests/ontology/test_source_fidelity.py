"""Bảng trong ontology phải chép đúng từng ô của văn bản gốc.

Bảng được trả nguyên khối cho mô hình ngôn ngữ, nên một ô lệch là một câu trả lời sai.
``references/`` giữ bản chép Markdown của các văn bản gốc để đối chiếu.
"""

from __future__ import annotations

import pyoxigraph as oxi

from ontchatbot.settings import ONTOLOGY_NS, ONTOLOGY_PATH, PROJECT_ROOT

#: Mỗi bảng của ontology và nơi chép nó trong ``references/``. Khoá là tên mục trong
#: ``ontology.trig``; giá trị là tệp nguồn và dòng đầu của bảng trong tệp đó.
VERBATIM_TABLE_SOURCES = {
    # Các mức học bổng dẫn đến đúng bảng chứa số tiền.
    "BangMucHocBongChuongTrinhChuan": (
        "Qd317.md",
        "| STT | Xếp loại học bổng | Học bổng 05 tháng / học kỳ (VNĐ) |",
    ),
    "BangMucHocBongChuongTrinhDacBiet": (
        "Qd317.md",
        "| STT | Xếp loại học bổng | Học bổng 05 tháng - chương trình đào tạo đặc biệt / học kỳ (VNĐ) |",
    ),
    "BangXepLoaiHocLuc": (
        "Qd1052.md",
        "| **Điểm trung bình chung** | **Mức xếp loại** |",
    ),
    "BangXepTrinhDoNamHoc": (
        "Qd1052.md",
        "| **TT** | **Số tín chỉ đã tích lũy** | **Xếp trình độ năm học** |",
    ),
    "BangXepHangTotNghiep": (
        "Qd1052.md",
        "| **TT.** | **Điểm trung bình chung tích lũy của toàn khoá** | **Xếp loại** |",
    ),
    "BangSiSoLopHocPhan": (
        "Qd1052.md",
        "| **TT** | **Học phần** | **Số lượng sinh viên** | |",
    ),
    # Bốn bảng Phụ lục 2 chép lại từ bản scan ngày 13/9/2026 (xem ghi chú trong ``Qd1052.md``).
    "BangQuyDoiChungChiTiengAnhChuongTrinhChuan": (
        "Qd1052.md",
        "| Khung NLNN 6 bậc | CEFR | TOEIC | TOEFL (iBT) | IELTS | Linguaskill | Aptis (General) | Cambridge English Scale | Quy đổi thành điểm 10 (Thang điểm 10) |",
    ),
    "BangQuyDoiNgoaiNguKhacChuongTrinhChuan": (
        "Qd1052.md",
        "| Khung NLNN 6 bậc | Tiếng Trung (HSK) | Tiếng Trung (TOCFL) | Tiếng Nhật (JLPT) | Tiếng Nhật (JPT) | Tiếng Nga (TPKN) | Tiếng Pháp (DELF) | Tiếng Pháp (TCF) | Tiếng Hàn (TOPIK) | Tiếng Hàn (KLPT) | Quy đổi thành điểm 10 (Thang điểm 10) |",
    ),
    "BangChuanTiengAnhChuongTrinhDacBiet": (
        "Qd1052.md",
        "| TT | Chương trình | KNLNN / CEFR | TOEIC | IELTS | TOEFL iBT | Linguaskill | Aptis (General) | Cambridge English Scale |",
    ),
    "BangChuanNgoaiNguKhacChuongTrinhDacBiet": (
        "Qd1052.md",
        "| TT | Chương trình | Tiếng Trung (HSK) | Tiếng Trung (TOCFL) | Tiếng Nhật (JLPT) | Tiếng Nhật (JPT) | Tiếng Nga (TPKN) | Tiếng Pháp (DELF) | Tiếng Pháp (TCF) | Tiếng Hàn (TOPIK) |",
    ),
    "BangQuyDoiNgoaiNguHaiNganhNgonNguAnh": (
        "Qd1052.md",
        "| Khung NLNN 6 bậc | Tiếng Trung (HSK) | Tiếng Trung (TOCFL) | Tiếng Nhật (JLPT) | Tiếng Nhật (JPT) | Tiếng Nga (TPKN) | Tiếng Pháp (DELF) | Tiếng Pháp (TCF) | Tiếng Hàn (TOPIK) | Tiếng Hàn (KLPT) | Quy đổi thành điểm 10 cho các cấp độ HP |",
    ),
    "DanhMucVietTatChungChiNgoaiNgu": (
        "Qd1052.md",
        "| TT | Ngoại ngữ | Từ viết tắt | Viết đầy đủ |",
    ),
    "BangQuyDoiChungChiTinHoc": (
        "Qd1052.md",
        "| TT | Điểm IC3 | Điểm ICDL | Điểm MOS | Điểm quy đổi / Điểm thưởng |",
    ),
    "DanhMucHocPhanNgoaiNgu": (
        "Qd1965.md",
        "| STT | Học phần | Tín chỉ | Khung NLNN tương ứng | Khóa 67 trở về trước | Khóa 68 trở đi |",
    ),
    "BangDanhGiaHocPhanNgoaiNgu": (
        "Qd1965.md",
        "| STT | Học phần | Thành phần đánh giá | Tỷ trọng |",
    ),
    "DanhMucNganhDaoTaoTheoKhoiNganh": (
        "Qd729.md",
        "| **TT** | **Tên ngành đào tạo** |",
    ),
    "BangKhungXuLyKyLuatNguoiHoc": (
        "Qd1351.md",
        "| STT | Nội dung vi phạm | Nhắc nhở | Khiển trách | Cảnh cáo | Đình chỉ học tập có thời hạn | Buộc thôi học | Ghi chú |",
    ),
    "BangChuanDauRaNgoaiNguChuongTrinhDaoTaoDaiHocKhongChuyenNgu": (
        "Qd1128.md",
        "| TT | Trình độ, ngành, chuyên ngành đào tạo | Khóa tuyển sinh 60 | Khóa tuyển sinh 61 trở đi | Ghi chú |",
    ),
    "BangChuanDauRaNgoaiNguDaiHocLienThongBang2": (
        "Tb106.md",
        "| STT | Tên ngành, chuyên ngành đào tạo | Khóa tuyển sinh K60 | Khóa tuyển sinh K61 trở đi |",
    ),
    "ChuanDauRaNgoaiNguThuHaiChoSinhVienNganhNgonNguAnh": (
        "Qd507.md",
        "| TT | Trình độ | Chuẩn đầu ra |",
    ),
    "DanhMucNganhDaoTaoDuocApDungChinhSachHocBongTheoNghiDinh1792026NdCp": (
        "Qd1826.md",
        "| STT | Nhóm ngành/ Mã ngành* | Tên ngành đào tạo |",
    ),
}


def _markdown_table_at(source: str, header: str) -> str:
    """Đọc nguyên khối Markdown từ dòng đầu, giữ cả ô rỗng và hàng căn lề."""

    lines = source.splitlines()
    start = lines.index(header)

    rows: list[str] = []
    while start < len(lines) and lines[start].startswith("|"):
        rows.append(lines[start])
        start += 1
    return "\n".join(rows)


def test_all_tables_are_copied_cell_for_cell_from_their_sources() -> None:
    """Mỗi bảng khớp nguồn từng ký tự, và mỗi mục bảng mang đúng một bảng.

    Bảng là giá trị ``noiDung`` mở đầu bằng ``|``. Mọi bảng có trong ontology phải
    nằm trong danh sách trên, nên thêm bảng mới mà quên nơi chép thì phép kiểm hỏng.
    """

    store = oxi.Store()
    store.load(path=str(ONTOLOGY_PATH), format=oxi.RdfFormat.TRIG)
    noi_dung = oxi.NamedNode(ONTOLOGY_NS + "noiDung")

    def tables_of(subject):
        return {
            quad.object.value
            for quad in store.quads_for_pattern(subject, noi_dung, None, None)
            if quad.object.value.startswith("|")
        }

    mismatches = []
    for local_name, (source_name, header) in VERBATIM_TABLE_SOURCES.items():
        source = (PROJECT_ROOT / "references" / source_name).read_text(encoding="utf-8")
        expected = _markdown_table_at(source, header)
        actual = tables_of(oxi.NamedNode(ONTOLOGY_NS + local_name))
        if actual != {expected}:
            mismatches.append(local_name)

    actual_tables = {
        quad.subject.value.rsplit("#", 1)[-1]
        for quad in store.quads_for_pattern(None, noi_dung, None, None)
        if quad.object.value.startswith("|")
    }
    assert actual_tables == set(VERBATIM_TABLE_SOURCES)
    assert mismatches == []

"""Chuyển ontology.ttl sang kiến trúc mới: TriG, nguồn theo túi, IRI tiếng Việt.

Ba việc cùng lúc, cố ý gộp vào một bước vì chúng phụ thuộc nhau:

1. **Tầng nguồn thay cho cây văn bản.** Chương/Điều/Khoản/Điểm thôi làm cá thể.
   Mỗi phần văn bản từng được dẫn trở thành một *địa chỉ trích dẫn* hai ô, trỏ về
   một *nguồn thô*. Cặp Quyết định/Quy chế gộp làm một bản ghi.
2. **Nguồn gắn vào câu, không gắn vào node.** Mỗi phát biểu nằm trong cái túi mang
   tên địa chỉ trích dẫn đã khẳng định nó. Câu không có nguồn nằm ngoài mọi túi.
3. **Bỏ node trung gian.** Bước, điều kiện, kết quả, thời hạn, hệ quả, cách giải
   quyết đều tan thành phát biểu của chính thực thể chứa chúng.

IRI đổi sang tiếng Việt không dấu, sinh máy móc từ ``rdfs:label``. Bảng đối chiếu
cũ-mới ghi ra ``iri-mapping.json`` để bộ kiểm tra tra cứu dò lại được.

    python resources/ontology/convert_to_trig.py
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from ontchatbot.settings import ONTOLOGY_NS

#: Bộ chuyển đổi đọc ontology CŨ bằng rdflib nên tự khai từ vựng của mình, không
#: mượn của gói search - gói đó nay chỉ nói tiếng của mô hình mới.
ACADEMIC = Namespace(ONTOLOGY_NS)


def local_name(iri) -> str:
    text = str(iri)
    return text.rsplit("#", 1)[-1] if "#" in text else text.rsplit("/", 1)[-1]

HERE = Path(__file__).parent
NGUON_TTL = HERE / "ontology.ttl"
DICH_TRIG = HERE / "ontology.trig"
BANG_DOI = HERE / "iri-mapping.json"
BAO_CAO = HERE / "conversion-report.md"
SUA_CHUA = HERE / "repairs.json"
DA_DUYET = HERE / "reviewed.json"

NS = str(ACADEMIC)

# --- thuộc tính: cái nào tan, cái nào đổi vai ---------------------------------

#: Gộp hết về :noiDung. Nội dung là nội dung, không phân loại theo lớp sở hữu.
VAN_BAN = {
    "summaryText", "stepText", "requirementText", "ruleText", "outcomeText",
    "deadlineText", "caseText", "consequenceText", "conditionText", "definitionText",
    "criterionText", "assessmentText", "feePolicyText",
    "verbatimTableText", "listedTitle",
}
#: Câu mô tả do ta viết để giới thiệu thực thể. Không văn bản nào chứa câu này,
#: nên nó nằm NGOÀI mọi túi - nói được, nhưng không trích dẫn được. Gắn nó vào
#: túi còn làm nó bị nhân lên khi thực thể dẫn nhiều nguồn.
MO_TA = {"summaryText"}
#: Dựng nên tầng nguồn, không còn là dữ kiện.
NGUON_HOC = {"basedOn", "citationLabel", "documentUrl", "webPageUrl", "inDocument", "partOf"}
#: Toạ độ trong văn bản: đi vào chuỗi :toaDo, không còn là ô riêng.
TOA_DO = {"articleNumber", "clauseNumber", "pointLetter", "chapterNumber", "appendixNumber"}
#: Node trung gian tan đi nên thứ tự và quan hệ chứa cũng tan theo.
TAN_DI = {"hasStep", "hasRequirement", "hasDeadline", "hasOutcome", "hasConsequence",
          "hasResolution", "stepOrder", "requirementOrder", "officialText", "issuedBy",
          "headingText"}
#: Lớp chỉ tồn tại để treo một câu; tan vào thực thể chứa nó.
LOP_TRUNG_GIAN = {"ProcedureStep", "Requirement", "Outcome", "Deadline", "Consequence", "CaseResolution"}
#: Lớp của tầng văn bản: thành địa chỉ trích dẫn, không còn là cá thể.
#: Bảng KHÔNG nằm đây - chúng mang nội dung thật và có altLabel do người thêm để
#: tra cứu, nên là thực thể tri thức dù nằm trong văn bản.
LOP_VAN_BAN = {"Chapter", "Article", "Clause", "Point", "Appendix", "DocumentSection",
               "DocumentPart"}
#: Thực thể vừa mang nội dung vừa là một chỗ trong văn bản: túi của chúng là địa
#: chỉ trích dẫn của chính chúng.
LOP_TU_LAM_NGUON = {"DocumentTable", "CertificateConversionTable"}
#: Lớp của nguồn thô.
LOP_NGUON = {"Decision", "Regulation", "GuidanceDocument", "FormCatalogue", "OfficialDocument"}
#: Bị xếp nhầm thành văn bản. Thật ra là hệ thống trực tuyến sinh viên dùng hằng
#: ngày - dấu hiệu nhận ra: chúng có tên gọi phụ do người thêm để tra cứu, và
#: chúng không cấp nội dung cho bất kỳ câu nào.
KHONG_PHAI_NGUON = {
    "TuitionLookupPage": "HeThongTrucTuyen",
    "AdmissionsLookupPage": "HeThongTrucTuyen",
}

#: Lớp chỉ khác nhau ở một hai ô số hoặc không khác gì: gộp thành một lớp, phân
#: biệt bằng một ô "loại". IRI của lớp cũ trở thành GIÁ TRỊ của ô đó, nên nhãn cũ
#: giữ nguyên và câu trả lời vẫn nói được đó là quy tắc gì, chứng chỉ loại nào.
#: Khoá là tên lớp sinh từ nhãn tiếng Việt.
GOP_LOP: dict[str, tuple[str, str]] = {}
for _lop_chung, _o_loai, _cac_lop in (
    ("QuyTac", "loaiQuyTac",
     ("QuyTacHocVu", "QuyTacBuocThoiHoc", "QuyTacCanhBaoKetQuaHocTap", "QuyTacDieuKienDuThi",
      "QuyTacGioiHanCongNhanVaChuyenDoiTinChi", "QuyTacHaHangTotNghiep",
      "QuyTacKhoiLuongDangKyMoiHocKy", "QuyTacThoiGianDaoTao",
      "QuyTacTyLeDaoTaoTrucTuyen", "ChinhSachHocVu")),
    ("KhaiNiem", "loaiKhaiNiem",
     ("KhaiNiemHocVu", "LoaiHocPhan", "HinhThucDaoTao", "LoaiHocKy",
      "HinhThucToChucDayHoc", "ThanhPhanDanhGiaHocPhan")),
    # Học phần ngoại ngữ là môn học thật - có số tín chỉ, sinh viên đăng ký học,
    # nằm trong danh mục học phần - không phải một thuật ngữ được giải nghĩa.
    ("HocPhan", "", ("HocPhanNgoaiNgu",)),
    # Điểm chữ có ký hiệu riêng: đó là bảng mã, không phải khái niệm.
    ("DanhMuc", "loaiDanhMuc",
     ("NganHang", "KhoiNganh", "PhuongThucDongHocPhi", "DonViTinhHocPhi", "TrinhDoDaoTao",
      "DiemChu")),
    # Đơn vị trong trường vốn là lớp con của chủ thể; gộp cho nhất quán với các nhóm khác.
    ("ChuThe", "loaiChuThe", ("ChuTheThamGia", "DonViTrongTruong")),
    # Mức lệ phí và mức học bổng cùng là "một số tiền cho một nhóm đối tượng".
    # Trước đây lệ phí bị xếp vào quy tắc còn học bổng đứng riêng - không nhất quán.
    ("MucTien", "loaiMucTien", ("QuyTacLePhiDongHocPhi", "MucHocBongKhuyenKhichHocTap")),
    ("ChungChi", "loaiChungChi", ("ChungChi", "ChungChiNgoaiNgu", "ChungChiTinHoc")),
    ("Bang", "loaiBang", ("BangTrongTaiLieu", "BangQuyDoiChungChi")),
):
    for _lop in _cac_lop:
        GOP_LOP[_lop] = (_lop_chung, _o_loai)

#: Vài cá thể lạc lớp dù cả lớp thì đúng. Khoá là tên sinh từ nhãn.
DOI_LOP_CA_THE: dict[str, tuple[str, str, str]] = {
    # Đây là điều khoản quy định phạm vi áp dụng, không phải một thuật ngữ.
    "PhamViVaDoiTuongApDungCuaQuyChe": ("QuyTac", "loaiQuyTac", "QuyTacHocVu"),
    # Quy đổi giờ của một tín chỉ là một phần của định nghĩa tín chỉ.
    "QuyDoiGioHocCuaMotTinChi": ("KhaiNiem", "loaiKhaiNiem", "KhaiNiemHocVu"),
}

#: Nhãn tiếng Việt cho các lớp chung mới sinh ra khi gộp.
_NHAN_LOP_CHUNG = {
    "HeThongTrucTuyen": "Hệ thống trực tuyến",
    "QuyTac": "Quy tắc", "KhaiNiem": "Khái niệm", "DanhMuc": "Danh mục",
    "ChungChi": "Chứng chỉ", "Bang": "Bảng", "HocPhan": "Học phần",
    "ChuThe": "Chủ thể", "MucTien": "Mức tiền",
    "Nguon": "Nguồn", "DiaChiTrichDan": "Địa chỉ trích dẫn",
}

#: Thuộc tính do chính bộ chuyển đổi sinh ra nên không có nhãn trong ontology cũ.
_NHAN_THUOC_TINH_MOI = {
    "noiDung": "nội dung",
    "apDungChoTruongHop": "áp dụng cho trường hợp",
    "thuocNguon": "thuộc nguồn", "toaDo": "toạ độ", "soHieu": "số hiệu",
    "banHanhNgay": "ban hành ngày", "ngayThuThap": "ngày thu thập",
    "hieuLucTu": "hiệu lực từ", "hieuLucTuHocKy": "hiệu lực từ học kỳ",
    "duongDan": "đường dẫn", "loaiNguon": "loại nguồn", "suaDoiVanBan": "sửa đổi văn bản",
    "loaiQuyTac": "loại quy tắc", "loaiKhaiNiem": "loại khái niệm",
    "loaiDanhMuc": "loại danh mục", "loaiChungChi": "loại chứng chỉ",
    "loaiBang": "loại bảng", "loaiChuThe": "loại chủ thể", "loaiMucTien": "loại mức tiền",
}

VIET_TAT_TOA_DO = [
    ("Regulation", ""), ("Decision", ""), ("Article", "_D"), ("Clause", "K"),
    ("Point", "d"), ("Appendix", "_PL"), ("Chapter", "_C"),
]


def bo_dau(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))


def pascal(nhan: str) -> str:
    tu = re.findall(r"[A-Za-z0-9]+", bo_dau(nhan))
    return "".join(t if t.isdigit() else t[:1].upper() + t[1:].lower() for t in tu)


def camel(nhan: str) -> str:
    ten = pascal(nhan)
    return ten[:1].lower() + ten[1:]


class BoChuyenDoi:
    def __init__(self, graph: Graph) -> None:
        self.g = graph
        self.canh_bao: list[str] = []
        self.ghi_chu: list[str] = []
        self.gop_lop_da_dung: set[str] = set()
        #: lớp và thuộc tính - từ vựng, không phải thực thể tri thức
        self.tu_vung: set[str] = set()
        #: tên sinh từ nhãn lớp -> nhãn gốc, để giá trị của ô "loại" luôn có nhãn
        #: kể cả khi không cá thể nào còn mang lớp đó.
        self.nhan_lop = {pascal(self.nhan(lop)): self.nhan(lop)
                         for lop in graph.subjects(RDF.type, OWL.Class)}
        self.ten_moi: dict[URIRef, str] = {}
        self.cha: dict[URIRef, URIRef] = {}
        self._dung_ten: dict[str, URIRef] = {}
        self.nguon_cua_phan: dict[URIRef, URIRef] = {}   # phần văn bản -> nguồn thô gộp
        self.dia_chi: dict[URIRef, str] = {}             # phần văn bản -> IRI địa chỉ trích dẫn

    # --- tiện ích đọc --------------------------------------------------------

    def nhan(self, node: URIRef) -> str:
        return str(next(iter(sorted(self.g.objects(node, RDFS.label), key=str)), local_name(node)))

    def lop(self, node: URIRef) -> set[str]:
        return {local_name(c) for c in self.g.objects(node, RDF.type)} - {"NamedIndividual"}

    def mot(self, node: URIRef, ten: str):
        return next(iter(self.g.objects(node, ACADEMIC[ten])), None)

    # --- đặt tên -------------------------------------------------------------

    def dat_ten(self, node: URIRef, kieu: str = "pascal") -> str:
        """Tên mới, sinh từ nhãn. Trùng tên thì thêm hậu tố lấy từ IRI cũ."""

        if node in self.ten_moi:
            return self.ten_moi[node]
        ten = (pascal if kieu == "pascal" else camel)(self.nhan(node))
        if not ten:
            # Nhãn không có chữ Latin nào, ví dụ "ТРКИ". Giữ tên cũ làm địa chỉ.
            ten = re.sub(r"[^A-Za-z0-9]", "", local_name(node)) or "Node"
            self.ghi_chu.append(f"nhãn {self.nhan(node)!r} không sinh được tên Latin; giữ {ten}")
        if ten in self._dung_ten and self._dung_ten[ten] != node:
            duoi = re.sub(r"[^A-Za-z0-9]", "", local_name(node))[-4:]
            ten = f"{ten}_{duoi}"
            self.canh_bao.append(f"trùng tên, phải thêm hậu tố: {local_name(node)} → {ten}")
        self._dung_ten[ten] = node
        self.ten_moi[node] = ten
        return ten

    def moi(self, node: URIRef) -> URIRef:
        return URIRef(NS + self.dat_ten(node))

    def dung_tu_vung(self, ra: Graph) -> None:
        """Nhãn tiếng Việt cho lớp và thuộc tính.

        Thiếu chúng thì dòng chỉ mục hiện ":noiDung" thay vì "nội dung", và câu trả
        lời cũng đọc ra tên máy thay vì tên người.
        """

        for thuoc_tinh in sorted(set(self.g.subjects(RDF.type, OWL.ObjectProperty))
                                 | set(self.g.subjects(RDF.type, OWL.DatatypeProperty)), key=str):
            ten = camel(self.nhan(thuoc_tinh))
            ten = "soTien" if ten == "mucLePhi" else ten
            ra.add((ACADEMIC[ten], RDFS.label, Literal(self.nhan(thuoc_tinh), lang="vi")))
            self.tu_vung.add(ten)
        for ten, nhan in _NHAN_THUOC_TINH_MOI.items():
            ra.add((ACADEMIC[ten], RDFS.label, Literal(nhan, lang="vi")))
            self.tu_vung.add(ten)
        for ten, nhan in _NHAN_LOP_CHUNG.items():
            ra.add((ACADEMIC[ten], RDFS.label, Literal(nhan, lang="vi")))
            self.tu_vung.add(ten)
        for lop in sorted(self.g.subjects(RDF.type, OWL.Class), key=str):
            ten = pascal(self.nhan(lop))
            ra.add((ACADEMIC[ten], RDFS.label, Literal(self.nhan(lop), lang="vi")))
            self.tu_vung.add(ten)

    # --- tầng nguồn ----------------------------------------------------------

    def dung_tang_nguon(self, ra: Graph) -> None:
        """Gộp cặp Quyết định/Quy chế, rồi dựng địa chỉ trích dẫn cho phần văn bản."""

        van_ban = [d for d in self.g.subjects(RDF.type, OWL.NamedIndividual)
                   if self.lop(d) & LOP_NGUON and local_name(d) not in KHONG_PHAI_NGUON]
        # Quy chế ban hành kèm Quyết định: một bản ghi, nhãn lấy của Quy chế,
        # số hiệu và ngày lấy của Quyết định.
        ghep: dict[URIRef, URIRef] = {}
        for quy_che in van_ban:
            quyet_dinh = self.mot(quy_che, "issuedBy")
            if quyet_dinh is not None:
                ghep[quyet_dinh] = quy_che
        goc = [d for d in van_ban if d not in ghep]

        for nguon in goc:
            iri = URIRef(NS + "Nguon" + re.sub(r"\D", "", local_name(nguon)) or NS + self.dat_ten(nguon))
            if not re.search(r"\d", local_name(nguon)):
                iri = URIRef(NS + "Nguon" + self.dat_ten(nguon))
            self.ten_moi[nguon] = local_name(iri)
            kem = [d for d, q in ghep.items() if q is nguon]

            ra.add((iri, RDF.type, ACADEMIC.Nguon))
            ra.add((iri, RDFS.label, Literal(self.nhan(nguon), lang="vi")))
            ra.add((iri, ACADEMIC.loaiNguon, ACADEMIC[pascal(self.nhan(next(iter(self.g.objects(nguon, RDF.type)))))]))
            for tu, sang in (("documentNumber", "soHieu"), ("issueDate", "banHanhNgay"),
                             ("retrievedDate", "ngayThuThap"), ("effectiveFromAcademicYear", "hieuLucTu"),
                             ("effectiveFromSemester", "hieuLucTuHocKy")):
                for nguoi_giu in (nguon, *kem):
                    gia_tri = self.mot(nguoi_giu, tu)
                    if gia_tri is not None:
                        ra.add((iri, ACADEMIC[sang], gia_tri))
                        break
            for tu in ("documentUrl", "webPageUrl"):
                for nguoi_giu in (nguon, *kem):
                    gia_tri = self.mot(nguoi_giu, tu)
                    if gia_tri is not None:
                        ra.add((iri, ACADEMIC.duongDan, gia_tri))
                        break
                else:
                    continue
                break
            for nguoi_giu in (nguon, *kem):
                for sua in self.g.objects(nguoi_giu, ACADEMIC.amends):
                    ra.add((iri, ACADEMIC.suaDoiVanBan, sua))
            self.nguon_cua_phan[nguon] = iri
            for d in kem:
                self.nguon_cua_phan[d] = iri

        # Mọi phần văn bản quy về nguồn thô chứa nó.
        for phan in self.g.subjects(RDF.type, OWL.NamedIndividual):
            if not self.lop(phan) & (LOP_VAN_BAN | LOP_TU_LAM_NGUON):
                continue
            tai_lieu = self.mot(phan, "inDocument")
            if tai_lieu is None:
                cha = self.mot(phan, "partOf")
                while cha is not None and self.mot(cha, "inDocument") is None:
                    cha = self.mot(cha, "partOf")
                tai_lieu = self.mot(cha, "inDocument") if cha is not None else None
            if tai_lieu is None:
                self.canh_bao.append(f"phần văn bản không truy được về tài liệu: {local_name(phan)}")
                continue
            self.nguon_cua_phan[phan] = self.nguon_cua_phan.get(tai_lieu, tai_lieu)

    def toa_do_cua(self, phan: URIRef) -> str:
        """Chuỗi toạ độ, cắt phần tên tài liệu ra khỏi trích dẫn dựng sẵn."""

        trich = self.mot(phan, "citationLabel")
        if trich is None:
            return self.nhan(phan)
        text = str(trich)
        cat = re.search(r"\s+(Quy chế|Quyết định|Hướng dẫn|Thông báo|Danh mục|trang |của Trường)", text)
        # Nhãn dựng sẵn có chỗ cắt ngay sau dấu phẩy ("mục tiêu chuẩn chung, trang ..."),
        # để lại toạ độ đọc lửng.
        return (text[: cat.start()] if cat else text).strip().rstrip(",;")

    def dia_chi_trich_dan(self, ra: Graph, phan: URIRef) -> URIRef | None:
        """IRI của địa chỉ trích dẫn; dựng một lần rồi dùng lại."""

        if phan in self.dia_chi:
            return URIRef(NS + self.dia_chi[phan])
        nguon = self.nguon_cua_phan.get(phan)
        if nguon is None:
            return None
        ten = local_name(phan)
        for tu, sang in VIET_TAT_TOA_DO:
            ten = ten.replace(tu, sang)
        ten = "TD" + re.sub(r"[^A-Za-z0-9_]", "", ten)
        if ten in self._dung_ten and self._dung_ten[ten] != phan:
            ten += "x"
        self._dung_ten[ten] = phan
        self.dia_chi[phan] = ten
        iri = URIRef(NS + ten)
        ra.add((iri, RDF.type, ACADEMIC.DiaChiTrichDan))
        ra.add((iri, ACADEMIC.thuocNguon, nguon))
        ra.add((iri, ACADEMIC.toaDo, Literal(self.toa_do_cua(phan), lang="vi")))
        return iri

    @staticmethod
    def _gon(text: str) -> str:
        return unicodedata.normalize("NFC", text).casefold().strip().rstrip(".")

    def trung_nhan(self, node: URIRef, text: str) -> bool:
        """Nội dung trùng y hệt nhãn thì không mang thêm thông tin nào, mà lại được
        đóng dấu nguồn như thể văn bản viết ra câu đó."""

        return self._gon(text) == self._gon(self.nhan(node))

    # --- phát biểu -----------------------------------------------------------

    def dung_ban_do_cha(self) -> None:
        for ten in ("hasStep", "hasRequirement", "hasDeadline", "hasOutcome",
                    "hasConsequence", "hasResolution"):
            for cha, con in self.g.subject_objects(ACADEMIC[ten]):
                self.cha.setdefault(con, cha)

    def node_goc(self, node: URIRef) -> URIRef:
        da_qua = {node}
        while node in self.cha and self.cha[node] not in da_qua:
            node = self.cha[node]
            da_qua.add(node)
        return node

    def tui_cua(self, ra: Graph, node: URIRef) -> list[URIRef]:
        """Các túi mà phát biểu của node thuộc về. Rỗng nghĩa là không có nguồn."""

        tui = []
        for phan in sorted(self.g.objects(node, ACADEMIC.basedOn), key=str):
            dia_chi = self.dia_chi_trich_dan(ra, phan)
            if dia_chi is not None:
                tui.append(dia_chi)
        if not tui and self.lop(node) & LOP_TU_LAM_NGUON:
            dia_chi = self.dia_chi_trich_dan(ra, node)
            if dia_chi is not None:
                tui.append(dia_chi)
        return tui

    def chuyen_phat_bieu(self, ds, mac_dinh: Graph) -> dict[str, int]:
        dem = defaultdict(int)
        ca_the = [i for i in self.g.subjects(RDF.type, OWL.NamedIndividual)
                  if not (self.lop(i) & (LOP_VAN_BAN | LOP_NGUON))
                  or local_name(i) in KHONG_PHAI_NGUON]

        for node in sorted(ca_the, key=str):
            goc = self.node_goc(node)
            trung_gian = bool(self.lop(node) & LOP_TRUNG_GIAN)
            tui = self.tui_cua(ra=mac_dinh, node=node) or self.tui_cua(ra=mac_dinh, node=goc)

            # Danh tính chỉ của thực thể thật, không của node trung gian.
            if not trung_gian:
                for lop in self.g.objects(node, RDF.type):
                    if lop == OWL.NamedIndividual:
                        continue
                    ten_lop = KHONG_PHAI_NGUON.get(local_name(node)) or pascal(self.nhan(lop))
                    lop_chung, o_loai = GOP_LOP.get(ten_lop, (ten_lop, None))
                    doi = DOI_LOP_CA_THE.get(self.dat_ten(node))
                    nhan_loai = self.nhan(lop)
                    if doi is not None:
                        lop_chung, o_loai, ten_lop = doi
                        nhan_loai = self.nhan_lop.get(ten_lop)
                    mac_dinh.add((self.moi(node), RDF.type, ACADEMIC[lop_chung]))
                    if o_loai and ten_lop != lop_chung:
                        mac_dinh.add((self.moi(node), ACADEMIC[o_loai], ACADEMIC[ten_lop]))
                        if nhan_loai is not None:
                            mac_dinh.add((ACADEMIC[ten_lop], RDFS.label, Literal(nhan_loai, lang="vi")))
                        self.gop_lop_da_dung.add(ten_lop)
                mac_dinh.add((self.moi(node), RDFS.label, Literal(self.nhan(node), lang="vi")))
                for ten_khac in self.g.objects(node, SKOS.altLabel):
                    mac_dinh.add((self.moi(node), SKOS.altLabel, Literal(str(ten_khac), lang="vi")))

            for p, o in sorted(self.g.predicate_objects(node), key=lambda x: (str(x[0]), str(x[1]))):
                ten = local_name(p)
                if ten in NGUON_HOC | TOA_DO | TAN_DI or p in (RDF.type, RDFS.label, SKOS.altLabel):
                    continue
                if ten in ("catalogueEntryForForm", "hasCatalogueEntry") and False:
                    continue

                # Cách giải quyết đảo chiều: thủ tục áp dụng cho trường hợp,
                # không phải trường hợp được giải quyết bằng thủ tục.
                if ten == "resolvedBy":
                    for t in tui or [None]:
                        self.them(ds, mac_dinh, t, self.moi(o), ACADEMIC.apDungChoTruongHop, self.moi(goc))
                        dem["đảo chiều trường hợp"] += 1
                    continue
                if ten == "scopedToCase":
                    for t in tui or [None]:
                        self.them(ds, mac_dinh, t, self.moi(goc), ACADEMIC.apDungChoTruongHop, self.moi(o))
                        dem["đảo chiều trường hợp"] += 1
                    continue

                if ten in MO_TA:
                    mac_dinh.add((self.moi(goc), ACADEMIC.noiDung, Literal(str(o), lang="vi")))
                    dem["mô tả không nguồn"] += 1
                    continue

                if ten in VAN_BAN:
                    if self.trung_nhan(goc, str(o)):
                        dem["bỏ nội dung trùng nhãn"] += 1
                        continue
                    chu_the = self.moi(goc)
                    # Điều kiện của cách giải quyết mô tả thủ tục, không mô tả trường hợp.
                    if ten == "conditionText":
                        muc_tieu = self.mot(node, "resolvedBy")
                        if muc_tieu is not None:
                            chu_the = self.moi(muc_tieu)
                    for t in tui or [None]:
                        self.them(ds, mac_dinh, t, chu_the, ACADEMIC.noiDung, Literal(str(o), lang="vi"))
                    dem["nội dung"] += 1
                    continue

                ten_moi_tt = camel(self.nhan(p))
                if ten_moi_tt == "mucLePhi":
                    ten_moi_tt = "soTien"
                thuoc_tinh = ACADEMIC[ten_moi_tt]
                gia_tri = self.moi(o) if isinstance(o, URIRef) else o
                for t in tui or [None]:
                    self.them(ds, mac_dinh, t, self.moi(goc), thuoc_tinh, gia_tri)
                dem["quan hệ" if isinstance(o, URIRef) else "giá trị"] += 1
                if not tui:
                    dem["không có nguồn"] += 1
        return dem

    @staticmethod
    def them(ds, mac_dinh: Graph, tui, s, p, o) -> None:
        (mac_dinh if tui is None else ds.graph(tui)).add((s, p, o))


def doi_chieu(bo: BoChuyenDoi, ds, da_sua: set = frozenset(), da_bo: set = frozenset()) -> list[str]:
    """Đã trừ những gì cố ý bỏ: câu bị thay theo quy chế, câu sai bị xoá trong
    ``dat_lai_cau``, thực thể bị xoá, và nội dung trùng y hệt nhãn."""

    """Mọi dữ kiện cũ phải xuất hiện lại. Dựng lại kỳ vọng từ đồ thị cũ, rồi so."""

    co_that = {(s, p, o) for s, p, o, _ in ds.quads((None, None, None, None))}
    _sc = json.loads(SUA_CHUA.read_text(encoding="utf-8")) if SUA_CHUA.exists() else {}
    da_xoa = {ACADEMIC[m["thuc_the"]] for m in _sc.get("xoa", [])}
    #: Câu mô tả được thay bằng câu gốc của quy chế và chuyển vào túi.
    da_dat_nguon = {ACADEMIC[m["thuc_the"]] for m in _sc.get("dat_nguon", [])}
    thieu: list[str] = []
    for node in sorted(bo.g.subjects(RDF.type, OWL.NamedIndividual), key=str):
        if bo.lop(node) & (LOP_VAN_BAN | LOP_NGUON) and local_name(node) not in KHONG_PHAI_NGUON:
            continue
        goc = bo.node_goc(node)
        if bo.moi(goc) in da_xoa:
            continue
        for p, o in bo.g.predicate_objects(node):
            ten = local_name(p)
            if ten in NGUON_HOC | TOA_DO | TAN_DI or p in (RDF.type, RDFS.label, SKOS.altLabel):
                continue
            if ten in ("resolvedBy", "scopedToCase"):
                continue
            if ten in MO_TA:
                if bo.moi(goc) in da_dat_nguon:
                    continue
                can = (bo.moi(goc), ACADEMIC.noiDung, Literal(str(o), lang="vi"))
                if can not in co_that and can not in da_bo:
                    thieu.append(f"{local_name(node)} · {ten} → {str(o)[:46]}")
                continue
            if ten in VAN_BAN:
                if bo.trung_nhan(goc, str(o)):
                    continue
                chu_the = bo.moi(goc)
                if ten == "conditionText":
                    muc_tieu = bo.mot(node, "resolvedBy")
                    if muc_tieu is not None:
                        chu_the = bo.moi(muc_tieu)
                can = (chu_the, ACADEMIC.noiDung, Literal(str(o), lang="vi"))
            else:
                ten_tt = camel(bo.nhan(p))
                can = (bo.moi(goc), ACADEMIC["soTien" if ten_tt == "mucLePhi" else ten_tt],
                       bo.moi(o) if isinstance(o, URIRef) else o)
            if (can[0], can[1]) in da_sua or can in da_bo:
                continue
            if can not in co_that:
                thieu.append(f"{local_name(node)} · {ten} → {str(o)[:46]}")
    return thieu


def ap_dung_sua_chua(bo: "BoChuyenDoi", ds, mac_dinh: Graph) -> tuple[int, set]:
    """Thay :noiDung của một cặp (thực thể, toạ độ) bằng câu gốc của quy chế.

    Bộ chuyển đổi không đoán được câu nào bị cắt đôi và câu gốc viết thế nào, nên
    phần này là quyết định của người, ghi trong ``repairs.json`` kèm lý do.
    """

    if not SUA_CHUA.exists():
        return 0, set()
    # Hai quy chế 1052 và 753 cùng nhãn nên chuỗi toạ độ như "khoản 2 Điều 10"
    # xuất hiện ở cả hai. Khoá tra phải gồm cả nguồn, nếu không sẽ sửa nhầm văn bản.
    theo_toa_do: dict[str, URIRef] = {}
    theo_cap: dict[tuple, URIRef] = {}
    for tui_, _, toa_ in mac_dinh.triples((None, ACADEMIC.toaDo, None)):
        nguon_ = next(iter(mac_dinh.objects(tui_, ACADEMIC.thuocNguon)), None)
        theo_cap[(str(toa_), str(nguon_))] = tui_
        # Cùng toạ độ trong CÙNG một nguồn là địa chỉ dựng trùng, được gộp ở bước sau;
        # chỉ khác nguồn mới là cái bẫy cho mục sửa chữa.
        if str(toa_) in theo_toa_do and mac_dinh.value(theo_toa_do[str(toa_)], ACADEMIC.thuocNguon) != nguon_:
            bo.ghi_chu.append(f"toạ độ {str(toa_)!r} có ở nhiều nguồn — mục sửa chữa nào chạm tới nó phải nêu nguon_hien_tai")
        theo_toa_do.setdefault(str(toa_), tui_)
    da_sua: set[tuple] = set()
    dem = 0

    def dia_chi_moi(toa_do: str, nguon_goc) -> URIRef:
        """Địa chỉ trích dẫn cho một toạ độ chưa có; dựng dưới nguồn được chỉ định."""

        khoa = (toa_do, str(nguon_goc))
        if khoa in theo_cap:
            return theo_cap[khoa]
        iri = dung_dia_chi(mac_dinh, nguon_goc, toa_do)
        theo_cap[khoa] = iri
        theo_toa_do.setdefault(toa_do, iri)
        return iri

    for muc in json.loads(SUA_CHUA.read_text(encoding="utf-8"))["sua"]:
        chu_the = ACADEMIC[muc["thuc_the"]]
        tui = (theo_cap.get((muc["toa_do"], str(ACADEMIC[muc["nguon_hien_tai"]])))
               if muc.get("nguon_hien_tai") else theo_toa_do.get(muc["toa_do"]))
        if tui is None:
            bo.canh_bao.append(f"sửa chữa: không thấy toạ độ {muc['toa_do']!r}")
            continue

        # Dời cả cụm sang văn bản khác: nội dung bị gán nhầm nguồn.
        if "chuyen_sang" in muc:
            dich_spec = muc["chuyen_sang"]
            dich = dia_chi_moi(dich_spec["toa_do"], ACADEMIC[dich_spec["nguon"]])
            for p_, o_ in list(ds.graph(tui).predicate_objects(chu_the)):
                ds.graph(tui).remove((chu_the, p_, o_))
                ds.graph(dich).add((chu_the, p_, o_))
                dem += 1
            continue
        for cu in list(ds.graph(tui).objects(chu_the, ACADEMIC.noiDung)):
            ds.graph(tui).remove((chu_the, ACADEMIC.noiDung, cu))
        da_sua.add((chu_the, ACADEMIC.noiDung))

        for cau in muc["thay_bang"]:
            dich = tui
            if cau.get("toa_do"):
                nguon = (ACADEMIC[cau["nguon"]] if cau.get("nguon")
                         else next(iter(mac_dinh.objects(tui, ACADEMIC.thuocNguon)), None))
                dich = theo_toa_do.get(cau["toa_do"]) if not cau.get("nguon") else None
                if dich is None:
                    dich = dia_chi_moi(cau["toa_do"], nguon)
            ds.graph(dich).add((chu_the, ACADEMIC.noiDung, Literal(cau["noiDung"], lang="vi")))
            dem += 1
    for muc in json.loads(SUA_CHUA.read_text(encoding="utf-8")).get("ten_goi_them", []):
        chu_the = ACADEMIC[muc["thuc_the"]]
        if (chu_the, RDFS.label, None) not in mac_dinh:
            bo.canh_bao.append(f"thêm tên gọi: không thấy thực thể {muc['thuc_the']!r}")
            continue
        for ten in muc["ten_goi_phu"]:
            mac_dinh.add((chu_the, SKOS.altLabel, Literal(ten, lang="vi")))
            dem += 1

    for muc in json.loads(SUA_CHUA.read_text(encoding="utf-8")).get("doi_nhan", []):
        chu_the = ACADEMIC[muc.get("iri_moi", muc["thuc_the"])]
        for cu in list(mac_dinh.objects(chu_the, RDFS.label)):
            mac_dinh.remove((chu_the, RDFS.label, cu))
        mac_dinh.add((chu_the, RDFS.label, Literal(muc["nhan"], lang="vi")))
        for cu in list(mac_dinh.objects(chu_the, SKOS.altLabel)):
            mac_dinh.remove((chu_the, SKOS.altLabel, cu))
        for ten in muc.get("ten_goi_phu", []):
            mac_dinh.add((chu_the, SKOS.altLabel, Literal(ten, lang="vi")))
        dem += 1

    for muc in json.loads(SUA_CHUA.read_text(encoding="utf-8")).get("xoa", []):
        chu_the = ACADEMIC[muc["thuc_the"]]
        for tui_ in [mac_dinh.identifier, *{q[3] for q in ds.quads((chu_the, None, None, None))}]:
            do_thi = mac_dinh if tui_ == mac_dinh.identifier else ds.graph(tui_)
            for p_, o_ in list(do_thi.predicate_objects(chu_the)):
                do_thi.remove((chu_the, p_, o_))
                dem += 1

    for muc in json.loads(SUA_CHUA.read_text(encoding="utf-8")).get("dat_nguon", []):
        chu_the = ACADEMIC[muc["thuc_the"]]
        for cu in list(mac_dinh.objects(chu_the, ACADEMIC.noiDung)):
            mac_dinh.remove((chu_the, ACADEMIC.noiDung, cu))
        dich = dia_chi_moi(muc["toa_do"], ACADEMIC[muc["nguon"]])
        ds.graph(dich).add((chu_the, ACADEMIC.noiDung, Literal(muc["noiDung"], lang="vi")))
        dem += 1

    return dem, da_sua


def ten_do_thi(do_thi) -> URIRef:
    """Tên của một túi. Tuỳ cách gọi, rdflib trả về tên hoặc chính đồ thị."""

    return do_thi if isinstance(do_thi, URIRef) else do_thi.identifier


def tim_dia_chi(mac_dinh: Graph, nguon: URIRef, toa_do: str) -> URIRef | None:
    for dia_chi in mac_dinh.subjects(ACADEMIC.toaDo, Literal(toa_do, lang="vi")):
        if (dia_chi, ACADEMIC.thuocNguon, nguon) in mac_dinh:
            return dia_chi
    return None


def dung_dia_chi(mac_dinh: Graph, nguon: URIRef, toa_do: str) -> URIRef:
    """Địa chỉ trích dẫn của một chỗ trong văn bản; chưa có thì dựng, tên không trùng.

    Tên từng bị cắt ở 28 ký tự, nên hai toạ độ dưới một nguồn có tên dài sẽ ra cùng
    một IRI và dồn câu của hai chỗ vào một túi.
    """

    co_san = tim_dia_chi(mac_dinh, nguon, toa_do)
    if co_san is not None:
        return co_san
    # Tên nguồn giữ nguyên chữ hoa; qua pascal() nó thành "Nguonhuongdandonghocphi...".
    goc = "TD" + local_name(nguon) + pascal(toa_do)
    iri, hau_to = URIRef(NS + goc), 2
    while (iri, None, None) in mac_dinh:
        iri, hau_to = URIRef(f"{NS}{goc}{hau_to}"), hau_to + 1
    mac_dinh.add((iri, RDF.type, ACADEMIC.DiaChiTrichDan))
    mac_dinh.add((iri, ACADEMIC.thuocNguon, nguon))
    mac_dinh.add((iri, ACADEMIC.toaDo, Literal(toa_do, lang="vi")))
    return iri


def ten_dia_chi(mac_dinh: Graph, dia_chi: URIRef) -> str:
    nguon = mac_dinh.value(dia_chi, ACADEMIC.thuocNguon)
    return f"{mac_dinh.value(dia_chi, ACADEMIC.toaDo)} ({local_name(nguon) if nguon else '?'})"


def doc_trich_dan(mac_dinh: Graph, muc: dict, loi: list[str], noi: str) -> URIRef | None:
    """Một trích dẫn trong repairs.json: ``{"dia_chi"}`` hoặc ``{"nguon", "toa_do"}``.

    Toạ độ chưa có chỉ được dựng khi mục ghi rõ ``"tao_moi": true``, để một lỗi gõ
    không lặng lẽ sinh ra một địa chỉ mới.
    """

    if "dia_chi" in muc:
        iri = ACADEMIC[muc["dia_chi"]]
        if (iri, RDF.type, ACADEMIC.DiaChiTrichDan) not in mac_dinh:
            loi.append(f"{noi}: không có địa chỉ trích dẫn {muc['dia_chi']}")
            return None
        return iri
    nguon = ACADEMIC[muc["nguon"]]
    if (nguon, RDF.type, ACADEMIC.Nguon) not in mac_dinh:
        loi.append(f"{noi}: không có nguồn {muc['nguon']}")
        return None
    co_san = tim_dia_chi(mac_dinh, nguon, muc["toa_do"])
    if co_san is None and not muc.get("tao_moi"):
        loi.append(f"{noi}: {muc['nguon']} chưa có toạ độ {muc['toa_do']!r} "
                   "(ghi \"tao_moi\": true nếu cố ý dựng mới)")
        return None
    return co_san or dung_dia_chi(mac_dinh, nguon, muc["toa_do"])


def doi_iri(bo: "BoChuyenDoi", ds, mac_dinh: Graph, sua_chua: dict, loi: list[str]) -> int:
    """Đổi IRI khi tên cũ gọi sai thứ nó trỏ tới.

    Chạy trước mọi sửa chữa khác, nên các mục khác trong repairs.json dùng tên MỚI.
    """

    dem = 0
    for muc in sua_chua.get("doi_nhan", []):
        if "iri_moi" not in muc:
            continue
        cu, moi = ACADEMIC[muc["thuc_the"]], ACADEMIC[muc["iri_moi"]]
        if muc["iri_moi"] != pascal(muc["nhan"]):
            loi.append(f"doi_nhan: IRI mới phải sinh từ nhãn mới, tức {pascal(muc['nhan'])}")
            continue
        if next(iter(ds.quads((moi, None, None, None))), None) is not None:
            loi.append(f"doi_nhan: IRI mới {muc['iri_moi']} đã có người dùng")
            continue
        cau = [q for q in ds.quads((None, None, None, None)) if cu in (q[0], q[2])]
        if not cau:
            loi.append(f"doi_nhan: không thấy thực thể {muc['thuc_the']}")
            continue
        for s, p, o, tui in cau:
            do_thi = ds.graph(ten_do_thi(tui))
            do_thi.remove((s, p, o))
            do_thi.add((moi if s == cu else s, p, moi if o == cu else o))
            dem += 1
        for node, ten in list(bo.ten_moi.items()):
            if ten == muc["thuc_the"]:
                bo.ten_moi[node] = muc["iri_moi"]
        # Giá trị của ô "loại" là từ vựng chứ không phải thực thể; đổi tên thì báo cáo
        # vẫn phải nhận ra nó là từ vựng.
        for tap in (bo.tu_vung, bo.gop_lop_da_dung):
            if muc["thuc_the"] in tap:
                tap.discard(muc["thuc_the"])
                tap.add(muc["iri_moi"])
    return dem


def doi_toa_do(mac_dinh: Graph, sua_chua: dict, loi: list[str]) -> int:
    """Viết lại toạ độ đọc lửng hoặc không khớp cách văn bản tự đánh số."""

    dem = 0
    for muc in sua_chua.get("doi_toa_do", []):
        dia_chi = ACADEMIC[muc["dia_chi"]]
        cu = list(mac_dinh.objects(dia_chi, ACADEMIC.toaDo))
        if not cu:
            loi.append(f"doi_toa_do: không có địa chỉ trích dẫn {muc['dia_chi']}")
            continue
        for toa_do in cu:
            mac_dinh.remove((dia_chi, ACADEMIC.toaDo, toa_do))
        mac_dinh.add((dia_chi, ACADEMIC.toaDo, Literal(muc["toa_do"], lang="vi")))
        dem += 1
    return dem


def gop_dia_chi_trung(ds, mac_dinh: Graph) -> list[str]:
    """Hai địa chỉ cùng nguồn, cùng toạ độ là một chỗ trong văn bản bị dựng hai lần."""

    theo_cho = defaultdict(list)
    for dia_chi, _, toa_do in mac_dinh.triples((None, ACADEMIC.toaDo, None)):
        theo_cho[(mac_dinh.value(dia_chi, ACADEMIC.thuocNguon), str(toa_do))].append(dia_chi)
    ra = []
    for cac_dia_chi in theo_cho.values():
        if len(cac_dia_chi) < 2:
            continue
        giu, *bo_di = sorted(cac_dia_chi, key=str)
        for dia_chi in bo_di:
            for cau in list(ds.graph(dia_chi)):
                ds.graph(giu).add(cau)
            ds.remove_graph(ds.graph(dia_chi))
            ra.append(f"{ten_dia_chi(mac_dinh, dia_chi)}: {local_name(dia_chi)} gộp vào {local_name(giu)}")
            for p, o in list(mac_dinh.predicate_objects(dia_chi)):
                mac_dinh.remove((dia_chi, p, o))
    return sorted(ra)


def _khop(gia_tri_that, gia_tri: str) -> bool:
    if isinstance(gia_tri_that, URIRef):
        return local_name(gia_tri_that) == gia_tri
    return str(gia_tri_that) == gia_tri


def rut_trich_dan(ds, mac_dinh: Graph, sua_chua: dict, loi: list[str]) -> int:
    """Gỡ thực thể khỏi một trích dẫn không nói gì về nó.

    Chỉ gỡ, không xoá: câu gỡ ra phải còn ở một chỗ khác. Câu chỉ nằm ở chỗ sai là
    câu cần đặt lại (``dat_lai_cau``), không phải câu thừa.
    """

    dem = 0
    for muc in sua_chua.get("rut_trich_dan", []):
        noi = f"rut_trich_dan {muc.get('toa_do', muc.get('dia_chi'))}"
        tui = doc_trich_dan(mac_dinh, muc, loi, noi)
        if tui is None:
            continue
        chi_thuoc_tinh = {ACADEMIC[t] for t in muc.get("thuoc_tinh", [])}
        cac_thuc_the = muc["thuc_the"] if isinstance(muc["thuc_the"], list) else [muc["thuc_the"]]
        for ten in cac_thuc_the:
            chu_the = ACADEMIC[ten]
            cau = [(p, o) for p, o in ds.graph(tui).predicate_objects(chu_the)
                   if not chi_thuoc_tinh or p in chi_thuoc_tinh]
            if not cau:
                loi.append(f"{noi}: {ten} không có câu nào ở đây")
                continue
            for p, o in cau:
                if not any(ten_do_thi(g) != tui for *_, g in ds.quads((chu_the, p, o, None))):
                    loi.append(f"{noi}: {ten} · {local_name(p)} chỉ nằm ở đây, gỡ ra là mất")
                    continue
                ds.graph(tui).remove((chu_the, p, o))
                dem += 1
    return dem


def tao_gia_tri(ds, thuoc_tinh: URIRef, gia_tri: str, loi: list[str], noi: str):
    """Giá trị cho một câu thêm mới.

    Tên một thực thể đã có thì là liên kết. Còn lại là chữ, mượn kiểu của các câu sẵn
    có cùng thuộc tính (số nguyên, chữ tiếng Việt...), để câu mới không lệch kiểu với
    câu cũ và vẫn so khớp được khi tìm.
    """

    if re.fullmatch(r"[A-Za-z0-9_]+", gia_tri):
        iri = ACADEMIC[gia_tri]
        if next(iter(ds.quads((iri, None, None, None))), None) is not None:
            return iri
    mau = next((o for _, _, o, _ in ds.quads((None, thuoc_tinh, None, None)) if isinstance(o, Literal)), None)
    if mau is None:
        loi.append(f"{noi}: {gia_tri!r} không phải thực thể, và chưa câu nào dùng "
                   f"{local_name(thuoc_tinh)} để mượn kiểu giá trị")
        return None
    return Literal(gia_tri, lang=mau.language, datatype=mau.datatype)


def tao_thuc_the(ds, mac_dinh: Graph, sua_chua: dict, loi: list[str]) -> int:
    """Dựng thực thể mới, ví dụ khi một quy tắc gộp hai mức phải tách làm hai.

    Chỉ dựng danh tính; các câu của nó ghi trong ``dat_lai_cau`` với ``"them": true``.
    Tên phải đúng là tên sinh từ nhãn, như mọi thực thể khác.
    """

    dem = 0
    for muc in sua_chua.get("tao_thuc_the", []):
        noi = f"tao_thuc_the {muc['thuc_the']}"
        chu_the, lop = ACADEMIC[muc["thuc_the"]], ACADEMIC[muc["lop"]]
        mong_doi = pascal(muc["nhan"])
        if muc["lop"] == "Nguon":
            # Nguồn theo lệ có sẵn: Nguon + số hiệu văn bản; trang web không số hiệu
            # thì Nguon + tên sinh từ nhãn.
            so = re.sub(r"\D", "", muc.get("so_hieu", "").split("/")[0])
            mong_doi = "Nguon" + (so or pascal(muc["nhan"]))
        if muc["thuc_the"] != mong_doi:
            loi.append(f"{noi}: tên phải là {mong_doi}")
            continue
        if next(iter(ds.quads((chu_the, None, None, None))), None) is not None:
            loi.append(f"{noi}: thực thể này đã có")
            continue
        if (None, RDF.type, lop) not in mac_dinh:
            loi.append(f"{noi}: không có lớp {muc['lop']}")
            continue
        mac_dinh.add((chu_the, RDF.type, lop))
        mac_dinh.add((chu_the, RDFS.label, Literal(muc["nhan"], lang="vi")))
        for ten in muc.get("ten_goi_phu", []):
            mac_dinh.add((chu_the, SKOS.altLabel, Literal(ten, lang="vi")))
        dem += 1
    return dem


def dat_lai_cau(ds, mac_dinh: Graph, sua_chua: dict, loi: list[str]) -> tuple[int, set]:
    """Đặt từng câu vào đúng chỗ văn bản nói ra nó.

    Dữ liệu cũ chỉ ghi nguồn cho cả thực thể, nên bộ chuyển đổi chép mọi câu vào mọi
    túi của thực thể. Mỗi mục ở đây gỡ một câu khỏi mọi túi rồi đặt lại vào đúng các
    trích dẫn liệt kê. Danh sách rỗng nghĩa là câu ta tự khẳng định, nằm ngoài mọi
    túi; ``"xoa": true`` bỏ hẳn một câu sai; ``"them": true`` thêm một câu chưa có.
    """

    dem, da_bo = 0, set()
    for nhom in sua_chua.get("dat_lai_cau", []):
        chu_the = ACADEMIC[nhom["thuc_the"]]
        for cau in nhom["cau"]:
            noi = f"dat_lai_cau {nhom['thuc_the']} · {cau['thuoc_tinh']} · {cau['gia_tri'][:40]}"
            if ("xoa" in cau) == ("trich_dan" in cau):
                loi.append(f"{noi}: cần đúng một trong hai trường xoa và trich_dan")
                continue
            thuoc_tinh = ACADEMIC[cau["thuoc_tinh"]]
            khop = [(o, ten_do_thi(g)) for _, _, o, g in ds.quads((chu_the, thuoc_tinh, None, None))
                    if _khop(o, cau["gia_tri"])]
            can_co = 0 if cau.get("them") else 1
            if len({o for o, _ in khop}) != can_co:
                loi.append(f"{noi}: thấy {len({o for o, _ in khop})} giá trị khớp, cần đúng {can_co}")
                continue
            dich = [doc_trich_dan(mac_dinh, td, loi, noi) for td in cau.get("trich_dan", [])]
            if None in dich:
                continue
            o = khop[0][0] if khop else tao_gia_tri(ds, thuoc_tinh, cau["gia_tri"], loi, noi)
            if o is None:
                continue
            for _, tui in khop:
                ds.graph(tui).remove((chu_the, thuoc_tinh, o))
            if cau.get("xoa"):
                da_bo.add((chu_the, thuoc_tinh, o))
            elif not dich:
                mac_dinh.add((chu_the, thuoc_tinh, o))
            for tui in dich:
                ds.graph(tui).add((chu_the, thuoc_tinh, o))
            dem += 1
    return dem, da_bo


def bo_dia_chi_rong(ds, mac_dinh: Graph) -> list[str]:
    """Địa chỉ không còn câu nào: thực thể dẫn tới nó đã bị xoá, hoặc mọi câu đã về
    đúng chỗ. Để lại thì trang quản trị sẽ bày ra những trích dẫn không chứng nhận gì."""

    co_cau = {ten_do_thi(g) for *_, g in ds.quads((None, None, None, None))}
    ra = []
    for dia_chi in sorted(set(mac_dinh.subjects(RDF.type, ACADEMIC.DiaChiTrichDan)), key=str):
        if dia_chi in co_cau:
            continue
        ra.append(ten_dia_chi(mac_dinh, dia_chi))
        for p, o in list(mac_dinh.predicate_objects(dia_chi)):
            mac_dinh.remove((dia_chi, p, o))
    for do_thi in list(ds.graphs()):
        if do_thi.identifier != mac_dinh.identifier and len(do_thi) == 0:
            ds.remove_graph(do_thi)
    return sorted(ra)


def cau_nhieu_trich_dan(ds, mac_dinh: Graph) -> tuple[list, list]:
    """Câu nằm ở hơn một túi, tách làm hai loại.

    Cùng một văn bản nói một điều ở hai chỗ gần như luôn là câu bị chép sang chỗ
    không nói ra nó. Hai văn bản khác nhau cùng nêu thì có thể đúng, nhưng phải có
    người đọc cả hai rồi ghi lý do.
    """

    theo_cau = defaultdict(list)
    for s, p, o, tui in ds.quads((None, None, None, None)):
        if ten_do_thi(tui) != mac_dinh.identifier:
            theo_cau[(s, p, o)].append(ten_do_thi(tui))
    cung_van_ban, khac_van_ban = [], []
    for (s, p, o), cac_tui in theo_cau.items():
        if len(cac_tui) < 2:
            continue
        khoa = f"{local_name(s)}|{local_name(p)}|{local_name(o) if isinstance(o, URIRef) else o}"
        dong = (khoa, sorted(ten_dia_chi(mac_dinh, t) for t in cac_tui))
        nguon = [mac_dinh.value(t, ACADEMIC.thuocNguon) for t in cac_tui]
        (cung_van_ban if len(set(nguon)) < len(nguon) else khac_van_ban).append(dong)
    return sorted(cung_van_ban), sorted(khac_van_ban)


def dieu_co_cho_min_hon(mac_dinh: Graph) -> list[str]:
    """Trích dẫn cả một điều trong khi đã có địa chỉ mịn hơn của chính điều đó: dấu
    hiệu câu được gán theo nguồn của cả thực thể chứ không theo khoản nói ra nó."""

    theo_nguon = defaultdict(set)
    for dia_chi, _, toa_do in mac_dinh.triples((None, ACADEMIC.toaDo, None)):
        theo_nguon[mac_dinh.value(dia_chi, ACADEMIC.thuocNguon)].add(str(toa_do))
    return sorted(
        f"{toa_do} ({local_name(nguon)})"
        for nguon, cac_toa_do in theo_nguon.items()
        for toa_do in cac_toa_do
        if re.fullmatch(r"Điều \d+", toa_do) and any(t.endswith(" " + toa_do) for t in cac_toa_do)
    )


def cau_bi_che_doi(ds, mac_dinh) -> list[tuple[str, str, list[str]]]:
    """Cặp (thực thể, điều khoản) mang nhiều hơn một :noiDung.

    Gần như toàn bộ là một câu của quy chế bị AI Agent cắt ở chỗ động từ thành
    "viết đơn" và "gửi đơn". Phải lấy lại câu gốc từ references/ rồi nhập một câu.
    """

    dong_tu_soan = re.compile(r"^(viết|làm|chuẩn bị|soạn)\b", re.I)
    dong_tu_nop = re.compile(r"^(gửi|nộp|trình)\b", re.I)

    gom = defaultdict(list)
    for s, _, o, tui in ds.quads((None, ACADEMIC.noiDung, None, None)):
        if tui != mac_dinh.identifier:
            gom[(s, tui)].append(str(o))
    ra = []
    for (chu_the, tui), cac_cau in gom.items():
        if len(cac_cau) < 2:
            continue
        nhan = next(iter(mac_dinh.objects(chu_the, RDFS.label)), local_name(chu_the))
        toa_do = next(iter(mac_dinh.objects(tui, ACADEMIC.toaDo)), local_name(tui))
        che_doi = (any(dong_tu_soan.match(c) for c in cac_cau)
                   and any(dong_tu_nop.match(c) for c in cac_cau))
        ra.append((not che_doi, str(nhan), str(toa_do), sorted(cac_cau), che_doi, chu_the))
    return sorted(ra)


def doc_da_duyet() -> dict:
    return json.loads(DA_DUYET.read_text(encoding="utf-8")) if DA_DUYET.exists() else {}


def main() -> None:
    import os
    import sys

    from rdflib import Dataset

    # rdflib xếp các túi theo thứ tự băm của Python, vốn đổi sau mỗi lần chạy: nội
    # dung vẫn y hệt nhưng tệp TriG xáo cả nghìn dòng, che mất thay đổi dữ liệu thật
    # trong git diff. Cố định hạt giống băm thì đầu ra giống nhau từng byte.
    if os.environ.get("PYTHONHASHSEED") != "0":
        os.execve(sys.executable, [sys.executable, *sys.argv], {**os.environ, "PYTHONHASHSEED": "0"})

    g = Graph()
    g.parse(NGUON_TTL, format="turtle")
    bo = BoChuyenDoi(g)
    bo.dung_ban_do_cha()

    ds = Dataset()
    mac_dinh = ds.default_graph
    bo.dung_tu_vung(mac_dinh)
    bo.dung_tang_nguon(mac_dinh)
    dem = bo.chuyen_phat_bieu(ds, mac_dinh)
    sua_chua = json.loads(SUA_CHUA.read_text(encoding="utf-8")) if SUA_CHUA.exists() else {}
    loi: list[str] = []
    dem["câu đổi sang IRI mới"] = doi_iri(bo, ds, mac_dinh, sua_chua, loi)
    dem["câu sửa lại theo quy chế"], da_sua = ap_dung_sua_chua(bo, ds, mac_dinh)
    dem["toạ độ viết lại"] = doi_toa_do(mac_dinh, sua_chua, loi)
    gop = gop_dia_chi_trung(ds, mac_dinh)
    dem["câu gỡ khỏi trích dẫn không nói ra nó"] = rut_trich_dan(ds, mac_dinh, sua_chua, loi)
    dem["thực thể dựng mới"] = tao_thuc_the(ds, mac_dinh, sua_chua, loi)
    dem["câu đặt lại đúng chỗ trích dẫn"], da_bo = dat_lai_cau(ds, mac_dinh, sua_chua, loi)
    rong = bo_dia_chi_rong(ds, mac_dinh)
    if loi:
        raise SystemExit("repairs.json có mục không áp được, chưa ghi tệp nào:\n"
                         + "\n".join(f"  - {x}" for x in loi))

    tui = {q[3] for q in ds.quads((None, None, None, None))} - {mac_dinh.identifier}
    ngoai = len(list(mac_dinh))
    tong = len(list(ds.quads((None, None, None, None))))
    thieu = doi_chieu(bo, ds, da_sua, da_bo)
    che_doi = cau_bi_che_doi(ds, mac_dinh)
    cung_van_ban, khac_van_ban = cau_nhieu_trich_dan(ds, mac_dinh)
    dieu_tho = dieu_co_cho_min_hon(mac_dinh)
    so_dia_chi = len(set(mac_dinh.subjects(RDF.type, ACADEMIC.DiaChiTrichDan)))
    # Thực thể mà KHÔNG câu nào của nó nằm trong túi: chỉ có danh tính và mô tả,
    # nên trả lời được nhưng không trích dẫn được.
    def ten_tui(tui_):
        return tui_ if isinstance(tui_, URIRef) else tui_.identifier

    co_nguon = {s_ for s_, _, _, tui_ in ds.quads((None, None, None, None))
                if ten_tui(tui_) != mac_dinh.identifier}
    ngoai_tui = {s_ for s_, _, _, tui_ in ds.quads((None, None, None, None))
                 if ten_tui(tui_) == mac_dinh.identifier}
    khong_nguon = sorted(
        str(next(iter(mac_dinh.objects(s_, RDFS.label)), local_name(s_)))
        for s_ in ngoai_tui - co_nguon
        if (s_, RDF.type, ACADEMIC.DiaChiTrichDan) not in mac_dinh
        and (s_, RDF.type, ACADEMIC.Nguon) not in mac_dinh
        and local_name(s_) not in bo.gop_lop_da_dung | bo.tu_vung)
    DICH_TRIG.write_bytes(ds.serialize(format="trig", encoding="utf-8"))
    BANG_DOI.write_text(
        json.dumps({local_name(k): v for k, v in sorted(bo.ten_moi.items(), key=lambda x: str(x[0]))},
                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    nguon_tho = len(set(bo.nguon_cua_phan.values()))
    dong = [
        "# Báo cáo chuyển đổi ontology sang TriG", "",
        f"- cũ: {len(g)} bộ ba, {len(set(g.subjects(RDF.type, OWL.NamedIndividual)))} cá thể",
        f"- mới: {tong} câu, trong đó {ngoai} nằm ngoài túi",
        f"- nguồn thô: {nguon_tho} · địa chỉ trích dẫn: {so_dia_chi} · túi dùng thật: {len(tui)}",
        "",
        "## Đã chuyển", "",
        *[f"- {k}: {v}" for k, v in sorted(dem.items())],
        f"- lớp gộp lại thành lớp chung kèm ô loại: {len(bo.gop_lop_da_dung)}",
        f"- địa chỉ trích dẫn gộp vì trùng chỗ: {len(gop)}",
        f"- địa chỉ trích dẫn rỗng đã bỏ: {len(rong)}",
        "", "## Cần người duyệt", "",
    ]

    duyet = doc_da_duyet()
    da_duyet_cau = duyet.get("nhieu_cau_mot_dieu_khoan", {})
    da_duyet_nguon = duyet.get("nhieu_nguon", {})
    che_doi_moi = [c for c in che_doi if f"{local_name(c[5])}|{c[2]}" not in da_duyet_cau]
    khac_van_ban_moi = [x for x in khac_van_ban if x[0] not in da_duyet_nguon]
    # Mục đã duyệt mà không còn khớp gì: dữ liệu đã đổi nên lý do cũ không còn đúng.
    thua = (sorted(set(da_duyet_cau) - {f"{local_name(c[5])}|{c[2]}" for c in che_doi})
            + sorted(set(da_duyet_nguon) - {khoa for khoa, _ in khac_van_ban}))
    dong += [f"Đã duyệt và giữ nguyên: {len(che_doi) - len(che_doi_moi)} chỗ nhiều câu, "
             f"{len(khac_van_ban) - len(khac_van_ban_moi)} câu hai văn bản cùng nói, "
             f"{len(khong_nguon) - len([x for x in khong_nguon if x not in set(duyet.get('khong_nguon', {}).get('thuc_the', []))])} "
             f"thực thể chỉ có danh tính (lý do ghi trong `reviewed.json`).", ""]
    che_doi = che_doi_moi
    if che_doi:
        cat = sum(1 for c in che_doi if c[4])
        dong += [f"### {len(che_doi)} chỗ một điều khoản mang nhiều câu", "",
                 f"`✂ cắt đôi` ({cat} chỗ) là một câu của quy chế bị cắt ở chỗ động từ — lấy lại",
                 "câu gốc trong `references/` rồi nhập thành một câu. `· xem lại` là những chỗ",
                 "có thể vốn là nhiều phát biểu thật, cần người đọc quyết.", ""]
        for _, nhan, toa_do, cac_cau, la_che_doi, _iri in che_doi:
            dau = "✂ cắt đôi" if la_che_doi else "· xem lại"
            dong.append(f"- {dau} — **{nhan}** · {toa_do}")
            dong += [f"    - {c}" for c in cac_cau]
        dong.append("")
    if cung_van_ban:
        dong += [f"### {len(cung_van_ban)} câu nằm ở hai chỗ của cùng một văn bản", "",
                 "Gần như luôn là câu bị chép sang chỗ không nói ra nó, nên không duyệt được:",
                 "đọc văn bản gốc rồi đặt lại về một chỗ bằng `dat_lai_cau` hoặc `rut_trich_dan`.", ""]
        dong += [f"- `{khoa}` — {'; '.join(cho)}" for khoa, cho in cung_van_ban]
        dong.append("")
    if khac_van_ban_moi:
        dong += [f"### {len(khac_van_ban_moi)} câu dẫn từ hai văn bản, chưa ghi lý do", "",
                 "Đọc cả hai văn bản. Nếu cả hai thật sự nói ra câu này thì ghi lý do vào",
                 "`reviewed.json` với khoá bên dưới; nếu không thì gỡ ở chỗ không nói ra nó.", ""]
        dong += [f"- `{khoa}` — {'; '.join(cho)}" for khoa, cho in khac_van_ban_moi]
        dong.append("")
    if dieu_tho:
        dong += [f"### {len(dieu_tho)} trích dẫn cả một điều trong khi đã có địa chỉ mịn hơn", "",
                 ", ".join(dieu_tho), ""]
    if thua:
        dong += [f"### {len(thua)} mục trong `reviewed.json` không còn khớp gì", "",
                 "Dữ liệu đã đổi nên lý do ghi ở đó không còn đúng; xoá mục đi.", ""]
        dong += [f"- `{khoa}`" for khoa in thua]
        dong.append("")
    khong_nguon_moi = [x for x in khong_nguon if x not in set(duyet.get("khong_nguon", {}).get("thuc_the", []))]
    if khong_nguon_moi:
        dong += [f"### {len(khong_nguon_moi)} thực thể không có phát biểu nào kèm nguồn", "",
                 ", ".join(khong_nguon_moi), ""]
    if thieu:
        dong += [f"### {len(thieu)} dữ kiện không tìm lại được", ""] + [f"- {t}" for t in thieu[:40]] + [""]
    if bo.canh_bao:
        dong += [f"### {len(bo.canh_bao)} cảnh báo lúc chuyển", ""] + [f"- {c}" for c in bo.canh_bao[:40]] + [""]
    if gop or rong:
        dong += ["## Địa chỉ trích dẫn đã dọn", ""]
        dong += [f"- gộp: {x}" for x in gop] + [f"- bỏ vì không còn câu nào: {x}" for x in rong] + [""]
    if bo.ghi_chu:
        dong += [f"## Ghi chú ({len(bo.ghi_chu)})", ""] + [f"- {c}" for c in bo.ghi_chu[:40]]
    BAO_CAO.write_text("\n".join(dong) + "\n", encoding="utf-8")

    print(f"cũ  : {len(g)} bộ ba")
    print(f"mới : {tong} câu · {ngoai} ngoài túi · {len(tui)} túi")
    print(f"nguồn thô {nguon_tho} · địa chỉ trích dẫn {so_dia_chi}")
    for k, v in sorted(dem.items()):
        print(f"   {k}: {v}")
    print(f"\nkhông tìm lại được: {len(thieu)} dữ kiện")
    for t in thieu[:10]:
        print(f"   ⚠ {t}")
    print(f"một điều khoản mang nhiều câu: {len(che_doi)} chỗ "
          f"({sum(1 for c in che_doi if c[4])} chỗ là câu bị cắt đôi)")
    print(f"câu nằm ở hai chỗ của cùng một văn bản: {len(cung_van_ban)}")
    print(f"câu dẫn từ hai văn bản chưa ghi lý do: {len(khac_van_ban_moi)}")
    print(f"trích dẫn cả điều dù có địa chỉ mịn hơn: {len(dieu_tho)}")
    print(f"mục duyệt không còn khớp: {len(thua)}")
    print(f"địa chỉ gộp: {len(gop)} · địa chỉ rỗng đã bỏ: {len(rong)}")
    print(f"thực thể không có phát biểu kèm nguồn: {len(khong_nguon_moi)}")
    print(f"cảnh báo: {len(bo.canh_bao)} · ghi chú: {len(bo.ghi_chu)}")
    for c in bo.canh_bao[:5]:
        print(f"   ⚠ {c}")


if __name__ == "__main__":
    main()

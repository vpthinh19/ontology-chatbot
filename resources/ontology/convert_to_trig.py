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

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from ontchatbot.search.vocabulary import ACADEMIC, local_name

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
        if ten in self._dung_ten and self._dung_ten[ten] != node:
            duoi = re.sub(r"[^A-Za-z0-9]", "", local_name(node))[-4:]
            ten = f"{ten}_{duoi}"
            self.canh_bao.append(f"trùng tên, phải thêm hậu tố: {local_name(node)} → {ten}")
        self._dung_ten[ten] = node
        self.ten_moi[node] = ten
        return ten

    def moi(self, node: URIRef) -> URIRef:
        return URIRef(NS + self.dat_ten(node))

    # --- tầng nguồn ----------------------------------------------------------

    def dung_tang_nguon(self, ra: Graph) -> None:
        """Gộp cặp Quyết định/Quy chế, rồi dựng địa chỉ trích dẫn cho phần văn bản."""

        van_ban = [d for d in self.g.subjects(RDF.type, OWL.NamedIndividual) if self.lop(d) & LOP_NGUON]
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
        return text[: cat.start()].strip() if cat else text

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
                  if not (self.lop(i) & (LOP_VAN_BAN | LOP_NGUON))]

        for node in sorted(ca_the, key=str):
            goc = self.node_goc(node)
            trung_gian = bool(self.lop(node) & LOP_TRUNG_GIAN)
            tui = self.tui_cua(ra=mac_dinh, node=node) or self.tui_cua(ra=mac_dinh, node=goc)

            # Danh tính chỉ của thực thể thật, không của node trung gian.
            if not trung_gian:
                for lop in self.g.objects(node, RDF.type):
                    if lop == OWL.NamedIndividual:
                        continue
                    ten_lop = pascal(self.nhan(lop))
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


def doi_chieu(bo: BoChuyenDoi, ds, da_sua: set = frozenset()) -> list[str]:
    """Đã trừ những gì cố ý bỏ: câu bị thay theo quy chế, thực thể bị xoá, và nội
    dung trùng y hệt nhãn."""

    """Mọi dữ kiện cũ phải xuất hiện lại. Dựng lại kỳ vọng từ đồ thị cũ, rồi so."""

    co_that = {(s, p, o) for s, p, o, _ in ds.quads((None, None, None, None))}
    _sc = json.loads(SUA_CHUA.read_text(encoding="utf-8")) if SUA_CHUA.exists() else {}
    da_xoa = {ACADEMIC[m["thuc_the"]] for m in _sc.get("xoa", [])}
    #: Câu mô tả được thay bằng câu gốc của quy chế và chuyển vào túi.
    da_dat_nguon = {ACADEMIC[m["thuc_the"]] for m in _sc.get("dat_nguon", [])}
    thieu: list[str] = []
    for node in sorted(bo.g.subjects(RDF.type, OWL.NamedIndividual), key=str):
        if bo.lop(node) & (LOP_VAN_BAN | LOP_NGUON):
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
                if can not in co_that:
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
            if (can[0], can[1]) in da_sua:
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
        if str(toa_) in theo_toa_do:
            bo.ghi_chu.append(f"toạ độ {str(toa_)!r} có ở nhiều nguồn — mục sửa chữa nào chạm tới nó phải nêu nguon_hien_tai")
        theo_toa_do.setdefault(str(toa_), tui_)
    da_sua: set[tuple] = set()
    dem = 0

    def dia_chi_moi(toa_do: str, nguon_goc) -> URIRef:
        """Địa chỉ trích dẫn cho một toạ độ chưa có; dựng dưới nguồn được chỉ định."""

        khoa = (toa_do, str(nguon_goc))
        if khoa in theo_cap:
            return theo_cap[khoa]
        iri = URIRef(NS + "TD" + pascal(str(nguon_goc).rsplit("#", 1)[-1] + " " + toa_do)[:28])
        mac_dinh.add((iri, RDF.type, ACADEMIC.DiaChiTrichDan))
        mac_dinh.add((iri, ACADEMIC.thuocNguon, nguon_goc))
        mac_dinh.add((iri, ACADEMIC.toaDo, Literal(toa_do, lang="vi")))
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
    from rdflib import Dataset

    g = Graph()
    g.parse(NGUON_TTL, format="turtle")
    bo = BoChuyenDoi(g)
    bo.dung_ban_do_cha()

    ds = Dataset()
    mac_dinh = ds.default_graph
    bo.dung_tang_nguon(mac_dinh)
    dem = bo.chuyen_phat_bieu(ds, mac_dinh)
    dem["câu sửa lại theo quy chế"], da_sua = ap_dung_sua_chua(bo, ds, mac_dinh)

    tui = {q[3] for q in ds.quads((None, None, None, None))} - {mac_dinh.identifier}
    ngoai = len(list(mac_dinh))
    tong = len(list(ds.quads((None, None, None, None))))
    thieu = doi_chieu(bo, ds, da_sua)
    che_doi = cau_bi_che_doi(ds, mac_dinh)
    # Khoá đối chiếu gồm cả tên cũ lẫn tên mới: node trung gian tan đi nên không
    # phải lúc nào cũng có tên mới, và tên mới còn phụ thuộc thứ tự sinh.
    nhieu_nguon = sorted(
        (str(next(iter(mac_dinh.objects(bo.moi(node), RDFS.label)), local_name(node))),
         [bo.toa_do_cua(phan) for phan in sorted(g.objects(node, ACADEMIC.basedOn), key=str)],
         (local_name(node), bo.ten_moi.get(node, local_name(node))))
        for node in g.subjects(RDF.type, OWL.NamedIndividual)
        if not (bo.lop(node) & (LOP_VAN_BAN | LOP_NGUON))
        and len(list(g.objects(node, ACADEMIC.basedOn))) > 1)
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
        and local_name(s_) not in bo.gop_lop_da_dung)
    DICH_TRIG.write_bytes(ds.serialize(format="trig", encoding="utf-8"))
    BANG_DOI.write_text(
        json.dumps({local_name(k): v for k, v in sorted(bo.ten_moi.items(), key=lambda x: str(x[0]))},
                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    nguon_tho = len(set(bo.nguon_cua_phan.values()))
    dong = [
        "# Báo cáo chuyển đổi ontology sang TriG", "",
        f"- cũ: {len(g)} bộ ba, {len(set(g.subjects(RDF.type, OWL.NamedIndividual)))} cá thể",
        f"- mới: {tong} câu, trong đó {ngoai} nằm ngoài túi",
        f"- nguồn thô: {nguon_tho} · địa chỉ trích dẫn: {len(bo.dia_chi)} · túi dùng thật: {len(tui)}",
        "",
        "## Đã chuyển", "",
        *[f"- {k}: {v}" for k, v in sorted(dem.items())],
        f"- lớp gộp lại thành lớp chung kèm ô loại: {len(bo.gop_lop_da_dung)}",
        "", "## Cần người duyệt", "",
    ]

    duyet = doc_da_duyet()
    da_duyet_cau = duyet.get("nhieu_cau_mot_dieu_khoan", {})
    da_duyet_nguon = duyet.get("nhieu_nguon", {})
    che_doi_moi = [c for c in che_doi if f"{local_name(c[5])}|{c[2]}" not in da_duyet_cau]
    nhieu_nguon_moi = [x for x in nhieu_nguon if not (set(x[2]) & set(da_duyet_nguon))]
    dong += [f"Đã duyệt và giữ nguyên: {len(che_doi) - len(che_doi_moi)} chỗ nhiều câu, "
             f"{len(nhieu_nguon) - len(nhieu_nguon_moi)} thực thể nhiều nguồn, "
             f"{len(khong_nguon) - len([x for x in khong_nguon if x not in set(duyet.get('khong_nguon', {}).get('thuc_the', []))])} "
             f"thực thể chỉ có danh tính (lý do ghi trong `reviewed.json`).", ""]
    che_doi, nhieu_nguon = che_doi_moi, nhieu_nguon_moi
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
    if nhieu_nguon:
        dong += [f"### {len(nhieu_nguon)} thực thể dẫn từ hai nguồn trở lên", "",
                 "Mọi phát biểu của chúng được nhân vào từng túi, vì dữ liệu cũ không nói",
                 "dữ kiện nào thuộc nguồn nào. Cần gán lại từng câu về đúng điều khoản.", ""]
        dong += [f"- **{nhan}** — {', '.join(toa)}" for nhan, toa, _ in nhieu_nguon]
        dong.append("")
    khong_nguon_moi = [x for x in khong_nguon if x not in set(duyet.get("khong_nguon", {}).get("thuc_the", []))]
    if khong_nguon_moi:
        dong += [f"### {len(khong_nguon_moi)} thực thể không có phát biểu nào kèm nguồn", "",
                 ", ".join(khong_nguon_moi), ""]
    if thieu:
        dong += [f"### {len(thieu)} dữ kiện không tìm lại được", ""] + [f"- {t}" for t in thieu[:40]] + [""]
    if bo.canh_bao:
        dong += [f"### {len(bo.canh_bao)} cảnh báo lúc chuyển", ""] + [f"- {c}" for c in bo.canh_bao[:40]] + [""]
    if bo.ghi_chu:
        dong += [f"## Ghi chú ({len(bo.ghi_chu)})", ""] + [f"- {c}" for c in bo.ghi_chu[:40]]
    BAO_CAO.write_text("\n".join(dong) + "\n", encoding="utf-8")

    print(f"cũ  : {len(g)} bộ ba")
    print(f"mới : {tong} câu · {ngoai} ngoài túi · {len(tui)} túi")
    print(f"nguồn thô {nguon_tho} · địa chỉ trích dẫn {len(bo.dia_chi)}")
    for k, v in sorted(dem.items()):
        print(f"   {k}: {v}")
    print(f"\nkhông tìm lại được: {len(thieu)} dữ kiện")
    for t in thieu[:10]:
        print(f"   ⚠ {t}")
    print(f"một điều khoản mang nhiều câu: {len(che_doi)} chỗ "
          f"({sum(1 for c in che_doi if c[4])} chỗ là câu bị cắt đôi)")
    print(f"thực thể dẫn từ hai nguồn trở lên: {len(nhieu_nguon)}")
    print(f"thực thể không có phát biểu kèm nguồn: {len(khong_nguon_moi)}")
    print(f"cảnh báo: {len(bo.canh_bao)} · ghi chú: {len(bo.ghi_chu)}")
    for c in bo.canh_bao[:5]:
        print(f"   ⚠ {c}")


if __name__ == "__main__":
    main()

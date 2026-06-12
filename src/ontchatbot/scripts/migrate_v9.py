"""Migrate the academic-procedure ontology v8 → v9 (reproducible, in-place text).

Step 2 of the redesign (docs/redesign/01). The transform is *textual* on the
OWL/XML so every assertion we do not touch survives byte-for-byte and the file
stays Protégé-friendly. Five changes, all driven by the tables below:

1. **Rename** every class/individual URI to the v9 convention (Vietnamese, no
   diacritics, PascalCase, no underscores). ``rdfs:label`` text is untouched.
2. **Split the fee dimension**: drop free-text ``appliesToTarget``; add ``Khoa``
   (cohort) + ``Nganh`` (program) classes and ``appliesToCohort`` /
   ``appliesToProgram`` edges so a fee query can *intersect* (K65 ∩ CNTT → 1).
3. **Structure conditions**: add ``metric``/``comparator``/``thresholdValue``/
   ``isQuantitative`` (+ ``conditionText`` = the prose) → unlocks the ELIGIBILITY
   ``cpa >= 5.5`` verdict.
4. **Clean aliases**: ``hasAlias`` keeps only name variants; question-shaped
   aliases are harvested to ``datasets/intent_seed.jsonl`` for step-3 training.
5. **Fix data errors**: ``QuyTrinhChuyenNganh`` now outputs a chuyển-ngành
   result (was wrongly the bảo-lưu output); the ``Phi_K63_620K`` casing is
   normalised by the rename.

Inverse edges (doc change #4) are deliberately *not* declared: the planner
already synthesises inverse traversal from domain/range, and an undeclared-but-
asserted-less ``owl:inverseOf`` would break the executor's forward walk.

Usage: ``uv run --extra inference python -m ontchatbot.scripts.migrate_v9``
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..config import DATASET_DIR, ONTOLOGY_DIR

SRC = ONTOLOGY_DIR / "Ontology_AcademicProcedure_v8.owx"
DST = ONTOLOGY_DIR / "Ontology_AcademicProcedure_v9.owx"
SEED = DATASET_DIR / "intent_seed.jsonl"


# 1 ─ URI rename map (old local-name → v9 local-name). Only changed names.
RENAME: dict[str, str] = {
    # Classes
    "AcademicProcedure": "QuyTrinhHocVu",
    "AdministrativeOffice": "PhongBanHanhChinh",
    "Condition": "DieuKien",
    "Document": "TaiLieuBieuMau",
    "FeeCategory": "DinhMucHocPhi",
    "OutputResult": "KetQuaDauRa",
    "PaymentMethod": "PhuongThucThanhToan",
    "Regulation": "QuyDinh",
    # Procedures
    "QuyTrinh_BaoLuu": "QuyTrinhBaoLuu",
    "QuyTrinh_ChuyenNganh": "QuyTrinhChuyenNganh",
    "QuyTrinh_DangKyHocPhan": "QuyTrinhDangKyHocPhan",
    "QuyTrinh_HocCaiThien": "QuyTrinhHocCaiThien",
    "QuyTrinh_HocLai": "QuyTrinhHocLai",
    "QuyTrinh_NopHocPhi": "QuyTrinhNopHocPhi",
    "QuyTrinh_RutMonHoc": "QuyTrinhRutMonHoc",
    "QuyTrinh_XetHocBong": "QuyTrinhXetHocBong",
    "QuyTrinh_XetTotNghiep": "QuyTrinhXetTotNghiep",
    # Offices
    "PhongCTSV": "PhongCongTacSinhVien",
    "PhongKHTC": "PhongKeHoachTaiChinh",
    # Conditions
    "DieuKienBaoLuu_CaNhan": "DieuKienBaoLuuCaNhan",
    "DieuKienBaoLuu_QuocTe": "DieuKienBaoLuuQuocTe",
    "DieuKienBaoLuu_VuTrang": "DieuKienBaoLuuVuTrang",
    "DieuKienBaoLuu_YTe": "DieuKienBaoLuuYTe",
    "DieuKienChuyenNganh_NamHoc": "DieuKienChuyenNganhNamHoc",
    "DieuKienHocBong_DiemHocTap": "DieuKienHocBongDiemHocTap",
    "DieuKienHocBong_DiemRenLuyen": "DieuKienHocBongDiemRenLuyen",
    "DieuKienHocBong_ThoiGian": "DieuKienHocBongThoiGian",
    "DieuKienHocBong_TinChi": "DieuKienHocBongTinChi",
    "DieuKienTotNghiep_CPA": "DieuKienTotNghiepCPA",
    "DieuKienTotNghiep_KyLuat": "DieuKienTotNghiepKyLuat",
    "DieuKienTotNghiep_NghiaVu": "DieuKienTotNghiepNghiaVu",
    "DieuKienTotNghiep_NgoaiNgu": "DieuKienTotNghiepNgoaiNgu",
    "DieuKienTotNghiep_TinChi": "DieuKienTotNghiepTinChi",
    # Outputs
    "Output_CoTenTrongDanhSachLop": "KetQuaCoTenTrongDanhSachLop",
    "Output_DuocBaoLuu": "KetQuaDuocBaoLuu",
    "Output_DuocXetTotNghiep": "KetQuaDuocXetTotNghiep",
    "Output_GhiNhanDiemCaoHon": "KetQuaGhiNhanDiemCaoHon",
    "Output_NhanHocBong": "KetQuaNhanHocBong",
    "Output_XoaTenKhoiLop": "KetQuaXoaTenKhoiLop",
    # Payment methods
    "BankTransfer": "ThanhToanTaiQuayNganHang",
    "PayOnline": "ThanhToanTrucTuyen",
    # Fees (one per cohort × price-band)
    "Phi_GiaoDucTongQuat": "HocPhiGiaoDucTongQuat",
    "Phi_K63_600k": "HocPhiK63CongNgheSinhHoc",
    "Phi_K63_620K": "HocPhiK63KyThuatThuySan",
    "Phi_K65_550k": "HocPhiK65QuanTriKinhDoanh",
    "Phi_K65_620k": "HocPhiK65CongNgheThongTin",
    "Phi_K66_510k": "HocPhiK66NgonNguAnh",
    "Phi_K66_550k": "HocPhiK66KinhDoanhThuongMai",
    "Phi_K66_620k": "HocPhiK66KyThuat",
    "Phi_K67_550k": "HocPhiK67KinhTeQuanLy",
    "Phi_K67_620k": "HocPhiK67KyThuat",
    # Regulations
    "Reg_QD1052": "QuyetDinh1052",
    "Reg_QD729": "QuyetDinh729",
}


# 2 ─ Cohorts. iri → (cohortCode, label, [aliases]).
COHORTS: dict[str, tuple[str, str, list[str]]] = {
    "KhoaK63": ("K63", "Khóa 63", ["k63"]),
    "KhoaK65": ("K65", "Khóa 65", ["k65"]),
    "KhoaK66": ("K66", "Khóa 66", ["k66"]),
    "KhoaK67": ("K67", "Khóa 67", ["k67"]),
}

# Programs. iri → (label, [aliases]).
PROGRAMS: dict[str, tuple[str, list[str]]] = {
    "NganhCongNgheSinhHoc": ("Công nghệ sinh học", ["cnsh"]),
    "NganhCheBienThuySan": ("Công nghệ chế biến thủy sản", []),
    "NganhKyThuatTauThuy": ("Kỹ thuật tàu thủy", []),
    "NganhNuoiTrongThuySan": ("Nuôi trồng thủy sản", []),
    "NganhQuanTriKinhDoanh": ("Quản trị kinh doanh", ["qtkd"]),
    "NganhKeToan": ("Kế toán", []),
    "NganhQuanTriKhachSan": ("Quản trị khách sạn", ["khách sạn"]),
    "NganhCongNgheThongTin": ("Công nghệ thông tin", ["cntt", "it"]),
    "NganhNgonNguAnh": ("Ngôn ngữ Anh", ["tiếng anh"]),
    "NganhKinhDoanhThuongMai": ("Kinh doanh thương mại", []),
    "NganhTaiChinhNganHang": ("Tài chính - Ngân hàng", ["tài chính"]),
    "NganhDuLich": ("Du lịch", []),
    "NganhKyThuatCoKhi": ("Kỹ thuật cơ khí", ["cơ khí"]),
    "NganhKyThuatOTo": ("Kỹ thuật ô tô", ["ô tô", "oto"]),
    "NganhXayDung": ("Xây dựng", []),
    "NganhCongNgheThucPham": ("Công nghệ thực phẩm", ["thực phẩm"]),
    "NganhQuanLyThuySan": ("Quản lý thủy sản", ["thủy sản"]),
    "NganhMarketing": ("Marketing", []),
    "NganhHeThongThongTinQuanLy": ("Hệ thống thông tin quản lý", ["httt"]),
    "NganhLuat": ("Luật", []),
    "NganhKinhTePhatTrien": ("Kinh tế phát triển", []),
    "NganhKhoaHocHangHai": ("Khoa học hàng hải", []),
    "NganhKyThuatNhiet": ("Kỹ thuật nhiệt", ["nhiệt"]),
    "NganhCoDienTu": ("Cơ điện tử", []),
    "NganhKyThuatDien": ("Kỹ thuật điện", ["điện"]),
}

# fee iri (v9) → (cohort iri | None, [program iris]).
FEE_DIMENSIONS: dict[str, tuple[str | None, list[str]]] = {
    "HocPhiGiaoDucTongQuat": (None, []),  # applies to all → no dimension edge
    "HocPhiK63CongNgheSinhHoc": ("KhoaK63", ["NganhCongNgheSinhHoc"]),
    "HocPhiK63KyThuatThuySan": ("KhoaK63", ["NganhCheBienThuySan",
                                            "NganhKyThuatTauThuy",
                                            "NganhNuoiTrongThuySan"]),
    "HocPhiK65QuanTriKinhDoanh": ("KhoaK65", ["NganhQuanTriKinhDoanh",
                                              "NganhKeToan",
                                              "NganhQuanTriKhachSan"]),
    "HocPhiK65CongNgheThongTin": ("KhoaK65", ["NganhCongNgheThongTin"]),
    "HocPhiK66NgonNguAnh": ("KhoaK66", ["NganhNgonNguAnh"]),
    "HocPhiK66KinhDoanhThuongMai": ("KhoaK66", ["NganhKinhDoanhThuongMai",
                                                "NganhTaiChinhNganHang",
                                                "NganhDuLich"]),
    "HocPhiK66KyThuat": ("KhoaK66", ["NganhKyThuatCoKhi", "NganhKyThuatOTo",
                                     "NganhXayDung", "NganhCongNgheThucPham",
                                     "NganhQuanLyThuySan"]),
    "HocPhiK67KinhTeQuanLy": ("KhoaK67", ["NganhMarketing",
                                          "NganhHeThongThongTinQuanLy",
                                          "NganhLuat", "NganhKinhTePhatTrien",
                                          "NganhKhoaHocHangHai"]),
    "HocPhiK67KyThuat": ("KhoaK67", ["NganhKyThuatNhiet", "NganhCoDienTu",
                                     "NganhKyThuatDien"]),
}


# 3 ─ Structured conditions. iri (v9) → metric/comparator/threshold (quantitative
# only; everything else stays qualitative). conditionText defaults to the label.
QUANT_CONDITIONS: dict[str, tuple[str, str, float]] = {
    "DieuKienTotNghiepCPA": ("CPA", ">=", 5.5),
    "DieuKienHocBongDiemHocTap": ("diemHocTap", ">=", 7.0),
    "DieuKienHocBongTinChi": ("soTinChi", ">=", 14),
    "DieuKienHocLai": ("diemHocPhan", "<", 5.0),
}


# 4 ─ Aliases to KEEP (name variants only), keyed by v9 iri. Anything else on a
# procedure in v8 is harvested as intent-train seed.
KEPT_ALIASES: dict[str, list[str]] = {
    # Procedures — trimmed to name variants
    "QuyTrinhBaoLuu": ["bao luu", "bảo lưu", "bl"],
    "QuyTrinhChuyenNganh": ["chuyen nganh", "chuyển ngành", "doi nganh", "đổi ngành"],
    "QuyTrinhDangKyHocPhan": ["dang ky hoc phan", "đăng ký học phần", "dkmh",
                              "đkmh", "đăng ký môn", "đăng ký tín chỉ",
                              "dang ki mon hoc"],
    "QuyTrinhHocCaiThien": ["hoc cai thien", "học cải thiện", "cải thiện cpa",
                            "cai thien diem", "nâng điểm", "cày lại điểm"],
    "QuyTrinhHocLai": ["hoc lai", "học lại", "no mon", "nợ môn", "rớt môn",
                       "trượt môn"],
    "QuyTrinhNopHocPhi": ["nop hoc phi", "nộp học phí", "dong hoc phi",
                          "đóng học phí", "hoc phi", "đóng tiền học",
                          "gia hạn học phí"],
    "QuyTrinhRutMonHoc": ["rut mon", "rút môn", "hủy môn", "hủy hp",
                          "bỏ học phần", "xóa môn học"],
    "QuyTrinhXetHocBong": ["hoc bong", "học bổng", "xet hb", "xét học bổng",
                           "hbkk"],
    "QuyTrinhXetTotNghiep": ["tot nghiep", "tốt nghiệp", "xet tn",
                             "xét tốt nghiệp", "tốt nghiệp sớm"],
    # Offices — keep all v8 variants
    "PhongCongTacSinhVien": ["cog tac sv", "cong tac chinh tri",
                             "cong tac chinh tri va sinh vien",
                             "cong tac sinh vien", "ct sinh vien", "ctsv"],
    "PhongDaoTaoDaiHoc": ["p dao tao", "pdt", "phong ao tao", "phong dao tao",
                          "phong dt", "pđt"],
    "PhongKeHoachTaiChinh": ["KH-TC", "ke hoach tai chinh", "phong nop tien",
                             "phong tai chinh"],
    "VanPhongTruong": ["van phong", "van phong truong", "vp truong", "vpt",
                       "văn phòng", "văn phòng trường"],
    # Documents — new aliases so a user's short name resolves (label is formal)
    "DonXinBaoLuu": ["đơn bảo lưu", "don bao luu", "đơn nghỉ học tạm thời",
                     "don nghi hoc tam thoi"],
    "DonXinChuyenNganh": ["đơn chuyển ngành", "don chuyen nganh"],
    "DonXinHocTroLai": ["đơn học trở lại", "don hoc tro lai"],
    "DonXetTotNghiepSom": ["đơn xét tốt nghiệp", "don xet tot nghiep"],
    "DonGiaHanThoiGianNopHocPhi": ["đơn gia hạn học phí", "don gia han hoc phi"],
}

# Procedure iris (v9) whose dropped aliases become intent-train seed.
_PROCEDURE_IRIS = {v for k, v in RENAME.items() if k.startswith("QuyTrinh_")}


# Output fix: ChuyenNganh's real result.
NEW_OUTPUT = ("KetQuaDuocChuyenNganh", "Được chuyển sang ngành mới phù hợp")

# New-property rdfs:labels.
PROP_LABELS = {
    "appliesToCohort": "Áp dụng cho khóa",
    "appliesToProgram": "Áp dụng cho ngành",
    "cohortCode": "Mã khóa",
    "metric": "Chỉ số đo",
    "comparator": "Toán tử so sánh",
    "thresholdValue": "Ngưỡng",
    "isQuantitative": "Là điều kiện định lượng",
    "conditionText": "Diễn giải điều kiện",
}
CLASS_LABELS = {"Khoa": "Khóa học", "Nganh": "Ngành đào tạo"}

XSD = "http://www.w3.org/2001/XMLSchema#"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _rename_text(text: str) -> str:
    """Replace every ``#OldName`` token (delimited by ``"`` or ``<``) at once."""
    keys = sorted(RENAME, key=len, reverse=True)
    pat = re.compile(r"#(" + "|".join(re.escape(k) for k in keys) + r')(?=["<])')
    return pat.sub(lambda m: "#" + RENAME[m.group(1)], text)


def _drop_blocks(text: str, tag: str, prop: str) -> str:
    """Remove every ``<tag>`` block whose first inner element references ``prop``."""
    pat = re.compile(
        rf"[ \t]*<{tag}>\s*<\w+ IRI=\"#{re.escape(prop)}\"/>.*?</{tag}>\s*\n",
        re.DOTALL,
    )
    return pat.sub("", text)


def _harvest_aliases(text: str) -> list[dict]:
    """Pull v8 ``hasAlias`` pairs; procedure aliases not kept become seed rows."""
    pat = re.compile(
        r"<DataPropertyAssertion>\s*<DataProperty IRI=\"#hasAlias\"/>\s*"
        r"<NamedIndividual IRI=\"#([^\"]+)\"/>\s*<Literal>([^<]*)</Literal>",
        re.DOTALL,
    )
    seed: list[dict] = []
    for old_iri, alias in pat.findall(text):
        new_iri = RENAME.get(old_iri, old_iri)
        if new_iri not in _PROCEDURE_IRIS:
            continue
        if alias in KEPT_ALIASES.get(new_iri, []):
            continue
        seed.append({"text": alias, "procedure": new_iri, "intent": ""})
    return seed


# Block builders (all emit v9 names, 4-space indented to match the file).

def _decl(kind: str, iri: str) -> str:
    return f"    <Declaration>\n        <{kind} IRI=\"#{iri}\"/>\n    </Declaration>\n"


def _class_assertion(cls: str, iri: str) -> str:
    return (f"    <ClassAssertion>\n        <Class IRI=\"#{cls}\"/>\n"
            f"        <NamedIndividual IRI=\"#{iri}\"/>\n    </ClassAssertion>\n")


def _obj_assertion(prop: str, src: str, dst: str) -> str:
    return (f"    <ObjectPropertyAssertion>\n        <ObjectProperty IRI=\"#{prop}\"/>\n"
            f"        <NamedIndividual IRI=\"#{src}\"/>\n"
            f"        <NamedIndividual IRI=\"#{dst}\"/>\n    </ObjectPropertyAssertion>\n")


def _data_assertion(prop: str, iri: str, value: str, dtype: str | None = None) -> str:
    lit = (f"<Literal datatypeIRI=\"{dtype}\">{_esc(value)}</Literal>"
           if dtype else f"<Literal>{_esc(value)}</Literal>")
    return (f"    <DataPropertyAssertion>\n        <DataProperty IRI=\"#{prop}\"/>\n"
            f"        <NamedIndividual IRI=\"#{iri}\"/>\n        {lit}\n"
            f"    </DataPropertyAssertion>\n")


def _obj_domain_range(prop: str, dom: str, rng: str) -> str:
    return (f"    <ObjectPropertyDomain>\n        <ObjectProperty IRI=\"#{prop}\"/>\n"
            f"        <Class IRI=\"#{dom}\"/>\n    </ObjectPropertyDomain>\n"
            f"    <ObjectPropertyRange>\n        <ObjectProperty IRI=\"#{prop}\"/>\n"
            f"        <Class IRI=\"#{rng}\"/>\n    </ObjectPropertyRange>\n")


def _data_domain(prop: str, dom: str) -> str:
    return (f"    <DataPropertyDomain>\n        <DataProperty IRI=\"#{prop}\"/>\n"
            f"        <Class IRI=\"#{dom}\"/>\n    </DataPropertyDomain>\n")


def _label(iri: str, text: str) -> str:
    return ("    <AnnotationAssertion>\n"
            "        <AnnotationProperty abbreviatedIRI=\"rdfs:label\"/>\n"
            f"        <IRI>#{iri}</IRI>\n        <Literal>{_esc(text)}</Literal>\n"
            "    </AnnotationAssertion>\n")


def _condition_labels(text: str) -> dict[str, str]:
    """Map every v9 condition iri → its rdfs:label (for conditionText)."""
    pat = re.compile(
        r"<IRI>#(DieuKien[^<]+)</IRI>\s*<Literal>([^<]*)</Literal>", re.DOTALL)
    return {iri: lbl for iri, lbl in
            ((m[0], m[1]) for m in pat.findall(text))}


def build() -> str:
    raw = SRC.read_text(encoding="utf-8")

    seed = _harvest_aliases(raw)
    SEED.parent.mkdir(parents=True, exist_ok=True)
    SEED.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in seed) + "\n",
                    encoding="utf-8")

    # Drop blocks tied to the removed/replaced structure (use v8 names first).
    text = raw
    text = _drop_blocks(text, "DataPropertyAssertion", "appliesToTarget")
    text = _drop_blocks(text, "DataPropertyAssertion", "hasAlias")
    text = _drop_blocks(text, "Declaration", "appliesToTarget")
    text = _drop_blocks(text, "DataPropertyDomain", "appliesToTarget")
    text = _drop_blocks(text, "DataPropertyRange", "appliesToTarget")
    text = _drop_blocks(text, "DataPropertyDomain", "hasAlias")
    # The mis-wired ChuyenNganh → bảo-lưu output assertion.
    text = re.sub(
        r"[ \t]*<ObjectPropertyAssertion>\s*<ObjectProperty IRI=\"#hasOutput\"/>\s*"
        r"<NamedIndividual IRI=\"#QuyTrinh_ChuyenNganh\"/>\s*"
        r"<NamedIndividual IRI=\"#Output_DuocBaoLuu\"/>\s*</ObjectPropertyAssertion>\s*\n",
        "", text, flags=re.DOTALL)
    # The appliesToTarget label annotation.
    text = re.sub(
        r"[ \t]*<AnnotationAssertion>\s*<AnnotationProperty abbreviatedIRI=\"rdfs:label\"/>\s*"
        r"<IRI>#appliesToTarget</IRI>.*?</AnnotationAssertion>\s*\n",
        "", text, flags=re.DOTALL)

    text = _rename_text(text)
    cond_text = _condition_labels(text)

    # Assemble the v9 additions.
    parts: list[str] = []

    # Declarations
    for c in CLASS_LABELS:
        parts.append(_decl("Class", c))
    for prop in ("appliesToCohort", "appliesToProgram"):
        parts.append(_decl("ObjectProperty", prop))
    for prop in ("cohortCode", "metric", "comparator", "thresholdValue",
                 "isQuantitative", "conditionText"):
        parts.append(_decl("DataProperty", prop))
    for iri in (*COHORTS, *PROGRAMS, NEW_OUTPUT[0]):
        parts.append(_decl("NamedIndividual", iri))

    # Class assertions
    for iri in COHORTS:
        parts.append(_class_assertion("Khoa", iri))
    for iri in PROGRAMS:
        parts.append(_class_assertion("Nganh", iri))
    parts.append(_class_assertion("KetQuaDauRa", NEW_OUTPUT[0]))

    # Fixed ChuyenNganh output + fee dimension edges
    parts.append(_obj_assertion("hasOutput", "QuyTrinhChuyenNganh", NEW_OUTPUT[0]))
    for fee, (cohort, programs) in FEE_DIMENSIONS.items():
        if cohort:
            parts.append(_obj_assertion("appliesToCohort", fee, cohort))
        for prog in programs:
            parts.append(_obj_assertion("appliesToProgram", fee, prog))

    # Data: cohort codes, structured conditions, conditionText, aliases
    for iri, (code, _lbl, _al) in COHORTS.items():
        parts.append(_data_assertion("cohortCode", iri, code))
    for iri, text_val in cond_text.items():
        parts.append(_data_assertion("conditionText", iri, text_val))
        if iri in QUANT_CONDITIONS:
            metric, comp, thr = QUANT_CONDITIONS[iri]
            parts.append(_data_assertion("metric", iri, metric))
            parts.append(_data_assertion("comparator", iri, comp))
            thr_s = str(int(thr)) if float(thr).is_integer() else str(thr)
            parts.append(_data_assertion("thresholdValue", iri, thr_s, XSD + "decimal"))
            parts.append(_data_assertion("isQuantitative", iri, "true", XSD + "boolean"))
        else:
            parts.append(_data_assertion("isQuantitative", iri, "false", XSD + "boolean"))
    for iri, aliases in KEPT_ALIASES.items():
        for al in aliases:
            parts.append(_data_assertion("hasAlias", iri, al))
    for iri, (_lbl, aliases) in PROGRAMS.items():
        for al in aliases:
            parts.append(_data_assertion("hasAlias", iri, al))
    for iri, (_code, _lbl, aliases) in COHORTS.items():
        for al in aliases:
            parts.append(_data_assertion("hasAlias", iri, al))

    # Domains / ranges for new properties
    parts.append(_obj_domain_range("appliesToCohort", "DinhMucHocPhi", "Khoa"))
    parts.append(_obj_domain_range("appliesToProgram", "DinhMucHocPhi", "Nganh"))
    parts.append(_data_domain("cohortCode", "Khoa"))
    for prop in ("metric", "comparator", "thresholdValue", "isQuantitative",
                 "conditionText"):
        parts.append(_data_domain(prop, "DieuKien"))

    # Labels for new classes / individuals / properties
    for c, lbl in CLASS_LABELS.items():
        parts.append(_label(c, lbl))
    for iri, (_code, lbl, _al) in COHORTS.items():
        parts.append(_label(iri, lbl))
    for iri, (lbl, _al) in PROGRAMS.items():
        parts.append(_label(iri, lbl))
    parts.append(_label(NEW_OUTPUT[0], NEW_OUTPUT[1]))
    for prop, lbl in PROP_LABELS.items():
        parts.append(_label(prop, lbl))

    addition = "".join(parts)
    text = text.replace("</Ontology>", addition + "</Ontology>")
    return text


def _validate() -> None:
    """Load v9 with owlready2 and assert the structural invariants of step 2."""
    from owlready2 import World

    w = World()
    onto = w.get_ontology(str(DST)).load()
    by_name = {i.name: i for i in onto.individuals()}

    assert "Khoa" in {c.name for c in onto.classes()}, "Khoa class missing"
    assert "Nganh" in {c.name for c in onto.classes()}, "Nganh class missing"
    assert by_name["KhoaK65"].cohortCode == ["K65"], "cohortCode wrong"

    fee = by_name["HocPhiK65CongNgheThongTin"]
    progs = {p.name for p in fee.appliesToProgram}
    assert progs == {"NganhCongNgheThongTin"}, f"CNTT fee programs={progs}"
    assert fee.appliesToCohort[0].name == "KhoaK65"

    cpa = by_name["DieuKienTotNghiepCPA"]
    assert cpa.thresholdValue == [5.5] and cpa.comparator == [">="]
    assert cpa.isQuantitative == [True] and cpa.conditionText, "CPA condition unstructured"

    cn = by_name["QuyTrinhChuyenNganh"]
    assert {o.name for o in cn.hasOutput} == {"KetQuaDuocChuyenNganh"}, "output not fixed"

    assert not hasattr(by_name["HocPhiK65CongNgheThongTin"], "appliesToTarget") or \
        not by_name["HocPhiK65CongNgheThongTin"].appliesToTarget, "appliesToTarget remains"

    n_ind = len(by_name)
    print(f"[migrate_v9] OK — individuals={n_ind} classes={len(list(onto.classes()))} "
          f"obj_props={len(list(onto.object_properties()))}")


def main() -> None:
    DST.write_text(build(), encoding="utf-8")
    print(f"[migrate_v9] wrote {DST.name} and {SEED.name}")
    _validate()


if __name__ == "__main__":
    main()

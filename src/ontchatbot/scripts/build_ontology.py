"""Dựng lại ontology học vụ TỪ v8 — nguồn đúng, chạy lại được.

    uv run python -m ontchatbot.scripts.build_ontology

Quy trình: nạp `Ontology_AcademicProcedure_v8.owx` (owlready2) → áp **bảng map**
(đổi URI tiếng Việt + nhãn-khớp) + **alias** (mã khoá/ngành cho mức phí, alias mạnh cho
quy trình đóng học phí, dọn alias câu-hỏi) → sửa lỗi dữ liệu v8 → ghi
`Ontology_AcademicProcedure.owl` (RDF/XML).

**Script này là nguồn đúng của ontology**; file `.owl` là artifact. Đổi nhãn/alias =
sửa bảng dưới rồi chạy lại. Theo DESIGN.md §6 + memory `ontology` §1–7. Chỉ duyệt xuôi
(không khai inverseOf — §6.8 hoãn).
"""

from __future__ import annotations

import re
import unicodedata

from owlready2 import DataProperty, ObjectProperty, Thing, World, types

from ..config import ONTOLOGY_DIR

V8_PATH = ONTOLOGY_DIR / "Ontology_AcademicProcedure_v8.owx"
OUT_PATH = ONTOLOGY_DIR / "Ontology_AcademicProcedure.owl"
NS = "http://www.ntu.edu.vn/ontology/academic#"

# v8 class local → (URI mới PascalCase, rdfs:label hoa chữ đầu). KHÔNG Khoa/Ngành.
CLASS_MAP: dict[str, tuple[str, str]] = {
    "AcademicProcedure":   ("QuyTrinhHocVu",        "Quy trình học vụ"),
    "AdministrativeOffice": ("PhongBanHanhChinh",   "Phòng ban hành chính"),
    "Condition":           ("DieuKien",             "Điều kiện"),
    "Document":            ("TaiLieuBieuMau",       "Tài liệu biểu mẫu"),
    "FeeCategory":         ("DinhMucHocPhi",        "Định mức học phí"),
    "OutputResult":        ("KetQuaDauRa",          "Kết quả đầu ra"),
    "PaymentMethod":       ("PhuongThucThanhToan",  "Phương thức thanh toán"),
    "Regulation":          ("QuyDinh",              "Quy định"),
}

# v8 object-prop → (URI mới camelCase, [nhãn-khớp...]). Nhãn = chìa khoá khớp con `object`.
# Bỏ `executedVia`, `hasStep` (0 assertion trong v8).
OBJ_PROP_MAP: dict[str, tuple[str, list[str]]] = {
    "handledBy":         ("duocXuLyBoi",           ["phòng phụ trách", "phòng xử lý", "xử lý"]),
    "hasCondition":      ("yeuCauDieuKien",        ["điều kiện"]),
    "requiresDocument":  ("canTaiLieu",            ["biểu mẫu", "đơn", "tài liệu"]),
    "hasFeeCategory":    ("apDungMucHocPhi",       ["học phí", "mức học phí"]),
    "hasOutput":         ("coKetQua",              ["kết quả"]),
    "hasPaymentMethod":  ("coPhuongThucThanhToan", ["phương thức thanh toán", "thanh toán"]),
    "basedOnRegulation": ("canCuQuyDinh",          ["căn cứ", "quy định"]),
}

# v8 data-prop → (URI mới, [nhãn-khớp...]). Nhãn = chìa khoá khớp con `data`.
# Bỏ `appliesToTarget` (chuyển thành alias mức phí, dưới).
DATA_PROP_MAP: dict[str, tuple[str, list[str]]] = {
    "procedureDescription": ("noiDung",          ["nội dung", "mô tả"]),
    "feeNote":              ("ghiChuHocPhi",      ["ghi chú", "lưu ý"]),
    "feePerCredit":         ("hocPhiMoiTinChi",   ["mỗi tín chỉ", "học phí mỗi tín chỉ"]),
    "formUrl":              ("duongDanBieuMau",   ["đường dẫn", "tải biểu mẫu", "link"]),
    "headOfOffice":         ("truongPhong",       ["trưởng phòng", "phụ trách"]),
    "officeEmail":          ("email",             ["email", "thư điện tử"]),
    "officeLocation":       ("diaDiem",           ["địa điểm", "địa chỉ", "ở đâu"]),
    "officePhoneNumber":    ("soDienThoai",       ["số điện thoại", "điện thoại"]),
    "officeWebsite":        ("website",           ["website", "trang web"]),
}
ALIAS_PROP = ("tenGoiKhac", ["tên gọi khác"])   # v8 hasAlias → khớp cá thể, không phải con

# Alias mạnh cho quy trình đóng học phí (memory §5) — để thắng resolve so với từng mức phí.
FEE_PAYMENT_V8 = "QuyTrinh_NopHocPhi"
PROC_STRONG_ALIASES = ["học phí", "đóng học phí", "hp", "hoc phi"]

# Sửa lỗi v8 (§6): QuyTrinh_ChuyenNganh hasOutput=Output_DuocBaoLuu (SAI) → output đúng.
FIX_CHUYENNGANH_V8 = "QuyTrinh_ChuyenNganh"
FIX_OUTPUT_NAME = "OutputDuocChuyenNganh"
FIX_OUTPUT_LABEL = "Được chuyển ngành"

# Dọn alias rác (memory §7): bỏ alias dạng câu hỏi / câu dài, chỉ giữ biến thể tên gọi.
_ALIAS_BLOCK = {"khong", "sao", "lam", "muon", "duoc", "nao", "gi", "the", "vay"}
_ALIAS_MAX_WORDS = 4


def _norm(s: str) -> str:
    """Lowercase, bỏ dấu, chỉ chữ-số-khoảng trắng — để kiểm tra alias rác."""
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("đ", "d")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", s)).strip()


def _is_name_alias(a: str) -> bool:
    """Giữ biến thể TÊN GỌI; bỏ câu hỏi/câu dài."""
    toks = _norm(a).split()
    return bool(toks) and len(toks) <= _ALIAS_MAX_WORDS and not any(t in _ALIAS_BLOCK for t in toks)


def _dedup(items: list[str]) -> list[str]:
    return list(dict.fromkeys(x.strip() for x in items if x and x.strip()))


def _coerce(v):
    """Số tín chỉ lưu chuỗi trong v8 → int để render gọn."""
    s = str(v)
    return int(s) if s.isdigit() else v


def build() -> None:
    src = World()
    v8 = src.get_ontology("file://" + V8_PATH.resolve().as_posix()).load()

    dst = World()
    onto = dst.get_ontology(NS)

    with onto:
        classes = {old: _mk(new, Thing, label) for old, (new, label) in CLASS_MAP.items()}
        objp = {old: _mk(new, ObjectProperty, None, labels)
                for old, (new, labels) in OBJ_PROP_MAP.items()}
        datap = {old: _mk(new, DataProperty, None, labels)
                 for old, (new, labels) in DATA_PROP_MAP.items()}
        _mk(ALIAS_PROP[0], DataProperty, None, ALIAS_PROP[1])

        # Pass 1 — tạo cá thể đổi tên (chưa gán quan hệ).
        inds: dict[str, object] = {}
        oldcls_of: dict[str, str] = {}
        for ind in v8.individuals():
            oldcls = next((c.name for c in ind.is_a if c.name in CLASS_MAP), None)
            if oldcls is None:
                continue
            inds[ind.name] = classes[oldcls](ind.name.replace("_", ""))
            oldcls_of[ind.name] = oldcls
        # +1 cá thể mới cho bản sửa lỗi §6.
        fix_output = classes["OutputResult"](FIX_OUTPUT_NAME)
        fix_output.label = [FIX_OUTPUT_LABEL]

        # Pass 2 — gán nhãn, data, object, alias.
        for ind in v8.individuals():
            if ind.name not in inds:
                continue
            ni = inds[ind.name]
            ni.label = [str(x) for x in (getattr(ind, "label", []) or [])]
            for old, (new, _) in DATA_PROP_MAP.items():
                vals = list(getattr(ind, old, []) or [])
                if vals:
                    # CHỈ ép int cho học phí/tín chỉ; số điện thoại... giữ chuỗi (số 0 đầu).
                    setattr(ni, new, [_coerce(v) for v in vals] if old == "feePerCredit"
                            else [str(v) for v in vals])
            for old, (new, _) in OBJ_PROP_MAP.items():
                tgt = [inds[v.name] for v in (getattr(ind, old, []) or []) if v.name in inds]
                if tgt:
                    setattr(ni, new, tgt)
            aliases = [str(a) for a in (getattr(ind, "hasAlias", []) or []) if _is_name_alias(str(a))]
            if oldcls_of[ind.name] == "FeeCategory":
                target = list(getattr(ind, "appliesToTarget", []) or [])
                if target:
                    aliases += [c.strip() for c in str(target[0]).split(",")]
                m = re.search(r"[Kk](\d{2})", ind.name)
                if m:
                    aliases.append("k" + m.group(1))
            if aliases:
                setattr(ni, ALIAS_PROP[0], _dedup(aliases))

        # Sửa lỗi §6 + alias mạnh — sau pass 2 để ghi đè.
        inds[FIX_CHUYENNGANH_V8].coKetQua = [fix_output]
        fp = inds[FEE_PAYMENT_V8]
        fp.tenGoiKhac = _dedup(list(fp.tenGoiKhac) + PROC_STRONG_ALIASES)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    onto.save(file=str(OUT_PATH), format="rdfxml")
    _report(onto, inds)
    _print_lint(onto)


def _mk(name, base, label=None, labels=None):
    cls = types.new_class(name, (base,))
    if label is not None:
        cls.label = [label]
    if labels is not None:
        cls.label = list(labels)
    return cls


# ── Lint ontology (REVIEW §C8): bắt nhãn/alias bẩn TRƯỚC khi làm oracle dataset ──

_GENERIC_1TOKEN = {"phong", "don", "hoc", "quy", "noi", "ket", "dieu", "muc", "ban"}
_ALIAS_QUESTION = _ALIAS_BLOCK            # tái dùng tập từ-hỏi ở trên
_COHORT_RE = re.compile(r"^k\d{2}$")      # mã khoá k63..k67: chia sẻ trong-cohort là CỐ Ý
_ROOT_SAFE_DUAL = {"hoc phi"}             # nhãn lưỡng vai có chủ đích (alias cá thể ⊕ nhãn property)

# ĐÃ XÁC NHẬN BY-DESIGN (người dùng 2026-06-16) — nghiệp vụ học vụ, KHÔNG sửa:
_ACK_GENERIC_LABEL = {"don"}              # "đơn" bắt buộc của nghiệp vụ (biểu mẫu/đơn)
_ACK_LONGALIAS_CLASS = {"DinhMucHocPhi"}  # tên ngành dài (vd "Hệ thống thông tin quản lý") là nghiệp vụ
_ACK_CROSS_COHORT = True                  # alias ngành chéo khoá tất yếu: 1 ngành có ở nhiều khoá


def _camel_words(name: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=[0-9])", " ", name)


def lint_ontology(onto) -> tuple[list[str], list[str]]:
    """Soi nhãn property + alias cá thể. Trả ``(errors, warnings)``.

    ERROR = sai nguyên tắc thiết kế (phải sửa bảng map); WARNING = đáng rà tay (có thể
    cố ý như alias ngành đa-cohort). Chạy mỗi lần build để chặn rác lọt vào oracle.
    """
    errors: list[str] = []
    warns: list[str] = []

    # nhãn property theo từng kind
    for kind, props in (("object", list(onto.object_properties())),
                        ("data", list(onto.data_properties()))):
        seen: dict[str, str] = {}
        for p in props:
            labels = [str(l) for l in (getattr(p, "label", []) or [])]
            if not labels:
                errors.append(f"[{kind}] property {p.name!r} KHÔNG có rdfs:label (con không khớp được)")
            for l in labels:
                n = _norm(l)
                if n in seen and seen[n] != p.name:
                    errors.append(f"[{kind}] nhãn trùng {l!r}: {seen[n]} ⟷ {p.name}")
                seen[n] = p.name
                if len(n.split()) == 1 and n in _GENERIC_1TOKEN and n not in _ACK_GENERIC_LABEL:
                    warns.append(f"[{kind}] nhãn 1-token quá chung {l!r} ({p.name}) — dễ over-match")

    # bề mặt cá thể (name camel + label + alias) → norm
    surf: dict[str, list[tuple[str, str]]] = {}     # norm → [(individual, class)]
    alias_cohorts: dict[str, set[str]] = {}         # norm alias → tập mã khoá fee dùng nó
    prop_labels = {_norm(str(l)) for p in list(onto.object_properties()) + list(onto.data_properties())
                   for l in (getattr(p, "label", []) or [])}
    class_labels = {_norm(str(l)) for c in onto.classes() for l in (getattr(c, "label", []) or [])}
    for ind in onto.individuals():
        cls = next((c.name for c in ind.is_a if getattr(c, "name", "") != "NamedIndividual"), "?")
        cohort = re.search(r"[Kk](\d{2})", ind.name)
        forms = {_camel_words(ind.name)}
        forms.update(str(l) for l in (getattr(ind, "label", []) or []))
        aliases = [str(a) for a in (getattr(ind, "tenGoiKhac", []) or [])]
        forms.update(aliases)
        for a in aliases:
            n = _norm(a)
            toks = n.split()
            if any(t in _ALIAS_QUESTION for t in toks):
                errors.append(f"alias chứa từ-hỏi (rác sót): {a!r} trên {ind.name}")
            elif len(toks) > 5 and cls not in _ACK_LONGALIAS_CLASS:
                warns.append(f"alias dài {len(toks)} từ {a!r} ({ind.name}) — khó khớp, cân nhắc bỏ")
            if cohort and not _COHORT_RE.match(n) and len(toks) <= 4:
                alias_cohorts.setdefault(n, set()).add("k" + cohort.group(1))
        for f in forms:
            n = _norm(f)
            if not n:
                continue
            surf.setdefault(n, []).append((ind.name, cls))
            if n in prop_labels and n not in _ROOT_SAFE_DUAL:
                warns.append(f"alias/cá thể {n!r} ({ind.name}) trùng NHÃN PROPERTY — gốc dễ thành rác")

    # alias ngành dùng chung qua NHIỀU KHOÁ (vd "kinh doanh" ở k65/k66/k67) → "học phí <ngành>"
    # không cohort sẽ trả nhiều mức; cần rà tay (có thể cố ý).
    for n, cohorts in sorted(alias_cohorts.items()):
        if len(cohorts) > 1 and not _ACK_CROSS_COHORT:
            warns.append(f"alias ngành {n!r} dùng chung qua khoá {sorted(cohorts)} — truy vấn thiếu khoá sẽ mơ hồ")

    # alias chia sẻ giữa cá thể khác LỚP (mã khoá k## bỏ qua — chia sẻ trong-cohort là cố ý)
    for n, owners in surf.items():
        names = sorted({o[0] for o in owners})
        classes = {o[1] for o in owners}
        if len(names) > 1 and not _COHORT_RE.match(n) and len(classes) > 1:
            warns.append(f"alias {n!r} dùng chung qua nhiều LỚP: {names}")

    return errors, warns


def _print_lint(onto) -> None:
    """In report; ERROR → exit non-zero (gate: chặn nhãn/alias bẩn lọt vào ontology)."""
    import sys
    errors, warns = lint_ontology(onto)
    print(f"[lint] {len(errors)} error, {len(warns)} warning")
    for e in errors:
        print(f"  ERROR  {e}")
    for w in warns:
        print(f"  warn   {w}")
    if errors:
        print("[lint] FAIL — sửa bảng map trong build_ontology.py rồi build lại.")
        sys.exit(1)


def _report(onto, inds) -> None:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"[build_ontology] wrote {OUT_PATH}")
    print(f"  classes={len(list(onto.classes()))} "
          f"obj_props={len(list(onto.object_properties()))} "
          f"data_props={len(list(onto.data_properties()))} "
          f"individuals={len(list(onto.individuals()))}")
    fp = inds[FEE_PAYMENT_V8]
    cn = inds[FIX_CHUYENNGANH_V8]
    print(f"  fee-payment aliases: {list(fp.tenGoiKhac)}")
    print(f"  K65/CNTT fee aliases: {list(inds['Phi_K65_620k'].tenGoiKhac)}")
    print(f"  ChuyenNganh.coKetQua (fix §6): {[o.name for o in cn.coKetQua]}")


def main() -> None:
    build()


if __name__ == "__main__":
    main()

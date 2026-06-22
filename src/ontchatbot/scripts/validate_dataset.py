"""Oracle NGHIÊM — validate cặp ``(text, tree)`` khi sinh dataset (công cụ thời sinh-dữ-liệu).

Hàm :func:`validate_case_strict` được các công cụ dựng dataset trong ``dev/`` gọi để CHỈ giữ lại
những cặp mà cây duyệt ra đúng đáp án chuẩn. Không thuộc đường chạy/triển khai của hệ thống.

REVIEW §C5/§D: node-match KHÔNG chứng minh cây đúng (cây sai vẫn có thể ra cùng node).
Oracle nghiêm pin **toàn bộ outcome** của một cặp, không chỉ tập node:

* ``parse_strict`` — cây hỏng/nhiều chủ thể/data-có-con → reject (không nuốt lặng như production);
* ``act`` đúng kỳ vọng; act phi-query không kèm node;
* ``vague`` đúng kỳ vọng (gốc-là-class/property → bắt buộc vague);
* tập node terminal **bằng đúng** ``expected`` (so set IRI);
* lá data so **đúng property + chuỗi con giá trị** (không chỉ "có chứa" toàn cục);
* ``misses`` bằng đúng kỳ vọng (nhánh rác KHÔNG được sibling tốt che);
* trace: resolve property phải đủ mạnh (score ≥ ``MIN_PROP_SCORE``) và KHÔNG nhập nhằng
  (best − runner-up ≥ ``TIE_MARGIN``) — chặn nhãn quá chung khớp may rủi.

Đây là oracle dùng để giữ cặp dataset do Codex sinh (Recipe 2). Cũng tự-kiểm
``resources/e2e/cases.jsonl`` (mọi cây vàng phải PASS nghiêm).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ontology import DATA, OBJECT, Ontology
from ..tree import QUERY, StrictParseError, parse_strict

MIN_PROP_SCORE = 80.0      # property/cá thể resolve yếu hơn → reject (REVIEW §A2)
TIE_MARGIN = 10.0          # property best − nhì < margin (mà best < 100) → nhập nhằng → reject


@dataclass(frozen=True)
class ExpectedValue:
    """Một lá data kỳ vọng: property (local name) + chuỗi con phải có trong giá trị."""
    prop: str
    contains: str


@dataclass
class ValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)


def validate_case_strict(
    text: str,
    raw_tree: object,
    *,
    expected_act: str,
    expected_nodes: set[str] | tuple[str, ...] = (),
    expected_values: list[ExpectedValue] | tuple[ExpectedValue, ...] = (),
    expected_vague: bool = False,
    expected_misses: list[str] | tuple[str, ...] = (),
    expected_trace: tuple | None = None,
    ontology: Ontology,
    min_prop_score: float = MIN_PROP_SCORE,
    tie_margin: float = TIE_MARGIN,
) -> ValidationReport:
    """Trả :class:`ValidationReport`; ``ok=False`` kèm lý do từng lỗi (để sửa dataset).

    ``expected_trace`` (tuỳ chọn) ghim **đường đi** chứ không chỉ đích — khi đặt, trace
    thật phải khớp đúng. Đây là vũ khí chống "may mắn cùng node" (REVIEW §C6): hai cây
    khác cấu trúc nhưng cùng denotation sẽ lệch trace ⇒ bị bắt.
    """
    errors: list[str] = []

    try:
        tree = parse_strict(raw_tree)
    except StrictParseError as e:
        return ValidationReport(False, [f"strict-parse: {e}"])

    if tree.act != expected_act:
        errors.append(f"act: {tree.act!r} != kỳ vọng {expected_act!r}")

    if tree.act != QUERY:
        if expected_nodes or expected_values or expected_vague or expected_misses:
            errors.append("act phi-query không được kèm node/value/vague/miss")
        return ValidationReport(not errors, errors)

    result = ontology.traverse(tree)

    if result.vague != expected_vague:
        errors.append(f"vague: {result.vague} != kỳ vọng {expected_vague}")
    if result.vague:
        return ValidationReport(not errors, errors)   # vague dừng sớm: không xét node/value/miss

    got_nodes = {n.iri for n in result.nodes}
    if got_nodes != set(expected_nodes):
        errors.append(f"nodes: {sorted(got_nodes)} != kỳ vọng {sorted(expected_nodes)}")

    if set(result.misses) != set(expected_misses):
        errors.append(f"misses: {sorted(set(result.misses))} != kỳ vọng {sorted(set(expected_misses))}")

    errors += _check_values(result.values, list(expected_values))
    errors += _check_trace(result.trace, min_prop_score, tie_margin)

    if expected_trace is not None and trace_signature(result) != expected_trace:
        errors.append("trace lệch kỳ vọng (cây khác cấu trúc dù cùng node)")

    return ValidationReport(not errors, errors)


def trace_signature(result) -> tuple:
    """Vân tay đường đi: (kind, label, resolved, tập-sau) mỗi bước — so cấu trúc, không chỉ đích."""
    return tuple((s.kind, s.label, tuple(sorted(s.resolved)), tuple(sorted(s.after)))
                 for s in result.trace)


def _check_values(values, expected: list[ExpectedValue]) -> list[str]:
    """Lá data: tập property phải bằng đúng kỳ vọng; mỗi property phải chứa chuỗi con."""
    errs: list[str] = []
    got_props = {v.prop for v in values}
    want_props = {e.prop for e in expected}
    if got_props != want_props:
        errs.append(f"data props: {sorted(got_props)} != kỳ vọng {sorted(want_props)}")
        return errs
    for e in expected:
        joined = " ".join(str(x) for v in values if v.prop == e.prop for x in v.values)
        if e.contains not in joined:
            errs.append(f"data[{e.prop}] không chứa {e.contains!r} (giá trị: {joined[:60]!r})")
    return errs


def _check_trace(trace, min_prop_score: float, tie_margin: float) -> list[str]:
    """Resolve quá yếu / nhập nhằng → reject (chặn nhãn quá chung khớp may rủi)."""
    errs: list[str] = []
    for s in trace:
        if not s.resolved:                    # miss đã tính ở misses-check
            continue
        if s.score < min_prop_score:
            errs.append(f"resolve yếu: {s.kind} {s.label!r} score={s.score:g}")
        if s.kind in (OBJECT, DATA) and s.score < 100.0 and s.runner_up > 0.0 \
                and (s.score - s.runner_up) < tie_margin:
            errs.append(f"property nhập nhằng: {s.label!r} best={s.score:g} nhì={s.runner_up:g}")
    return errs


def case_kwargs(row: dict) -> dict:
    """Một bản ghi (catalog hoặc case) có ``tree`` + ``expected*`` → kwargs cho :func:`validate_case_strict`."""
    return dict(
        expected_act=row["tree"]["act"],
        expected_nodes=tuple(row.get("expected", [])),
        expected_values=tuple(ExpectedValue(**e) for e in row.get("expected_values", [])),
        expected_vague=bool(row.get("expected_vague", False)),
        expected_misses=tuple(row.get("expected_misses", [])),
    )

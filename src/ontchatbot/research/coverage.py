"""Machine-checkable coverage requirements for the official dataset."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ..catalogue import QuerySpec, match_target

_REQUIRED_FIELDS = {
    "priority_domains",
    "numeric_cases",
    "rejection_classes",
    "required_registers",
}
_SPLITS = ("train", "val", "test")
_REGISTERS = ("formal", "neutral", "colloquial", "noisy")
_DOMAINS = {
    "procedure",
    "tuition",
    "form",
    "academic-rule",
    "certificate",
    "out-of-domain",
    "assistant",
}
_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?")


class CoverageError(ValueError):
    """The official dataset coverage contract is invalid or incomplete."""


@dataclass(frozen=True)
class NumericCase:
    query_id: str
    split: str
    slots: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CoverageRequirements:
    priority_domains: tuple[str, ...]
    numeric_cases: tuple[NumericCase, ...]
    rejection_classes: tuple[str, ...]
    required_registers: tuple[str, ...]


def load_coverage_requirements(
    path: Path,
    catalogue: Mapping[str, QuerySpec],
) -> CoverageRequirements:
    """Load and validate the immutable official coverage requirements."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CoverageError("coverage requirements are invalid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != _REQUIRED_FIELDS:
        raise CoverageError(f"fields must be exactly {sorted(_REQUIRED_FIELDS)}")

    priority_domains = _parse_unique_names(
        payload["priority_domains"], "priority domain", accepted=_DOMAINS
    )
    rejection_classes = _parse_unique_names(
        payload["rejection_classes"], "rejection class"
    )
    required_registers = _parse_unique_names(
        payload["required_registers"], "required register", accepted=set(_REGISTERS)
    )
    if set(required_registers) != set(_REGISTERS):
        raise CoverageError(f"required registers must be exactly {list(_REGISTERS)}")

    raw_cases = payload["numeric_cases"]
    if not isinstance(raw_cases, list):
        raise CoverageError("numeric_cases must be a list")
    numeric_cases = tuple(_parse_numeric_case(raw, catalogue) for raw in raw_cases)
    if len(numeric_cases) != len(set(numeric_cases)):
        raise CoverageError("duplicate numeric case")

    return CoverageRequirements(
        priority_domains=priority_domains,
        numeric_cases=numeric_cases,
        rejection_classes=rejection_classes,
        required_registers=required_registers,
    )


def assess_coverage(
    splits: Mapping[str, list[Mapping[str, str]]],
    catalogue: Mapping[str, QuerySpec],
    requirements: CoverageRequirements,
    rejection_checklist: Mapping[str, list[str]],
    mentions: Mapping[str, tuple[str, ...]],
) -> dict[str, object]:
    """Report whether a release meets the additional official coverage contract."""

    rows_by_split = {split: splits.get(split, []) for split in _SPLITS}
    query_ids_by_split = {
        split: {row.get("query_id") for row in rows}
        for split, rows in rows_by_split.items()
    }
    # Chỉ họ ``primary`` bắt buộc có mặt trong dataset; ``secondary`` chỉ hỗ trợ runtime.
    required = {
        query_id
        for query_id, spec in catalogue.items()
        if spec.tier == "primary"
    }
    missing_query_ids = {
        split: sorted(required - query_ids)
        for split, query_ids in query_ids_by_split.items()
        if required - query_ids
    }

    registers = {
        split: _registers_by_query(rows) for split, rows in rows_by_split.items()
    }
    missing_train_registers = _missing_registers(
        registers["train"],
        {query_id: catalogue[query_id] for query_id in required},
        requirements.required_registers,
    )
    priority_query_ids = {
        query_id
        for query_id, spec in catalogue.items()
        if spec.tier == "primary" and spec.domain in requirements.priority_domains
    }
    missing_priority_registers = {
        split: _missing_registers(
            registers[split],
            {query_id: catalogue[query_id] for query_id in priority_query_ids},
            requirements.required_registers,
        )
        for split in _SPLITS
    }
    missing_priority_registers = {
        split: gaps for split, gaps in missing_priority_registers.items() if gaps
    }

    missing_numeric_cases = [
        _case_payload(case)
        for case in requirements.numeric_cases
        if not _has_numeric_case(rows_by_split[case.split], catalogue[case.query_id], case)
    ]
    missing_rejection_coverage = _missing_rejection_coverage(
        rows_by_split,
        catalogue,
        requirements,
        rejection_checklist,
    )
    name_coverage = assess_name_coverage(splits, catalogue, mentions)
    complete = not any(
        (
            missing_query_ids,
            missing_train_registers,
            missing_priority_registers,
            missing_numeric_cases,
            missing_rejection_coverage,
            name_coverage["missing"],
        )
    )
    return {
        "complete": complete,
        "missing_query_ids": missing_query_ids,
        "missing_train_registers": missing_train_registers,
        "missing_priority_registers": missing_priority_registers,
        "missing_numeric_cases": missing_numeric_cases,
        "missing_rejection_coverage": missing_rejection_coverage,
        "name_coverage": name_coverage,
    }


def require_complete_coverage(report: Mapping[str, object]) -> None:
    """Raise when an assessed release still has required coverage gaps."""

    if report.get("complete") is True:
        return
    name_coverage = report.get("name_coverage")
    if isinstance(name_coverage, Mapping):
        missing = name_coverage.get("missing")
        if isinstance(missing, list) and missing:
            details = "\n".join(
                f"- node {item.get('node')}: thiếu nhãn {item.get('label')!r}"
                for item in missing
                if isinstance(item, Mapping)
            )
            raise CoverageError(
                "coverage incomplete; các cặp (node, nhãn) chưa có dòng dạy:\n"
                + details
            )
    raise CoverageError("coverage incomplete")


def assess_name_coverage(
    splits: Mapping[str, list[Mapping[str, str]]],
    catalogue: Mapping[str, QuerySpec],
    mentions: Mapping[str, tuple[str, ...]],
) -> dict[str, object]:
    """Đo mọi cặp ``(node, tên gọi)`` đã xuất hiện trong dòng dạy hay chưa.

    Một node xuất hiện trong đích chưa đủ: chính tên gọi phải nằm trong input của
    một dòng train có đích ràng buộc tới node đó. So không phân biệt hoa/thường,
    vì hoa/thường là một trục phong cách riêng chứ không phải hai tên khác nhau.
    """

    expected = {
        (value, label)
        for spec in catalogue.values()
        if spec.tier == "primary" and spec.domain != "out-of-domain"
        for slot in spec.slots.values()
        if slot.kind == "iri"
        for value in slot.values
        for label in mentions.get(value[1:], ())
    }
    covered: set[tuple[str, str]] = set()
    for row in splits.get("train", []):
        query_id = row.get("query_id")
        target = row.get("target")
        question = row.get("input")
        if not all(isinstance(value, str) for value in (query_id, target, question)):
            continue
        spec = catalogue.get(query_id)
        if spec is None:
            continue
        binding = match_target(spec, target)
        if binding is None:
            continue
        folded_question = _fold_name(question)
        for slot_name, value in binding.items():
            slot = spec.slots.get(slot_name)
            if slot is None or slot.kind != "iri":
                continue
            for label in mentions.get(value[1:], ()):
                if _fold_name(label) in folded_question:
                    covered.add((value, label))

    missing = sorted(expected - covered, key=lambda pair: (pair[0], pair[1].casefold()))
    return {
        "total": len(expected),
        "covered": len(expected) - len(missing),
        "missing_count": len(missing),
        "missing": [
            {"node": node, "label": label}
            for node, label in missing
        ],
    }


def _fold_name(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _parse_unique_names(
    value: object,
    field: str,
    *,
    accepted: set[str] | None = None,
) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise CoverageError(f"{field}s must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise CoverageError(f"duplicate {field}")
    if accepted is not None:
        invalid = next((item for item in value if item not in accepted), None)
        if invalid is not None:
            raise CoverageError(f"invalid {field} {invalid!r}")
    return tuple(value)


def _parse_numeric_case(raw: object, catalogue: Mapping[str, QuerySpec]) -> NumericCase:
    if not isinstance(raw, dict) or set(raw) != {"query_id", "split", "slots"}:
        raise CoverageError("numeric case fields must be exactly ['query_id', 'slots', 'split']")
    query_id = raw["query_id"]
    split = raw["split"]
    slots = raw["slots"]
    if not isinstance(query_id, str) or query_id not in catalogue:
        raise CoverageError(f"unknown query_id {query_id!r}")
    if split not in _SPLITS:
        raise CoverageError(f"invalid split {split!r}")
    if not isinstance(slots, dict) or not slots:
        raise CoverageError("numeric case slots must be a non-empty object")

    declared_slots = catalogue[query_id].slots
    numeric_slots = {name for name, slot in declared_slots.items() if slot.kind == "number"}
    if not numeric_slots:
        raise CoverageError(f"numeric case query {query_id!r} has no number slots")
    if set(slots) != set(declared_slots):
        invalid = next((name for name in slots if name not in declared_slots), None)
        if invalid is not None:
            raise CoverageError(f"unknown slot {invalid!r} in numeric case")
        raise CoverageError(f"numeric case must assign every slot for {query_id}")
    for name, value in slots.items():
        spec = declared_slots[name]
        if not isinstance(value, str):
            raise CoverageError(f"numeric case slot {name!r} must be text")
        if spec.kind == "number" and not _NUMBER.fullmatch(value):
            raise CoverageError(f"numeric case slot {name!r} must be a canonical number")
        if spec.kind == "iri" and value not in spec.values:
            raise CoverageError(f"numeric case slot {name!r} has invalid IRI {value!r}")
    return NumericCase(query_id, split, tuple(sorted(slots.items())))


def _registers_by_query(
    rows: list[Mapping[str, str]],
) -> dict[str, set[str]]:
    registers: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        query_id = row.get("query_id")
        register = row.get("register")
        if isinstance(query_id, str) and isinstance(register, str):
            registers[query_id].add(register)
    return registers


def _missing_registers(
    registers: Mapping[str, set[str]],
    catalogue: Mapping[str, QuerySpec],
    required_registers: tuple[str, ...],
) -> dict[str, list[str]]:
    required = set(required_registers)
    return {
        query_id: sorted(required - registers.get(query_id, set()))
        for query_id in sorted(catalogue)
        if required - registers.get(query_id, set())
    }


def _has_numeric_case(
    rows: list[Mapping[str, str]], spec: QuerySpec, case: NumericCase
) -> bool:
    expected = dict(case.slots)
    for row in rows:
        if row.get("query_id") != case.query_id:
            continue
        target = row.get("target")
        if not isinstance(target, str):
            continue
        matched = match_target(spec, target)
        if matched is not None and all(matched.get(name) == value for name, value in expected.items()):
            return True
    return False


def _case_payload(case: NumericCase) -> dict[str, object]:
    return {"query_id": case.query_id, "split": case.split, "slots": dict(case.slots)}


def _missing_rejection_coverage(
    rows_by_split: Mapping[str, list[Mapping[str, str]]],
    catalogue: Mapping[str, QuerySpec],
    requirements: CoverageRequirements,
    rejection_checklist: Mapping[str, list[str]],
) -> dict[str, list[dict[str, str]]]:
    locations: dict[str, list[tuple[str, Mapping[str, str]]]] = defaultdict(list)
    for split, rows in rows_by_split.items():
        for row in rows:
            record_id = row.get("id")
            if isinstance(record_id, str):
                locations[record_id].append((split, row))

    missing: dict[str, list[dict[str, str]]] = {}
    for rejection_class in requirements.rejection_classes:
        required_ids = set(rejection_checklist.get(rejection_class, []))
        gaps = []
        for split in _SPLITS:
            for register in requirements.required_registers:
                if not any(
                    location_split == split
                    and row.get("register") == register
                    and _is_rejection_row(row, catalogue)
                    for record_id in required_ids
                    for location_split, row in locations.get(record_id, [])
                ):
                    gaps.append({"split": split, "register": register})
        if gaps:
            missing[rejection_class] = gaps
    return missing


def _is_rejection_row(row: Mapping[str, str], catalogue: Mapping[str, QuerySpec]) -> bool:
    query_id = row.get("query_id")
    target = row.get("target")
    if not isinstance(query_id, str) or not isinstance(target, str):
        return False
    spec = catalogue.get(query_id)
    # Các phản hồi từ chối và phản hồi khả năng đều phủ nhóm không có đáp án trực tiếp.
    return (
        spec is not None
        and spec.domain in ("out-of-domain", "assistant")
        and match_target(spec, target) is not None
    )

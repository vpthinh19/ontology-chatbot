"""Deterministic, read-only audit for a SPARQL dataset release."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Mapping, Sequence

from rdflib import Graph, RDF, RDFS, URIRef
from rdflib.namespace import OWL

from ..runtime.text import normalize_model_input
from ..settings import ONTOLOGY_NS
from .dataset import DatasetError, REQUIRED_SPLITS, validate_release
from .audit_learning import learning_evidence_report, tokenizer_report

AUDIT_VERSION = 1
_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_LOCAL_IRI = re.compile(r"(?<![A-Za-z0-9_?]):([A-Za-z][A-Za-z0-9]*)")
_META_LANGUAGE = re.compile(
    r"\b(?:ontology|class|item|cá thể|cơ sở dữ liệu|mô hình hoá|mô hình hóa)\b"
    r"|\blớp\s+(?:điều kiện|kết quả|phương thức|văn bản)\b",
    re.IGNORECASE,
)


def audit_release(
    release: Mapping[str, list[dict[str, str]]],
    graph: Graph,
    *,
    checksums: Mapping[str, str] | None = None,
    near_duplicate_threshold: float = 0.84,
    tokenizers: Mapping[str, Any] | None = None,
    validation_reports: Sequence[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return a machine report and a family-review worksheet without mutation."""

    rows = _indexed_rows(release)
    validation = _validation_report(release, graph)
    distributions = _distribution_report(release)
    duplicates = _duplicate_report(rows, near_duplicate_threshold)
    ontology = _ontology_report(release, graph)
    learning_contract = _learning_contract_report(release, ontology)
    tokenizer_reports = {
        name: tokenizer_report(name, tokenizer, release)
        for name, tokenizer in sorted((tokenizers or {}).items())
    }
    learning_evidence = learning_evidence_report(release, validation_reports)
    worksheet = _family_worksheet(
        release,
        duplicates=duplicates,
        learning_contract=learning_contract,
        learning_evidence=learning_evidence,
        tokenizer_reports=tokenizer_reports,
    )
    flag_counts = Counter(
        flag
        for family in worksheet
        for flag in family["audit_flags"]
    )
    priority_counts = Counter(family["audit_priority"] for family in worksheet)

    report = {
        "audit_version": AUDIT_VERSION,
        "read_only": True,
        "baseline": {
            "records": len(rows),
            "checksums": dict(sorted((checksums or {}).items())),
            "validation": validation,
        },
        "distributions": distributions,
        "learning_contract": learning_contract,
        "duplicates": duplicates,
        "ontology_coverage": ontology,
        "tokenizers": tokenizer_reports,
        "validation_learning_evidence": learning_evidence,
        "review": {
            "families": len(worksheet),
            "priority_counts": dict(sorted(priority_counts.items())),
            "flag_counts": dict(sorted(flag_counts.items())),
            "automatic_decisions": False,
        },
        "limitations": [
            "Lexical near-duplicate candidates are review hints, not proof of semantic leakage.",
            "Ontology terms absent from targets are coverage candidates, not automatic data gaps.",
            "Learning evidence uses validation runs only; benchmark/test metrics are excluded.",
            "Register correctness and question naturalness require human review.",
        ],
    }
    return report, worksheet


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_validation_reports(root: Path) -> list[dict[str, Any]]:
    """Load validation metrics only; benchmark metrics are deliberately excluded."""

    paths = sorted(Path(root).glob("*/seed-*/metrics.json"))
    reports = []
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("cases"), list):
            raise ValueError(f"validation report has no cases: {path}")
        value = dict(value)
        value["_audit_path"] = str(path)
        value["_audit_sha256"] = sha256_file(path)
        reports.append(value)
    return reports


def _validation_report(
    release: Mapping[str, list[dict[str, str]]],
    graph: Graph,
) -> dict[str, Any]:
    try:
        details = validate_release(dict(release), graph)
    except DatasetError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "details": details}


def _indexed_rows(
    release: Mapping[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    return [dict(row, _split=split) for split in REQUIRED_SPLITS for row in release[split]]


def _distribution_report(
    release: Mapping[str, list[dict[str, str]]],
) -> dict[str, Any]:
    rows = _indexed_rows(release)
    families_by_split = {
        split: len({row["family_id"] for row in release[split]}) for split in REQUIRED_SPLITS
    }
    targets_by_split = {
        split: len({row["target"] for row in release[split]}) for split in REQUIRED_SPLITS
    }
    family_sizes = Counter(row["family_id"] for row in rows)
    target_counts = Counter(row["target"] for row in rows)
    return {
        "records_by_split": {split: len(release[split]) for split in REQUIRED_SPLITS},
        "families": {
            "total": len(family_sizes),
            "by_split": families_by_split,
            "size_distribution": _summary(list(family_sizes.values())),
            "size_histogram": _counter_dict(Counter(family_sizes.values())),
        },
        "targets": {
            "total_unique": len(target_counts),
            "by_split": targets_by_split,
            "frequency_distribution": _summary(list(target_counts.values())),
            "frequency_histogram": _counter_dict(Counter(target_counts.values())),
        },
        "register_by_split": {
            split: dict(sorted(Counter(row["register"] for row in release[split]).items()))
            for split in REQUIRED_SPLITS
        },
        "query_shape_by_split": {
            split: dict(sorted(Counter(row["query_shape"] for row in release[split]).items()))
            for split in REQUIRED_SPLITS
        },
        "lengths": {
            "source_characters": _summary([len(row["input"]) for row in rows]),
            "source_words": _summary([len(_words(row["input"])) for row in rows]),
            "normalized_source_characters": _summary(
                [len(normalize_model_input(row["input"])) for row in rows]
            ),
            "normalized_source_words": _summary(
                [len(_words(normalize_model_input(row["input"]))) for row in rows]
            ),
            "target_characters": _summary([len(row["target"]) for row in rows]),
            "target_words": _summary([len(row["target"].split()) for row in rows]),
            "normalizer_changed_records": sum(
                normalize_model_input(row["input"]) != row["input"] for row in rows
            ),
        },
    }


def _duplicate_report(
    rows: Sequence[dict[str, str]],
    threshold: float,
) -> dict[str, Any]:
    normalized_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    prepared = []
    for row in rows:
        normalized = normalize_model_input(row["input"]).casefold()
        tokens = frozenset(_words(normalized))
        item = dict(row, _normalized=normalized, _tokens=tokens)
        prepared.append(item)
        normalized_groups[normalized].append(item)

    exact_pairs = []
    for group in normalized_groups.values():
        if len(group) < 2:
            continue
        for left_index, left in enumerate(group):
            for right in group[left_index + 1 :]:
                exact_pairs.append(_pair_record(left, right, 1.0, 1.0))

    near_pairs = []
    for left_index, left in enumerate(prepared):
        for right in prepared[left_index + 1 :]:
            if left["family_id"] == right["family_id"]:
                continue
            token_score = _jaccard(left["_tokens"], right["_tokens"])
            same_target = left["target"] == right["target"]
            if not same_target and token_score < threshold:
                continue
            sequence_score = SequenceMatcher(
                None,
                left["_normalized"],
                right["_normalized"],
                autojunk=False,
            ).ratio()
            if max(sequence_score, token_score) < threshold:
                continue
            near_pairs.append(_pair_record(left, right, sequence_score, token_score))
    near_pairs.sort(
        key=lambda pair: (
            -max(pair["sequence_ratio"], pair["token_jaccard"]),
            pair["left_id"],
            pair["right_id"],
        )
    )
    return {
        "threshold": threshold,
        "exact": {
            "pair_count": len(exact_pairs),
            "cross_split_pairs": sum(pair["cross_split"] for pair in exact_pairs),
            "pairs": exact_pairs,
        },
        "near": {
            "pair_count": len(near_pairs),
            "cross_split_pairs": sum(pair["cross_split"] for pair in near_pairs),
            "same_target_pairs": sum(pair["same_target"] for pair in near_pairs),
            "pairs": near_pairs,
        },
    }


def _pair_record(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    sequence_score: float,
    token_score: float,
) -> dict[str, Any]:
    return {
        "left_id": left["id"],
        "left_family": left["family_id"],
        "left_split": left["_split"],
        "left_input": left["input"],
        "right_id": right["id"],
        "right_family": right["family_id"],
        "right_split": right["_split"],
        "right_input": right["input"],
        "same_target": left["target"] == right["target"],
        "cross_split": left["_split"] != right["_split"],
        "sequence_ratio": round(sequence_score, 6),
        "token_jaccard": round(token_score, 6),
    }


def _ontology_report(
    release: Mapping[str, list[dict[str, str]]],
    graph: Graph,
) -> dict[str, Any]:
    target_counts = Counter(row["target"] for row in _indexed_rows(release))
    term_counts: Counter[str] = Counter()
    for target, count in target_counts.items():
        for term in set(_LOCAL_IRI.findall(target)):
            term_counts[term] += count

    object_properties = _local_subjects(graph, OWL.ObjectProperty)
    datatype_properties = _local_subjects(graph, OWL.DatatypeProperty)
    classes = _local_subjects(graph, OWL.Class)
    individuals = _local_subjects(graph, OWL.NamedIndividual)
    categories = {
        "named_individuals": individuals,
        "datatype_properties": datatype_properties,
        "object_properties": object_properties,
        "classes": classes,
    }
    report: dict[str, Any] = {}
    all_known = set().union(*categories.values())
    for name, values in categories.items():
        covered = sorted(values & term_counts.keys())
        report[name] = {
            "total": len(values),
            "covered": len(covered),
            "covered_terms": {term: term_counts[term] for term in covered},
            "uncovered_terms": sorted(values - term_counts.keys()),
        }
    report["unknown_local_terms"] = sorted(set(term_counts) - all_known)
    report["all_target_local_terms"] = dict(sorted(term_counts.items()))
    report["labelled_resources"] = len(
        {
            subject
            for subject, label in graph.subject_objects(RDFS.label)
            if isinstance(subject, URIRef) and str(subject).startswith(ONTOLOGY_NS)
        }
    )
    return report


def _learning_contract_report(
    release: Mapping[str, list[dict[str, str]]],
    ontology: Mapping[str, Any],
) -> dict[str, Any]:
    train_targets = {row["target"] for row in release["train"]}
    targets_by_split = {
        split: {row["target"] for row in release[split]} for split in REQUIRED_SPLITS
    }
    train_terms = set().union(*(_target_terms(row["target"]) for row in release["train"]))
    targets_missing: dict[str, list[dict[str, Any]]] = {}
    terms_missing: dict[str, list[str]] = {}
    for split in ("val", "test"):
        target_rows: dict[str, list[str]] = defaultdict(list)
        split_terms = set()
        for row in release[split]:
            target_rows[row["target"]].append(row["id"])
            split_terms.update(_target_terms(row["target"]))
        targets_missing[split] = [
            {"target": target, "record_ids": sorted(ids)}
            for target, ids in sorted(target_rows.items())
            if target not in train_targets
        ]
        terms_missing[split] = sorted(split_terms - train_terms)

    target_families: dict[str, set[str]] = defaultdict(set)
    target_records = Counter()
    for row in release["train"]:
        target_families[row["target"]].add(row["family_id"])
        target_records[row["target"]] += 1

    family_registers: dict[tuple[str, str], set[str]] = defaultdict(set)
    for split in ("train", "val"):
        for row in release[split]:
            family_registers[(split, row["family_id"])].add(row["register"])
    profile_histogram = Counter(len(registers) for registers in family_registers.values())
    target_family_support = {}
    for split in REQUIRED_SPLITS:
        split_target_families: dict[str, set[str]] = defaultdict(set)
        for row in release[split]:
            split_target_families[row["target"]].add(row["family_id"])
        target_family_support[split] = _counter_dict(
            Counter(len(families) for families in split_target_families.values())
        )
    target_memberships: dict[str, list[str]] = defaultdict(list)
    for target in sorted(set().union(*targets_by_split.values())):
        membership = "+".join(
            split for split in REQUIRED_SPLITS if target in targets_by_split[split]
        )
        target_memberships[membership].append(target)
    return {
        "targets_missing_from_train": targets_missing,
        "ontology_terms_missing_from_train": terms_missing,
        "train_target_support": [
            {
                "target": target,
                "records": target_records[target],
                "families": len(target_families[target]),
            }
            for target in sorted(train_targets)
        ],
        "rare_train_targets": [
            {
                "target": target,
                "records": target_records[target],
                "families": len(target_families[target]),
            }
            for target in sorted(train_targets)
            if len(target_families[target]) < 2
        ],
        "family_register_profiles": {
            "histogram": _counter_dict(profile_histogram),
            "single_register_train_val_families": profile_histogram[1],
            "four_register_train_val_families": profile_histogram[4],
        },
        "target_family_support_by_split": target_family_support,
        "target_overlap": {
            left: {
                right: len(targets_by_split[left] & targets_by_split[right])
                for right in REQUIRED_SPLITS
            }
            for left in REQUIRED_SPLITS
        },
        "target_membership_counts": {
            membership: len(targets) for membership, targets in sorted(target_memberships.items())
        },
        "targets_by_membership": dict(sorted(target_memberships.items())),
        "test_family_profiles": {
            "families": len({row["family_id"] for row in release["test"]}),
            "singleton_families": sum(
                count == 1
                for count in Counter(row["family_id"] for row in release["test"]).values()
            ),
            "note": "v1 test family IDs are per-record review units, not reviewed semantic groups",
        },
        "known_ontology_target_terms": len(ontology["all_target_local_terms"]),
    }




def _family_worksheet(
    release: Mapping[str, list[dict[str, str]]],
    *,
    duplicates: Mapping[str, Any],
    learning_contract: Mapping[str, Any],
    learning_evidence: Mapping[str, Any],
    tokenizer_reports: Mapping[str, Any],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for split in REQUIRED_SPLITS:
        for row in release[split]:
            groups[(split, row["family_id"])].append(row)

    near_family_flags: dict[str, set[str]] = defaultdict(set)
    for pair in duplicates["near"]["pairs"]:
        flag = "cross_split_lexical_near_duplicate" if pair["cross_split"] else "lexical_near_duplicate"
        near_family_flags[pair["left_family"]].add(flag)
        near_family_flags[pair["right_family"]].add(flag)

    missing_target_families = set()
    for split in ("val", "test"):
        missing_targets = {
            item["target"] for item in learning_contract["targets_missing_from_train"][split]
        }
        missing_target_families.update(
            row["family_id"] for row in release[split] if row["target"] in missing_targets
        )
    rare_targets = {item["target"] for item in learning_contract["rare_train_targets"]}
    hard_families = {
        item["family_id"]
        for item in learning_evidence.get("hard_families", [])
    }
    unknown_source_ids = {
        name: set(report["source_unknown_records"])
        for name, report in tokenizer_reports.items()
    }

    worksheet = []
    for (split, family_id), rows in sorted(groups.items()):
        flags = set(near_family_flags[family_id])
        target = rows[0]["target"]
        if family_id in missing_target_families:
            flags.add("target_missing_from_train")
        if split == "train" and target in rare_targets:
            flags.add("rare_train_target")
        if split in {"train", "val"} and len(rows) == 1:
            flags.add("singleton_train_val_family")
        if family_id in hard_families:
            flags.add("validation_answer_exact_at_most_50_percent")
        for name, record_ids in unknown_source_ids.items():
            if any(row["id"] in record_ids for row in rows):
                flags.add(f"source_unknown_token_{name}")
        if any(normalize_model_input(row["input"]) != row["input"] for row in rows):
            flags.add("normalizer_changes_input")
        if any(_META_LANGUAGE.search(row["input"]) for row in rows):
            flags.add("ontology_meta_language")

        priority = _priority(flags)
        worksheet.append(
            {
                "family_id": family_id,
                "split": split,
                "record_ids": [row["id"] for row in rows],
                "registers": [row["register"] for row in rows],
                "query_shape": rows[0]["query_shape"],
                "target": target,
                "inputs": [row["input"] for row in rows],
                "audit_priority": priority,
                "audit_flags": sorted(flags),
                "review_status": "pending",
                "reviewer_decision": "",
                "reviewer_notes": "",
            }
        )
    return worksheet


def _priority(flags: set[str]) -> str:
    high = {
        "cross_split_lexical_near_duplicate",
        "target_missing_from_train",
        "validation_answer_exact_at_most_50_percent",
        "source_unknown_token_bartpho",
        "ontology_meta_language",
    }
    medium = {
        "lexical_near_duplicate",
        "rare_train_target",
        "singleton_train_val_family",
    }
    if flags & high:
        return "high"
    if flags & medium:
        return "medium"
    return "low"


def _local_subjects(graph: Graph, kind: URIRef) -> set[str]:
    return {
        str(subject)[len(ONTOLOGY_NS) :]
        for subject in graph.subjects(RDF.type, kind)
        if isinstance(subject, URIRef) and str(subject).startswith(ONTOLOGY_NS)
    }


def _target_terms(target: str) -> set[str]:
    return set(_LOCAL_IRI.findall(target))


def _words(text: str) -> list[str]:
    return _WORD.findall(text.casefold())


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _summary(values: Sequence[int]) -> dict[str, int | float]:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "min": 0, "p50": 0, "p95": 0, "max": 0, "mean": 0.0}
    return {
        "count": len(ordered),
        "min": ordered[0],
        "p50": _percentile(ordered, 0.50),
        "p95": _percentile(ordered, 0.95),
        "max": ordered[-1],
        "mean": round(sum(ordered) / len(ordered), 6),
    }


def _percentile(values: Sequence[int], quantile: float) -> int:
    index = max(0, math.ceil(len(values) * quantile) - 1)
    return values[index]


def _counter_dict(counter: Counter[Any]) -> dict[str, int]:
    return {str(key): counter[key] for key in sorted(counter)}

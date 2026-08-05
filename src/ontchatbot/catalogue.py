"""Typed contract for supported SPARQL query families."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping

SlotKind = Literal["iri", "number"]
Domain = Literal[
    "procedure",
    "tuition",
    "form",
    "academic-rule",
    "certificate",
    "out-of-domain",
]

_DOMAINS = frozenset(
    {
        "procedure",
        "tuition",
        "form",
        "academic-rule",
        "certificate",
        "out-of-domain",
    }
)
_PLACEHOLDER = re.compile(r"\$\{([a-z][a-z0-9_]*)\}")
_IRI = re.compile(r"^:[A-Za-z][A-Za-z0-9]*$")
_NUMBER_PATTERN = r"-?(?:0|[1-9]\d*)(?:\.\d+)?"
_REQUIRED_FIELDS = {"query_id", "domain", "target_template", "slots", "coverage"}
_LOCAL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")


class CatalogueError(ValueError):
    """The query catalogue violates its public contract."""


@dataclass(frozen=True)
class SlotSpec:
    kind: SlotKind
    values: tuple[str, ...] = ()


@dataclass(frozen=True)
class CoverageSelector:
    anchor_classes: tuple[str, ...]
    paths: tuple[tuple[str, ...], ...]
    anchors: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuerySpec:
    query_id: str
    domain: Domain
    target_template: str
    slots: Mapping[str, SlotSpec]
    coverage: tuple[CoverageSelector, ...] = ()


def load_catalogue(path: Path) -> dict[str, QuerySpec]:
    """Load a JSON Lines catalogue while preserving its declared order."""

    catalogue: dict[str, QuerySpec] = {}
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CatalogueError(f"line {line_number}: invalid JSON") from exc
        try:
            spec = _parse_spec(payload)
        except CatalogueError as exc:
            raise CatalogueError(f"line {line_number}: {exc}") from exc
        if spec.query_id in catalogue:
            raise CatalogueError(f"line {line_number}: duplicate query_id {spec.query_id}")
        catalogue[spec.query_id] = spec
    if not catalogue:
        raise CatalogueError("catalogue is empty")
    return catalogue


def match_target(spec: QuerySpec, target: str) -> dict[str, str] | None:
    """Return instantiated slot values when target exactly matches its family."""

    pattern: list[str] = []
    seen: set[str] = set()
    cursor = 0
    for placeholder in _PLACEHOLDER.finditer(spec.target_template):
        pattern.append(re.escape(spec.target_template[cursor : placeholder.start()]))
        name = placeholder.group(1)
        if name in seen:
            pattern.append(f"(?P={name})")
        else:
            slot = spec.slots[name]
            if slot.kind == "iri":
                accepted = "|".join(re.escape(value) for value in slot.values)
                pattern.append(f"(?P<{name}>{accepted})")
            else:
                pattern.append(f"(?P<{name}>{_NUMBER_PATTERN})")
            seen.add(name)
        cursor = placeholder.end()
    pattern.append(re.escape(spec.target_template[cursor:]))
    matched = re.fullmatch("".join(pattern), target)
    return matched.groupdict() if matched else None


def find_query_family(
    catalogue: Mapping[str, QuerySpec],
    target: str,
) -> str | None:
    """Return the query_id whose family generates target exactly, else None.

    Rejection families are skipped: the marker never reaches SPARQL execution.
    """

    for query_id, spec in catalogue.items():
        if spec.domain == "out-of-domain":
            continue
        if match_target(spec, target) is not None:
            return query_id
    return None


def _parse_spec(payload: object) -> QuerySpec:
    if not isinstance(payload, dict) or set(payload) != _REQUIRED_FIELDS:
        raise CatalogueError(f"fields must be exactly {sorted(_REQUIRED_FIELDS)}")

    query_id = payload["query_id"]
    domain = payload["domain"]
    template = payload["target_template"]
    raw_slots = payload["slots"]
    raw_coverage = payload["coverage"]
    if not isinstance(query_id, str) or not query_id:
        raise CatalogueError("query_id must be non-empty text")
    if not isinstance(domain, str) or domain not in _DOMAINS:
        raise CatalogueError(f"invalid domain {domain!r}")
    if not isinstance(template, str) or not template:
        raise CatalogueError("target_template must be non-empty text")
    if not isinstance(raw_slots, dict):
        raise CatalogueError("slots must be an object")

    placeholders = set(_PLACEHOLDER.findall(template))
    declared = set(raw_slots)
    undeclared = sorted(placeholders - declared)
    if undeclared:
        raise CatalogueError(f"undeclared slots: {undeclared}")
    unused = sorted(declared - placeholders)
    if unused:
        raise CatalogueError(f"unused slots: {unused}")

    slots = {name: _parse_slot(name, raw) for name, raw in raw_slots.items()}
    coverage = _parse_coverage(raw_coverage)
    if domain == "out-of-domain" and coverage:
        raise CatalogueError("rejection query cannot declare coverage")
    if domain != "out-of-domain" and not coverage:
        raise CatalogueError("non-rejection query must declare coverage")
    return QuerySpec(  # type: ignore[arg-type]
        query_id,
        domain,
        template,
        slots,
        coverage,
    )


def _parse_slot(name: str, payload: object) -> SlotSpec:
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise CatalogueError(f"invalid slot name {name!r}")
    if not isinstance(payload, dict) or "kind" not in payload:
        raise CatalogueError(f"slot {name} must declare kind")
    if set(payload) - {"kind", "values"}:
        raise CatalogueError(f"slot {name} has unsupported fields")
    kind = payload["kind"]
    if kind not in {"iri", "number"}:
        raise CatalogueError(f"slot {name} has invalid kind {kind!r}")

    raw_values = payload.get("values", [])
    if not isinstance(raw_values, list) or not all(
        isinstance(value, str) and value for value in raw_values
    ):
        raise CatalogueError(f"slot {name} values must be non-empty strings")
    if len(raw_values) != len(set(raw_values)):
        raise CatalogueError(f"slot {name} has duplicate values")
    values = tuple(raw_values)
    if kind == "iri":
        if not values:
            raise CatalogueError(f"IRI slot {name} must declare values")
        invalid = next((value for value in values if not _IRI.fullmatch(value)), None)
        if invalid is not None:
            raise CatalogueError(f"invalid IRI slot value {invalid!r}")
    elif values:
        raise CatalogueError(f"number slot {name} cannot declare finite values")
    return SlotSpec(kind, values)


def _parse_coverage(payload: object) -> tuple[CoverageSelector, ...]:
    if not isinstance(payload, list):
        raise CatalogueError("coverage must be a list")
    return tuple(_parse_selector(raw) for raw in payload)


def _parse_selector(payload: object) -> CoverageSelector:
    if not isinstance(payload, dict):
        raise CatalogueError("coverage selector must be an object")
    if set(payload) - {"anchor_classes", "paths", "anchors"}:
        raise CatalogueError("coverage selector has unsupported fields")
    if "anchor_classes" not in payload or "paths" not in payload:
        raise CatalogueError("coverage selector must declare anchor_classes and paths")

    anchor_classes = _parse_local_names(
        payload["anchor_classes"],
        "anchor_classes",
        non_empty=True,
    )
    anchors = _parse_local_names(payload.get("anchors", []), "anchors")
    raw_paths = payload["paths"]
    if not isinstance(raw_paths, list) or not raw_paths:
        raise CatalogueError("coverage selector paths must be non-empty")

    paths: list[tuple[str, ...]] = []
    for raw_path in raw_paths:
        if not isinstance(raw_path, list) or not raw_path:
            raise CatalogueError("coverage path must be a non-empty list")
        path: list[str] = []
        for component in raw_path:
            if not isinstance(component, str) or not (
                component == "rdfs:label" or _LOCAL_NAME.fullmatch(component)
            ):
                raise CatalogueError(f"invalid path component {component!r}")
            path.append(component)
        paths.append(tuple(path))
    if len(paths) != len(set(paths)):
        raise CatalogueError("coverage selector has duplicate paths")
    return CoverageSelector(anchor_classes, tuple(paths), anchors)


def _parse_local_names(
    payload: object,
    field: str,
    *,
    non_empty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(payload, list) or (non_empty and not payload):
        suffix = " must be non-empty" if non_empty else " must be a list"
        raise CatalogueError(f"coverage selector {field}{suffix}")
    if not all(isinstance(value, str) and _LOCAL_NAME.fullmatch(value) for value in payload):
        raise CatalogueError(f"coverage selector {field} contains an invalid local name")
    if len(payload) != len(set(payload)):
        raise CatalogueError(f"coverage selector {field} contains duplicates")
    return tuple(payload)

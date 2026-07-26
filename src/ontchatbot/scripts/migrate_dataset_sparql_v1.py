"""Migrate reviewed Vietnamese questions from QueryPlan targets to SPARQL."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ..config import DATASET_PATH, RESOURCES
from ..dataset import validate_dataset
from ..query_engine import load_ontology

SOURCE = RESOURCES / "datasets_v1/production_v1.jsonl"
MAPPING = RESOURCES / "datasets/queryplan_to_sparql_v1.json"
_DIALOGUE_OUTPUTS = {"greeting", "unrelated", "clarify"}
_FLATTENED = {"hasCondition": "condition", "hasOutcome": "outcome"}
_ENDPOINT_NAMES = {
    "content": "content",
    "hasCondition": "condition",
    "hasOutcome": "outcome",
    "hasDocument": "document",
    "handledBy": "office",
    "basedOnRegulation": "regulation",
    "appliesTuitionRate": "tuitionRate",
    "supportsPaymentMethod": "paymentMethod",
    "email": "email",
    "headName": "headName",
    "location": "location",
    "phoneNumber": "phoneNumber",
    "websiteUrl": "websiteUrl",
    "documentUrl": "documentUrl",
    "tuitionNote": "tuitionNote",
    "tuitionPerCredit": "tuitionPerCredit",
    "programName": "programName",
    "cohortCode": "cohortCode",
}
_OBJECT_NODE_NAMES = {
    "handledBy": "officeNode",
    "hasDocument": "documentNode",
    "basedOnRegulation": "regulationNode",
    "appliesTuitionRate": "tuitionRateNode",
    "supportsPaymentMethod": "paymentMethodNode",
}


def convert_queryplan(output: str) -> str | None:
    if output in _DIALOGUE_OUTPUTS:
        return None
    lines = output.splitlines()
    if not lines or lines[0] != "query" or len(lines) < 2:
        raise ValueError(f"unsupported legacy output: {output!r}")

    routes = [_parse_route(line) for line in lines[1:]]
    multi = len(routes) > 1
    projections: list[str] = []
    patterns: list[str] = []
    used_names: Counter[str] = Counter()
    for route_index, route in enumerate(routes, 1):
        endpoint = route["steps"][-1][1] if route["steps"] else route["root"]
        base_name = _ENDPOINT_NAMES.get(endpoint, "answer") if multi else "answer"
        used_names[base_name] += 1
        output_name = base_name if used_names[base_name] == 1 else f"{base_name}{used_names[base_name]}"
        projections.append(f"?{output_name}")
        patterns.extend(_route_patterns(route, output_name, multi))

    return f"SELECT {' '.join(projections)} WHERE {{ {' '.join(patterns)} }}"


def _parse_route(line: str) -> dict:
    tokens = line.split()
    if len(tokens) < 3 or tokens[0] != "route" or tokens[1] not in {"class", "individual"}:
        raise ValueError(f"invalid legacy route: {line}")
    tail = tokens[3:]
    if len(tail) % 2:
        raise ValueError(f"invalid legacy steps: {line}")
    steps = list(zip(tail[::2], tail[1::2], strict=True))
    if any(kind not in {"object", "data"} for kind, _ in steps):
        raise ValueError(f"invalid legacy step kind: {line}")
    return {"root_kind": tokens[1], "root": tokens[2], "steps": steps}


def _route_patterns(route: dict, output_name: str, multi: bool) -> list[str]:
    root = route["root"]
    steps = list(route["steps"])

    if route["root_kind"] == "class":
        if steps:
            raise ValueError("legacy class routes must not contain steps")
        if root in {"Condition", "Outcome"}:
            prop = "condition" if root == "Condition" else "outcome"
            return [f"?item :{prop} ?{output_name} ."]
        return [f"?node a :{root} .", f"?node rdfs:label ?{output_name} ."]

    # The two old Condition->Regulation paths duplicated a regulation already
    # linked from the procedure. Query that canonical parent edge in v11.
    if len(steps) >= 2 and steps[:2] == [
        ("object", "hasCondition"),
        ("object", "basedOnRegulation"),
    ]:
        steps = [("object", "basedOnRegulation"), *steps[2:]]

    current = f":{root}"
    patterns = []
    for step_index, (kind, prop) in enumerate(steps, 1):
        final = step_index == len(steps)
        if prop in _FLATTENED:
            if kind != "object" or not final:
                raise ValueError(f"unsupported flattened route: {route}")
            patterns.append(f"{current} :{_FLATTENED[prop]} ?{output_name} .")
            continue

        if kind == "data":
            if not final:
                raise ValueError(f"datatype property must end a route: {route}")
            patterns.append(f"{current} :{prop} ?{output_name} .")
            continue

        if multi:
            node_name = _OBJECT_NODE_NAMES.get(prop, f"node{step_index}")
            node = f"?{node_name}"
        else:
            node = "?node"
        patterns.append(f"{current} :{prop} {node} .")
        current = node
        if final:
            patterns.append(f"{current} rdfs:label ?{output_name} .")
    return patterns


def migrate(source: Path = SOURCE, target: Path = DATASET_PATH, mapping_path: Path = MAPPING) -> dict:
    source_rows = [
        json.loads(line)
        for line in Path(source).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    converted = []
    mapping: dict[str, str] = {}
    excluded: Counter[str] = Counter()
    for row in source_rows:
        target_query = convert_queryplan(row["output"])
        if target_query is None:
            excluded[row["output"]] += 1
            continue
        existing = mapping.setdefault(row["output"], target_query)
        if existing != target_query:
            raise RuntimeError("legacy output mapped inconsistently")
        converted.append(
            {
                "id": row["id"],
                "family_id": row["family_id"],
                "split": row["split"],
                "register": row["register"],
                "input": row["input"],
                "target": target_query,
            }
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in converted),
        encoding="utf-8",
    )
    report = validate_dataset(converted, load_ontology())
    manifest = {
        "source": str(source),
        "target": str(target),
        "source_records": len(source_rows),
        "converted_records": len(converted),
        "excluded_dialogue": dict(sorted(excluded.items())),
        "legacy_query_targets": len(mapping),
        "validation": report,
        "mapping": dict(sorted(mapping.items())),
    }
    mapping_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--target", type=Path, default=DATASET_PATH)
    parser.add_argument("--mapping", type=Path, default=MAPPING)
    args = parser.parse_args()
    manifest = migrate(args.source, args.target, args.mapping)
    print(json.dumps({key: value for key, value in manifest.items() if key != "mapping"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

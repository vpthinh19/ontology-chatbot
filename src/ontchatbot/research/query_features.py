"""Derive overlapping research features from canonical SPARQL targets."""

from __future__ import annotations

import re
from collections.abc import Collection

_OUTER_SELECT = re.compile(r"\bSELECT\b(?P<projection>.*?)\bWHERE\b", re.IGNORECASE | re.DOTALL)
_PROJECTION_TOKEN = re.compile(r"\(|\)|\bAS\b|\?[A-Za-z][A-Za-z0-9]*", re.IGNORECASE)
_LOCAL_NAME = re.compile(r"(?<![A-Za-z0-9]):([A-Za-z][A-Za-z0-9]*)")
_AGGREGATE = re.compile(r"\b(?:COUNT|SUM|AVG|MIN|MAX)\s*\(", re.IGNORECASE)


def extract_query_features(
    query: str,
    *,
    object_properties: Collection[str] = (),
) -> dict[str, int | bool]:
    """Describe a restricted one-line SELECT without forcing one shape label."""

    local_names = set(_LOCAL_NAME.findall(query))
    return {
        "output_columns": _count_outer_projection_columns(query),
        "triple_patterns": query.count(" .") + query.count(" ; "),
        "graph_hop": bool(local_names & set(object_properties)),
        "aggregate": bool(_AGGREGATE.search(query)),
        "filter": bool(re.search(r"\bFILTER\b", query, re.IGNORECASE)),
        "group": bool(re.search(r"\bGROUP\s+BY\b", query, re.IGNORECASE)),
        "order": bool(re.search(r"\bORDER\s+BY\b", query, re.IGNORECASE)),
        "limit": bool(re.search(r"\bLIMIT\s+\d+\b", query, re.IGNORECASE)),
        "values": bool(re.search(r"\bVALUES\b", query, re.IGNORECASE)),
    }


def query_feature_tags(features: dict[str, int | bool]) -> tuple[str, ...]:
    """Turn numeric/boolean features into overlapping report groups."""

    tags = [
        "multi_column" if features["output_columns"] > 1 else "single_column",
        "multi_branch" if features["triple_patterns"] > 1 else "single_branch",
    ]
    tags.extend(
        name
        for name in (
            "graph_hop",
            "aggregate",
            "filter",
            "group",
            "order",
            "limit",
            "values",
        )
        if features[name]
    )
    return tuple(tags)


def _count_outer_projection_columns(query: str) -> int:
    match = _OUTER_SELECT.search(query)
    if match is None:
        return 0

    depth = 0
    after_as = False
    count = 0
    for token_match in _PROJECTION_TOKEN.finditer(match.group("projection")):
        token = token_match.group(0)
        if token == "(":
            depth += 1
            after_as = False
        elif token == ")":
            depth = max(0, depth - 1)
            after_as = False
        elif token.casefold() == "as":
            after_as = True
        elif token.startswith("?"):
            if depth == 0 or after_as:
                count += 1
            after_as = False
    return count

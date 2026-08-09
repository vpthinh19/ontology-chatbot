"""Execute model-generated, read-only SPARQL on the canonical ontology."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import TypeAlias

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.plugins.sparql.parser import parseQuery

from ..settings import ONTOLOGY_NS, ONTOLOGY_PATH

Primitive: TypeAlias = str | int | float | bool | None
QueryRow: TypeAlias = dict[str, Primitive]
QueryRows: TypeAlias = list[QueryRow]

PREFIXES = f"""\
PREFIX : <{ONTOLOGY_NS}>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

MAX_QUERY_CHARS = 4096
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(?:SERVICE|FROM|INSERT|DELETE|LOAD|CLEAR|CREATE|DROP|COPY|MOVE|ADD|WITH)\b",
    flags=re.IGNORECASE,
)


class SparqlError(ValueError):
    """The generated query violates the runtime contract or cannot execute."""


def load_ontology(path: Path = ONTOLOGY_PATH) -> Graph:
    """Load the canonical Turtle ontology."""

    return Graph().parse(Path(path), format="turtle")


def validate_select(query: str) -> str:
    """Validate and return a model query without trying to repair it."""

    if not isinstance(query, str):
        raise SparqlError("SPARQL query must be text")

    query = query.strip()
    if not query:
        raise SparqlError("SPARQL query is empty")
    if len(query) > MAX_QUERY_CHARS:
        raise SparqlError(f"SPARQL query exceeds {MAX_QUERY_CHARS} characters")
    if not re.match(r"^SELECT\b", query, flags=re.IGNORECASE):
        raise SparqlError("only SELECT queries are allowed")
    if re.match(r"^SELECT\s+\*", query, flags=re.IGNORECASE):
        raise SparqlError("SELECT * is not allowed; project explicit answer columns")

    forbidden = _FORBIDDEN_KEYWORDS.search(query)
    if forbidden:
        raise SparqlError(f"SPARQL keyword is not allowed: {forbidden.group(0).upper()}")

    try:
        parseQuery(PREFIXES + query)
    except Exception as exc:  # RDFLib exposes parser implementation exceptions.
        raise SparqlError(f"invalid SPARQL: {exc}") from exc
    return query


def execute_select(
    graph: Graph,
    query: str,
    *,
    max_rows: int = 100,
) -> QueryRows:
    """Run a validated SELECT and return only plain Python mappings."""

    if max_rows < 1:
        raise ValueError("max_rows must be positive")

    query = validate_select(query)
    try:
        result = graph.query(PREFIXES + query)
    except Exception as exc:
        raise SparqlError(f"SPARQL execution failed: {exc}") from exc

    columns = [str(variable) for variable in result.vars or ()]
    if not columns:
        raise SparqlError("SELECT query has no result columns")

    rows: QueryRows = []
    for row_number, row in enumerate(result, start=1):
        if row_number > max_rows:
            raise SparqlError(f"SPARQL result exceeds {max_rows} rows")
        rows.append(
            {
                column: _to_primitive(row[index], column)
                for index, column in enumerate(columns)
            }
        )
    return rows


def _to_primitive(value: object, column: str) -> Primitive:
    if value is None:
        return None
    if isinstance(value, (URIRef, BNode)):
        raise SparqlError(
            f"result column ?{column} contains a graph node; project rdfs:label or a literal"
        )
    if not isinstance(value, Literal):
        raise SparqlError(f"result column ?{column} is not an RDF literal")

    converted = value.toPython()
    if converted is None or isinstance(converted, (str, int, float, bool)):
        return converted
    # ``xsd:decimal`` thành ``Decimal``, không phải ``float``. Để nguyên thì nó
    # rơi xuống ``str`` và sĩ số 20 hiện ra thành "20.0".
    if isinstance(converted, Decimal):
        return int(converted) if converted == converted.to_integral_value() else float(converted)
    return str(converted)

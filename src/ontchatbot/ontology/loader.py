"""Ontology loading and label-map utilities (cached singletons).

The ontology is loaded once per process via ``owlready2``; the label-map JSON is
also cached. Helpers here expose the BIO inventory used by the NER head and a
small set of accessors used by the SPARQL and fuzzy modules.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Iterable

from owlready2 import Ontology, default_world

from ..config import LABEL_MAP_PATH, ONTOLOGY_PATH

_CAMEL_RE = re.compile(r"([a-z])([A-Z])")


@lru_cache(maxsize=1)
def load_label_map() -> dict[str, dict]:
    """Flatten ``label_map.json`` (a list of single-key dicts) into one dict."""
    raw = json.loads(LABEL_MAP_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for item in raw:
        out.update(item)
    return out


def ontology_tags() -> list[str]:
    """NER tags backed by an ontology class, in declaration order."""
    return [k for k, v in load_label_map().items() if v.get("type") == "ontology"]


def bio_label_list() -> list[str]:
    """Label set for the token classifier: ``O``, ``B-X``, ``I-X``."""
    out = ["O"]
    for tag in ontology_tags():
        out.extend([f"B-{tag}", f"I-{tag}"])
    return out


def class_local(tag: str) -> str:
    """Local class name (suffix of the URI) for a NER tag."""
    uri = load_label_map().get(tag, {}).get("uri", "")
    return uri.rsplit("#", 1)[-1] if "#" in uri else uri


@lru_cache(maxsize=1)
def load_ontology() -> Ontology:
    """Load the OWL ontology into the default world (cached)."""
    return default_world.get_ontology(str(ONTOLOGY_PATH)).load()


def iter_individuals(class_local_name: str) -> Iterable:
    """Iterate over every individual asserted as an instance of ``class_local_name``."""
    onto = load_ontology()
    cls = onto[class_local_name]
    return iter(cls.instances()) if cls is not None else iter(())


def short_name(individual) -> str:
    return getattr(individual, "name", str(individual))


def primary_label(individual) -> str:
    """First ``rdfs:label`` if present, otherwise the humanised local name.

    The fallback splits underscores and CamelCase boundaries, so a missing
    label produces ``"Don Xin Bao Luu"`` rather than ``"DonXinBaoLuu"``.
    """
    labels = list(getattr(individual, "label", []) or [])
    if labels:
        return str(labels[0])
    name = short_name(individual).replace("_", " ")
    return _CAMEL_RE.sub(r"\1 \2", name).strip()

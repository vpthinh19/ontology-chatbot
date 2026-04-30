"""Ontology loading and label-map utilities.

The ontology is loaded once and cached at process start. The label map (NER tag
inventory and class-to-URI mapping) is also exposed here so downstream modules
share a single source of truth.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Iterable

from owlready2 import World, Ontology, default_world

from ..config import LABEL_MAP_PATH, ONTOLOGY_NS, ONTOLOGY_PATH


@lru_cache(maxsize=1)
def load_label_map() -> dict[str, dict]:
    """Return the ordered label map keyed by NER tag (without B-/I- prefix)."""
    raw = json.loads(LABEL_MAP_PATH.read_text(encoding="utf-8"))
    flat: dict[str, dict] = {}
    for item in raw:
        for tag, meta in item.items():
            flat[tag] = meta
    return flat


def ontology_tags() -> list[str]:
    """Tags backed by an ontology class (eligible for entity recognition)."""
    return [k for k, v in load_label_map().items() if v.get("type") == "ontology"]


def all_tags() -> list[str]:
    """All tags including non-ontology intents (greeting, OOD)."""
    return list(load_label_map().keys())


def bio_label_list() -> list[str]:
    """BIO tag set used by the token classifier: O, B-X, I-X for each ontology tag."""
    labels = ["O"]
    for tag in ontology_tags():
        labels.extend([f"B-{tag}", f"I-{tag}"])
    return labels


@lru_cache(maxsize=1)
def load_ontology() -> Ontology:
    """Load the OWL ontology into the default world (cached)."""
    # ``owlready2`` infers format from extension; .owx is OWL/XML.
    onto = default_world.get_ontology(str(ONTOLOGY_PATH)).load()
    return onto


def get_world() -> World:
    return default_world


def class_uri(tag: str) -> str:
    """Resolve a NER tag to its full ontology class URI."""
    meta = load_label_map().get(tag, {})
    return meta.get("uri", "")


def short_iri(individual) -> str:
    """Strip namespace from an Owlready individual to obtain its local name."""
    return getattr(individual, "name", str(individual))


def iter_individuals(class_local_name: str) -> Iterable:
    """Iterate over all individuals asserted as members of the given class."""
    onto = load_ontology()
    cls = onto[class_local_name]
    if cls is None:
        return iter(())
    return iter(cls.instances())


# Mapping from NER tag -> ontology class local name (suffix of URI)
def tag_to_class_local(tag: str) -> str:
    uri = class_uri(tag)
    return uri.split("#", 1)[-1] if "#" in uri else uri

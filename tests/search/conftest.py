from __future__ import annotations

from pathlib import Path

import pytest

from ontchatbot.search import Ontology, TurtleFileSource

MINI_ONTOLOGY = Path(__file__).resolve().parents[1] / "fixtures" / "mini-ontology.ttl"


@pytest.fixture(scope="module")
def mini_source() -> TurtleFileSource:
    return TurtleFileSource(MINI_ONTOLOGY)


@pytest.fixture(scope="module")
def mini_ontology(mini_source) -> Ontology:
    return Ontology.from_source(mini_source)

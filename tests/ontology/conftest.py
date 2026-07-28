import pytest
from rdflib import Graph, Namespace

from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import ONTOLOGY_NS


@pytest.fixture(scope="session")
def ontology_graph() -> Graph:
    return load_ontology()


@pytest.fixture(scope="session")
def academic() -> Namespace:
    return Namespace(ONTOLOGY_NS)

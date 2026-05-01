"""Shared pytest fixtures.

The ontology takes a few seconds to parse; load it once per session and reuse
it across the test suite.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def onto():
    from ontchatbot.ontology.loader import load_ontology
    return load_ontology()


@pytest.fixture(scope="session")
def label_map():
    from ontchatbot.ontology.loader import load_label_map
    return load_label_map()

"""Shared pytest fixtures.

The ontology takes a few seconds to parse; load it once per session and
reuse it across the test suite.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def ontology():
    from ontchatbot.ontology.store import Ontology
    return Ontology.get()


# Backwards-compat alias retained for older fixtures.
@pytest.fixture(scope="session")
def onto(ontology):
    return ontology

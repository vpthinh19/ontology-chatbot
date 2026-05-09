"""Shared pytest fixtures.

The ontology takes a few seconds to parse; load it once per session.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def ontology():
    from ontchatbot.ontology import Ontology
    return Ontology.get()


@pytest.fixture(scope="session")
def onto(ontology):
    """Backwards-compat alias retained for older fixtures."""
    return ontology

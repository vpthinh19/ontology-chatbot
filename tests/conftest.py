"""Fixtures dùng chung. Ontology nạp một lần cho cả phiên test."""

from __future__ import annotations

import pytest

from ontchatbot.ontology import Ontology


@pytest.fixture(scope="session")
def ont() -> Ontology:
    return Ontology.get()

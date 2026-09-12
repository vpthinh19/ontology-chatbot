"""Lưới an toàn cho đợt tái cấu trúc: câu nào đang tra cứu đúng thì không được tụt.

Bộ câu và mốc nằm ở ``resources/end-to-end/``; bài kiểm này chỉ gọi lại đúng hàm mà
kịch bản báo cáo dùng, để hai bên không lệch nhau.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from ontchatbot.search import SearchEngine, TurtleFileSource
from ontchatbot.settings import ONTOLOGY_PATH

KIEM_TRA = Path(__file__).resolve().parents[2] / "resources" / "end-to-end" / "check_retrieval.py"


def _nap_kich_ban():
    spec = importlib.util.spec_from_file_location("check_retrieval", KIEM_TRA)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def kich_ban():
    if not KIEM_TRA.exists():
        pytest.skip("chưa có kịch bản kiểm tra tra cứu")
    return _nap_kich_ban()


@pytest.fixture(scope="module")
def ket_qua(kich_ban):
    return kich_ban.chay(SearchEngine.open(TurtleFileSource(ONTOLOGY_PATH)))


def test_no_question_that_used_to_be_retrieved_is_lost(kich_ban, ket_qua) -> None:
    if not kich_ban.MOC.exists():
        pytest.skip("chưa ghi mốc; chạy check_retrieval.py --ghi-moc")
    moc = set(json.loads(kich_ban.MOC.read_text(encoding="utf-8"))["dat"])

    tut = sorted(moc - set(ket_qua["dat"]))

    assert not tut, f"tụt so với mốc: {tut}"


def test_the_frozen_set_still_matches_the_baseline_size(kich_ban, ket_qua) -> None:
    """Bộ câu là cố định; đổi số câu là mọi con số đã đo hết so sánh được."""

    moc = json.loads(kich_ban.MOC.read_text(encoding="utf-8"))

    assert ket_qua["tong"] == moc["tong"]

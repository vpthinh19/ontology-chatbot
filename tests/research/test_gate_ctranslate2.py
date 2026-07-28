from __future__ import annotations

import argparse
import json
from pathlib import Path

from ontchatbot.research.evaluate_gate_ctranslate2 import evaluate
from ontchatbot.runtime.gate import GateDecision


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_ct2_gate_evaluation_reports_metrics_and_pytorch_parity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dataset_dir = tmp_path / "dataset"
    rows = [
        {"input": "inside one", "label": "in_scope"},
        {"input": "inside two", "label": "in_scope"},
        {"input": "outside one", "label": "out_of_scope"},
        {"input": "outside two", "label": "out_of_scope"},
    ]
    _write_jsonl(dataset_dir / "test.jsonl", rows)
    baseline = tmp_path / "baseline.jsonl"
    baseline_probabilities = [0.91, 0.81, 0.21, 0.11]
    _write_jsonl(
        baseline,
        [
            {
                **row,
                "in_scope_probability": probability,
                "accepted": probability >= 0.75,
            }
            for row, probability in zip(rows, baseline_probabilities, strict=True)
        ],
    )

    class FakeGate:
        threshold = 0.75

        def __init__(self) -> None:
            self._probabilities = iter([0.90, 0.80, 0.20, 0.10])

        def decide(self, text: str) -> GateDecision:
            probability = next(self._probabilities)
            return GateDecision(probability >= 0.75, probability)

    monkeypatch.setattr(
        "ontchatbot.research.evaluate_gate_ctranslate2.CTranslate2DomainGate.load",
        lambda *args, **kwargs: FakeGate(),
    )
    output = tmp_path / "metrics.json"
    args = argparse.Namespace(
        model_dir=tmp_path / "model",
        dataset_dir=dataset_dir,
        baseline_predictions=baseline,
        device="cpu",
        compute_type="int8",
        output=output,
    )

    report = evaluate(args)

    assert report["test"]["confusion"] == {"tp": 2, "fn": 0, "fp": 0, "tn": 2}
    assert report["parity"]["decision_differences"] == 0
    assert report["parity"]["max_probability_drift"] == 0.01
    assert report["parity"]["confusion_matrix_matches"] is True
    assert report["production_criteria"]["passed"] is True
    assert json.loads(output.read_text(encoding="utf-8")) == report

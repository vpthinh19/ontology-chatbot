"""Integration test: ONNX export and inference for a tiny model."""

import os
import numpy as np
import pytest

@pytest.mark.skipif(
    not os.path.exists(os.path.join("models", "phobert-bce", "config.json")),
    reason="Trained BCE model not found — skipping ONNX export test",
)
class TestOnnxExport:
    def test_export_and_validate(self, tmp_path):
        """Export BCE model to ONNX in a temp dir and validate."""
        from src.scripts.export_onnx import export_model_to_onnx
        from src.core.config import MODEL_BCE_DIR
        from src.utils.inference import load_onnx_session, predict_onnx

        onnx_path = str(tmp_path / "test_model.onnx")
        # Export with smaller max_length for speed
        export_model_to_onnx(MODEL_BCE_DIR, onnx_path, max_length=32)

        assert os.path.exists(onnx_path)
        assert os.path.getsize(onnx_path) > 0

        # Test ONNX utilities
        session = load_onnx_session(onnx_path, providers=["CPUExecutionProvider"])
        assert session is not None

        # Dummy inputs
        input_ids = np.zeros((1, 32), dtype=np.int64)
        attention_mask = np.ones((1, 32), dtype=np.int64)

        preds = predict_onnx(session, input_ids, attention_mask, threshold=0.5)
        
        assert isinstance(preds, np.ndarray)
        assert preds.shape[0] == 1
        assert preds.ndim == 2

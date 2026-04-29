"""PhoBERT fine-tuning pipeline for Vietnamese multi-label classification.

Subpackages:
    core      -- Configuration, metrics, and shared inference utilities
    data      -- Loading, preprocessing, tokenization, Dataset
    losses    -- Custom loss functions (Focal, ASL, ZLPR)
    trainers  -- Custom HuggingFace Trainer overrides
    viz       -- Visualization functions
    scripts   -- Entry-point scripts (train, evaluate, export_onnx)
"""

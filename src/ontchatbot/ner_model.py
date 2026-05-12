"""NerModel: PhoBERT NER inference (onnxruntime) + training-data utilities.

Runtime path uses :mod:`onnxruntime` directly — no optimum wrapper — so the
dependency tree stays minimal and free from optimum's version churn.
Tokenizer remains :class:`transformers.AutoTokenizer` because PhoBERT v2
ships only a slow tokenizer that ORT cannot replicate.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np
import torch
from datasets import Dataset
from transformers import (
    AutoConfig,
    AutoTokenizer,
    PreTrainedTokenizerBase,
)

from .config import MAX_LENGTH, MODEL_DIR, FINETUNED_MODEL_NAME
from .ontology import Ontology

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Entity:
    """One BIO-decoded span."""
    surface: str
    tag: str
    start: int  # inclusive word index
    end: int    # exclusive word index


class NerModel:
    """PhoBERT NER backbone + training adapters; singleton via ``get()``."""

    def __init__(self,
                 model_dir=MODEL_DIR,
                 max_length: int = MAX_LENGTH) -> None:
        self._model_dir = str(model_dir) if Path(model_dir).is_dir() else FINETUNED_MODEL_NAME
        self._max_length = int(max_length)
        self._tok = None
        self._session = None
        self._config = None
        self._encode = None

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "NerModel":
        return cls()

    # Inference

    def extract_entities(self, words: list[str]) -> list[Entity]:
        """Pre-segmented words → BIO-decoded :class:`Entity` spans.

        Cleaning + word-segmentation is the caller's responsibility (the
        :class:`Pipeline._preprocess` stage handles it) so the model layer
        stays pure inference and does not depend on :class:`Preprocessor`.
        """
        if not words:
            return []
        tags = self._predict_tags(words)
        return self.decode_bio(words, tags)

    @staticmethod
    def decode_bio(words: list[str], tags: list[str]) -> list[Entity]:
        """Decode parallel word/tag arrays into BIO entity spans.

        Lenient: an ``I-X`` after ``O`` opens a new entity, recovering spans
        the model emits without a leading ``B-X`` (common when two same-class
        entities are adjacent, e.g. *"hp k65 và k67"*).
        """
        out: list[Entity] = []
        i, n = 0, len(tags)
        while i < n:
            t = tags[i]
            if t == "O":
                i += 1
                continue
            label = t[2:]
            j = i + 1
            while j < n and tags[j] == f"I-{label}":
                j += 1
            surface = " ".join(w.replace("_", " ") for w in words[i:j])
            out.append(Entity(surface=surface, tag=label, start=i, end=j))
            i = j
        return out

    # Schema (BIO labels)

    @staticmethod
    def bio_labels(tags: list[str] | None = None) -> list[str]:
        """Project NER tags into ``[O, B-X, I-X, ...]`` BIO format."""
        if tags is None:
            tags = Ontology.get().tags
        out = ["O"]
        for tag in tags:
            out.extend([f"B-{tag}", f"I-{tag}"])
        return out

    @staticmethod
    def label_mappings() -> tuple[list[str], dict[str, int], dict[int, str]]:
        labels = NerModel.bio_labels()
        l2i = {l: i for i, l in enumerate(labels)}
        return labels, l2i, {i: l for l, i in l2i.items()}

    # Word→sub-word aligner (used by both inference and training)

    @staticmethod
    def make_encoder(
        tokenizer: PreTrainedTokenizerBase,
        max_length: int,
    ) -> Callable[[list[str]], tuple[list[int], list[int | None]]]:
        """Manual word→sub-word aligner; same closure used by training and inference.

        PhoBERT v2 ships only a slow tokenizer (no ``BatchEncoding.word_ids``),
        so the alignment is built manually so a span tagged at training time
        decodes exactly at inference time.
        """
        cls_id = tokenizer.cls_token_id
        sep_id = tokenizer.sep_token_id
        convert = tokenizer.convert_tokens_to_ids
        tokenize = tokenizer.tokenize

        @lru_cache(maxsize=8192)
        def _word_to_ids(word: str) -> tuple[int, ...]:
            return tuple(convert(tokenize(word)))

        def encode(words: list[str]) -> tuple[list[int], list[int | None]]:
            ids: list[int] = [cls_id]
            wids: list[int | None] = [None]
            budget = max_length - 1  # leave room for </s>
            for w_idx, w in enumerate(words):
                sub = _word_to_ids(w)
                if not sub:
                    continue
                if len(ids) + len(sub) > budget:
                    break
                ids.extend(sub)
                wids.extend([w_idx] * len(sub))
            ids.append(sep_id)
            wids.append(None)
            return ids, wids

        return encode

    # Training-time data adapters (formerly dataset.py)

    @staticmethod
    def b_to_i_table(l2i: dict[str, int]) -> dict[int, int]:
        """``B-X id → I-X id`` map for sub-word continuation rewriting."""
        return {l2i[l]: l2i["I-" + l[2:]] for l in l2i if l.startswith("B-")}

    @staticmethod
    def project_labels(word_ids: list[int | None],
                       tag_seq: list[int],
                       b_to_i: dict[int, int]) -> list[int]:
        """Map word-level tags onto a sub-word sequence with B→I downgrade."""
        out: list[int] = []
        prev: int | None = None
        for wid in word_ids:
            if wid is None:
                out.append(-100)
            elif wid != prev:
                out.append(tag_seq[wid])
            else:
                t = tag_seq[wid]
                out.append(b_to_i.get(t, t))
            prev = wid
        return out

    @staticmethod
    def make_tokenize_fn(tokenizer: PreTrainedTokenizerBase):
        """HuggingFace ``Dataset.map`` callable: word-level → sub-word features."""
        _, l2i, _ = NerModel.label_mappings()
        b_to_i = NerModel.b_to_i_table(l2i)
        encode = NerModel.make_encoder(tokenizer, MAX_LENGTH)

        def _fn(batch):
            ids_b, masks_b, labels_b = [], [], []
            for words, tag_seq in zip(batch["tokens"], batch["tags"]):
                ids, wids = encode(list(words))
                labels_b.append(NerModel.project_labels(wids, list(tag_seq), b_to_i))
                ids_b.append(ids)
                masks_b.append([1] * len(ids))
            return {"input_ids": ids_b, "attention_mask": masks_b, "labels": labels_b}
        return _fn

    @staticmethod
    def load_split(path: Path, l2i: dict[str, int]) -> Dataset:
        """JSONL → HuggingFace ``Dataset`` with ``tokens`` and ``tags`` columns."""
        rows: list[dict] = []
        with Path(path).open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return Dataset.from_dict({
            "tokens": [r["tokens"] for r in rows],
            "tags": [[l2i[t] for t in r["ner_tags"]] for r in rows],
        })

    # Internals — inference path

    def _ensure_loaded(self) -> None:
        if self._session is not None:
            return
        # Lazy imports — onnxruntime + hf_hub_download only touched the first
        # time a real inference is requested. Unit tests that exercise
        # ``decode_bio`` / encoder static methods never trigger this path.
        import onnxruntime as ort

        log.info("[NerModel] loading ONNX runtime from %s", self._model_dir)
        # Slow tokenizer from transformers (PhoBERT v2 has no fast variant);
        # AutoTokenizer transparently pulls from HF Hub when the path is a
        # repo id instead of a local directory.
        self._tok = AutoTokenizer.from_pretrained(self._model_dir)
        # Config is loaded separately because the InferenceSession doesn't
        # carry one — we need ``id2label`` to map argmax ids back to BIO
        # strings. ``AutoConfig.from_pretrained`` only fetches config.json
        # (a few KB), no model weights.
        self._config = AutoConfig.from_pretrained(self._model_dir)

        onnx_path = self._resolve_onnx_path()
        providers = (["CUDAExecutionProvider", "CPUExecutionProvider"]
                     if torch.cuda.is_available()
                     else ["CPUExecutionProvider"])
        self._session = ort.InferenceSession(str(onnx_path), providers=providers)
        self._encode = NerModel.make_encoder(self._tok, self._max_length)
        log.info("[NerModel] providers=%s n_labels=%d",
                 self._session.get_providers(), len(self._config.id2label))

    def _resolve_onnx_path(self) -> Path:
        """Locate ``model.onnx`` — local dir if present, else fetch from HF Hub.

        When ``self._model_dir`` is a local directory containing the file,
        return that path. When it is an HF Hub repo id (fallback set in
        ``__init__``), use :func:`huggingface_hub.hf_hub_download` which
        caches the download under ``~/.cache/huggingface/`` so subsequent
        starts are instant.
        """
        if Path(self._model_dir).is_dir():
            local = Path(self._model_dir) / "model.onnx"
            if not local.exists():
                raise FileNotFoundError(
                    f"{local} not found — run `uv run train` to export ONNX, "
                    f"or delete the directory to fall back to HF Hub."
                )
            return local
        from huggingface_hub import hf_hub_download
        log.info("[NerModel] pulling model.onnx from HF repo %s",
                 self._model_dir)
        return Path(hf_hub_download(
            repo_id=self._model_dir, filename="model.onnx",
        ))

    def _predict_tags(self, words: list[str]) -> list[str]:
        """Run onnxruntime inference on ``words`` and return word-level BIO tags."""
        self._ensure_loaded()
        input_ids, word_ids = self._encode(words)
        ids = np.asarray([input_ids], dtype=np.int64)
        mask = np.ones_like(ids)
        # InferenceSession.run returns a list (one ndarray per output node).
        # Our exported graph has a single ``logits`` output → outputs[0].
        # Drop batch dim ([0]) so logits shape is (seq, n_labels).
        logits = self._session.run(
            None,
            {"input_ids": ids, "attention_mask": mask},
        )[0][0]
        pred_ids = logits.argmax(axis=-1).tolist()
        id2lab = self._config.id2label
        tags = ["O"] * len(words)
        seen: set[int] = set()
        for tid, wid in zip(pred_ids, word_ids):
            if wid is None or wid in seen:
                continue
            seen.add(wid)
            # transformers normalizes id2label keys to int when loading
            # config.json, so direct int lookup is safe.
            tags[wid] = id2lab[int(tid)]
        log.info("[NerModel] tags=%s", list(zip(words, tags)))
        return tags

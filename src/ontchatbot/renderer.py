"""JSON dict → Vietnamese chat string renderer.

Consumes the dict shape emitted by :class:`Ontology.describe` /
:class:`Ontology.list_class`. Does not import owlready2 — tests use mocked
dicts and complete in milliseconds.

Contract: 4 fixed keys (``type``, ``iri``, ``class``, ``label``); every
other key is a property ``rdfs:label`` and renders as a section header.
URL-shaped string values become markdown links.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from .config import RENDER_CLASS_EMOJI
from .preprocessor import Preprocessor

log = logging.getLogger(__name__)

# Mirror the constant from :mod:`store` rather than importing it, so the
# renderer remains structurally independent of the ontology layer.
_FIXED_KEYS: frozenset[str] = frozenset({"type", "iri", "class", "label"})

# User-facing copy. Lives here (not in the Ontology) because it is purely a
# presentation concern.
GREETING_REPLY = (
    "Xin chào! Mình có thể tra cứu giúp bạn về quy trình học vụ, phòng ban "
    "hành chính, định mức học phí, biểu mẫu hoặc phương thức thanh toán. "
    "Bạn cần hỏi gì ạ?"
)
OUT_OF_DOMAIN_REPLY = (
    "Câu hỏi của bạn nằm ngoài phạm vi tri thức hiện có. Hãy thử hỏi về quy "
    "trình học vụ, phòng ban hành chính, học phí, biểu mẫu hoặc phương thức "
    "thanh toán."
)


def _md_link(label: str, url: str | None) -> str:
    return f"[{label}]({url})" if url else label


def _format_scalar(v) -> str:
    if isinstance(v, bool):
        return "Có" if v else "Không"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


class Renderer:
    """Vietnamese chat renderer; singleton via ``get()``."""

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "Renderer":
        return cls()

    # Public API

    def render_blocks(self, descriptions: list[dict]) -> str:
        """Concatenate blocks; dedup by (class, iri/listing)."""
        seen: set[tuple[str, str]] = set()
        blocks: list[str] = []
        for d in descriptions:
            if not d:
                continue
            kind = d.get("type")
            key = (d.get("class", ""),
                   "__listing__" if kind == "listing" else d.get("iri", ""))
            if key in seen:
                continue
            seen.add(key)
            block = self.render(d)
            if block:
                blocks.append(block)
        return "\n\n".join(blocks)

    def render(self, description: dict) -> str:
        """Dispatch by the ``type`` key."""
        kind = description.get("type")
        if kind == "listing":
            return self._render_listing(description)
        if kind == "individual":
            return self._render_individual(description)
        log.warning("[Renderer.render] unknown kind=%r", kind)
        return ""

    def compose(self, blocks: str, *, greeting: bool) -> str:
        """Final reply: blocks > greeting reply > OOD reply (minimal-greeting policy)."""
        if blocks:
            return blocks
        return GREETING_REPLY if greeting else OUT_OF_DOMAIN_REPLY

    # Sub-templates

    def _render_individual(self, d: dict) -> str:
        emoji = RENDER_CLASS_EMOJI.get(d.get("class", ""), "•")
        lines: list[str] = [f"{emoji} {d.get('label', '')}"]

        # Iterate all non-fixed keys in dict insertion order — that order
        # was already imposed by Ontology.describe(), so this layer simply
        # consumes it.
        for header, value in d.items():
            if header in _FIXED_KEYS:
                continue
            section = self._format_section(header, value)
            if section:
                lines.append(section)
        return "\n".join(lines)

    def _render_listing(self, d: dict) -> str:
        emoji = RENDER_CLASS_EMOJI.get(d.get("class", ""), "•")
        lines = [f"{emoji} {d.get('label', '')}"]
        for it in d.get("items", []):
            lines.append(f"• {it.get('label', '')}")
        return "\n".join(lines)

    # Section formatting

    def _format_section(self, header: str, value) -> str:
        """``• Header: …`` (scalar) or ``• Header:\\n  – …`` (list)."""
        # Paragraph — Ontology marks free-flow text with a leading newline
        # (see :meth:`Ontology._render_property_value`). This works for both
        # multi-line and single-line paragraph property values, and keeps
        # the renderer free of per-property paragraph configuration.
        if isinstance(value, str) and value.startswith("\n"):
            return value.lstrip("\n")

        if isinstance(value, list) and value and isinstance(value[0], dict):
            return self._format_object_section(header, value)

        if isinstance(value, list):
            rendered = [_format_scalar(v) for v in value]
            sub = "\n".join(f"  – {r}" for r in rendered)
            return f"• {header}:\n{sub}"

        text = _format_scalar(value)
        if Preprocessor.is_url(text):
            text = _md_link(text, text)
        return f"• {header}: {text}"

    def _format_object_section(self, header: str, targets: list[dict]) -> str:
        rendered = [self._format_object_target(t) for t in targets]
        if len(rendered) == 1:
            return f"• {header}: {rendered[0]}"
        sub = "\n".join(f"  – {r}" for r in rendered)
        return f"• {header}:\n{sub}"

    @staticmethod
    def _format_object_target(target: dict) -> str:
        """``[label](url)`` if any URL-shaped value present, else just ``label``."""
        label = target.get("label", "")
        for k, v in target.items():
            if k in _FIXED_KEYS:
                continue
            if Preprocessor.is_url(v):
                return _md_link(label, v)
        return label

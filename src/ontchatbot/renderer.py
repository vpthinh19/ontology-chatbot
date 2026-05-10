"""JSON dict → Vietnamese chat string renderer.

Consumes the dict shape emitted by :class:`Ontology.describe` /
:class:`Ontology.list_class`. Does not import owlready2 — tests use mocked
dicts and complete in milliseconds.

Contract: 4 fixed keys (``type``, ``iri``, ``class``, ``label``); every
other key is a property ``rdfs:label`` and renders as a section header.
URL-shaped string values become markdown links.

Hierarchy markers (generic, schema-agnostic):
    •   entity-level property section
    -   list item (multi-value or multi-target)
    ◦   nested data section under an object-property target

Each marker maps to one semantic role; depth manifests through indentation.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from .config import RENDER_CLASS_EMOJI
from .preprocessor import Preprocessor

log = logging.getLogger(__name__)

# Mirror :data:`store.FIXED_KEYS` here so the renderer stays structurally
# independent of the ontology layer (tests can use synthetic dicts).
_FIXED_KEYS: frozenset[str] = frozenset({"type", "iri", "class", "label"})

# Visual hierarchy markers. ``ENTITY`` is the top-level entity property
# bullet; ``ITEM`` opens a list item; ``NESTED`` is the bullet for sub-
# sections under an object-property target.
_M_ENTITY = "•"
_M_ITEM = "-"
_M_NESTED = "◦"
_INDENT = "  "  # 2 spaces — used for every level of nesting

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
    """Markdown link with parens encoded so frontend regex doesn't truncate."""
    if not url:
        return label
    safe = url.replace("(", "%28").replace(")", "%29")
    return f"[{label}]({safe})"


def _format_scalar(v) -> str:
    if isinstance(v, bool):
        return "Có" if v else "Không"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def _indent(text: str, prefix: str = _INDENT) -> str:
    """Indent every line of ``text`` by ``prefix``."""
    return "\n".join(prefix + line for line in text.split("\n"))


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
        """Top-level entity render. Title + each block separated by a blank
        line so paragraphs and bullet sections breathe independently."""
        emoji = RENDER_CLASS_EMOJI.get(d.get("class", ""))
        title_label = d.get("label", "")
        title = f"{emoji} {title_label}" if emoji else title_label
        blocks: list[str] = [title]
        for header, value in d.items():
            if header in _FIXED_KEYS:
                continue
            section = self._format_section(header, value, marker=_M_ENTITY)
            if section:
                blocks.append(section)
        return "\n\n".join(blocks)

    def _render_listing(self, d: dict) -> str:
        emoji = RENDER_CLASS_EMOJI.get(d.get("class", ""))
        title_label = d.get("label", "")
        title = f"{emoji} {title_label}" if emoji else title_label
        lines = [title]
        for it in d.get("items", []):
            lines.append(f"{_M_ENTITY} {it.get('label', '')}")
        return "\n".join(lines)

    # Section formatting — generic across hierarchy levels

    def _format_section(self, header: str, value, *, marker: str) -> str:
        """Render one ``{marker} Header: …`` section.

        ``marker`` is the visual bullet for this section in the hierarchy:
        :data:`_M_ENTITY` for top-level entity sections,
        :data:`_M_NESTED` for sections living under an object-property
        target. List items always use :data:`_M_ITEM` regardless of level.
        """
        # Paragraph — leading newline marker from Ontology, no bullet.
        if isinstance(value, str) and value.startswith("\n"):
            return value.lstrip("\n")

        if isinstance(value, list) and value and isinstance(value[0], dict):
            return self._format_object_section(header, value, marker=marker)

        if isinstance(value, list):
            rendered = [_format_scalar(v) for v in value]
            sub = "\n".join(f"{_INDENT}{_M_ITEM} {r}" for r in rendered)
            return f"{marker} {header}:\n{sub}"

        text = _format_scalar(value)
        if Preprocessor.is_url(text):
            text = _md_link(text, text)
        return f"{marker} {header}: {text}"

    def _format_object_section(self, header: str, targets: list[dict], *,
                               marker: str) -> str:
        """Render an object-property section.

        Single target → ``{marker} Header: label`` inline; if the target
        has its own data, sub-sections follow on indented lines with
        :data:`_M_NESTED` markers.

        Multiple targets → ``{marker} Header:`` then each target as a
        ``  – label`` item, with target data indented one level further.
        """
        if len(targets) == 1:
            rendered = self._render_target(targets[0])
            if "\n" not in rendered:
                return f"{marker} {header}: {rendered}"
            head, body = rendered.split("\n", 1)
            return f"{marker} {header}: {head}\n{body}"

        items: list[str] = []
        for t in targets:
            rendered = self._render_target(t)
            if "\n" in rendered:
                head, body = rendered.split("\n", 1)
                items.append(f"{_INDENT}{_M_ITEM} {head}\n{_indent(body)}")
            else:
                items.append(f"{_INDENT}{_M_ITEM} {rendered}")
        # Rich items (with their own ``◦`` sub-sections) get a blank line
        # between them so the eye can group each item's data; compact
        # one-line items stay tight.
        sep = "\n\n" if any("\n" in it for it in items) else "\n"
        return f"{marker} {header}:\n" + sep.join(items)

    def _render_target(self, target: dict) -> str:
        """Render one object-property target.

        * **Compact** (target carries only identity, possibly a URL value)
          → returns ``label`` or ``[label](url)``.
        * **Rich** (target has substantive data sections) → returns a
          multi-line block: head on the first line, then indented sub-
          sections with :data:`_M_NESTED` markers. Callers are responsible
          for the surrounding context (inline-after-header for single,
          ``-`` list item for multi).
        """
        label = target.get("label", "")
        substantive = [(k, v) for k, v in target.items() if k not in _FIXED_KEYS]
        link_url = next(
            (v for k, v in substantive if Preprocessor.is_url(v)), None,
        )
        head = _md_link(label, link_url) if link_url else label

        non_url = [(k, v) for k, v in substantive
                   if not Preprocessor.is_url(v)]
        if not non_url:
            return head

        lines = [head]
        for k, v in non_url:
            section = self._format_section(k, v, marker=_M_NESTED)
            lines.append(_indent(section))
        return "\n".join(lines)

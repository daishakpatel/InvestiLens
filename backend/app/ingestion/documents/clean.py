"""HTML cleaning and hidden-element removal (DP-004).

Strips scripts/styles and invisible content (`display:none`, `visibility:hidden`, zero-size
text, `hidden`/`aria-hidden`). This is ALSO the first line of defense against prompt injection
hidden in filing markup — later RAG stages (Phase 2c) can rely on hidden text already being gone.
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser, Node

_HIDDEN_STYLE = re.compile(
    r"(display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(px|pt|em|%)?\b)", re.I
)
_DROP_TAGS = ("script", "style", "noscript", "head", "template")


def _is_hidden(node: Node) -> bool:
    attrs = node.attributes
    if "hidden" in attrs:
        return True
    if (attrs.get("aria-hidden") or "").lower() == "true":
        return True
    style = attrs.get("style") or ""
    return bool(_HIDDEN_STYLE.search(style))


def clean_tree(html: str) -> HTMLParser:
    """Parse HTML and remove scripts/styles and hidden elements in place."""
    tree = HTMLParser(html)
    for selector in _DROP_TAGS:
        for node in tree.css(selector):
            node.decompose()
    # Remove hidden elements (DP-004). Walk a snapshot since we mutate the tree.
    root = tree.body or tree.root
    if root is not None:
        for node in list(root.traverse(include_text=False)):
            if node.parent is not None and _is_hidden(node):
                node.decompose()
    return tree

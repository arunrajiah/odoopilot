#!/usr/bin/env python3
"""Lint odoopilot/static/description/index.html for App Store renderability.

The Odoo App Store sanitises this HTML before serving it. Empirically:

1. Inline ``style=""`` is preserved EXCEPT ``background`` and
   ``background-color`` declarations, which are stripped silently.
2. ``<a href="...">CustomText</a>`` is rewritten to
   ``<span href="...">CustomText</span>`` -- which is non-clickable HTML.
   Plain URL text in the body is auto-linked by a separate pass that
   emits a fresh ``<a rel="nofollow">`` that survives the sanitiser.

This script enforces three rules so a future contributor doesn't
reintroduce the failures we already fixed:

* No ``background`` / ``background-color`` in inline styles.
  (If present, the App Store renders white text on white.)
* No white text colours, UNLESS the element or one of its ancestors
  sets ``background-image``.
  (White text becomes invisible once the dark background it was paired
  with is stripped -- but ``background-image: linear-gradient(C, C)``
  is NOT stripped, so a bubble painted that way keeps its colour and
  white text on top of it stays legible. Verified against the live
  listing: ``background`` and ``background-color`` are absent from the
  served HTML while all 54 ``background-image`` declarations survive
  with their computed colour intact.)
* No raw ``<a `` tags in the body.
  (These get rewritten to non-clickable ``<span>``. Use plain URL text
  instead and let the auto-linker make it clickable.)

HTML comments are stripped before scanning so the documentation header
in index.html (which deliberately mentions these patterns to explain
the rules) does not trigger the linter.

Usage::

    python3 scripts/check_listing_rendering.py

Exit code 0 if clean, 1 if violations found.
"""

from __future__ import annotations

import pathlib
import re
import sys
from html.parser import HTMLParser

LISTING = pathlib.Path("odoopilot/static/description/index.html")

# Strip HTML comments (which legitimately mention the forbidden patterns
# in our documentation header) before scanning the body.
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Match ``background:`` or ``background-color:`` as a CSS property.
# Using a word boundary on the left and ``:`` on the right avoids false
# positives like ``border:`` (no -color suffix risk; ``border-color``
# is fine to keep).
_BACKGROUND_RE = re.compile(r"\bbackground(-color)?\s*:", re.IGNORECASE)

# Match white text colours in any common form. Comparing on the value
# side of ``color:`` only -- a literal hex like ``#fff`` outside a
# ``color`` declaration is fine.
_WHITE_TEXT_RE = re.compile(
    r"\bcolor\s*:\s*(?:#fff(?:fff)?\b|white\b)",
    re.IGNORECASE,
)

# Match any opening ``<a `` tag (with at least one attribute) or bare
# ``<a>``. Closing ``</a>`` is fine -- it doesn't appear without an
# opening tag and harmless if the sanitiser saw none.
_ANCHOR_RE = re.compile(r"<a(\s|>)", re.IGNORECASE)


def _line_of(text: str, offset: int) -> int:
    """Return the 1-based line number for a byte offset in *text*."""
    return text.count("\n", 0, offset) + 1


_VOID_TAGS = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)


class _WhiteTextScanner(HTMLParser):
    """Find white text that has no surviving background behind it.

    The background may be set on the element itself or on any ancestor,
    so this walks the tree rather than looking at one ``style`` attribute
    in isolation. Only ``background-image`` counts as surviving: the App
    Store sanitiser strips ``background`` and ``background-color`` but
    leaves ``background-image`` alone, which makes
    ``background-image: linear-gradient(C, C)`` the supported way to keep
    a solid colour behind white text.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        # Stack of booleans: is this element (or an ancestor) painted?
        self._painted: list[bool] = []
        self.violations: list[int] = []

    def _enter(self, tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        style = ""
        for name, value in attrs:
            if name.lower() == "style" and value:
                style = value.replace(" ", "").lower()
                break
        inherited = self._painted[-1] if self._painted else False
        painted = inherited or "background-image:" in style
        if _WHITE_TEXT_RE.search(style) and not painted:
            self.violations.append(self.getpos()[0])
        return painted

    def handle_starttag(self, tag, attrs):
        painted = self._enter(tag, attrs)
        if tag.lower() not in _VOID_TAGS:
            self._painted.append(painted)

    def handle_startendtag(self, tag, attrs):
        self._enter(tag, attrs)

    def handle_endtag(self, tag):
        if tag.lower() not in _VOID_TAGS and self._painted:
            self._painted.pop()


def main() -> int:
    if not LISTING.exists():
        print(f"ERROR: {LISTING} not found")
        return 2

    raw = LISTING.read_text(encoding="utf-8")
    body = _COMMENT_RE.sub("", raw)
    # Same content, but each comment is replaced by its own newlines so
    # the HTML parser reports line numbers that match the real file.
    body_lined = _COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), raw)

    violations: list[tuple[int, str, str]] = []

    for m in _BACKGROUND_RE.finditer(body):
        # Recover the original line number by counting newlines in the
        # *commented-stripped* body up to this offset; remap to the
        # original by finding the same snippet in raw.
        snippet = body[max(0, m.start() - 30) : m.end() + 40]
        line = _line_of(raw, raw.find(snippet)) if snippet in raw else 0
        violations.append(
            (
                line,
                "background",
                "App Store strips ``background`` declarations -- text on a "
                "painted background becomes invisible",
            )
        )

    # White text is only a problem when nothing survives behind it, so
    # this walks the element tree and honours a background-image set on
    # any ancestor. Line numbers come from the parser, which is why they
    # are exact here rather than recovered by snippet lookup.
    scanner = _WhiteTextScanner()
    scanner.feed(body_lined)
    for line in scanner.violations:
        violations.append(
            (
                line,
                "white text",
                "App Store strips backgrounds; white text is invisible unless "
                "the element or an ancestor sets background-image",
            )
        )

    for m in _ANCHOR_RE.finditer(body):
        snippet = body[max(0, m.start() - 30) : m.end() + 60]
        line = _line_of(raw, raw.find(snippet)) if snippet in raw else 0
        violations.append(
            (
                line,
                "anchor tag",
                "App Store rewrites <a> to <span href> (non-clickable). "
                "Use plain URL text and let the auto-linker handle it",
            )
        )

    if not violations:
        print(f"OK: {LISTING} renders cleanly under the App Store sanitiser.")
        return 0

    print(f"FAIL: {LISTING} would render badly on the Odoo App Store.")
    print()
    for line, kind, why in sorted(violations, key=lambda v: v[0]):
        print(f"  line {line}: {kind} -- {why}")
    print()
    print(f"{len(violations)} violation(s). See header comment in")
    print(f"{LISTING} for the rules and rationale.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

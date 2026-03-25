"""Markdown sanitization using bleach.

Only tags that can appear in rendered Markdown (headings, lists,
emphasis, code, tables, etc.) are allowed.  Dangerous attributes like
event handlers and javascript: URLs are stripped.

Usage
-----
    from services.markdown import sanitize_md

    safe_html = sanitize_md(user_supplied_markdown_string)
"""

import bleach
from bleach.css_sanitizer import CSSSanitizer

# Tags allowed in Markdown-rendered output
_ALLOWED_TAGS = [
    # Structure
    "p", "br", "hr",
    # Headings
    "h1", "h2", "h3", "h4", "h5", "h6",
    # Lists
    "ul", "ol", "li",
    # Inline formatting
    "strong", "b", "em", "i", "u", "s", "del", "ins", "mark",
    # Code
    "code", "pre", "kbd", "samp",
    # Blockquote
    "blockquote",
    # Tables
    "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    # Links (href checked via allowed_attrs)
    "a",
    # Images embedded via data-uri or https URLs
    "img",
    # Details/summary
    "details", "summary",
    # Math (KaTeX renders to these)
    "span", "div",
    # Superscript / subscript
    "sup", "sub",
]

_ALLOWED_ATTRS = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "th": ["align", "scope"],
    "td": ["align"],
    "code": ["class"],       # syntax highlighting class
    "span": ["class", "style"],  # KaTeX output
    "div": ["class", "style"],   # KaTeX block
    "*": ["id"],
}

# KaTeX emits inline style attributes. Restrict style properties to a curated
# subset needed for math layout so arbitrary CSS cannot be injected.
_ALLOWED_CSS_PROPERTIES = [
    "color",
    "background-color",
    "font-size",
    "font-style",
    "font-weight",
    "font-family",
    "line-height",
    "letter-spacing",
    "text-align",
    "text-indent",
    "vertical-align",
    "white-space",
    "display",
    "position",
    "top",
    "bottom",
    "left",
    "right",
    "height",
    "width",
    "min-width",
    "max-width",
    "margin",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "padding",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
]

_CSS_SANITIZER = CSSSanitizer(allowed_css_properties=_ALLOWED_CSS_PROPERTIES)


def sanitize_md(text: str | None) -> str | None:
    """Strip dangerous HTML from a Markdown string.

    The input is treated as already-plain Markdown (not rendered HTML).
    We run bleach over it so that any inline HTML the user embedded cannot
    introduce XSS payloads.  KaTeX-style spans/divs with class/style are
    preserved.
    """
    if text is None:
        return None
    return bleach.clean(
        text,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        css_sanitizer=_CSS_SANITIZER,
        strip=True,
    )

"""Read the results of a jamovi ``.omv`` document.

An ``.omv`` is a ZIP archive whose ``index.html`` member holds every analysis the
user ran, already rendered as APA-style tables.  Reading the rendered document
means the LMS can grade analysis output without touching the jamovi client.
"""
from __future__ import annotations

import io
import posixpath
import re
import zipfile
from html.parser import HTMLParser
from typing import Any, Optional, Union

PathLike = Union[str, "posixpath.PurePath", bytes, io.IOBase]

_EMPTY_MODULES = {"empty", "Rjp"}


class _CellParser(HTMLParser):
    """Collect the text of each cell, keyed by its ``aria-labelledby`` id."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[str] = []      # <h1> text, in document order
        self.paragraphs: list[str] = []    # <p> text, in document order
        self.tables: list[dict] = []
        self.images: list[str] = []
        self._table: Optional[dict] = None
        self._row: Optional[list] = None
        self._cell: Optional[list] = None
        self._stack: list[str] = []
        self._heading: Optional[list] = None
        self._paragraph: Optional[list] = None
        self._caption: Optional[list] = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "img":
            src = a.get("src", "")
            if src:
                self.images.append(src)
        elif tag == "h1":
            self._heading = []
        elif tag == "p":
            self._paragraph = []
        elif tag == "table":
            self._table = {"title": "", "caption": "", "columns": [], "rows": []}
        elif tag == "caption" and self._table is not None:
            self._caption = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            if tag == "th":
                self._row.append({"text": None, "labelled_by": a.get("aria-labelledby"),
                                  "scope": a.get("scope")})
            else:
                self._row.append({"text": None, "labelled_by": None, "scope": a.get("scope")})
        self._stack.append(tag)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            text = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            if self._row:
                self._row[-1]["text"] = text
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self._table["rows"].append(self._row)  # type: ignore[union-attr]
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._caption is not None:
                self._table["caption"] = re.sub(r"\s+", " ", "".join(self._caption)).strip()
                self._caption = None
            self._finish_table(self._table)
            self._table = None
        elif tag == "h1" and self._heading is not None:
            self.headings.append("".join(self._heading).strip())
            self._heading = None
        elif tag == "p" and self._paragraph is not None:
            text = "".join(self._paragraph).strip()
            if text:
                self.paragraphs.append(text)
            self._paragraph = None
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        elif self._caption is not None:
            self._caption.append(data)
        elif self._heading is not None:
            self._heading.append(data)
        elif self._paragraph is not None:
            self._paragraph.append(data)

    def _finish_table(self, raw: dict) -> None:
        rows = raw["rows"]
        if not rows:
            return
        label_ids: dict[str, str] = {}
        # the live results view titles a table with <caption>; an exported
        # index.html uses a full-width <th scope="colgroup"> instead
        title = raw.get("caption", "")
        header_rows: list[list] = []
        body_rows: list[list] = []
        for row in rows:
            is_header = any(c["scope"] in ("col", "colgroup") for c in row)
            if is_header:
                header_rows.append(row)
                for cell in row:
                    if cell["labelled_by"]:
                        label_ids[cell["labelled_by"]] = cell["text"] or ""
            else:
                body_rows.append(row)

        for row in header_rows:
            if title:
                break
            if len(row) == 1 and row[0]["scope"] == "colgroup" and row[0]["labelled_by"]:
                title = label_ids.get(row[0]["labelled_by"], "")
            elif len(row) == 1 and row[0]["scope"] == "colgroup":
                title = row[0]["text"] or ""

        columns: list[str] = []
        if header_rows:
            last = header_rows[-1]
            if len(last) > 1 or not last[0]["labelled_by"]:
                columns = [c["text"] or "" for c in last]
        if not columns:
            width = max((len(r) for r in body_rows), default=0)
            columns = [""] * width

        self.tables.append({
            "analysis": self.headings[-1] if self.headings else "",
            "title": title,
            "columns": columns,
            "rows": [[c["text"] or "" for c in row] for row in body_rows],
        })


def parse_omv(source: PathLike, html: Optional[str] = None) -> dict[str, Any]:
    """Parse an ``.omv`` (path or bytes) into analyses, tables and notes.

    ``html`` overrides the archive's rendered report.  A ``.omv`` saved by the
    jamovi *server* keeps its analysis results as RDS blobs and carries no
    ``index.html`` at all — only the desktop app embeds one — so the browser has
    to hand over the report it rendered for the tables to be readable.
    """
    if isinstance(source, (bytes, bytearray)):
        archive = zipfile.ZipFile(io.BytesIO(bytes(source)))
    elif hasattr(source, "read"):
        archive = zipfile.ZipFile(io.BytesIO(source.read()))
    else:
        archive = zipfile.ZipFile(str(source))

    with archive:
        if html is None:
            html = (
                archive.read("index.html").decode("utf-8", "replace")
                if "index.html" in archive.namelist() else ""
            )
        entries = [n for n in archive.namelist() if n.endswith("/analysis")]
        resources = [n for n in archive.namelist() if "/resources/" in n]

    modules: list[str] = []
    for name in sorted(entries, key=lambda n: _entry_index(n)):
        module = name.split("/", 1)[0].split(" ", 1)[-1]
        if module not in _EMPTY_MODULES:
            modules.append(module)

    parser = _CellParser()
    parser.feed(html)

    analyses: list[dict] = []
    for table in parser.tables:
        name = table["analysis"]
        if analyses and analyses[-1]["name"] == name:
            analyses[-1]["tables"].append(table)
        else:
            analyses.append({"name": name, "tables": [table]})

    # jamovi names an analysis in the UI ("Linear Regression") but keys it in the
    # archive ("linReg").  The two lists line up when every analysis rendered at
    # least one table, which is the only case a teacher can grade anyway.
    names = list(dict.fromkeys(t["analysis"] for t in parser.tables if t["analysis"]))
    module_by_name = dict(zip(names, modules)) if len(names) == len(modules) else {}
    for entry in analyses:
        entry["module"] = module_by_name.get(entry["name"])

    return {
        "modules": modules,
        "analyses": analyses,
        "tables": parser.tables,
        "notes": parser.paragraphs,
        "images": parser.images,
        "resources": resources,
        "titles": parser.headings,
        "module_by_analysis": module_by_name,
    }


def _entry_index(name: str) -> int:
    head = name.split(" ", 1)[0]
    try:
        return int(head)
    except ValueError:
        return 999


def _score_name(haystack: str, needle: str, aliases: dict[str, str]) -> int:
    """How strongly a rendered name matches what the teacher typed."""
    h, n = normalise(haystack), normalise(needle)
    if not n:
        return 0
    if h == n or aliases.get(h) == n:
        return 3
    if n in h:
        return 1
    return -1


def find_stat(
    doc: dict[str, Any],
    analysis: Optional[str] = None,
    table: Optional[str] = None,
    column: Optional[str] = None,
    row: Optional[str] = None,
) -> Optional[float]:
    """Pull one numeric value out of a parsed document.

    ``analysis``/``table``/``column``/``row`` are matched case-insensitively as
    substrings so a teacher can write ``table="Model Fit"`` without knowing the
    exact caption.  An analysis may also be given as its jamovi module key
    (``linReg``).  ``row=None`` means "the first data row", ``row="*"`` the last.

    Candidates are taken best-match first: "One-Way ANOVA" is a substring of both
    "One-Way ANOVA" and "One-Way ANOVA (Non-parametric)", and grading the wrong
    one silently gives the student a wrong mark.
    """
    aliases = {normalise(k): normalise(v) for k, v in (doc.get("module_by_analysis") or {}).items()}
    scored = []
    for order, t in enumerate(doc["tables"]):
        score = 0
        if analysis:
            score += _score_name(t["analysis"], analysis, aliases)
            if score < 0:
                continue
        if table:
            title = _score_name(t["title"], table, {})
            if title < 0:
                continue
            score += title
        scored.append((score, order, t))
    scored.sort(key=lambda item: (-item[0], item[1]))

    for _, _, t in scored:
        if column:
            idx = _column_index(t["columns"], column)
            if idx is None:
                continue
        else:
            idx = 0
        rows = t["rows"]
        if not rows:
            continue
        if row in (None, ""):
            target = rows[0]
        elif row == "*":
            target = rows[-1]
        else:
            target = next((r for r in rows if _contains(" ".join(r), row)), None)
            if target is None:
                continue
        if idx < len(target):
            value = parse_number(target[idx])
            if value is not None:
                return value
    return None


def find_row(doc: dict[str, Any], table: str, row: str) -> Optional[dict[str, str]]:
    """Return one data row of a table as ``{column: cell}``, or None."""
    for t in doc["tables"]:
        if not _contains(t["title"], table):
            continue
        for cells in t["rows"]:
            if _contains(" ".join(cells), row):
                cols = t["columns"]
                return {(cols[i] if i < len(cols) else str(i)): c for i, c in enumerate(cells)}
    return None


def _contains(haystack: str, needle: str) -> bool:
    return normalise(needle) in normalise(haystack)


def grading_schema(doc: dict[str, Any]) -> list[dict]:
    """The analyses, tables, columns and row labels a teacher can build checks on.

    Teachers grade from what jamovi actually rendered, not from names they have
    to remember, so the UI offers this instead of free-text fields.
    """
    out: list[dict] = []
    for a in doc["analyses"]:
        tables: list[dict] = []
        for t in a["tables"]:
            labels: list[str] = []
            for cells in t["rows"]:
                label = next((c for c in cells if c), "")
                # jamovi prints the table caption as a trailing "Note." row
                if not label or label.startswith("Note."):
                    continue
                if label not in labels:
                    labels.append(label)
            tables.append({
                "title": t["title"],
                "columns": [c for c in t["columns"] if c],
                "row_labels": labels[:20],
            })
        out.append({"name": a["name"], "module": a.get("module"), "tables": tables})
    return out


# jamovi writes statistics with typographic marks (R², \u03b1, \u2212) that a teacher
# would never type back, so they are folded before matching.
_FOLD = str.maketrans({"\u00b2": "2", "\u00b3": "3", "\u03b1": "a", "\u03b2": "b", "\u03c1": "r",
                       "\u03b7": "n", "\u03c7": "chi", "\u03bc": "mu", "\u03c3": "s",
                       "\u2212": "-", "\u2264": "<=", "\u2265": ">=", "\u00d7": "x"})


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.translate(_FOLD).lower())


def _column_index(columns: list[str], needle: str) -> Optional[int]:
    wanted = normalise(needle)
    for i, col in enumerate(columns):
        if normalise(col) == wanted:
            return i
    for i, col in enumerate(columns):
        if wanted in normalise(col):
            return i
    return None


_NUM = re.compile(r"(-?)(\d*\.?\d+)")


def parse_number(text: Any) -> Optional[float]:
    """Read a jamovi cell as a float; ``.023``, ``1,234.5``, ``<.001``, ``\u2212.02``."""
    if isinstance(text, bool):
        return None
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text or "").translate(str.maketrans({"\u2212": "-", "\u2013": "-"})).replace(",", "")
    match = _NUM.search(s)
    if not match:
        return None
    value = float(match.group(2))
    if match.group(1) == "-":
        value = -value
    # jamovi reports "p < .001"; half the bound keeps thresholds like "< 0.05" satisfiable
    if value and "<" in s[: match.start(2)]:
        return value / 2
    return value

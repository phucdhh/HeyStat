"""Read the results of a jamovi ``.omv`` document.

An ``.omv`` is a ZIP archive.  Every ``NNN <name>/analysis`` member holds one
``AnalysisResponse`` protobuf, and inside it the tables, cells and notes jamovi
just computed — so the LMS can read a submission's numbers out of the file the
student saved, without a browser and without R.  The rendered ``index.html`` (if
the client handed one over) is only used as a fallback for documents whose
analysis results were never stored.
"""
from __future__ import annotations

import html as _html
import io
import posixpath
import re
import zipfile
from html.parser import HTMLParser
from typing import Any, Optional, Union

from services import omv_proto

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


def _read_archive(source: PathLike) -> dict[str, Any]:
    if isinstance(source, (bytes, bytearray)):
        archive = zipfile.ZipFile(io.BytesIO(bytes(source)))
    elif hasattr(source, "read"):
        archive = zipfile.ZipFile(io.BytesIO(source.read()))
    else:
        archive = zipfile.ZipFile(str(source))

    with archive:
        names = archive.namelist()
        members = {n: archive.read(n) for n in names
                   if n == "index.html" or n.endswith("/analysis")}
        resources = [n for n in names if "/resources/" in n]
    return {"names": names, "members": members, "resources": resources}


def _decode_analyses(members: dict[str, bytes]) -> list[dict]:
    out: list[dict] = []
    for name in sorted(members, key=_entry_index):
        if not name.endswith("/analysis"):
            continue
        decoded = omv_proto.decode_analysis(members[name])
        if decoded is not None:
            dir_module = name.split("/", 1)[0].split(" ", 1)[-1]
            decoded["dir"] = dir_module
            out.append(decoded)
    return out


def _column_cells(column: dict, notes: dict[str, int]) -> tuple[list, list[str]]:
    """The raw values of a column and how jamovi would print each one."""
    values = [None if cell["missing"] else cell["value"] for cell in column["cells"]]
    fmt = omv_proto.determ_format(values, column["type"], column["format"])
    texts: list[str] = []
    for cell, value in zip(column["cells"], values):
        if cell["missing"]:
            text = ""
        else:
            text = omv_proto.format_number(value, fmt)
        for mark in cell["footnotes"]:
            index = notes.get(mark)
            if index is not None:
                text += "^{{{}}}".format(index)
        texts.append(text)
    return values, texts


def _table_from(item: dict, analysis: str) -> dict:
    raw = item["table"]
    notes = {note["key"]: i + 1 for i, note in enumerate(raw["notes"])}
    columns = [c for c in raw["columns"] if omv_proto.is_visible(c)]
    cells = [_column_cells(c, notes) for c in columns]
    height = max((len(values) for values, _ in cells), default=0)
    rows = [[texts[r] if r < len(texts) else "" for _, texts in cells] for r in range(height)]
    numbers = [[values[r] if r < len(values) else None for values, _ in cells] for r in range(height)]
    return {
        "analysis": analysis,
        "title": item["title"],
        "path": list(item["path"]),
        "columns": [c["title"] for c in columns],
        "column_names": [c["name"] for c in columns],
        "rows": rows,
        "values": numbers,
        "notes": [note["note"] for note in raw["notes"]],
    }


def tables_from_results(analyses: list[dict]) -> tuple[list[dict], list[dict]]:
    """Turn decoded analyses into the ``tables``/``analyses`` shape of a document.

    An analysis is stored under its module key (``ttestOneS``) and titled by the
    root of its output tree (``One Sample T-Test``), which is what a teacher sees
    on screen and types into a grading rule.
    """
    tables: list[dict] = []
    out: list[dict] = []
    for analysis in analyses:
        items = list(omv_proto.walk(analysis["results"]))
        title = items[0]["path"][0] if items and items[0]["path"] else (
            analysis.get("title") or analysis.get("name") or "")
        found: list[dict] = []
        for item in items:
            if item["kind"] != "table":
                continue
            table = _table_from(item, title)
            if not table["rows"] or not table["columns"]:
                continue
            table["module"] = analysis["name"]
            tables.append(table)
            found.append(table)
        images = [i["image"] for i in items if i["kind"] == "image"]
        notices = [i["notice"] for i in items if i["kind"] == "notice"]
        if not found and not images and not notices:
            continue
        out.append({"name": title, "module": analysis["name"],
                    "ns": analysis["ns"], "tables": found,
                    "images": images, "notices": notices})
    return tables, out


def parse_omv(source: PathLike, html: Optional[str] = None) -> dict[str, Any]:
    """Parse an ``.omv`` (path or bytes) into analyses, tables and notes.

    Results stored in the archive itself win: they are the numbers jamovi
    computed, not text that has been through a browser.  ``html`` (the report the
    client rendered) is only read when the document carries no results, which is
    the case for a ``.omv`` saved before any analysis ran.
    """
    archive = _read_archive(source)
    members = archive["members"]
    resources = archive["resources"]

    decoded = _decode_analyses(members)
    file_tables, file_analyses = tables_from_results(decoded)

    modules: list[str] = []
    for name in sorted((n for n in archive["names"] if n.endswith("/analysis")),
                       key=_entry_index):
        module = name.split("/", 1)[0].split(" ", 1)[-1]
        if module not in _EMPTY_MODULES:
            modules.append(module)

    if file_analyses:
        tables: list[dict] = file_tables
        analyses: list[dict] = file_analyses
        notes = [note for t in file_tables for note in t["notes"]]
        images = [image["path"] for a in file_analyses for image in a["images"]]
        titles = [a["name"] for a in file_analyses]
        aliases = {a["name"]: a["module"] for a in file_analyses}
        source_kind = "results"
    else:
        if html is None:
            html = members.get("index.html", b"").decode("utf-8", "replace")
        parser = _CellParser()
        parser.feed(html or "")
        tables = parser.tables
        notes = parser.paragraphs
        images = parser.images
        titles = parser.headings
        analyses = []
        for table in tables:
            name = table["analysis"]
            if analyses and analyses[-1]["name"] == name:
                analyses[-1]["tables"].append(table)
            else:
                analyses.append({"name": name, "module": None, "tables": [table]})
        # jamovi names an analysis in the UI ("Linear Regression") but keys it in the
        # archive ("linReg").  The two lists line up when every analysis rendered at
        # least one table, which is the only case a teacher can grade anyway.
        names = list(dict.fromkeys(t["analysis"] for t in tables if t["analysis"]))
        module_by_name = dict(zip(names, modules)) if len(names) == len(modules) else {}
        for entry in analyses:
            entry["module"] = module_by_name.get(entry["name"])
        aliases = dict(module_by_name)
        source_kind = "html"

    return {
        "source": source_kind,
        "modules": modules,
        "analyses": analyses,
        "tables": tables,
        "notes": notes,
        "images": images,
        "resources": resources,
        "titles": titles,
        "module_by_analysis": aliases,
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


def _table_names(table: dict) -> list[str]:
    """Everything a table can be recognised by: its caption and its group path."""
    names = [table.get("title") or ""]
    names.extend(p for p in table.get("path") or [] if p)
    return names


def _matches_table(table: dict, needle: str) -> int:
    best = -1
    for name in _table_names(table):
        score = _score_name(name, needle, {})
        if score > best:
            best = score
    return best


def lookup_stat(
    doc: dict[str, Any],
    analysis: Optional[str] = None,
    table: Optional[str] = None,
    column: Optional[str] = None,
    row: Optional[str] = None,
) -> tuple[Optional[float], str]:
    """Find one numeric value, and say why it could not be found.

    Returns ``(value, "")`` on success, or ``(None, reason)`` where reason is one
    of ``analysis``, ``table``, ``column``, ``row`` or ``value`` — a teacher
    reading "the table has no such column" knows the answer key is wrong, while
    "no such analysis" tells the student they never ran it.

    ``analysis``/``table``/``column``/``row`` are matched case-insensitively as
    substrings so a teacher can write ``table="Model Fit"`` without knowing the
    exact caption.  An analysis may also be given as its jamovi module key
    (``linReg``).  ``row=None`` means "the first data row", ``row="*"`` the last.

    Candidates are taken best-match first: "One-Way ANOVA" is a substring of both
    "One-Way ANOVA" and "One-Way ANOVA (Non-parametric)", and grading the wrong
    one silently gives the student a wrong mark.
    """
    aliases = {normalise(k): normalise(v) for k, v in (doc.get("module_by_analysis") or {}).items()}
    tables = doc.get("tables") or []
    scored = []
    for order, t in enumerate(tables):
        score = 0
        if analysis:
            analysis_score = max(
                _score_name(t.get("analysis") or "", analysis, aliases),
                _score_name(t.get("module") or "", analysis, {}),
            )
            if analysis_score < 0:
                continue
            score += analysis_score
        if table:
            table_score = _matches_table(t, table)
            if table_score < 0:
                continue
            score += table_score
        scored.append((score, order, t))
    scored.sort(key=lambda item: (-item[0], item[1]))

    if not scored:
        if analysis and not any(_score_name(t.get("analysis") or "", analysis, aliases) >= 0
                                or _score_name(t.get("module") or "", analysis, {}) >= 0
                                for t in tables):
            return None, "analysis"
        return None, "table"

    saw_column = False
    saw_row = False
    for _, _, t in scored:
        if column:
            idx = _column_index(t["columns"], column)
            if idx is None:
                continue
        else:
            idx = 0
        saw_column = True
        rows = t["rows"]
        if not rows:
            continue
        if row in (None, ""):
            position = 0
        elif row == "*":
            position = len(rows) - 1
        else:
            position = next((i for i, cells in enumerate(rows)
                             if _contains(" ".join(cells), row)), None)
            if position is None:
                continue
        saw_row = True
        values = t.get("values") or []
        if position < len(values) and idx < len(values[position]):
            raw = values[position][idx]
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                return float(raw), ""
        if idx < len(rows[position]):
            value = parse_number(rows[position][idx])
            if value is not None:
                return value, ""

    if not saw_column:
        return None, "column"
    if not saw_row:
        return None, "row"
    return None, "value"


def find_table(doc: dict[str, Any], table: str) -> Optional[dict]:
    """The table a grading rule points at, best match first, or None."""
    scored = [(_matches_table(t, table), i, t) for i, t in enumerate(doc.get("tables") or [])]
    scored = [s for s in scored if s[0] >= 0]
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][2]


def find_row(doc: dict[str, Any], table: str, row: str) -> Optional[dict[str, str]]:
    """Return one data row of a table as ``{column: cell}``, or None."""
    for t in doc["tables"]:
        if _matches_table(t, table) < 0:
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

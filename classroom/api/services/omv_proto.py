"""Decode the analysis results that jamovi stores inside a ``.omv``.

Every ``NNN <ns> <name>/analysis`` member of an ``.omv`` is an
``AnalysisResponse`` protobuf (``server/jamovi/server/jamovi.proto``) whose
``results`` element holds the whole output tree: tables, cells, images and
notices.  Reading it here hands the LMS the numbers themselves rather than text
scraped out of a browser's copy of the report, so a submission stays gradeable
even when nothing was captured on screen.

The wire format is decoded directly instead of generating ``jamovi_pb2``, which
would tie the classroom API to a build step of the jamovi server.
"""
from __future__ import annotations

import math
import struct
from typing import Any, Iterator, Optional

_VARINT = 0
_FIXED64 = 1
_LENGTH = 2
_FIXED32 = 5


class ProtoError(ValueError):
    pass


def _read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise ProtoError("truncated varint")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7
        if shift > 70:
            raise ProtoError("varint too long")


def fields(buf: bytes) -> Iterator[tuple[int, int, Any]]:
    """Yield ``(field number, wire type, value)`` for a protobuf message."""
    pos = 0
    end = len(buf)
    while pos < end:
        key, pos = _read_varint(buf, pos)
        number, wire = key >> 3, key & 7
        if wire == _VARINT:
            value, pos = _read_varint(buf, pos)
        elif wire == _FIXED64:
            if pos + 8 > end:
                raise ProtoError("truncated fixed64")
            value = struct.unpack_from("<d", buf, pos)[0]
            pos += 8
        elif wire == _LENGTH:
            length, pos = _read_varint(buf, pos)
            if pos + length > end:
                raise ProtoError("truncated length delimited field")
            value = buf[pos:pos + length]
            pos += length
        elif wire == _FIXED32:
            if pos + 4 > end:
                raise ProtoError("truncated fixed32")
            value = struct.unpack_from("<f", buf, pos)[0]
            pos += 4
        else:
            raise ProtoError(f"unsupported wire type {wire}")
        yield number, wire, value


def _text(buf: bytes, number: int) -> str:
    for n, wire, value in fields(buf):
        if n == number and wire == _LENGTH:
            return value.decode("utf-8", "replace")
    return ""


def _int(buf: bytes, number: int, default: int = 0) -> int:
    for n, wire, value in fields(buf):
        if n == number and wire == _VARINT:
            return value
    return default


def _int32(buf: bytes, number: int) -> Optional[int]:
    for n, wire, value in fields(buf):
        if n == number and wire == _VARINT:
            return value - (1 << 32) if value >= 1 << 31 else value
    return None


# jamovi formats numbers with the rules in client/common/formatting.ts; these are
# the settings a fresh jamovi install uses (significant figures, 3 digits).
DEFAULT_SETTINGS = {"t": "sf", "n": 3, "pt": "dp", "p": 3, "ds": "."}
_MIN_NS = 1e-3
_MAX_NS = 1e6


def determ_format(values: list, type_: str, format_: str,
                  settings: Optional[dict] = None) -> dict:
    """How wide a column needs to be printed, mirroring ``determFormat``."""
    settings = settings or DEFAULT_SETTINGS
    formats = format_.split(",") if format_ else []

    min_abs_ns = math.inf
    max_abs_expnt = -math.inf
    for value in values:
        if value is None or isinstance(value, str) or math.isnan(value):
            continue
        if "log10" in formats:
            value = 10 ** value
        abs_value = abs(value)
        if _MIN_NS <= abs_value <= _MAX_NS:
            if abs_value != 0 and math.isfinite(abs_value) and abs_value < min_abs_ns:
                min_abs_ns = abs_value
        else:
            exponent = int(math.log10(abs_value)) if abs_value else 0
            if exponent != 0 and math.isfinite(exponent):
                max_abs_expnt = max(max_abs_expnt, abs(exponent))

    lz = True
    t, n, ds = settings["t"], settings["n"], settings["ds"]
    if "pvalue" in formats:
        t, n, lz = settings["pt"], settings["p"], False

    min_ns, max_ns = _MIN_NS, _MAX_NS
    if t == "dp" and "pvalue" in formats:
        dp = sf = n
        min_ns, max_ns = -math.inf, math.inf
    elif "pvalue" not in formats and ("zto" in formats or "pc" in formats):
        dp = sf = n
        min_ns, max_ns = -math.inf, math.inf
    elif t == "sf":
        if type_ == "integer":
            dp, sf = 0, n
        elif not math.isfinite(min_abs_ns) or min_abs_ns == 0:
            dp, sf = n - 1, n
        else:
            sf = n
            dp = max(n - 1 - int(math.floor(math.log10(min_abs_ns))), 0)
    else:
        max_ns = math.inf
        min_ns = -math.inf
        dp, sf = n, n + 1

    expw = 0
    if math.isfinite(max_abs_expnt):
        expw = int(math.log10(max_abs_expnt)) + 1 if max_abs_expnt > 0 else 1

    return {"dp": dp, "sf": sf, "expw": max(expw, 0), "t": t, "lz": lz, "ds": ds,
            "format": format_, "minNS": min_ns, "maxNS": max_ns}


def _fixed(value: float, digits: int) -> str:
    """``toFixed()``: fixed point, halves rounded away from zero."""
    from decimal import Decimal, ROUND_HALF_UP
    quant = Decimal(1).scaleb(-digits) if digits > 0 else Decimal(1)
    sign = "-" if value < 0 else ""
    text = str(Decimal(repr(abs(value))).quantize(quant, rounding=ROUND_HALF_UP))
    if digits <= 0:
        text = text.split(".")[0]
    return sign + text


def format_number(value: Any, fmt: dict) -> str:
    """Render one numeric cell the way the results view would."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if math.isnan(value):
        return "NaN"
    if not math.isfinite(value):
        return "Inf" if value > 0 else "-Inf"

    formats = fmt["format"].split(",") if fmt["format"] else []
    ds = fmt["ds"]
    if "log10" in formats:
        value = 10 ** value
        if not math.isfinite(value):
            return "Inf" if value > 0 else "-Inf"

    if fmt["t"] == "dp" and "pvalue" in formats and value < 10 ** -fmt["dp"]:
        bound = _fixed(10 ** -fmt["dp"], fmt["dp"]).replace(".", ds)[1:]
        return "<\u2009" + bound
    if "pc" in formats:
        return f"{_fixed(100 * value, fmt['dp'] - 2).replace('.', ds)}\u2009%"
    if fmt["minNS"] <= abs(value) <= fmt["maxNS"]:
        out = _fixed(value, fmt["dp"])
        if not fmt["lz"] and out.startswith("0."):
            out = out[1:]
        return out.replace(".", ds)

    if value == 0:
        return _fixed(value, fmt["dp"]).replace(".", ds)
    exponent = int(math.floor(math.log10(abs(value))))
    mantissa = value / 10 ** exponent
    sign = "-" if abs(value) < 1 else "+"
    spaces = max(fmt["expw"] - (int(math.floor(math.log10(abs(exponent)))) if exponent else 0), 0)
    return (f"{_fixed(mantissa, fmt['sf'] - 1).replace('.', ds)}e{' ' * max(spaces - 1, 0)}"
            f"{sign}{abs(exponent)}")


def _decode_cell(buf: bytes) -> dict:
    cell: dict[str, Any] = {"value": None, "missing": True, "format": 0,
                            "footnotes": [], "symbols": []}
    for number, wire, value in fields(buf):
        if number in (1, 2, 3, 4):
            if number == 1 and wire == _VARINT:
                cell["value"] = _int32(buf, 1)
            elif number == 2 and wire == _FIXED64:
                cell["value"] = value
            elif number == 3 and wire == _LENGTH:
                cell["value"] = value.decode("utf-8", "replace")
            elif number == 4 and wire == _VARINT:
                cell["value"] = "NaN" if value == 1 else None
            cell["missing"] = False
        elif number == 5:
            cell["format"] = value
        elif number == 6:
            cell["footnotes"].append(value.decode("utf-8", "replace"))
        elif number == 7:
            cell["symbols"].append(value.decode("utf-8", "replace"))
    if cell["value"] is None:
        cell["missing"] = True
    return cell


def _decode_column(buf: bytes) -> dict:
    column: dict[str, Any] = {"name": "", "title": "", "type": "", "format": "",
                              "superTitle": "", "cells": [], "visible": None}
    for number, wire, value in fields(buf):
        if number == 1:
            column["name"] = value.decode("utf-8", "replace")
        elif number == 2:
            column["title"] = value.decode("utf-8", "replace")
        elif number == 3:
            column["type"] = value.decode("utf-8", "replace")
        elif number == 4:
            column["format"] = value.decode("utf-8", "replace")
        elif number == 5:
            column["superTitle"] = value.decode("utf-8", "replace")
        elif number == 7:
            column["cells"].append(_decode_cell(value))
        elif number == 15:
            column["visible"] = value
    return column


def _decode_table(buf: bytes) -> dict:
    table: dict[str, Any] = {"columns": [], "rowNames": [], "notes": [],
                             "swapRowsColumns": False, "asText": ""}
    for number, wire, value in fields(buf):
        if number == 1:
            table["columns"].append(_decode_column(value))
        elif number == 2:
            table["rowNames"].append(value.decode("utf-8", "replace"))
        elif number == 3:
            table["swapRowsColumns"] = bool(value)
        elif number == 4:
            table["notes"].append({"key": _text(value, 1), "note": _text(value, 2)})
        elif number == 5:
            table["asText"] = value.decode("utf-8", "replace")
    return table


def walk(element: dict, path: Optional[tuple] = None) -> Iterator[dict]:
    """Yield the leaf outputs of an element tree, with their group titles."""
    path = path or ()
    kind = element.get("kind")
    if kind in ("group", "array"):
        if element.get("title") or element.get("name"):
            child_path = path + (element.get("title") or element.get("name"),)
        else:
            child_path = path
        for child in element.get("elements", []):
            yield from walk(child, child_path)
    elif kind is not None:
        yield {"kind": kind, "name": element.get("name", ""),
               "title": element.get("title", ""), "path": path,
               **{k: v for k, v in element.items() if k in ("table", "image", "notice", "html", "preformatted")}}


def _decode_element(buf: bytes) -> dict:
    element: dict[str, Any] = {"kind": None, "name": "", "title": "", "status": 0,
                               "error": "", "elements": []}
    for number, wire, value in fields(buf):
        if number == 1:
            element["name"] = value.decode("utf-8", "replace")
        elif number == 2:
            element["title"] = value.decode("utf-8", "replace")
        elif number == 3:
            element["status"] = value
        elif number == 4:
            element["error"] = _text(value, 1)
        elif number == 6:
            element["kind"] = "table"
            element["table"] = _decode_table(value)
        elif number == 7:
            element["kind"] = "image"
            element["image"] = {"path": _text(value, 1), "width": _int(value, 2),
                                "height": _int(value, 3)}
        elif number == 8:
            element["kind"] = "group"
            element["elements"] = [_decode_element(child) for n, w, child in fields(value) if n == 1]
        elif number == 9:
            element["kind"] = "array"
            element["elements"] = [_decode_element(child) for n, w, child in fields(value) if n == 1]
        elif number == 10:
            element["kind"] = "preformatted"
            element["preformatted"] = value.decode("utf-8", "replace")
        elif number == 12:
            element["kind"] = "html"
            element["html"] = {"content": _text(value, 1)}
        elif number == 24:
            element["kind"] = "notice"
            element["notice"] = {"content": _text(value, 1), "type": _int(value, 2)}
    return element


def decode_analysis(blob: bytes) -> Optional[dict]:
    """Decode one ``NNN <name>/analysis`` member.

    Returns ``None`` for the placeholder entries jamovi writes for a document
    with no analyses, and for anything that is not a readable
    ``AnalysisResponse``.
    """
    if not blob:
        return None
    try:
        name = ns = title = ""
        analysis_id = 0
        results = None
        for number, wire, value in fields(blob):
            if number == 2 and wire == _VARINT:
                analysis_id = value
            elif number == 3 and wire == _LENGTH:
                name = value.decode("utf-8", "replace")
            elif number == 4 and wire == _LENGTH:
                ns = value.decode("utf-8", "replace")
            elif number == 7 and wire == _LENGTH:
                results = _decode_element(value)
            elif number == 18 and wire == _LENGTH:
                title = value.decode("utf-8", "replace")
        if results is None:
            return None
    except (ProtoError, struct.error, UnicodeDecodeError, IndexError):
        return None

    return {"id": analysis_id, "name": name, "ns": ns, "title": title,
            "results": results}


def is_visible(column: dict) -> bool:
    """Whether the results view shows this column — the client's ``isVis()``.

    ``Visible`` is ``DEFAULT_YES 0, DEFAULT_NO 1, YES 2, NO 3``, and
    ``client/resultsview/table.ts`` renders a column only for 0 or 2, so a
    statistics box the teacher unticked stays out of the grading table.
    """
    return column.get("visible") in (None, 0, 2)

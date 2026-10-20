"""Build ``.omv`` analysis members the way the jamovi server writes them.

``services.omv_proto`` reads the wire format; this writes just enough of it for
tests to describe an output tree in Python instead of committing binary blobs.
Field numbers come from ``server/jamovi/server/jamovi.proto``.
"""
from __future__ import annotations

import io
import struct
import zipfile


def varint(value: int) -> bytes:
    out = bytearray()
    value &= (1 << 64) - 1
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def tag(number: int, wire: int) -> bytes:
    return varint((number << 3) | wire)


def field(number: int, value) -> bytes:
    if isinstance(value, bool):
        return tag(number, 0) + varint(int(value))
    if isinstance(value, int):
        return tag(number, 0) + varint(value)
    if isinstance(value, float):
        return tag(number, 1) + struct.pack("<d", value)
    if isinstance(value, str):
        value = value.encode()
    if isinstance(value, bytes):
        return tag(number, 2) + varint(len(value)) + value
    raise TypeError(value)


def repeated(number: int, values) -> bytes:
    return b"".join(field(number, v) for v in values)


def cell(value, footnotes=()) -> bytes:
    if value is None:
        out = field(4, 0)                                  # Other.MISSING
    elif isinstance(value, bool):
        out = field(4, 1)                                  # Other.NOT_A_NUMBER
    elif isinstance(value, int):
        out = field(1, value)
    elif isinstance(value, float):
        out = field(2, value)
    else:
        out = field(3, str(value))
    return out + repeated(6, footnotes)


def column(name, title, cells, *, type_="number", format="", visible=None) -> bytes:
    out = field(1, name) + field(2, title) + field(3, type_) + field(4, format)
    out += b"".join(field(7, c) for c in cells)
    if visible is not None:
        out += field(15, visible)
    return out


def note(key, text) -> bytes:
    return field(1, key) + field(2, text)


def table(columns, *, title="", row_names=(), notes=()) -> bytes:
    out = b"".join(field(1, c) for c in columns)
    out += repeated(2, row_names)
    out += b"".join(field(4, n) for n in notes)
    return out


def image(path, width=700, height=400) -> bytes:
    return field(1, path) + field(2, width) + field(3, height)


def element(name, title, payload=None, *, kind=6, elements=()) -> bytes:
    """A ``ResultsElement``: payload for a leaf, elements= for a group/array.

    ``kind`` is the ``ResultsElement`` oneof field — 6 table, 7 image, 24 notice,
    and it defaults to a table because that is what gets graded.
    """
    out = field(1, name) + field(2, title)
    if elements:
        out += field(8, b"".join(field(1, e) for e in elements))
    elif payload is not None and kind is not None:
        out += field(kind, payload)
    return out


def analysis(name, results, *, analysis_id=1, ns="jmv", title="", options=None) -> bytes:
    """An ``AnalysisResponse``, which is what ``NNN <name>/analysis`` stores."""
    out = field(2, analysis_id) + field(3, name) + field(4, ns)
    if options is not None:
        out += field(6, options)
    out += field(7, results)
    out += field(18, title)
    return out


def omv(analyses, *, index_html="", resources=()) -> bytes:
    """A document holding ``NNN <name>/analysis`` members, like a real ``.omv``.

    ``analyses`` is a list of ``(directory name, AnalysisResponse bytes)``.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("meta", "Manifest-Version: 1.0\njamovi-Archive-Version: 11.0\n")
        archive.writestr("metadata.json", '{"document":{},"dataSet":{}}')
        if index_html:
            archive.writestr("index.html", index_html)
        for i, (name, blob) in enumerate(analyses, start=1):
            archive.writestr(f"{i:02d} {name}/analysis", blob)
        for path in resources:
            archive.writestr(path, b"\x89PNG")
    return buf.getvalue()

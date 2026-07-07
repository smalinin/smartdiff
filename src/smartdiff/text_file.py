#
# Copyright (C) 2015-2023 Sergey Malinin
#  Apache-2.0 license http://www.apache.org/licenses/
#
from __future__ import annotations

from codecs import BOM_UTF16_BE, BOM_UTF16_LE, BOM_UTF8
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TextFileFormat:
    encoding: str
    bom: bytes = b""
    newline: str = "\n"


@dataclass(frozen=True)
class LoadedTextFile:
    text: str
    format: TextFileFormat


def read_text_file(path: Path) -> LoadedTextFile:
    data = path.read_bytes()
    text, encoding, bom = _decode_text_bytes(data)
    return LoadedTextFile(
        text=text,
        format=TextFileFormat(
            encoding=encoding,
            bom=bom,
            newline=_detect_newline(text),
        ),
    )


def write_text_file(path: Path, text: str, file_format: TextFileFormat) -> None:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    serialized = normalized if file_format.newline == "\n" else normalized.replace("\n", file_format.newline)
    path.write_bytes(file_format.bom + serialized.encode(file_format.encoding))


def _decode_text_bytes(data: bytes) -> tuple[str, str, bytes]:
    if data.startswith(BOM_UTF8):
        return _decode_with_fallback(data[len(BOM_UTF8):], "utf-8", BOM_UTF8)
    if data.startswith(BOM_UTF16_LE):
        return _decode_with_fallback(data[len(BOM_UTF16_LE):], "utf-16-le", BOM_UTF16_LE)
    if data.startswith(BOM_UTF16_BE):
        return _decode_with_fallback(data[len(BOM_UTF16_BE):], "utf-16-be", BOM_UTF16_BE)

    if 0 in data:
        inferred_encoding = _infer_utf16_without_bom(data)
        if inferred_encoding is not None:
            return _decode_with_fallback(data, inferred_encoding, b"")

    try:
        return data.decode("utf-8"), "utf-8", b""
    except UnicodeDecodeError:
        inferred_encoding = _infer_utf16_without_bom(data)
        if inferred_encoding is not None:
            return _decode_with_fallback(data, inferred_encoding, b"")
        return data.decode("utf-8", errors="replace"), "utf-8", b""


def _decode_with_fallback(data: bytes, encoding: str, bom: bytes) -> tuple[str, str, bytes]:
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        text = data.decode(encoding, errors="replace")
    return text, encoding, bom


def _infer_utf16_without_bom(data: bytes) -> str | None:
    if len(data) < 2 or len(data) % 2 != 0:
        return None

    even_bytes = data[0::2]
    odd_bytes = data[1::2]
    even_zero_ratio = even_bytes.count(0) / len(even_bytes)
    odd_zero_ratio = odd_bytes.count(0) / len(odd_bytes)
    if odd_zero_ratio >= 0.25 and even_zero_ratio <= 0.1:
        return "utf-16-le"
    if even_zero_ratio >= 0.25 and odd_zero_ratio <= 0.1:
        return "utf-16-be"

    candidate_scores: list[tuple[float, str]] = []
    for encoding in ("utf-16-le", "utf-16-be"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        ascii_ratio = _ascii_text_ratio(text)
        control_ratio = _control_character_ratio(text)
        candidate_scores.append((ascii_ratio - control_ratio, encoding))

    if len(candidate_scores) != 2:
        return None

    candidate_scores.sort(reverse=True)
    best_score, best_encoding = candidate_scores[0]
    next_score, _ = candidate_scores[1]
    if best_score >= 0.6 and best_score - next_score >= 0.2:
        return best_encoding
    return None


def _ascii_text_ratio(text: str) -> float:
    if not text:
        return 1.0
    ascii_chars = sum(
        1
        for char in text
        if char in "\r\n\t" or (char.isascii() and char.isprintable())
    )
    return ascii_chars / len(text)


def _control_character_ratio(text: str) -> float:
    if not text:
        return 0.0
    control_chars = sum(
        1
        for char in text
        if char not in "\r\n\t" and (ord(char) < 32 or 127 <= ord(char) <= 159)
    )
    return control_chars / len(text)


def _detect_newline(text: str) -> str:
    crlf_count = text.count("\r\n")
    lf_count = text.count("\n") - crlf_count
    cr_count = text.count("\r") - crlf_count
    newline_count, newline = max(
        (
            (crlf_count, "\r\n"),
            (lf_count, "\n"),
            (cr_count, "\r"),
        ),
        key=lambda item: item[0],
    )
    return newline if newline_count > 0 else "\n"

"""
Resolve OCR bib candidates to WebAPI roster forms.

Mirrors RaceDay EventDistance.FormatBib:
  FormatBib(prefix, sequence) => prefix + sequence.ToString("D4")
  e.g. ("A", 20) -> "A0020", ("21", 20) -> "210020", ("", 20) -> "0020"
"""

from __future__ import annotations

import re
from collections import defaultdict


def normalize_alnum(raw: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())


def format_webapi_bib(prefix: str, sequence: int) -> str:
    if sequence < 1 or sequence > 9999:
        raise ValueError("sequence must be 1..9999")
    num = f"{sequence:04d}"
    p = (prefix or "").strip().upper()
    return f"{p}{num}" if p else num


def parse_webapi_bib(bib: str) -> tuple[str, int] | None:
    """
    Parse a WebAPI-issued bib (prefix + D4).
    Last 4 alnum digits are the zero-padded sequence; anything before is prefix.
    Dashes in prefix are stripped for parse; caller maps back via roster original.
    """
    b = normalize_alnum(bib)
    if len(b) >= 4 and b[-4:].isdigit():
        seq = int(b[-4:])
        if 1 <= seq <= 9999:
            return (b[:-4], seq)
    if b.isdigit():
        seq = int(b)
        if 1 <= seq <= 9999:
            return ("", seq)
    return None


def _roster_maps(roster: set[str]) -> tuple[dict[str, str], dict[int, list[str]]]:
    """norm -> original roster string; sequence -> list of original roster strings."""
    norm_to_orig: dict[str, str] = {}
    by_seq: dict[int, list[str]] = defaultdict(list)
    for raw in roster:
        if not raw:
            continue
        n = normalize_alnum(raw)
        if not n:
            continue
        if n not in norm_to_orig:
            norm_to_orig[n] = raw.strip().upper()
        parsed = parse_webapi_bib(n)
        if parsed is None:
            continue
        _, seq = parsed
        orig = norm_to_orig[n]
        if orig not in by_seq[seq]:
            by_seq[seq].append(orig)
    return norm_to_orig, by_seq


def resolve_against_roster(candidate: str, roster: set[str]) -> str | None:
    """
    Map an OCR token to exactly one roster bib when unambiguous.
    Returns the roster's original form (uppercased). None if no match / ambiguous.
    Empty roster → return normalized candidate (caller decides).
    """
    c = normalize_alnum(candidate)
    if not c:
        return None
    if not roster:
        return c

    norm_to_orig, by_seq = _roster_maps(roster)

    if c in norm_to_orig:
        return norm_to_orig[c]

    # Pure digits → treat as sequence (0020 / 20 / 020)
    if c.isdigit():
        seq = int(c)
        if 1 <= seq <= 9999:
            hits = by_seq.get(seq, [])
            if len(hits) == 1:
                return hits[0]
            return None

    parsed = parse_webapi_bib(c)
    if parsed is not None:
        pref, seq = parsed
        exact = format_webapi_bib(pref, seq)
        if exact in norm_to_orig:
            return norm_to_orig[exact]
        if not pref:
            hits = by_seq.get(seq, [])
            if len(hits) == 1:
                return hits[0]

    # Candidate has prefix shorter than D4 split (e.g. A20, A020)
    for orig in norm_to_orig.values():
        parsed_r = parse_webapi_bib(orig)
        if parsed_r is None:
            continue
        pref, _ = parsed_r
        if not pref:
            continue
        if c.startswith(pref):
            rest = c[len(pref) :]
            if rest.isdigit():
                seq = int(rest)
                if 1 <= seq <= 9999:
                    formatted = format_webapi_bib(pref, seq)
                    if formatted in norm_to_orig:
                        return norm_to_orig[formatted]
                    # Roster original may keep dashes; compare via parse
                    if normalize_alnum(orig) == normalize_alnum(formatted):
                        return orig

    return None

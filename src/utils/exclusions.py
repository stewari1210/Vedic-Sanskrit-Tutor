"""Fail-loud exclusion loader for the frozen G2-series held-out test set.

Rule (docs/roadmap_phase2_3.md): every SFT/DPO/GRPO data builder AND every data-layer
seed script must load ``excluded_units`` from the G2 manifest at RUNTIME and fail loudly
(raise, never warn/skip silently) if any excluded text appears in its outputs.

The manifest lives in the llm_lab repo (it is metadata only; the case file is kept
outside both repos by the owner). Override its location with the env var G2_MANIFEST.

Citation grammar handled (units are prefix-matched on integer components):
    RV 7.018.22 / 7.018.22 (bare RV key) / AVŚ 5.4.1 / PB 13.3.2 / ŚB 1.8.1.4 / AB 8.21.11
A unit 'RV 1.131' excludes every verse RV 1.131.*; 'ŚB 1.8.1' excludes ŚB 1.8.1.*.

This module has NO heavy imports on purpose (it is imported by build scripts).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

Unit = Tuple[str, Tuple[int, ...]]


class ExclusionViolation(RuntimeError):
    """Raised when excluded (held-out) text would appear in a data-layer output."""


_CORPUS_CODES = {
    "RV": "RV", "AVŚ": "AVS", "AVS": "AVS", "AV": "AVS", "AVP": "AVP",
    "VS": "VS", "TS": "TS", "MS": "MS", "KS": "KS", "KAPS": "KAPS", "KapS": "KAPS",
    "AB": "AB", "PB": "PB", "TMB": "PB", "ŚB": "SB", "SB": "SB", "ŚBM": "SB",
    "KB": "KB", "GB": "GB", "JB": "JB", "JUB": "JUB", "TB": "TB", "TA": "TA", "TĀ": "TA",
    "BĀU": "BAU", "BAU": "BAU", "CHU": "CHU", "ChU": "CHU", "CU": "CHU",
    "BŚS": "BSS", "BSS": "BSS", "NIR": "NIR", "Nir": "NIR",
}
# BUG FIX (found reviewing the kinship-audit diff): the old pattern whitelisted the preceding
# character ([\s॥(\[]), so a citation directly after a JSON quote / colon / comma — e.g.
# "hymn_reference": "RV 10.33.4" — was INVISIBLE to the fail-loud check. A negative lookbehind
# for word characters is the correct boundary.
_CIT = re.compile(
    r"(?<![A-Za-z0-9_ĀāĪīŪūṚṛŚśṢṣṬṭḌḍṆṇ])"
    r"(KapS|KAPS|AVŚ|AVS|AVP|AV|BŚS|BSS|BĀU|BAU|ChU|CHU|JUB|Nir|NIR|ŚBM|ŚB|SB|RV|VS|TS|MS|KS|AB|PB|KB|GB|JB|TB|TĀ|TA|CU)"
    r"\s*(\d+(?:\.\d+)*)"
)
_BARE_RV = re.compile(r"^\s*(\d+)\.(\d+)\.(\d+)\s*$")


def manifest_path() -> Path:
    env = os.environ.get("G2_MANIFEST")
    if env:
        return Path(env).expanduser()
    return (Path.home() / "claude" / "llm_lab" / "llm_lab" / "domains" / "vedic"
            / "eval" / "g2_test_manifest.json")


def parse_unit(text: str) -> Unit:
    m = _CIT.search(" " + text)
    if not m:
        raise ValueError(f"cannot parse excluded unit {text!r}")
    return _CORPUS_CODES[m.group(1)], tuple(int(x) for x in m.group(2).split("."))


def _parse_parallel_entry(entry) -> Unit:
    """Parse an entry in `parallel_units` (either a string like 'AVP 7.10' or a dict
    with {'unit': 'AVP 7.10', 'parallels': [...], 'evidence': '...'})."""
    if isinstance(entry, str):
        return parse_unit(entry)
    if isinstance(entry, dict) and isinstance(entry.get("unit"), str):
        return parse_unit(entry["unit"])
    raise ValueError(f"malformed parallel_units entry: {entry!r}")


def load_excluded_units(path: Optional[Path] = None, include_parallels: bool = True) -> List[Unit]:
    """Load `excluded_units` (and `parallel_units` when present) from the manifest.
    Raises loudly if the manifest is unavailable, malformed, or `excluded_units` is empty —
    a builder must never run with an empty/unknown exclusion list."""
    p = Path(path) if path else manifest_path()
    if not p.exists():
        raise FileNotFoundError(
            f"G2 manifest not found at {p}. Refusing to run a data builder without the "
            f"exclusion list (set G2_MANIFEST or check out the llm_lab repo).")
    data = json.loads(p.read_text(encoding="utf-8"))
    units = data.get("excluded_units")
    if not units or not isinstance(units, list):
        raise ValueError(f"manifest {p} has no usable 'excluded_units'")
    parsed = [parse_unit(u) for u in units]
    if include_parallels and "parallel_units" in data:
        parallels = data["parallel_units"]
        if not isinstance(parallels, list):
            raise ValueError(f"manifest {p} has non-list 'parallel_units'")
        for entry in parallels:
            u = _parse_parallel_entry(entry)
            if u not in parsed:
                parsed.append(u)
    return parsed


def parse_citation(text: str, default_corpus: Optional[str] = None) -> Optional[Unit]:
    """'RV 7.018.22' | '7.018.22' (RV) | 'ŚB 1.8.1.4' -> (corpus, ints). None if no citation."""
    m = _CIT.search(" " + text)
    if m:
        return _CORPUS_CODES[m.group(1)], tuple(int(x) for x in m.group(2).split("."))
    b = _BARE_RV.match(text)
    if b:
        return "RV", tuple(int(x) for x in b.groups())
    if default_corpus and re.match(r"^\s*\d+(\.\d+)*\s*$", text):
        return default_corpus, tuple(int(x) for x in text.strip().split("."))
    return None


def _inside(cit: Unit, unit: Unit) -> bool:
    return cit[0] == unit[0] and cit[1][: len(unit[1])] == unit[1]


def is_excluded(text: str, units: Optional[Sequence[Unit]] = None,
                default_corpus: Optional[str] = None) -> bool:
    units = units if units is not None else load_excluded_units()
    cit = parse_citation(text, default_corpus)
    return bool(cit) and any(_inside(cit, u) for u in units)


def find_citations(text: str) -> List[Unit]:
    return [(_CORPUS_CODES[m.group(1)], tuple(int(x) for x in m.group(2).split(".")))
            for m in _CIT.finditer(" " + text)]


def text_hits_excluded(text: str, units: Optional[Sequence[Unit]] = None) -> List[str]:
    """Every citation embedded in free text that falls inside an excluded unit."""
    units = units if units is not None else load_excluded_units()
    out = []
    for cit in find_citations(text):
        if any(_inside(cit, u) for u in units):
            out.append(f"{cit[0]} {'.'.join(map(str, cit[1]))}")
    return out


def assert_none_excluded(keys: Iterable[str], what: str,
                         units: Optional[Sequence[Unit]] = None,
                         default_corpus: Optional[str] = "RV") -> None:
    """Raise ExclusionViolation if any key/citation lies in an excluded unit.
    ``keys`` may be 'verse|token' keys ('7.096.05|3') — only the verse part is used."""
    units = units if units is not None else load_excluded_units()
    bad = []
    for k in keys:
        cit = parse_citation(str(k).split("|")[0], default_corpus)
        if cit and any(_inside(cit, u) for u in units):
            bad.append(k)
    if bad:
        raise ExclusionViolation(
            f"{what}: {len(bad)} output entr{'y' if len(bad) == 1 else 'ies'} fall inside "
            f"G2 excluded units (first 10: {bad[:10]}). Refusing to write.")


def excluded_rv_hymns(units: Optional[Sequence[Unit]] = None) -> set:
    """RV hymn keys 'M.SSS' (zero-padded, as in morphology_rv.json) that are excluded."""
    units = units if units is not None else load_excluded_units()
    return {"%d.%03d" % u[1][:2] for u in units if u[0] == "RV" and len(u[1]) >= 2}


def rv_verse_is_excluded(verse_key: str, units: Optional[Sequence[Unit]] = None) -> bool:
    """verse_key like '7.096.05' (morphology_rv.json style)."""
    units = units if units is not None else load_excluded_units()
    a, b, c = (int(x) for x in verse_key.split("."))
    return any(u[0] == "RV" and (a, b, c)[: len(u[1])] == u[1] for u in units)

"""Word-boundary sliding-window chunking & full-unit reconstruction for long Vedic prose.

Design (owner-approved 2026-11-23):
  - Sliding windows of ~120 encoder tokens (`paraphrase-multilingual-mpnet-base-v2`)
    with ~20 tokens of overlap, cut strictly at whitespace word boundaries (never
    inside a Devanāgarī grapheme cluster or word).
  - Every window keeps the unit's EXACT native citation (e.g. `MS 1.6.3` — never
    synthetic suffixes like `MS 1.6.3a`), plus `part` (0..n-1), `n_parts`, and
    `text_search` (accent-stripped text of THIS window).
  - Full native unit text is stored once: in `metadata["text"]` on `part == 0`
    and in a lightweight local sidecar `local_store/<dir>/<dir>_units.json` so
    retrieval can reconstruct the full unit centered around any winning window.
  - Both Qdrant and BM25 index the exact same windows (`<dir>_windows.jsonl`).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.utils.citations import strip_vedic_accents

TARGET_TOKENS = 120
OVERLAP_TOKENS = 20
MAX_ENCODER_TOKENS = 128


def make_sliding_windows(
    body: str,
    citation: str,
    tokenizer,
    target_tokens: int = TARGET_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
    max_tokens: int = MAX_ENCODER_TOKENS,
) -> List[str]:
    """Split a native unit's Devanāgarī `body` into word-boundary sliding windows.

    Each returned string is the window's Devanāgarī body (WITHOUT the trailing
    ` ॥ citation ॥` marker, which callers append). Every window + ` ॥ citation ॥`
    fits within `max_tokens` (128) encoder tokens whenever a single word fits.
    """
    words = body.split()
    if not words:
        return []

    suffix = f" ॥ {citation} ॥"
    full_search = strip_vedic_accents(body + suffix)
    full_len = len(tokenizer.encode(full_search, add_special_tokens=True, truncation=False))
    if full_len <= max_tokens:
        return [body]

    # Precompute individual word token lengths (fast lower-bound heuristic,
    # verified by exact tokenizer.encode on the candidate window).
    suffix_toks = len(tokenizer.encode(suffix, add_special_tokens=True, truncation=False))
    word_toks = [
        max(1, len(tokenizer.encode(strip_vedic_accents(w), add_special_tokens=False, truncation=False)))
        for w in words
    ]

    def _window_tokens(lo: int, hi: int) -> int:
        seg = " ".join(words[lo:hi]) + suffix
        return len(tokenizer.encode(strip_vedic_accents(seg), add_special_tokens=True, truncation=False))

    windows: List[str] = []
    n = len(words)
    i = 0
    while i < n:
        # Greedily estimate end index j using per-word token sums
        acc = suffix_toks
        j = i
        while j < n and (j == i or acc + word_toks[j] <= target_tokens):
            acc += word_toks[j]
            j += 1

        # Refine j against exact full-string encoding: grow up to target_tokens
        while j < n and _window_tokens(i, j + 1) <= target_tokens:
            j += 1
        # Shrink if combined tokenization exceeded max_tokens (always keep >= 1 word)
        while j > i + 1 and _window_tokens(i, j) > max_tokens:
            j -= 1

        windows.append(" ".join(words[i:j]))
        if j >= n:
            break

        # Walk back from j to achieve ~overlap_tokens of overlap (strictly > i)
        if j <= i + 1:
            i = j
        else:
            back = j
            ov = 0
            while back > i + 1 and ov < overlap_tokens:
                back -= 1
                ov += word_toks[back]
            i = max(i + 1, back)

    return windows


@lru_cache(maxsize=32)
def _load_unit_sidecar(local_folder: str, filename: str) -> Dict[str, str]:
    p = Path(local_folder) / filename / f"{filename}_units.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_full_unit_text(doc, local_folder: Optional[str] = None) -> Optional[str]:
    """Return the full native unit text (with `॥ citation ॥`) for a windowed doc."""
    meta = getattr(doc, "metadata", None) or {}
    if meta.get("full_unit_text"):
        return meta["full_unit_text"]
    if meta.get("part") == 0 and meta.get("text"):
        return meta["text"]
    cite = meta.get("citation")
    fname = meta.get("filename")
    if cite and fname:
        if local_folder is None:
            from src.config import LOCAL_FOLDER
            local_folder = str(LOCAL_FOLDER)
        sidecar = _load_unit_sidecar(local_folder, fname)
        if cite in sidecar:
            return sidecar[cite]
    return None


def center_excerpt_around_window(
    full_unit: str,
    matched_window: str,
    char_budget: int = 1200,
) -> str:
    """Return `full_unit` if it fits `char_budget`, otherwise a word-boundary slice
    of `full_unit` centered around `matched_window`, always preserving the trailing
    `॥ citation ॥` marker."""
    if len(full_unit) <= char_budget:
        return full_unit

    # Separate trailing citation marker so it is never lost on truncation
    m = re.search(r"\s*॥[^॥]+॥\s*$", full_unit)
    marker = m.group(0).strip() if m else ""
    body = full_unit[:m.start()].strip() if m else full_unit.strip()

    # Strip marker from matched_window to locate its span inside body
    mw = re.sub(r"\s*॥[^॥]+॥\s*$", "", matched_window).strip()
    pos = body.find(mw)
    if pos == -1 and len(mw) > 40:
        pos = body.find(mw[:40])
    if pos == -1:
        pos = 0
    center = pos + len(mw) // 2

    budget_body = max(200, char_budget - len(marker) - 6)
    half = budget_body // 2
    lo = max(0, center - half)
    hi = min(len(body), lo + budget_body)
    if hi == len(body):
        lo = max(0, hi - budget_body)

    # Snap lo/hi to whitespace word boundaries (never split inside a grapheme/word)
    if lo > 0:
        sp = body.find(" ", lo)
        if sp != -1 and sp < center:
            lo = sp + 1
    if hi < len(body):
        sp = body.rfind(" ", center, hi)
        if sp != -1 and sp > lo:
            hi = sp

    prefix = "… " if lo > 0 else ""
    suffix = " …" if hi < len(body) else ""
    core = f"{prefix}{body[lo:hi].strip()}{suffix}"
    return f"{core} {marker}".strip() if marker else core

#!/usr/bin/env python3
"""
Tranche 2 (The Sanskrit Library, CC BY-NC-SA 3.0) Corpus Expansion Ingest Script.

Fetches (or reads from `--cache-dir`), parses, converts SLP1 → Devanāgarī, validates
(visarga-bug check, accent preservation, Book 10 exclusion for TA, oversize >128
encoder-token audit), writes `local_store/<dir>/` + `knowledge_store/sources/<veda>.json`,
and generates `docs/tranche2_dryrun_report.{md,json}`.

Tranche 2 active dry-run texts:
  1. tb  — Taittirīya Brāhmaṇa                (Layer 4, brahmana_prose, accented)
  2. jub — Jaiminīya Upaniṣad Brāhmaṇa        (Layer 4, brahmana_prose)
  3. ta  — Taittirīya Āraṇyaka (Books 1–9; Book 10 / Mahānārāyaṇa Upaniṣad EXCLUDED)
             - Prapāṭhakas 1 (1–6), 4, 5: Sanskrit Library (accented)
             - Prapāṭhakas 7–9 (TaittUp): Sanskrit Library (unaccented)
             - Optional `--ta-manual-dir` fills 1.7–32, 2, 3, 6 from owner-supplied
               accented `sanskritdocuments.org` `.itx` files + diffs SL overlap.

Note on BŚS (`baudhss`), KS, JB:
  - `baudhss` `LoadText` strips TEI praśna/kaṇḍikā tags and `LoadXML` returns HTTP 500;
    BŚS is held pending `baudhss.xml` from The Sanskrit Library.
  - KS and JB are not hosted by The Sanskrit Library (TITUS permission required).

Usage:
    python ingest_tranche2_sanskritlibrary.py --dry-run --cache-dir <raw_cache>
    python ingest_tranche2_sanskritlibrary.py --dry-run --cache-dir <raw_cache> --ta-manual-dir archive/tranche2_manual
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import random
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
load_dotenv(PROJECT_ROOT / ".env", override=True)

from langchain_core.documents import Document
from src.config import COLLECTION_NAME, LOCAL_FOLDER, QDRANT_API_KEY, QDRANT_URL
from src.utils.citations import (
    BY_VEDA,
    convert_itrans_ta_to_devanagari,
    convert_slp1_sanskritlibrary_to_devanagari,
    convert_to_devanagari,
    find_visarga_bugs,
    has_vedic_accents,
    strip_vedic_accents,
)
from src.utils.pronunciation import assert_accents_preserved, clean_for_speech
from src.utils.windowing import (
    MAX_ENCODER_TOKENS,
    OVERLAP_TOKENS,
    TARGET_TOKENS,
    make_sliding_windows,
)

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "Accept": "application/json,text/html,*/*"}
SOURCES_DIR = PROJECT_ROOT / "knowledge_store" / "sources"

SL_VERBATIM_LICENCE = (
    "Copyright (C) 2010 The Sanskrit Library. All rights reserved other than those "
    "granted under the Creative Commons Attribution Non-Commercial Share Alike license "
    "available in full at http://creativecommons.org/licenses/by-nc-sa/3.0/legalcode , "
    "and summarized at http://creativecommons.org/licenses/by-nc-sa/3.0/ . Permission is "
    "granted to build upon this work non-commercially, as long as credit is explicitly "
    "acknowledged exactly as described herein and derivative work is distributed under "
    "the same license."
)

TEXT_CONFIGS: Dict[str, dict] = {
    "tb": {
        "veda": "taittiriya_brahmana",
        "prefix": "TB",
        "dir": "tb",
        "title": "Taittirīya Brāhmaṇa",
        "sl_ids": ["tb"],
        "accented": True,
        "edition": (
            "The Sanskrit Library First XML edition v0.1 (Peter M. Scharf & Matthias H. Ahlborn, 2010); "
            "TITUS Black Yajur-Veda Taittirīya-Brāhmaṇa (Jost Gippert, 2008); Makoto Fushimi (Ōsaka)"
        ),
        "licence": "CC BY-NC-SA 3.0 (The Sanskrit Library)",
        "licence_verbatim": SL_VERBATIM_LICENCE,
    },
    "jub": {
        "veda": "jaiminiya_upanisad_brahmana",
        "prefix": "JUB",
        "dir": "jub",
        "title": "Jaiminīya Upaniṣad Brāhmaṇa",
        "sl_ids": ["jub"],
        "accented": False,
        "edition": (
            "The Sanskrit Library First XML edition v0.1 (Peter M. Scharf & Matthias H. Ahlborn, 2010); "
            "TITUS (Jost Gippert, 2008); Masato Fujii & Mieko Kajihara (1995), based on Hanns Oertel (JAOS 16, 1896)"
        ),
        "licence": "CC BY-NC-SA 3.0 (The Sanskrit Library)",
        "licence_verbatim": SL_VERBATIM_LICENCE,
    },
    "ta": {
        "veda": "taittiriya_aranyaka",
        "prefix": "TA",
        "dir": "ta",
        "title": "Taittirīya Āraṇyaka (Books 1–9; Book 10 excluded)",
        "sl_ids": ["ta1", "ta4", "ta5", "taittup"],
        "accented": "partial",  # Prapāṭhakas 1, 4, 5 accented; Prapāṭhakas 7–9 (taittup) unaccented
        "edition": (
            "Prapāṭhakas 1 (Anuvākas 1–6), 4, 5: The Sanskrit Library v0.1 (Scharf & Ahlborn, 2010; "
            "TITUS/Gippert 2008; Arlo Griffiths 1997–98; Mitra 1872, Śāstri 1985, Āpaṭe 1897). "
            "Prapāṭhakas 7–9 (Taittirīya Upaniṣad): The Sanskrit Library v0.1 (Scharf & Ahlborn, 2010; "
            "TITUS/Gippert 2008; Kartik Jayaraman ITRANS)."
        ),
        "licence": "CC BY-NC-SA 3.0 (The Sanskrit Library)",
        "licence_verbatim": SL_VERBATIM_LICENCE,
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def fetch_sl_json(sl_id: str, cache_dir: Optional[Path]) -> Tuple[dict, str, int, str]:
    """Load Sanskrit Library LoadText JSON from cache_dir or live API."""
    url = f"https://sanskritlibrary.org/Library/LoadText?text=titus/vedic/{sl_id}&texttype=forTranslation"
    if cache_dir is not None:
        cached = cache_dir / f"{sl_id}.json"
        if cached.exists():
            raw = cached.read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            return json.loads(raw), sha, len(raw), datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=120).read()
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{sl_id}.json").write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    return json.loads(raw), sha, len(raw), datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def decode_sl_line(ln: List[str]) -> Tuple[str, str]:
    """Decode one Sanskrit Library LoadText token list into `(kind, text)`.

    ONLY `ln[0][0]` carries `'c'` (content) or `'s'` (structure/apparatus).
    """
    if not ln:
        return ("", "")
    kind = ln[0][0]
    first = ln[0][1:]
    text = " ".join([first] + ln[1:]).strip()
    return (kind, text)


def _strip_inline_braces_keeping_depth(txt: str, depth: int) -> Tuple[str, int]:
    """Keep only characters at `depth == 0` outside `{ ... }` apparatus blocks."""
    out: List[str] = []
    for ch in txt:
        if ch == "{":
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
        elif depth == 0:
            out.append(ch)
    return "".join(out), depth


# ── Per-text parsers ─────────────────────────────────────────────────────────

def parse_tb(data: dict) -> Tuple[List[Tuple[str, str, bool]], List[str]]:
    """Parse Taittirīya Brāhmaṇa (`tb.json`). Returns `([(cite, dev, accented)], notes)`."""
    lines = data["lines"]
    cite_re = re.compile(r"^\{BS\s+(\d+\.\d+\.\d+\.\d+)\}$")
    cur_cite: Optional[str] = None
    buf: List[str] = []
    units_raw: List[Tuple[str, str]] = []
    depth = 0
    apparatus_lines_skipped = 0

    def _flush():
        nonlocal cur_cite, buf
        if cur_cite and buf:
            joined = re.sub(r"\s+", " ", " ".join(buf)).strip()
            if joined:
                units_raw.append((cur_cite, joined))
        buf = []

    for ln in lines:
        k, txt = decode_sl_line(ln)
        if not k:
            continue
        if k == "s":
            m = cite_re.match(txt)
            if m:
                _flush()
                cur_cite = f"TB {m.group(1)}"
                depth = 0
                continue
            # Non-citation structural/apparatus line: update brace depth
            # Inline mantra letter tags `{z }` or `{h }` open & close on one line (depth stays 0)
            _, depth = _strip_inline_braces_keeping_depth(txt, depth)
            continue

        # k == 'c'
        if cur_cite is None:
            continue
        # Handle inline apparatus blocks `{ ... }` across or within c-lines
        cleaned, new_depth = _strip_inline_braces_keeping_depth(txt, depth)
        if depth > 0 and not cleaned.strip():
            apparatus_lines_skipped += 1
        depth = new_depth
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        # Strip trailing double-danda on the unit (citation marker adds ॥ TB K.P.A.V ॥)
        cleaned = re.sub(r"\s*\.\.+\s*$", "", cleaned).strip()
        if cleaned and cleaned not in (".", ".."):
            buf.append(cleaned)

    _flush()
    out: List[Tuple[str, str, bool]] = []
    for cite, slp1 in units_raw:
        # Remove trailing .. if split across buffer lines
        slp1 = re.sub(r"\s*\.\.+\s*$", "", slp1).strip()
        dev = convert_slp1_sanskritlibrary_to_devanagari(slp1, accented=True)
        dev = re.sub(r"\s*[।॥]+\s*$", "", dev).strip()
        if dev:
            out.append((cite, dev, True))
    notes = [
        f"Parsed {len(out)} native units across 28 Kāṇḍa.Prapāṭhaka pairs from {{BS K.P.A.V}} markers.",
        f"Stripped {apparatus_lines_skipped} variant-reading lines inside {{...}} apparatus blocks.",
    ]
    return out, notes


_ORDINAL_MAP: Dict[str, int] = {
    "azwAdaS": 18, "saptadaS": 17, "zoqaS": 16, "paYcadaS": 15,
    "caturdaS": 14, "trayodaS": 13, "dvAdaS": 12, "ekAdaS": 11,
    "daSam": 10, "navam": 9, "azwam": 8, "zwam": 8, "saptam": 7,
    "zazW": 6, "zazT": 6, "paYcam": 5, "caturT": 4,
    "tftIy": 3, "tftIt": 3, "dvitIy": 2, "praTam": 1,
}


def _ord_to_int(word: str) -> Optional[int]:
    w = word.strip().rstrip(".")
    for base, num in _ORDINAL_MAP.items():
        if w.startswith(base):
            return num
    return None


def parse_jub(data: dict) -> Tuple[List[Tuple[str, str, bool]], List[str]]:
    """Parse Jaiminīya Upaniṣad Brāhmaṇa (`jub.json`) into unique `JUB A.A.K` units."""
    lines = data["lines"]
    khanda_col_re = re.compile(
        r"([A-Za-z]+)[eo]\s+'nuvAke\s+('?[A-Za-z]+)\s+KaRqaH\b[.\s]*"
    )
    anuv_end_re = re.compile(r"^([A-Za-z]+)[eo]\s+'nuvAkas\s+samAptaH\b")

    adhyaya = 1
    prev_anuv = 0
    khanda_seq_by_anuv: Dict[Tuple[int, int], int] = {}
    buf: List[str] = []
    seen_cites: set[str] = set()
    units_raw: List[Tuple[str, str]] = []
    notes: List[str] = []

    def _emit(ad: int, an: int):
        nonlocal buf
        txt = re.sub(r"\s+", " ", " ".join(buf)).strip()
        buf = []
        if not txt:
            return
        k_num = khanda_seq_by_anuv.get((ad, an), 0) + 1
        khanda_seq_by_anuv[(ad, an)] = k_num
        cite = f"JUB {ad}.{an}.{k_num}"
        assert cite not in seen_cites, f"Duplicate JUB citation: {cite}"
        seen_cites.add(cite)
        txt = re.sub(r"\s*---\s*", " ", txt)
        txt = re.sub(r"\s*\.\.+\s*$", "", txt).strip()
        if txt:
            units_raw.append((cite, txt))

    for idx, ln in enumerate(lines):
        k, txt = decode_sl_line(ln)
        if not txt or "upanizadbrAhmaRaM samAptam" in txt:
            continue

        # Handle inline colophons (e.g. L2656/L2657 ending with '..saptame 'nuvAke ... KaRqaH ..')
        km = khanda_col_re.search(txt)
        if km:
            before = txt[:km.start()].strip()
            before = re.sub(r"\s*\.\.+\s*$", "", before).strip()
            if before:
                buf.append(before)
            anuv_num = _ord_to_int(km.group(1))
            kh_word = km.group(2).lstrip("'")
            # Handle `'zwama` elided form -> azwama
            if kh_word.startswith("zwama"):
                kh_ord = 8
            else:
                kh_ord = _ord_to_int(kh_word)
            assert anuv_num is not None, f"Unparsed JUB anuvaka at L{idx}: {txt!r}"
            if anuv_num == 1 and prev_anuv > 1:
                adhyaya += 1
            prev_anuv = anuv_num
            expected_k = khanda_seq_by_anuv.get((adhyaya, anuv_num), 0) + 1
            if kh_ord is not None and kh_ord != expected_k:
                notes.append(
                    f"JUB {adhyaya}.{anuv_num}: source colophon L{idx+1} reads ord={kh_ord} "
                    f"(assigned sequential JUB {adhyaya}.{anuv_num}.{expected_k})."
                )
            _emit(adhyaya, anuv_num)
            after = txt[km.end():].strip()
            if after:
                buf.append(after)
            continue

        am = anuv_end_re.match(txt)
        if am:
            anuv_num = _ord_to_int(am.group(1))
            assert anuv_num is not None, f"Unparsed JUB anuvaka end at L{idx}: {txt!r}"
            if anuv_num == 1 and prev_anuv > 1:
                adhyaya += 1
            prev_anuv = anuv_num
            # 1-khaṇḍa anuvākas (e.g. 1.5, 4.1..4.5) have no separate KaRqaH colophon
            if buf:
                _emit(adhyaya, anuv_num)
            continue

        buf.append(txt)

    if buf:
        _emit(adhyaya, prev_anuv or 1)

    out: List[Tuple[str, str, bool]] = []
    for cite, slp1 in units_raw:
        dev = convert_slp1_sanskritlibrary_to_devanagari(slp1, accented=False)
        dev = re.sub(r"\s*[।॥]+\s*$", "", dev).strip()
        if dev:
            out.append((cite, dev, False))
    notes.insert(0, f"Parsed {len(out)} unique khaṇḍas across Adhyāyas 1–{adhyaya}.")
    return out, notes


_ROMAN_MAP = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}


def _parse_anuvaka_num(tok: str) -> Optional[int]:
    t = tok.strip().upper()
    if t in _ROMAN_MAP:
        return _ROMAN_MAP[t]
    m = re.match(r"^(\d+)$", t)
    return int(m.group(1)) if m else None


def parse_ta_1_4_5(data: dict, prapathaka: int) -> Tuple[List[Tuple[str, str, bool]], List[str]]:
    """Parse Sanskrit Library `ta1.json`, `ta4.json`, or `ta5.json` (all accented)."""
    lines = data["lines"]
    anuv_hdr_re = re.compile(r"^Anuv\[[?a-z]+\]ka\s+([A-Za-z0-9]+)\b")
    stop_index_re = re.compile(r"initial words or phrases of", re.I)

    started = prapathaka != 1  # For TA1, wait for 'PRAP[?][?]HAKA I' / Anuvāka I to avoid double śānti
    cur_anuv: Optional[int] = None
    depth = 0
    raw_anuvs: Dict[int, List[str]] = {}
    anuv_order: List[int] = []
    notes: List[str] = []

    for idx, ln in enumerate(lines):
        k, txt = decode_sl_line(ln)
        if not k:
            continue
        if stop_index_re.search(txt):
            break
        if prapathaka == 1 and not started:
            if "PRAP" in txt:
                started = True
            continue

        if k == "s":
            hm = anuv_hdr_re.match(txt)
            if hm:
                depth = 0  # Anuvāka boundary always starts at brace depth 0
                anum = _parse_anuvaka_num(hm.group(1))
                assert anum is not None
                # Skip stray forward-header TA4 L338 (Anuvāka 9 immediately before Anuvāka 8)
                if idx + 1 < len(lines):
                    nk, nt = decode_sl_line(lines[idx + 1])
                    if nk == "s" and anuv_hdr_re.match(nt):
                        notes.append(f"TA {prapathaka}: skipped duplicate header L{idx+1} ({txt!r}) before {nt!r}.")
                        continue
                cur_anuv = anum
                if cur_anuv not in raw_anuvs:
                    raw_anuvs[cur_anuv] = []
                    anuv_order.append(cur_anuv)
                continue
            _, depth = _strip_inline_braces_keeping_depth(txt, depth)
            continue

        # k == 'c': always update brace depth even before Anuvāka 1!
        # Workaround for SL ta4 L689 typo where '{P[,]C: ... [)]' used ')' instead of '}'.
        if depth > 0 and "[)]" in txt and "(" not in txt and "}" not in txt:
            txt = txt.replace("[)]", "[}]")
        cleaned, depth = _strip_inline_braces_keeping_depth(txt, depth)
        if cur_anuv is None:
            continue
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned and cleaned not in (".", ".."):
            raw_anuvs[cur_anuv].append(cleaned)

    out: List[Tuple[str, str, bool]] = []
    for anum in anuv_order:
        joined = re.sub(r"\s+", " ", " ".join(raw_anuvs[anum])).strip()
        if not joined:
            # e.g. trailing empty Anuvāka 7 header in ta1.json
            notes.append(f"TA {prapathaka}.{anum}: empty in SL source (omitted).")
            continue

        # Strip trailing mnemonic summary marker `-- N --` if present
        joined = re.sub(r"--\s*\d+\s*---?\s*$", "", joined).strip()

        if prapathaka == 1:
            # TA 1 has explicit subsection markers `.. N ..` or `.. pX [=] mY ..`
            sub_re = re.compile(r"\.\.\s*(?:\d+|p\s*\d+\s*\[=\]\s*\[?m\s*\d+\]?)\s*\.\.")
            subs = [s.strip() for s in sub_re.split(joined) if s.strip()]
            if len(subs) >= 2:
                for k_idx, sub in enumerate(subs, start=1):
                    dev = convert_slp1_sanskritlibrary_to_devanagari(sub, accented=True)
                    dev = re.sub(r"\s*[।॥]+\s*$", "", dev).strip()
                    if dev:
                        out.append((f"TA 1.{anum}.{k_idx}", dev, True))
                continue

        # TA 4 and TA 5 (or undivided anuvaka): emit per-anuvaka native unit (windowed cleanly later)
        joined = re.sub(r"\s*\.\.+\s*$", "", joined).strip()
        dev = convert_slp1_sanskritlibrary_to_devanagari(joined, accented=True)
        dev = re.sub(r"\s*[।॥]+\s*$", "", dev).strip()
        if dev:
            out.append((f"TA {prapathaka}.{anum}", dev, True))

    notes.insert(0, f"TA Prapāṭhaka {prapathaka}: parsed {len(out)} native units from {len([a for a in anuv_order if raw_anuvs[a]])} anuvākas.")
    return out, notes


def parse_taittup(data: dict) -> Tuple[List[Tuple[str, str, bool]], List[str]]:
    """Parse Taittirīya Upaniṣad (`taittup.json`) as TA Prapāṭhakas 7, 8, 9 (unaccented)."""
    lines = data["lines"]
    # Skip opening guru/invocation (L0..L2) and stop after 'iti BfguvallI samAptA ..'
    valli_map = {
        "SIkzAvallI": 7,
        "brahmAnandavallI": 8,
        "BfguvallI": 9,
    }
    anuv_col_re = re.compile(r"^iti\s*([A-Za-z']+)|^ity\s*([A-Za-z']+)")
    kandika_re = re.compile(r"\.\.\s*(\d+)\s*\.\.")

    # First pass: collect lines by (prapathaka, anuvaka)
    prap = 7
    anuv = 1
    buf: List[str] = []
    units_out: List[Tuple[str, str, bool]] = []
    notes: List[str] = []

    def _flush_anuv(p: int, a: int):
        nonlocal buf
        joined = re.sub(r"\s+", " ", " ".join(buf)).strip()
        buf = []
        if not joined:
            return
        # Split on explicit `.. K..` kaṇḍikā markers
        matches = list(kandika_re.finditer(joined))
        if matches:
            pos = 0
            for m in matches:
                seg = joined[pos:m.start()].strip()
                pos = m.end()
                k_num = int(m.group(1))
                seg = re.sub(r"\s*\.\.+\s*$", "", seg).strip()
                if seg:
                    dev = convert_slp1_sanskritlibrary_to_devanagari(seg, accented=False)
                    dev = re.sub(r"\s*[।॥]+\s*$", "", dev).strip()
                    if dev:
                        units_out.append((f"TA {p}.{a}.{k_num}", dev, False))
            rem = joined[pos:].strip()
            if rem and len(rem) > 3:
                dev = convert_slp1_sanskritlibrary_to_devanagari(rem, accented=False)
                dev = re.sub(r"\s*[।॥]+\s*$", "", dev).strip()
                if dev:
                    next_k = int(matches[-1].group(1)) + 1
                    units_out.append((f"TA {p}.{a}.{next_k}", dev, False))
        else:
            dev = convert_slp1_sanskritlibrary_to_devanagari(joined, accented=False)
            dev = re.sub(r"\s*[।॥]+\s*$", "", dev).strip()
            if dev:
                units_out.append((f"TA {p}.{a}.1", dev, False))

    for idx, ln in enumerate(lines):
        _, txt = decode_sl_line(ln)
        if not txt:
            continue
        if idx <= 2 and any(x in txt for x in ("tEttirIyopanizat", "guruByo namaH", "hariH oM")):
            continue

        # Check vallī end colophon FIRST
        v_done = None
        for vname, pnum in valli_map.items():
            if f"{vname} samAptA" in txt:
                v_done = pnum
                break
        if v_done is not None:
            if buf:
                _flush_anuv(prap, anuv)
            prap = v_done + 1
            anuv = 1
            if v_done == 9:
                break  # Stop before closing śānti after Bhṛguvallī
            continue

        # Detect anuvāka end colophon (e.g. "iti praTamo 'nuvAkaH ..", "ityazwamo 'nuvAkaH ..")
        if "'nuvAkaH" in txt and txt.startswith("it"):
            # Extract ordinal right after iti / ity
            m_ord = re.match(r"it[iy]\s*([A-Za-z]+)", txt)
            anuv_num = _ord_to_int(m_ord.group(1)) if m_ord else anuv
            if anuv_num is None:
                anuv_num = anuv
            _flush_anuv(prap, anuv_num)
            anuv = anuv_num + 1
            continue

        # Note TA 7.10 and TA 8.8 lack closing `'nuvAkaH` colophon line right before next anuvāka
        # TA 7.10 (`ahaM vfkzasya rerivA` at L192) ends with `.. 1..` and immediately followed by
        # `iti daSamo 'nuvAkaH ..` at L198; TA 7.11 ends at `L246 ityekAdaSa 'nuvAkaH ..`.
        buf.append(txt)

    # Assert Book 10 is absent
    assert all(p in (7, 8, 9) for p in {int(c.split()[1].split(".")[0]) for c, _, _ in units_out}), (
        "Unexpected Prapāṭhaka outside 7–9 in taittup!"
    )
    notes.append(f"TA Prapāṭhakas 7–9 (taittup): parsed {len(units_out)} kaṇḍikā units (unaccented).")
    return units_out, notes


# ── Manual sanskritdocuments TA parser, overlap comparator & merger ──────────

def parse_ta_manual_itx(itx_path: Path) -> Tuple[Dict[int, List[Tuple[str, str, int]]], List[str]]:
    """Parse accented `taittirIyaAraNyaka.itx` for TA Prapāṭhakas 1–9 ONLY.

    Strictly excludes Prapāṭhaka 10 (Mahānārāyaṇa Upaniṣad) and the Ekāgnikāṇḍa
    appended at the end of the file (`|| 0| 0| ...||`). Returns
    `({prap_int: [(cite='TA P.A.K', dev, continuous_v), ...]}, notes)`.
    """
    raw_lines = itx_path.read_text(encoding="utf-8", errors="replace").splitlines()
    sec_re = re.compile(r"^\\section\{AraNyake\s+\S+\s+prashnaH\s+(\d+)\b")
    stop_re = re.compile(r"^\\section\{(?:AraNyake\s+dashamaH\s+prashnaH\s+10\b|ekAgnikANDe\b)")

    sections_raw: Dict[int, List[str]] = {}
    cur_p: Optional[int] = None
    for ln in raw_lines:
        if stop_re.match(ln.strip()):
            break
        sm = sec_re.match(ln.strip())
        if sm:
            pnum = int(sm.group(1))
            if 1 <= pnum <= 9:
                cur_p = pnum
                sections_raw[cur_p] = []
            else:
                cur_p = None
            continue
        if cur_p is None:
            continue
        st = ln.strip()
        if not st or st.startswith(("%", "\\chapter", "\\end", "\\engtitle", "\\itxtitle", "iti taittirIya")):
            continue
        sections_raw[cur_p].append(st)

    marker_re = re.compile(r"\|\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\|")
    by_prap: Dict[int, List[Tuple[str, str, int]]] = {}
    notes: List[str] = []

    for pnum in sorted(sections_raw):
        assert 1 <= pnum <= 9, f"Unexpected TA ITX section: {pnum}"
        joined = re.sub(r"\s+", " ", " ".join(sections_raw[pnum])).strip()
        matches = list(marker_re.finditer(joined))
        assert matches, f"No || 0| {pnum}| a| v|| markers found in ITX section {pnum}"

        units_p: List[Tuple[str, str, int]] = []
        k_counter_by_anuv: Dict[int, int] = {}
        prev_end = 0
        prev_anuv: Optional[int] = None

        for idx_m, m in enumerate(matches):
            f0, mp, anuv, cont_v = map(int, m.groups())
            assert f0 == 0 and mp == pnum, f"Unexpected marker in section {pnum}: {m.group(0)!r}"
            seg = joined[prev_end:m.start()].strip()
            prev_end = m.end()

            if idx_m == 0:
                # Strip opening pre-anuvaka invocation `0 ... shAntiH ||` before kaṇḍikā `1 ...`
                seg = re.sub(r"^0\s+.*?shAntiH[^|]*\|\|\s*(?=1\b)", "", seg)
            elif prev_anuv is not None and anuv != prev_anuv:
                # Strip trailing anuvāka mnemonic summary `(padas) || prev_anuv||` (and optional daśati summary `||`)
                seg = re.sub(rf"^.*?\|\|\s*{prev_anuv}\s*\|\|\s*(?:[^|\d][^|]*?\|\|\s*)?", "", seg)
                # Also strip any leading solitary `|| a||` variant at start of next anuvāka
                seg = re.sub(r"^\|\|\s*\d+\s*\|\|\s*", "", seg)
            else:
                # Inside same anuvāka: strip occasional stray `|| a||` if present
                seg = re.sub(r"^\|\|\s*\d+\s*\|\|\s*", "", seg)

            # Strip leading continuous kaṇḍikā number (e.g. `1 `, `4 `, `131 `)
            seg = re.sub(r"^\d+\s+", "", seg).strip()
            dev = convert_itrans_ta_to_devanagari(seg)
            dev = re.sub(r"\s*[।॥]+\s*$", "", dev).strip()
            if dev:
                k_seq = k_counter_by_anuv.get(anuv, 0) + 1
                k_counter_by_anuv[anuv] = k_seq
                units_p.append((f"TA {pnum}.{anuv}.{k_seq}", dev, cont_v))
            prev_anuv = anuv

        by_prap[pnum] = units_p
        notes.append(
            f"ITX Prapāṭhaka {pnum}: {len(units_p)} accented kaṇḍikā units across "
            f"{len(k_counter_by_anuv)} anuvākas (v={units_p[0][2]}..{units_p[-1][2]})."
        )

    assert 0 not in by_prap and 10 not in by_prap
    return by_prap, notes


def _norm_words_for_diff(dev_text: str) -> List[str]:
    s = strip_vedic_accents(dev_text)
    s = s.replace("।", " ").replace("॥", " ").replace("ऽ", " ").replace("ळ", "ल")
    return re.findall(r"[\u0900-\u097F]+", s)


def compare_ta_overlap(
    sl_by_prap: Dict[int, List[Tuple[str, str, bool]]],
    itx_by_prap: Dict[int, List[Tuple[str, str, int]]],
    out_md: Path,
) -> dict:
    """Compare Sanskrit Library TA (1.1–6, 4, 5, 7–9) against manual ITX where they overlap."""
    lines = [
        "# Taittirīya Āraṇyaka Overlap Comparison — Sanskrit Library vs. Manual `sanskritdocuments.org` ITX",
        "",
        "Compares accent-stripped Devanāgarī words & section numbering across all overlapping regions:",
        "- `TA 1.1–6` (`titus/vedic/ta1`, accented vs ITX accented)",
        "- `TA 4` (`titus/vedic/ta4`, accented vs ITX accented)",
        "- `TA 5` (`titus/vedic/ta5`, accented vs ITX accented)",
        "- `TA 7–9` (`titus/vedic/taittup`, unaccented vs ITX accented)",
        "",
        "| Region | SL Anuvākas | ITX Anuvākas | SL Units | ITX Units | Word Jaccard | Shared / Union Words | Key Observed Differences |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    summary = {}

    regions = [
        ("TA 1.1–6", [u for u in sl_by_prap[1] if int(u[0].split(".")[1]) <= 6], [u for u in itx_by_prap[1] if int(u[0].split(".")[1]) <= 6]),
        ("TA 4", sl_by_prap[4], itx_by_prap[4]),
        ("TA 5", sl_by_prap[5], itx_by_prap[5]),
        ("TA 7", sl_by_prap[7], itx_by_prap[7]),
        ("TA 8", sl_by_prap[8], itx_by_prap[8]),
        ("TA 9", sl_by_prap[9], itx_by_prap[9]),
    ]

    sample_blocks: List[str] = ["", "## Observed Anuvāka-Level Differences & Text Samples", ""]

    for label, sl_u, itx_u in regions:
        sl_anuv = {int(c.split()[1].split(".")[1]) for c, _, _ in sl_u}
        itx_anuv = {int(c.split()[1].split(".")[1]) for c, _, _ in itx_u}
        sl_words = set(_norm_words_for_diff(" ".join(d for _, d, _ in sl_u)))
        itx_words = set(_norm_words_for_diff(" ".join(d for _, d, _ in itx_u)))
        inter = len(sl_words & itx_words)
        union = len(sl_words | itx_words) or 1
        jacc = inter / union

        # Group by anuvāka for fine-grained comparison
        sl_by_a: Dict[int, List[str]] = {}
        for c, d, _ in sl_u:
            a = int(c.split()[1].split(".")[1])
            sl_by_a.setdefault(a, []).append(d)
        itx_by_a: Dict[int, List[str]] = {}
        for c, d, _ in itx_u:
            a = int(c.split()[1].split(".")[1])
            itx_by_a.setdefault(a, []).append(d)

        notes_diff = []
        if label == "TA 1.1–6":
            notes_diff.append("Both cover Anuvākas 1–6; SL includes final pratīka words in unit 4 of anuvāka (`सुतौषधयो द्वे च`), ITX separates after `|| 0| 1| a| v||`; ITX joins internal sandhi without spaces.")
        elif label in ("TA 4", "TA 5"):
            notes_diff.append(f"Exact {len(sl_anuv)}={len(itx_anuv)} anuvāka alignment; ITX splits into {len(itx_u)} pañcāśat/kaṇḍikā markers (`v`), SL groups by anuvāka (`TA {label.split()[1]}.A`); SL marks word boundaries whereas ITX preserves continuous Taittirīya sandhi (`संवथ्सर` vs `संवत्सर`).")
        else:
            notes_diff.append("Exact anuvāka alignment; SL `taittup` is unaccented while ITX has full Vedic svara marks (`॑ ॒ ᳚`) + Taittirīya anusvāra-sandhi.")

        lines.append(
            f"| `{label}` | {len(sl_anuv)} | {len(itx_anuv)} | {len(sl_u)} | {len(itx_u)} | "
            f"{jacc:.3f} | {inter}/{union} | {notes_diff[0]} |"
        )
        summary[label] = {
            "sl_anuvakas": len(sl_anuv),
            "itx_anuvakas": len(itx_anuv),
            "sl_units": len(sl_u),
            "itx_units": len(itx_u),
            "word_jaccard": round(jacc, 4),
        }

        # Pick first matching anuvāka for side-by-side preview
        a0 = sorted(sl_anuv & itx_anuv)[0]
        sl_preview = strip_vedic_accents(" ".join(sl_by_a[a0]))[:180]
        itx_preview = strip_vedic_accents(" ".join(itx_by_a[a0]))[:180]
        sample_blocks.append(f"### {label} — Anuvāka {a0} (SL `{len(sl_by_a[a0])}` unit(s) vs ITX `{len(itx_by_a[a0])}` unit(s))")
        sample_blocks.append(f"- **SL (unaccented view):** {sl_preview}")
        sample_blocks.append(f"- **ITX (unaccented view):** {itx_preview}")
        sample_blocks.append("")

    out_md.write_text("\n".join(lines + sample_blocks) + "\n", encoding="utf-8")
    return summary


def merge_ta_with_manual_itx(
    manual_dir: Optional[Path],
    sl_by_prap: Dict[int, List[Tuple[str, str, bool]]],
) -> Tuple[List[Tuple[str, str, bool]], dict, List[str]]:
    """Fill TA 1.7–32, 2, 3, and 6 from `taittirIyaAraNyaka.itx` if present, keeping SL for 1.1–6, 4, 5, 7–9."""
    if not manual_dir or not manual_dir.exists():
        merged = sl_by_prap[1] + sl_by_prap[4] + sl_by_prap[5] + sl_by_prap[7] + sl_by_prap[8] + sl_by_prap[9]
        return merged, {"present": False, "path": str(manual_dir) if manual_dir else None}, []

    itx_path = manual_dir / "taittirIyaAraNyaka.itx"
    if not itx_path.exists():
        candidates = sorted(manual_dir.glob("*.itx"))
        assert candidates, f"No .itx file found in {manual_dir}"
        itx_path = candidates[0]

    itx_sha = hashlib.sha256(itx_path.read_bytes()).hexdigest()
    itx_by_prap, itx_notes = parse_ta_manual_itx(itx_path)

    # Compare SL vs ITX where they overlap
    overlap_path = PROJECT_ROOT / "docs" / "ta_overlap_comparison.md"
    overlap_summary = compare_ta_overlap(sl_by_prap, itx_by_prap, overlap_path)

    # Build ordered merged TA 1..9:
    # - Prap 1.1–6 from SL, Prap 1.7–32 from ITX
    # - Prap 2, 3, 6 from ITX (all accented)
    # - Prap 4, 5 from SL (accented)
    # - Prap 7, 8, 9 from SL `taittup` (unaccented)
    p1_sl = [u for u in sl_by_prap[1] if int(u[0].split()[1].split(".")[1]) <= 6]
    p1_itx = [(c, d, True) for c, d, _ in itx_by_prap[1] if int(c.split()[1].split(".")[1]) >= 7]
    p2_itx = [(c, d, True) for c, d, _ in itx_by_prap[2]]
    p3_itx = [(c, d, True) for c, d, _ in itx_by_prap[3]]
    p6_itx = [(c, d, True) for c, d, _ in itx_by_prap[6]]

    merged = (
        p1_sl + p1_itx
        + p2_itx + p3_itx
        + sl_by_prap[4] + sl_by_prap[5]
        + p6_itx
        + sl_by_prap[7] + sl_by_prap[8] + sl_by_prap[9]
    )
    info = {
        "present": True,
        "path": str(itx_path),
        "sha256": itx_sha,
        "bytes": itx_path.stat().st_size,
        "overlap_comparison_doc": "docs/ta_overlap_comparison.md",
        "overlap_summary": overlap_summary,
        "added_units": {
            "1_anuvakas_7_to_32": len(p1_itx),
            "2": len(p2_itx),
            "3": len(p3_itx),
            "6": len(p6_itx),
        },
    }
    merge_notes = [
        f"Loaded manual ITX {itx_path.name} (sha256={itx_sha[:16]}…).",
        f"Filled TA 1.7–32 ({len(p1_itx)} units), TA 2 ({len(p2_itx)}), TA 3 ({len(p3_itx)}), TA 6 ({len(p6_itx)}); total TA 1–9 = {len(merged)} units.",
        f"Overlap report written -> docs/ta_overlap_comparison.md",
    ] + itx_notes
    return merged, info, merge_notes


# ── Document building & validation ───────────────────────────────────────────

def build_documents_for_text(
    code: str,
    units: List[Tuple[str, str, bool]],
    source_meta: dict,
    tokenizer,
) -> Tuple[str, List[Document], Dict[str, str], dict]:
    cfg = TEXT_CONFIGS[code]
    spec = BY_VEDA[cfg["veda"]]
    md_lines = [
        f"# {cfg['title']} (Devanāgarī, from The Sanskrit Library)\n",
        f"Edition: {cfg['edition']}.\n",
        f"Licence: {cfg['licence']}. Layer {spec.chronology_layer} ({spec.chronology_name}).\n",
    ]
    base_meta = {
        "title": cfg["title"],
        "author": ["Vedic Tradition", cfg["edition"]],
        "creator": "The Sanskrit Library (CC BY-NC-SA 3.0)",
        "source_id": cfg["veda"],
        "licence": cfg["licence"],
        "filename": cfg["dir"],
        "preprocessing": "sanskrit",
        "source_type": spec.source_type,
        "veda": cfg["veda"],
        "chronology_layer": spec.chronology_layer,
        "chronology_name": spec.chronology_name,
    }
    if spec.chronology_note:
        base_meta["chronology_note"] = spec.chronology_note

    docs: List[Document] = []
    units_sidecar: Dict[str, str] = {}
    cur_section = None
    accented_count = 0
    expected_accented_count = 0
    native_units = 0
    units_split = 0

    for cite, dev, expect_accent in units:
        if not dev:
            continue
        native_units += 1
        sec = ".".join(cite.split()[-1].split(".")[:-1]) or cite.split()[-1]
        if sec != cur_section:
            cur_section = sec
            md_lines.append(f"\n## {cfg['prefix']} {sec}\n")
        full_line = f"{dev} ॥ {cite} ॥"
        md_lines.append(full_line)
        units_sidecar[cite] = full_line

        if expect_accent:
            expected_accented_count += 1
        if has_vedic_accents(dev):
            accented_count += 1
            assert_accents_preserved(full_line, clean_for_speech(full_line))

        win_bodies = make_sliding_windows(
            dev,
            cite,
            tokenizer,
            target_tokens=TARGET_TOKENS,
            overlap_tokens=OVERLAP_TOKENS,
            max_tokens=MAX_ENCODER_TOKENS,
        )
        n_parts = len(win_bodies)
        if n_parts > 1:
            units_split += 1

        for part, wdev in enumerate(win_bodies):
            win_line = f"{wdev} ॥ {cite} ॥"
            win_search = strip_vedic_accents(win_line)
            unit_meta = {
                **base_meta,
                "citation": cite,
                "part": part,
                "n_parts": n_parts,
                "text_search": win_search,
            }
            if part == 0:
                unit_meta["text"] = full_line
            docs.append(Document(page_content=win_line, metadata=unit_meta))

    md_text = "\n".join(md_lines) + "\n"
    stats = {
        "accented_units": accented_count,
        "expected_accented_units": expected_accented_count,
        "native_units": native_units,
        "units_split": units_split,
    }
    return md_text, docs, units_sidecar, {**base_meta, "_stats": stats}


def count_oversize_chunks(docs: List[Document], tokenizer) -> Tuple[int, int]:
    over = 0
    max_tok = 0
    for d in docs:
        txt = d.metadata.get("text_search") or d.page_content
        n = len(tokenizer.encode(txt, add_special_tokens=True, truncation=False))
        if n > 128:
            over += 1
        if n > max_tok:
            max_tok = n
    return over, max_tok


# ── Additive-only Qdrant upload (HELD until --confirm-upload) ────────────────

def verify_collection_embedding(client, embed_model) -> None:
    model_name = getattr(embed_model, "model_name", "")
    assert "paraphrase-multilingual-mpnet-base-v2" in model_name, (
        f"Wrong embedding model: {model_name!r}"
    )
    info = client.get_collection(str(COLLECTION_NAME))
    vec_cfg = info.config.params.vectors
    col_dim = vec_cfg.size if hasattr(vec_cfg, "size") else next(iter(vec_cfg.values())).size
    probe = embed_model.embed_query("अग्निमीळे पुरोहितम्")
    assert len(probe) == col_dim == 768, f"Dimension mismatch: embed={len(probe)} vs collection={col_dim}"
    print(f"✅ Verified embedding model={model_name}, dim={col_dim}")


def upload_additive(client, embed_model, veda: str, docs: List[Document], batch_size: int = 32) -> int:
    from qdrant_client.http import models as qmodels

    existing = client.count(
        collection_name=str(COLLECTION_NAME),
        count_filter=qmodels.Filter(must=[qmodels.FieldCondition(
            key="metadata.veda", match=qmodels.MatchValue(value=veda)
        )]),
        exact=True,
    ).count
    if existing > 0:
        raise RuntimeError(
            f"Refusing additive upload: metadata.veda={veda!r} already has {existing:,} points in Qdrant."
        )
    total = len(docs)
    for i in range(0, total, batch_size):
        bc = docs[i:i + batch_size]
        vecs = embed_model.embed_documents([c.metadata.get("text_search") or c.page_content for c in bc])
        points = [
            qmodels.PointStruct(
                id=str(uuid4()),
                vector=v,
                payload={"page_content": c.page_content, "metadata": c.metadata},
            )
            for c, v in zip(bc, vecs)
        ]
        for attempt in range(4):
            try:
                client.upsert(collection_name=str(COLLECTION_NAME), points=points, wait=True)
                break
            except Exception as e:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        print(f"   📤 {veda}: {min(i + batch_size, total):,}/{total:,}", end="\r")
    print()
    return total


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Tranche 2 (Sanskrit Library) Corpus Expansion Ingest")
    ap.add_argument("--dry-run", action="store_true", help="Write local_store + sources + report; NO Qdrant calls.")
    ap.add_argument("--confirm-upload", action="store_true", help="Explicit confirmation required to write to cloud Qdrant.")
    ap.add_argument("--only", nargs="+", choices=list(TEXT_CONFIGS.keys()), help="Process only selected text codes.")
    ap.add_argument("--cache-dir", type=Path, default=None, help="Raw LoadText JSON cache directory.")
    ap.add_argument("--ta-manual-dir", type=Path, default=PROJECT_ROOT / "archive" / "tranche2_manual", help="Optional dir with manual accented TA .itx files.")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed for 10 random sample chunks per text.")
    args = ap.parse_args()

    if not args.dry_run and not args.confirm_upload:
        ap.error("Specify --dry-run (no Qdrant calls) or --confirm-upload (after owner settles TA & BŚS).")

    codes = args.only or list(TEXT_CONFIGS.keys())
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    from transformers import AutoTokenizer
    print("🔤 Loading paraphrase-multilingual-mpnet-base-v2 tokenizer…")
    enc_tok = AutoTokenizer.from_pretrained("sentence-transformers/paraphrase-multilingual-mpnet-base-v2")

    rng = random.Random(args.seed)
    all_docs_by_code: Dict[str, List[Document]] = {}
    summary_rows = []
    samples_by_code: Dict[str, List[dict]] = {}
    parse_notes_by_code: Dict[str, List[str]] = {}
    total_visarga_bugs = 0

    for code in codes:
        cfg = TEXT_CONFIGS[code]
        spec = BY_VEDA[cfg["veda"]]
        print(f"\n{'='*72}\n📥 [{code.upper()}] {cfg['title']} ({cfg['veda']})\n{'='*72}")

        source_files = {}
        raw_payloads: Dict[str, dict] = {}
        retrieved_utc = ""
        for sl_id in cfg["sl_ids"]:
            data, sha, nbytes, ret = fetch_sl_json(sl_id, args.cache_dir)
            raw_payloads[sl_id] = data
            retrieved_utc = ret
            source_files[sl_id] = {
                "url": f"https://sanskritlibrary.org/Library/LoadText?text=titus/vedic/{sl_id}&texttype=forTranslation",
                "catalog_url": f"https://sanskritlibrary.org/Catalog/texts.php?text=titus/vedic/{sl_id}",
                "bytes": nbytes,
                "sha256": sha,
            }
            print(f"  Loaded SL {sl_id}: {nbytes:,} bytes, {len(data['lines']):,} lines, sha256={sha[:16]}…")

        if code == "tb":
            units, notes = parse_tb(raw_payloads["tb"])
        elif code == "jub":
            units, notes = parse_jub(raw_payloads["jub"])
        elif code == "ta":
            u1, n1 = parse_ta_1_4_5(raw_payloads["ta1"], 1)
            u4, n4 = parse_ta_1_4_5(raw_payloads["ta4"], 4)
            u5, n5 = parse_ta_1_4_5(raw_payloads["ta5"], 5)
            u79, n79 = parse_taittup(raw_payloads["taittup"])
            sl_by_prap: Dict[int, List[Tuple[str, str, bool]]] = {
                1: u1,
                4: u4,
                5: u5,
                7: [u for u in u79 if u[0].startswith("TA 7.")],
                8: [u for u in u79 if u[0].startswith("TA 8.")],
                9: [u for u in u79 if u[0].startswith("TA 9.")],
            }
            units, manual_info, merge_notes = merge_ta_with_manual_itx(args.ta_manual_dir, sl_by_prap)
            notes = n1 + n4 + n5 + n79 + merge_notes

            # Mandatory Book 10 AND Ekāgnikāṇḍa exclusion assertions
            praps_seen = {int(c.split()[1].split(".")[0]) for c, _, _ in units}
            assert 10 not in praps_seen, f"Book 10 leaked into TA: {praps_seen}"
            assert 0 not in praps_seen, f"Ekāgnikāṇḍa (p=0) leaked into TA: {praps_seen}"
            assert praps_seen.issubset(set(range(1, 10))), f"Unexpected TA prapathakas: {praps_seen}"
            combined_ta = " ".join(dev for _, dev, _ in units)
            combined_ta_plain = strip_vedic_accents(combined_ta)
            assert "नारायणाय विद्महे" not in combined_ta_plain, "Mahānārāyaṇa Upaniṣad text found in TA!"
            assert "एकाग्निकाण्ड" not in combined_ta_plain, "Ekāgnikāṇḍa header leaked into TA!"
            assert "प्रसुग्मन्ता धियसानस्य" not in combined_ta_plain, "Ekāgnikāṇḍa 1.1 mantra leaked into TA!"
            assert "दीधियुर्नर" not in combined_ta_plain, "Ekāgnikāṇḍa 1.1 pratīka leaked into TA!"
        else:
            raise ValueError(f"Unsupported code: {code}")

        parse_notes_by_code[code] = notes
        for nt in notes:
            print(f"  ℹ️  {nt}")

        source_record = {
            "source_id": cfg["veda"],
            "code": code,
            "title": cfg["title"],
            "veda": cfg["veda"],
            "provider": "The Sanskrit Library",
            "retrieved_utc": retrieved_utc,
            "sl_sources": source_files,
            "edition": cfg["edition"],
            "licence": cfg["licence"],
            "licence_verbatim": cfg["licence_verbatim"],
            "chronology_layer": spec.chronology_layer,
            "chronology_name": spec.chronology_name,
            "source_type": spec.source_type,
        }
        if code == "ta":
            source_record["book_10_excluded"] = True
            source_record["ekagnikanda_excluded"] = True
            has_manual = bool(manual_info.get("present"))
            manual_desc = (
                "sanskritdocuments.org accented .itx (taittirIyaAraNyaka.itx, sha256 4be2a36e...149f6d; personal study & research only)"
                if has_manual
                else "PENDING manual download of accented .itx from sanskritdocuments.org"
            )
            source_record["prapathaka_sources"] = {
                "1_anuvakas_1_to_6": "The Sanskrit Library (titus/vedic/ta1, accented, CC BY-NC-SA 3.0)",
                "1_anuvakas_7_to_32": manual_desc,
                "2": manual_desc,
                "3": manual_desc,
                "4": "The Sanskrit Library (titus/vedic/ta4, accented, CC BY-NC-SA 3.0)",
                "5": "The Sanskrit Library (titus/vedic/ta5, accented, CC BY-NC-SA 3.0)",
                "6": manual_desc,
                "7_siksavalli": "The Sanskrit Library (titus/vedic/taittup, unaccented, CC BY-NC-SA 3.0)",
                "8_brahmanandavalli": "The Sanskrit Library (titus/vedic/taittup, unaccented, CC BY-NC-SA 3.0)",
                "9_bhrguvalli": "The Sanskrit Library (titus/vedic/taittup, unaccented, CC BY-NC-SA 3.0)",
                "10_mahanarayana": "EXCLUDED (late Upaniṣad, excluded per corpus spec)",
                "ekagnikanda_0": "EXCLUDED (Mantra-pāṭha / Ekāgnikāṇḍa, excluded per corpus spec)",
            }
            source_record["manual_ta_dir"] = manual_info
            if has_manual:
                source_record["manual_itx_licence_verbatim"] = (
                    "This text is prepared by volunteers and is to be used for personal study and research. "
                    "The file is not to be copied or reposted for promotion of any website or individuals or "
                    "for commercial purpose without permission. Please help to maintain respect for volunteer spirit."
                )

        src_path = SOURCES_DIR / f"{cfg['veda']}.json"
        src_path.write_text(json.dumps(source_record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        md_text, docs, units_sidecar, meta_out = build_documents_for_text(code, units, source_record, enc_tok)
        stats = meta_out.pop("_stats")
        accented_units = stats["accented_units"]
        expected_accented = stats["expected_accented_units"]
        native_units = stats["native_units"]
        units_split = stats["units_split"]

        vbugs = find_visarga_bugs(md_text)
        total_visarga_bugs += len(vbugs)
        over128, max_tok = count_oversize_chunks(docs, enc_tok)

        out_dir = Path(LOCAL_FOLDER) / cfg["dir"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{cfg['dir']}.md").write_text(md_text, encoding="utf-8")
        (out_dir / f"{cfg['dir']}_metadata.json").write_text(
            json.dumps(meta_out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (out_dir / f"{cfg['dir']}_units.json").write_text(
            json.dumps(units_sidecar, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        win_jsonl_path = out_dir / f"{cfg['dir']}_windows.jsonl"
        payload_bytes = 0
        with win_jsonl_path.open("w", encoding="utf-8") as wfh:
            for d in docs:
                rec_str = json.dumps({"page_content": d.page_content, "metadata": d.metadata}, ensure_ascii=False)
                payload_bytes += len(rec_str.encode("utf-8"))
                wfh.write(rec_str + "\n")

        vec_hnsw_mb = (len(docs) * 768 * 4 * 1.4) / (1024 * 1024)
        payload_mb = payload_bytes / (1024 * 1024)
        est_mb = vec_hnsw_mb + payload_mb

        print(f"  Native units  : {native_units:,} ({units_split:,} split into sliding windows)")
        print(f"  Window points : {len(docs):,}")
        print(f"  Accented units: {accented_units:,} / {expected_accented:,} expected (assert_accents_preserved: PASS)")
        print(f"  Windows >128  : {over128:,}, max_tokens={max_tok}")
        print(f"  Visarga bugs  : {len(vbugs)} {'✅ PASS' if not vbugs else '❌ FAIL: ' + str(vbugs[:10])}")
        print(f"  Est. Qdrant   : ~{est_mb:.2f} MB (vec+HNSW ~{vec_hnsw_mb:.2f} MB, payload ~{payload_mb:.2f} MB)")

        sample = rng.sample(docs, min(10, len(docs)))
        samples_by_code[code] = [
            {
                "citation": sd.metadata["citation"],
                "part": f"{sd.metadata['part']+1}/{sd.metadata['n_parts']}",
                "text": sd.page_content,
                "text_search": sd.metadata["text_search"],
            }
            for sd in sample
        ]

        all_docs_by_code[code] = docs
        summary_rows.append({
            "code": code,
            "veda": cfg["veda"],
            "prefix": cfg["prefix"],
            "layer": spec.chronology_layer,
            "source_type": spec.source_type,
            "native_units": native_units,
            "units_split": units_split,
            "windows": len(docs),
            "over128": over128,
            "max_tok": max_tok,
            "accented": accented_units,
            "expected_accented": expected_accented,
            "visarga_bugs": len(vbugs),
            "visarga_samples": vbugs[:10],
            "vec_hnsw_mb": round(vec_hnsw_mb, 2),
            "payload_mb": round(payload_mb, 2),
            "est_mb": round(est_mb, 2),
        })

    # Totals & headroom vs post-Tranche-1 baseline (36,403 pts, 148.35 MB disk / 42.61 MB RSS)
    total_native = sum(r["native_units"] for r in summary_rows)
    total_split = sum(r["units_split"] for r in summary_rows)
    total_windows = sum(r["windows"] for r in summary_rows)
    total_over = sum(r["over128"] for r in summary_rows)
    total_vec_mb = sum(r["vec_hnsw_mb"] for r in summary_rows)
    total_pay_mb = sum(r["payload_mb"] for r in summary_rows)
    total_mb = sum(r["est_mb"] for r in summary_rows)

    report_json = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "dry_run" if args.dry_run else "upload",
        "baseline_qdrant": {"points": 36403, "disk_mb": 148.35, "ram_rss_mb": 42.61},
        "projected_qdrant_after_dryrun_subset": {
            "points": 36403 + total_windows,
            "est_added_mb": round(total_mb, 2),
            "est_total_mb": round(148.35 + total_mb, 2),
        },
        "rows": summary_rows,
        "parse_notes": parse_notes_by_code,
        "samples": samples_by_code,
    }
    json_path = PROJECT_ROOT / "docs" / "tranche2_dryrun_report.json"
    json_path.write_text(json.dumps(report_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Write Markdown dry-run report
    md_rep = [
        "# Tranche 2 Dry-Run Report — The Sanskrit Library (TB, JUB, TA partial; BŚS held)",
        "",
        f"Generated: `{report_json['generated_utc']}` | Seed: `{args.seed}` | Qdrant writes: **NONE (HOLD)**",
        "",
        "## 1. Per-Text Summary",
        "",
        "| Prefix | Text | Layer | Native Units | Split Units | Window Pts | >128 tok | Max Tok | Accented Units | Visarga Bugs | Est. Qdrant MB |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in summary_rows:
        md_rep.append(
            f"| `{r['prefix']}` | `{r['veda']}` | L{r['layer']} | {r['native_units']:,} | {r['units_split']:,} | "
            f"{r['windows']:,} | {r['over128']} | {r['max_tok']} | {r['accented']:,}/{r['expected_accented']:,} | "
            f"{r['visarga_bugs']} | ~{r['est_mb']:.2f} |"
        )
    md_rep.extend([
        f"| **TOTAL** | *(TB + JUB + TA partial)* | — | **{total_native:,}** | **{total_split:,}** | "
        f"**{total_windows:,}** | **{total_over}** | **{max(r['max_tok'] for r in summary_rows)}** | "
        f"**{sum(r['accented'] for r in summary_rows):,}** | **{total_visarga_bugs}** | **~{total_mb:.2f}** |",
        "",
        "### Qdrant Capacity & Headroom (vs. Post-Tranche-1 Cluster State)",
        "",
        f"- **Current live Qdrant (`ancient_history`):** `36,403` points · `148.35 MB` disk/collection data · `42.61 MB` server jemalloc RSS.",
        f"- **Estimated Tranche 2 partial delta (`TB` + `JUB` + `TA 1.1–6, 4, 5, 7–9`):** `+{total_windows:,}` points · `~{total_mb:.2f} MB` (vec+HNSW `~{total_vec_mb:.2f} MB`, payload `~{total_pay_mb:.2f} MB`).",
        f"- **Projected total before `TA 1.7–32/2/3/6` & `BŚS`:** `{36403 + total_windows:,}` points · `~{148.35 + total_mb:.2f} MB` total collection footprint (well inside 1 GB Qdrant Cloud free tier).",
        "",
        "## 2. Structural & Source-Coverage Notes",
        "",
        "- **Taittirīya Āraṇyaka (`TA`) completeness:** Sanskrit Library `ta1` only contains **Prapāṭhaka 1 Anuvākas 1–6** (`L328 Anuvāka 7` is an empty header). Prapāṭhakas `1.7–32`, `2`, `3`, and `6` await manual download of accented `.itx` files from `sanskritdocuments.org` into `archive/tranche2_manual/`.",
        "- **Book 10 exclusion asserted:** Verified zero `TA 10.*` citations and zero Mahānārāyaṇa Upaniṣad text.",
    ])
    for code, nts in parse_notes_by_code.items():
        for nt in nts:
            md_rep.append(f"- **[{code.upper()}]** {nt}")

    md_rep.extend([
        "",
        "## 3. Baudhāyana Śrauta Sūtra (`BŚS`) Boundary Investigation",
        "",
        "- Downloaded `LoadText?text=titus/vedic/baudhss&texttype=forTranslation` (`1,696,490` bytes, `23,818` lines: `22,369` `'c'` content lines, `1,449` `'s'` variant/footnote lines).",
        "- **Conclusion: Praśna and kaṇḍikā boundaries do NOT survive in `LoadText` output.**",
        "  - Zero `'s'` or `'c'` lines carry praśna/kaṇḍikā numbers or colophons (`1,449` `'s'` lines are solely `{FN ...}` critical footnotes and textual variant sigla such as `BI`, `F`, `TS`, `TB`, `AnSS`).",
        "  - Actual Praśna boundaries have no uniform delimiter (for example, `P1 → P2` at `L1012 → L1013` has not even a `..`, whereas `P11 → P12` at `L7870 → L7871` ends with `saMtizWate vAjapeyaH ..`).",
        "  - `..` occurs `2,895` times across the text—including inside quoted mantras (e.g., `L330`, `L1102`)—with `609` occurrences before the Āyu/Amāvasu passage at `L15130` (Caland `BŚS 18.44`). Therefore Caland's `P.K` numbering cannot be reconstructed safely from `LoadText` alone.",
        "- **`LoadXML` returns HTTP `500`:** Per plan, BŚS waits for `baudhss.xml` from The Sanskrit Library.",
        "",
        "## 4. Ten Random Sample Windows Per Text",
        "",
    ])
    for code in codes:
        cfg = TEXT_CONFIGS[code]
        md_rep.append(f"### {cfg['prefix']} — {cfg['title']}\n")
        for i, item in enumerate(samples_by_code[code], 1):
            md_rep.append(f"{i}. **`{item['citation']}`** *(part {item['part']})*")
            md_rep.append(f"   - `text`: {item['text']}")
            md_rep.append(f"   - `text_search`: {item['text_search']}")
        md_rep.append("")

    md_path = PROJECT_ROOT / "docs" / "tranche2_dryrun_report.md"
    md_path.write_text("\n".join(md_rep) + "\n", encoding="utf-8")
    print(f"\n💾 Wrote {json_path}\n💾 Wrote {md_path}")

    if total_visarga_bugs > 0:
        print(f"\n❌ Visarga check FAILED with {total_visarga_bugs} offending word(s)!")
        sys.exit(2)

    if args.dry_run:
        print("\n⚡ --dry-run complete: ZERO Qdrant calls, ZERO BM25/lexicon modifications.")
        return

    # ── Additive upload path (--confirm-upload only) ─────────────────────────
    from qdrant_client import QdrantClient
    from src.settings import Settings

    assert QDRANT_URL and QDRANT_API_KEY
    client = QdrantClient(url=str(QDRANT_URL), api_key=str(QDRANT_API_KEY), timeout=120)
    embed_model = Settings.get_embed_model()
    verify_collection_embedding(client, embed_model)
    for code in codes:
        upload_additive(client, embed_model, TEXT_CONFIGS[code]["veda"], all_docs_by_code[code])
    py = sys.executable
    subprocess.run([py, str(PROJECT_ROOT / "rebuild_bm25_pickle.py")], check=True)
    subprocess.run([py, str(PROJECT_ROOT / "rebuild_bm25_pickle.py"), "--check"], check=True)
    subprocess.run([py, str(PROJECT_ROOT / "build_corpus_lexicon.py")], check=True)


if __name__ == "__main__":
    main()

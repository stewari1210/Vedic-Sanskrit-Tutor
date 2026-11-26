#!/usr/bin/env python3
"""
Tranche 1 (GRETIL) Corpus Expansion Ingest Script.

Fetches, converts to Devanāgarī, validates (visarga-bug check, accent check,
oversize >128 encoder-token audit), writes `local_store/<dir>/` +
`knowledge_store/sources/<veda>.json`, and (only with explicit `--confirm-upload`,
never in `--dry-run`) performs strictly additive upserts to cloud Qdrant +
BM25/lexicon resync.

Tranche 1 texts:
  1. ms  — Maitrāyaṇī Saṃhitā                  (Layer 3, yv_samhita)
  2. avp — Atharvaveda Paippalāda              (Layer 3, av_samhita)
  3. kb  — Kauṣītaki Brāhmaṇa                  (Layer 4, brahmana_prose)
  4. gb  — Gopatha Brāhmaṇa (Arlo Griffiths)   (Layer 4, brahmana_prose, late Brāhmaṇa)
  5. bau — Bṛhadāraṇyaka Upaniṣad (Kāṇva mūla) (Layer 4, brahmana_prose)
  6. chu — Chāndogya Upaniṣad (mūla)           (Layer 4, brahmana_prose)
  7. nir — Yāska: Nirukta                      (Layer 5, sutra_vedanga, source_type="commentary")

Usage:
    python ingest_tranche1_gretil.py --dry-run
    python ingest_tranche1_gretil.py --dry-run --only ms avp
    python ingest_tranche1_gretil.py --dry-run --cache-dir /path/to/raw_cache
    python ingest_tranche1_gretil.py --confirm-upload   # additive Qdrant upsert + BM25/lexicon sync
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import html as html_lib
import json
import random
import re
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
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

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "Accept": "text/html,application/xml,*/*"}
TEI_NS = {"t": "http://www.tei-c.org/ns/1.0"}
SOURCES_DIR = PROJECT_ROOT / "knowledge_store" / "sources"

TEXT_CONFIGS: Dict[str, dict] = {
    "ms": {
        "veda": "maitrayani_samhita",
        "prefix": "MS",
        "dir": "ms",
        "title": "Maitrāyaṇī Saṃhitā",
        "url": "https://gretil.sub.uni-goettingen.de/gretil/1_sanskr/1_veda/1_sam/maitrs_pu.htm",
        "ext": ".htm",
        "edition": "Leopold von Schroeder, Maitrāyaṇī Saṃhitā (Leipzig 1881–1886; repr. Wiesbaden 1970–1972)",
        "inputter": "Makoto Fushimi (Osaka, 2015); TITUS version by Jost Gippert (2016-05-05); GRETIL version 2016-12-01",
        "licence": "TITUS / GRETIL (scholarly, non-commercial use only)",
        "licence_verbatim": "All texts that can be downloaded via http from the TITUS server can be used freely for scholarly purposes, provided that they are quoted as sources and the name(s) of the editor(s) and the date of last changes are indicated in publications. The texts must not be used for any kind of commercial usage.",
    },
    "avp": {
        "veda": "atharvaveda_paippalada",
        "prefix": "AVP",
        "dir": "avp",
        "title": "Atharvaveda Saṃhitā (Paippalāda)",
        "url": "https://gretil.sub.uni-goettingen.de/gretil/corpustei/sa_paippalAdasaMhitA.xml",
        "ext": ".xml",
        "edition": "Dipak Bhattacharya, The Paippalāda-Saṁhitā of the Atharvaveda, Vols. 1–4 (Calcutta 1997–2016); Umberto Selva (2019, Kāṇḍa 17 selections)",
        "inputter": "Arlo Griffiths, Thomas Zehnder, Philipp Kubisch, Duccio Lelli, Alexander Lubotsky, Carmen Spiers, Michael Witzel; TEI by Maximilian Mehner (GRETIL 2020-02-10)",
        "licence": "CC BY-NC-SA 4.0",
        "licence_verbatim": "Distributed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.",
    },
    "kb": {
        "veda": "kausitaki_brahmana",
        "prefix": "KB",
        "dir": "kb",
        "title": "Kauṣītaki Brāhmaṇa (Śāṅkhāyana Brāhmaṇa)",
        "url": "https://gretil.sub.uni-goettingen.de/gretil/corpustei/sa_kauSItakibrAhmaNa.xml",
        "ext": ".xml",
        "edition": "E. R. Sreekrishna Sarma (Wiesbaden 1968; VOHD, Suppl. 9,1)",
        "inputter": "Muneo Tokunaga (March–April 1995); Reinhold Grünendahl; TEI by Maximilian Mehner",
        "licence": "CC BY-NC-SA 4.0",
        "licence_verbatim": "Distributed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.",
    },
    "gb": {
        "veda": "gopatha_brahmana",
        "prefix": "GB",
        "dir": "gb",
        "title": "Gopatha Brāhmaṇa",
        "url": "https://gretil.sub.uni-goettingen.de/gretil/corpustei/sa_gopathabrAhmaNa.xml",
        "ext": ".xml",
        "edition": "Dieuke Gaastra, Das Gopatha Brāhmaṇa (Leiden: Brill, 1919)",
        "inputter": "Arlo Griffiths (2005–06); Reinhold Grünendahl; TEI by Maximilian Mehner",
        "licence": "CC BY-NC-SA 4.0",
        "licence_verbatim": "Distributed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.",
    },
    "bau": {
        "veda": "brihadaranyaka_upanisad",
        "prefix": "BĀU",
        "dir": "bau",
        "title": "Bṛhadāraṇyaka Upaniṣad (Kāṇva)",
        "url": "https://gretil.sub.uni-goettingen.de/gretil/1_sanskr/1_veda/4_upa/brup___u.htm",
        "ext": ".htm",
        "edition": "Checked against V. P. Limaye & R. D. Vadekar, Eighteen Principal Upanisads, vol. 1 (Poona 1958), and TITUS",
        "inputter": "Members of the Sansknet project (www.sansknet.org); Reinhold Grünendahl (GRETIL)",
        "licence": "GRETIL (scholarly, non-commercial; companion TEI CC BY-NC-SA 4.0)",
        "licence_verbatim": "THIS GRETIL TEXT FILE IS FOR REFERENCE PURPOSES ONLY! COPYRIGHT AND TERMS OF USAGE AS FOR SOURCE FILE.",
    },
    "chu": {
        "veda": "chandogya_upanisad",
        "prefix": "ChU",
        "dir": "chu",
        "title": "Chāndogya Upaniṣad",
        "url": "https://gretil.sub.uni-goettingen.de/gretil/1_sanskr/1_veda/4_upa/chup___u.htm",
        "ext": ".htm",
        "edition": "Checked against V. P. Limaye & R. D. Vadekar, Eighteen Principal Upanisads, vol. 1 (Poona 1958), and TITUS",
        "inputter": "Members of the Sansknet project; revision 2017-03-17 (7,16.1) by James Fitzgerald; Reinhold Grünendahl (GRETIL)",
        "licence": "GRETIL (scholarly, non-commercial; companion TEI CC BY-NC-SA 4.0)",
        "licence_verbatim": "THIS GRETIL TEXT FILE IS FOR REFERENCE PURPOSES ONLY! COPYRIGHT AND TERMS OF USAGE AS FOR SOURCE FILE.",
    },
    "nir": {
        "veda": "nirukta",
        "prefix": "Nir",
        "dir": "nir",
        "title": "Nirukta (Yāska)",
        "url": "https://gretil.sub.uni-goettingen.de/gretil/corpustei/sa_yAska-nirukta.xml",
        "ext": ".xml",
        "edition": "Lakshman Sarup",
        "inputter": "Muneo Tokunaga (and partly M. Kobayashi, 1999-07-29); Reinhold Grünendahl; TEI by Maximilian Mehner (2020-07-31)",
        "licence": "CC BY-NC-SA 4.0",
        "licence_verbatim": "Distributed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.",
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def fetch_source(code: str, cache_dir: Optional[Path]) -> Tuple[bytes, str, str]:
    """Fetch raw bytes (from live URL or cache_dir if provided), return (bytes, sha256, retrieved_utc)."""
    cfg = TEXT_CONFIGS[code]
    raw: bytes
    if cache_dir is not None:
        cached = cache_dir / f"{code}{cfg['ext']}"
        if cached.exists():
            raw = cached.read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            return raw, sha, datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = urllib.request.Request(cfg["url"], headers=UA)
    raw = urllib.request.urlopen(req, timeout=120).read()
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{code}{cfg['ext']}").write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    return raw, sha, datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_iast_common(s: str) -> str:
    """Clean punctuation/markup artifacts from GRETIL IAST before Devanagari conversion."""
    s = html_lib.unescape(s).replace("\xa0", " ")
    # Remove [Page ...] editorial page markers and { ... } critical notes
    s = re.sub(r"\[Page[^\]]*\]", " ", s)
    # Remove double/single ASCII bars & editorial slashes/underscores/stars/daggers
    s = s.replace("//", " ").replace("||", " ").replace("|", " ").replace("/", " ")
    s = s.replace("_", " ").replace("*", "").replace("†", "").replace("+", " ")
    # Fix GRETIL 'h' immediately before whitespace/end when clearly an editorial visarga typo?
    # NEVER silently guess unless clearly non-word; let visarga validator report any real issue!
    s = re.sub(r"\s+", " ", s).strip()
    return s


def strip_html_body(raw_html: str) -> str:
    """Strip HTML head/style/tables and editorial footnote spans (`class="red"` / `class="blue"`),
    keeping only the Sanskrit text body."""
    # GRETIL legacy HTML files put the copyright & character table before </table>
    idx = raw_html.lower().rfind("</table>")
    body = raw_html[idx + 8:] if idx != -1 else raw_html
    # Strip editorial footnotes (MS uses <span class="red">...</span> for German/English FN
    # and <span class="blue">[Page ...]</span> for Schroeder page numbers)
    body = re.sub(r'<span\s+class=["\'](?:red|blue)["\'][^>]*>.*?</span>', " ", body, flags=re.I | re.S)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html_lib.unescape(body).replace("\xa0", " ")
    return body


def tei_element_text(el: ET.Element) -> str:
    """Extract Sanskrit text from a TEI element, skipping `<note>` editorial glosses
    and preferring `<corr>` over `<sic>` inside `<choice>`."""
    parts: List[str] = []
    tag = el.tag.split("}")[-1]
    if tag in ("note", "fw", "pb"):
        return ""
    if tag == "choice":
        corr = el.find("t:corr", TEI_NS) or el.find("t:reg", TEI_NS)
        if corr is not None:
            return tei_element_text(corr)
    if el.text:
        parts.append(el.text)
    for child in el:
        ctag = child.tag.split("}")[-1]
        if ctag not in ("note", "fw", "pb"):
            parts.append(tei_element_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


# ── Per-text parsers -> list[(citation_key, iast_text)] ──────────────────────

def parse_ms(raw: bytes) -> List[Tuple[str, str]]:
    """Maitrāyaṇī Saṃhitā (maitrs_pu.htm): units end with //MS_K,P.A//."""
    body = strip_html_body(raw.decode("utf-8", errors="replace"))
    marker_re = re.compile(r"//MS_(\d+),(\d+)\.(\d+)//")
    units: List[Tuple[str, str]] = []
    pos = 0
    for m in marker_re.finditer(body):
        seg = body[pos:m.start()]
        pos = m.end()
        # Strip any standalone heading lines (e.g. "Maitrāyaṇī-Saṃhitā" or "1,1")
        seg = re.sub(r"(?m)^\s*\[Page[^\]]*\]\s*$", "", seg)
        seg = re.sub(r"(?m)^\s*MS_\d+,\d+.*$", "", seg)
        seg = re.sub(r"(?m)^\s*Prapāṭhaka.*$", "", seg, flags=re.I)
        seg = re.sub(r"(?m)^\s*Kāṇḍa.*$", "", seg, flags=re.I)
        seg = clean_iast_common(seg)
        # Drop any leading stray ASCII header lines before first anuvaka
        if not units and "STRUCTURE OF REFERENCES" in seg:
            seg = seg.split("STRUCTURE OF REFERENCES", 1)[-1]
        if len(seg) > 2:
            cite = f"MS {int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}"
            units.append((cite, seg))
    return units


def parse_avp(raw: bytes) -> List[Tuple[str, str]]:
    """Atharvaveda Paippalāda (sa_paippalAdasaMhitA.xml): <lg xml:id='PS_K.H.V'>."""
    root = ET.fromstring(raw)
    body = root.find(".//t:body", TEI_NS)
    assert body is not None, "AVP TEI missing <body>"
    id_re = re.compile(r"^PS_(\d+)\.(\d+)\.(\d+)$")
    units: List[Tuple[str, str]] = []
    for lg in body.findall(".//t:lg", TEI_NS):
        xid = lg.attrib.get("{http://www.w3.org/XML/1998/namespace}id", "")
        m = id_re.match(xid)
        if not m:
            continue
        lines = [tei_element_text(l_el) for l_el in lg.findall("t:l", TEI_NS)]
        text = clean_iast_common(" ".join(lines))
        # Remove editorial lacuna markers like [---], (...), <...>
        text = re.sub(r"\[[^\]]*\]", " ", text)
        text = re.sub(r"\{[^}]*\}", " ", text)
        text = re.sub(r"-+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 2:
            cite = f"AVP {int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}"
            units.append((cite, text))
    return units


def parse_kb(raw: bytes) -> List[Tuple[str, str]]:
    """Kauṣītaki Brāhmaṇa (sa_kauSItakibrAhmaNa.xml): <p xml:id='KB_A.K.S'>."""
    root = ET.fromstring(raw)
    body = root.find(".//t:body", TEI_NS)
    assert body is not None, "KB TEI missing <body>"
    id_re = re.compile(r"^KB_(\d+)\.(\d+)\.(\d+)$")
    units: List[Tuple[str, str]] = []
    for p in body.findall(".//t:p", TEI_NS):
        xid = p.attrib.get("{http://www.w3.org/XML/1998/namespace}id", "")
        m = id_re.match(xid)
        if not m:
            continue
        txt = tei_element_text(p)
        # Drop Tokunaga ritual running-header parentheticals e.g. (agnyādhāna)
        txt = re.sub(r"\([^)]*\)", " ", txt)
        # Tokunaga uses '.' as word separator
        txt = txt.replace(".", " ")
        txt = clean_iast_common(txt)
        if len(txt) > 2:
            cite = f"KB {int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}"
            units.append((cite, txt))
    return units


def parse_gb(raw: bytes) -> List[Tuple[str, str]]:
    """Gopatha Brāhmaṇa (sa_gopathabrAhmaNa.xml, Arlo Griffiths): group (GBr_B,P.K<subletter>) into GB B.P.K."""
    root = ET.fromstring(raw)
    body = root.find(".//t:body", TEI_NS)
    assert body is not None, "GB TEI missing <body>"
    full = "\n".join(tei_element_text(p) for p in body.findall(".//t:p", TEI_NS))
    tag_re = re.compile(r"\(GBr_([^)]+)\)")
    grouped: Dict[Tuple[int, int, int], List[str]] = {}
    order: List[Tuple[int, int, int]] = []
    matches = list(tag_re.finditer(full))
    for i, m in enumerate(matches):
        tag_body = m.group(1)
        km = re.match(r"^(\d+),(\d+)\.(\d+)", tag_body)
        if not km:
            continue  # skip 0.0.0 mangala and colophons
        key = (int(km.group(1)), int(km.group(2)), int(km.group(3)))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full)
        seg = full[start:end]
        # Strip critical brackets & numbers
        seg = re.sub(r"\[[^\]]*\]", " ", seg)
        seg = re.sub(r"\([^)]*\)", " ", seg)
        seg = clean_iast_common(seg)
        if seg:
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(seg)
    units: List[Tuple[str, str]] = []
    for key in order:
        joined = re.sub(r"\s+", " ", " ".join(grouped[key])).strip()
        if len(joined) > 2:
            units.append((f"GB {key[0]}.{key[1]}.{key[2]}", joined))
    return units


def parse_up_legacy(raw: bytes, tag_prefix: str, canon_prefix: str) -> List[Tuple[str, str]]:
    """BĀU (brup___u.htm) & ChU (chup___u.htm): units end with || BrhUp_A,B.K || or || ChUp_P,K.V ||."""
    body = strip_html_body(raw.decode("utf-8", errors="replace"))
    marker_re = re.compile(rf"\|\|\s*{re.escape(tag_prefix)}_(\d+),(\d+)\.(\d+)\s*\|\|")
    units: List[Tuple[str, str]] = []
    pos = 0
    for m in marker_re.finditer(body):
        seg = body[pos:m.start()]
        pos = m.end()
        # Drop any non-Sanskrit header fragments before the first verse
        if not units:
            # Find start of actual Upanisad text (after UTF-8 char table / om)
            for anchor in ("oṃ", "uṣā vā", "om ity"):
                ai = seg.lower().rfind(anchor)
                if ai != -1:
                    seg = seg[ai:]
                    break
        seg = re.sub(r"\[[^\]]*\]", " ", seg)
        seg = re.sub(r"\([^)]*\)", " ", seg)
        seg = clean_iast_common(seg)
        if len(seg) > 2:
            cite = f"{canon_prefix} {int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}"
            units.append((cite, seg))
    return units


def parse_nir(raw: bytes) -> List[Tuple[str, str]]:
    """Yāska: Nirukta (sa_yAska-nirukta.xml): lines tagged 'A,K: ...'."""
    root = ET.fromstring(raw)
    body = root.find(".//t:body", TEI_NS)
    assert body is not None, "Nirukta TEI missing <body>"
    full = "\n".join(tei_element_text(p) for p in body.findall(".//t:p", TEI_NS))
    line_re = re.compile(r"^\s*(\d+),(\d+):\s*(.+)$")
    grouped: Dict[Tuple[int, int], List[str]] = {}
    order: List[Tuple[int, int]] = []
    for raw_line in full.splitlines():
        m = line_re.match(raw_line)
        if not m:
            continue
        key = (int(m.group(1)), int(m.group(2)))
        txt = m.group(3)
        # Drop Sarup/Tokunaga critical apparatus variants & RV reference parens/brackets
        txt = re.sub(r"\([^)]*\)", " ", txt)
        txt = re.sub(r"\[[^\]]*\]", " ", txt)
        # Tokunaga uses '.' as word separator
        txt = txt.replace(".", " ")
        txt = clean_iast_common(txt)
        if txt:
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(txt)
    units: List[Tuple[str, str]] = []
    for key in order:
        joined = re.sub(r"\s+", " ", " ".join(grouped[key])).strip()
        if len(joined) > 2:
            units.append((f"Nir {key[0]}.{key[1]}", joined))
    return units


PARSERS = {
    "ms":  parse_ms,
    "avp": parse_avp,
    "kb":  parse_kb,
    "gb":  parse_gb,
    "bau": lambda raw: parse_up_legacy(raw, "BrhUp", "BĀU"),
    "chu": lambda raw: parse_up_legacy(raw, "ChUp", "ChU"),
    "nir": parse_nir,
}


# ── Post-conversion cleanup for stray GRETIL artifacts ───────────────────────

def iast_unit_to_devanagari(iast: str) -> str:
    """Convert cleaned IAST unit to Devanāgarī and verify clean Sanskrit output."""
    # Remove stray ASCII digits / editorial punctuation that shouldn't transliterate
    s = re.sub(r"[0-9=#@~^\\<>\"'`]", " ", iast)
    # Fix GRETIL 'ṅ' / 'ñ' / punctuation artifacts; keep apostrophe as avagraha ONLY between Sanskrit letters
    s = re.sub(r"\s+'", " '", s)
    s = re.sub(r"\s+", " ", s).strip()
    dev = convert_to_devanagari(s, "iast")
    # Clean stray punctuation / excess spaces
    dev = re.sub(r"\s+", " ", dev).strip()
    return dev


def build_documents_for_text(
    code: str,
    units: List[Tuple[str, str]],
    source_meta: dict,
    tokenizer,
) -> Tuple[str, List[Document], Dict[str, str], dict]:
    """Build full-unit markdown, sliding-window LangChain Documents (~120 enc. tokens,
    ~20 overlap, word-boundary cut), full-unit sidecar map `{cite: full_line}`, and metadata dict."""
    cfg = TEXT_CONFIGS[code]
    spec = BY_VEDA[cfg["veda"]]
    md_lines = [
        f"# {cfg['title']} (Devanāgarī, from GRETIL)\n",
        f"Source: {cfg['url']}\n",
        f"Edition: {cfg['edition']}. Input: {cfg['inputter']}.\n",
        f"Licence: {cfg['licence']}. Layer {spec.chronology_layer} ({spec.chronology_name}).\n",
    ]
    base_meta = {
        "title": cfg["title"],
        "author": ["Vedic Tradition" if spec.source_type == "vedic_text" else "Yāska", cfg["inputter"]],
        "edition": cfg["edition"],
        "creator": "GRETIL (Göttingen Register of Electronic Texts in Indian Languages)",
        "source_url": cfg["url"],
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
    native_units = 0
    units_split = 0

    for cite, iast in units:
        dev = iast_unit_to_devanagari(iast)
        if not dev:
            continue
        native_units += 1
        sec = ".".join(cite.split()[-1].split(".")[:-1])
        if sec != cur_section:
            cur_section = sec
            md_lines.append(f"\n## {cfg['prefix']} {sec}\n")
        full_line = f"{dev} ॥ {cite} ॥"
        md_lines.append(full_line)
        units_sidecar[cite] = full_line

        if has_vedic_accents(dev):
            accented_count += 1
            # Verify Rule: assert_accents_preserved holds for user-visible pronunciation path
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
            # Keep full native unit text ONCE in Qdrant payload (on part == 0 only)
            if part == 0:
                unit_meta["text"] = full_line
            docs.append(Document(page_content=win_line, metadata=unit_meta))

    md_text = "\n".join(md_lines) + "\n"
    stats = {
        "accented_units": accented_count,
        "native_units": native_units,
        "units_split": units_split,
    }
    return md_text, docs, units_sidecar, {**base_meta, "_stats": stats}


def count_oversize_chunks(docs: List[Document], tokenizer) -> Tuple[int, int]:
    """Return (count_over_128, max_tokens) using the exact mpnet encoder tokenizer."""
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


# ── Additive-only Qdrant upload (ONLY with --confirm-upload) ─────────────────

def verify_collection_embedding(client, embed_model) -> None:
    """Rule 4: assert embedding model name & dimension match the collection before upload."""
    model_name = getattr(embed_model, "model_name", "")
    assert "paraphrase-multilingual-mpnet-base-v2" in model_name, (
        f"Wrong embedding model: {model_name!r} (expected paraphrase-multilingual-mpnet-base-v2)"
    )
    info = client.get_collection(str(COLLECTION_NAME))
    vec_cfg = info.config.params.vectors
    col_dim = vec_cfg.size if hasattr(vec_cfg, "size") else next(iter(vec_cfg.values())).size
    probe = embed_model.embed_query("अग्निमीळे पुरोहितम्")
    assert len(probe) == col_dim == 768, f"Dimension mismatch: embed={len(probe)} vs collection={col_dim}"
    print(f"✅ Verified embedding model={model_name}, dim={col_dim}")


def upload_additive(client, embed_model, veda: str, docs: List[Document], batch_size: int = 32) -> int:
    """Rule 3: strictly additive upsert for `veda` only — NEVER deletes existing points."""
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
            f"Refusing additive upload: metadata.veda={veda!r} already has {existing:,} points in Qdrant. "
            f"Roll back explicitly by metadata.veda filter first if re-uploading."
        )

    total = len(docs)
    for i in range(0, total, batch_size):
        bc = docs[i:i + batch_size]
        # Embed accent-stripped text_search so accented & unaccented texts share the exact vector space
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
                wait = 5 * (attempt + 1)
                print(f"   ⚠️ retry {attempt+1} in {wait}s ({type(e).__name__}: {e})")
                time.sleep(wait)
        print(f"   📤 {veda}: {min(i + batch_size, total):,}/{total:,}", end="\r")
    print()
    return total


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Tranche 1 (GRETIL) Corpus Expansion Ingest")
    ap.add_argument("--dry-run", action="store_true", help="Write local_store + sources JSON + full report; NO Qdrant calls.")
    ap.add_argument("--confirm-upload", action="store_true", help="Explicit confirmation required to write to cloud Qdrant.")
    ap.add_argument("--only", nargs="+", choices=list(TEXT_CONFIGS.keys()), help="Process only selected text codes.")
    ap.add_argument("--cache-dir", type=Path, default=None, help="Optional raw download cache directory.")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed for 10 random sample chunks per text.")
    args = ap.parse_args()

    if not args.dry_run and not args.confirm_upload:
        ap.error("Specify --dry-run (no Qdrant calls) or --confirm-upload (after owner sign-off).")

    codes = args.only or list(TEXT_CONFIGS.keys())
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    # Load exact encoder tokenizer for oversize (>128 token) measurement
    from transformers import AutoTokenizer
    print("🔤 Loading paraphrase-multilingual-mpnet-base-v2 tokenizer for oversize-chunk audit…")
    enc_tok = AutoTokenizer.from_pretrained("sentence-transformers/paraphrase-multilingual-mpnet-base-v2")

    rng = random.Random(args.seed)
    all_docs_by_code: Dict[str, List[Document]] = {}
    summary_rows = []
    total_visarga_bugs = 0

    for code in codes:
        cfg = TEXT_CONFIGS[code]
        spec = BY_VEDA[cfg["veda"]]
        print(f"\n{'='*72}\n📥 [{code.upper()}] {cfg['title']} ({cfg['veda']})\n{'='*72}")
        raw, sha, retrieved_utc = fetch_source(code, args.cache_dir)
        print(f"  Source: {cfg['url']}")
        print(f"  Downloaded: {len(raw):,} bytes  sha256={sha}")

        # Rule 1: record provenance JSON in knowledge_store/sources/<veda>.json
        source_record = {
            "source_id": cfg["veda"],
            "code": code,
            "title": cfg["title"],
            "veda": cfg["veda"],
            "source_url": cfg["url"],
            "retrieved_utc": retrieved_utc,
            "bytes": len(raw),
            "sha256": sha,
            "edition": cfg["edition"],
            "inputter": cfg["inputter"],
            "licence": cfg["licence"],
            "licence_verbatim": cfg["licence_verbatim"],
            "chronology_layer": spec.chronology_layer,
            "chronology_name": spec.chronology_name,
            "chronology_note": spec.chronology_note,
            "source_type": spec.source_type,
        }
        src_path = SOURCES_DIR / f"{cfg['veda']}.json"
        src_path.write_text(json.dumps(source_record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        units = PARSERS[code](raw)
        assert units, f"Parser returned 0 units for {code}!"
        md_text, docs, units_sidecar, meta_out = build_documents_for_text(code, units, source_record, enc_tok)
        stats = meta_out.pop("_stats")
        accented_units = stats["accented_units"]
        native_units = stats["native_units"]
        units_split = stats["units_split"]

        # Visarga-bug check (MUST BE ZERO!)
        vbugs = find_visarga_bugs(md_text)
        total_visarga_bugs += len(vbugs)

        # Oversize >128 encoder token check on emitted windows
        over128, max_tok = count_oversize_chunks(docs, enc_tok)

        # Write local_store/<dir>/<dir>.md, <dir>_metadata.json, <dir>_units.json, <dir>_windows.jsonl
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
                rec_str = json.dumps(
                    {"page_content": d.page_content, "metadata": d.metadata},
                    ensure_ascii=False,
                )
                payload_bytes += len(rec_str.encode("utf-8"))
                wfh.write(rec_str + "\n")

        # Estimate Qdrant RAM + disk storage:
        #   vectors (fp32 768d = 3,072 B/pt) + HNSW graph (~1.4x vector size) + actual UTF-8 JSON payload
        vec_hnsw_mb = (len(docs) * 768 * 4 * 1.4) / (1024 * 1024)
        payload_mb = payload_bytes / (1024 * 1024)
        est_mb = vec_hnsw_mb + payload_mb

        print(f"  Native units  : {native_units:,} ({units_split:,} split into sliding windows)")
        print(f"  Window points : {len(docs):,} (+{len(docs) - native_units:,} extra windows)")
        print(f"  Accented units: {accented_units:,} (assert_accents_preserved: PASS)")
        print(f"  Windows >128  : {over128:,} ({100.0 * over128 / len(docs):.2f}%), max_tokens={max_tok}")
        print(f"  Visarga bugs  : {len(vbugs)} {'✅ PASS' if not vbugs else '❌ FAIL: ' + str(vbugs[:10])}")
        print(f"  Est. Qdrant   : ~{est_mb:.2f} MB (vec+HNSW ~{vec_hnsw_mb:.2f} MB, payload ~{payload_mb:.2f} MB)")

        # 10 random sample chunks in Devanāgarī with citations
        sample = rng.sample(docs, min(10, len(docs)))
        print(f"\n  ── 10 Random Sample Windows ({cfg['prefix']}) ──")
        for idx, sd in enumerate(sample, 1):
            preview = sd.page_content if len(sd.page_content) <= 180 else sd.page_content[:177] + "…"
            part_info = f" [part {sd.metadata['part']+1}/{sd.metadata['n_parts']}]" if sd.metadata.get("n_parts", 1) > 1 else ""
            print(f"    [{idx:02d}]{part_info} {preview}")

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
            "visarga_bugs": len(vbugs),
            "visarga_samples": vbugs[:10],
            "vec_hnsw_mb": round(vec_hnsw_mb, 2),
            "payload_mb": round(payload_mb, 2),
            "est_mb": round(est_mb, 2),
        })

    print(f"\n{'='*72}\n📊 TRANCHE 1 SUMMARY (SLIDING-WINDOW PROSE SPLITTING)\n{'='*72}")
    total_native = sum(r["native_units"] for r in summary_rows)
    total_split = sum(r["units_split"] for r in summary_rows)
    total_windows = sum(r["windows"] for r in summary_rows)
    total_over = sum(r["over128"] for r in summary_rows)
    total_vec_mb = sum(r["vec_hnsw_mb"] for r in summary_rows)
    total_pay_mb = sum(r["payload_mb"] for r in summary_rows)
    total_mb = sum(r["est_mb"] for r in summary_rows)
    for r in summary_rows:
        print(
            f"  {r['prefix']:4s} (L{r['layer']}, {r['source_type']:10s}): "
            f"{r['native_units']:5,d} units ({r['units_split']:3,d} split) → {r['windows']:6,d} pts | "
            f">128 tok: {r['over128']:3,d} (max {r['max_tok']:3d}) | "
            f"visarga_bugs: {r['visarga_bugs']} | ~{r['est_mb']:.2f} MB"
        )
    print(
        f"  TOTAL: {total_native:,} native units ({total_split:,} split) → {total_windows:,} window pts | "
        f">128 tok: {total_over:,} | est. Qdrant: ~{total_mb:.1f} MB "
        f"(vec+HNSW ~{total_vec_mb:.1f} MB, payload ~{total_pay_mb:.1f} MB) | visarga_bugs: {total_visarga_bugs}"
    )

    report_path = PROJECT_ROOT / "docs" / "tranche1_dryrun_report.json"
    report_path.write_text(json.dumps(summary_rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"💾 Wrote summary JSON -> {report_path}")

    if total_visarga_bugs > 0:
        print(f"\n❌ Visarga check FAILED with {total_visarga_bugs} offending word(s). Fix before upload!")
        sys.exit(2)

    if args.dry_run:
        print("\n⚡ --dry-run complete: wrote local_store/ + knowledge_store/sources/ with ZERO Qdrant calls.")
        return

    # ── Real additive upload (--confirm-upload) ─────────────────────────────
    from qdrant_client import QdrantClient
    from src.settings import Settings

    assert QDRANT_URL and QDRANT_API_KEY, "QDRANT_URL / QDRANT_API_KEY not configured"
    client = QdrantClient(url=str(QDRANT_URL), api_key=str(QDRANT_API_KEY), timeout=120)
    embed_model = Settings.get_embed_model()
    verify_collection_embedding(client, embed_model)

    before_total = client.get_collection(str(COLLECTION_NAME)).points_count
    print(f"\n🔌 Qdrant points before Tranche 1 upload: {before_total:,}")
    for code in codes:
        veda = TEXT_CONFIGS[code]["veda"]
        upload_additive(client, embed_model, veda, all_docs_by_code[code])
    after_total = client.get_collection(str(COLLECTION_NAME)).points_count
    print(f"\n✅ Additive upload complete: {before_total:,} → {after_total:,} (+{after_total - before_total:,})")

    # Rule 5: Two indexes, one truth — resync BM25 + verify + rebuild lexicon
    py = sys.executable
    subprocess.run([py, str(PROJECT_ROOT / "rebuild_bm25_pickle.py")], check=True)
    subprocess.run([py, str(PROJECT_ROOT / "rebuild_bm25_pickle.py"), "--check"], check=True)
    subprocess.run([py, str(PROJECT_ROOT / "build_corpus_lexicon.py")], check=True)
    print("✅ Tranche 1 upload + BM25 pickle + corpus lexicon fully synced!")


if __name__ == "__main__":
    main()

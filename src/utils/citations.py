"""Canonical citation registry, accent utilities, and visarga validation for VSR.

Single source of truth for all Vedic corpora (Layers 1–5), used by:
  - Citation extraction & normalization (frontend pinned lookup, exclusions, citation_enhancer)
  - Accent preservation (text) vs accent stripping (text_search)
  - Converter round-trip & visarga-bug validation (no spurious word-final ह्)
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

# ── Vedic accent codepoints (must stay in sync with src/utils/pronunciation.py) ─
VEDIC_ACCENT_CODEPOINTS: frozenset[int] = frozenset(
    [0x0951, 0x0952]                    # ॑ udātta, ॒ anudātta (Devanagari)
    + list(range(0x1CD0, 0x1D00))       # Vedic Extensions (svarita marks, etc.)
    + list(range(0xA8E0, 0xA900))       # Devanagari Extended (combining Vedic)
    + [0x0300, 0x0301, 0x0302, 0x0304]  # combining grave/acute/circumflex/macron (on romanization)
)

# Combining Devanagari Vedic accents ONLY (for stripping accents from Devanagari
# text_search while keeping all letters, vowel signs, anusvara, visarga, halanta).
_DEV_ACCENT_RE = re.compile(r"[\u0951\u0952\u1CD0-\u1CFF\uA8E0-\uA8FF]")


def strip_vedic_accents(text: str) -> str:
    """Return `text` with Vedic svara marks stripped for `text_search`.

    Leaves all Devanagari consonants, vowel signs, anusvāra (ं), visarga (ः),
    halanta (्), candrabindu (ँ), and avagraha (ऽ) completely intact.
    """
    if not text:
        return ""
    return _DEV_ACCENT_RE.sub("", text)


def has_vedic_accents(text: str) -> bool:
    return bool(_DEV_ACCENT_RE.search(text or ""))


# ── Visarga bug detection ────────────────────────────────────────────────────
# Existing AB/SB/TS/PB converters rendered visarga (ः) as ह् before whitespace /
# danda / EOL in ~39 places. New converters MUST NOT do this.
# Explicit allow-list of genuine Sanskrit verb roots / grammatical citations that
# legitimately end in ह् (e.g., cited bare roots in Nirukta etymologies).
ALLOWED_FINAL_HALANT_HA_WORDS: frozenset[str] = frozenset({
    "वह्", "दह्", "सह्", "लिह्", "दुह्", "गुह्", "रुह्", "रोह्", "नह्", "स्निह्",
    "द्रुह्", "मुह्", "मिह्", "मह्", "बृह्", "बर्ह्", "तृह्", "दृंह्", "स्पृह्",
    "ईह्", "गर्ह्", "अर्ह्", "गाह्", "बाह्", "उह्", "ऊह्", "गृह्", "स्नुह्",
    "रंह्", "तंह्", "मंह्", "राह्", "प्रवह्", "आवह्", "उपह्", "अभिदुह्",
    "निरुह्", "आरोह्", "प्ररुह्",
})

# ASCII IAST bare roots legitimately ending in vowel + 'h' (NOT visarga typos).
_IAST_ROOTS_ENDING_H: frozenset[str] = frozenset({
    "vah", "dah", "sah", "lih", "duh", "guh", "ruh", "roh", "nah", "snih",
    "druh", "muh", "mih", "mah", "gṛh", "gāh", "bāh", "uh", "ūh", "īh",
    "tṛh", "spṛh", "garh", "arh", "bṛh", "barh", "rāh", "snuh",
})

_IAST_WORD_FINAL_VOWEL_H_RE = re.compile(
    r"([a-zāīūṛṝḷḹṃḥṅñṭḍṇśṣ]*[aāiīuūṛṝḷḹeo])s?h(?=$|[\s,.;:!?।॥|/\"'()\[\]—–-])"
)


def fix_iast_ascii_visarga(iast: str) -> str:
    """Normalize GRETIL/Tokunaga ASCII word-final `h` after a vowel to visarga `ḥ`,
    except for genuine Sanskrit bare roots (e.g. `vah`, `roh`). Never touches
    aspirated consonants (`kh`, `gh`, `th`, `dh`, `bh`, etc.)."""
    def _repl(m: re.Match) -> str:
        full = m.group(0)
        if full in _IAST_ROOTS_ENDING_H:
            return full
        return m.group(1) + "ḥ"
    return _IAST_WORD_FINAL_VOWEL_H_RE.sub(_repl, iast)

_TRAILING_HALANT_HA_RE = re.compile(r"([\u0900-\u097F]*ह्)(?=\s|[।॥,.;:!?]|$)")


def find_visarga_bugs(
    text: str,
    allow_words: Optional[Set[str]] = None,
) -> List[Tuple[int, str]]:
    """Return [(line_no_1based, offending_word), ...] for any word ending in ह्
    before whitespace, a daṇḍa, punctuation, or EOL that is not on the allow-list."""
    allowed = ALLOWED_FINAL_HALANT_HA_WORDS if allow_words is None else (
        ALLOWED_FINAL_HALANT_HA_WORDS | set(allow_words)
    )
    bad: List[Tuple[int, str]] = []
    for lineno, line in enumerate((text or "").splitlines(), start=1):
        # Skip citation markers ॥ ... ॥
        body = re.sub(r"॥[^॥]*॥", " ", line)
        for m in _TRAILING_HALANT_HA_RE.finditer(body):
            word = strip_vedic_accents(m.group(1))
            if word not in allowed:
                bad.append((lineno, m.group(1)))
    return bad


# ── Transliteration helper (IAST / Velthuis / HK / SLP1 → Devanagari) ────────
# Accent marks that may appear on IAST/GRETIL vowels (combining acute U+0301 ->
# Devanagari udātta U+0951, combining grave U+0300 -> anudātta U+0952).
_ROMAN_ACCENT_MAP = {
    "\u0301": "\u0951",  # acute -> udātta (॑)
    "\u0300": "\u0952",  # grave -> anudātta (॒)
}
# Precomposed accented IAST vowels -> (base IAST char, Devanagari accent mark)
# Precomposed accented IAST vowels -> (base IAST vowel, PUA placeholder)
# Diphthongs ái/áu MUST keep their marker AFTER the full diphthong so sanscript
# produces वै॑ / वौ॑ instead of splitting into व॑इ / व॑उ.
_PUA_UDATTA = "\uE001"
_PUA_ANUDATTA = "\uE002"
_PUA_SVARITA = "\uE003"

_PRECOMPOSED_IAST_ACCENTS: Dict[str, Tuple[str, str]] = {
    "ái": ("ai", _PUA_UDATTA), "ài": ("ai", _PUA_ANUDATTA),
    "áu": ("au", _PUA_UDATTA), "àu": ("au", _PUA_ANUDATTA),
    "a\u0301i": ("ai", _PUA_UDATTA), "a\u0300i": ("ai", _PUA_ANUDATTA),
    "a\u0301u": ("au", _PUA_UDATTA), "a\u0300u": ("au", _PUA_ANUDATTA),
    "ā́": ("ā", _PUA_UDATTA), "ā̀": ("ā", _PUA_ANUDATTA),
    "ī́": ("ī", _PUA_UDATTA), "ī̀": ("ī", _PUA_ANUDATTA),
    "ū́": ("ū", _PUA_UDATTA), "ū̀": ("ū", _PUA_ANUDATTA),
    "ṛ́": ("ṛ", _PUA_UDATTA), "ṛ̀": ("ṛ", _PUA_ANUDATTA),
    "ṝ́": ("ṝ", _PUA_UDATTA), "ṝ̀": ("ṝ", _PUA_ANUDATTA),
    "á": ("a", _PUA_UDATTA), "à": ("a", _PUA_ANUDATTA),
    "í": ("i", _PUA_UDATTA), "ì": ("i", _PUA_ANUDATTA),
    "ú": ("u", _PUA_UDATTA), "ù": ("u", _PUA_ANUDATTA),
    "é": ("e", _PUA_UDATTA), "è": ("e", _PUA_ANUDATTA),
    "ó": ("o", _PUA_UDATTA), "ò": ("o", _PUA_ANUDATTA),
}


def _extract_iast_accents(iast: str) -> str:
    """Convert acute/grave accents on IAST vowels into PUA placeholders that
    pass untouched through `sanscript.transliterate(IAST -> DEVANAGARI)`, and
    normalize non-standard combining IAST sequences (e.g. GRETIL AVP m̐, ṝ, r̥)."""
    s = unicodedata.normalize("NFC", iast).lower()
    # Normalize GRETIL / scholarly combining sequences before transliteration:
    # - ṛ + combining macron -> ṝ ; ḷ + combining macron -> ḹ
    # - r + ring below (U+0325) -> ṛ ; l + ring below -> ḷ
    # - m + combining candrabindu (U+0310) -> ̐ (anunāsika -> Devanagari ँ)
    s = (s
         .replace("ṛ\u0304", "ṝ")
         .replace("ḷ\u0304", "ḹ")
         .replace("r\u0325\u0304", "ṝ")
         .replace("r\u0325", "ṛ")
         .replace("l\u0325", "ḷ")
         .replace("m\u0310", "\uE004")
         .replace("\u0310", "\uE004"))
    for k in sorted(_PRECOMPOSED_IAST_ACCENTS, key=len, reverse=True):
        if k in s:
            base, mark = _PRECOMPOSED_IAST_ACCENTS[k]
            s = s.replace(k, base + mark)
    s = s.replace("\u0301", _PUA_UDATTA).replace("\u0300", _PUA_ANUDATTA)
    return s


def convert_to_devanagari(text: str, scheme: str = "iast") -> str:
    """Convert Sanskrit text from `iast`, `velthuis`, `hk`, or `slp1` to Devanagari.

    Guarantees:
      - NFC normalization + lowercasing for IAST so decomposed `h\\u0323` or
        uppercase `Ḥ` always becomes visarga (ः), never `ह्`.
      - Vedic acute/grave accents in IAST become Devanagari udātta (॑) / anudātta (॒),
        including diphthongs (vái -> वै॑).
      - GRETIL candrabindu (`m̐`) becomes Devanagari candrabindu (`ँ`).
    """
    from indic_transliteration import sanscript

    scheme_l = scheme.lower().strip()
    if scheme_l == "iast":
        prepped = fix_iast_ascii_visarga(_extract_iast_accents(text))
        out = sanscript.transliterate(prepped, sanscript.IAST, sanscript.DEVANAGARI)
        return (out
                .replace(_PUA_UDATTA, "\u0951")
                .replace(_PUA_ANUDATTA, "\u0952")
                .replace(_PUA_SVARITA, "\u1CDA")
                .replace("\uE004", "\u0901"))
    elif scheme_l == "velthuis":
        return sanscript.transliterate(text, sanscript.VELTHUIS, sanscript.DEVANAGARI)
    elif scheme_l == "hk":
        return sanscript.transliterate(text, sanscript.HK, sanscript.DEVANAGARI)
    elif scheme_l == "slp1":
        prepped = (text
                   .replace("/", _PUA_UDATTA)
                   .replace("\\", _PUA_ANUDATTA)
                   .replace("^", _PUA_SVARITA))
        out = sanscript.transliterate(prepped, sanscript.SLP1, sanscript.DEVANAGARI)
        return (out
                .replace(_PUA_UDATTA, "\u0951")
                .replace(_PUA_ANUDATTA, "\u0952")
                .replace(_PUA_SVARITA, "\u1CDA"))
    else:
        raise ValueError(f"Unsupported transliteration scheme: {scheme!r}")


_SL_LONG_R_RE = re.compile(
    r"(?i)((?:pit|mAt|BrAt|hot|pot|nezw|SAst|gAt|kart|dAt|hart|jAmAt|duhAt|Bart|janayit)|(?<![A-Za-z])n)F(?=\\?(?:n\b|nt\b|MH|mR|RA|Ri))"
)
_SL_GENUINE_LONG_R_PLACEHOLDER = "\uE010"
_SLP1_ROOTS_ENDING_H: frozenset[str] = frozenset({
    "vah", "dah", "sah", "lih", "duh", "guh", "ruh", "roh", "nah", "snih",
    "druh", "muh", "mih", "mah", "gfh", "gAh", "bAh", "uh", "Uh", "Ih",
    "tfh", "spfh", "garh", "arh", "bFh", "barh", "rAh", "snuh",
})
_SLP1_WORD_FINAL_VOWEL_H_RE = re.compile(
    r"([A-Za-z0-9'*/\\^]*[aAiIuUfFxXeEoO][/\\^]?)h(?=$|[\s.,;!?|\"'()\[\]\-])"
)


def fix_slp1_ascii_visarga(slp1: str) -> str:
    """Normalize SLP1 word-final `h` typo after a vowel to visarga `H`, except bare roots."""
    def _repl(m: re.Match) -> str:
        raw_root = re.sub(r"[/\\^]", "", m.group(0))
        if raw_root in _SLP1_ROOTS_ENDING_H:
            return m.group(0)
        return m.group(1) + "H"
    return _SLP1_WORD_FINAL_VOWEL_H_RE.sub(_repl, slp1)


def convert_slp1_sanskritlibrary_to_devanagari(slp1_text: str, accented: bool = True) -> str:
    """Convert Sanskrit Library `LoadText` SLP1 (TITUS-derived) to Devanagari.

    Handles four quirks of Sanskrit Library's TITUS-to-SLP1 export:
      1. `[\x7f]` (anusvara/anunasika glyph) and inline `[ ]` in JUB -> `M`.
      2. Editorial hiatus `[_]` -> space; bracketed notes `[?]`, `[!]`, `[[,]]`,
         `[\\[]`, `[\\]]`, `[.]`, `[;]`, etc. stripped cleanly; `j[~]n`/`[~]n` -> `jY`/`Y`.
      3. When `accented=True` (TB, TA 1/4/5): TITUS exported accented `ṛ́` as `F`
         (and genuine long `ṝ` also as `F`), so preserve genuine long `ṝ` forms
         (`pitFn`, `hotFRAm`, `nF\\n`, `BartF\\Ri`, etc.) and map remaining `F`
         (without `/` or `\\`) -> `f/` (`ऋ॑` / `ृ॑`).
      4. When `accented=True`: split accented diphthongs (`a/i`, `a\\i`, `a/u`, `a\\u`)
         -> `E/`, `E\\`, `O/`, `O\\` so `sanscript` renders `वै॑` / `तौ॑` atomically.
    """
    s = slp1_text
    # 1. Punctuation & editorial markers
    s = s.replace("j[~]n", "jY").replace("[~]n", "Y")
    s = s.replace("[\x7f][\x7f]", "M").replace("[\x7f]", "M")
    s = re.sub(r"(?<=[A-Za-z/\\])\[ \](?=[A-Za-z/\\])", "M", s)
    s = s.replace("[_]", " ")
    # Strip editorial bracketed tags while keeping surrounding letters intact
    s = re.sub(r"\[\[?,?\]\]?|\[(?:\\\[|\\\]|[?@!;:.~]|\s+)\]|\\\[|\\\]|\[[{}]\]|\[[()]\]:?", "", s)
    s = re.sub(r"[{}()@*~]", "", s)

    # 2. Accented TITUS SLP1 repairs (ONLY for accented texts TB, TA1, TA4, TA5)
    if accented:
        # Protect genuine long-r stems before converting remaining plain F -> f/
        s = _SL_LONG_R_RE.sub(r"\1" + _SL_GENUINE_LONG_R_PLACEHOLDER, s)
        s = re.sub(r"F(?![/\\])", "f/", s)
        s = s.replace(_SL_GENUINE_LONG_R_PLACEHOLDER, "F")

        # Split accented diphthongs a/i -> E/, a/u -> O/ (hiatus was separated by [_] -> space)
        s = (s
             .replace("a/i", "E/")
             .replace("a\\i", "E\\")
             .replace("a/u", "O/")
             .replace("a\\u", "O\\"))

    # 3. Danda normalization before transliteration: '..' / '.' inside unit body -> ' । '
    # Note: Keep '॥ ... ॥' exclusively for trailing canonical citation markers so
    # pronunciation `_VERSE_MARKER` (`॥[^॥]*॥`) never spans across internal text.
    s = re.sub(r"\.\.+", " \uE012 ", s)
    s = re.sub(r"\.", " \uE012 ", s)
    # Remove stray ASCII punctuation not part of SLP1/accents
    s = re.sub(r"[\",;:!?=+\[\]<>_-]", " ", s)
    s = fix_slp1_ascii_visarga(s)
    s = re.sub(r"\s+", " ", s).strip()

    dev = convert_to_devanagari(s, "slp1")
    dev = (dev
           .replace("\uE011", "॥")
           .replace("\uE012", "।"))
    # Tighten space before dandas while keeping clean word spacing
    dev = re.sub(r"\s+([।॥])", r" \1", dev)
    dev = re.sub(r"\s+", " ", dev).strip()
    return dev


def convert_itrans_ta_to_devanagari(itrans_text: str) -> str:
    """Convert accented `sanskritdocuments.org` Taittirīya Āraṇyaka ITRANS to Devanāgarī.

    Maps:
      - `\\'` -> udātta / svarita (`\\u0951` `॑`)
      - ``\\``` -> anudātta (`\\u0952` `॒`)
      - `\\"` -> dīrgha-svarita (`\\u1CDA` `᳚`)
      - `{\\m+}` (and optional kampa digit `2`/`3` before `{\\m+}`) -> anusvāra `M` (`ं`)
      - `|` / `||` inside body -> `।` (never `॥`, reserved for trailing citations)
    """
    from indic_transliteration import sanscript

    s = itrans_text
    # Normalize Taittirīya anusvāra + optional kampa digit 2/3, plus (4) in o(4)m
    s = s.replace("{\\m+}", "M")
    s = s.replace("o(4)m", "om").replace("o(3)m", "om")
    s = re.sub(r"\([^)]*\)", " ", s)
    # Protect ITRANS Vedic accent escapes BEFORE sanscript (strip duplicate adjacent marks too)
    s = s.replace('\\"', _PUA_SVARITA).replace("\\'", _PUA_UDATTA).replace("\\`", _PUA_ANUDATTA)
    s = re.sub(r"([aAiIuUReEoO])([" + _PUA_UDATTA + _PUA_ANUDATTA + _PUA_SVARITA + r"]?)[23]M", r"\1\2M", s)
    # Strip editorial TeX/commentary fragments & leading kaṇḍikā numbers
    s = s.replace("\\.h", "").replace("#", " ")
    s = re.sub(r"\|+", " \uE012 ", s)
    s = re.sub(r"\s+", " ", s).strip()

    dev = sanscript.transliterate(s, sanscript.ITRANS, sanscript.DEVANAGARI)
    dev = (
        dev.replace(_PUA_UDATTA, "\u0951")
        .replace(_PUA_ANUDATTA, "\u0952")
        .replace(_PUA_SVARITA, "\u1CDA")
        .replace("\uE012", "।")
    )
    # Collapse duplicate identical accent marks on the same syllable (e.g. सुवर्ण॒ं॒ -> सुवर्ण॒ं)
    dev = re.sub(r"([\u0951\u0952\u1CDA])\1+", r"\1", dev)
    dev = re.sub(r"\s+([।॥])", r" \1", dev)
    dev = re.sub(r"\s+", " ", dev).strip()
    return dev


# ── Canonical Corpus Registry (Layers 1–5) ───────────────────────────────────

@dataclass(frozen=True)
class CorpusSpec:
    prefix: str                 # Canonical display/marker prefix, e.g. "AVŚ", "BŚS", "BĀU"
    norm_code: str              # ASCII-normalized exclusion key, e.g. "AVS", "BSS", "BAU"
    veda: str                   # Qdrant payload `metadata.veda`
    display_name: str           # Human-readable UI label
    local_relpath: str          # Path under local_store/ (may contain {k:02d})
    levels: int                 # Typical numeric depth (2, 3, or 4)
    chronology_layer: int       # 1..5
    chronology_name: str        # early_rigveda | late_rigveda | av_samhita | yv_samhita | samhita | brahmana_prose | sutra_vedanga
    source_type: str = "vedic_text"  # "vedic_text" or "commentary" (Nirukta)
    chronology_note: Optional[str] = None
    colliding_abbr: bool = False     # True if bare abbreviation collides with English (MS, KS, TA, GB, JB, TB, ChU, VS)


CORPUS_SPECS: Tuple[CorpusSpec, ...] = (
    # Existing 7 corpora
    CorpusSpec("RV",   "RV",   "rigveda",                   "Ṛgveda Saṃhitā",               "r{k:02d}/r{k:02d}.md", 3, 1, "early_rigveda"),
    CorpusSpec("AVŚ",  "AVS",  "atharvaveda_shaunaka",      "Atharvaveda (Śaunaka)",        "avs/avs.md",           3, 3, "av_samhita"),
    CorpusSpec("VS",   "VS",   "vajasaneyi_samhita",        "Vājasaneyi Saṃhitā",           "yv/yv.md",             2, 2, "samhita", colliding_abbr=True),
    CorpusSpec("TS",   "TS",   "taittiriya_samhita",        "Taittirīya Saṃhitā",           "ts/ts.md",             4, 2, "samhita"),
    CorpusSpec("AB",   "AB",   "aitareya_brahmana",         "Aitareya Brāhmaṇa",            "ab/ab.md",             3, 4, "brahmana_prose"),
    CorpusSpec("PB",   "PB",   "pancavimsa_brahmana",       "Pañcaviṃśa Brāhmaṇa",          "pb/pb.md",             3, 4, "brahmana_prose"),
    CorpusSpec("SB",   "SB",   "shatapatha_brahmana",       "Śatapatha Brāhmaṇa",           "sb/sb_{k:02d}.md",     4, 4, "brahmana_prose"),
    # Tranche 1 (GRETIL)
    CorpusSpec("MS",   "MS",   "maitrayani_samhita",        "Maitrāyaṇī Saṃhitā",           "ms/ms.md",             3, 3, "yv_samhita", colliding_abbr=True),
    CorpusSpec("AVP",  "AVP",  "atharvaveda_paippalada",    "Atharvaveda (Paippalāda)",     "avp/avp.md",           3, 3, "av_samhita"),
    CorpusSpec("KB",   "KB",   "kausitaki_brahmana",        "Kauṣītaki Brāhmaṇa",           "kb/kb.md",             3, 4, "brahmana_prose"),
    CorpusSpec("GB",   "GB",   "gopatha_brahmana",          "Gopatha Brāhmaṇa",             "gb/gb.md",             3, 4, "brahmana_prose", chronology_note="late Brāhmaṇa", colliding_abbr=True),
    CorpusSpec("BĀU",  "BAU",  "brihadaranyaka_upanisad",   "Bṛhadāraṇyaka Upaniṣad (Kāṇva)", "bau/bau.md",         3, 4, "brahmana_prose"),
    CorpusSpec("ChU",  "CHU",  "chandogya_upanisad",        "Chāndogya Upaniṣad",           "chu/chu.md",           3, 4, "brahmana_prose", colliding_abbr=True),
    CorpusSpec("Nir",  "NIR",  "nirukta",                   "Nirukta (Yāska — commentary)", "nir/nir.md",           2, 5, "sutra_vedanga", source_type="commentary"),
    # Tranche 2 (Sanskrit Library / TITUS)
    CorpusSpec("BŚS",  "BSS",  "baudhayana_srauta_sutra",   "Baudhāyana Śrauta Sūtra",      "bss/bss.md",           2, 5, "sutra_vedanga"),
    CorpusSpec("KS",   "KS",   "kathaka_samhita",           "Kāṭhaka Saṃhitā",              "ks/ks.md",             2, 3, "yv_samhita", colliding_abbr=True),
    CorpusSpec("JB",   "JB",   "jaiminiya_brahmana",        "Jaiminīya Brāhmaṇa",           "jb/jb.md",             2, 4, "brahmana_prose", colliding_abbr=True),
    CorpusSpec("JUB",  "JUB",  "jaiminiya_upanisad_brahmana", "Jaiminīya Upaniṣad Brāhmaṇa", "jub/jub.md",          3, 4, "brahmana_prose"),
    CorpusSpec("TB",   "TB",   "taittiriya_brahmana",       "Taittirīya Brāhmaṇa",          "tb/tb.md",             4, 4, "brahmana_prose", colliding_abbr=True),
    CorpusSpec("TA",   "TA",   "taittiriya_aranyaka",       "Taittirīya Āraṇyaka (1–9)",    "ta/ta.md",             3, 4, "brahmana_prose", colliding_abbr=True),
    # Tranche 3 (provisional)
    CorpusSpec("KapS", "KAPS", "kapisthala_katha_samhita",  "Kapiṣṭhala-Kaṭha Saṃhitā",     "kaps/kaps.md",         2, 3, "yv_samhita"),
)

BY_VEDA: Dict[str, CorpusSpec] = {s.veda: s for s in CORPUS_SPECS}
BY_PREFIX: Dict[str, CorpusSpec] = {s.prefix: s for s in CORPUS_SPECS}

# Case-insensitive alias map -> (canonical_display_prefix, norm_code)
ALIAS_TO_CANON: Dict[str, Tuple[str, str]] = {
    "rv": ("RV", "RV"), "rgveda": ("RV", "RV"), "rigveda": ("RV", "RV"), "ṛgveda": ("RV", "RV"),
    "avś": ("AVŚ", "AVS"), "avs": ("AVŚ", "AVS"), "av": ("AVŚ", "AVS"),
    "avp": ("AVP", "AVP"),
    "vs": ("VS", "VS"),
    "ts": ("TS", "TS"),
    "ms": ("MS", "MS"),
    "ks": ("KS", "KS"),
    "kaps": ("KapS", "KAPS"),
    "ab": ("AB", "AB"),
    "pb": ("PB", "PB"), "tmb": ("PB", "PB"),
    "sb": ("SB", "SB"), "śb": ("SB", "SB"), "śbm": ("SB", "SB"),
    "kb": ("KB", "KB"),
    "gb": ("GB", "GB"),
    "jb": ("JB", "JB"),
    "jub": ("JUB", "JUB"),
    "tb": ("TB", "TB"),
    "ta": ("TA", "TA"), "tā": ("TA", "TA"),
    "bāu": ("BĀU", "BAU"), "bau": ("BĀU", "BAU"), "bṛu": ("BĀU", "BAU"),
    "chu": ("ChU", "CHU"), "cu": ("ChU", "CHU"),
    "bśs": ("BŚS", "BSS"), "bss": ("BŚS", "BSS"), "baudhśs": ("BŚS", "BSS"),
    "nir": ("Nir", "NIR"), "nirukta": ("Nir", "NIR"),
}

# Longest-first alternation for regex matching (diacritic-aware, case-insensitive)
_PREFIX_ALT = "|".join(
    sorted(
        (re.escape(k) for k in ALIAS_TO_CANON if len(k) <= 7),
        key=len,
        reverse=True,
    )
)

CITATION_RE = re.compile(
    rf"(?<![A-Za-z0-9_ĀāĪīŪūṚṛŚśṢṣṬṭḌḍṆṇ])({_PREFIX_ALT})\.?\s*(\d+(?:\.\d+)+)",
    re.IGNORECASE,
)

# Double-daṇḍa marker inside corpus markdown / chunks:
# Matches both prefixed (`॥ MS 1.6.3 ॥`, `॥ BŚS 18.44 ॥`) and bare RV (`॥ 7.018.23 ॥`).
MARKER_CITATION_RE = re.compile(
    rf"॥\s*(?:(?P<prefix>{_PREFIX_ALT})\s+)?(?P<nums>\d+(?:\.\d+)+)\s*॥",
    re.IGNORECASE,
)


def canonicalize_prefix(raw: str) -> Tuple[str, str]:
    """Return (display_prefix, norm_code) for a raw corpus prefix."""
    key = unicodedata.normalize("NFC", raw).strip().lower()
    if key in ALIAS_TO_CANON:
        return ALIAS_TO_CANON[key]
    raise KeyError(f"Unknown corpus prefix: {raw!r}")


def parse_marker_citation(text: str) -> Optional[str]:
    """Extract the first canonical citation from a `॥ ... ॥` marker in `text`."""
    m = MARKER_CITATION_RE.search(text or "")
    if not m:
        return None
    raw_pre = m.group("prefix")
    nums = m.group("nums")
    if raw_pre:
        disp, _ = canonicalize_prefix(raw_pre)
        return f"{disp} {nums}"
    # Bare M.SSS.VV marker in rNN.md -> RV
    if nums.count(".") == 2:
        return f"RV {nums}"
    return None


def extract_citations(text: str) -> List[Tuple[str, Tuple[int, ...]]]:
    """Extract all (display_prefix, int_tuple) citations from `text`."""
    out: List[Tuple[str, Tuple[int, ...]]] = []
    for m in CITATION_RE.finditer(text or ""):
        disp, _ = canonicalize_prefix(m.group(1))
        parts = tuple(int(x) for x in m.group(2).split("."))
        out.append((disp, parts))
    return out


def format_citation(prefix: str, parts: Sequence[int]) -> str:
    disp, _ = canonicalize_prefix(prefix)
    return f"{disp} {'.'.join(str(int(x)) for x in parts)}"

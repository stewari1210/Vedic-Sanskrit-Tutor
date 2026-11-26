"""
Stored padapāṭha + morphology + lemma index for the Rigveda (local sidecars, no Qdrant).

Built by ingest_padapatha.py from the VedaWeb/Zurich glossed Rigveda (Lubotsky et al.,
CC-BY 4.0 — see NOTICE). Three roles:

  • padapatha_block(citation)   — prompt block with the stored padapāṭha and a per-token
                                  (form · lemma · tags) table for ONE RV verse, so the model
                                  analyses from stored data instead of re-splitting sandhi.
  • expand_terms(terms)         — lemma → inflected-form expansion for the Devanāgarī lexical
                                  rescue (e.g. पूरु → पूरवे), so inflected forms are reachable.
  • lemma_gloss_de(lemma)       — Zurich's German lemma gloss (stored; NOT injected in prompts).

Only the Rigveda is covered. Any other citation returns "" and the caller's behaviour is
unchanged. Load failures are logged loudly (never silent) and degrade to "no block".
"""
import json
import re
import threading
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

from src.helper import logger

_KS = Path(__file__).resolve().parent.parent.parent / "knowledge_store"
_FILES = {"pad": "padapatha_rv.json", "morph": "morphology_rv.json", "lem": "lemma_index_rv.json",
          # Phase-1 correction sidecars (all corpus-wide, rule-derived; optional):
          #   names — GAZETTEER proper-name flags (build_name_flags.py)
          #   lex   — lexicon rules L3 (pure name) / L1 (dual-sense)  (build_lexicon_flags.py)
          #   div   — rule R2 pada-vs-saṃhitā visarga divergence    (build_pada_samhita_divergence.py)
          "names": "proper_names_rv.json", "lex": "lexicon_names_rv.json",
          "div": "pada_samhita_divergence_rv.json"}
_CACHE: Dict[str, Optional[dict]] = {}
_LOCK = threading.Lock()
_RV_CITE = re.compile(r"\bRV\s*(\d+)\.(\d+)\.(\d+)\b", re.I)


def _lemkey(s: str) -> str:
    """Accent-stripped, lower, stem-marker-free lemma key (matches proper_names_rv.json)."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.split(r"[~/]", s)[0].strip()
    return s.strip("-").strip().replace(" ", "")


def _load(key: str) -> Optional[dict]:
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
        p = _KS / _FILES[key]
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"📖 padapāṭha sidecar loaded: {p.name}")
        except FileNotFoundError:
            logger.warning(f"📖 {p.name} not found — run ingest_padapatha.py (feature disabled)")
            data = None
        except Exception as e:
            logger.error(f"📖 FAILED to load {p.name}: {e} (feature disabled)")
            data = None
        _CACHE[key] = data
        return data


def verse_key(citation: str) -> Optional[str]:
    """'RV 7.018.23' / 'RV 7.18.23' → '7.018.23'; non-RV → None."""
    m = _RV_CITE.search(citation or "")
    if not m:
        return None
    a, b, c = (int(x) for x in m.groups())
    return "%d.%03d.%02d" % (a, b, c)


# ───────────────────────── prompt block ─────────────────────────

def _tags(t: dict) -> str:
    """Compact grammatical tags from a stored token (English codes; slashes = Zurich's own ambiguity)."""
    if t.get("lt") == "indecl":
        base = ["indecl."]
    elif t.get("t") or t.get("mo") or t.get("p"):
        # finite verb: tense.mood.voice person+number
        pn = (t.get("p", "").rstrip(".") + (t.get("nu", "") if t.get("p") else "")) if t.get("p") else t.get("nu", "")
        base = [x for x in (t.get("t"), t.get("mo"), t.get("vo")) if x] + ([pn] if pn else [])
    else:
        base = [x for x in (t.get("c"), t.get("nu"), t.get("g")) if x]
    extra = [t[k] for k in ("nf", "gr", "dr", "lp") if t.get(k)]
    if t.get("pc"):
        extra.append(f"pres.class {t['pc']}")
    if t.get("wv"):
        extra.append(t["wv"])
    out = ".".join(base) if base else (t.get("lt") or "")
    if t.get("lt") == "pronoun":
        out = ("pronoun " + out).strip()
    return (out + (" [" + "; ".join(extra) + "]" if extra else "")).strip()


def padapatha_block(citation: str) -> str:
    """Prompt-ready block for one RV verse; '' when not RV, not stored, or sidecars unavailable."""
    k = verse_key(citation)
    if not k:
        return ""
    pad, morph = _load("pad"), _load("morph")
    if not pad or not morph or k not in pad["verses"] or k not in morph["verses"]:
        return ""
    v = pad["verses"][k]
    names = _load("names") or {}
    lex = _load("lex") or {}
    div = (_load("div") or {}).get("by_token", {})
    name_always = names.get("always", {})
    lex_names = lex.get("name_lemmas", {})
    lex_local = lex.get("localised_name_lemmas", {})        # rule L3b: name sense valid only at cited verses
    lex_dual = lex.get("dual_sense_lemmas", {})             # rule L1: DISABLED (empty) since 2026-11-21
    lines = [
        f"STORED PADAPĀṬHA AND MORPHOLOGY — RV {k} (VedaWeb/Zurich, Lubotsky et al., CC-BY 4.0). "
        "These are STORED DATA from a manually annotated corpus. Rules: (a) use the padapāṭha forms "
        "below VERBATIM for word division — do NOT re-split the saṃhitā text or invent a different "
        "segmentation (if you think the padapāṭha is wrong, say so explicitly); (b) analyse each word "
        "FROM these tags (case/number/gender; tense/mood/voice/person) — do not re-derive them from "
        "scratch, and where the tags show a slash (e.g. dat./gen.) the annotators themselves record "
        "ambiguity, so present both options; (c) if your reading departs from a tag, say so and justify "
        "it from the grammar; (d) in your ANSWER write grammatical terms out in full words for a learner "
        "(e.g. 'aorist imperative active, 2nd person plural'), never the bare codes used in the table "
        "(aor., impv., 2pl, sg., pl.); (e) a trailing flag such as + = * ? ! on a form or lemma is the "
        "annotators' own marker, not part of the Sanskrit word. Accents are Lubotsky's. "
        "(f) A token marked «PROPER NAME: X» is a NAMED person/deity/people/place, NOT the literal "
        "meaning of its parts — read it as the name X, not as a common noun or adjective. "
        "(g) A token marked «ALT READING …» has an alternative to the stored tag (a lexicon "
        "name sense, or a different resolution of the saṃhitā sandhi) — present BOTH the stored "
        "reading and the alternative and mark the choice disputed; do not assert the stored tag "
        "as settled.",
        "Lubotsky pāda text: " + " | ".join(t for _, t in v["p"] if t),
        "Padapāṭha forms: " + re.sub(r"\s+[+=*?!]+(?=\s|$)", "", v["f"]),
        "Token table (n · padapāṭha form · lemma · tags):",
    ]
    for t in morph["verses"][k]:
        lem = t.get("l") or "?"
        extra = ""
        lk = _lemkey(lem)
        if lk in name_always and name_always[lk].get("contexts", {}).get("RV", True) is not False:
            extra += f"   «PROPER NAME: {name_always[lk]['name']}»"          # GAZETTEER (curated); skipped where
        elif lem in lex_names:                                              # its context says "not a name in RV"
            extra += f"   «PROPER NAME: {lex_names[lem]['title']}»"          # rule L3 (lexicon: pure name)
        elif lem in lex_local and k in lex_local[lem].get("verses", []):     # rule L3b: only at the cited verse(s)
            extra += f"   «PROPER NAME: {lex_local[lem]['title']}»"
        if lem in lex_dual:                                     # rule L1 (lexicon: name + common sense)
            extra += (f"   «ALT READING (lexicon, context decides): this lemma is also a proper name "
                      f"({lex_dual[lem]['title']}) besides its common sense»")
        d = div.get(f"{k}|{t['n']}")                            # rule R2 (pada vs saṃhitā)
        if d:
            nxt = f"before «{d['next_initial']}…»" if d.get("next_initial") else "at pāda end"
            alts = "; ".join(f"{a['form']} ({', '.join(a['lemmas'][:2])})" for a in d["alternatives"][:2])
            extra += (f"   «ALT READING (pada vs saṃhitā, disputed): the saṃhitā word {d['samhita_word']} "
                      f"{nxt} is regular sandhi for {alts}, not for this padapāṭha form — present both»")
        lines.append(f"  {t['n']}. {t.get('f', '?')} · {lem} · {_tags(t)}{extra}")
    return "\n".join(lines) + "\n"


# ───────────────────────── lemma expansion (lexical rescue) ─────────────────────────

def expand_terms(terms: List[str], max_per_lemma: int = 6, max_total: int = 12) -> List[str]:
    """Extra Devanāgarī search terms: other attested inflected forms of each term's lemma.

    Only forms that do NOT already contain a query term as a substring are returned — those that
    do are already caught by the substring scan; the added value is forms such as पूरवे for the
    stem पूरु. Returns [] (and logs) when the lemma index is unavailable.
    """
    lem = _load("lem")
    if not lem or not terms:
        return []
    f2l, l2f = lem["forms_to_lemmas"], lem["lemmas_to_forms"]
    base = [t.rstrip("्") for t in terms]
    out: List[str] = []
    seen = set(terms)
    for t in base:
        lemmas = []
        if t in l2f:
            lemmas.append(t)
        for form in (t, t + "म्"):
            lemmas += [x for x in f2l.get(form, []) if x not in lemmas]
        for lm in lemmas[:2]:
            added = 0
            for form in l2f.get(lm, []):
                if len(form) < 3 or form in seen or any(b and b in form for b in base):
                    continue
                seen.add(form)
                out.append(form)
                added += 1
                if added >= max_per_lemma or len(out) >= max_total:
                    break
            if len(out) >= max_total:
                break
    if out:
        logger.info(f"📖 lemma expansion: +{len(out)} inflected forms {out}")
    return out


def lemma_gloss_de(lemma: str) -> Optional[str]:
    lem = _load("lem")
    return (lem or {}).get("lemma_gloss_de", {}).get(lemma)

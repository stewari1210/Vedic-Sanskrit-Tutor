#!/usr/bin/env python3
"""Rule R2 — pada–saṃhitā VISARGA divergence detector.

FROZEN SPEC: docs/phase1_correction_rules.md (rule R2). Not to be edited after dev results
exist without listing the change in the report's "Post-freeze changes".

Idea: the padapāṭha resolves word-final sandhi; the saṃhitā surface may be regular for a
DIFFERENT resolution. Where the saṃhitā word is NOT a regular external-visarga-sandhi
surface of the padapāṭha form, but IS regular for another attested form of the same stem,
the stored tag is one resolution among two and we record the alternative.

Writes knowledge_store/pada_samhita_divergence_rv.json (sidecar JSON only; no Qdrant).
Exclusions: G2 manifest loaded at runtime; excluded verses skipped at input; output
asserted clean (fails loudly).
"""
import collections
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.utils import exclusions as EX                       # noqa: E402

KS = ROOT / "knowledge_store"
OUT = KS / "pada_samhita_divergence_rv.json"
GOLD_HYMNS = {"1.063", "1.112", "1.184", "3.053", "4.042", "6.061", "7.018", "10.060"}  # FP-sample filter only

# ───────────────────────── normalisation ─────────────────────────

def strip_accents(s: str) -> str:
    """Strip Vedic accents but keep ś (= s + combining acute in NFD)."""
    out, base = [], ""
    for ch in unicodedata.normalize("NFD", s):
        if unicodedata.combining(ch):
            if ch in ("́", "̀", "̍") and base != "s":
                continue
            out.append(ch)
        else:
            base = ch
            out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def norm(s: str) -> str:
    s = strip_accents(s).lower().replace("ṁ", "ṃ").replace("m̐", "ṃ")
    return re.sub(r"[+=*?!|‖\-‑]", "", s).strip()


# ───────────────────────── visarga sandhi ─────────────────────────

FINAL_VOWELS = ("ai", "au", "r̥̄", "r̥", "ṝ", "ṛ", "ā", "ī", "ū", "a", "i", "u", "e", "o")
LENGTHEN = {"i": "ī", "u": "ū", "r̥": "r̥̄", "ṛ": "ṝ"}
ENDINGS = ("aiḥ", "auḥ", "aḥ", "āḥ", "iḥ", "īḥ", "uḥ", "ūḥ", "eḥ", "oḥ")
AVAGRAHA = ("'", "’", "ʼ", "ऽ")


def final_vowel(stem: str):
    for v in FINAL_VOWELS:
        if stem.endswith(v):
            return v
    return None


def initial_class(n):
    """Class of the next word's initial: pause|kp|c|ṭ|t|sib|a|vowel|cons."""
    if n is None or n == "":
        return "pause"
    if n[0] in AVAGRAHA:
        return "a"                                   # avagraha = elided a-
    c = n[0]
    if c in "kp":
        return "kp"
    if c == "c":
        return "c"
    if c == "ṭ":
        return "ṭ"
    if c == "t":
        return "t"
    if c in "śṣs":
        return "sib"
    if c == "a":
        return "a"
    if c in "āiīuūeo" or (c == "r" and n[1:2] == "̥") or c in "ṛṝ":
        return "vowel"
    return "cons"


def visarga_surfaces(P: str, N):
    """Regular external-sandhi surfaces of normalised padapāṭha form P (ends in ḥ) before
    next initial N. Returns None when P cannot be evaluated."""
    if not P.endswith("ḥ"):
        return None
    stem = P[:-1]
    V = final_vowel(stem)
    if V is None:
        return None
    base = stem[: -len(V)]
    cls = initial_class(N)
    S = set()
    if cls == "pause":
        S.add(P)
    elif cls == "kp":
        S.update({P, stem + "s"})                   # v2: the RV text writes -s before k/p (brahmaṇas pate)
    elif cls == "c":
        S.add(stem + "ś")
    elif cls == "ṭ":
        S.add(stem + "ṣ")
    elif cls == "t":
        S.add(stem + "s")
    elif cls == "sib":
        S.update({stem + (N[0] if N else "s"), P})
    else:                                           # voiced consonant or vowel
        if V == "a":
            S.add(base + ("o" if cls in ("cons", "a") else "a"))
        elif V == "ā":
            S.add(stem)
        else:
            S.add(stem + "r")
            if cls == "cons" and N and N[0] == "r":
                S.add(base + LENGTHEN.get(V, V))    # ḥ dropped, short vowel lengthened
        if P in ("saḥ", "eṣaḥ") and cls == "cons":
            S.add(stem)                             # sá / eṣá before consonants
    return S


# ───────────────────────── alignment ─────────────────────────

def match(P: str, S: str) -> bool:
    if not P or not S or abs(len(P) - len(S)) > 3:
        return False
    if min(len(P), len(S)) < 3:
        return P[0] == S[0]
    k = min(len(P), len(S)) - 2
    return P[:k] == S[:k]


def align(T, W):
    """Greedy ±1-lookahead alignment of token forms T to saṃhitā words W (both normalised)."""
    pairs, i, j = [], 0, 0
    while i < len(T) and j < len(W):
        if match(T[i], W[j]):
            pairs.append((i, j)); i += 1; j += 1
        elif j + 1 < len(W) and match(T[i], W[j + 1]):
            j += 1
        elif i + 1 < len(T) and match(T[i + 1], W[j]):
            i += 1
        else:
            i += 1; j += 1
    return pairs


def samhita_words(p_lines):
    """-> [(orig, norm, next_word_norm_or_None)].

    v2 (pre-dev revision, diagnosed on non-gold verses): in Lubotsky's text sandhi is applied
    ACROSS pāda boundaries. The next initial is None (pausa / no sandhi) only
      (a) before a half-verse/verse marker '|' or '‖', and
      (b) after a word ending in '-' (sandhi suspended at the pāda boundary: hiatus, visarga kept).
    A pāda-final word with neither is followed by the first word of the next pāda."""
    lines = [[w for w in t.split() if w != "/"] for _, t in p_lines]
    words = []
    for li, toks in enumerate(lines):
        for wi, w in enumerate(toks):
            if w in ("|", "‖"):
                continue
            if w.endswith("-"):
                nxt = None                           # sandhi suspended
            elif wi + 1 < len(toks):
                nxt = None if toks[wi + 1] in ("|", "‖") else (norm(toks[wi + 1]) or None)
            else:                                    # last token of the pāda line, no marker
                nxt = None
                if li + 1 < len(lines):
                    first = [x for x in lines[li + 1] if x not in ("|", "‖")]
                    nxt = (norm(first[0]) or None) if first else None
            words.append((w, norm(w), nxt))
    return words


def implied_alternatives(P: str, S: str, N, attested):
    """Other padapāṭha endings whose regular surface equals S AND whose form is attested."""
    V = final_vowel(P[:-1])
    if V is None:
        return []
    core = P[: -1 - len(V)]
    out = []
    for e in ENDINGS:
        Pp = core + e
        if Pp == P:
            continue
        E = visarga_surfaces(Pp, N)
        if E and S[1:] in {x[1:] for x in E}:
            lem = attested(Pp)
            if lem:
                out.append({"form": Pp, "lemmas": lem})
    return out


def main():
    from indic_transliteration import sanscript
    units = EX.load_excluded_units()
    pad = json.loads((KS / "padapatha_rv.json").read_text(encoding="utf-8"))["verses"]
    morph = json.loads((KS / "morphology_rv.json").read_text(encoding="utf-8"))["verses"]
    f2l = json.loads((KS / "lemma_index_rv.json").read_text(encoding="utf-8"))["forms_to_lemmas"]

    def to_dev(x):
        x = x.replace("r̥̄", "ṝ").replace("r̥", "ṛ")
        return sanscript.transliterate(x, sanscript.IAST, sanscript.DEVANAGARI)

    def attested(form):
        lem = f2l.get(to_dev(form))
        return [sanscript.transliterate(l, sanscript.DEVANAGARI, sanscript.IAST) for l in lem[:3]] if lem else None

    st = collections.Counter()
    entries = {}
    detail = {}
    for vk, toks in morph.items():
        if EX.rv_verse_is_excluded(vk, units):
            st["verses_skipped_excluded"] += 1
            continue
        if vk not in pad:
            continue
        st["verses"] += 1
        T = [norm(re.sub(r"\s+[+=*?!]+$", "", t.get("f", ""))) for t in toks]
        W = samhita_words(pad[vk]["p"])
        pairs = align(T, [w[1] for w in W])
        st["tokens"] += len(T)
        st["aligned"] += len(pairs)
        for i, j in pairs:
            P, S, N = T[i], W[j][1], W[j][2]
            if not P.endswith("ḥ") or len(P) < 5:
                continue
            core = P[1:-3]
            if not S[1:].startswith(core) or len(S) - len(core) - 1 > 4:
                st["visarga_core_mismatch"] += 1
                continue
            E = visarga_surfaces(P, N)
            if E is None:
                st["visarga_unparsed"] += 1
                continue
            st["visarga_evaluated"] += 1
            if S[1:] in {e[1:] for e in E}:
                st["regular"] += 1
                continue
            st["irregular"] += 1
            alts = implied_alternatives(P, S, N, attested)
            if not alts:
                st["irregular_no_attested_alt"] += 1
                continue
            key = f"{vk}|{toks[i]['n']}"
            entries[key] = {"padapatha_form": toks[i].get("f"), "samhita_word": W[j][0],
                            "next_initial": (N[0] if N else None), "alternatives": alts}
            detail[key] = (W[j][0], P, N, alts, pad[vk]["p"])

    EX.assert_none_excluded(entries.keys(), "pada_samhita_divergence_rv", units)      # fail loud
    out = {"_meta": {"built_by": "build_pada_samhita_divergence.py", "spec": "docs/phase1_correction_rules.md",
                     "rule": "R2 visarga pada-vs-saṃhitā divergence with attested implied alternative",
                     "excluded_units_loaded": [f"{c} {'.'.join(map(str, u))}" for c, u in units],
                     "stats": dict(st), "entries": len(entries)},
           "by_token": entries}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("RULE R2 stats:", dict(st))
    cov = 100 * st["aligned"] / max(1, st["tokens"])
    print(f"alignment coverage: {cov:.1f}% of tokens | visarga evaluated: {st['visarga_evaluated']} | "
          f"regular: {st['regular']} | irregular: {st['irregular']} | ENTRIES ADDED (irregular + attested alt): {len(entries)}")
    rng = random.Random(20261121)
    pool = [k for k in entries if ".".join(k.split("|")[0].split(".")[:2]) not in GOLD_HYMNS]
    print(f"\n── FP sample, R2 (15 of {len(pool)} non-gold entries) ──")
    for k in rng.sample(pool, min(15, len(pool))):
        Sw, P, N, alts, plines = detail[k]
        line = next((t for _, t in plines if Sw in t), "")
        print(f"  RV {k}  pada={entries[k]['padapatha_form']}  saṃhitā={Sw}  next={N[:3] if N else 'pausa'}"
              f"  alt={[(a['form'], a['lemmas'][:2]) for a in alts]}\n       line: {line}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Rules L3 (lexicon proper-name flag) and L1 (dual-sense lexicon alternative).

FROZEN SPEC: docs/phase1_correction_rules.md. This script must not be edited after dev
results exist without listing the change in the report's "Post-freeze changes".

Writes knowledge_store/lexicon_names_rv.json — sidecar JSON only, no Qdrant writes.

Source: the Zurich glossary (`lemma_gloss_de` in lemma_index_rv.json). The glosses are
NOT injected into prompts (existing design); only the flags derived here are.

Exclusions: loads the G2 manifest at runtime (src/utils/exclusions.py), skips excluded
verses at input, and asserts at output (fails loudly on any violation).
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
from src.utils import exclusions as EX                      # noqa: E402
from src.utils.padapatha import _lemkey                     # noqa: E402

# Owner decision 2026-11-21: L1 (dual-sense alternative) is DISABLED — its false-positive check found
# 0/15 hits that fit their context. The rule is still classified and counted (for the record), but
# nothing is written to the sidecar's `dual_sense_lemmas` and nothing is rendered. No frequency guard.
ENABLE_L1 = False

KS = ROOT / "knowledge_store"
MORPH, LEMIDX, NAMES = KS / "morphology_rv.json", KS / "lemma_index_rv.json", KS / "proper_names_rv.json"
OUT = KS / "lexicon_names_rv.json"

# Gold (dev) hymns: used ONLY to keep false-positive samples outside them.
GOLD_HYMNS = {"1.063", "1.112", "1.184", "3.053", "4.042", "6.061", "7.018", "10.060"}

HEADS = ["Königs", "Fürsten", "Mannes", "Sängers", "Dichters", "Weisen", "Sehers", "Priesters",
         "Opferpriesters", "Opferers", "Opferherrn", "Spenders", "Schenkers", "Schützlings",
         "Günstlings", "Patrons", "Vaters", "Gottes", "Gottheit", "Göttin", "Dämons", "Feindes",
         "Wesens", "Frau", "Flusses", "Volkes", "Volksstammes", "Stammes", "Stammeshelden",
         "Familie", "Priestergeschlechts", "Bharatiden", "Aṅgiras", "Örtlichkeit", "Berges",
         "Landes", "Indra-Freunden", "R̥ṣi", "Ṛṣi"]
NAME_RE = re.compile(
    r"N\. ?pr\.|Eigenname|Personenname|Frauenname|Stammesname|Volksname|Flussname"
    r"|\bName (?:eines|einer|des|der)\s+(?:[^\s,;()]+\s+){0,2}?(?:%s)(?![\wāīūṛṣśṭḍṇñṅṃḥ])"
    % "|".join(re.escape(h) for h in HEADS))
HEDGE_RE = re.compile(r"\b(?:unklar|unsicher|vielleicht|wohl|mögl|möglicherweise|evtl|eventuell"
                      r"|fraglich|vermutlich|angeblich)\b|\?")
IGNORE_RE = re.compile(r"^\s*(?:\(|\[|<|\*|unklar|unsicher|wohl\b|vielleicht|etwa\b|entweder"
                       r"|Br\.|vgl\.|cf\.|s\.\s)")


def split_senses(gloss: str):
    """Cut at top-level ';' (not inside () or [])."""
    out, depth, cur = [], 0, ""
    for ch in gloss:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == ";" and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


# v2 (pre-dev revision): a verse locator such as '5.44.11', '8.1.34', '5. 44.11' marks a
# VERSE-LOCALISED sense ("in 5.30.14 … Name eines Sängers"): it must not be applied to every
# token of the lemma.
LOCATOR_RE = re.compile(r"\b\d{1,2}\.\s?\d{1,3}(?:\.\d{1,3})?\b")


def classify_sense(sense: str) -> str:
    if NAME_RE.search(sense):
        if LOCATOR_RE.search(sense):
            # v3 (owner-adopted L3b amendment): a verse-localised name sense is usable AT the cited
            # verse(s) when it is firm; hedged localised senses are still dropped.
            return "NAME_LOCAL_HEDGED" if HEDGE_RE.search(sense) else "NAME_LOCAL_FIRM"
        return "NAME_HEDGED" if HEDGE_RE.search(sense) else "NAME_FIRM"
    if IGNORE_RE.search(sense):
        return "IGN"
    return "APP"


LOCAL_CLASSES = ("NAME_LOCAL_FIRM", "NAME_LOCAL_HEDGED")
VERSE_REF_RE = re.compile(r"(?<!\d)(\d{1,2})\.\s?(\d{1,3})\.\s?(\d{1,3})(?!\d)")


def firm_local_loci(gloss: str):
    """Verse keys ('M.SSS.VV', as in morphology_rv.json) cited by the FIRM verse-localised name
    senses of a gloss. Also returns the number of firm-localised senses with NO 3-component
    locator (hymn-level / malformed) — counted, never applied."""
    loci, unparsed = [], 0
    for sense in split_senses(gloss):
        if classify_sense(sense) != "NAME_LOCAL_FIRM":
            continue
        refs = ["%d.%03d.%02d" % tuple(int(x) for x in m.groups()) for m in VERSE_REF_RE.finditer(sense)]
        if refs:
            loci += [r for r in refs if r not in loci]
        else:
            unparsed += 1
    return loci, unparsed


def classify_gloss(gloss: str) -> str:
    """v2 first-sense primacy (unchanged) + v3 L3b.

    L3  — the FIRST substantive sense is a firm, unlocalised name -> proper name everywhere.
    L1  — FIRST sense appellative and a LATER sense is a firm unlocalised name (DISABLED for
          rendering by owner decision 2026-11-21: 0/15 hits fit their context; still counted).
    L3B — (v3) not L3, but a FIRM verse-localised name sense exists -> name flag at the cited
          verse(s) ONLY (applied token-by-token in main()).
    DROP_HEDGED / DROP_LOCAL — only hedged / hedged-localised name senses: counted, never rendered.
    """
    cls = [classify_sense(s) for s in split_senses(gloss)]
    subst = [c for c in cls if c not in ("IGN",) + LOCAL_CLASSES]    # localised names don't set the primary sense
    if subst:
        first, rest = subst[0], subst[1:]
        if first == "NAME_FIRM":
            return "L3"
        if first == "APP" and "NAME_FIRM" in rest:
            return "L1"
    if "NAME_LOCAL_FIRM" in cls:
        return "L3B"
    if "NAME_LOCAL_HEDGED" in cls:
        return "DROP_LOCAL"
    if "NAME_HEDGED" in cls:
        return "DROP_HEDGED"
    return "NONE"


def title_of(lemma: str) -> str:
    """Lemma -> display name. Strips vowel accents but keeps ś (= s + combining acute)."""
    out, base = [], ""
    for ch in unicodedata.normalize("NFD", lemma):
        if unicodedata.combining(ch):
            if ch in ("́", "̀", "̍") and base != "s":
                continue                      # vowel accent
            out.append(ch)
        else:
            base = ch
            out.append(ch)
    s = unicodedata.normalize("NFC", "".join(out))
    s = re.split(r"[~/]", s)[0].strip().strip("-").strip()
    return s[:1].upper() + s[1:]


def main():
    units = EX.load_excluded_units()                                   # fails loudly if absent
    morph = json.loads(MORPH.read_text(encoding="utf-8"))["verses"]
    gloss = json.loads(LEMIDX.read_text(encoding="utf-8"))["lemma_gloss_de"]
    gaz = set(json.loads(NAMES.read_text(encoding="utf-8")).get("always", {})) if NAMES.exists() else set()

    klass = {lem: classify_gloss(g) for lem, g in gloss.items()}
    print("gloss classes (all 10,031 lemmas):", dict(collections.Counter(klass.values())))

    # L3b candidates: any lemma that is NOT a global L3 name but has a FIRM verse-localised name sense.
    local_cand, unparsed_senses = {}, 0
    for lem, g in gloss.items():
        if klass[lem] == "L3":
            continue
        loci, unp = firm_local_loci(g)
        unparsed_senses += unp
        if loci:
            local_cand[lem] = loci
    n_loci_total = sum(len(v) for v in local_cand.values())

    occ = collections.defaultdict(list)            # lemma -> [(verse, n, form)] (L3 / L1) in NON-excluded verses
    occ_local = collections.defaultdict(list)      # lemma -> tokens AT a cited locus (L3b)
    skipped_verses = 0
    for vk, toks in morph.items():
        if EX.rv_verse_is_excluded(vk, units):
            skipped_verses += 1
            continue
        for t in toks:
            lem = t.get("l")
            if not lem:
                continue
            if klass.get(lem) in ("L3", "L1"):
                occ[lem].append((vk, t["n"], t.get("f", "")))
            if lem in local_cand and vk in local_cand[lem]:
                occ_local[lem].append((vk, t["n"], t.get("f", "")))
    print(f"excluded verses skipped at input: {skipped_verses}")

    name_lemmas, dual_lemmas, covered_by_gaz = {}, {}, {}
    for lem, hits in occ.items():
        entry = {"title": title_of(lem), "tokens": len(hits)}
        if klass[lem] == "L3":
            if _lemkey(lem) in gaz:
                covered_by_gaz[lem] = entry
            else:
                name_lemmas[lem] = entry
        else:
            dual_lemmas[lem] = entry                # counted for the record; written only if ENABLE_L1

    # L3b: token-level, only at the verse(s) the glossary itself cites
    localised, loc_in_gaz = {}, 0
    loci_in_excluded = sum(1 for loci in local_cand.values() for v in loci if EX.rv_verse_is_excluded(v, units))
    for lem, hits in occ_local.items():
        if _lemkey(lem) in gaz:
            loc_in_gaz += 1
            continue
        verses = sorted({v for v, _, _ in hits})
        localised[lem] = {"title": title_of(lem), "verses": verses, "tokens": len(hits)}
    loci_without_token = sum(1 for lem, loci in local_cand.items()
                             for v in loci if not EX.rv_verse_is_excluded(v, units)
                             and v not in {h[0] for h in occ_local.get(lem, [])})

    # ── fail-loud output check ──
    all_hits = [h for lem in list(name_lemmas) + list(dual_lemmas) for h in occ[lem]] \
        + [h for lem in localised for h in occ_local[lem]]
    EX.assert_none_excluded([f"{v}|{n}" for v, n, _ in all_hits], "lexicon_names_rv hits", units)
    EX.assert_none_excluded([v for e in localised.values() for v in e["verses"]], "lexicon_names_rv localised verses", units)

    written_dual = dual_lemmas if ENABLE_L1 else {}
    out = {"_meta": {"built_by": "build_lexicon_flags.py", "spec": "docs/phase1_correction_rules.md",
                     "rules": {"L3": "pure firm name per Zurich glossary (first-sense primacy)",
                               "L3b": "firm VERSE-LOCALISED name sense, applied only at the cited verse(s) "
                                      "(owner-adopted 2026-11-21, after a gold outcome was seen)",
                               "L1": "DISABLED by owner decision 2026-11-21 (0/15 hits fit their context)"},
                     "l1_enabled": ENABLE_L1,
                     "excluded_units_loaded": [f"{c} {'.'.join(map(str, u))}" for c, u in units],
                     "name_lemmas": len(name_lemmas), "name_tokens": sum(e["tokens"] for e in name_lemmas.values()),
                     "l3_already_in_gazetteer": len(covered_by_gaz),
                     "localised_name_lemmas": len(localised),
                     "localised_verses": sum(len(e["verses"]) for e in localised.values()),
                     "localised_tokens": sum(e["tokens"] for e in localised.values()),
                     "l1_would_be_lemmas": len(dual_lemmas),
                     "l1_would_be_tokens": sum(e["tokens"] for e in dual_lemmas.values())},
           "name_lemmas": name_lemmas, "localised_name_lemmas": localised, "dual_sense_lemmas": written_dual}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    m = out["_meta"]
    print(f"\nRULE L3  (pure-name flag):    {m['name_lemmas']} lemmas -> {m['name_tokens']} tokens flagged "
          f"(+{m['l3_already_in_gazetteer']} L3 lemmas already covered by the GAZETTEER)")
    print(f"RULE L3b (localised name):    {m['localised_name_lemmas']} lemmas, {m['localised_verses']} verse loci, "
          f"{m['localised_tokens']} tokens flagged")
    print(f"   L3b bookkeeping: candidate lemmas={len(local_cand)} | cited loci={n_loci_total} | loci inside G2-excluded "
          f"verses (dropped)={loci_in_excluded} | loci with no matching token={loci_without_token} | "
          f"already in GAZETTEER={loc_in_gaz} | firm-localised senses with no 3-part locator={unparsed_senses}")
    print(f"RULE L1  DISABLED:            would have been {m['l1_would_be_lemmas']} lemmas / {m['l1_would_be_tokens']} tokens "
          f"(nothing written)")

    # ── false-positive samples: 15 hits, outside gold hymns & excluded units ──
    rng = random.Random(20261121)

    def hit_pool(lemmas, source):
        return [(lem,) + h for lem in lemmas for h in source[lem]
                if ".".join(h[0].split(".")[:2]) not in GOLD_HYMNS]

    pool = hit_pool(name_lemmas, occ)
    print(f"\n── FP sample, L3 proper-name flag (15 of {len(pool)} non-gold hits) ──")
    for lem, vk, n, form in rng.sample(pool, min(15, len(pool))):
        print(f"  RV {vk} #{n}  {form}  ({lem})  :: {gloss[lem][:140]}")

    dpool = sorted(l for l in name_lemmas if any(".".join(h[0].split(".")[:2]) not in GOLD_HYMNS for h in occ[l]))
    print(f"\n── supplementary DISTINCT-LEMMA sample, L3 (15 of {len(dpool)}) ──")
    for lem in rng.sample(dpool, min(15, len(dpool))):
        print(f"  {lem}  ->  {name_lemmas[lem]['title']}  :: {gloss[lem][:130]}")

    lpool = hit_pool(localised, occ_local)
    print(f"\n── FP sample, L3b localised name (15 of {len(lpool)} non-gold hits; "
          f"{'ALL shown' if len(lpool) <= 15 else 'random'}) ──")
    for lem, vk, n, form in rng.sample(lpool, min(15, len(lpool))):
        print(f"  RV {vk} #{n}  {form}  ({lem}) -> {localised[lem]['title']}  :: {gloss[lem][:150]}")
    gold_hits = [(lem,) + h for lem in localised for h in occ_local[lem]
                 if ".".join(h[0].split(".")[:2]) in GOLD_HYMNS]
    print(f"\n── L3b hits that fall in GOLD (dev) hymns — reported, NOT part of the FP sample ({len(gold_hits)}) ──")
    for lem, vk, n, form in gold_hits:
        print(f"  RV {vk} #{n}  {form}  ({lem}) -> {localised[lem]['title']}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()

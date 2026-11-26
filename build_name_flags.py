#!/usr/bin/env python3
"""Build knowledge_store/proper_names_rv.json — a per-token proper-name flag layer.

Why: judge cases G10/G11 showed every local model had the right morphology tag but
read `devávataḥ` (gen.sg.m. of devávant-) as the appellative "possessing gods"
instead of the PROPER NAME Devavat. The morphology sidecar has no "this lemma is a
name" signal, so the models can't know. This adds one.

Sources for the name set (sidecar JSON only, no Qdrant):
  * explicit seeds (the names called out in the judge analysis),
  * the GAZETTEER in src/utils/devanagari_lexical.py (curated name list),
  * the self-built KG entities (knowledge_store/vedic_relations.json), and
  * the anukramaṇī ṛṣi names (knowledge_store/anukramani_rv.json).
(Grassmann's proper-name entries aren't available locally; noted as a TODO source.)

Precision over recall: a few clearly-appellative / grammatically-ambiguous keys are
excluded from "always" flagging (dāsa/dasyu = enemy classes, not names; anu/puru
collide with the preposition ánu and the adjective purú). `devávant-` is flagged
CONTEXTUALLY (it is the adjective elsewhere), seeded at the patron verses.

Output: {"always": {lemma_key: {name, sources}}, "contextual": {"V|lemma_key": {...}},
         "_meta": {...}}.  padapatha.py consults it when rendering the token table.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

KS = Path(__file__).resolve().parent / "knowledge_store"
MORPH = KS / "morphology_rv.json"
KG = KS / "vedic_relations.json"
ANUKR = KS / "anukramani_rv.json"
GAZ_PY = Path(__file__).resolve().parent / "src" / "utils" / "devanagari_lexical.py"
OUT = KS / "proper_names_rv.json"

# Appellatives / grammatically-ambiguous keys kept OUT of "always".
EXCLUDE = {"dasa", "dasyu", "anu", "puru", "dasarajna", "dasharajna"}

# Context-dependent name flags (owner decision 2026-11-21). A GAZETTEER name that is a COMMON WORD in
# some corpora is flagged only where it is a name. `contexts` is stored on the sidecar entry and
# honoured by the renderer: the RV renderer skips an entry whose contexts["RV"] is False. The entry is
# NOT deleted: Rohita is a deity in AVŚ book 13, so a future AVŚ renderer (Phase 2) must flag it there.
# (In the RV, róhita- is the adjective 'red' / 'a red horse' — the Zurich glossary: "rot, rötlich;
# m. rotes Pferd".)
NAME_FLAG_CONTEXTS = {"rohita": {"RV": False, "AVŚ": {"books": [13]}}}

# PHASE-1 CORRECTION: the hand-picked SEEDS (names called out in the judge analysis) and
# the gold-seeded CONTEXTUAL devávant-@7.018.22 entry were REMOVED (contamination rule).
# Every name here now comes from the curated GAZETTEER alone, corpus-wide; contextual
# (per-verse) name entries no longer exist. Lexicon-driven names/alternatives are built
# by build_lexicon_flags.py (rules L1/L3), not here.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.utils import exclusions as EX  # noqa: E402  (fail-loud G2 exclusion loader)


def norm(s: str) -> str:
    """Accent-stripped, lower, no trailing stem markers — a stable lemma key."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.split(r"[~/]", s)[0].strip()          # 'gav- ~ go-' -> 'gav-'
    return s.strip("-").strip().replace(" ", "")


def load_gazetteer_keys():
    txt = GAZ_PY.read_text(encoding="utf-8")
    block = txt[txt.find("GAZETTEER = {"): txt.find("THEME_GAZETTEER")]
    return {norm(k) for k in re.findall(r'"([a-z_]+)":', block)}


def load_kg_names():
    ents = json.loads(KG.read_text(encoding="utf-8")).get("entities", {})
    out = {}
    for key, rec in ents.items():
        disp = (rec or {}).get("display_name") or key
        out[norm(key)] = disp
        out[norm(disp)] = disp
    return out


def load_anukr_names():
    hymns = json.loads(ANUKR.read_text(encoding="utf-8")).get("hymns", {})
    names = set()
    for h in hymns.values():
        for field in ("rishi", "devata"):
            for tok in re.split(r"[\s,/]+", str(h.get(field, ""))):
                if len(tok) > 3:
                    names.add(norm(tok))
    return names


def main():
    gaz = load_gazetteer_keys()
    kg = load_kg_names()
    anukr = load_anukr_names()

    # the "always" name-key -> (canonical name, sources)
    always = {}
    def add(key, name, src):
        if not key or key in EXCLUDE:
            return
        if key not in always:
            always[key] = {"name": name, "sources": []}
        if src not in always[key]["sources"]:
            always[key]["sources"].append(src)

    # Flag triggers: ONLY the hand-verified seeds + the curated GAZETTEER. The
    # self-built KG is too noisy to trigger a flag (it lists common nouns like
    # deva/yajña/stóma/ójas as "entities"), so it is used only to supply a canonical
    # display name for a lemma the GAZETTEER already flagged. anukramaṇī likewise is
    # recorded as a cross-reference, not a trigger.
    for k in gaz:
        add(k, kg.get(k, k.capitalize()), "gazetteer")
        if k in anukr:
            always.get(k, {}).get("sources", []).append("anukramani")

    # scan morphology: which lemmas actually occur (in NON-excluded verses), flag tokens
    units = EX.load_excluded_units()                      # fails loudly if manifest absent
    morph = json.loads(MORPH.read_text(encoding="utf-8"))["verses"]
    flagged_lemmas, flagged_tokens, examples = {}, 0, []
    gated_rv_tokens = {}
    for vk, toks in morph.items():
        if EX.rv_verse_is_excluded(vk, units):
            continue
        for t in toks:
            if t.get("lt") != "nominal":
                continue
            lk = norm(t.get("l", ""))
            if lk in always and NAME_FLAG_CONTEXTS.get(lk, {}).get("RV", True) is False:
                gated_rv_tokens[lk] = gated_rv_tokens.get(lk, 0) + 1     # would have been flagged; context says no
                continue
            if lk in always:
                flagged_tokens += 1
                flagged_lemmas.setdefault(lk, 0)
                flagged_lemmas[lk] += 1
                if len(examples) < 400:
                    examples.append((vk, t.get("f"), t.get("l"), always[lk]["name"],
                                     ",".join(always[lk]["sources"])))

    # keep only "always" entries that actually occur (prunes the 3k-entity KG noise)
    used = {k: v for k, v in always.items() if k in flagged_lemmas or k in NAME_FLAG_CONTEXTS}
    for k, ctx in NAME_FLAG_CONTEXTS.items():
        if k in used:
            used[k]["contexts"] = ctx
    # fail loud: this sidecar is lemma-level (no verse keys), but assert on the examples too
    EX.assert_none_excluded([e[0] for e in examples], "proper_names_rv examples", units)
    out = {"_meta": {"built_by": "build_name_flags.py",
                     "sources": ["gazetteer", "kg (display names only)", "anukramani (cross-ref)"],
                     "note": "Hand seeds and the gold-seeded contextual entry were removed "
                             "(Phase-1 correction). Grassmann entries not available locally (TODO).",
                     "always_lemmas": len(used), "flagged_tokens": flagged_tokens,
                     "context_gated": {k: {"contexts": NAME_FLAG_CONTEXTS[k], "rv_tokens_not_flagged": n}
                                       for k, n in gated_rv_tokens.items()}},
           "always": used, "contextual": {}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── report ──
    print(f"name-key sources: gazetteer={len(gaz)} "
          f"kg={len({k for k in kg})} anukramani={len(anukr)}")
    print(f"'always' lemmas that OCCUR in the RV: {len(used)}")
    print(f"tokens flagged (always): {flagged_tokens}")
    print(f"context-gated (RV off): {gated_rv_tokens}")
    # REPORT-ONLY: GAZETTEER names whose Zurich gloss does NOT begin with a name sense (cf. rohita)
    from build_lexicon_flags import classify_sense, split_senses
    gloss = json.loads((KS / "lemma_index_rv.json").read_text(encoding="utf-8"))["lemma_gloss_de"]
    by_key = {}
    for lem in gloss:
        by_key.setdefault(norm(lem), []).append(lem)
    odd = []
    for k in sorted(used):
        for lem in by_key.get(k, []):
            subst = [c for c in (classify_sense(x) for x in split_senses(gloss[lem])) if c != "IGN"]
            if not subst or not subst[0].startswith("NAME"):
                odd.append((k, lem, subst[0] if subst else "-", gloss[lem][:70]))
    print(f"GAZETTEER first-sense audit (report only): {len(odd)} of {len(used)} flagged names do not begin with a name sense:")
    for o in odd:
        print("   ", o)
    print(f"top flagged lemmas: "
          + ", ".join(f"{k}×{n}" for k, n in sorted(flagged_lemmas.items(),
                                                     key=lambda x: -x[1])[:12]))
    print("\n── spot-check 20 flagged tokens (verse · form · lemma → NAME [sources]) ──")
    import random
    random.seed(0)
    for vk, f, l, name, src in random.sample(examples, min(20, len(examples))):
        print(f"  RV {vk}  {f}  ({l})  → {name}  [{src}]")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()

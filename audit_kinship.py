#!/usr/bin/env python3
"""Rule K — corpus-wide kinship audit of proper_noun_variants.json.

FROZEN SPEC: docs/phase1_correction_rules.md (rule K). Whole-file audit; driven by the rule
only — no gold or G2 case is targeted. Default is a dry run (prints the audit table);
``--apply`` edits the file IN PLACE in the working tree (never stages/commits it: the owner
reviews the diff first).

Edits are SURGICAL text replacements on the raw file (the file keeps short lists on one line,
so a json re-dump would produce a noisy diff). Correctness is proven by parsing the edited
text and requiring it to equal the intended structure exactly (fails loudly otherwise).

Rule summary
  * kinship claim      : a string field (outside `variants` arrays and `_*` metadata) that
                         matches the kinship lexicon.
  * generation-count   : grandson/grandfather/…/great-grand*, son(s)/daughter(s)/father(s)/
                         mother(s)/brother(s)/sister(s)  ("X's son", "son of X", …).
  * BACKED             : the same field carries a citation that is ADMISSIBLE (not in a G2
                         excluded unit, not in a gold hymn) and the cited RV verse contains a
                         kinship lemma in the morphology sidecar.
  * UNBACKED Vedic     : relabel counts -> "descendant (patronymic)"; citations into G2
                         excluded units are REMOVED (with a parenthetical describing their
                         content); citations into gold hymns are kept bare, claim relabelled.
  * EPIC (Rāmāyaṇa)    : not a Vedic-corpus claim, cannot be "patronymic" -> annotated
                         "(itihāsa tradition, not attested in the Vedic corpus)". JUDGMENT CALL.
  * lineage-generic    : ancestor/lineage/dynasty/progenitor without a count -> listed, unchanged.
"""
import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.utils import exclusions as EX                                  # noqa: E402

FILE = ROOT / "proper_noun_variants.json"
MORPH = ROOT / "knowledge_store" / "morphology_rv.json"
GOLD_RV_HYMNS = {"1.063", "1.112", "1.184", "3.053", "4.042", "6.061", "7.018", "10.060"}
GOLD_OTHER_UNITS = [("SB", (13, 5, 4)), ("SB", (1, 4, 1)), ("AB", (7, 13))]

KIN = re.compile(r"\b(grand\w+|great-grand\w+|sons?|daughters?|fathers?|mothers?|brothers?|sisters?"
                 r"|nephews?|uncles?|ancestors?|descendants?|progenitors?|offspring|heirs?"
                 r"|lineage|dynasty)\b", re.I)
GEN = re.compile(r"\b(grand(?:son|father|mother|daughter|child|children)|great-grand\w+"
                 r"|sons?|daughters?|fathers?|mothers?|brothers?|sisters?)\b", re.I)
LINEAGE_STRONG = re.compile(r"\b(ancestors?|progenitors?|descendants?)\b", re.I)
EPIC = re.compile(r"\b(Rama|Ramayana|Ayodhya|Sita|Janaka|Lakshmana|Dasharatha)\b", re.I)
EPIC_NOTE = " (itihāsa tradition, not attested in the Vedic corpus)"
KIN_LEMMAS = {"putra", "sunu", "napat", "naptr", "napti", "pitr", "pitar", "matr", "matar",
              "bhratr", "bhratar", "svasr", "svasar", "duhitr", "duhitar", "tanaya", "putri", "jami"}
DEL = object()

# ── Owner-directed amendments (2026-11-21), recorded in docs/phase1_correction_rules.md ──
# K3: citations that point at the WRONG hymn are corrected — and VERIFIED against local_store
#     (the cited verses must be admissible: not G2-excluded, not gold) before being applied.
CITATION_FIXES = {
    "Srinjayas/key_references/0": {"from": "RV 10.60.4", "to": "RV 4.15.4",
                                   "verify": [("4.015.04", ["सृञ्जय", "दैववात"])]},
    "Somakas/key_references/0": {"from": "RV 10.60.9", "to": "RV 4.15.7–9",
                                 "verify": [("4.015.07", ["साहदेव्य"]), ("4.015.08", ["साहदेव्य"]),
                                            ("4.015.09", ["साहदेव्य", "सोमक"])]},
}
# K4: the Kuruśravaṇa–Trasadasyu lineage claim has a held-out unit (RV 10.33) as its ONLY source:
#     removed entirely (not relabelled), in every entry that carries it.
OWNER_REMOVE = {
    "Kurus/rigveda_lineage/early_references/1",
    "kings_and_heroes/Kurusravana/lineage",
    "kings_and_heroes/Trasadasyu/descendants",
}


def verify_local_store(verse_key: str, needles) -> str:
    """Read the verse from local_store/rNN/rNN.md and require every needle to be present."""
    mandala = int(verse_key.split(".")[0])
    f = ROOT / "local_store" / f"r{mandala:02d}" / f"r{mandala:02d}.md"
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.rstrip().endswith(f"॥ {verse_key} ॥"):
            missing = [n for n in needles if n not in line]
            if missing:
                raise RuntimeError(f"local_store RV {verse_key} lacks {missing}: citation fix NOT verified")
            return line
    raise RuntimeError(f"RV {verse_key} not found in {f}")


def apply_citation_fix(text: str, fix: dict, units) -> str:
    cit_new = EX.find_citations(fix["to"])[0]
    assert not any(EX._inside(cit_new, u) for u in units), "corrected citation is in a G2 excluded unit"
    assert not in_gold(cit_new), "corrected citation is in a gold hymn"
    for vk, needles in fix["verify"]:
        verify_local_store(vk, needles)
        print(f"  verified in local_store: RV {vk} contains {needles}")
    out = text.replace(fix["from"], fix["to"])
    return re.sub(r"^(RV [^:]+): '(.*)'$", r"\1: \2", out)       # no longer a quoted translation


def lemkey(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z]", "", s.replace("ṛ", "r").replace("ṝ", "r"))


def in_gold(cit) -> bool:
    corpus, comp = cit
    if corpus == "RV" and len(comp) >= 2 and "%d.%03d" % comp[:2] in GOLD_RV_HYMNS:
        return True
    return any(corpus == c and comp[: len(u)] == u for c, u in GOLD_OTHER_UNITS)


def verse_has_kin_lemma(cit, morph) -> bool:
    if cit[0] != "RV" or len(cit[1]) != 3:
        return False                                          # only RV verses are verifiable
    toks = morph.get("%d.%03d.%02d" % cit[1], [])
    return any(lemkey(t.get("l", "")) in KIN_LEMMAS for t in toks)


def relabel(t: str) -> str:
    def cap(m, new):
        return new[0].upper() + new[1:] if m.group(0)[0].isupper() else new
    t = re.sub(r"\bgrand(?:son|child)\b", lambda m: cap(m, "descendant (patronymic)"), t, flags=re.I)
    t = re.sub(r"\bson of\b", lambda m: cap(m, "descendant (patronymic) of"), t, flags=re.I)
    t = re.sub(r"(\w)'s son\b", r"\1's descendant (patronymic)", t, flags=re.I)
    return t


def strip_excluded_citations(t: str, units) -> str:
    """Remove citations into G2 excluded units (+ the parenthetical describing their content)."""
    out = t
    for m in list(EX._CIT.finditer(" " + t))[::-1]:
        cit = (EX._CORPUS_CODES[m.group(1)], tuple(int(x) for x in m.group(2).split(".")))
        if not any(EX._inside(cit, u) for u in units):
            continue
        s, e = m.start(1) - 1, m.end(2) - 1                    # offsets into t (we prepended a space)
        tail = re.match(r"\s*\([^)]*\)", out[e:])
        if s == 0 or not out[:s].strip():
            e += tail.end() if tail else 0                    # citation leads the field: drop its parenthetical too
            out = out[:s] + out[e:]
        else:
            before = re.search(r",\s*$", out[:s])
            out = out[: before.start() if before else s] + out[e:]
    return re.sub(r"\s+", " ", out).strip(" ,;:")


def walk(o, path, fn):
    if isinstance(o, dict):
        return {k: (v if (k.startswith("_") and not path) or k == "variants" else walk(v, path + [k], fn))
                for k, v in o.items()}
    if isinstance(o, list):
        return [walk(v, path + [i], fn) for i, v in enumerate(o)]
    return fn(path, o) if isinstance(o, str) else o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="edit the file in place (working tree only)")
    args = ap.parse_args()
    units = EX.load_excluded_units()
    morph = json.loads(MORPH.read_text(encoding="utf-8"))["verses"]
    raw = FILE.read_text(encoding="utf-8")
    obj = json.loads(raw)

    records, edits = [], []                                   # edits: (path, old, new|DEL)

    def audit(path, text):
        p = "/".join(map(str, path))
        if p in OWNER_REMOVE:                                  # K4
            records.append((p, "OWNER-REMOVED (K4: sole source is a G2-held-out unit)", text, ""))
            edits.append((path, text, DEL))
            return DEL
        orig_text = text
        fixed = None
        if p in CITATION_FIXES:                                # K3
            fixed = CITATION_FIXES[p]
            text = apply_citation_fix(text, fixed, units)
        # K2 — manifest rule: NO citation into a G2 excluded unit may remain anywhere in a data
        # file. Scrub every field (kinship or not) BEFORE classifying.
        excl = [c for c in EX.find_citations(text) if any(EX._inside(c, u) for u in units)]
        work = strip_excluded_citations(text, units) if excl else text
        excl_txt = ", ".join("%s %s" % (c[0], ".".join(map(str, c[1]))) for c in excl)
        if excl and not work:
            records.append((p, f"EXCLUDED-CITATION ({excl_txt}) -> field REMOVED", orig_text, ""))
            edits.append((path, orig_text, DEL))
            return DEL
        if not KIN.search(work):
            if work != text:
                records.append((p, f"EXCLUDED-CITATION ({excl_txt}) -> scrubbed", orig_text, work))
                edits.append((path, orig_text, work))
            return work
        cits = EX.find_citations(work)
        gold = [c for c in cits if in_gold(c)]
        if not GEN.search(work):
            new = work
            records.append((p, "LINEAGE-GENERIC (unchanged)" + (" [strong]" if LINEAGE_STRONG.search(work) else "")
                            + (f"; EXCLUDED-CITATION ({excl_txt}) scrubbed" if excl else ""), orig_text, new))
            if new != text:
                edits.append((path, orig_text, new))
            return new
        if EPIC.search(work) or "ramayana" in p.lower():
            new = work if EPIC_NOTE.strip() in work else work.rstrip() + EPIC_NOTE
            records.append((p, "EPIC (annotated)", orig_text, new))
            if new != text:
                edits.append((path, orig_text, new))
            return new
        admissible = [c for c in cits if c not in gold]
        if admissible and all(verse_has_kin_lemma(c, morph) for c in admissible):
            records.append((p, "BACKED (kept)", orig_text, work))
            if work != text:
                edits.append((path, orig_text, work))
            return work
        new = relabel(work)
        adm = [c for c in cits if c not in gold]
        why = ("UNBACKED; cited G2-excluded unit " + excl_txt if excl else
               "UNBACKED; cites gold hymn " + ", ".join("%s %s" % (c[0], ".".join(map(str, c[1]))) for c in gold)
               if gold else
               ("CITATION-CORRECTED (K3: %s -> %s, verified in local_store); admissible, but the verse attests only "
                "a patronymic (no kin lemma)" % (fixed["from"], fixed["to"]) if fixed
                else "ADMISSIBLE citation, no kin lemma in the verse" if adm else "UNBACKED; no citation"))
        records.append((p, why + " -> relabelled", orig_text, new))
        edits.append((path, orig_text, new))
        return new

    def prune(o):                                              # drop DEL markers produced above
        if isinstance(o, dict):
            return {k: prune(v) for k, v in o.items() if v is not DEL}
        if isinstance(o, list):
            return [prune(v) for v in o if v is not DEL]
        return o
    new_obj = prune(walk(obj, [], audit))

    # ── audit table ──
    print(f"kinship-bearing fields: {len(records)}   (file has {sum(1 for _ in re.finditer(chr(34)+':', raw))} key/value pairs)")
    from collections import Counter
    print("classes:", dict(Counter(r[1].split(' (')[0].split(';')[0].split(' ->')[0] for r in records)))
    for p, cls, old, new in records:
        print(f"\n[{cls}]\n  {p}\n    - {old}\n    + {new if new != old else '(unchanged)'}")

    # ── surgical raw-text edits, then prove equality with the intended structure ──
    text = raw
    for path, old, new in edits:
        eo = json.dumps(old, ensure_ascii=False)
        if text.count(eo) != 1:
            raise RuntimeError(f"edit target not unique/absent ({text.count(eo)}x): {old!r}")
        if new is DEL:
            m = re.search(r"^[ \t]*\"[^\"]+\":\s*" + re.escape(eo) + r"(,?)[ \t]*\n", text, re.M) \
                or re.search(r"^[ \t]*" + re.escape(eo) + r"(,?)[ \t]*\n", text, re.M)          # list item on its own line
            if not m:
                raise RuntimeError(f"cannot delete (not a 'key: value' or list-item line): {old!r}")
            text = text[: m.start()] + text[m.end():]         # a trailing comma left behind is repaired below
        else:
            text = text.replace(eo, json.dumps(new, ensure_ascii=False))
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        text = re.sub(r",(\s*[}\]])", r"\1", text)            # repair a trailing comma left by a deleted last member
        parsed = json.loads(text)
    if parsed != new_obj:
        raise RuntimeError("edited text does not equal the intended structure — aborting, file untouched")
    print(f"\nverified: edited file parses and equals the intended structure ({len(edits)} edits)")

    # fail loud: no excluded citation may remain anywhere in the data file
    leftover = EX.text_hits_excluded(json.dumps(parsed, ensure_ascii=False), units)
    if leftover:
        raise EX.ExclusionViolation(f"excluded-unit citations remain after audit: {leftover}")
    print("verified: no citation into a G2 excluded unit remains in the file")

    if args.apply:
        FILE.write_text(text, encoding="utf-8")
        print(f"wrote {FILE} (working tree only — NOT staged, NOT committed)")
    else:
        print("dry run — nothing written (use --apply)")


if __name__ == "__main__":
    main()

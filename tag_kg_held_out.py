#!/usr/bin/env python3
"""Tag KG relations whose citations fall in a G2 EXCLUDED unit (owner decision 2026-11-21).

Writes knowledge_store/kg_held_out_relations.json — a NEW sidecar; it does NOT modify
knowledge_store/vedic_relations.json (the local mirror) and performs NO Qdrant write or delete
(it only READS the effective KG, i.e. what the pipeline actually serves: Qdrant if reachable,
else the mirror). Eval/training loaders filter these relations through
src/utils/vedic_kg.py (fact_is_held_out / iter_relations / KG_EXCLUDE_HELD_OUT=1); that filter
RECOMPUTES from the manifest at runtime, so this file is the auditable record, not the gate.

Self-check (fails loudly): iter_relations(exclude_held_out=True) must yield exactly
total − tagged relations, and none of them may mention an excluded unit under a loose scan.
"""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.utils import exclusions as EX                     # noqa: E402
from src.utils import vedic_kg as K                        # noqa: E402

OUT = ROOT / "knowledge_store" / "kg_held_out_relations.json"
MIRROR = ROOT / "knowledge_store" / "vedic_relations.json"


def hit_units(fact, units):
    out = set()
    for c in (fact.get("citations") or [fact.get("citation", "")]):
        out.update(EX.text_hits_excluded(c or "", units))
        if c and EX.is_excluded(c, units):
            cit = EX.parse_citation(c)
            if cit:
                out.add("%s %s" % (cit[0], ".".join(map(str, cit[1]))))
    return sorted(out)


def main():
    units = EX.load_excluded_units()
    kg = K._load()                                          # READ only (Qdrant or mirror)
    source = "effective KG as served by vedic_kg._load() (Qdrant if reachable, else the local mirror)"
    tagged, total, by_prov, by_prov_tagged = [], 0, collections.Counter(), collections.Counter()
    for key, entity in kg["entities"].items():
        for fact in entity.get("relations", []):
            total += 1
            by_prov[fact.get("provenance", "inferred")] += 1
            if K.fact_is_held_out(fact):
                by_prov_tagged[fact.get("provenance", "inferred")] += 1
                tagged.append({"entity": key, "display_name": entity.get("display_name", key),
                               "relation": fact.get("relation"), "object": fact.get("object"),
                               "citations": fact.get("citations") or [fact.get("citation", "")],
                               "provenance": fact.get("provenance", "inferred"),
                               "held_out_units_hit": hit_units(fact, units)})

    # ── self-check: the loader filter yields exactly the untagged relations, with no excluded mention ──
    kept = list(K.iter_relations(exclude_held_out=True))
    assert len(kept) == total - len(tagged), (len(kept), total, len(tagged))
    for _, _, fact in kept:
        assert not hit_units(fact, units), f"filter leaked a held-out relation: {fact}"
    # loose scan (independent of the citation regex): a kept relation must not mention an excluded hymn.
    # Corpus-aware (found by this very self-check: 'AVS 4.38.6' is Atharvaveda, NOT the excluded RV 4.38).
    RV_CODES = {"RV", ""}
    loose = []
    for u in units:
        if u[0] == "RV" and len(u[1]) >= 2:
            a, b = u[1][:2]
            loose.append(re.compile(r"(?<![0-9.])%d\.(?:%d|%03d)\.\d+" % (a, b, b)))

    def loose_rv_hit(txt):
        for r in loose:
            for m in r.finditer(txt):
                code = re.search(r"([A-Za-zŚś]+)\s*$", txt[max(0, m.start() - 6):m.start()])
                if (code.group(1) if code else "") in RV_CODES:     # bare or 'RV' prefix only
                    return True
        return False
    for _, _, fact in kept:
        txt = " ".join(fact.get("citations") or [])
        assert not loose_rv_hit(txt), f"loose scan: kept relation cites an excluded RV hymn: {txt}"

    # mirror comparison (informational): same rule applied to the local JSON mirror
    mirror = json.loads(MIRROR.read_text(encoding="utf-8"))["entities"]
    m_total = sum(len(e.get("relations", [])) for e in mirror.values())
    m_tag = sum(1 for e in mirror.values() for f in e.get("relations", []) if K.fact_is_held_out(f))

    out = {"_meta": {"built_by": "tag_kg_held_out.py", "decision": "owner 2026-11-21: tag; loaders filter; no Qdrant deletes",
                     "source": source, "excluded_units_loaded": [f"{c} {'.'.join(map(str, u))}" for c, u in units],
                     "total_relations": total, "tagged_relations": len(tagged),
                     "tagged_entities": len({t["entity"] for t in tagged}),
                     "by_provenance_all": dict(by_prov), "by_provenance_tagged": dict(by_prov_tagged),
                     "mirror_total": m_total, "mirror_tagged": m_tag,
                     "nothing_deleted": "no relation was removed locally or in Qdrant"},
           "relations": tagged}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    m = out["_meta"]
    print(f"effective KG relations: {total} | tagged held-out: {len(tagged)} "
          f"({100 * len(tagged) / total:.2f}%) across {m['tagged_entities']} entities")
    print(f"by provenance — all: {m['by_provenance_all']}  tagged: {m['by_provenance_tagged']}")
    print(f"local mirror: {m_total} relations, {m_tag} tagged (the effective KG may differ slightly from the mirror)")
    print(f"self-check passed: iter_relations(exclude_held_out=True) -> {len(kept)} = {total} - {len(tagged)}; "
          f"no excluded mention in any kept relation (citation regex + loose scan)")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

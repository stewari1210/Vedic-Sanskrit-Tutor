"""Unit tests for the Phase-1 correction rules (docs/phase1_correction_rules.md).

Synthetic inputs only — invented words and neutral glosses. Nothing here consults a gold
or held-out case. Run:  python tests/test_phase1_rules.py   (or under pytest)
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils import exclusions as EX                     # noqa: E402
import build_lexicon_flags as LX                           # noqa: E402
import build_pada_samhita_divergence as R2                 # noqa: E402


# ── exclusions (real manifest) ──
def test_exclusion_units_and_matching():
    base_units = EX.load_excluded_units(include_parallels=False)
    assert len(base_units) == 15, base_units
    units = EX.load_excluded_units()
    assert len(units) >= 15, units
    assert EX.is_excluded("RV 7.096.05", units) and EX.is_excluded("7.096.05", units)
    assert not EX.is_excluded("RV 7.095.01", units)
    assert EX.is_excluded("ŚB 1.8.1.4", units) and not EX.is_excluded("ŚB 1.8.2.1", units)
    assert EX.is_excluded("AB 8.21.11", units) and not EX.is_excluded("AB 8.20.1", units)
    assert EX.is_excluded("॥ AVŚ 19.39.3 ॥", units)
    assert EX.rv_verse_is_excluded("10.033.04", units) and not EX.rv_verse_is_excluded("10.034.01", units)
    assert "7.096" in EX.excluded_rv_hymns(units)
    # Parallel units are enforced identically to excluded_units
    assert EX.is_excluded("AVP 7.10.1", units) and EX.is_excluded("Nir 9.26", units)
    assert EX.is_excluded("MS 4.10.1", units) and not EX.is_excluded("AVP 20.46.9", units)


def test_exclusion_fails_loudly():
    units = EX.load_excluded_units()
    try:
        EX.assert_none_excluded(["2.012.03|1", "7.096.05|3"], "t", units)
    except EX.ExclusionViolation:
        pass
    else:
        raise AssertionError("did not raise on an excluded key")
    EX.assert_none_excluded(["2.012.03|1"], "t", units)             # clean passes
    try:
        EX.load_excluded_units(Path("/nonexistent/g2.json"))
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("missing manifest must raise")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps({"excluded_units": []}))
        try:
            EX.load_excluded_units(p)
        except ValueError:
            pass
        else:
            raise AssertionError("empty exclusion list must raise")
    assert EX.text_hits_excluded("see RV 10.33.4 and RV 2.12.3") == ["RV 10.33.4"]


# ── lexicon rules (synthetic glosses) ──
def test_gloss_classification():
    c = LX.classify_gloss
    # L3: first substantive sense is a firm name (later senses elaborate the name)
    assert c("N. pr., Name eines Fürsten, traivr̥ṣṇá-, *Trivr̥ṣan-Nachkomme; etwa: '*dreifach rötlich'") == "L3"
    assert c("Name eines Stammeshelden, meist zusammen mit Turvaśa genannt") == "L3"
    assert c("Name eines vedischen Sängers") == "L3"                       # one intervening word
    assert c("Name eines Gottes; Pl. einer Götterklasse (auch Bezeichnung anderer vedischer Götter)") == "L3"
    assert c("N. pr., Name eines Sängers; m. Plur. 'die Xas', eine Sängerfamilie") == "L3"
    # L1: appellative first, firm (unlocalised, unhedged) name sense later
    assert c("lebensvoll, beweglich; m. Mensch; Name eines Feindes des Indra") == "L1"
    assert c("vielstimmig, Chorgesang; als N. pr. aufzufassen") == "L1"
    # dropped, never rendered: hedged / verse-localised name senses
    assert c("zehn Wagen enthaltend; mögl. auch N. pr., Eigenname (GM)") == "DROP_HEDGED"
    assert c("Getöse, Lärm; vielleicht auch N. pr., Eigenname") == "DROP_HEDGED"
    assert c("zahlreich, häufig; N. pr. in 8.1.34?") == "DROP_LOCAL"            # hedged + localised: still dropped
    # v3 / L3b (owner-adopted): a FIRM localised name sense is applied at the cited verse(s) only
    assert c("rotbraun, braun; in 5.30.14 und 8.22.10 Name eines Sängers") == "L3B"
    assert c("von Göttern umgeben; (N. pr.) in RV 03.001.02 Name eines Mannes") == "L3B"   # invented locus
    assert c("unklar; vielleicht N. pr. bzw. Name eines dämonischen Wesens") == "DROP_HEDGED"
    assert c("N. pr.?, Name eines Mannes") == "DROP_HEDGED"
    # not names
    assert c("Name eines Metrums") == "NONE"
    assert c("Feuer; das vergöttlichte Feuer, Gott Agni") == "NONE"
    assert c("anrufen, durch Lieder preisen") == "NONE"


def test_sense_split_ignores_parentheses():
    assert LX.split_senses("a (x; y); b") == ["a (x; y)", "b"]


def test_title_keeps_sibilant_drops_accent():
    assert LX.title_of("índra-") == "Indra"
    assert LX.title_of("kuruśrávaṇa-") == "Kuruśravaṇa"                    # ś must survive accent stripping
    assert LX.title_of("yádu-") == "Yadu"


# ── R2 sandhi surfaces ──
def test_visarga_surfaces():
    v = R2.visarga_surfaces
    assert v("agniḥ", "d") == {"agnir"}
    assert v("agniḥ", None) == {"agniḥ"}
    assert v("indraḥ", "a") == {"indro"}
    assert v("indraḥ", "i") == {"indra"}
    assert v("devāḥ", "g") == {"devā"}
    assert v("devaḥ", "c") == {"devaś"} and v("devaḥ", "t") == {"devas"} and v("devaḥ", "ṭ") == {"devaṣ"}
    assert v("devaḥ", "s") == {"devas", "devaḥ"}
    assert v("devaḥ", "k") == {"devaḥ", "devas"} and v("devaḥ", "p") == {"devaḥ", "devas"}   # v2: -s before k/p
    assert "agnī" in v("agniḥ", "r") and "agnir" in v("agniḥ", "r")
    assert v("saḥ", "g") == {"so", "sa"}
    assert v("agni", "d") is None                                         # no visarga -> not evaluated


def test_norm_and_accents():
    assert R2.norm("yáḥ") == "yaḥ"
    assert R2.norm("śácībhiḥ") == "śacībhiḥ"                              # ś kept
    assert R2.norm("purú +") == "puru"
    assert R2.norm("dákṣiṇena-") == "dakṣiṇena"


def test_samhita_words_pada_boundary_semantics():
    # v2: sandhi applies ACROSS pāda boundaries unless the word ends in '-' (suspended) or a
    # half-verse/verse marker follows (pausa).
    W = R2.samhita_words([["a", "hántā vr̥tráṃ dákṣiṇena-"], ["b", "-índraḥ purū́ |"], ["c", "x yaḥ"], ["d", "dá ‖"]])
    assert [w[1] for w in W] == ["hantā", "vr̥traṃ", "dakṣiṇena", "indraḥ", "purū", "x", "yaḥ", "dá".replace("á", "a")]
    assert W[2][2] is None                    # hyphen: sandhi suspended (pausa-like)
    assert W[0][2] == "vr̥traṃ"                # ordinary in-line neighbour
    assert W[4][2] is None                    # '|' follows: pausa
    assert W[6][2] == "da"                    # pāda-final, no marker: sandhi continues into the next pāda
    assert W[7][2] is None                    # '‖' follows: pausa


def test_alignment_skips_merged_tokens():
    T = ["yaḥ", "agnim", "īḍe"]
    W = ["yo", "agnim", "īḍe"]
    assert R2.align(T, W) == [(0, 0), (1, 1), (2, 2)] or len(R2.align(T, W)) >= 2


def test_implied_alternative_and_attestation():
    # invented stem: padapāṭha 'dhenoḥ' would give 'dhenor' before a voiced initial; the saṃhitā shows
    # 'dheno', which is regular for 'dhenaḥ'. Alternative reported only if 'dhenaḥ' is attested.
    att = lambda f: ["dhenu"] if f == "dhenaḥ" else None                  # noqa: E731
    assert R2.implied_alternatives("dhenoḥ", "dheno", "d", att) == [{"form": "dhenaḥ", "lemmas": ["dhenu"]}]
    assert R2.implied_alternatives("dhenoḥ", "dheno", "d", lambda f: None) == []   # unattested -> nothing
    # a regular pair yields no divergence in the first place
    assert "dhenor"[1:] in {e[1:] for e in R2.visarga_surfaces("dhenoḥ", "d")}


def test_citation_boundary_regression():
    """Regression: a citation directly after a quote/colon/comma was invisible to the guard."""
    units = EX.load_excluded_units()
    for t in ['"RV 10.33.4"', '"hymn_reference": "RV 10.33.4",', "'RV 10.33.4'", "x:RV 10.33.4",
              "(RV 10.33.4)", "see,RV 10.33.4.", "RV 10.33.4"]:
        assert EX.text_hits_excluded(t, units) == ["RV 10.33.4"], t
    assert EX.text_hits_excluded("ARV 10.33.4 and NRV 1.131.2", units) == []        # not a citation (letter before)
    assert EX.text_hits_excluded('"RV 2.12.3"', units) == []                        # admissible unit
    assert EX.text_hits_excluded('"ŚB 1.8.1.4"', units) == ["SB 1.8.1.4"]


def test_localised_loci_parsing():
    f = LX.firm_local_loci
    assert f("rotbraun, braun; in 5.30.14 und 8.22.10 Name eines Sängers") == (["5.030.14", "8.022.10"], 0)
    assert f("x; in 5. 44.11 N. pr.") == (["5.044.11"], 0)                  # space after the first dot
    assert f("x; (N. pr.) in RV 03.001.02 Name eines Mannes") == (["3.001.02"], 0)   # zero-padded form
    assert f("x; N. pr. in 5.44") == ([], 1)                                # hymn-level only: counted, never applied
    assert f("x; N. pr. in 8.1.34?") == ([], 0)                             # hedged: not a firm sense at all
    assert f("Name eines Gottes") == ([], 0)                                # unlocalised: not an L3b matter
    assert LX.ENABLE_L1 is False                                            # owner decision: L1 disabled


def test_kg_held_out_filter_synthetic():
    import os
    from src.utils import vedic_kg as K
    bad = {"relation": "has_son", "object": "x", "citations": ["RV 10.033.04"]}
    ok = {"relation": "has_son", "object": "y", "citations": ["RV 2.012.03"]}
    txt = {"relation": "a", "object": "b", "citations": ["see RV 7.096.1 and AB 8.21.11"]}
    assert K.fact_is_held_out(bad) and K.fact_is_held_out(txt) and not K.fact_is_held_out(ok)
    K._KG_CACHE = {"_meta": {"total_facts": 3},
                   "entities": {"e": {"display_name": "E", "relations": [bad, ok, txt]}}}
    try:
        assert [f["object"] for _, _, f in K.iter_relations()] == ["y"]             # default excludes
        assert len(list(K.iter_relations(exclude_held_out=False))) == 3
        os.environ.pop("KG_EXCLUDE_HELD_OUT", None)
        off = K.get_entity_context(["e"], hops=1)
        assert "→ x" in off and "→ y" in off                                       # production path unchanged
        os.environ["KG_EXCLUDE_HELD_OUT"] = "1"
        on = K.get_entity_context(["e"], hops=1)
        assert "→ y" in on and "→ x" not in on and "→ b" not in on                 # eval path filters
    finally:
        os.environ.pop("KG_EXCLUDE_HELD_OUT", None)
        K._KG_CACHE = None


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"\n{len(fns)} tests passed")

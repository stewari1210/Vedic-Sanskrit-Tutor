"""
Gold test set for the translation / grammar / interpretation layer.

G1–G16 come from TRANSLATION_DIAGNOSIS.md; G17–G18 and two retrieval
regressions (R1, R2) were added with the fix plan.

Run (live, billed — ~20 LLM calls):
    GOLD_LABEL=phase0 python tests/gold_translation.py            # run + table
    GOLD_LABEL=phase0 python tests/gold_translation.py --fresh    # ignore cache
    GOLD_LABEL=phase1 python tests/gold_translation.py --only G2,G4
    python tests/gold_translation.py --report phase0 phase1       # compare labels
or under pytest (one test function per case; results are cached per label, so
the pipeline is only called once per case per label):
    GOLD_LABEL=phase0 pytest tests/gold_translation.py -q

Design notes
  • Programmatic checks wherever the expected answer is a form (a token, a
    case/number tag, a required or forbidden phrase). The LLM judge is used ONLY
    where wording varies (G10, G11, G14, G15) and all four are judged in ONE call.
  • Checks are heuristics over accent-stripped, NFC-normalised IAST/Devanāgarī
    text. A programmatic PASS means "the required content is present and the
    forbidden content is absent", not "the whole answer is right". The saved
    JSON keeps every full answer so failures can be inspected by hand.
  • G16 tests the retrieval step only (execute_tools_node), not synthesis: the
    unpinned factual path also fires a background KG write to cloud Qdrant, which
    a test must not trigger.
  • Nothing here reads .env directly; config is reported via the settings loader.
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

CACHE_DIR = ROOT / "tests" / "gold_cache"
LABEL = os.environ.get("GOLD_LABEL", "current")

# ───────────────────────── text helpers ─────────────────────────

_ACCENTS = {"́", "̀", "̍", "॑", "॒"}


def norm(s: str) -> str:
    """Lower-case, strip Vedic accent marks, unify ṁ→ṃ, NFC."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if c not in _ACCENTS)
    s = unicodedata.normalize("NFC", s).lower()
    return s.replace("ṁ", "ṃ").replace("m̐", "ṃ")


def windows(text: str, pattern: str, after: int = 220, before: int = 0):
    """Text windows around every regex match of `pattern` in normalised text."""
    t = norm(text)
    return [t[max(0, m.start() - before): m.end() + after]
            for m in re.finditer(pattern, t)]


def hedged(text: str, pattern: str, hedge: str, span: int = 160) -> bool:
    """True when EVERY occurrence of `pattern` has a hedge word within `span`."""
    ws = windows(text, pattern, after=span, before=span)
    return all(re.search(hedge, w) for w in ws)


# ───────────────────────── checks (programmatic) ─────────────────────────
# Each returns (passed: bool, detail: str).

def _need(text, *pats):
    t = norm(text)
    miss = [p for p in pats if not re.search(p, t)]
    return miss


def _forbid(text, *pats):
    t = norm(text)
    return [p for p in pats if re.search(p, t)]


def _result(miss, bad):
    if not miss and not bad:
        return True, "ok"
    return False, "; ".join(
        ([f"missing: {', '.join(miss)}"] if miss else []) +
        ([f"forbidden present: {', '.join(bad)}"] if bad else []))


def chk_g1(a, ctx):  # ŚB 13.5.4.5 daurgaheṇa + īje
    return _result(_need(a, r"daurgaheṇa\b", r"\bīje\b"),
                   _forbid(a, r"daurgaheṇaḥ"))


def chk_g2(a, ctx):  # RV 10.60.6 rājann arādhasaḥ
    return _result(_need(a, r"rājann\s*(\+|\||·|-|–|—)?\s*arādhasaḥ|rājann arādhasaḥ"),
                   _forbid(a, r"narādhasaḥ", r"rājan\s*(\+|\||·|-)?\s*narādhas"))


def chk_g3(a, ctx):  # RV 1.63.7 vark, aṃhoḥ/aṃhaḥ ambiguity
    return _result(_need(a, r"\bvark\b", r"aṃhoḥ", r"aṃhaḥ", r"aorist"),
                   [])


def _window_check(a, token, need=(), forbid=(), after=200):
    ws = windows(a, token, after=after)
    if not ws:
        return False, f"token /{token}/ not found in answer"
    miss = [p for p in need if not any(re.search(p, w) for w in ws)]
    bad = [p for p in forbid if any(re.search(p, w) for w in ws)]
    return _result(miss, bad)


_NEG = r"(not|nor|never|neither|no|rather than|instead of|isn't|is not)\W+(\w+\W+){0,3}$"


def marayi_not_person(a):
    """Cross-case (RV 10.60.4: G4, G9): marāyī must not be called a queen, person or
    place (it is an epithet of the verse's subject, not a proper name). A mention is
    forgiven when negated just before ('not a queen', 'nor a place')."""
    t = norm(a)
    bad = []
    for m in re.finditer(r"marāyī", t):
        win = t[max(0, m.start() - 90): m.end() + 90]
        for w in re.finditer(r"\b(queen|person|place|woman|princess|toponym)\b", win):
            before = win[:w.start()]
            if not re.search(_NEG, before[-40:]):
                bad.append(w.group(1))
    return sorted(set(bad))


def _with_marayi_guard(fn):
    def wrapped(a, ctx):
        ok, detail = fn(a, ctx)
        bad = marayi_not_person(a)
        if bad:
            msg = f"marāyī called {'/'.join(bad)} (cross-case RV 10.60.4)"
            return False, (msg if ok else f"{detail}; {msg}")
        return ok, detail
    return wrapped


def chk_g4(a, ctx):  # marāyī = nom. sg. m. epithet, not locative
    return _window_check(a, r"marāyī", need=[r"nominative|nom\."],
                         forbid=[r"locative|\bloc\."])


def chk_g5(a, ctx):  # māhīnānām gen. pl. "of the mighty ones", not a clan
    return _window_check(a, r"māhīnānām", need=[r"genitive|gen\.", r"plural|pl\."],
                         forbid=[r"\bclan\b|\btribe\b|\bpeople named\b"])


def chk_g6(a, ctx):  # sudāstarāya comparative -tara
    return _window_check(a, r"sudāstarāya|sudās-?tara|sudāstara",
                         need=[r"comparative"],
                         forbid=[r"superlative", r"patronymic", r"\bmost\b",
                                 r"√\s*dāś|\broot\s+dāś|\bfrom\s+dāś|\bdāś\s*\(",
                                 r"sqrt\{\s*dā(\\acute\{s\}|ś)|dā\\acute\{s\}"])


def chk_g7(a, ctx):  # aviṣṭana iṣ-aorist imperative 2nd pl.
    return _window_check(a, r"aviṣṭana",
                         need=[r"aorist", r"imperative", r"2nd|second|\b2\b", r"plural|pl\."])


def chk_g8(a, ctx):  # na compares Sudās with Divodāsa
    t = norm(a)
    ws = windows(a, r"divodāsaṃ\s+na\b|divodāsaṃ|na pitaraṃ", after=260, before=60)
    if not ws:
        return False, "divodāsaṃ ná pitaraṃ not discussed"
    ok = any(re.search(r"compar|simile|\blike\b|\bas (his|a|the) ", w) for w in ws)
    bad = any(re.search(r"not (his|the|a) father|negat|na (is|means) (a )?negati|weaken", w)
              for w in ws)
    return (ok and not bad), ("ok" if ok and not bad else
                              f"comparison-marker={ok}, negation/weakening reading={bad}")


def chk_g9(a, ctx):  # divīva pañca kṛṣṭayaḥ is a simile
    return _window_check(a, r"divīva|divī iva|divi iva",
                         need=[r"simile|\blike\b|as if|comparison|compar"], after=240)


def chk_g12(a, ctx):  # RV 3.53.11 must not assert aśvamedha
    t = norm(a)
    if not re.search(r"aśvamedha|ashvamedha|asvamedha", t):
        return True, "ok (aśvamedha not mentioned)"
    ok = hedged(a, r"aśvamedha|ashvamedha|asvamedha",
                r"later|resembl|inferr|not attested|tradition|anachron|no mention|does not|not name|rather")
    return ok, "ok (hedged)" if ok else "aśvamedha asserted without INFERRED/later hedge"


def chk_g13(a, ctx):  # RV 4.42.8 daurgahe: Sāyaṇa Tier 2; ŚB reads horse
    t = norm(a)
    miss = []
    if not re.search(r"sāyaṇa|sayana", t):
        miss.append("attribution to Sāyaṇa")
    if not re.search(r"tier[ -]?2|commentar", t):
        miss.append("commentary/Tier-2 label")
    if not (re.search(r"śatapatha|\bśb\b|shatapatha", t) and re.search(r"horse|aśva", t)):
        miss.append("ŚB 13.5.4.5 horse reading")
    return _result(miss, [])


def chk_g16(docs_text, ctx):  # retrieval: pūrave found
    return _result(_need(docs_text, r"पूरवे"), [])


def chk_g17(a, ctx):  # AB 7.13.1 rājāputra = rājā aputraḥ
    miss = _need(a, r"aputra", r"without a son|sonless|no son|childless|son-?less")
    asserted_bad = False
    for w in windows(a, r"king'?s son|son of (a|the) king|prince", after=0, before=50):
        if not re.search(r"not|rather than|instead of|no |never|incorrect|wrong", w):
            asserted_bad = True
    return _result(miss, ["asserts 'king's son'"] if asserted_bad else [])


def chk_g18(a, ctx):  # ŚB 1.4.1.15 taddhākṣetrataram
    miss = _need(a, r"akṣetrataram", r"uncultivated|not cultivated|unploughed|barren|non-cultivable")
    bad = _forbid(a, r"taddhā\s*(\+|-|\|)?\s*kṣetrataram")
    return _result(miss, bad)


def chk_g15(a, ctx):  # RV 1.112.19 sudevyam: BOTH readings, marked disputed
    # Now programmatic (tag-alternatives data seeds the feminine Sudevī reading):
    # a pass = the neuter 'divine favour' tag reading AND the feminine proper name
    # Sudevī AND an explicit disputed/ambiguous marker. "tag + noted alternative".
    t = norm(a)
    miss = []
    if not re.search(r"neuter|divine (favour|favor|help|gift)|abstract", t):
        miss.append("neuter 'divine favour' reading")
    if not re.search(r"sudevī|sudevi|sudevyā|feminine (proper )?(name|noun)", t):
        miss.append("feminine Sudevī reading")
    if not re.search(r"disput|ambigu|two readings|both readings|alternativ|contested|uncertain", t):
        miss.append("marked disputed/ambiguous")
    return _result(miss, [])


def chk_g19(a, ctx):  # RV 3.53.9 ápriyāyata = 'showed friendship / was friendly', not á-priya
    # Denominative of priyá ('friendly'), NOT the privative á-priya ('un-dear/unpleasant').
    # Require a friendship reading; forbid the 'unpleasant/displeased' misreading. (The
    # literal 'á-priya' string is NOT forbidden — a correct answer may cite it to reject it.)
    return _result(_need(a, r"friend"),
                   _forbid(a, r"unpleasant", r"displeas", r"made.{0,6}(un)?pleasant",
                           r"not dear", r"hostile toward"))


# ───────────────────────── case registry ─────────────────────────

def _q(ref, extra=""):
    # Deliberately DIGIT-FREE apart from the citation: the single-verse non-RV
    # resolver runs re.findall(r'\d+') over the whole query, so a numbered list
    # ("1) … 2) …") silently breaks AB/SB/TS lookups (defect D1, see FIX_LOG).
    return (f"Give a full scholarly interpretation of {ref}, covering the Devanagari as given, "
            f"the IAST, a word-by-word padapāṭha with sandhi resolution, the grammar and "
            f"morphology of each word, and an English interpretation grounded in that "
            f"morphology. {extra}").strip()


# kind: "pipe" (full run_agentic_rag), "judge" (pipe + LLM judge), "retr" (retrieval only)
CASES = {
    "G1":  dict(kind="pipe", q=_q("ŚB 13.5.4.5"), check=chk_g1,
                desc="ŚB 13.5.4.5 daurgaheṇeja = daurgaheṇa (instr.) + īje"),
    "G2":  dict(kind="pipe", q=_q("RV 10.60.6"), check=chk_g2,
                desc="RV 10.60.6 rājann arādhasaḥ"),
    "G3":  dict(kind="pipe", q=_q("RV 1.63.7"), check=chk_g3,
                desc="RV 1.63.7 vark (root aor. √vṛj); aṃhoḥ/aṃhaḥ ambiguity flagged"),
    "G4":  dict(kind="pipe", q=_q("RV 10.60.4"), check=_with_marayi_guard(chk_g4),
                desc="RV 10.60.4 marāyī nom. sg. m. epithet beside revān"),
    "G5":  dict(kind="pipe", q=_q("RV 10.60.1"), check=chk_g5,
                desc="RV 10.60.1 māhīnānām gen. pl. 'of the mighty ones'"),
    "G6":  dict(kind="pipe", q=_q("RV 1.184.1"), check=chk_g6,
                desc="RV 1.184.1 sudāstarāya comparative -tara"),
    "G7":  dict(kind="pipe", q=_q("RV 7.18.25"), check=chk_g7,
                desc="RV 7.18.25 aviṣṭana iṣ-aorist imperative 2nd pl."),
    "G8":  dict(kind="pipe", q=_q("RV 7.18.25"), check=chk_g8,
                desc="RV 7.18.25 na compares Sudās with Divodāsa"),
    "G9":  dict(kind="pipe", q=_q("RV 10.60.4"), check=_with_marayi_guard(chk_g9),
                desc="RV 10.60.4 divīva pañca kṛṣṭayaḥ is a simile"),
    "G10": dict(kind="judge", q=_q("RV 3.53.9"),
                crit="The answer must treat 'the great seer' and Viśvāmitra in this verse as ONE "
                     "and the same subject (the great seer IS Viśvāmitra), not as two different persons.",
                desc="RV 3.53.9 great seer = Viśvāmitra (one subject)"),
    "G11": dict(kind="judge", q=_q("RV 7.18.22"),
                crit="The answer must attribute BOTH gifts mentioned (cows and chariots) to ONE giver — "
                     "the descendant of Devavat (naptur devavataḥ), i.e. Sudās — not to two donors.",
                desc="RV 7.18.22 both gifts from one man (Sudās)"),
    "G12": dict(kind="pipe",
                q="Interpret RV 3.53.11. What ritual or event does it describe, and on what grounds?",
                check=chk_g12, desc="RV 3.53.11 must not assert aśvamedha"),
    "G13": dict(kind="pipe",
                q="In RV 4.42.8, who is daurgahe? Who makes that identification and on what authority?",
                check=chk_g13, desc="RV 4.42.8 Purukutsa = Sāyaṇa (Tier 2); ŚB reads the horse"),
    "G14": dict(kind="judge",
                q="What kinship relationship does RV 6.61.5 attest?",
                crit="The verse contains no kinship term. The answer must say so plainly (no kinship "
                     "term / kinship not attested in this verse) and must NOT build a kinship argument "
                     "from it. Fail if it asserts or argues a kinship relationship from this verse.",
                desc="RV 6.61.5 has no kinship term -> say so"),
    # G15 is now PROGRAMMATIC: the tag-alternatives sidecar seeds the feminine Sudevī
    # reading, so "tag reading + noted alternative, marked disputed" is checkable and
    # becomes a reward signal (was judge-only).
    "G15": dict(kind="pipe", q=_q("RV 1.112.19"), check=chk_g15,
                desc="RV 1.112.19 sudevyam: neuter 'divine favour' AND feminine Sudevī, disputed"),
    "G16": dict(kind="retr", q="Where are the dwellings of the Pūru described in the Rigveda?",
                check=chk_g16, desc="Pūru query retrieves pūrave (dat. sg.), e.g. RV 7.5.3 / 1.130.7"),
    "G17": dict(kind="pipe", q=_q("AB 7.13.1"), check=chk_g17,
                desc="AB 7.13.1 rājāputra = rājā aputraḥ 'a king without a son'"),
    "G18": dict(kind="pipe", q=_q("ŚB 1.4.1.15"), check=chk_g18,
                desc="ŚB 1.4.1.15 taddhākṣetrataram = tad dha akṣetrataram 'very uncultivated'"),
    "G19": dict(kind="pipe", q=_q("RV 3.53.9"), check=chk_g19,
                desc="RV 3.53.9 ápriyāyata = 'showed friendship/was friendly' (denom. of priyá), not á-priya"),
}

# Retrieval regressions (R1 free; R2 = resolver free + one live call)
FIVE_VERSE_Q = ("Return the stored text, padapāṭha and word analysis for each verse: "
                "RV 7.018.23, RV 7.018.25, RV 7.020.02, RV 1.184.01, RV 1.112.19")
FIVE_IDS = ["7.018.23", "7.018.25", "7.020.02", "1.184.01", "1.112.19"]
MISSING_Q = "Return the stored text for each verse: RV 7.018.23, RV 7.999.99"

ORDER = [f"G{i}" for i in range(1, 20)] + ["R1", "R2", "R3", "R4"]


# ───────────────────────── infrastructure ─────────────────────────

class CallMeter:
    """Counts LLM calls/tokens by wrapping Settings.invoke_llm."""
    def __init__(self):
        self.calls = 0
        self.in_tok = 0
        self.out_tok = 0
        self.by_case = {}
        self.current = None

    def install(self):
        from src.settings import Settings
        orig = Settings.invoke_llm

        def wrapped(llm_obj, msgs):
            resp = orig(llm_obj, msgs)
            self.calls += 1
            um = getattr(resp, "usage_metadata", None) or {}
            i, o = um.get("input_tokens", 0), um.get("output_tokens", 0)
            self.in_tok += i
            self.out_tok += o
            d = self.by_case.setdefault(self.current, {"calls": 0, "in": 0, "out": 0})
            d["calls"] += 1; d["in"] += i; d["out"] += o
            return resp
        Settings.invoke_llm = staticmethod(wrapped)


METER = CallMeter()
_APP = None


def app():
    """The frontend's verse resolver, without Streamlit session state."""
    global _APP
    if _APP is None:
        from src.sanskrit_tutor_frontend import SanskritTutorApp
        _APP = SanskritTutorApp.__new__(SanskritTutorApp)  # skip __init__ (st.session_state)
    return _APP


def live_config() -> dict:
    from src.config import get_config_value as g
    keys = ["LLM_PROVIDER", "GEMINI_MODEL", "TEMPERATURE", "MAX_TOKENS",
            "GEMINI_THINKING_BUDGET", "EVAL_ENABLED", "EMBEDDING_PROVIDER", "COLLECTION_NAME"]
    return {k: g(k, None) for k in keys}


def _cache_path():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{LABEL}.json"


def load_cache():
    p = _cache_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"config": None, "cases": {}}


def save_cache(c):
    _cache_path().write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def run_pipeline(question: str):
    """Exactly the chat-mode path: resolve citations → pin → run_agentic_rag."""
    from src.utils.agentic_rag import run_agentic_rag
    pinned = app()._lookup_verses_in_query(question)
    res = run_agentic_rag(question, input_language="English", pinned_verse=pinned)
    ans = res.get("answer", {})
    text = ans.get("answer", "") if isinstance(ans, dict) else str(ans)
    return text, pinned


def run_retrieval(question: str):
    """Retrieval step only (LLM query expansion + hybrid retriever), no synthesis."""
    from src.utils.agentic_rag import execute_tools_node
    out = execute_tools_node({"next_action": "corpus", "query_type": "factual",
                              "question": question, "pinned_verse": None})
    return out.get("corpus_examples", [])


def judge_all(items: dict) -> dict:
    """ONE LLM call judging every wording-dependent case. items: {id: (criteria, answer)}."""
    from src.settings import Settings
    from src.utils import agentic_rag as ar
    blocks = []
    for cid, (crit, ans) in items.items():
        blocks.append(f"### CASE {cid}\nCRITERION: {crit}\nANSWER:\n{ans[:14000]}\n")
    prompt = ("You are a strict grader of Vedic Sanskrit analyses. For each CASE, decide whether the "
              "ANSWER satisfies the CRITERION. Judge only what the answer says. Return ONLY a JSON "
              'object: {"<CASE id>": {"pass": true|false, "reason": "<max 20 words>"}, ...}\n\n'
              + "\n".join(blocks))
    METER.current = "judge"
    resp = Settings.invoke_llm(ar.llm, [__import__("langchain_core.messages", fromlist=["x"]).SystemMessage(content=prompt)])
    text = Settings.extract_llm_text(resp)
    m = re.search(r"\{[\s\S]*\}", text)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


def run_case(cid: str, cache: dict, fresh=False):
    if cid in cache["cases"] and not fresh:
        return cache["cases"][cid]
    METER.current = cid
    t0 = time.time()
    rec = {"id": cid}
    try:
        if cid == "R1":
            found = app()._lookup_verses_in_query(FIVE_VERSE_Q) or {}
            got = [v["citation"] for v in found.get("multi_verses", [])]
            texts = {v["citation"]: v["text"] for v in found.get("multi_verses", [])}
            ok_ids = all(any(i.replace(".0", ".") in c.replace(".0", ".") or i in c for c in got)
                         for i in FIVE_IDS)
            ok_text = all(any(f"॥ {i} ॥" in t for t in texts.values()) for i in FIVE_IDS)
            rec.update(passed=bool(ok_ids and ok_text and len(got) == 5 and not found.get("missing_ids")),
                       detail=f"resolved={got} missing={found.get('missing_ids')}", desc="5-verse ID query resolves all five (free)")
        elif cid == "R3":  # D1: extra digits in the query must not break non-RV resolution
            probes = {
                "AB 7.13.1": "Interpret AB 7.13.1: 1) Devanagari, 2) IAST, 3) padapāṭha, 4) grammar",
                "SB 13.5.4.5": "Interpret ŚB 13.5.4.5: 1) Devanagari, 2) IAST, 3) padapāṭha",
                "TS 1.1.1.1": "Explain TS 1.1.1.1 in 3 steps: 1) text 2) grammar",
                "AVŚ 5.22.1": "Give 2 readings of AVŚ 5.22.1 and 1 summary",
            }
            bad = {}
            for want, q in probes.items():
                got = (app()._lookup_verses_in_query(q) or {}).get("citation")
                if got != want:
                    bad[want] = got
            rec.update(passed=not bad, detail="ok" if not bad else f"wrong/None: {bad}",
                       desc="D1: numbered-list query still resolves AB/ŚB/TS/AVŚ")
        elif cid == "R4":  # D2: ŚB must never silently resolve to an RV verse
            a_ = app()
            multi = a_._lookup_verses_in_query("Compare ŚB 1.4.1.15 and ŚB 1.4.1.16") or {}
            cits = [v["citation"] for v in multi.get("multi_verses", [])]
            m2 = a_._lookup_verses_in_query("Compare ŚB 1.4.1.15 and ŚB 1.4.1.99") or {}
            single_missing = a_._lookup_verses_in_query("Interpret ŚB 1.4.1.99")
            ok = (cits == ["SB 1.4.1.15", "SB 1.4.1.16"]
                  and [v["citation"] for v in m2.get("multi_verses", [])] == ["SB 1.4.1.15"]
                  and len(m2.get("missing_ids", [])) == 1
                  and not any("RV" in c for c in cits + [v["citation"] for v in m2.get("multi_verses", [])])
                  and single_missing is None)
            rec.update(passed=bool(ok),
                       detail=f"pair={cits}; pair+missing resolved={[v['citation'] for v in m2.get('multi_verses', [])]} "
                              f"missing={m2.get('missing_ids')}; single-missing={'None' if single_missing is None else single_missing.get('citation')}",
                       desc="D2: ŚB IDs resolve as SB, never as RV; nonexistent ŚB verse is not pinned")
        elif cid == "R2":
            found = app()._lookup_verses_in_query(MISSING_Q) or {}
            free_ok = found.get("missing_ids") == ["RV 7.999.99"] and len(found.get("multi_verses", [])) == 1
            text, _ = run_pipeline(MISSING_Q)
            near = windows(text, r"7\.999\.99", after=200, before=120)
            live_ok = bool(near) and any(re.search(r"not in index|not in the (index|corpus)", w) for w in near)
            rec.update(passed=bool(free_ok and live_ok), answer=text,
                       detail=f"resolver_ok={free_ok} says_not_in_index={live_ok}",
                       desc="RV 7.999.99 -> 'not in index' for that ID only")
        else:
            spec = CASES[cid]
            rec["desc"] = spec["desc"]
            if spec["kind"] == "retr":
                docs = run_retrieval(spec["q"])
                blob = "\n".join(d.page_content for d in docs)
                ok, detail = spec["check"](blob, None)
                hits = [m for m in ("7.005.03", "1.130.07") if m in blob]
                rec.update(passed=ok, detail=f"{detail}; n_docs={len(docs)}; target markers present: {hits}",
                           answer=blob[:3000])
            else:
                text, pinned = run_pipeline(spec["q"])
                rec["answer"] = text
                rec["pinned"] = (pinned or {}).get("citation")
                if spec["kind"] == "pipe":
                    ok, detail = spec["check"](text, None)
                    rec.update(passed=ok, detail=detail)
                else:
                    rec.update(passed=None, detail="awaiting judge")
    except Exception as e:  # never swallow: record loudly
        rec.update(passed=False, detail=f"EXCEPTION {type(e).__name__}: {e}")
    rec["seconds"] = round(time.time() - t0, 1)
    if str(rec.get("detail", "")).startswith("EXCEPTION"):
        # Infrastructure failure (bad key, network, quota) is NOT a gold result:
        # never cache it, or a rerun would silently reuse it as a baseline.
        print(f"[gold] {cid}: infrastructure error, not cached: {rec['detail'][:200]}", file=sys.stderr)
        return rec
    cache["cases"][cid] = rec
    save_cache(cache)
    return rec


def finalize_judge(cache: dict):
    """Judge all pending judge-cases in one call."""
    pending = {c: (CASES[c]["crit"], cache["cases"][c].get("answer", ""))
               for c in CASES if CASES[c]["kind"] == "judge"
               and c in cache["cases"] and cache["cases"][c].get("passed") is None}
    if not pending:
        return
    verdict = judge_all(pending)
    for cid in pending:
        v = verdict.get(cid) or {}
        cache["cases"][cid]["passed"] = bool(v.get("pass")) if v else False
        cache["cases"][cid]["detail"] = "judge: " + (v.get("reason") or "NO VERDICT RETURNED")
    save_cache(cache)


def run_all(only=None, fresh=False):
    cache = load_cache()
    cache["config"] = live_config()
    if fresh:
        cache["cases"] = {} if not only else cache["cases"]
    METER.install()
    for cid in ORDER:
        if only and cid not in only:
            continue
        run_case(cid, cache, fresh=fresh)
    finalize_judge(cache)
    cache["meter"] = {"calls": METER.calls, "input_tokens": METER.in_tok,
                      "output_tokens": METER.out_tok, "by_case": METER.by_case}
    save_cache(cache)
    return cache


def table(cache: dict, compare: dict = None) -> str:
    rows = ["| case | result | " + ("before | " if compare else "") + "detail |",
            "|---|---|" + ("---|" if compare else "") + "---|"]
    n = 0
    for cid in ORDER:
        r = cache["cases"].get(cid)
        if not r:
            continue
        flag = "PASS" if r.get("passed") else "FAIL"
        n += bool(r.get("passed"))
        b = ""
        if compare:
            br = compare["cases"].get(cid)
            b = f" {'PASS' if br and br.get('passed') else 'FAIL'} |" if br else " – |"
        rows.append(f"| {cid} | {flag} |{b} {str(r.get('detail',''))[:140]} |")
    rows.append(f"\n**{n} / {len([c for c in ORDER if c in cache['cases']])} pass**")
    return "\n".join(rows)


# ───────────────────────── pytest entry points ─────────────────────────

def _pytest_case(cid):
    cache = load_cache()
    METER.install()
    rec = run_case(cid, cache)
    if rec.get("passed") is None:
        finalize_judge(cache)
        rec = cache["cases"][cid]
    assert rec.get("passed"), f"{cid}: {rec.get('detail')}"


for _cid in ORDER:
    globals()[f"test_{_cid.lower()}"] = (lambda c=_cid: _pytest_case(c))


# ───────────────────────── CLI ─────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--rejudge", metavar="LABEL", help="re-run the ONE batched judge call over cached answers")
    ap.add_argument("--rescore", metavar="LABEL", help="re-apply CURRENT programmatic checks to cached answers (no LLM calls)")
    ap.add_argument("--report", nargs="*", help="print table for cached label(s) without running")
    a = ap.parse_args()
    if a.rejudge:
        LABEL = a.rejudge
        c = load_cache()
        for cid in c["cases"]:
            if CASES.get(cid, {}).get("kind") == "judge":
                c["cases"][cid]["passed"] = None
        METER.install()
        finalize_judge(c)
        print(table(c))
        sys.exit(0)
    if a.rescore:
        LABEL = a.rescore
        c = load_cache()
        changes = []
        for cid, rec in c["cases"].items():
            spec = CASES.get(cid)
            if not spec or spec["kind"] != "pipe" or not rec.get("answer"):
                continue
            ok, detail = spec["check"](rec["answer"], None)
            if ok != rec.get("passed") or detail != rec.get("detail"):
                changes.append((cid, rec.get("passed"), ok, detail))
                rec.setdefault("phase0_original", {"passed": rec.get("passed"), "detail": rec.get("detail")})
                rec["passed"], rec["detail"] = ok, detail
        save_cache(c)
        print("rescored", LABEL, "changes:", changes or "none")
        print(table(c))
        sys.exit(0)
    if a.report:
        prev = None
        for lab in a.report:
            LABEL = lab
            c = load_cache()
            print(f"\n=== {lab} ===  config={c.get('config')}\n{table(c, prev)}")
            prev = c
        sys.exit(0)
    only = {x.strip().upper() for x in a.only.split(",") if x.strip()}
    c = run_all(only or None, a.fresh)
    print(f"\nLABEL={LABEL}\nCONFIG={json.dumps(c['config'])}\n")
    print(table(c))
    print(f"\nLLM calls: {c['meter']['calls']}  in_tokens={c['meter']['input_tokens']}  out_tokens={c['meter']['output_tokens']}")

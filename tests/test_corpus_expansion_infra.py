"""Unit tests for corpus expansion infrastructure:
  1. Citation parser round-trips across all 20 corpora (Layers 1–5)
  2. Source-text filter positive detection & English collision misfire guard
  3. Transliteration converter round-trips (IAST, Velthuis, HK, SLP1)
  4. Visarga-bug validator (rejects trailing ह् unless allow-listed root)
  5. Accent preservation (text + assert_accents_preserved) vs stripping (text_search)
"""
import pytest

from src.utils.citations import (
    CORPUS_SPECS,
    BY_VEDA,
    convert_to_devanagari,
    extract_citations,
    find_visarga_bugs,
    format_citation,
    has_vedic_accents,
    parse_marker_citation,
    strip_vedic_accents,
)
from src.utils.exclusions import parse_citation as excl_parse_citation
from src.utils.citation_enhancer import VedicCitationExtractor, CitationFormatter
from src.utils.pronunciation import assert_accents_preserved, clean_for_speech
from langchain_core.documents import Document


# ── 1. Citation round-trip tests ─────────────────────────────────────────────

ROUND_TRIP_SAMPLES = [
    ("RV 7.018.23",  "RV",  (7, 18, 23)),
    ("AVŚ 5.22.1",   "AVŚ", (5, 22, 1)),
    ("AVS 5.22.1",   "AVŚ", (5, 22, 1)),
    ("AVP 1.1.1",    "AVP", (1, 1, 1)),
    ("VS 1.1",       "VS",  (1, 1)),
    ("TS 1.1.1.1",   "TS",  (1, 1, 1, 1)),
    ("MS 1.6.3",     "MS",  (1, 6, 3)),
    ("KS 20.1",      "KS",  (20, 1)),
    ("KapS 1.1",     "KapS", (1, 1)),
    ("AB 8.21.11",   "AB",  (8, 21, 11)),
    ("PB 25.10.1",   "PB",  (25, 10, 1)),
    ("SB 1.4.1.10",  "SB",  (1, 4, 1, 10)),
    ("ŚB 1.4.1.10",  "SB",  (1, 4, 1, 10)),
    ("KB 2.1",       "KB",  (2, 1)),
    ("GB 1.1.1",     "GB",  (1, 1, 1)),
    ("JB 1.1",       "JB",  (1, 1)),
    ("JUB 1.1.1.1",  "JUB", (1, 1, 1, 1)),
    ("TB 1.1.1.1",   "TB",  (1, 1, 1, 1)),
    ("TA 1.1.1",     "TA",  (1, 1, 1)),
    ("TĀ 1.1.1",     "TA",  (1, 1, 1)),
    ("BĀU 1.1.1",    "BĀU", (1, 1, 1)),
    ("BAU 1.1.1",    "BĀU", (1, 1, 1)),
    ("ChU 1.1.1",    "ChU", (1, 1, 1)),
    ("BŚS 18.44",    "BŚS", (18, 44)),
    ("BSS 18.44",    "BŚS", (18, 44)),
    ("Nir 1.1",      "Nir", (1, 1)),
]


@pytest.mark.parametrize("raw,canon_pre,parts", ROUND_TRIP_SAMPLES)
def test_citation_round_trip(raw, canon_pre, parts):
    # extract_citations
    found = extract_citations(f"See {raw} for details.")
    assert found == [(canon_pre, parts)], f"extract_citations failed for {raw}: {found}"
    # format_citation -> parse_marker_citation round trip
    formatted = format_citation(canon_pre, parts)
    marker_text = f"अग्निमीळे पुरोहितम् ॥ {formatted} ॥"
    assert parse_marker_citation(marker_text) == formatted
    # exclusions.py parser
    ex = excl_parse_citation(raw)
    assert ex is not None and ex[1] == parts, f"exclusions parse failed for {raw}: {ex}"
    # citation_enhancer
    assert VedicCitationExtractor.extract_verse_reference(marker_text) == formatted


def test_nirukta_commentary_label():
    doc = Document(
        page_content="समाम्नायः समाम्नातः ॥ Nir 1.1 ॥",
        metadata={"veda": "nirukta", "source_type": "commentary", "citation": "Nir 1.1", "filename": "nir"},
    )
    label, _ = CitationFormatter.format_citation_with_source(doc, 1)
    assert "Nir 1.1" in label
    assert "commentary" in label.lower()
    assert "not primary verse evidence" in label.lower()


# ── 2. Source-text filter collision & positive tests ─────────────────────────

def _make_dummy_retriever():
    from src.utils.retriever import HybridRetriever
    return HybridRetriever.model_construct(semantic_retriever=None, keyword_retriever=None, k=10)


@pytest.mark.parametrize("query", [
    "the TA said this verse is late",
    "I exported the notes to MS Word",
    "This model needs 16 GB of RAM",
    "Store the corpus on a 1 TB drive",
    "Run a KS test on the distribution",
    "Compare early vs later Vedic layers",
    "JB mentioned a parallel passage",
    "What does ChU mean in Chinese?",
])
def test_source_filter_no_english_misfires(query):
    r = _make_dummy_retriever()
    sources, strict = r._detect_source_text_filter(query)
    assert sources == [], f"Misfire on {query!r}: got {sources} (strict={strict})"


@pytest.mark.parametrize("query,expected_veda", [
    ("What does MS 1.6.3 say?", "maitrayani_samhita"),
    ("Rituals in Maitrāyaṇī Saṃhitā", "maitrayani_samhita"),
    ("Check KS 20.1 for Kurus", "kathaka_samhita"),
    ("What does Kāṭhaka Saṃhitā say about Agni?", "kathaka_samhita"),
    ("Read AVP 1.1.1", "atharvaveda_paippalada"),
    ("Compare passages in Atharvaveda Paippalāda", "atharvaveda_paippalada"),
    ("What does KB 2.1 say?", "kausitaki_brahmana"),
    ("Ritual in Kauṣītaki Brāhmaṇa", "kausitaki_brahmana"),
    ("Look up GB 1.1.1", "gopatha_brahmana"),
    ("Explain Gopatha Brāhmaṇa", "gopatha_brahmana"),
    ("Check JB 1.1", "jaiminiya_brahmana"),
    ("Stories in Jaiminīya Brāhmaṇa", "jaiminiya_brahmana"),
    ("Look up JUB 1.1.1.1", "jaiminiya_upanisad_brahmana"),
    ("Check TB 1.1.1.1", "taittiriya_brahmana"),
    ("What is in Taittirīya Brāhmaṇa?", "taittiriya_brahmana"),
    ("Check TA 1.1.1", "taittiriya_aranyaka"),
    ("What is in Taittirīya Āraṇyaka?", "taittiriya_aranyaka"),
    ("What does BĀU 1.1.1 say about Janaka?", "brihadaranyaka_upanisad"),
    ("Check ChU 1.1.1", "chandogya_upanisad"),
    ("Explain Chāndogya Upaniṣad", "chandogya_upanisad"),
    ("What does BŚS 18.44 say about Āyu and Amāvasu?", "baudhayana_srauta_sutra"),
    ("What does Nir 1.1 say?", "nirukta"),
    ("How does Yāska's Nirukta explain this word?", "nirukta"),
])
def test_source_filter_positive_new_corpora(query, expected_veda):
    r = _make_dummy_retriever()
    sources, _ = r._detect_source_text_filter(query)
    assert expected_veda in sources, f"Expected {expected_veda} in {sources} for {query!r}"
    # Specific sub-corpus checks: TB/TA must not pull in TS; AVP must not pull in AVS
    if expected_veda in ("taittiriya_brahmana", "taittiriya_aranyaka"):
        assert "taittiriya_samhita" not in sources
    if expected_veda == "atharvaveda_paippalada":
        assert "atharvaveda_shaunaka" not in sources


# ── 3. Converter round-trips (IAST, Velthuis, HK, SLP1) ─────────────────────

def test_converters_all_encodings():
    assert convert_to_devanagari("agnir vai devānām avamaḥ", "iast") == "अग्निर् वै देवानाम् अवमः"
    # Decomposed NFD h + combining dot below + uppercase Ḥ MUST produce visarga ः, never ह्
    assert convert_to_devanagari("prajāpatih\u0323 devaḤ", "iast") == "प्रजापतिः देवः"
    assert convert_to_devanagari("agni.h devaa.h", "velthuis") == "अग्निः देवाः"
    assert convert_to_devanagari("agniH devAH", "hk") == "अग्निः देवाः"
    assert convert_to_devanagari("agniH devAH", "slp1") == "अग्निः देवाः"


# ── 4. Visarga-bug validator ─────────────────────────────────────────────────

def test_visarga_bug_detector():
    clean = "प्रजापतिः देवाः बर्हिः ॥ MS 1.6.3 ॥"
    assert find_visarga_bugs(clean) == []

    broken = "प्रजापतिह् देवाह् बर्हिह् ॥ AB 1.1.1 ॥"
    bugs = find_visarga_bugs(broken)
    assert [w for _, w in bugs] == ["प्रजापतिह्", "देवाह्", "बर्हिह्"]

    # Real cited Sanskrit verb root on allow-list passes
    allowed = "वह् इति धातोः ॥ Nir 1.1 ॥"
    assert find_visarga_bugs(allowed) == []


# ── 5. Accent preservation (text) vs accent stripping (text_search) ──────────

def test_accent_preservation_and_text_search():
    dev_accented = convert_to_devanagari("agnír vái devā́nām avamáḥ", "iast")
    assert has_vedic_accents(dev_accented), f"Accents dropped in conversion: {dev_accented!r}"
    # Pronunciation cleaning must preserve accents on user-visible text
    cleaned = clean_for_speech(dev_accented + " ॥ MS 1.1.1 ॥")
    assert_accents_preserved(dev_accented, cleaned)
    # text_search strips ONLY svaras so unaccented queries match
    search_text = strip_vedic_accents(dev_accented)
    assert not has_vedic_accents(search_text)
    assert "अग्निर्" in search_text and "देवानाम्" in search_text and "अवमः" in search_text
    assert find_visarga_bugs(dev_accented) == []


# ── 6. Sliding-window prose splitting & retrieval dedup ──────────────────────

class _StubWordTokenizer:
    """Fast deterministic tokenizer (1 word -> 2 tokens) for unit-testing window invariants."""
    def encode(self, text: str, add_special_tokens: bool = True, truncation: bool = False):
        toks = []
        for w in text.split():
            toks.extend([1, 2])
        if add_special_tokens:
            return [0] + toks + [2]
        return toks


def test_sliding_windows_word_boundary_and_overlap():
    from src.utils.windowing import make_sliding_windows, center_excerpt_around_window

    tok = _StubWordTokenizer()
    # 150 Devanāgarī words -> ~300 tokens -> must split into ~3-4 windows <=128 tokens each
    words = [f"प्रजापतिः{i}" for i in range(150)]
    body = " ".join(words)
    cite = "MS 1.6.3"
    wins = make_sliding_windows(body, cite, tok, target_tokens=120, overlap_tokens=20, max_tokens=128)
    assert len(wins) >= 3
    for w in wins:
        # Every window ends on a complete word (never split mid-word/grapheme)
        for token in w.split():
            assert token in words
        # Token count including " ॥ MS 1.6.3 ॥" stays <= 128
        n_tok = len(tok.encode(f"{w} ॥ {cite} ॥", add_special_tokens=True))
        assert n_tok <= 128, f"Window exceeded 128 tokens: {n_tok}"
    # Consecutive windows overlap on tail/head words (~20 tokens -> ~10 words)
    for a, b in zip(wins, wins[1:]):
        a_words, b_words = a.split(), b.split()
        overlap = set(a_words[-15:]) & set(b_words[:15])
        assert len(overlap) >= 5, f"Expected overlap between consecutive windows, got {overlap}"
    # Full coverage: first word in wins[0], last word in wins[-1]
    assert wins[0].split()[0] == words[0]
    assert wins[-1].split()[-1] == words[-1]

    # center_excerpt_around_window preserves trailing native citation marker & word boundaries
    full_unit = f"{body} ॥ {cite} ॥"
    excerpt = center_excerpt_around_window(full_unit, f"{wins[1]} ॥ {cite} ॥", char_budget=300)
    assert excerpt.endswith(f"॥ {cite} ॥")
    assert len(excerpt) <= 320


def test_deduplicate_windowed_docs_keeps_best_window():
    r = _make_dummy_retriever()
    full_line = "अग्निः प्रथमः मध्यभागः अन्त्यभागः ॥ MS 1.6.3 ॥"
    d_part1 = Document(
        page_content="मध्यभागः ॥ MS 1.6.3 ॥",
        metadata={"citation": "MS 1.6.3", "part": 1, "n_parts": 3, "veda": "maitrayani_samhita", "full_unit_text": full_line},
    )
    d_part0 = Document(
        page_content="अग्निः प्रथमः ॥ MS 1.6.3 ॥",
        metadata={"citation": "MS 1.6.3", "part": 0, "n_parts": 3, "veda": "maitrayani_samhita", "text": full_line},
    )
    d_other = Document(
        page_content="इन्द्रः ॥ MS 1.6.4 ॥",
        metadata={"citation": "MS 1.6.4", "part": 0, "n_parts": 1, "veda": "maitrayani_samhita", "text": "इन्द्रः ॥ MS 1.6.4 ॥"},
    )
    deduped = r._deduplicate_windowed_docs([d_part1, d_part0, d_other])
    assert len(deduped) == 2
    assert deduped[0].metadata["citation"] == "MS 1.6.3"
    assert deduped[0].metadata["part"] == 1  # best-scoring (first) window wins
    assert deduped[0].page_content == full_line  # full native unit reconstructed
    assert deduped[0].metadata["matched_window"] == "मध्यभागः ॥ MS 1.6.3 ॥"
    assert deduped[1].metadata["citation"] == "MS 1.6.4"


# ── 7. G2 manifest parallel_units exclusion enforcement ──────────────────────

def test_exclusions_load_frozen_and_parallel_units():
    from src.utils.exclusions import load_excluded_units, is_excluded, assert_none_excluded, ExclusionViolation

    base = load_excluded_units(include_parallels=False)
    combined = load_excluded_units(include_parallels=True)
    # Frozen 15 excluded_units remain intact
    assert len(base) == 15
    assert len(combined) >= 18
    # Approved parallel_units (Tranche 1 + Tranche 2) are enforced identically to excluded_units
    assert is_excluded("AVP 7.10.1", combined)
    assert is_excluded("AVP 7.10.9", combined)
    assert is_excluded("AVP 1.31.4", combined)
    assert is_excluded("Nir 10.31", combined)
    assert is_excluded("TB 3.5.8.18", combined)
    assert is_excluded("TB 3.5.13.30", combined)
    assert is_excluded("TB 1.6.6.45", combined)
    assert is_excluded("TB 2.8.8.69", combined)
    assert is_excluded("JUB 4.8.4", combined)
    # Non-excluded neighbours remain allowed
    assert not is_excluded("AVP 7.11.1", combined)
    assert not is_excluded("Nir 10.32", combined)
    assert not is_excluded("JUB 4.8.5", combined)
    with pytest.raises(ExclusionViolation):
        assert_none_excluded(["AVP 7.10.3"], "test_parallel_guard", units=combined)


# ── 8. G16 Rigveda routing, BM25 citation dot preservation, Janaka precision ─

@pytest.mark.parametrize("query", [
    "Where are the dwellings of the Pūru described in the Rigveda?",
    "Where are the dwellings of the Pūru described in the Ṛgveda?",
    "Where are the dwellings of the Pūru described in the RV?",
])
def test_rigveda_source_filter_and_strict_no_leak(query):
    r = _make_dummy_retriever()
    sources, strict = r._detect_source_text_filter(query)
    assert sources == ["rigveda"] and strict is True

    # Under strict single-corpus mode, expansion docs with 0 matching corpus hits
    # must drop cleanly (allow_fallback=False) and NEVER leak KB/AVP into RV results.
    non_rv = [
        Document(page_content="ब्रह्म यशसस्य अवरुद्ध्यै ॥ KB 7.12.15 ॥", metadata={"veda": "kausitaki_brahmana"}),
        Document(page_content="दिवे स्वाहा ॥ AVP 6.13.10 ॥", metadata={"veda": "atharvaveda_paippalada"}),
    ]
    assert r._filter_docs_by_source(non_rv, sources, strict=True, allow_fallback=False) == []


def test_bm25_query_normalization_preserves_citation_dots():
    import re, unicodedata

    def _norm_bm25_query(query: str) -> str:
        # Mirrors src/utils/retriever.py Latin BM25 query normalization
        s = "".join(c for c in unicodedata.normalize("NFD", query) if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^\w\s\[\]\-\.]", "", s)
        s = re.sub(r"(?<!\d)\.|\.(?!\d)", "", s).strip()
        return s

    assert "1.6.3" in _norm_bm25_query("What does MS 1.6.3 say?")
    assert "7.018.23" in _norm_bm25_query("Interpret RV 7.018.23.")
    assert "13.5.4.5" in _norm_bm25_query("Explain ŚB 13.5.4.5, please.")
    assert not _norm_bm25_query("What does MS 1.6.3 say.").endswith(".")


def test_janaka_lexical_rescue_no_janakalpa_false_positive():
    from src.utils.devanagari_lexical import query_terms, devanagari_lexical_hits

    terms = query_terms("Who was Janaka?")
    assert "जनकल्पा" not in terms and "जनकल्पाः" not in terms
    assert "जनको" in terms and "जानकय" in terms

    docs = [
        Document(page_content="जनको ह वैदेहो बहुदक्षिणेन यज्ञेनेजे ॥ BĀU 3.1.1 ॥", metadata={"veda": "brihadaranyaka_upanisad"}),
        Document(page_content="क्रतुविदे जानकय ॥ AB 7.34.9 ॥", metadata={"veda": "aitareya_brahmana"}),
        Document(page_content="जनकल्पाः शंसति प्रजा वै जनकल्पा ॥ AB 6.32.23 ॥", metadata={"veda": "aitareya_brahmana"}),
        Document(page_content="जनकल्पा उत्तराः शंसति ॥ GB 2.6.12 ॥", metadata={"veda": "gopatha_brahmana"}),
    ]
    hits, _ = devanagari_lexical_hits("Who was Janaka?", docs, top_k=5)
    hit_texts = [d.page_content for d in hits]
    assert any("BĀU 3.1.1" in t for t in hit_texts)
    assert any("AB 7.34.9" in t for t in hit_texts)
    assert not any("AB 6.32.23" in t for t in hit_texts)
    assert not any("GB 2.6.12" in t for t in hit_texts)


# ── 9. Tranche 2 Sanskrit Library SLP1 conversion & TA Book-10 exclusion ─────

def test_slp1_sanskritlibrary_accent_and_diphthong_conversion():
    from src.utils.citations import convert_slp1_sanskritlibrary_to_devanagari, find_visarga_bugs, strip_vedic_accents
    from src.utils.pronunciation import assert_accents_preserved, clean_for_speech

    # 1. Accented F -> short ṛ́ (f/), genuine long F (pitFn, nF\n, BartF\Ri) kept as ṝ
    assert convert_slp1_sanskritlibrary_to_devanagari("kFttikAH", accented=True) == "कृ॑त्तिकाः"
    assert convert_slp1_sanskritlibrary_to_devanagari("bFhaspa/tiS", accented=True) == "बृ॑हस्प॑तिश्"
    assert convert_slp1_sanskritlibrary_to_devanagari("pitFRA/M", accented=True) == "पितॄणा॑ं"
    assert convert_slp1_sanskritlibrary_to_devanagari("pitFn", accented=True) == "पितॄन्"
    assert convert_slp1_sanskritlibrary_to_devanagari("pitF\\n", accented=True) == "पितॄ॒न्"
    assert convert_slp1_sanskritlibrary_to_devanagari("pitFBiH", accented=True) == "पितृ॑भिः"

    # 2. Split accented diphthongs a/i, a/u -> atomic वै॑, तौ॑, द्यौ॑ः
    assert convert_slp1_sanskritlibrary_to_devanagari("va/i", accented=True) == "वै॑"
    assert convert_slp1_sanskritlibrary_to_devanagari("ta/u", accented=True) == "तौ॑"
    assert convert_slp1_sanskritlibrary_to_devanagari("dya/uH", accented=True) == "द्यौ॑ः"

    # 3. Anusvāra [\x7f], JUB inline [ ], hiatus [_], and SLP1 word-final visarga typo h -> H
    assert convert_slp1_sanskritlibrary_to_devanagari("CandA[\x7f]si", accented=False) == "छन्दांसि"
    assert convert_slp1_sanskritlibrary_to_devanagari("ka[ ]sAya", accented=False) == "कंसाय"
    assert convert_slp1_sanskritlibrary_to_devanagari("bra/hma BU/r Bu/vaH su/vah ..", accented=True).startswith("ब्र॑ह्म भू॑र् भु॑वः सु॑वः")

    sample = "bra/hma BU/r Bu/vaH su/vah .. sa/rvA/n kA/mA/n ."
    dev = convert_slp1_sanskritlibrary_to_devanagari(sample, accented=True)
    full_line = f"{dev} ॥ TB 3.7.6.57 ॥"
    assert find_visarga_bugs(full_line) == []
    assert_accents_preserved(full_line, clean_for_speech(full_line))
    assert "ब्रह्म भूर् भुवः सुवः" in strip_vedic_accents(dev)


def test_ta_book10_excluded():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    ta_units_path = root / "local_store" / "ta" / "ta_units.json"
    ta_src_path = root / "knowledge_store" / "sources" / "taittiriya_aranyaka.json"
    assert ta_units_path.exists() and ta_src_path.exists()

    units = json.loads(ta_units_path.read_text(encoding="utf-8"))
    assert len(units) >= 100
    for cite, txt in units.items():
        assert not cite.startswith("TA 10."), f"Book 10 leaked: {cite}"
        prap = int(cite.split()[1].split(".")[0])
        assert 1 <= prap <= 9
        assert "नारायणाय विद्महे" not in txt

    src_meta = json.loads(ta_src_path.read_text(encoding="utf-8"))
    assert src_meta["book_10_excluded"] is True
    assert "prapathaka_sources" in src_meta
    assert "10_mahanarayana" in src_meta["prapathaka_sources"]


def test_tranche2_dryrun_zero_oversize_and_visarga():
    import json
    from pathlib import Path
    from src.utils.citations import find_visarga_bugs, has_vedic_accents, strip_vedic_accents

    root = Path(__file__).resolve().parent.parent
    for folder, expect_accented_books in [("tb", None), ("jub", set()), ("ta", {1, 4, 5})]:
        wpath = root / "local_store" / folder / f"{folder}_windows.jsonl"
        assert wpath.exists(), f"Missing dry-run windows: {wpath}"
        lines = [json.loads(ln) for ln in wpath.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) > 0
        all_text = "\n".join(rec["page_content"] for rec in lines)
        assert find_visarga_bugs(all_text) == []
        for rec in lines:
            pc = rec["page_content"]
            ts = rec["metadata"]["text_search"]
            assert not has_vedic_accents(ts), f"Accent leaked into text_search for {rec['metadata']['citation']}"
            assert strip_vedic_accents(pc) == ts
            if expect_accented_books is None:
                assert has_vedic_accents(pc), f"Expected accent in TB window: {rec['metadata']['citation']}"
            elif expect_accented_books:
                prap = int(rec["metadata"]["citation"].split()[1].split(".")[0])
                if prap in expect_accented_books:
                    assert has_vedic_accents(pc), f"Expected accent in TA book {prap}: {rec['metadata']['citation']}"


def test_itrans_ta_accent_conversion_and_exclusions():
    import json
    from pathlib import Path
    from src.utils.citations import (
        convert_itrans_ta_to_devanagari,
        find_visarga_bugs,
        has_vedic_accents,
        strip_vedic_accents,
    )
    from src.utils.pronunciation import assert_accents_preserved, clean_for_speech

    sample = r"Apa'mApAma\`paH sarvA\"H | su\`varNa\`{\m+}\` hastA\'dA\`dadA\'nA"
    dev = convert_itrans_ta_to_devanagari(sample)
    assert "\u0951" in dev, "udātta ॑ missing"
    assert "\u0952" in dev, "anudātta ॒ missing"
    assert "\u1CDA" in dev, "dīrgha-svarita ᳚ missing"
    assert not has_vedic_accents(strip_vedic_accents(dev))
    full_line = f"{dev} ॥ TA 6.1.3 ॥"
    assert find_visarga_bugs(full_line) == []
    assert_accents_preserved(full_line, clean_for_speech(full_line))

    root = Path(__file__).resolve().parent.parent
    ta_units = json.loads((root / "local_store" / "ta" / "ta_units.json").read_text(encoding="utf-8"))
    praps = {int(c.split()[1].split(".")[0]) for c in ta_units}
    assert praps == set(range(1, 10)), f"Expected full TA Books 1–9, got {sorted(praps)}"
    assert 10 not in praps and 0 not in praps
    joined_plain = strip_vedic_accents(" ".join(ta_units.values()))
    assert "नारायणाय विद्महे" not in joined_plain
    assert "एकाग्निकाण्ड" not in joined_plain
    assert "प्रसुग्मन्ता धियसानस्य" not in joined_plain
    assert "दीधियुर्नर" not in joined_plain


def test_unaccented_query_matches_accented_tb_verse():
    import json
    from pathlib import Path
    from src.utils.citations import has_vedic_accents
    from src.utils.devanagari_lexical import devanagari_lexical_hits

    root = Path(__file__).resolve().parent.parent
    tb_rows = [
        json.loads(ln)
        for ln in (root / "local_store" / "tb" / "tb_windows.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    tb_docs = [Document(page_content=r["page_content"], metadata=r["metadata"]) for r in tb_rows]
    # Unaccented Devanāgarī query must match accented TB 1.1.2.6 via text_search
    hits, _ = devanagari_lexical_hits("कृत्तिकास्व् अग्निम् आदधीत", tb_docs, top_k=5)
    assert hits, "Expected unaccented query to match accented TB verse"
    assert any(d.metadata.get("citation") == "TB 1.1.2.6" for d in hits)
    tb_hit = next(d for d in hits if d.metadata.get("citation") == "TB 1.1.2.6")
    assert has_vedic_accents(tb_hit.page_content)
    assert not has_vedic_accents(tb_hit.metadata["text_search"])


def test_gazetteer_disambiguation_and_bhagiratha():
    from src.utils.devanagari_lexical import devanagari_lexical_hits, query_terms

    # 1. Bhagiratha variant भगेरथ matches JUB 4.6.1
    assert "भगेरथ" in query_terms("Who was Bhagiratha?")
    jub_doc = Document(page_content="भगेरथो हैक्ष्वाको राजा कामप्रेण यज्ञेन ॥ JUB 4.6.1 ॥", metadata={"veda": "jaiminiya_upanisad_brahmana"})
    hits, _ = devanagari_lexical_hits("Bhagiratha", [jub_doc], top_k=3)
    assert len(hits) == 1

    # 2. Ambiguous names must NOT match common-noun contexts
    samples = [
        Document(page_content="सविता वशे मम ॥ AVP 1.40.1 ॥", metadata={"veda": "atharvaveda_paippalada"}),
        Document(page_content="यथा चिद्वशो अश्व्यः पृथुश्रवसि ॥ RV 8.046.21 ॥", metadata={"veda": "rigveda"}),
        Document(page_content="सर्वम् आयुर् एति य एवं वेद ॥ AB 1.5.6 ॥", metadata={"veda": "aitareya_brahmana"}),
        Document(page_content="पुरूरवा वा ऐड उर्वशीम् अविन्दत तस्या आयुर् अजायत ॥ MS 1.6.12 ॥", metadata={"veda": "maitrayani_samhita"}),
        Document(page_content="दिशः पार्श्वे अवान्तरदिशः पर्शव ऋतवो ॥ BĀU 1.1.1 ॥", metadata={"veda": "brihadaranyaka_upanisad"}),
        Document(page_content="पर्शुर्ह नाम मानवी साकं ससूव विंशतिम् ॥ RV 10.086.23 ॥", metadata={"veda": "rigveda"}),
        Document(page_content="कश्यपाय काश्यप ऋश्यशृङ्गाय ॥ JUB 3.7.3 ॥", metadata={"veda": "jaiminiya_upanisad_brahmana"}),
        Document(page_content="स होवाचाजातशत्रुं काश्यं ब्रह्म ते ब्रवाणीति ॥ BĀU 2.1.1 ॥", metadata={"veda": "brihadaranyaka_upanisad"}),
        Document(page_content="तद् एतत् त्रिशलं त्रिपूरुषम् ॥ TB 1.5.10.47 ॥", metadata={"veda": "taittiriya_brahmana"}),
        Document(page_content="भाग्जेष्म पूरुं विदथे मृध्रवाचम् ॥ RV 7.018.13 ॥", metadata={"veda": "rigveda"}),
    ]
    for query, good_cite, bad_cite in [
        ("Who was Vasa Asvya?", "RV 8.046.21", "AVP 1.40.1"),
        ("Who was Ayu?", "MS 1.6.12", "AB 1.5.6"),
        ("Who is Parsu?", "RV 10.086.23", "BĀU 1.1.1"),
        ("Tell me about Kasi kings", "BĀU 2.1.1", "JUB 3.7.3"),
        ("Tell me about the Puru tribe", "RV 7.018.13", "TB 1.5.10.47"),
    ]:
        h, _ = devanagari_lexical_hits(query, samples, top_k=10)
        cites = [d.page_content for d in h]
        assert any(good_cite in c for c in cites), f"{query!r} missed {good_cite}"
        assert not any(bad_cite in c for c in cites), f"{query!r} falsely matched {bad_cite}"


def test_nonrv_pinned_lookup_jub_and_ta():
    from src.sanskrit_tutor_frontend import SanskritTutorApp
    from src.utils.citations import strip_vedic_accents

    app = SanskritTutorApp.__new__(SanskritTutorApp)

    jub_res = app._lookup_nonrv_verse("What does JUB 4.6.1 say?")
    assert jub_res is not None
    assert jub_res["citation"] == "JUB 4.6.1"
    assert "भगेरथ" in jub_res["text"]

    tb_res = app._lookup_nonrv_verse("What does TB 3.10.9.31 say?")
    assert tb_res is not None
    assert tb_res["citation"] == "TB 3.10.9.31"
    tb_plain = strip_vedic_accents(tb_res["text"])
    assert "जनको" in tb_plain or "विदेह" in tb_plain

    ta4_res = app._lookup_nonrv_verse("Explain TA 4.1")
    assert ta4_res is not None
    assert ta4_res["citation"] == "TA 4.1"
    assert "TA 4.1" in ta4_res["text"]

    ta6_res = app._lookup_nonrv_verse("Explain TA 6.1.1")
    assert ta6_res is not None
    assert ta6_res["citation"] == "TA 6.1.1"
    assert "TA 6.1.1" in ta6_res["text"]


def test_videha_matches_vaideha_in_tb():
    from src.utils.devanagari_lexical import devanagari_lexical_hits, query_terms

    terms = query_terms("Janaka Videha")
    assert "जनको" in terms and "वैदेह" in terms
    tb_doc = Document(
        page_content="जनको॑ ह वै॑देहः । अहोरात्रै॑ः समा॑जगाम ॥ TB 3.10.9.31 ॥",
        metadata={
            "veda": "taittiriya_brahmana",
            "citation": "TB 3.10.9.31",
            "text_search": "जनको ह वैदेहः । अहोरात्रैः समाजगाम ॥ TB 3.10.9.31 ॥",
        },
    )
    hits, _ = devanagari_lexical_hits("Janaka Videha", [tb_doc], top_k=3)
    assert len(hits) == 1
    assert hits[0].metadata["citation"] == "TB 3.10.9.31"


def test_retriever_unfiltered_query_unchanged_by_strict_rescue_fix(monkeypatch):
    from types import SimpleNamespace
    from src.utils import devanagari_lexical as dl
    from src.utils.retriever import HybridRetriever

    docs = [
        Document(page_content="तद् एतद् ऋक् ॥ RV 1.1.1 ॥", metadata={"veda": "rigveda", "citation": "RV 1.1.1"}),
        Document(page_content="जनको ह वैदेहः ॥ TB 3.10.9.31 ॥", metadata={"veda": "taittiriya_brahmana", "citation": "TB 3.10.9.31"}),
        Document(page_content="जनको ह वैदेहः ॥ BĀU 3.1.1 ॥", metadata={"veda": "brihadaranyaka_upanisad", "citation": "BĀU 3.1.1"}),
    ]
    captured = []

    def fake_hits(q, dlist, top_k=5):
        captured.append((q, [d.metadata.get("veda") for d in dlist]))
        return [], []

    monkeypatch.setattr(dl, "devanagari_lexical_hits", fake_hits)
    r = HybridRetriever.model_construct(
        semantic_retriever=SimpleNamespace(invoke=lambda _: []),
        keyword_retriever=SimpleNamespace(invoke=lambda _: [], docs=docs),
        vec_db=None,
        mw_helper=None,
        k=10,
    )

    # 1. Query WITHOUT a source filter must pass all corpus docs & query unchanged (standalone "Brahmana" preserved)
    q_unfiltered = "Who was Janaka Brahmana?"
    r._get_relevant_documents(q_unfiltered)
    assert captured[-1][0] == q_unfiltered
    assert len(captured[-1][1]) == 3

    # 2. Query WITH a strict single-corpus filter restricts corpus_docs and strips multi-word corpus title
    r._get_relevant_documents("Janaka Videha in Taittiriya Brahmana")
    assert "taittiriya" not in captured[-1][0].lower() and "brahmana" not in captured[-1][0].lower()
    assert captured[-1][1] == ["taittiriya_brahmana"]


def test_lat_word_unicode_diacritics_and_combining_marks():
    from src.utils.devanagari_lexical import _extract_latin_words, query_terms

    # Test both NFC and NFD (combining marks) for Pūru, Ṛgveda, Sudās, Aśvattha
    nfd_samples = {
        "Pūru": "Pu\u0304ru",
        "Ṛgveda": "R\u0323gveda",
        "Sudās": "Suda\u0304s",
        "Aśvattha": "As\u0301vattha",
    }
    for nfc, nfd in nfd_samples.items():
        assert _extract_latin_words(f"About {nfc} and देव") == ["About", nfc, "and"]
        assert _extract_latin_words(f"About {nfd} and देव") == ["About", nfc, "and"]

    terms_rg = query_terms("Where are the dwellings of the Pūru described in the Ṛgveda?")
    assert "पूरवे" in terms_rg
    assert not any("ऋग्व" in t or "र्ग्व" in t for t in terms_rg)

    terms_sudas = query_terms("Who was Sudās?")
    assert "सुदास" in terms_sudas

    terms_asv = query_terms("Role of Aśvattha")
    assert any("अश्वत्थ" in t for t in terms_asv)






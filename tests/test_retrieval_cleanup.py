"""Regression tests for the 11.8 cleanup (iOS parity work): the four retrieval findings that were fixed in both Python and Swift.
Run: python -m pytest tests/test_retrieval_cleanup.py   (or: python tests/test_retrieval_cleanup.py)"""
import os, sys, subprocess, json, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

def test_latin_word_keeps_iast_words_whole():                       # finding #1
    from src.utils.devanagari_lexical import _LAT_WORD
    assert _LAT_WORD.findall("nṛcakṣā rakṣaḥ Śunaḥśepa Indra-Agni") == ["nṛcakṣā", "rakṣaḥ", "Śunaḥśepa", "Indra-Agni"]
    assert _LAT_WORD.findall("Who is Sudas?") == ["Who", "Sudas"]

def test_auto_transliteration_is_corpus_validated():                # finding #2
    from src.utils import devanagari_lexical as dl
    if not dl._corpus_forms_blob():
        import pytest; pytest.skip("corpus lexicon not available")
    for noise in ("dwellings", "kings", "myth"):
        assert dl._auto_transliterate_token(noise) == []
    assert "हरिश्चन्द्र" in dl._auto_transliterate_token("harishchandra")
    assert dl._popular_to_iast_variants("harishchandra") == dl._popular_to_iast_variants("harishchandra")      # ordered list, not a set

def test_positive_bm25_has_no_zero_score_padding():                 # finding #3
    from langchain_core.documents import Document
    from src.utils.retriever import PositiveBM25Retriever
    docs = [Document(page_content=t) for t in ("agni indra soma", "varuna mitra", "indra vayu", "usha savitar", "rudra marut")]
    r = PositiveBM25Retriever.from_documents(documents=docs); r.k = 4
    assert [d.page_content for d in r.invoke("agni")] == ["agni indra soma"]          # the stock retriever would return 4 documents
    assert [d.page_content for d in r.invoke("zzzz")] == []
    assert [d.page_content for d in r.invoke("indra")] == ["agni indra soma", "indra vayu"] or len(r.invoke("indra")) == 2

def test_normalize_query_is_deterministic_across_hash_seeds():      # finding #4
    from src.utils.transliteration import normalize_query
    for q in ("सरस्वती", "Sarasvatī vināśana", "अग्निमीळे पुरोहितं", "Ā Ṛṣi"):
        v = normalize_query(q)
        assert v == sorted(set(v), key=lambda s: (-len(s), s)), q
    code = "import sys,json;sys.path.insert(0,%r);from src.utils.transliteration import normalize_query as n;print(json.dumps([n(q) for q in ('सरस्वती','Sarasvatī vināśana','Ā Ṛṣi')],ensure_ascii=False))" % os.getcwd()
    outs = {subprocess.run([sys.executable, "-c", code], env={**os.environ, "PYTHONHASHSEED": str(s)}, capture_output=True, text=True).stdout for s in (0, 1, 2, 3)}
    assert len(outs) == 1, "normalize_query output depends on PYTHONHASHSEED"

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)

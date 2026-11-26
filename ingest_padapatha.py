#!/usr/bin/env python3
"""
ingest_padapatha.py — VedaWeb / Zurich (Lubotsky) glossed Rigveda → LOCAL sidecars.

Source : The morphologically glossed Rigveda — Zurich annotation corpus, hosted by
         VedaWeb.  Zenodo concept DOI 10.5281/zenodo.8410655, CC-BY 4.0
         (attribution required — see NOTICE).  Fetched from the real source, md5-verified.
Writes : knowledge_store/padapatha_rv.json   per-verse Lubotsky pāda text + padapāṭha forms
         knowledge_store/morphology_rv.json  per-verse token table (form, lemma, morph tags)
         knowledge_store/lemma_index_rv.json local lemma ⇄ inflected-form index (Devanāgarī)
NEVER writes to Qdrant and never touches the BM25 pickle (the sidecars are a separate,
local layer; the verse collection is unchanged, so "two indexes, one truth" is unaffected).

    python ingest_padapatha.py --dry-run        # download + parse + validate + stats, write nothing
    python ingest_padapatha.py                  # write the three sidecars
    python ingest_padapatha.py --xlsx PATH      # use an already-downloaded file (md5 still checked)

Alignment is validated against local_store/rNN/rNN.md (`॥ M.SSS.VV ॥` markers) before
anything is written; the script aborts if the verse-ID sets differ.
"""
import argparse
import collections
import hashlib
import json
import re
import sys
import tempfile
import unicodedata
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KS = ROOT / "knowledge_store"
CONCEPT_DOI = "10.5281/zenodo.8410655"
RECORD_API = "https://zenodo.org/api/records/8410655"
FILE_KEY = "vedaweb_zurich.xlsx"

# ───────────────────────── minimal stdlib xlsx reader ─────────────────────────
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _col(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx_rows(path):
    z = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
            ss.append("".join(t.text or "" for t in si.iter("{%s}t" % _NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    first = wb.find("m:sheets", _NS)[0]
    tgt = rels[first.get("{%s}id" % _RNS)].lstrip("/")
    tgt = tgt if tgt.startswith("xl/") else "xl/" + tgt
    for _, el in ET.iterparse(z.open(tgt)):
        if el.tag == "{%s}row" % _NS["m"]:
            row = {}
            for c in el.findall("m:c", _NS):
                v, t = c.find("m:v", _NS), c.get("t")
                if t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter("{%s}t" % _NS["m"]))
                elif v is None:
                    continue
                elif t == "s":
                    val = ss[int(v.text)]
                else:
                    val = v.text
                row[_col(c.get("r"))] = val
            yield [row.get(i) for i in range(max(row) + 1)] if row else []
            el.clear()


# ───────────────────────── fetch + verify ─────────────────────────

def fetch(workdir: Path) -> Path:
    """Download the xlsx from Zenodo (latest version of the concept record), verify md5."""
    with urllib.request.urlopen(RECORD_API, timeout=60) as r:
        rec = json.load(r)
    f = next(f for f in rec["files"] if f["key"] == FILE_KEY)
    out = workdir / FILE_KEY
    print(f"downloading {FILE_KEY} ({f['size']:,} bytes) from record {rec['doi']} …")
    urllib.request.urlretrieve(f["links"]["self"], out)
    verify_md5(out, f["checksum"].split(":", 1)[1])
    return out


def verify_md5(path: Path, expected: str):
    h = hashlib.md5(path.read_bytes()).hexdigest()
    if expected and h != expected:
        sys.exit(f"md5 mismatch for {path}: {h} != {expected}")
    print(f"md5 ok: {h}")
    return h


# ───────────────────────── romanisation → Devanāgarī (unaccented) ─────────────────────────
_ACCENTS = "́̀̍̂́"
_CONS = {"kh": "ख", "gh": "घ", "ch": "छ", "jh": "झ", "ṭh": "ठ", "ḍh": "ढ", "th": "थ", "dh": "ध",
         "ph": "फ", "bh": "भ", "k": "क", "g": "ग", "ṅ": "ङ", "c": "च", "j": "ज", "ñ": "ञ", "ṭ": "ट",
         "ḍ": "ड", "ṇ": "ण", "t": "त", "d": "द", "n": "न", "p": "प", "b": "ब", "m": "म", "y": "य",
         "r": "र", "l": "ल", "v": "व", "ś": "श", "ṣ": "ष", "s": "स", "h": "ह", "ḷ": "ळ"}
_VOW = {"ai": ("ऐ", "ै"), "au": ("औ", "ौ"), "a": ("अ", ""), "ā": ("आ", "ा"), "i": ("इ", "ि"),
        "ī": ("ई", "ी"), "u": ("उ", "ु"), "ū": ("ऊ", "ू"), "ṛ": ("ऋ", "ृ"), "ṝ": ("ॠ", "ॄ"),
        "ḹ": ("ॡ", "ॣ"), "e": ("ए", "े"), "o": ("ओ", "ो"), "l̥": ("ऌ", "ॢ")}
_ORDER_C = sorted(_CONS, key=len, reverse=True)
_ORDER_V = sorted(_VOW, key=len, reverse=True)


def roman_to_deva(s: str) -> str:
    """Lubotsky romanisation → unaccented Devanāgarī. Accents are dropped here ONLY because the
    output feeds the (unaccented) corpus lexicon; the accented Roman form is always stored too."""
    s = unicodedata.normalize("NFD", s or "")
    s = s.replace("ś", "ś").replace("Ś", "Ś")
    s = s.replace("r̥", "ṛ").replace("l̥", "ḷ").replace("m̐", "ṃ")
    s = "".join(c for c in s if c not in _ACCENTS)
    s = unicodedata.normalize("NFC", s).lower().replace("ṁ", "ṃ")
    out, i, n = [], 0, len(s)
    while i < n:
        ch = s[i]
        c = next((k for k in _ORDER_C if s.startswith(k, i)), None)
        if c:
            out.append(_CONS[c]); i += len(c)
            v = next((k for k in _ORDER_V if s.startswith(k, i)), None)
            if v:
                out.append(_VOW[v][1]); i += len(v)
            else:
                out.append("्")
            continue
        v = next((k for k in _ORDER_V if s.startswith(k, i)), None)
        if v:
            out.append(_VOW[v][0]); i += len(v); continue
        if ch == "ṃ": out.append("ं")
        elif ch == "ḥ": out.append("ः")
        elif ch == "'": out.append("ऽ")
        i += 1
    return "".join(out)


# ───────────────────────── tag normalisation (German → English codes) ─────────────────────────
_TAG = {"Nom.": "nom", "Akk.": "acc", "Gen.": "gen", "Dat.": "dat", "Instr.": "instr", "Lok.": "loc",
        "Vok.": "voc", "Abl.": "abl", "Sg.": "sg", "Du.": "du", "Pl.": "pl",
        "Präs.": "pres", "Aor.": "aor", "Perf.": "perf", "Imperf.": "impf", "Pluperf.": "plupf",
        "Fut.": "fut", "Ind.": "ind", "Konj.": "subj", "Opt.": "opt", "Ipv.": "impv", "si-Ipv.": "si-impv",
        "Inj.": "inj", "Prek.": "prec", "Kond.": "cond", "akt.": "act", "med.": "mid", "pass.": "pass",
        "Ptz.": "ptcp", "ta-Ptz.": "ta-ptcp", "na-Ptz.": "na-ptcp", "Inf.": "inf", "Gdv.": "gdv",
        "Abs.": "abs", "Kaus.": "caus", "Den.": "denom", "Int.": "intens", "Des.": "desid",
        "sup.": "superl", "comp.": "compar", "LP": "local-particle",
        "Nominalstamm": "nominal", "Wurzel": "root", "Invariabile": "indecl", "Pronomen": "pronoun",
        "nominal stem": "nominal"}


def tag(v):
    if v is None or v == "":
        return None
    parts = [p.strip() for p in str(v).split("/")]
    return "/".join(_TAG.get(p, p) for p in parts)  # unknown tags pass through verbatim, never dropped


def lemma_deva(lem: str):
    """LEMMA_ZÜRICH 'agní-' → 'अग्नि'; '√īḍ- ~ īḷ-' → 'ईड्' (first variant, root marker/hyphens removed)."""
    if not lem:
        return None
    first = lem.split("~")[0].strip()
    first = re.sub(r"\(.*?\)", "", first).replace("√", "").strip(" -")
    first = re.sub(r"[^\ẁ-̥ͯ]", "", first, flags=re.U)
    return roman_to_deva(first) or None


# ───────────────────────── corpus side (for alignment) ─────────────────────────

def corpus_ids():
    ids = {}
    for m in range(1, 11):
        txt = (ROOT / "local_store" / f"r{m:02d}" / f"r{m:02d}.md").read_text(encoding="utf-8")
        for line in txt.split("\n"):
            mk = re.search(r"॥\s*(?:RV\s*)?(\d+)\.(\d+)\.(\d+)\s*॥\s*$", line)
            if mk:
                ids[tuple(int(x) for x in mk.groups())] = True
    return ids


def vid_str(v):
    return "%d.%03d.%02d" % v


# ───────────────────────── main ─────────────────────────

def parse(xlsx: Path):
    it = read_xlsx_rows(xlsx)
    hdr = next(it)
    ix = {h: i for i, h in enumerate(hdr)}

    def g(r, k):
        i = ix.get(k)
        return r[i] if i is not None and i < len(r) and r[i] not in (None, "") else None

    verses = collections.OrderedDict()
    for r in it:
        if not r or not g(r, "VERS_NR"):
            continue
        mm = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", g(r, "VERS_NR"))
        if not mm:
            sys.exit(f"unparsable VERS_NR {g(r, 'VERS_NR')!r}")
        vid = tuple(int(x) for x in mm.groups())
        v = verses.setdefault(vid, {"padas": collections.OrderedDict(), "toks": []})
        v["padas"].setdefault(g(r, "PADA_NR"), g(r, "PADA_TEXT_LUBOTSKY"))
        tok = r_to_tok(r, g)
        tok["_dv"] = roman_to_deva(tok["f"]) if tok.get("f") else None   # build-time only
        tok["_gl"] = g(r, "LEMMA_ZÜRICH_BEDEUTUNG")                       # build-time only
        v["toks"].append(tok)
    return verses


def r_to_tok(r, g):
    form = g(r, "FORM")
    lem = g(r, "LEMMA_ZÜRICH")
    tok = {"n": int(float(g(r, "TOKEN_NR_VERS") or 0)), "pd": g(r, "PADA_NR"), "f": form,
           "l": lem, "ld": lemma_deva(lem),
           "lt": tag(g(r, "LEMMA_ZÜRICH_LEMMATYP"))}
    for key, col in (("c", "KASUS"), ("g", "GENUS"), ("nu", "NUMERUS"), ("p", "PERSON"), ("t", "TEMPUS"),
                     ("mo", "MODUS"), ("vo", "DIATHESE"), ("nf", "INFINIT"), ("dr", "ABGELEITETE_KONJUGATION"),
                     ("gr", "GRADUS"), ("lp", "LOKALPARTIKEL")):
        v = tag(g(r, col))
        if v:
            tok[key] = v
    for key, col in (("pc", "PRAESENSKLASSE"), ("wv", "WEITERE_WERTE"),
                     ("km", "KOMMENTAR_ZÜRICH"), ("gid", "LEMMA_GRASSMANN_ID")):
        v = g(r, col)
        if v:
            tok[key] = v
    return {k: v for k, v in tok.items() if v is not None}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="download/parse/validate, write nothing")
    ap.add_argument("--xlsx", help="use this already-downloaded file instead of fetching")
    a = ap.parse_args()

    with tempfile.TemporaryDirectory() as td:
        if a.xlsx:
            xlsx = Path(a.xlsx)
            md5 = verify_md5(xlsx, "")
        else:
            xlsx = fetch(Path(td))
            md5 = hashlib.md5(xlsx.read_bytes()).hexdigest()
        verses = parse(xlsx)

    cids = set(corpus_ids())
    vids = set(verses)
    only_c, only_v = sorted(cids - vids), sorted(vids - cids)
    print(f"verses: corpus={len(cids):,} vedaweb={len(vids):,} corpus-only={len(only_c)} vedaweb-only={len(only_v)}")
    if only_c or only_v:
        print("ALIGNMENT MISMATCH — aborting, nothing written.")
        print("corpus-only:", [vid_str(v) for v in only_c[:30]])
        print("vedaweb-only:", [vid_str(v) for v in only_v[:30]])
        sys.exit(1)

    meta = {"source": "VedaWeb / Zurich morphologically glossed Rigveda (Lubotsky et al.)",
            "doi": CONCEPT_DOI, "license": "CC-BY-4.0", "file": FILE_KEY, "md5": md5,
            "retrieved": date.today().isoformat(),
            "note": "Pāda text is Lubotsky's; token 'f' is the padapāṭha form; 'ld' is the lemma in "
                    "unaccented Devanāgarī (lexicon key; lemma_index_rv.json only). German lemma glosses "
                    "(lemma_gloss_de) are Zurich's, stored verbatim and NOT injected into prompts."}
    pad, morph = {}, {}
    f2l = collections.defaultdict(collections.Counter)      # Devanāgarī form -> lemma (Dev)
    l2f = collections.defaultdict(collections.Counter)      # lemma (Dev) -> forms
    ntok = 0
    gloss_de = {}                                            # Zurich lemma -> German meaning (verbatim)
    for vid, v in verses.items():
        k = vid_str(vid)
        toks = sorted(v["toks"], key=lambda t: t["n"])
        ntok += len(toks)
        pad[k] = {"p": [[p, t] for p, t in v["padas"].items()],
                  "f": " ".join(t["f"] for t in toks if t.get("f"))}
        for t in toks:
            dv, gl = t.pop("_dv", None), t.pop("_gl", None)
            if gl and t.get("l"):
                gloss_de.setdefault(t["l"], gl)
            if dv and t.get("ld"):
                f2l[dv][t["ld"]] += 1
                l2f[t["ld"]][dv] += 1
        morph[k] = toks
    lemma_index = {"forms_to_lemmas": {f: [l for l, _ in c.most_common()] for f, c in f2l.items()},
                   "lemmas_to_forms": {l: [f for f, _ in c.most_common()] for l, c in l2f.items()},
                   "lemma_gloss_de": gloss_de}
    print(f"tokens={ntok:,}  distinct forms={len(f2l):,}  distinct lemmas={len(l2f):,}")
    probe = "पूरवे"
    print(f"probe {probe}: lemmas={lemma_index['forms_to_lemmas'].get(probe)}")

    if a.dry_run:
        print("dry run — nothing written.")
        return
    KS.mkdir(exist_ok=True)
    for name, obj in (("padapatha_rv.json", {"_meta": meta, "verses": pad}),
                      ("morphology_rv.json", {"_meta": meta, "verses": morph}),
                      ("lemma_index_rv.json", {"_meta": meta, **lemma_index})):
        p = KS / name
        p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"wrote {p.relative_to(ROOT)}  {p.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()

# Corpus Citation Formats, Payload Schema & Layer-5 Code Audit

**Branch:** `corpus-expansion` (cut from `translation-fixes @ 9a06367`)  
**Status:** **APPROVED by owner (2026-11-23)** — single `chronology_name = "brahmana_prose"` across all Layer 4 texts; `docs/ios_data_licensing.md` copied from `ios-portable`; diachronic map added at `docs/vedic_geography_diachronic_map_v2_6.html`.

---

## 1. Proposed Citation Formats & Chronology Layers

Each text uses its edition's native numbering inside Devanāgarī double-daṇḍa markers (`॥ <PREFIX> <NUMBERS> ॥`), unpadded except for existing Ṛgveda files (`M.SSS.VV`). Exact sub-unit depth for texts marked *confirm on fetch* will be verified against the downloaded edition during each tranche's `--dry-run` before any upload.

### Existing Indexed Texts (reference — untouched in Qdrant)

| Text | `veda` payload | Canonical marker | Layer | `chronology_name` | `source_type` |
|---|---|---|---|---|---|
| Ṛgveda Saṃhitā (Maṇḍalas 2–7) | `rigveda` | `॥ M.SSS.VV ॥` (`RV M.SSS.VV`) | 1 | `early_rigveda` | `vedic_text` |
| Ṛgveda Saṃhitā (Maṇḍalas 1, 8–10) | `rigveda` | `॥ M.SSS.VV ॥` (`RV M.SSS.VV`) | 2 | `late_rigveda` | `vedic_text` |
| Atharvaveda Śaunaka | `atharvaveda_shaunaka` | `॥ AVŚ K.H.V ॥` | 3 | `av_samhita` | `vedic_text` |
| Vājasaneyi Saṃhitā | `vajasaneyi_samhita` | `॥ VS A.V ॥` | 2\* | `samhita` | `vedic_text` |
| Taittirīya Saṃhitā | `taittiriya_samhita` | `॥ TS K.P.A.V ॥` | 2\* | `samhita` | `vedic_text` |
| Aitareya Brāhmaṇa | `aitareya_brahmana` | `॥ AB P.A.S ॥` | 4 | `brahmana_prose` | `vedic_text` |
| Pañcaviṃśa Brāhmaṇa | `pancavimsa_brahmana` | `॥ PB K.A.V ॥` | 4 | `brahmana_prose` | `vedic_text` |
| Śatapatha Brāhmaṇa (Mādhyandina, excl. Book 12) | `shatapatha_brahmana` | `॥ SB K.A.B.V ॥` | 4 | `brahmana_prose` | `vedic_text` |

*\*Note: `ingest_vajasaneyi_samhita.py:381` and `ingest_taittiriya_samhita.py:492` wrote `chronology_layer: 2` (`samhita`) to Qdrant, whereas `CLAUDE.md` groups VS and TS with Layer 3. Per Rule 3 (additive-only writes), existing Qdrant points will not be modified.*

### New Texts (Tranches 1–2 + Tranche 3 provisional)

| Tranche | Text | `veda` payload | `local_store/` dir | Canonical marker | Native numbering | Layer | `chronology_name` | `source_type` | Special notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Maitrāyaṇī Saṃhitā | `maitrayani_samhita` | `local_store/ms/` | `॥ MS K.P.A ॥` (e.g. `॥ MS 1.6.3 ॥`) | `Kāṇḍa.Prapāṭhaka.Anuvāka` (or `.Sentence` if numbered in GRETIL; confirm on fetch) | 3 | `yv_samhita` | `vedic_text` | Accented source → keep svaras in `text`, strip in `text_search` |
| 1 | Atharvaveda Paippalāda | `atharvaveda_paippalada` | `local_store/avp/` | `॥ AVP K.H.V ॥` (e.g. `॥ AVP 1.1.1 ॥`) | `Kāṇḍa.Sūkta.Stanza` | 3 | `av_samhita` | `vedic_text` | Accented where present → `text` + `text_search` |
| 1 | Kauṣītaki Brāhmaṇa | `kausitaki_brahmana` | `local_store/kb/` | `॥ KB A.K ॥` (e.g. `॥ KB 2.1 ॥`) | `Adhyāya.Khaṇḍa` (confirm sub-numbering on fetch) | 4 | `brahmana_prose` | `vedic_text` | Alias: Śāṅkhāyana Brāhmaṇa |
| 1 | Gopatha Brāhmaṇa | `gopatha_brahmana` | `local_store/gb/` | `॥ GB B.P.K ॥` (e.g. `॥ GB 1.1.1 ॥`) | `Bhāga(1=Pūrva, 2=Uttara).Prapāṭhaka.Kaṇḍikā` | 4 | `brahmana_prose` | `vedic_text` | `chronology_note="late Brāhmaṇa"` |
| 1 | Bṛhadāraṇyaka Upaniṣad (Kāṇva) | `brihadaranyaka_upanisad` | `local_store/bau/` | `॥ BĀU A.B.K ॥` (e.g. `॥ BĀU 1.1.1 ॥`) | `Adhyāya.Brāhmaṇa.Kaṇḍikā` | 4 | `brahmana_prose` | `vedic_text` | Kāṇva recension |
| 1 | Chāndogya Upaniṣad | `chandogya_upanisad` | `local_store/chu/` | `॥ ChU P.K.V ॥` (e.g. `॥ ChU 1.1.1 ॥`) | `Prapāṭhaka.Khaṇḍa.Verse` | 4 | `brahmana_prose` | `vedic_text` | |
| 1 | Nirukta (Yāska) | `nirukta` | `local_store/nir/` | `॥ Nir A.K ॥` (e.g. `॥ Nir 1.1 ॥`) | `Adhyāya.Khaṇḍa` (confirm sub-numbering on fetch) | **5** | `sutra_vedanga` | **`commentary`** | **Commentary only — never cited as verse evidence** |
| 2 | Baudhāyana Śrauta Sūtra | `baudhayana_srauta_sutra` | `local_store/bss/` | `॥ BŚS P.K ॥` (e.g. `॥ BŚS 18.44 ॥`) | `Praśna.Khaṇḍa` (confirm sub-numbering in TEI; priority `BŚS 18.44`) | **5** | `sutra_vedanga` | `vedic_text` | Caland / Fushimi / Gippert TEI |
| 2 | Kāṭhaka Saṃhitā | `kathaka_samhita` | `local_store/ks/` | `॥ KS S.A ॥` (e.g. `॥ KS 20.1 ॥`) | `Sthānaka.Anuvāka` (confirm sub-numbering in TEI) | 3 | `yv_samhita` | `vedic_text` | |
| 2 | Jaiminīya Brāhmaṇa | `jaiminiya_brahmana` | `local_store/jb/` | `॥ JB K.S ॥` (e.g. `॥ JB 1.1 ॥`) | `Kāṇḍa.Section` (confirm sub-numbering in TEI) | 4 | `brahmana_prose` | `vedic_text` | |
| 2 | Jaiminīya Upaniṣad Brāhmaṇa | `jaiminiya_upanisad_brahmana` | `local_store/jub/` | `॥ JUB A.An.K.V ॥` (e.g. `॥ JUB 1.1.1.1 ॥`) | `Adhyāya.Anuvāka.Khaṇḍa.Verse` | 4 | `brahmana_prose` | `vedic_text` | |
| 2 | Taittirīya Brāhmaṇa | `taittiriya_brahmana` | `local_store/tb/` | `॥ TB A.P.An.S ॥` (e.g. `॥ TB 1.1.1.1 ॥`) | `Aṣṭaka.Prapāṭhaka.Anuvāka.Section` | 4 | `brahmana_prose` | `vedic_text` | |
| 2 | Taittirīya Āraṇyaka (Books 1–9) | `taittiriya_aranyaka` | `local_store/ta/` | `॥ TA P.A.S ॥` (e.g. `॥ TA 1.1.1 ॥`) | `Prapāṭhaka.Anuvāka.Section` (**Book 10 dropped with assertion**) | 4 | `brahmana_prose` | `vedic_text` | Excludes Book 10 (Mahānārāyaṇa Up.) |
| 3 (prov.) | Kapiṣṭhala-Kaṭha Saṃhitā | `kapisthala_katha_samhita` | `local_store/kaps/` | `॥ KapS A.Adh ॥` (e.g. `॥ KapS 1.1 ॥`) | `Aṣṭaka.Adhyāya` (provisional) | 3 | `yv_samhita` | `vedic_text` | Tranche 3 — report options only |

---

## 2. Canonical Citation Normalization & Collision Rules

### Prefix Normalization Table (input aliases → canonical code)

- `RV`, `Rgveda`, `Rigveda` → `RV`
- `AVŚ`, `AVS`, `AV` → `AVŚ` (internal exclusion key `AVS`)
- `AVP` → `AVP`
- `VS` → `VS`
- `TS` → `TS`
- `MS` → `MS`
- `KS` → `KS`
- `KapS`, `KAPS` → `KapS` *(provisional)*
- `AB` → `AB`
- `PB`, `TMB` → `PB`
- `SB`, `ŚB`, `ŚBM` → `SB`
- `KB`, `ŚB` *(never alias ŚB→KB; Śāṅkhāyana Brāhmaṇa full name only)* → `KB`
- `GB` → `GB`
- `JB` → `JB`
- `JUB` → `JUB`
- `TB` → `TB`
- `TA`, `TĀ` → `TA`
- `BĀU`, `BAU`, `BṛU` → `BĀU`
- `ChU`, `CHU`, `CU` → `ChU`
- `BŚS`, `BSS`, `BaudhŚS` → `BŚS`
- `Nir`, `NIR`, `Nirukta` → `Nir`

### Strict Collision-Avoidance Rules for `_detect_source_text_filter`

The abbreviations **`MS`, `KS`, `TA`, `GB`, `JB`, `TB`, `ChU`, `CU`, `VS`** collide with English words or common abbreviations (`MS Word`, `GB of RAM`, `the TA said`, `TB drive`, `KS` state, `JB` initials, `vs` = versus).

- **Bare abbreviations NEVER trigger `_detect_source_text_filter` on their own** for colliding codes (`MS`, `KS`, `TA`, `GB`, `JB`, `TB`, `ChU`, `CU`, `VS`).
- Instead, `_detect_source_text_filter` accepts them **only** when:
  1. Immediately followed by a citation number: e.g. `(?i)\b(?:MS|KS|TA|TĀ|GB|JB|TB|ChU|BĀU|BAU|BŚS|BSS|AVP|KB|JUB|Nir|VS)\s+\d+(?:\.\d+)+`, **OR**
  2. Matched via unambiguous full/distinctive corpus names (whole-word/phrase): e.g. `"maitrayani"`, `"maitrāyaṇī"`, `"kathaka samhita"`, `"kāṭhaka saṃhitā"`, `"paippalada"`, `"paippalāda"`, `"kausitaki"`, `"kauṣītaki"`, `"sankhayana brahmana"`, `"śāṅkhāyana brāhmaṇa"`, `"gopatha"`, `"jaiminiya brahmana"`, `"jaiminīya brāhmaṇa"`, `"jaiminiya upanisad"`, `"jaiminīya upaniṣad"`, `"taittiriya brahmana"`, `"taittirīya brāhmaṇa"`, `"taittiriya aranyaka"`, `"taittirīya āraṇyaka"`, `"brihadaranyaka"`, `"bṛhadāraṇyaka"`, `"chandogya"`, `"chāndogya"`, `"baudhayana srauta"`, `"baudhāyana śrauta"`, `"nirukta"`.
- Notice also: `"taittiriya"` alone currently maps to `taittiriya_samhita` in `retriever.py:366`! Once `TB` and `TA` exist, `"taittiriya brahmana"` and `"taittiriya aranyaka"` must be matched **before** bare `"taittiriya"` (or bare `"taittiriya"` must exclude `"taittiriya brahmana"` / `"taittiriya aranyaka"`), and `"atharvaveda"` alone without `"paippalada"` should either match both AV recensions or explicitly distinguish `"atharvaveda shaunaka"` vs `"atharvaveda paippalada"`.
- Collision misfire tests to add: `"MS Word"`, `"the TA said"`, `"GB of RAM"`, `"1 TB drive"`, `"KS test"`, `"JB Hi-Fi"`, `"early vs later layers"`.

---

## 3. Payload Schema & Accent Handling (`text` vs `text_search`)

Every new Qdrant point payload will store (under LangChain's `page_content` + `metadata` convention, matching existing points):

```json
{
  "page_content": "<original Devanāgarī WITH svaras preserved verbatim> ॥ MS 1.6.3 ॥",
  "metadata": {
    "title": "Maitrayani Samhita",
    "filename": "ms",
    "preprocessing": "sanskrit",
    "source_type": "vedic_text",          // "commentary" for Nirukta ONLY
    "veda": "maitrayani_samhita",
    "chronology_layer": 3,                // 3, 4, or 5
    "chronology_name": "yv_samhita",      // yv_samhita | av_samhita | brahmana_prose | aranyaka | upanisad | sutra_vedanga
    "chronology_note": null,              // "late Brāhmaṇa" for GB; omitted when unused
    "source_id": "maitrayani_samhita",    // points to knowledge_store/sources/maitrayani_samhita.json
    "licence": "GRETIL (scholarly, non-commercial)",
    "citation": "MS 1.6.3",
    "text": "<original Devanāgarī WITH svaras preserved verbatim> ॥ MS 1.6.3 ॥",
    "text_search": "<accent-stripped Devanāgarī for BM25, lexical rescue, and embedding>"
  }
}
```

### Accent Handling Design
- **Display & grounding (`page_content` / `metadata.text`):** keeps Vedic svara marks (`U+0951`, `U+0952`, `U+1CD0–1CFF`, `U+A8E0–A8FF`) verbatim as in the source. `assert_accents_preserved()` in `src/utils/pronunciation.py` continues to verify that user-visible text never drops svaras.
- **Search & embedding (`metadata.text_search`):** strips **only** Vedic accent combining codepoints (`_ACCENT_CODEPOINTS` in `pronunciation.py`), keeping all consonants, vowel signs, anusvāra, visarga, halanta, and Devanāgarī nuktas intact.
  - **Embeddings:** Qdrant vectors are computed from `text_search` so accented MS/AVP passages live in the exact same embedding space as unaccented RV/TS/VS/AVŚ passages.
  - **BM25 & lexical rescue (`devanagari_lexical.py`, `rebuild_bm25_pickle.py`, `build_corpus_lexicon.py`):** index/scan `metadata.get("text_search") or doc.page_content`, while returning the intact accented `doc.page_content` to synthesis and the UI.

### Sliding-Window Chunking for Oversize Prose Units
- `paraphrase-multilingual-mpnet-base-v2` truncates inputs beyond 128 tokens.
- Any new unit whose `text_search` exceeds 128 encoder tokens is split by `src/utils/windowing.py` into **~120-token sliding windows with ~20 tokens of overlap**, cut strictly at whitespace word boundaries (never inside a Devanāgarī grapheme cluster or word).
- Every window retains the unit's **exact native citation** (`citation: "MS 1.6.3"` — never synthetic suffixes like `MS 1.6.3a`), plus `part` (`0..n_parts-1`), `n_parts`, and its own `text_search`. Full unit text is stored once (`metadata["text"]` on `part == 0` and in `local_store/<dir>/<dir>_units.json`).
- Both Qdrant and BM25 (`local_store/<dir>/<dir>_windows.jsonl`) index the exact same windows. At retrieval, `HybridRetriever._deduplicate_windowed_docs()` deduplicates by `(veda, citation)` keeping the highest-scoring window, and synthesis displays the full native unit centered on the matching window (`center_excerpt_around_window`).
- **Existing corpus note (not modified in this task):** Existing `ŚB`, `AB`, `PB`, and `TS` prose chunks in Qdrant have the same >128-token encoder truncation; per owner direction (2026-11-23), they are left untouched in this task (Rule 3: additive-only writes).

### Commentary Handling (Nirukta: `source_type="commentary"`)
- `source_type="commentary"` in payload and `local_store/nir/nir_metadata.json`.
- **Retrieval (`retriever.py`):**
  - Never let Nirukta occupy primary verse slots in diachronic layer balancing; tag Nirukta chunks explicitly as `[COMMENTARY (Vedāṅga, layer 5 — NOT primary verse evidence): Nirukta — ...]`.
- **Synthesis (`agentic_rag.py`):**
  - Add an explicit instruction in the synthesis prompt: passages marked `[COMMENTARY: Nirukta ...]` are Yāska's later etymological commentary (Vedāṅga, Layer 5) — present them only as traditional commentary/etymology and **never** cite them as primary Vedic verse evidence.
- **Citation formatting (`citation_enhancer.py`):**
  - Prefix Nirukta citations clearly: `Nir 1.1 (Commentary)`.

---

## 4. Complete Layer-5 & Citation-Parser Code Audit

Every code path in the codebase that currently assumes layers 1–4 or hardcodes the 7 existing corpora:

### A. Chronology Layers (1–4 assumptions)

| File | Location | Current behavior | Required change for Layer 5 & new texts |
|---|---|---|---|
| `src/utils/retriever.py` | `L1006–1040` (diachronic mode) | Dynamically groups by `chronology_layer`, takes 4 docs/layer, **tags only `merged_docs[:8]`** (with 5 layers, rank-1 docs beyond index 7 lose `[SOURCE:]` tags; commentary chunks would also mix into verse layers). | Exclude `source_type="commentary"` from primary verse layer slots (append separately labelled as `[COMMENTARY: ...]`); expand tagging window to cover all balanced layers (e.g. up to `SYNTHESIS_DOC_BUDGET = 12`); include `chronology_note` when present (e.g. `GB: late Brāhmaṇa`). |
| `src/utils/agentic_rag.py` | `L792–808` (`diachronic_block`) | Hardcodes layers 1–4 (`"early RV → Brāhmaṇa prose"`, `"layer 4, the latest Vedic period"`). | Update prompt legend to cover all 5 layers: Layer 1 (Early RV 2–7), Layer 2 (Late RV 1, 8–10), Layer 3 (Post-RV Saṃhitās: AVŚ, AVP, VS, TS, MS, KS), Layer 4 (Brāhmaṇas, Āraṇyakas, Early Upaniṣads: AB, PB, SB, KB, GB [late Brāhmaṇa], JB, JUB, TB, TA 1–9, BĀU, ChU), Layer 5 (Sūtra/Vedāṅga: BŚS; plus Nirukta as commentary only). |
| `src/utils/agentic_rag.py` | `L94–130` (`extract_source_texts`), `L952–955` (empty-corpus fallback) | Only maps 4–7 legacy texts (and checks `metadata["source"]` rather than `veda`). | Map all 20 `veda` keys cleanly; distinguish primary texts vs Nirukta commentary. |
| `src/sanskrit_tutor_frontend.py` | `L1074–1075`, `L1098–1111` | Home-screen corpus cards only list Saṃhitās (4) and Brāhmaṇas (3). | Add new Saṃhitās, Brāhmaṇas, Āraṇyaka/Upaniṣads (Layer 4), and Sūtra/Vedāṅga (Layer 5, marking Nirukta as commentary). |
| `create_qdrant_payload_index.py` | `L21–25` | Indexes only `metadata.veda`, `metadata.chronology_name`, `metadata.filename`. | Add `metadata.chronology_layer` (INTEGER) and `metadata.source_type` (KEYWORD) payload indexes. |
| `src/utils/devanagari_lexical.py` | `L83, L129, L300` | Gazetteer sections/comments organized by layers 1–4. | Add Layer 3/4/5 proper-noun sections verified against the new texts; scan `text_search` when present. |
| `docs/vedic_geography_diachronic_map_v2_6.html` | `L317–331`, `L626`, `L744–749` | Filter pills (`L1–L4`), `LAYER_FULL`, and comparison header (`Layers 2–4`) cover only Layers 1–4. | Add `L5 (Sūtra/Vedāṅga)` filter pill, `LAYER_FULL.L5`, and update header to `Layers 2–5`. |
| **iOS bundle (`ios-portable` branch — do not touch here)** | `ios/VedicResource/VedicResource/Retrieval/Models.swift:49–77` | `CorpusNames.label()` has 7 corpora; `CorpusNames.chronologyLabel()` switches only on layers 1–4. | Tracked for future iOS sync (subject to `docs/ios_data_licensing.md` — CC BY-NC-SA / research-only texts cannot enter paid/monetised builds). |
| `ios/tools/export_mobile_bundle.py` (`ios-portable`) | `L47, L51, L222–228` | `EXPECTED_FILES` hardcoded to 16 dirs; `PREFIX` regex lists 6 prefixes; `docs` table lacks `source_id`, `licence`, `chronology_note`, `text_search`. | Tracked for future iOS sync. |

### B. Citation Parsers, Source Filters & Index Sync Scripts

| File | Location | Current behavior | Required change |
|---|---|---|---|
| `src/sanskrit_tutor_frontend.py` | `L1250–1260` (`_NONRV_CORPORA`), `L1356–1357` (RV other-corpus guard), `L1423–1429` (`_extract_verse_ids`) | Hardcodes 6 non-RV prefixes (`AVŚ, VS, TS, AB, PB, SB`) and `local_store` paths. | Add all new prefixes & paths; handle colliding abbreviations strictly (only when followed by digits); update RV guard regex & `_extract_verse_ids`. |
| `src/utils/retriever.py` | `L346–436` (`_detect_source_text_filter`) | Hardcodes 7 corpora; uses bare tokens (`ts`, `ab`, `pb`, `sb`, `av`, `rv`). | Add all new corpora using whole-word full names + digit-anchored abbreviations only for colliding codes (`MS`, `KS`, `TA`, `GB`, `JB`, `TB`, `ChU`, `VS`). Fix `"taittiriya"` vs `TB`/`TA` precedence and `"atharvaveda"` vs `AVŚ`/`AVP`. |
| `src/utils/exclusions.py` | `L31–40` (`_CORPUS_CODES`, `_CIT`) | Only parses 7 corpus codes (`RV, AVŚ/AVS/AV, VS, TS, AB, PB, ŚB/SB/ŚBM`). | Add all new corpus codes so held-out parallel screening and future exclusion entries parse cleanly. (**Do NOT edit the exclusion manifest itself.**) |
| `src/utils/citation_enhancer.py` | `L25–168` (`VedicCitationExtractor`) | Legacy regexes (`RV, VS, PB, SB, Ramayana`); misses `AVŚ, TS, AB` and all 13 new prefixes; ignores `॥ PREFIX N.N ॥` markers and `metadata["citation"]`. | Recognize `metadata["citation"]` and all `॥ <PREFIX> <NUMS> ॥` markers; label `source_type="commentary"` (`Nir`) as commentary. |
| `src/utils/devanagari_lexical.py` | `L498` (`_VERSE_LINE_ID`), `L510, L556, L585` | `_VERSE_LINE_ID` only matches bare RV `॥ \d+\.\d+\.\d+ ॥`; lexical rescue scans raw `page_content` (accent-sensitive!). | Match prefixed markers too; scan `metadata.get("text_search") or page_content` while keeping accented `page_content` for display. |
| `rebuild_bm25_pickle.py` | `L32–44` | **Bug:** only loads `folder / f"{folder.name}.md"` (skips multi-file folders like `local_store/sb/sb_01.md..sb_14.md`!); no `--check` flag; doesn't use `text_search`. | Support both single-file and multi-file (`*.md`) folders; add `--check` mode verifying sync against `local_store` & Qdrant counts; ensure BM25 indexes accent-stripped `text_search` while keeping accented `page_content` for display. |
| `build_corpus_lexicon.py` | `L29–37` | Extracts `[ऀ-ॿ]+` directly from `local_store/**/*.md` — accents (`॑`, `॒`) sit inside `U+0900–U+097F` and would create separate accented surface tokens that miss unaccented queries if not normalized! | Strip Vedic svaras when building `corpus_lexicon.pkl` keys/forms (matching `text_search`). |
| `src/utils/vedic_kg.py` | `L589` | Prompt mentions `(RV, SB, AB, PB, YV)`. | Per Rule 7, do **not** auto-seed KG from new texts (also guard background KG extraction in `agentic_rag.py:994` if needed so new texts / held-out parallel candidates don't leak into the inferred KG tier!). |
| `CLAUDE.md`, `GEMINI.md`, `README.md`, `NOTICE` | Corpus lists & "Not indexed" lines | List only the 7 existing corpora. | Update `NOTICE` *before* each tranche; update `CLAUDE.md`, `GEMINI.md`, `README.md` after each tranche lands. |
| **iOS citation files (`ios-portable`, read-only note)** | `Citations.swift`, `QueryAnalysis.swift`, `CitationValidator.swift`, `citation_split.py`, `make_validator_fixture.py` | Hardcode 7 corpus codes. | Documented here for later parity sync on `ios-portable`; **not modified on `corpus-expansion`**. |

---

## 5. Open Decisions for Owner Sign-Off (Stop Point 1)

1. **Citation formats & `chronology_name` values above:**
   - Are the canonical prefixes (`MS`, `KS`, `AVP`, `KB`, `GB`, `JB`, `JUB`, `TB`, `TA`, `BŚS`, `BĀU`, `ChU`, `Nir`, provisional `KapS`) approved?
   - For Layer 4 `chronology_name`: do you prefer distinct sub-genre names (`brahmana_prose`, `aranyaka`, `upanisad`) as proposed above, or a single `brahmana_prose` value across all of Layer 4?
2. **`docs/ios_data_licensing.md` on `corpus-expansion`:**
   - That file currently exists only on `ios-portable`, not on `translation-fixes`. Should I copy it from `ios-portable` onto `corpus-expansion` (without touching `ios-portable`) so Rule 2 updates stay in sync, or maintain a new copy here?
3. **Background KG extraction guard (Rule 7 & Rule 8):**
   - `agentic_rag.py:994` runs background `extract_and_store_facts()` on live queries. Should we add a guard so queries touching the new texts (or candidate held-out parallels) never write into the `inferred` KG tier until you review them?
4. **External diachronic map / layer legend:**
   - No diachronic map file exists in `vedic_rag`. If it lives in another folder/repo, let me know where so we can update its legend for Layer 5 when ready.
